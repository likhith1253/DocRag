"""
Stage 3: Canonical Claim Construction Stage

Constructs a stable CanonicalClaimSet data structure to decouple
downstream evaluation metrics from raw claim extraction variations.
"""

import time
import hashlib
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field
from eval.stage_framework import StageResult, StageStatus

@dataclass
class CanonicalClaim:
    canonical_id: str
    claim_hash: str
    normalized_text: str
    raw_text: str
    claim_type: str  # 'factual', 'numerical', 'comparative'

@dataclass
class CanonicalClaimSet:
    claims: List[CanonicalClaim] = field(default_factory=list)
    raw_answer: str = ""

    def to_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "canonical_id": c.canonical_id,
                "claim_hash": c.claim_hash,
                "normalized_text": c.normalized_text,
                "text": c.raw_text,
                "claim_type": c.claim_type
            }
            for c in self.claims
        ]

class ClaimExtractionStage:
    """Stage 3: Validates claim extraction & constructs CanonicalClaimSet."""
    
    STAGE_ID = 3
    STAGE_NAME = "Canonical Claim Construction"

    def execute(
        self,
        raw_llm_answer: str,
        extract_claims_fn: Callable[[str], List[Any]]
    ) -> StageResult:
        start_time = time.perf_counter()

        raw_claims = extract_claims_fn(raw_llm_answer)
        
        canonical_list: List[CanonicalClaim] = []
        claim_types = []
        empty_claims = []

        for i, c in enumerate(raw_claims):
            text = c.text if hasattr(c, 'text') else c.get('text', '')
            ctype = c.claim_type if hasattr(c, 'claim_type') else c.get('claim_type', 'factual')
            
            norm_text = text.lower().strip()
            chash = hashlib.sha256(norm_text.encode('utf-8')).hexdigest()[:10]
            cid = f"claim_{i+1:03d}_{chash[:6]}"

            if not text.strip():
                empty_claims.append(i)
                
            claim_types.append(ctype)
            canonical_list.append(CanonicalClaim(
                canonical_id=cid,
                claim_hash=chash,
                normalized_text=norm_text,
                raw_text=text,
                claim_type=ctype
            ))

        canonical_set = CanonicalClaimSet(claims=canonical_list, raw_answer=raw_llm_answer)

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "raw_llm_answer_len": len(raw_llm_answer),
                "raw_llm_answer": raw_llm_answer[:200]
            },
            outputs={
                "num_claims": len(raw_claims),
                "claims": raw_claims,
                "canonical_claim_set": canonical_set.to_list()
            },
            intermediate_artifacts={
                "claim_types": claim_types,
                "canonical_ids": [c.canonical_id for c in canonical_list]
            }
        )

        # Invariant 1: Claim count non-negative
        result.add_invariant_check(
            len(raw_claims) >= 0,
            "Claim Count Non-Negative",
            f"Claim count must be non-negative (got {len(raw_claims)})"
        )

        # Invariant 2: Extracted claims non-empty text
        result.add_invariant_check(
            len(empty_claims) == 0,
            "Extracted Claims Non-Empty Text",
            f"Found {len(empty_claims)} empty claims at indices {empty_claims}"
        )

        # Invariant 3: Valid claim types
        valid_types = {'factual', 'numerical', 'comparative'}
        invalid_types = [t for t in claim_types if t not in valid_types]
        result.add_invariant_check(
            len(invalid_types) == 0,
            "Claim Type Schema Validity",
            f"Found invalid claim types: {invalid_types} (must be in {valid_types})"
        )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
