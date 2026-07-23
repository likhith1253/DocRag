"""
Comprehensive Evaluation Framework for DocumentRAG

This framework provides detailed analysis of every stage of the pipeline
without modifying the system itself. It instruments the existing orchestrator
to collect detailed traces and generates comprehensive reports.

Usage:
    python eval/comprehensive_evaluator.py --dataset eval/dataset/ai_papers.json --output eval/results/comprehensive
"""

import os
import sys
import json
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import difflib

# Add parent directory to path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agents.orchestrator import answer, Orchestrator, LOGS_PATH
from storage.vector_store import VectorStoreManager
from storage.registry import get_registry
from retrieval.mmr_rerank import mmr_rerank
from retrieval.cross_encoder_rerank import rerank_cross_encoder


@dataclass
class PipelineStage:
    """Represents a single stage in the pipeline with timing and I/O."""
    name: str
    input_data: Any
    output_data: Any
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkInfo:
    """Detailed information about a retrieved chunk."""
    rank: int
    content: str
    vector_similarity: float
    cross_encoder_score: float
    mmr_score: float
    repository: str
    paper_title: str
    section: str
    page_start: int
    page_end: int
    chunk_type: str
    chunk_length: int
    eventually_selected: bool
    discarded: bool
    discard_reason: str = ""


@dataclass
class QuestionReport:
    """Comprehensive report for a single question."""
    question_id: str
    paper: str
    question: str
    question_type: str
    expected_answer: str
    
    # Pipeline trace
    pipeline_stages: List[PipelineStage] = field(default_factory=list)
    
    # Retrieval details
    retrieved_chunks: List[ChunkInfo] = field(default_factory=list)
    
    # Prompt analysis
    prompt_token_count: int = 0
    context_token_count: int = 0
    question_token_count: int = 0
    num_chunks: int = 0
    chunk_order: List[int] = field(default_factory=list)
    prompt_truncated: bool = False
    duplicate_chunks: int = 0
    
    # Generated answer
    raw_llm_answer: str = ""
    final_parsed_answer: str = ""
    answer_latency_ms: float = 0.0
    
    # Comparison metrics
    semantic_similarity: float = 0.0
    keyword_recall: float = 0.0
    keyword_precision: float = 0.0
    numerical_accuracy: float = 0.0
    entity_match: float = 0.0
    
    # Grounding analysis
    grounding_statements: List[Dict[str, Any]] = field(default_factory=list)
    grounding_score: float = 0.0
    
    # Failure analysis
    failure_category: str = ""
    failure_confidence: str = ""
    failure_evidence: str = ""
    
    # Scoring
    retrieval_quality: float = 0.0
    context_quality: float = 0.0
    grounding: float = 0.0
    answer_correctness: float = 0.0
    overall_score: float = 0.0
    
    # Improvement suggestions
    improvement_suggestion: str = ""
    expected_gain: str = ""


class ComprehensiveEvaluator:
    """Comprehensive evaluation framework for DocumentRAG."""
    
    def __init__(self, dataset_path: str, output_dir: str):
        self.dataset_path = dataset_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Load dataset
        with open(dataset_path, 'r', encoding='utf-8') as f:
            self.dataset = json.load(f)
        
        # Load expected answers if available
        self.expected_map = {}
        try:
            with open('eval/ai_papers_expected_answers.json', 'r', encoding='utf-8') as f:
                expected_list = json.load(f)
                for item in expected_list:
                    if item.get('id'):
                        self.expected_map[item['id']] = item
        except Exception:
            pass
        
        self.orch = Orchestrator()
        self.reports: List[QuestionReport] = []
    
    def _get_question_type(self, item: Dict) -> str:
        """Determine question type from category or question text."""
        category = item.get('category', '').lower()
        question = item.get('question', '').lower()
        
        type_mapping = {
            'main_contribution': 'Contribution',
            'methodology': 'Methodology',
            'experimental_setup': 'Experimental Setup',
            'results': 'Results',
            'hyperparameters': 'Hyperparameter',
        }
        
        if category in type_mapping:
            return type_mapping[category]
        
        # Analyze question text
        if any(word in question for word in ['table', 'figure', 'chart']):
            return 'Table'
        elif any(word in question for word in ['equation', 'formula', 'mathematical']):
            return 'Equation'
        elif any(word in question for word in ['how many', 'what is the', 'number', 'count', 'percentage']):
            return 'Numerical'
        elif any(word in question for word in ['compare', 'difference', 'versus', 'vs']):
            return 'Comparison'
        elif any(word in question for word in ['why', 'how', 'explain', 'describe']):
            return 'Reasoning'
        else:
            return 'Definition'
    
    def _instrument_pipeline(self, question: str, repo_id: str = None, filters: Dict = None) -> Tuple[str, Dict, List[PipelineStage]]:
        """
        Run the pipeline with instrumentation to capture all stages.
        Returns: (answer, response_dict, pipeline_stages)
        """
        stages = []
        total_start = time.perf_counter()
        
        # Stage 1: Repository Router
        t0 = time.perf_counter()
        registry = get_registry()
        
        if repo_id:
            selected_repos = [repo_id]
        else:
            from retrieval.repository_router import rank_repositories
            top_repos = rank_repositories(question, registry, top_k=3)
            selected_repos = top_repos
        
        t1 = time.perf_counter()
        stages.append(PipelineStage(
            name="Repository Router",
            input_data={"question": question, "repo_id": repo_id},
            output_data={"selected_repos": selected_repos},
            latency_ms=(t1 - t0) * 1000
        ))
        
        # Stage 2: Collection Selection
        t0 = time.perf_counter()
        collections = []
        for rid in selected_repos:
            repo = registry.get_repository(rid)
            if repo:
                collections.append({
                    "repo_id": rid,
                    "vector_collection": repo.vector_collection,
                    "name": repo.name
                })
        
        t1 = time.perf_counter()
        stages.append(PipelineStage(
            name="Collections Selected",
            input_data={"repos": selected_repos},
            output_data={"collections": collections},
            latency_ms=(t1 - t0) * 1000
        ))
        
        # Stage 3: Embedding Search (via orchestrator)
        # We'll capture this from the orchestrator response
        t0 = time.perf_counter()
        
        # Run the full orchestrator
        response = self.orch.answer(question, repo_id=repo_id, filters=filters)
        
        t1 = time.perf_counter()
        
        # Extract latency breakdown from response
        latency_breakdown = response.get('latency_breakdown', {})
        
        stages.append(PipelineStage(
            name="Embedding Search",
            input_data={"question": question},
            output_data={"query_embedding": "captured"},
            latency_ms=latency_breakdown.get('embedding_ms', 0)
        ))
        
        stages.append(PipelineStage(
            name="Vector Retrieval",
            input_data={"query_embedding": "captured"},
            output_data={"num_candidates": "captured"},
            latency_ms=latency_breakdown.get('vector_ms', 0)
        ))
        
        stages.append(PipelineStage(
            name="MMR Reranking",
            input_data={"candidates": "captured"},
            output_data={"mmr_scores": "captured"},
            latency_ms=latency_breakdown.get('mmr_ms', 0)
        ))
        
        stages.append(PipelineStage(
            name="Cross Encoder Reranking",
            input_data={"mmr_results": "captured"},
            output_data={"reranked_chunks": "captured"},
            latency_ms=latency_breakdown.get('reranker_ms', 0)
        ))
        
        stages.append(PipelineStage(
            name="Context Packing",
            input_data={"reranked_chunks": "captured"},
            output_data={"packed_context": "captured"},
            latency_ms=latency_breakdown.get('context_ms', 0)
        ))
        
        stages.append(PipelineStage(
            name="LLM Generation",
            input_data={"prompt": "captured"},
            output_data={"answer": response.get('answer', '')[:100]},
            latency_ms=latency_breakdown.get('llm_ms', 0)
        ))
        
        return response.get('answer', ''), response, stages
    
    def _extract_retrieved_chunks(self, question: str, response: Dict = None) -> List[ChunkInfo]:
        """Extract detailed chunk information from orchestrator response."""
        chunks = []
        
        try:
            # Try to get chunks from response
            if response and 'retrieved_chunks' in response:
                retrieved = response['retrieved_chunks']
            else:
                # Fall back to query logs
                if not os.path.exists(LOGS_PATH):
                    return chunks
                
                with open(LOGS_PATH, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get('question') == question:
                                retrieved = entry.get('retrieved_chunks', [])
                                break
                        except Exception:
                            continue
                    else:
                        return chunks
            
            # Build chunk info from retrieved chunks
            for idx, chunk in enumerate(retrieved[:20]):  # Top 20
                if isinstance(chunk, dict):
                    content = chunk.get('content', '')
                    metadata = chunk.get('metadata', {})
                    score = chunk.get('score', 0.0)
                elif hasattr(chunk, 'content'):
                    content = chunk.content
                    metadata = chunk.metadata if hasattr(chunk, 'metadata') else {}
                    score = chunk.score if hasattr(chunk, 'score') else 0.0
                else:
                    continue
                
                chunk_info = ChunkInfo(
                    rank=idx + 1,
                    content=content,
                    vector_similarity=score,  # Use as vector similarity
                    cross_encoder_score=metadata.get('cross_encoder_score', 0.0),
                    mmr_score=metadata.get('mmr_score', 0.0),
                    repository=metadata.get('repository', 'unknown'),
                    paper_title=metadata.get('paper_title', 'unknown'),
                    section=metadata.get('section', 'unknown'),
                    page_start=metadata.get('page_start', 0),
                    page_end=metadata.get('page_end', 0),
                    chunk_type=metadata.get('chunk_type', 'unknown'),
                    chunk_length=len(content),
                    eventually_selected=idx < 15,  # Assume top 15 are selected
                    discarded=idx >= 15,
                    discard_reason="Context limit" if idx >= 15 else ""
                )
                chunks.append(chunk_info)
                
        except Exception as e:
            print(f"Error extracting chunks: {e}")
            import traceback
            traceback.print_exc()
        
        return chunks
    
    def _compute_semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity using difflib (can be upgraded to embeddings)."""
        return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio() * 100
    
    def _compute_keyword_metrics(self, expected: str, generated: str) -> Tuple[float, float]:
        """Compute keyword recall and precision."""
        expected_words = set(w.lower() for w in re.findall(r'\b\w+\b', expected) if len(w) > 3)
        generated_words = set(w.lower() for w in re.findall(r'\b\w+\b', generated) if len(w) > 3)
        
        if not expected_words:
            return 0.0, 0.0
        
        recall = len(expected_words & generated_words) / len(expected_words)
        precision = len(expected_words & generated_words) / len(generated_words) if generated_words else 0.0
        
        return recall * 100, precision * 100
    
    def _compute_numerical_accuracy(self, expected: str, generated: str) -> float:
        """Extract and compare numerical values."""
        expected_numbers = re.findall(r'\d+\.?\d*', expected)
        generated_numbers = re.findall(r'\d+\.?\d*', generated)
        
        if not expected_numbers:
            return 100.0  # No numbers to compare
        
        if not generated_numbers:
            return 0.0
        
        matches = sum(1 for num in expected_numbers if num in generated_numbers)
        return (matches / len(expected_numbers)) * 100
    
    def _analyze_grounding(self, answer: str, chunks: List[ChunkInfo]) -> Tuple[float, List[Dict]]:
        """Analyze grounding of answer statements against retrieved chunks."""
        # Split answer into statements
        statements = [s.strip() for s in answer.split('.') if s.strip()]
        
        chunk_contents = [c.content.lower() for c in chunks]
        grounded_statements = []
        
        for stmt in statements:
            stmt_lower = stmt.lower()
            
            # Check if statement is supported by any chunk
            supported = False
            best_chunk = None
            best_similarity = 0.0
            
            for idx, chunk_content in enumerate(chunk_contents):
                similarity = difflib.SequenceMatcher(None, stmt_lower, chunk_content).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_chunk = chunks[idx] if idx < len(chunks) else None
            
            if best_similarity > 0.3:  # Threshold for support
                supported = True
            
            grounded_statements.append({
                "statement": stmt,
                "supported": supported,
                "chunk": best_chunk.content[:100] if best_chunk else "",
                "page": best_chunk.page_start if best_chunk else 0,
                "similarity": best_similarity,
                "is_hallucination": not supported
            })
        
        # Compute grounding score
        if grounded_statements:
            grounded_count = sum(1 for s in grounded_statements if s['supported'])
            grounding_score = (grounded_count / len(grounded_statements)) * 100
        else:
            grounding_score = 0.0
        
        return grounding_score, grounded_statements
    
    def _classify_failure(self, report: QuestionReport) -> Tuple[str, str, str]:
        """Classify failure category with confidence and evidence."""
        if report.overall_score >= 80:
            return "None", "High", "Answer is correct"
        
        evidence = []
        
        # Check grounding first (most critical)
        if report.grounding < 30:
            return "LLM Reasoning", "High", f"Very low grounding score ({report.grounding:.1f}) indicates significant hallucination - LLM is not using retrieved context"
        
        if report.grounding < 50:
            return "LLM Reasoning", "Medium", f"Low grounding score ({report.grounding:.1f}) indicates partial hallucination - LLM not fully grounded in retrieved context"
        
        # Check semantic similarity
        if report.semantic_similarity < 20:
            return "LLM Reasoning", "High", f"Very low semantic similarity ({report.semantic_similarity:.1f}) - LLM answer is semantically unrelated to expected answer"
        
        if report.semantic_similarity < 40:
            return "LLM Extraction", "Medium", f"Low semantic similarity ({report.semantic_similarity:.1f}) - LLM failed to extract correct information from context"
        
        # Check keyword recall
        if report.keyword_recall < 30:
            return "LLM Extraction", "Medium", f"Low keyword recall ({report.keyword_recall:.1f}) - LLM missing key concepts from expected answer"
        
        # Check retrieval quality
        if report.retrieval_quality < 50:
            return "Retrieval Issue", "High", f"Retrieval quality is low ({report.retrieval_quality:.1f}) - relevant chunks not retrieved or ranked poorly"
        
        # Check context quality
        if report.context_quality < 50:
            return "Context Packing", "High", f"Context quality is low ({report.context_quality:.1f}) - insufficient or poorly packed context"
        
        # Check numerical accuracy specifically
        if report.numerical_accuracy < 50:
            return "LLM Extraction", "Medium", f"Numerical accuracy is low ({report.numerical_accuracy:.1f}) - LLM failed to extract numerical values correctly"
        
        # Default for moderate failures
        if report.overall_score < 50:
            return "LLM Reasoning", "Medium", f"Multiple factors contributing to low overall score ({report.overall_score:.1f})"
        
        return "LLM Reasoning", "Low", f"Minor performance issues - overall score {report.overall_score:.1f}"
    
    def _compute_scores(self, report: QuestionReport) -> None:
        """Compute multi-dimensional scores based on available evidence."""
        # Retrieval quality: based on number of chunks and content relevance
        if report.retrieved_chunks:
            # Check if chunks contain relevant content
            relevant_chunks = 0
            for chunk in report.retrieved_chunks[:10]:
                # Check if chunk contains any keywords from question
                question_words = set(w.lower() for w in re.findall(r'\b\w+\b', report.question) if len(w) > 3)
                chunk_words = set(w.lower() for w in re.findall(r'\b\w+\b', chunk.content) if len(w) > 3)
                if question_words & chunk_words:  # Intersection
                    relevant_chunks += 1
            
            if report.num_chunks >= 10:
                report.retrieval_quality = (relevant_chunks / 10) * 100
            else:
                report.retrieval_quality = (relevant_chunks / max(1, report.num_chunks)) * 100
        else:
            report.retrieval_quality = 0.0
        
        # Context quality: based on number of chunks and duplicates
        if report.num_chunks >= 10 and report.duplicate_chunks == 0:
            report.context_quality = 100.0
        elif report.num_chunks >= 5:
            report.context_quality = 70.0
        elif report.num_chunks >= 3:
            report.context_quality = 50.0
        else:
            report.context_quality = 30.0
        
        # Grounding: from grounding analysis
        report.grounding = report.grounding_score
        
        # Answer correctness: combination of semantic similarity and numerical accuracy
        report.answer_correctness = (report.semantic_similarity * 0.6 + report.numerical_accuracy * 0.2 + report.keyword_recall * 0.2)
        
        # Overall score: weighted average
        weights = {
            'retrieval': 0.15,
            'context': 0.15,
            'grounding': 0.25,
            'answer': 0.45
        }
        
        report.overall_score = (
            report.retrieval_quality * weights['retrieval'] +
            report.context_quality * weights['context'] +
            report.grounding * weights['grounding'] +
            report.answer_correctness * weights['answer']
        )
    
    def _generate_improvement_suggestion(self, report: QuestionReport) -> None:
        """Generate improvement suggestion based on failure analysis."""
        if report.overall_score >= 80:
            report.improvement_suggestion = "No improvement needed"
            report.expected_gain = "None"
            return
        
        if report.retrieval_quality < 50:
            report.improvement_suggestion = "Improve retrieval by adjusting embedding model or increasing top-k"
            report.expected_gain = "High"
        elif report.grounding < 50:
            report.improvement_suggestion = "Improve prompt construction to encourage better grounding"
            report.expected_gain = "Medium"
        elif report.numerical_accuracy < 50:
            report.improvement_suggestion = "Enhance LLM extraction capability for numerical values"
            report.expected_gain = "Medium"
        elif report.semantic_similarity < 60:
            report.improvement_suggestion = "Improve context packing to include more relevant information"
            report.expected_gain = "Medium"
        else:
            report.improvement_suggestion = "General LLM reasoning improvement needed"
            report.expected_gain = "Low"
    
    def evaluate_question(self, item: Dict) -> QuestionReport:
        """Evaluate a single question comprehensively."""
        question_id = item.get('id', 'unknown')
        paper = item.get('paper', 'unknown')
        question = item.get('question', '')
        
        # Get expected answer
        expected = item.get('expected_answer', '')
        if not expected and question_id in self.expected_map:
            expected = self.expected_map[question_id].get('expected_answer', '')
        
        # Create report
        report = QuestionReport(
            question_id=question_id,
            paper=paper,
            question=question,
            question_type=self._get_question_type(item),
            expected_answer=expected
        )
        
        # Find repo_id for this paper
        repo_id = self._find_repo_for_file(paper)
        
        # Instrument pipeline
        start_time = time.perf_counter()
        answer_text, response, stages = self._instrument_pipeline(question, repo_id, {"file": paper})
        total_latency = (time.perf_counter() - start_time) * 1000
        
        report.pipeline_stages = stages
        report.raw_llm_answer = answer_text
        report.final_parsed_answer = answer_text
        report.answer_latency_ms = total_latency
        
        # Extract retrieved chunks
        report.retrieved_chunks = self._extract_retrieved_chunks(question, response)
        report.num_chunks = len([c for c in report.retrieved_chunks if c.eventually_selected])
        report.duplicate_chunks = self._count_duplicates(report.retrieved_chunks)
        
        # Compute comparison metrics
        report.semantic_similarity = self._compute_semantic_similarity(expected, answer_text)
        report.keyword_recall, report.keyword_precision = self._compute_keyword_metrics(expected, answer_text)
        report.numerical_accuracy = self._compute_numerical_accuracy(expected, answer_text)
        
        # Analyze grounding
        report.grounding_score, report.grounding_statements = self._analyze_grounding(answer_text, report.retrieved_chunks)
        
        # Classify failure
        report.failure_category, report.failure_confidence, report.failure_evidence = self._classify_failure(report)
        
        # Compute scores
        self._compute_scores(report)
        
        # Generate improvement suggestion
        self._generate_improvement_suggestion(report)
        
        return report
    
    def _find_repo_for_file(self, file_name: str) -> Optional[str]:
        """Find repository ID for a given file."""
        registry = get_registry()
        for rid, repo in registry.repositories.items():
            try:
                vman = VectorStoreManager(collection_name=repo.vector_collection)
                all_chunks = vman.get_all_chunks()
                for c in all_chunks:
                    if c.get('metadata', {}).get('file') == file_name:
                        return rid
            except Exception:
                continue
        return None
    
    def _count_duplicates(self, chunks: List[ChunkInfo]) -> int:
        """Count duplicate chunks based on content similarity."""
        duplicates = 0
        seen = []
        for chunk in chunks:
            for seen_chunk in seen:
                if difflib.SequenceMatcher(None, chunk.content, seen_chunk).ratio() > 0.9:
                    duplicates += 1
                    break
            seen.append(chunk.content)
        return duplicates
    
    def run(self) -> List[QuestionReport]:
        """Run comprehensive evaluation on all questions."""
        print(f"Starting comprehensive evaluation on {len(self.dataset)} questions...")
        
        for idx, item in enumerate(self.dataset):
            print(f"\n[{idx+1}/{len(self.dataset)}] Evaluating {item.get('id', 'unknown')}...")
            
            try:
                report = self.evaluate_question(item)
                self.reports.append(report)
                print(f"  Overall Score: {report.overall_score:.1f}/100")
                print(f"  Failure Category: {report.failure_category}")
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
        
        return self.reports
    
    def generate_report(self, report: QuestionReport) -> str:
        """Generate detailed markdown report for a single question."""
        lines = []
        
        # SECTION 1: Question Information
        lines.append("# SECTION 1: Question Information")
        lines.append(f"**Question ID**: {report.question_id}")
        lines.append(f"**Paper**: {report.paper}")
        lines.append(f"**Question Type**: {report.question_type}")
        lines.append(f"**Question**: {report.question}")
        lines.append(f"**Expected Answer**: {report.expected_answer}")
        lines.append("")
        
        # SECTION 2: Pipeline Trace
        lines.append("# SECTION 2: Pipeline Trace")
        for stage in report.pipeline_stages:
            lines.append(f"## {stage.name}")
            lines.append(f"- **Latency**: {stage.latency_ms:.2f}ms")
            lines.append(f"- **Input**: {str(stage.input_data)[:200]}")
            lines.append(f"- **Output**: {str(stage.output_data)[:200]}")
            lines.append("")
        lines.append("")
        
        # SECTION 3: Retrieval Details
        lines.append("# SECTION 3: Retrieval Details")
        lines.append(f"**Total Chunks Retrieved**: {len(report.retrieved_chunks)}")
        lines.append(f"**Chunks Selected**: {report.num_chunks}")
        lines.append("")
        
        for chunk in report.retrieved_chunks[:10]:  # Show top 10
            lines.append(f"### Rank {chunk.rank}")
            lines.append(f"- **Vector Similarity**: {chunk.vector_similarity:.4f}")
            lines.append(f"- **Cross Encoder Score**: {chunk.cross_encoder_score:.4f}")
            lines.append(f"- **MMR Score**: {chunk.mmr_score:.4f}")
            lines.append(f"- **Paper**: {chunk.paper_title}")
            lines.append(f"- **Section**: {chunk.section}")
            lines.append(f"- **Pages**: {chunk.page_start}-{chunk.page_end}")
            lines.append(f"- **Selected**: {chunk.eventually_selected}")
            lines.append(f"- **Discarded**: {chunk.discarded} ({chunk.discard_reason})")
            lines.append(f"- **Content Preview**: {chunk.content[:150]}...")
            lines.append("")
        lines.append("")
        
        # SECTION 4: Final Prompt
        lines.append("# SECTION 4: Final Prompt Analysis")
        lines.append(f"**Number of Chunks**: {report.num_chunks}")
        lines.append(f"**Duplicate Chunks**: {report.duplicate_chunks}")
        lines.append(f"**Prompt Truncated**: {report.prompt_truncated}")
        lines.append("")
        
        # SECTION 5: Generated Answer
        lines.append("# SECTION 5: Generated Answer")
        lines.append(f"**Raw LLM Answer**: {report.raw_llm_answer}")
        lines.append(f"**Latency**: {report.answer_latency_ms:.2f}ms")
        lines.append("")
        
        # SECTION 6: Expected Answer Comparison
        lines.append("# SECTION 6: Expected Answer Comparison")
        lines.append(f"**Semantic Similarity**: {report.semantic_similarity:.2f}/100")
        lines.append(f"**Keyword Recall**: {report.keyword_recall:.2f}/100")
        lines.append(f"**Keyword Precision**: {report.keyword_precision:.2f}/100")
        lines.append(f"**Numerical Accuracy**: {report.numerical_accuracy:.2f}/100")
        lines.append("")
        
        # SECTION 7: Grounding Analysis
        lines.append("# SECTION 7: Grounding Analysis")
        lines.append(f"**Grounding Score**: {report.grounding_score:.2f}/100")
        lines.append("")
        
        for stmt in report.grounding_statements[:5]:  # Show top 5
            status = "✓ SUPPORTED" if stmt['supported'] else "✗ HALLUCINATION"
            lines.append(f"### Statement: {stmt['statement'][:100]}...")
            lines.append(f"- **Status**: {status}")
            lines.append(f"- **Similarity**: {stmt['similarity']:.4f}")
            if stmt['supported']:
                lines.append(f"- **Source Chunk**: {stmt['chunk'][:100]}...")
                lines.append(f"- **Page**: {stmt['page']}")
            lines.append("")
        lines.append("")
        
        # SECTION 8: Failure Analysis
        lines.append("# SECTION 8: Failure Analysis")
        lines.append(f"**Failure Category**: {report.failure_category}")
        lines.append(f"**Confidence**: {report.failure_confidence}")
        lines.append(f"**Evidence**: {report.failure_evidence}")
        lines.append("")
        
        # SECTION 9: Scoring
        lines.append("# SECTION 9: Scoring")
        lines.append(f"**Retrieval Quality**: {report.retrieval_quality:.1f}/100")
        lines.append(f"**Context Quality**: {report.context_quality:.1f}/100")
        lines.append(f"**Grounding**: {report.grounding:.1f}/100")
        lines.append(f"**Answer Correctness**: {report.answer_correctness:.1f}/100")
        lines.append(f"**Semantic Similarity**: {report.semantic_similarity:.1f}/100")
        lines.append(f"**Numerical Accuracy**: {report.numerical_accuracy:.1f}/100")
        lines.append(f"**Overall Score**: {report.overall_score:.1f}/100")
        lines.append("")
        
        # SECTION 10: Improvement Suggestions
        lines.append("# SECTION 10: Improvement Suggestions")
        lines.append(f"**Suggestion**: {report.improvement_suggestion}")
        lines.append(f"**Expected Gain**: {report.expected_gain}")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_summary(self) -> str:
        """Generate final summary with averages and distributions."""
        if not self.reports:
            return "No reports generated."
        
        # Compute averages
        avg_retrieval = sum(r.retrieval_quality for r in self.reports) / len(self.reports)
        avg_context = sum(r.context_quality for r in self.reports) / len(self.reports)
        avg_semantic = sum(r.semantic_similarity for r in self.reports) / len(self.reports)
        avg_grounding = sum(r.grounding for r in self.reports) / len(self.reports)
        avg_numerical = sum(r.numerical_accuracy for r in self.reports) / len(self.reports)
        avg_answer = sum(r.answer_correctness for r in self.reports) / len(self.reports)
        avg_overall = sum(r.overall_score for r in self.reports) / len(self.reports)
        
        # Compute distributions
        distributions = {
            '90-100': sum(1 for r in self.reports if r.overall_score >= 90),
            '80-90': sum(1 for r in self.reports if 80 <= r.overall_score < 90),
            '70-80': sum(1 for r in self.reports if 70 <= r.overall_score < 80),
            '60-70': sum(1 for r in self.reports if 60 <= r.overall_score < 70),
            'Below 60': sum(1 for r in self.reports if r.overall_score < 60)
        }
        
        # Most common failures
        failure_counts = {}
        for r in self.reports:
            if r.failure_category and r.failure_category != "None":
                failure_counts[r.failure_category] = failure_counts.get(r.failure_category, 0) + 1
        
        most_common_failure = max(failure_counts.items(), key=lambda x: x[1]) if failure_counts else ("None", 0)
        
        lines = []
        lines.append("# COMPREHENSIVE EVALUATION SUMMARY")
        lines.append("")
        lines.append("## Average Scores")
        lines.append(f"- **Average Retrieval Score**: {avg_retrieval:.1f}/100")
        lines.append(f"- **Average Context Score**: {avg_context:.1f}/100")
        lines.append(f"- **Average Semantic Similarity**: {avg_semantic:.1f}/100")
        lines.append(f"- **Average Grounding**: {avg_grounding:.1f}/100")
        lines.append(f"- **Average Numerical Accuracy**: {avg_numerical:.1f}/100")
        lines.append(f"- **Average Answer Correctness**: {avg_answer:.1f}/100")
        lines.append(f"- **Average Overall Score**: {avg_overall:.1f}/100")
        lines.append("")
        
        lines.append("## Score Distribution")
        for range_name, count in distributions.items():
            percentage = (count / len(self.reports)) * 100
            lines.append(f"- **{range_name}**: {count} questions ({percentage:.1f}%)")
        lines.append("")
        
        lines.append("## Most Common Failure Category")
        lines.append(f"- **{most_common_failure[0]}**: {most_common_failure[1]} questions")
        lines.append("")
        
        lines.append("## Detailed Failure Breakdown")
        for failure, count in sorted(failure_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(self.reports)) * 100
            lines.append(f"- **{failure}**: {count} questions ({percentage:.1f}%)")
        lines.append("")
        
        return "\n".join(lines)
    
    def save_reports(self) -> None:
        """Save all reports to files."""
        # Save individual question reports
        for report in self.reports:
            filename = f"question_{report.question_id}.md"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.generate_report(report))
        
        # Save summary
        summary_path = os.path.join(self.output_dir, "summary.md")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_summary())
        
        # Save JSON for programmatic access
        json_path = os.path.join(self.output_dir, "results.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([r.__dict__ for r in self.reports], f, indent=2, default=str)
        
        print(f"\nReports saved to {self.output_dir}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Evaluation Framework for DocumentRAG")
    parser.add_argument('--dataset', default='eval/dataset/ai_papers.json', help='Path to dataset JSON')
    parser.add_argument('--output', default='eval/results/comprehensive', help='Output directory for reports')
    
    args = parser.parse_args()
    
    evaluator = ComprehensiveEvaluator(args.dataset, args.output)
    reports = evaluator.run()
    evaluator.save_reports()
    
    print(f"\nEvaluation complete. {len(reports)} questions evaluated.")


if __name__ == '__main__':
    main()
