"""
DocumentRAG Central Debug & Diagnostic Logger.
Instruments all 14 pipeline stages with structured JSON logging to logs/pipeline_debug.jsonl
and terminal output when DEBUG_MODE is enabled.
"""

import os
import sys
import json
import time
import uuid
import yaml
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

LOGS_DIR = Path(__file__).parent.parent / "logs"
DEBUG_LOG_PATH = LOGS_DIR / "pipeline_debug.jsonl"
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

_log_lock = threading.Lock()
_config_cache: Optional[Dict[str, Any]] = None


def get_config() -> Dict[str, Any]:
    global _config_cache
    if _config_cache is None:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    _config_cache = yaml.safe_load(f) or {}
            except Exception:
                _config_cache = {}
        else:
            _config_cache = {}
    return _config_cache


def is_debug_mode() -> bool:
    """
    Returns True if DEBUG_MODE is enabled via env var or config.yaml.
    """
    env_flag = os.environ.get("DEBUG_MODE", "").lower()
    if env_flag in ("true", "1", "yes", "on"):
        return True
    if env_flag in ("false", "0", "no", "off"):
        return False
    cfg = get_config()
    return bool(cfg.get("debug_mode", True))


def generate_request_id() -> str:
    """Generate a unique request ID for tracking across all 14 stages."""
    return str(uuid.uuid4())


def append_debug_log(entry: Dict[str, Any]):
    """Appends a structured JSON entry to logs/pipeline_debug.jsonl in a thread-safe manner."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with _log_lock:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        sys.stderr.write(f"[DEBUG_LOGGER ERROR] Failed to write log: {e}\n")


def log_stage(
    request_id: str,
    stage_num: int,
    stage_name: str,
    data: Dict[str, Any],
    latency_ms: float = 0.0,
    print_to_console: bool = True
):
    """
    Log a pipeline stage to JSONL log file and optionally print to console.
    """
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime()) + f"{int((time.time() % 1) * 1000):03d}Z"
    
    log_entry = {
        "request_id": request_id,
        "timestamp": timestamp,
        "stage": stage_num,
        "stage_name": stage_name,
        "latency_ms": round(latency_ms, 2),
        "data": data
    }
    
    append_debug_log(log_entry)
    
    if print_to_console and is_debug_mode():
        sep = "=" * 60
        print(f"\n{sep}", flush=True)
        print(f"STAGE {stage_num}: {stage_name.upper()} (Request: {request_id[:8]})", flush=True)
        print(f"Latency: {latency_ms:.2f} ms", flush=True)
        print(f"{sep}", flush=True)
        
        # Formatted console output depending on stage
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                formatted_v = json.dumps(v, indent=2, default=str)
                if len(formatted_v) > 2000 and not stage_num in (9, 10, 11, 14):
                    formatted_v = formatted_v[:2000] + "\n...[truncated for display]"
                print(f"{k}:\n{formatted_v}", flush=True)
            else:
                print(f"{k}: {v}", flush=True)


def log_grounding_exit(
    request_id: str,
    file_path: str,
    function_name: str,
    line_number: int,
    reason: str,
    condition: str,
    evidence: Dict[str, Any]
):
    """
    Log an early exit / grounding fallback ("I cannot find this information...")
    with exact file, function, line number, reason, condition, and evidence.
    """
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime()) + f"{int((time.time() % 1) * 1000):03d}Z"
    
    entry = {
        "request_id": request_id,
        "timestamp": timestamp,
        "stage": 12,
        "stage_name": "Grounding Validation Early Exit",
        "file": file_path,
        "function": function_name,
        "line_number": line_number,
        "reason": reason,
        "condition": condition,
        "evidence": evidence,
        "response": "I cannot find this information in the uploaded documents."
    }
    
    append_debug_log(entry)
    
    if is_debug_mode():
        sep = "=" * 60
        print(f"\n{sep}", flush=True)
        print("STAGE 12: GROUNDING VALIDATION (EARLY EXIT DETECTED)", flush=True)
        print(f"{sep}", flush=True)
        print(f"FILE        : {file_path}", flush=True)
        print(f"FUNCTION    : {function_name}", flush=True)
        print(f"LINE NUMBER : {line_number}", flush=True)
        print(f"REASON      : {reason}", flush=True)
        print(f"CONDITION   : {condition}", flush=True)
        print(f"EVIDENCE    : {json.dumps(evidence, default=str)}", flush=True)
        print("RESPONSE    : \"I cannot find this information in the uploaded documents.\"", flush=True)
        print(f"{sep}\n", flush=True)
