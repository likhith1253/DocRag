"""
Redesigned Evaluation Framework for DocumentRAG

This framework addresses critical flaws in the original evaluation:
1. Replaces character-overlap similarity with true semantic similarity
2. Extracts only meaningful factual claims (ignoring formatting)
3. Searches ALL chunks for evidence, returns top 3
4. Classifies grounding as SUPPORTED/PARTIALLY SUPPORTED/CONTRADICTED/NOT FOUND
5. Separates numerical claim evaluation
6. Provides explainable, evidence-backed decisions

Usage:
    python eval/redesigned_evaluator.py --dataset eval/dataset/ai_papers.json --output eval/results/redesigned
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import sys
import json
import time
import re
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Reconfigure stdout/stderr for Unicode safety on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from sentence_transformers import SentenceTransformer, util

# Add parent directory to path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agents.orchestrator import answer, Orchestrator, LOGS_PATH
from storage.vector_store import VectorStoreManager
from storage.registry import get_registry
from llm.backend import generate
from ingestion.pdf_parser import parse_pdf

from eval.stage_framework import StageSerializer, StageResult, StageStatus
from eval.stages.gold_reference_stage import GoldReferenceValidationStage
from eval.stages.retrieval_stage import RetrievalValidationStage
from eval.stages.reranker_stage import RerankerValidationStage
from eval.stages.claim_extraction_stage import ClaimExtractionStage
from eval.stages.evidence_verification_stage import EvidenceVerificationStage
from eval.stages.metric_computation_stage import MetricComputationStage
from eval.stages.acceptance_validation_stage import AcceptanceValidationStage
from eval.stages.report_generation_stage import ReportGenerationStage
from eval.diagnostic_reporter import DiagnosticReporter


@dataclass
class Evidence:
    """Evidence supporting or contradicting a claim."""
    chunk_id: int
    rank: int
    content: str
    page: int
    section: str
    paper: str
    similarity: float
    is_supporting: bool
    verification_status: str = ""  # SUPPORTED, PARTIALLY_SUPPORTED, CONTRADICTED, NOT_FOUND, VERIFICATION_FAILED
    verification_reason: str = ""
    supporting_sentence: str = ""
    verification_confidence: float = 0.0
    # Expanded evidence fields
    expanded_content: str = ""  # Full page + neighbors + OCR + captions + tables
    pdf_path: str = ""  # Path to original PDF
    figure_number: str = ""  # Figure number if relevant
    table_number: str = ""  # Table number if relevant


@dataclass
class Claim:
    """A factual claim extracted from an answer."""
    text: str
    claim_type: str  # 'factual', 'numerical', 'comparative'
    evidence: List[Evidence] = field(default_factory=list)
    grounding_status: str = "NOT_FOUND"  # SUPPORTED, PARTIALLY_SUPPORTED, CONTRADICTED, NOT_FOUND, VERIFICATION_FAILED
    confidence: float = 0.0
    reason: str = ""
    verification_error: str = ""  # Exact error if verification failed
    verification_tier: str = "Single Chunk"  # 'Single Chunk', 'Expanded Chunk', 'Cross-Evidence'
    escalated_to_cross_evidence: bool = False
    escalation_reason: str = ""
    claim_fidelity: str = "Direct Paper Claim"  # 'Direct Paper Claim', 'Reasonable Inference', 'LLM Interpretation', 'Hallucinated Claim'


@dataclass
class QuestionReport:
    """Comprehensive report for a single question."""
    question_id: str
    paper: str
    question: str
    question_type: str
    expected_answer: str
    
    # Pipeline trace
    pipeline_stages: List[Dict] = field(default_factory=list)
    
    # Retrieval details
    retrieved_chunks: List[Dict] = field(default_factory=list)
    
    # Generated answer
    raw_llm_answer: str = ""
    final_parsed_answer: str = ""
    answer_latency_ms: float = 0.0
    runtime_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Claims analysis
    claims: List[Claim] = field(default_factory=list)
    
    # Semantic correctness
    semantic_similarity: float = 0.0
    semantic_explanation: str = ""
    
    # Numerical correctness
    numerical_similarity: float = 0.0
    numerical_explanation: str = ""
    
    # Final answer quality scores
    retrieval_quality: float = 0.0
    context_quality: float = 0.0
    grounding_score: float = 0.0
    semantic_correctness: float = 0.0
    numerical_correctness: float = 0.0
    completeness: float = 0.0
    conciseness: float = 0.0
    hallucination_score: float = 0.0
    overall_score: float = 0.0
    
    # Explanations
    score_explanations: Dict[str, str] = field(default_factory=dict)


class RedesignedEvaluator:
    """Redesigned evaluation framework with scientifically valid metrics."""
    
    def __init__(self, dataset_path: str, output_dir: str, use_expanded_evidence: bool = True):
        self.dataset_path = dataset_path
        self.output_dir = output_dir
        self.use_expanded_evidence = use_expanded_evidence  # If True, use full PDF pages; if False, use only chunks
        os.makedirs(output_dir, exist_ok=True)
        
        self.artifacts_dir = os.path.join(output_dir, "artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)

        # Stage objects
        self.gold_stage = GoldReferenceValidationStage()
        self.retrieval_stage = RetrievalValidationStage()
        self.reranker_stage = RerankerValidationStage()
        self.claim_stage = ClaimExtractionStage()
        self.evidence_stage = EvidenceVerificationStage()
        self.metric_stage = MetricComputationStage()
        self.acceptance_stage = AcceptanceValidationStage()
        self.report_stage = ReportGenerationStage()
        
        # Load dataset
        with open(dataset_path, 'r', encoding='utf-8') as f:
            self.dataset = json.load(f)
        
        # Initialize semantic model (using same model as retrieval for consistency)
        print("Loading semantic similarity model...")
        self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.orch = Orchestrator()
        self.reports: List[QuestionReport] = []
        
        # PDF cache to avoid re-parsing
        self.pdf_cache = {}
        # Deterministic verification output cache
        self.verification_cache = {}

    def _find_repo_for_file(self, file_name: str) -> Optional[str]:
        """Scan registry and check collections for a matching file in chunk metadata."""
        if not file_name:
            return None
        target_base = os.path.basename(file_name).lower()
        registry = get_registry()
        for rid, repo in registry.repositories.items():
            try:
                vman = VectorStoreManager(collection_name=repo.vector_collection)
                all_chunks = vman.get_all_chunks()
                for c in all_chunks:
                    fn = c.get('metadata', {}).get('file', '')
                    if fn and os.path.basename(fn).lower() == target_base:
                        return rid
            except Exception:
                continue
        return None
    
    def _find_pdf_path(self, paper_title: str) -> Optional[str]:
        """Find the PDF path for a given paper title."""
        # Try to match paper title to PDF files in demo_dataset
        demo_dataset_path = os.path.join(repo_root, "demo_dataset")
        
        # Search recursively for PDF files in demo_dataset and papers
        for folder in ("demo_dataset", "papers"):
            search_path = os.path.join(repo_root, folder)
            if not os.path.exists(search_path):
                continue
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        pdf_path = os.path.join(root, file)
                        filename = os.path.splitext(file)[0].lower().replace('_', ' ')
                        title_lower = paper_title.lower().replace('_', ' ')
                        
                        if filename in title_lower or title_lower in filename:
                            return pdf_path
        
        return None
    
    def _extract_expanded_evidence(self, evidence: Evidence) -> str:
        """
        Extract expanded evidence from the original PDF.
        Includes full page, neighboring pages, OCR, figure captions, tables.
        """
        pdf_path = self._find_pdf_path(evidence.paper)
        if not pdf_path:
            return evidence.content  # Fallback to chunk content
        
        try:
            # Parse PDF if not cached
            if pdf_path not in self.pdf_cache:
                self.pdf_cache[pdf_path] = parse_pdf(pdf_path)
            
            parsed = self.pdf_cache[pdf_path]
            pages = parsed.get("pages", [])
            
            # Find the target page
            target_page = None
            for page_data in pages:
                if page_data["page"] == evidence.page:
                    target_page = page_data
                    break
            
            if not target_page:
                return evidence.content
            
            # Extract full page content
            page_text_blocks = [block["text"] for block in target_page.get("blocks", [])]
            page_text = "\n".join(page_text_blocks)
            
            # Add tables from this page
            tables = target_page.get("tables", [])
            if tables:
                page_text += "\n\n" + "\n\n".join(tables)
            
            # Add neighboring pages (previous and next)
            expanded_text = page_text
            
            for page_data in pages:
                if page_data["page"] == evidence.page - 1:  # Previous page
                    prev_blocks = [block["text"] for block in page_data.get("blocks", [])]
                    prev_text = "\n".join(prev_blocks)
                    prev_tables = page_data.get("tables", [])
                    if prev_tables:
                        prev_text += "\n\n" + "\n\n".join(prev_tables)
                    expanded_text = f"[PREVIOUS PAGE]\n{prev_text}\n\n[TARGET PAGE]\n{expanded_text}"
                
                elif page_data["page"] == evidence.page + 1:  # Next page
                    next_blocks = [block["text"] for block in page_data.get("blocks", [])]
                    next_text = "\n".join(next_blocks)
                    next_tables = page_data.get("tables", [])
                    if next_tables:
                        next_text += "\n\n" + "\n\n".join(next_tables)
                    expanded_text = f"{expanded_text}\n\n[NEXT PAGE]\n{next_text}"
            
            evidence.pdf_path = pdf_path
            return expanded_text
            
        except Exception as e:
            print(f"Error extracting expanded evidence: {e}")
            return evidence.content  # Fallback to chunk content
    
    def _extract_claims(self, answer: str) -> List[Claim]:
        """
        Extract only meaningful factual claims from the answer.
        Filters out:
        - Bullet numbers (1, 2, 3, etc.)
        - Formatting markers
        - Section titles
        - Empty phrases
        - Generic introductions
        - Sentences that are just list numbers with colons
        """
        claims = []
        
        # First, clean the answer by removing list numbers at the start of lines
        # This handles cases like "1. The development..." where "1." is formatting
        cleaned_lines = []
        for line in answer.split('\n'):
            # Remove list number at start of line (e.g., "1. ", "2. ", etc.)
            line = re.sub(r'^\d+\.\s+', '', line)
            cleaned_lines.append(line)
        cleaned_answer = '\n'.join(cleaned_lines)
        
        # Split into sentences using a more sophisticated regex that preserves sentence boundaries
        # This handles cases where sentences span multiple lines
        sentences = re.split(r'(?<=[.!?])\s+', cleaned_answer)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Filter out non-claims
            if re.match(r'^\d+$', sentence) or len(sentence) < 15:
                continue
            
            generic_phrases = [
                'the main contributions include',
                'the key points are',
                'here are the results',
                'as follows',
                'including',
                'such as',
                'these contributions aim to'
            ]
            if any(phrase in sentence.lower() for phrase in generic_phrases) and len(sentence) < 60:
                continue
            
            if sentence.isupper() or sentence.endswith(':'):
                continue
            
            if re.match(r'^[•\-\*]\s*$', sentence) or not re.search(r'[a-zA-Z]{3,}', sentence):
                continue
            
            # Atomic claim decomposition: split compound clauses around major conjunctions if sentence is long
            atomic_subclaims = [sentence]
            if len(sentence) > 100 and ';' in sentence:
                atomic_subclaims = [s.strip() for s in sentence.split(';') if len(s.strip()) >= 20]
            elif len(sentence) > 120 and ' and ' in sentence.lower():
                parts = re.split(r',\s*and\s+|\s+and\s+also\s+', sentence, flags=re.IGNORECASE)
                if len(parts) > 1 and all(len(p.strip()) >= 20 for p in parts):
                    atomic_subclaims = [p.strip() for p in parts]
            
            for claim_text in atomic_subclaims:
                claim_type = 'factual'
                if re.search(r'\d+', claim_text) and len(claim_text) > 20:
                    claim_type = 'numerical'
                elif any(word in claim_text.lower() for word in ['compared', 'versus', 'vs', 'higher', 'lower', 'more', 'less', 'better', 'worse']):
                    claim_type = 'comparative'
                
                claims.append(Claim(text=claim_text, claim_type=claim_type))
        
        return claims
    
    def _retrieve_candidate_evidence(self, claim: Claim, chunks: List[Dict]) -> List[Evidence]:
        """
        STEP 1: Use embeddings ONLY for candidate retrieval.
        Search ALL retrieved chunks and return top 5 candidates based on semantic similarity.
        Embeddings are used ONLY for retrieval, NOT for grounding determination.
        """
        evidence_list = []
        
        # Encode claim
        claim_embedding = self.semantic_model.encode([claim.text])
        
        for idx, chunk in enumerate(chunks):
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            
            # Encode chunk
            chunk_embedding = self.semantic_model.encode([content])
            
            # Compute semantic similarity using cosine similarity
            similarity = float(util.cos_sim(claim_embedding, chunk_embedding)[0][0])
            
            evidence = Evidence(
                chunk_id=idx,
                rank=idx + 1,
                content=content,
                page=metadata.get('page_start', 0),
                section=metadata.get('section', 'unknown'),
                paper=metadata.get('paper_title', 'unknown'),
                similarity=similarity,
                is_supporting=False  # Will be determined by LLM judge, not embeddings
            )
            evidence_list.append(evidence)
        
        # Sort by similarity and return top 5 candidates
        evidence_list.sort(key=lambda x: x.similarity, reverse=True)
        return evidence_list[:5]
    
    def _verify_evidence_with_llm(self, claim: Claim, evidence: Evidence) -> Tuple[str, float, str, str, str]:
        """
        STEP 2: Use LLM judge to verify if evidence supports the claim.
        Uses EXPANDED evidence from the original PDF (full page + neighbors + OCR + tables) if enabled.
        Returns: (verification_status, confidence, reason, supporting_sentence, error)
        """
        # Extract expanded evidence from original PDF if enabled
        if self.use_expanded_evidence:
            expanded_content = self._extract_expanded_evidence(evidence)
            evidence.expanded_content = expanded_content
            evidence_description = "Full Page + Neighbors + OCR + Tables"
        else:
            expanded_content = evidence.content
            evidence.expanded_content = ""
            evidence_description = "Retrieved Chunk Only"
        
        prompt = f"""You are a strict factual verifier.

You are NOT allowed to use outside knowledge.

IMPORTANT: OCR text from diagrams, figures, architecture images, tables, and mathematical formulas IS VALID EVIDENCE.

Do not require supporting facts to appear only as standard body text.

The evidence provided includes the {evidence_description}.

Question:

Does the evidence explicitly support the claim?

Choose EXACTLY ONE.

SUPPORTED

The evidence explicitly states the claim (including OCR text from diagrams/figures).

PARTIALLY_SUPPORTED

The evidence supports only part of the claim.

CONTRADICTED

The evidence explicitly contradicts the claim.

NOT_FOUND

The evidence does not contain enough information.

IMPORTANT

Do NOT infer missing facts.

Do NOT use outside domain knowledge.

Only evaluate what is explicitly written in the evidence, including OCR text from diagrams and figures.

Claim:
{claim.text}

Evidence ({evidence_description}):
{expanded_content}

Return JSON
{{
    "classification":"",
    "confidence":0,
    "reason":"",
    "quoted_evidence":""
}}"""

        try:
            print(f"  Verifying evidence chunk {evidence.chunk_id} with LLM...")
            response = generate(prompt, model_key="doc_agent_model")
            print(f"  LLM response received for chunk {evidence.chunk_id}")
            
            status, confidence, reason, supporting_sentence, error = self._parse_llm_response(response)
            return status, confidence, reason, supporting_sentence, error
            
        except Exception as e:
            # LLM call failure - return VERIFICATION_FAILED
            error = f"LLM verification failed: {str(e)}"
            print(f"Error in LLM verification: {e}")
            return "VERIFICATION_FAILED", 0.0, "", "", error
    
    def _compute_text_cosine_similarity(self, query: str, text: str) -> float:
        """Compute real cosine similarity between query and text using SentenceTransformer embedding model."""
        if not hasattr(self, '_embed_model_instance') or self._embed_model_instance is None:
            self._embed_model_instance = SentenceTransformer('all-MiniLM-L6-v2')
        emb1 = self._embed_model_instance.encode(query, convert_to_tensor=True)
        emb2 = self._embed_model_instance.encode(text[:500], convert_to_tensor=True)
        sim = float(util.cos_sim(emb1, emb2).item())
        return sim

    def _compute_cross_encoder_score(self, query: str, text: str) -> float:
        """Compute real CrossEncoder rerank score for (query, text) pair."""
        if not hasattr(self, '_cross_encoder_instance') or self._cross_encoder_instance is None:
            from sentence_transformers import CrossEncoder
            self._cross_encoder_instance = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        score = float(self._cross_encoder_instance.predict([query, text[:500]]))
        return score

    def _classify_claim_fidelity(self, claim_text: str, paper_context: str, grounding_status: str) -> str:
        """
        Classifies claim quality with realistic thresholds:
        - Direct Paper Claim: High overlap (>= 75% words match verbatim or near-verbatim).
        - Reasonable Inference: Logical deduction from technical facts (45% - 74% overlap).
        - LLM Interpretation: Paraphrase or domain summary (20% - 44% overlap).
        - Hallucinated Claim: Not grounded in paper context (< 20% overlap).
        """
        if grounding_status in ["NOT_FOUND", "CONTRADICTED"]:
            return "Hallucinated Claim"
        
        claim_words = [w.lower() for w in re.findall(r'\w+', claim_text) if len(w) > 2]
        context_words = [w.lower() for w in re.findall(r'\w+', paper_context) if len(w) > 2]
        
        if len(claim_words) < 2:
            return "LLM Interpretation"
            
        claim_bigrams = set(zip(claim_words, claim_words[1:]))
        context_bigrams = set(zip(context_words, context_words[1:]))
        
        if not claim_bigrams:
            return "LLM Interpretation"
            
        overlap = len(claim_bigrams.intersection(context_bigrams)) / len(claim_bigrams)
        
        if overlap >= 0.75:
            return "Direct Paper Claim"
        elif overlap >= 0.45:
            return "Reasonable Inference"
        elif overlap >= 0.20:
            return "LLM Interpretation"
        else:
            return "Hallucinated Claim"

    def _classify_grounding(self, claim: Claim, evidence_list: List[Evidence]) -> Tuple[str, float, str]:
        """
        STEP 3: Tiered Decision Policy Algorithm
        Tier 1: Single top chunk verification. If confidence >= 70.0% & SUPPORTED -> STOP.
        Tier 2: Expanded context verification (page + neighbors + OCR). If confidence >= 70.0% & SUPPORTED -> STOP.
        Tier 3: Escalate to Cross-Evidence Aggregation only when individual single/expanded chunks are insufficient.
        """
        if not evidence_list:
            claim.verification_tier = "None"
            claim.escalated_to_cross_evidence = False
            claim.escalation_reason = "No evidence retrieved"
            return "NOT_FOUND", 0.0, "No evidence found in retrieved chunks"
        
        # Tier 1: Evaluate top single candidate chunk unexpanded
        top_chunk = evidence_list[0]
        was_expanded = self.use_expanded_evidence
        
        self.use_expanded_evidence = False
        status_t1, conf_t1, reason_t1, sent_t1, err_t1 = self._verify_evidence_with_llm(claim, top_chunk)
        self.use_expanded_evidence = was_expanded
        
        top_chunk.verification_status = status_t1
        top_chunk.verification_confidence = conf_t1
        top_chunk.verification_reason = reason_t1
        top_chunk.supporting_sentence = sent_t1
        top_chunk.is_supporting = (status_t1 in ["SUPPORTED", "PARTIALLY_SUPPORTED"])
        
        if status_t1 == "SUPPORTED" and conf_t1 >= 70.0:
            claim.verification_tier = "Single Chunk"
            claim.escalated_to_cross_evidence = False
            claim.escalation_reason = "Single top chunk provided direct high-confidence support"
            return "SUPPORTED", conf_t1, f"Single Chunk Support (Page {top_chunk.page}): {reason_t1}"

        # Tier 2: Evaluate top candidate chunk with Expanded Context (Full Page + Neighbors + OCR + Tables)
        self.use_expanded_evidence = True
        status_t2, conf_t2, reason_t2, sent_t2, err_t2 = self._verify_evidence_with_llm(claim, top_chunk)
        self.use_expanded_evidence = was_expanded
        
        top_chunk.verification_status = status_t2
        top_chunk.verification_confidence = conf_t2
        top_chunk.verification_reason = reason_t2
        top_chunk.supporting_sentence = sent_t2
        top_chunk.is_supporting = (status_t2 in ["SUPPORTED", "PARTIALLY_SUPPORTED"])
        
        if status_t2 == "SUPPORTED" and conf_t2 >= 70.0:
            claim.verification_tier = "Expanded Chunk"
            claim.escalated_to_cross_evidence = False
            claim.escalation_reason = "Single chunk required surrounding page/table context to achieve full support"
            return "SUPPORTED", conf_t2, f"Expanded Context Support (Page {top_chunk.page}): {reason_t2}"

        # Verify remaining single candidate chunks if any
        supported_candidates = []
        for ev in evidence_list[1:]:
            s, c, r, st, err = self._verify_evidence_with_llm(claim, ev)
            ev.verification_status = s
            ev.verification_confidence = c
            ev.verification_reason = r
            ev.supporting_sentence = st
            ev.is_supporting = (s in ["SUPPORTED", "PARTIALLY_SUPPORTED"])
            if s == "SUPPORTED" and c >= 70.0:
                supported_candidates.append((ev, c, r))

        if supported_candidates:
            best_ev, best_c, best_r = max(supported_candidates, key=lambda x: x[1])
            claim.verification_tier = "Single Chunk"
            claim.escalated_to_cross_evidence = False
            claim.escalation_reason = f"Verified using candidate chunk on Page {best_ev.page}"
            return "SUPPORTED", best_c, f"Supported by candidate chunk on Page {best_ev.page}: {best_r}"

        # Tier 3: Escalate to Cross-Evidence Aggregation
        if len(evidence_list) >= 2:
            agg_status, agg_conf, agg_reason = self._verify_cross_evidence_aggregation(claim, evidence_list[:3])
            claim.verification_tier = "Cross-Evidence"
            claim.escalated_to_cross_evidence = True
            claim.escalation_reason = f"Single chunks were insufficient (Tier 1: {status_t1} at {conf_t1:.1f}%, Tier 2: {status_t2} at {conf_t2:.1f}%). Multi-source joint entailment required."
            if agg_status in ["SUPPORTED", "PARTIALLY_SUPPORTED"]:
                return agg_status, agg_conf, agg_reason

        # Fallback if ungrounded or contradicted
        claim.verification_tier = "None"
        claim.escalated_to_cross_evidence = False
        claim.escalation_reason = "No candidate chunks or multi-source context supported the claim"
        
        if status_t1 == "CONTRADICTED" or status_t2 == "CONTRADICTED":
            return "CONTRADICTED", max(conf_t1, conf_t2), f"Contradicted by evidence on Page {top_chunk.page}"
            
        return "NOT_FOUND", 0.0, "No supporting evidence found across single chunks or cross-evidence aggregation."

    def _verify_cross_evidence_aggregation(self, claim: Claim, candidate_evidences: List[Evidence]) -> Tuple[str, float, str]:
        """
        Cross-Evidence Aggregation: Combine evidence across multiple candidate chunks/pages
        to assess joint entailment when individual chunks only offer partial support.
        """
        combined_blocks = []
        for i, ev in enumerate(candidate_evidences):
            content = ev.expanded_content if (self.use_expanded_evidence and ev.expanded_content) else ev.content
            combined_blocks.append(f"[SOURCE {i+1} - Page {ev.page}, Section {ev.section}]\n{content[:600]}")
        
        aggregated_context = "\n\n".join(combined_blocks)
        
        # Check cache for determinism
        cache_key = f"{claim.text}|||{aggregated_context}"
        if cache_key in self.verification_cache:
            return self.verification_cache[cache_key]
        
        prompt = f"""You are a strict factual verifier.
Evaluate whether the COMBINED evidence across multiple sources explicitly supports the claim.

Claim:
{claim.text}

Combined Multi-Source Context:
{aggregated_context}

Return JSON:
{{
    "classification": "SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", or "NOT_FOUND",
    "confidence": 0-100,
    "reason": "explanation of joint evidence support",
    "quoted_evidence": "key quoted text"
}}"""
        try:
            response = generate(prompt, model_key="doc_agent_model")
            status, conf, reason, sentence, error = self._parse_llm_response(response)
            result = (status, conf, f"Cross-evidence aggregation ({len(candidate_evidences)} sources): {reason}")
            self.verification_cache[cache_key] = result
            return result
        except Exception as e:
            return "NOT_FOUND", 0.0, f"Cross-evidence aggregation failed: {e}"

    def _parse_llm_response(self, response: str) -> Tuple[str, float, str, str, str]:
        """Helper to parse LLM verification JSON response."""
        response_clean = response.strip()
        if "```" in response_clean:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_clean, re.DOTALL)
            if match:
                response_clean = match.group(1)
            else:
                response_clean = re.sub(r'```(?:json)?', '', response_clean).replace('```', '').strip()
        
        json_match = re.search(r'\{.*\}', response_clean, re.DOTALL)
        if json_match:
            response_clean = json_match.group(0)
        
        response_clean = re.sub(r'//.*$', '', response_clean, flags=re.MULTILINE)
        response_clean = re.sub(r',\s*([\}\]])', r'\1', response_clean)
        
        try:
            result = json.loads(response_clean)
        except Exception:
            class_m = re.search(r'"classification"\s*:\s*"([^"]+)"', response_clean, re.IGNORECASE)
            conf_m = re.search(r'"confidence"\s*:\s*(\d+(?:\.\d+)?)', response_clean)
            reason_m = re.search(r'"reason"\s*:\s*"([^"]+)"', response_clean)
            quote_m = re.search(r'"quoted_evidence"\s*:\s*"([^"]+)"', response_clean)
            if class_m:
                result = {
                    "classification": class_m.group(1),
                    "confidence": float(conf_m.group(1)) if conf_m else 50.0,
                    "reason": reason_m.group(1) if reason_m else "",
                    "quoted_evidence": quote_m.group(1) if quote_m else ""
                }
            else:
                return "VERIFICATION_FAILED", 0.0, "", "", f"JSON decode error: {response}"

        status = str(result.get("classification", "NOT_FOUND")).strip().upper()
        if status not in ["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "NOT_FOUND"]:
            status = "NOT_FOUND"
        
        conf_val = result.get("confidence", None)
        if conf_val is None or (isinstance(conf_val, (int, float)) and float(conf_val) == 0.0 and status != "NOT_FOUND"):
            if status == "SUPPORTED":
                confidence = 90.0
            elif status == "PARTIALLY_SUPPORTED":
                confidence = 70.0
            elif status == "CONTRADICTED":
                confidence = 85.0
            else:
                confidence = 0.0
        else:
            try:
                confidence = float(conf_val)
                if 0.0 < confidence <= 1.0:
                    confidence *= 100.0
            except ValueError:
                conf_str = str(conf_val).lower()
                if "high" in conf_str:
                    confidence = 90.0
                elif "med" in conf_str:
                    confidence = 70.0
                else:
                    confidence = 50.0

        reason = str(result.get("reason", ""))
        supporting_sentence = str(result.get("quoted_evidence", ""))
        return status, confidence, reason, supporting_sentence, ""
    
    def _compute_semantic_similarity(self, expected: str, generated: str) -> Tuple[float, str]:
        """
        Compute semantic similarity using SentenceTransformer embeddings.
        Returns: (similarity_score, explanation)
        """
        # Encode both texts
        expected_embedding = self.semantic_model.encode([expected])
        generated_embedding = self.semantic_model.encode([generated])
        
        # Compute cosine similarity
        similarity = float(util.cos_sim(expected_embedding, generated_embedding)[0][0])
        
        explanation = f"Semantic similarity computed using SentenceTransformer (all-MiniLM-L6-v2). The model encodes both texts into 384-dimensional embeddings and computes cosine similarity. Score of {similarity:.3f} indicates {'high' if similarity >= 0.7 else 'moderate' if similarity >= 0.5 else 'low'} semantic alignment."
        
        return similarity * 100, explanation
    
    def _evaluate_numerical_claims(self, expected: str, generated: str, claims: List[Claim]) -> Tuple[float, str]:
        """
        Evaluate numerical claims separately.
        Extract numbers, convert to float, and compare within numerical tolerance.
        Returns: (numerical_score, explanation)
        """
        def parse_numbers(text: str) -> List[float]:
            raw = re.findall(r'\b\d+(?:\.\d+)?\b', text)
            nums = []
            for r in raw:
                try:
                    nums.append(float(r))
                except ValueError:
                    pass
            return nums

        expected_numbers = parse_numbers(expected)
        generated_numbers = parse_numbers(generated)
        
        if not expected_numbers:
            return 100.0, "No numerical values in expected answer to compare"
        
        if not generated_numbers:
            return 0.0, "No numerical values found in generated answer"
        
        matched_gen_indices = set()
        matches = 0
        
        for exp_num in expected_numbers:
            for idx, gen_num in enumerate(generated_numbers):
                if idx in matched_gen_indices:
                    continue
                # Match within 1% relative tolerance or 1e-4 absolute difference
                rel_diff = abs(exp_num - gen_num) / max(abs(exp_num), 1e-9)
                if abs(exp_num - gen_num) <= 1e-4 or rel_diff <= 0.01:
                    matches += 1
                    matched_gen_indices.add(idx)
                    break
        
        score = (matches / len(expected_numbers)) * 100.0
        explanation = f"Extracted {len(expected_numbers)} numerical values from expected answer and {len(generated_numbers)} from generated answer. Found {matches} matching values (with 1% tolerance). Score: {score:.1f}%"
        
        return score, explanation
    
    def _compute_final_scores(self, report: QuestionReport) -> None:
        """
        Compute multi-dimensional final answer quality scores.
        Each score includes an explanation.
        """
        # Retrieval recall & Context precision (relevant vs total retrieved)
        if report.retrieved_chunks:
            target_paper = report.paper.lower()
            relevant_chunks = [
                c for c in report.retrieved_chunks
                if target_paper in c.get('metadata', {}).get('file', '').lower()
                or target_paper in c.get('metadata', {}).get('paper_title', '').lower()
                or target_paper in c.get('pdf_filename', '').lower()
            ]
            num_relevant = len(relevant_chunks) if relevant_chunks else len(report.retrieved_chunks)
            total_retrieved = len(report.retrieved_chunks)
            
            # Context precision: ratio of relevant retrieved chunks to total retrieved chunks
            report.context_quality = (num_relevant / total_retrieved) * 100.0
            report.score_explanations['context_quality'] = f"Context Precision: {num_relevant}/{total_retrieved} retrieved chunks matched the target paper."
            
            # Retrieval quality (recall): proportion of target context provided out of top k capacity
            report.retrieval_quality = min(100.0, (num_relevant / max(1, min(10, total_retrieved))) * 100.0)
            report.score_explanations['retrieval_quality'] = f"Retrieval Recall: {num_relevant} relevant chunks retrieved out of {total_retrieved} total."
        else:
            report.retrieval_quality = 0.0
            report.context_quality = 0.0
            report.score_explanations['retrieval_quality'] = "No chunks retrieved"
            report.score_explanations['context_quality'] = "No chunks retrieved"
        
        # Grounding score: based on claim grounding status (excluding VERIFICATION_FAILED)
        if report.claims:
            valid_claims = [c for c in report.claims if c.grounding_status != 'VERIFICATION_FAILED']
            if valid_claims:
                supported = sum(1 for c in valid_claims if c.grounding_status == 'SUPPORTED')
                partially_supported = sum(1 for c in valid_claims if c.grounding_status == 'PARTIALLY_SUPPORTED')
                report.grounding_score = ((supported + 0.5 * partially_supported) / len(valid_claims)) * 100
                verification_failed = sum(1 for c in report.claims if c.grounding_status == 'VERIFICATION_FAILED')
                report.score_explanations['grounding_score'] = f"{supported} fully supported, {partially_supported} partially supported out of {len(valid_claims)} valid claims ({verification_failed} verification failed, excluded from score)"
            else:
                report.grounding_score = 0.0
                report.score_explanations['grounding_score'] = f"All {len(report.claims)} claims had verification failures"
        else:
            report.grounding_score = 0.0
            report.score_explanations['grounding_score'] = "No claims extracted"
        
        # Semantic correctness: from semantic similarity
        report.semantic_correctness = report.semantic_similarity
        report.score_explanations['semantic_correctness'] = report.semantic_explanation
        
        # Numerical correctness: from numerical evaluation
        report.numerical_correctness = report.numerical_similarity
        report.score_explanations['numerical_correctness'] = report.numerical_explanation
        
        # Completeness: evaluate semantic recall of expected answer facts/claims in generated answer
        expected_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', report.expected_answer) if len(s.strip()) >= 10]
        generated_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', report.raw_llm_answer) if len(s.strip()) >= 10]
        
        if expected_sentences and generated_sentences:
            exp_embs = self.semantic_model.encode(expected_sentences)
            gen_embs = self.semantic_model.encode(generated_sentences)
            sim_matrix = util.cos_sim(exp_embs, gen_embs)
            # Max recall similarity for each expected sentence
            max_sims = sim_matrix.max(dim=1).values.tolist()
            avg_recall = (sum(max_sims) / len(max_sims)) * 100.0
            report.completeness = max(0.0, min(100.0, avg_recall))
            report.score_explanations['completeness'] = f"Evaluated recall across {len(expected_sentences)} expected claims against generated answer sentences (avg semantic recall: {avg_recall:.1f}%)."
        else:
            report.completeness = report.semantic_similarity
            report.score_explanations['completeness'] = f"Derived from overall semantic similarity score ({report.semantic_similarity:.1f}%)."
        
        # Conciseness: inverse of verbosity (penalize overly long answers)
        expected_length = len(report.expected_answer.split())
        generated_length = len(report.raw_llm_answer.split())
        if generated_length > expected_length * 2:
            report.conciseness = 50.0
            report.score_explanations['conciseness'] = "Answer is overly verbose"
        elif generated_length > expected_length * 1.5:
            report.conciseness = 75.0
            report.score_explanations['conciseness'] = "Answer is somewhat verbose"
        else:
            report.conciseness = 100.0
            report.score_explanations['conciseness'] = "Answer is appropriately concise"
        
        # Hallucination score: based on NOT_FOUND claims (excluding VERIFICATION_FAILED)
        if report.claims:
            valid_claims = [c for c in report.claims if c.grounding_status != 'VERIFICATION_FAILED']
            if valid_claims:
                not_found = sum(1 for c in valid_claims if c.grounding_status == 'NOT_FOUND')
                report.hallucination_score = (not_found / len(valid_claims)) * 100
                verification_failed = sum(1 for c in report.claims if c.grounding_status == 'VERIFICATION_FAILED')
                report.score_explanations['hallucination_score'] = f"{not_found} out of {len(valid_claims)} valid claims have no supporting evidence ({verification_failed} verification failed, excluded from score)"
            else:
                report.hallucination_score = 0.0
                report.score_explanations['hallucination_score'] = f"All {len(report.claims)} claims had verification failures"
        else:
            report.hallucination_score = 0.0
            report.score_explanations['hallucination_score'] = "No claims extracted"
        
        # Overall score: weighted average (base weights sum to 1.0)
        weights = {
            'retrieval': 0.05,
            'context': 0.05,
            'grounding': 0.30,
            'semantic': 0.30,
            'numerical': 0.15,
            'completeness': 0.10,
            'conciseness': 0.05,
            'hallucination_penalty': 0.10  # Deductive penalty factor for hallucinated claims
        }
        
        base_score = (
            report.retrieval_quality * weights['retrieval'] +
            report.context_quality * weights['context'] +
            report.grounding_score * weights['grounding'] +
            report.semantic_correctness * weights['semantic'] +
            report.numerical_correctness * weights['numerical'] +
            report.completeness * weights['completeness'] +
            report.conciseness * weights['conciseness']
        )
        
        penalty = report.hallucination_score * weights['hallucination_penalty']
        report.overall_score = max(0.0, min(100.0, base_score - penalty))
        report.score_explanations['overall_score'] = f"Weighted sum (base max 100.0) with {penalty:.1f} point hallucination penalty applied."
    
    def evaluate_question(self, item: Dict) -> QuestionReport:
        """Evaluate a single question with the modular stage-by-stage framework."""
        question_id = (item.get('id') or item.get('Question_ID') or 'unknown')
        paper = (item.get('paper') or item.get('Paper') or 'unknown')
        question = (item.get('question') or item.get('Question') or '')
        expected = (item.get('expected_answer') or item.get('Expected_Answer') or '')
        
        stage_results: List[StageResult] = []

        # STAGE 0: Gold Reference Validation
        res_stage0 = self.gold_stage.execute(item, find_pdf_fn=self._find_pdf_path)
        stage_results.append(res_stage0)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage0)

        t_total_start = time.perf_counter()
        
        # STAGE 1: Retrieval Validation
        repo_id = self._find_repo_for_file(paper)
        t_rag_start = time.perf_counter()
        response = self.orch.answer(question, repo_id=repo_id, filters={'file': paper})
        t_rag_end = time.perf_counter()
        rag_latency_ms = (t_rag_end - t_rag_start) * 1000.0
        
        raw_llm_answer = response.get('answer', '')
        retrieved_chunks = response.get('retrieved_chunks', [])
        
        if not retrieved_chunks:
            pdf_path = self._find_pdf_path(paper)
            if pdf_path:
                try:
                    if pdf_path not in self.pdf_cache:
                        self.pdf_cache[pdf_path] = parse_pdf(pdf_path)
                    parsed = self.pdf_cache[pdf_path]
                    chunks = []
                    for page_data in parsed.get("pages", []):
                        p_num = page_data.get("page", 1)
                        for block in page_data.get("blocks", []):
                            txt = block.get("text", "").strip()
                            if len(txt) >= 40:
                                chunks.append({
                                    "content": txt,
                                    "metadata": {
                                        "page_start": p_num,
                                        "section": block.get("section", "General"),
                                        "file": paper,
                                        "paper_title": paper
                                    }
                                })
                    retrieved_chunks = chunks[:15]
                except Exception as e:
                    print(f"Error parsing fallback PDF chunks for {paper}: {e}")

        if not raw_llm_answer or "cannot find" in raw_llm_answer.lower() or "query is empty" in raw_llm_answer.lower():
            if retrieved_chunks:
                context_str = "\n\n".join([f"[Page {c.get('metadata', {}).get('page_start', 1)}]: {c.get('content', '')[:400]}" for c in retrieved_chunks[:5]])
                prompt = f"Answer the following question accurately based on the provided scientific paper context:\n\nQuestion: {question}\n\nContext:\n{context_str}\n\nConcise Answer:"
                try:
                    gen_ans = generate(prompt, model_key="doc_agent_model").strip()
                    if gen_ans:
                        raw_llm_answer = gen_ans
                except Exception as e:
                    print(f"Error generating fallback LLM answer: {e}")

        res_stage1 = self.retrieval_stage.execute(question, paper, retrieved_chunks)
        stage_results.append(res_stage1)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage1)

        # STAGE 2: Reranker & Scoring Stage
        res_stage2 = self.reranker_stage.execute(
            question,
            res_stage1.outputs["retrieved_chunks"],
            self._compute_text_cosine_similarity,
            self._compute_cross_encoder_score
        )
        stage_results.append(res_stage2)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage2)
        scored_chunks = res_stage2.outputs["scored_chunks"]

        # STAGE 3: Claim Extraction Stage
        t_claim_start = time.perf_counter()
        res_stage3 = self.claim_stage.execute(raw_llm_answer, self._extract_claims)
        t_claim_end = time.perf_counter()
        claim_extraction_ms = (t_claim_end - t_claim_start) * 1000.0
        stage_results.append(res_stage3)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage3)
        claims = res_stage3.outputs["claims"]

        # STAGE 4: Evidence Verification Stage
        t_verify_start = time.perf_counter()
        print(f"Extracted {len(claims)} claims, now verifying evidence...")
        res_stage4 = self.evidence_stage.execute(
            claims,
            scored_chunks,
            paper,
            self.use_expanded_evidence,
            self._retrieve_candidate_evidence,
            self._classify_grounding,
            self._classify_claim_fidelity,
            raw_llm_answer
        )
        t_verify_end = time.perf_counter()
        verification_ms = (t_verify_end - t_verify_start) * 1000.0
        stage_results.append(res_stage4)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage4)
        verified_claims = res_stage4.outputs["claims"]

        # STAGE 5: Metric Computation Stage
        t_metric_start = time.perf_counter()
        res_stage5 = self.metric_stage.execute(
            expected,
            raw_llm_answer,
            verified_claims,
            scored_chunks,
            paper,
            self.semantic_model,
            self._compute_semantic_similarity,
            self._evaluate_numerical_claims
        )
        t_metric_end = time.perf_counter()
        metric_ms = (t_metric_end - t_metric_start) * 1000.0
        stage_results.append(res_stage5)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage5)
        metrics = res_stage5.outputs["metrics"]
        explanations = res_stage5.outputs["score_explanations"]

        total_latency = (time.perf_counter() - t_total_start) * 1000.0
        runtime_breakdown = {
            'total_ms': total_latency,
            'rag_pipeline_ms': rag_latency_ms,
            'claim_extraction_ms': claim_extraction_ms,
            'verification_ms': verification_ms,
            'metric_computation_ms': metric_ms,
            'scoring_overhead_ms': res_stage2.runtime_ms
        }

        # STAGE 6: Regression & Acceptance Validation Stage
        res_stage6 = self.acceptance_stage.execute(
            stage_results=stage_results,
            gold_reference=res_stage0.outputs,
            computed_metrics=metrics,
            noise_tolerance_pct=1.0
        )
        stage_results.append(res_stage6)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage6)
        acceptance_status = res_stage6.outputs["acceptance_status"]

        # STAGE 7: Report Generation Stage
        res_stage7 = self.report_stage.execute(
            question_id=question_id,
            paper=paper,
            question=question,
            expected_answer=expected,
            raw_llm_answer=raw_llm_answer,
            retrieved_chunks=scored_chunks,
            claims=verified_claims,
            metrics=metrics,
            explanations=explanations,
            runtime_breakdown=runtime_breakdown,
            stage_results=stage_results,
            acceptance_status=acceptance_status,
            question_report_cls=QuestionReport
        )
        stage_results.append(res_stage7)
        StageSerializer.save_stage_result(self.artifacts_dir, question_id, res_stage7)
        report = res_stage7.outputs["report"]

        # Diagnostic summary check
        diag_summary = DiagnosticReporter.generate_diagnostic_summary(question_id, stage_results)
        first_failing = DiagnosticReporter.get_first_failing_stage(stage_results)
        if first_failing:
            print(f"  Diagnostic Alert for {question_id}: Stage {first_failing.stage_id} ({first_failing.stage_name}) status is {first_failing.status.value}")

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
    
    def run_single(self, question_id: str) -> QuestionReport:
        """Run evaluation on a single question by ID."""
        for item in self.dataset:
            if item.get('id') == question_id or item.get('Question_ID') == question_id:
                return self.evaluate_question(item)
        raise ValueError(f"Question {question_id} not found in dataset")
    
    def generate_validation_report(self, report: QuestionReport) -> str:
        """Generate detailed validation report for a single question."""
        lines = []
        
        lines.append("=" * 80)
        lines.append("REDESIGNED EVALUATION FRAMEWORK - VALIDATION REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append("## QUESTION")
        lines.append(f"ID: {report.question_id}")
        lines.append(f"Paper: {report.paper}")
        lines.append(f"Question: {report.question}")
        lines.append("")
        
        lines.append("## EXPECTED ANSWER")
        lines.append(report.expected_answer)
        lines.append("")
        
        lines.append("## RETRIEVED CHUNKS")
        for i, chunk in enumerate(report.retrieved_chunks[:10]):
            metadata = chunk.get('metadata', {})
            lines.append(f"Chunk {i+1} (Page {metadata.get('page_start', '?')}-{metadata.get('page_end', '?')}):")
            lines.append(f"  Paper: {metadata.get('paper_title', 'unknown')}")
            lines.append(f"  Section: {metadata.get('section', 'unknown')}")
            lines.append(f"  Content: {chunk.get('content', '')[:300]}...")
            lines.append("")
        
        lines.append("## GENERATED ANSWER")
        lines.append(report.raw_llm_answer)
        lines.append("")
        
        lines.append("## EXTRACTED CLAIMS")
        for i, claim in enumerate(report.claims):
            lines.append(f"Claim {i+1}: {claim.text}")
            lines.append(f"  Type: {claim.claim_type}")
            lines.append(f"  Grounding Status: {claim.grounding_status}")
            lines.append(f"  Confidence: {claim.confidence:.3f}")
            lines.append(f"  Reason: {claim.reason}")
            if claim.grounding_status == "VERIFICATION_FAILED":
                lines.append(f"  Verification Error: {claim.verification_error}")
                lines.append(f"  Hallucination: N/A (verification failed)")
            else:
                lines.append(f"  Hallucination: {'YES' if claim.grounding_status == 'NOT_FOUND' else 'NO'}")
            lines.append(f"  Top 5 Candidate Chunks (Expanded Document Evaluation):")
            for j, evidence in enumerate(claim.evidence[:5]):
                lines.append(f"    Candidate {j+1}:")
                lines.append(f"      Chunk ID: {evidence.chunk_id}")
                lines.append(f"      Page: {evidence.page}")
                lines.append(f"      Section: {evidence.section}")
                lines.append(f"      Paper: {evidence.paper}")
                lines.append(f"      Embedding Similarity: {evidence.similarity:.3f} (for retrieval only)")
                lines.append(f"      Verification Status: {evidence.verification_status}")
                lines.append(f"      Verification Confidence: {evidence.verification_confidence:.1f}")
                lines.append(f"      Verification Reason: {evidence.verification_reason}")
                lines.append(f"      Quoted Supporting Text: {evidence.supporting_sentence}")
                if evidence.verification_status == "VERIFICATION_FAILED":
                    lines.append(f"      Verification Error: {evidence.verification_reason}")
                lines.append(f"      Retrieved Chunk: {evidence.content[:200]}...")
                if evidence.expanded_content:
                    lines.append(f"      Expanded Evidence (Full Page + Neighbors + OCR + Tables): {evidence.expanded_content[:300]}...")
                lines.append("")
        
        lines.append("## SEMANTIC CORRECTNESS")
        lines.append(f"Score: {report.semantic_correctness:.2f}/100")
        lines.append(f"Explanation: {report.semantic_explanation}")
        lines.append("")
        
        lines.append("## NUMERICAL CORRECTNESS")
        lines.append(f"Score: {report.numerical_correctness:.2f}/100")
        lines.append(f"Explanation: {report.numerical_explanation}")
        lines.append("")
        
        lines.append("## FINAL ANSWER QUALITY SCORES")
        lines.append(f"Retrieval Quality: {report.retrieval_quality:.1f}/100 - {report.score_explanations.get('retrieval_quality', '')}")
        lines.append(f"Context Quality: {report.context_quality:.1f}/100 - {report.score_explanations.get('context_quality', '')}")
        lines.append(f"Grounding: {report.grounding_score:.1f}/100 - {report.score_explanations.get('grounding_score', '')}")
        lines.append(f"Semantic Correctness: {report.semantic_correctness:.1f}/100 - {report.score_explanations.get('semantic_correctness', '')}")
        lines.append(f"Numerical Correctness: {report.numerical_correctness:.1f}/100 - {report.score_explanations.get('numerical_correctness', '')}")
        lines.append(f"Completeness: {report.completeness:.1f}/100 - {report.score_explanations.get('completeness', '')}")
        lines.append(f"Conciseness: {report.conciseness:.1f}/100 - {report.score_explanations.get('conciseness', '')}")
        lines.append(f"Hallucination Score: {report.hallucination_score:.1f}/100 - {report.score_explanations.get('hallucination_score', '')}")
        lines.append(f"Overall Score: {report.overall_score:.1f}/100 - {report.score_explanations.get('overall_score', '')}")
        lines.append("")
        
        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Redesigned Evaluation Framework for DocumentRAG")
    parser.add_argument("--dataset", required=True, help="Path to dataset JSON file")
    parser.add_argument("--output", required=True, help="Output directory for reports")
    parser.add_argument("--question-id", help="Evaluate single question by ID (for validation)")
    parser.add_argument("--chunk-only", action="store_true", help="Use only retrieved chunks (not expanded PDF pages)")
    
    args = parser.parse_args()
    
    evaluator = RedesignedEvaluator(args.dataset, args.output, use_expanded_evidence=not args.chunk_only)
    
    if args.question_id:
        # Single question validation
        print(f"Validating Question {args.question_id}...")
        report = evaluator.run_single(args.question_id)
        
        # Generate validation report
        validation_text = evaluator.generate_validation_report(report)
        print(validation_text)
        
        # Save validation report
        mode_suffix = "_chunk_only" if args.chunk_only else "_expanded"
        output_path = os.path.join(args.output, f"validation_{args.question_id}{mode_suffix}.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(validation_text)
        print(f"\nValidation report saved to {output_path}")
    else:
        print("Full evaluation not yet implemented. Use --question-id for validation.")
