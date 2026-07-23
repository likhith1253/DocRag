"""
Stage Framework for Modular AI Evaluation Pipeline

Defines core data structures, invariant checking utilities,
provenance versioning, and stage artifact serialization/deserialization.
"""

import os
import json
import time
import uuid
import hashlib
import subprocess
from enum import Enum
from typing import Dict, List, Any, Optional, Generic, TypeVar
from dataclasses import dataclass, field

class StageStatus(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class AcceptanceStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

def get_git_commit() -> str:
    """Retrieve current git commit hash or fallback string."""
    try:
        cmd = ["git", "rev-parse", "--short", "HEAD"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2.0)
        return output.decode('utf-8').strip()
    except Exception:
        return "unknown_commit"

def get_provenance_metadata() -> Dict[str, Any]:
    """Retrieve system configuration provenance versioning metadata."""
    return {
        "run_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": get_git_commit(),
        "embedding_model": "all-MiniLM-L6-v2",
        "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "llm_model": "qwen2.5:3b-instruct",
        "config_hash": hashlib.sha256("doc_rag_v1_config".encode("utf-8")).hexdigest()[:12],
        "dataset_version": "v1.0"
    }

@dataclass
class StageResult:
    stage_id: int
    stage_name: str
    status: StageStatus
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    intermediate_artifacts: Dict[str, Any] = field(default_factory=dict)
    runtime_ms: float = 0.0
    error_messages: List[str] = field(default_factory=list)
    invariant_violations: List[Dict[str, Any]] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=get_provenance_metadata)

    def add_invariant_check(self, condition: bool, name: str, details: str, severity: str = "ERROR") -> bool:
        """Verify an invariant condition. Returns True if passed, False if violated."""
        if not condition:
            self.invariant_violations.append({
                "name": name,
                "details": details,
                "severity": severity
            })
            if severity == "ERROR" and self.status != StageStatus.FAILED:
                self.status = StageStatus.FAILED
            elif severity == "WARNING" and self.status == StageStatus.PASSED:
                self.status = StageStatus.WARNING
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "status": self.status.value if isinstance(self.status, StageStatus) else str(self.status),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "intermediate_artifacts": self.intermediate_artifacts,
            "runtime_ms": self.runtime_ms,
            "error_messages": self.error_messages,
            "invariant_violations": self.invariant_violations,
            "provenance": self.provenance
        }

@dataclass
class StageResultContainer:
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StageResult:
        status_str = data.get("status", "PASSED")
        try:
            status = StageStatus(status_str)
        except ValueError:
            status = StageStatus.PASSED

        return StageResult(
            stage_id=data.get("stage_id", 0),
            stage_name=data.get("stage_name", "UnknownStage"),
            status=status,
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            intermediate_artifacts=data.get("intermediate_artifacts", {}),
            runtime_ms=data.get("runtime_ms", 0.0),
            error_messages=data.get("error_messages", []),
            invariant_violations=data.get("invariant_violations", []),
            provenance=data.get("provenance", get_provenance_metadata())
        )

class StageSerializer:
    """Handles serialization and deserialization of stage inputs/outputs with provenance metadata."""
    
    @staticmethod
    def get_artifact_path(artifacts_dir: str, question_id: str, stage_id: int, stage_name: str) -> str:
        q_dir = os.path.join(artifacts_dir, question_id)
        os.makedirs(q_dir, exist_ok=True)
        sanitized_name = stage_name.lower().replace(" ", "_")
        return os.path.join(q_dir, f"stage_{stage_id}_{sanitized_name}.json")

    @classmethod
    def save_stage_result(cls, artifacts_dir: str, question_id: str, result: StageResult) -> str:
        filepath = cls.get_artifact_path(artifacts_dir, question_id, result.stage_id, result.stage_name)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        return filepath

    @classmethod
    def load_stage_result(cls, artifacts_dir: str, question_id: str, stage_id: int, stage_name: str) -> Optional[StageResult]:
        filepath = cls.get_artifact_path(artifacts_dir, question_id, stage_id, stage_name)
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return StageResultContainer.from_dict(data)
