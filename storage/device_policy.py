"""
storage/device_policy.py — CPU-First Device Policy Manager.

Manages execution device assignments across:
  1. LLM (Primary GPU workload, e.g. Qwen on Tesla V100 16GB)
  2. Embedding (Auxiliary workload: SentenceTransformer)
  3. CrossEncoder (Auxiliary workload: Reranker)

Guarantees:
  - CPU is a first-class supported path and works without CUDA.
  - If CUDA is unavailable, all models cleanly select CPU.
  - If CUDA is available, Qwen is given primary GPU allocation.
  - Auxiliary models (Embedding, CrossEncoder) use GPU ONLY when safe VRAM
    remains (configurable safety margin, default ~3500 MB).
  - Any GPU load failure or out-of-memory gracefully falls back to CPU.
  - Clear, structured reason logging for every device decision.
"""

import os
import sys
import threading
from typing import Dict, Any, Optional, Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SAFE_VRAM_MARGIN_MB = 3500


class DevicePolicyManager:
    """
    Central manager for hardware device allocation policy.
    Thread-safe singleton with mockable hooks for unit testing.
    """
    _instance: Optional["DevicePolicyManager"] = None
    _lock = threading.Lock()

    def __init__(self, safe_margin_mb: int = _DEFAULT_SAFE_VRAM_MARGIN_MB):
        self.safe_margin_mb = safe_margin_mb
        self._decisions_log: list = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls, safe_margin_mb: int = _DEFAULT_SAFE_VRAM_MARGIN_MB) -> "DevicePolicyManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(safe_margin_mb=safe_margin_mb)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        with cls._lock:
            cls._instance = None

    def _check_cuda_available(self) -> bool:
        """Check if CUDA is available via torch.cuda."""
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _get_cuda_memory_mb(self) -> Tuple[int, int]:
        """
        Return (free_mb, total_mb) for cuda:0.
        Returns (0, 0) if CUDA unavailable or check fails.
        """
        try:
            import torch
            if not torch.cuda.is_available():
                return 0, 0
            # mem_get_info returns (free_bytes, total_bytes)
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            return int(free_bytes / (1024 * 1024)), int(total_bytes / (1024 * 1024))
        except Exception:
            return 0, 0

    def can_allocate_aux_gpu(self, margin_mb: Optional[int] = None) -> Tuple[bool, str]:
        """
        Evaluate if an auxiliary model (embedding or reranker) can safely use GPU.
        Returns (allowed, reason).
        """
        if not self._check_cuda_available():
            return False, "CUDA unavailable"

        required_margin = margin_mb if margin_mb is not None else self.safe_margin_mb
        free_mb, total_mb = self._get_cuda_memory_mb()

        if total_mb == 0:
            return False, "Unable to query GPU memory"

        if free_mb < required_margin:
            return False, (
                f"insufficient safe GPU memory: {free_mb} MB free < "
                f"{required_margin} MB safety margin"
            )

        return True, f"safe GPU memory available: {free_mb} MB free >= {required_margin} MB margin"

    def get_llm_device(self, preferred: str = "cuda") -> Tuple[str, str]:
        """
        Determine device for LLM (primary workload).
        Returns (device_str, reason).
        """
        preferred = str(preferred).lower().strip()
        if preferred == "cpu":
            return "cpu", "configured as cpu"

        if not self._check_cuda_available():
            return "cpu", "CUDA unavailable"

        return "cuda", "CUDA available for primary LLM workload"

    def get_embedding_device(self, config_device: Optional[str] = None) -> Tuple[str, str]:
        """
        Determine device for SentenceTransformer embeddings.
        Returns (device_str, reason).
        """
        if config_device is not None:
            cd = str(config_device).lower().strip()
            if cd == "cpu":
                return "cpu", "configured as cpu"
            if cd == "cuda":
                # User explicitly requested cuda; check safe memory
                can_gpu, reason = self.can_allocate_aux_gpu()
                if can_gpu:
                    return "cuda", f"explicitly configured cuda and {reason}"
                return "cpu", f"CUDA requested for embedding but {reason}"

        # Default / auto policy:
        can_gpu, reason = self.can_allocate_aux_gpu()
        if can_gpu:
            return "cuda", reason
        return "cpu", reason

    def get_reranker_device(self, config_device: Optional[str] = None) -> Tuple[str, str]:
        """
        Determine device for CrossEncoder reranker.
        Returns (device_str, reason).
        """
        if config_device is not None:
            cd = str(config_device).lower().strip()
            if cd == "cpu":
                return "cpu", "configured as cpu"
            if cd == "cuda":
                can_gpu, reason = self.can_allocate_aux_gpu()
                if can_gpu:
                    return "cuda", f"explicitly configured cuda and {reason}"
                return "cpu", f"CUDA requested for reranker but {reason}"

        # Default / auto policy:
        can_gpu, reason = self.can_allocate_aux_gpu()
        if can_gpu:
            return "cuda", reason
        return "cpu", reason

    def log_decision(self, component: str, device: str, reason: str) -> None:
        """Record and log a device assignment decision."""
        msg = f"[{component.upper()} DEVICE POLICY] Selected: {device} | Reason: {reason}"
        print(msg, flush=True)
        with self._lock:
            self._decisions_log.append({
                "component": component,
                "device": device,
                "reason": reason
            })

    def get_system_device_summary(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Produce a structured summary of device assignments for diagnostics & profiling.
        """
        cfg = config or {}
        emb_cfg = cfg.get("embedding", {}) if isinstance(cfg.get("embedding"), dict) else {}
        configured_emb = emb_cfg.get("device") or cfg.get("device")
        
        emb_dev, emb_reason = self.get_embedding_device(configured_emb)
        ce_dev, ce_reason = self.get_reranker_device(cfg.get("reranker_device") or cfg.get("device"))
        llm_dev, llm_reason = self.get_llm_device(cfg.get("llm_device") or cfg.get("device", "cuda"))

        return {
            "cuda_available": self._check_cuda_available(),
            "safe_margin_mb": self.safe_margin_mb,
            "embedding": {"device": emb_dev, "reason": emb_reason},
            "cross_encoder": {"device": ce_dev, "reason": ce_reason},
            "llm": {"device": llm_dev, "reason": llm_reason},
        }


def get_device_policy_manager(safe_margin_mb: int = _DEFAULT_SAFE_VRAM_MARGIN_MB) -> DevicePolicyManager:
    """Convenience accessor for global DevicePolicyManager."""
    return DevicePolicyManager.get_instance(safe_margin_mb=safe_margin_mb)
