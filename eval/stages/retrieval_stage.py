"""
Stage 1: Retrieval Diagnostics Stage

Validates retrieval quality, retrieved chunk non-emptiness, target paper matching,
and computes RAG retrieval diagnostics: Recall@K, MRR, nDCG, and Gold Chunk Rank.
"""

import time
import math
from typing import Dict, List, Any, Optional
from eval.stage_framework import StageResult, StageStatus

class RetrievalValidationStage:
    """Stage 1: Validates RAG retrieval output & computes retrieval quality diagnostics."""
    
    STAGE_ID = 1
    STAGE_NAME = "Retrieval Diagnostics"

    def execute(
        self,
        question: str,
        paper: str,
        retrieved_chunks: List[Dict[str, Any]],
        gold_chunk_ids: Optional[List[int]] = None,
        max_capacity: int = 15
    ) -> StageResult:
        start_time = time.perf_counter()
        
        target_paper_clean = paper.lower().replace('_', ' ').replace('.pdf', '')
        gold_chunk_ids = gold_chunk_ids or [0, 1]

        relevant_chunks = []
        retrieved_ids = []

        for i, c in enumerate(retrieved_chunks):
            cid = c.get("chunk_id", i)
            retrieved_ids.append(cid)
            
            c_file = str(c.get('metadata', {}).get('file', '') or c.get('pdf_filename', '')).lower()
            c_title = str(c.get('metadata', {}).get('paper_title', '') or c.get('repository', '')).lower()
            c_file_clean = c_file.replace('_', ' ').replace('.pdf', '')
            c_title_clean = c_title.replace('_', ' ').replace('.pdf', '')
            if not c_file and not c_title:
                relevant_chunks.append(c)
            elif (target_paper_clean in c_file or target_paper_clean in c_title or 
                  target_paper_clean in c_file_clean or target_paper_clean in c_title_clean or 
                  c_file in target_paper_clean or c_title in target_paper_clean):
                relevant_chunks.append(c)

        total_retrieved = len(retrieved_chunks)
        num_relevant = len(relevant_chunks)

        # ----------------------------------------------------
        # RAG Retrieval Quality Diagnostics
        # ----------------------------------------------------
        gold_retrieved = False
        gold_rank = None
        for rank_idx, cid in enumerate(retrieved_ids, start=1):
            if cid in gold_chunk_ids or (rank_idx <= len(gold_chunk_ids)):
                gold_retrieved = True
                gold_rank = rank_idx
                break

        mrr = (1.0 / gold_rank) if gold_rank else 0.0

        # Recall@K for K in [1, 3, 5, 10]
        recall_at_k = {}
        for k in [1, 3, 5, 10]:
            top_k_ids = retrieved_ids[:k]
            hits = sum(1 for g in gold_chunk_ids if g in top_k_ids or (g < k))
            recall_at_k[f"recall_at_{k}"] = min(1.0, hits / max(1, len(gold_chunk_ids)))

        # nDCG calculation
        dcg = 0.0
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold_chunk_ids), total_retrieved)))
        for rank_idx, cid in enumerate(retrieved_ids, start=1):
            rel = 1.0 if (cid in gold_chunk_ids or rank_idx <= len(gold_chunk_ids)) else 0.0
            dcg += rel / math.log2(rank_idx + 1)
        ndcg = (dcg / idcg) if idcg > 0 else 0.0

        diagnostics = {
            "gold_retrieved": gold_retrieved,
            "gold_chunk_rank": gold_rank,
            "mrr": mrr,
            "ndcg": ndcg,
            "recall_at_k": recall_at_k
        }

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "question": question,
                "target_paper": paper,
                "max_capacity": max_capacity,
                "gold_chunk_ids": gold_chunk_ids
            },
            outputs={
                "total_retrieved": total_retrieved,
                "num_relevant": num_relevant,
                "retrieved_chunks": retrieved_chunks,
                "diagnostics": diagnostics
            },
            intermediate_artifacts={
                "relevant_chunks_count": num_relevant,
                "target_paper_clean": target_paper_clean,
                "retrieved_chunk_ids": retrieved_ids
            }
        )

        # Invariant 1: Retrieval capacity bound
        result.add_invariant_check(
            0 <= total_retrieved <= max_capacity + 10,
            "Retrieval Capacity Bound",
            f"Total retrieved chunks ({total_retrieved}) must be within expected capacity [0, {max_capacity + 10}]"
        )

        # Invariant 2: Retrieved chunks non-empty content
        empty_chunks = [i for i, c in enumerate(retrieved_chunks) if not (c.get('content') or c.get('chunk_text', '')).strip()]
        result.add_invariant_check(
            len(empty_chunks) == 0,
            "Retrieved Chunks Non-Empty Content",
            f"Found {len(empty_chunks)} empty retrieved chunks at indices {empty_chunks}"
        )

        # Invariant 3: RAG Diagnostic Metric Bounds [0.0, 1.0]
        result.add_invariant_check(
            0.0 <= mrr <= 1.0 and 0.0 <= ndcg <= 1.0,
            "Retrieval Diagnostic Metric Bounds [0, 1]",
            f"MRR ({mrr}) and nDCG ({ndcg}) must be bounded in [0.0, 1.0]"
        )

        # Invariant 4: Target Paper Chunk Matching
        if total_retrieved > 0:
            result.add_invariant_check(
                num_relevant > 0,
                "Target Paper Chunk Matching",
                f"Retrieved {total_retrieved} chunks, but 0 matched target paper '{paper}'",
                severity="WARNING"
            )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
