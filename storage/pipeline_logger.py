"""
DocumentRAG Central Debug & Diagnostic Logger.
Provides persistent structured logging to logs/backend_debug.log (RotatingFileHandler: 5MB, 5 backups),
prompt trace artifacts to logs/prompts/, model output artifacts to logs/model_outputs/,
retrieval JSON traces to logs/retrieval/, and exception tracebacks to logs/errors.log.
"""

import os
import sys
import json
import time
import uuid
import yaml
import logging
import traceback
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Directories & Paths Setup
# ---------------------------------------------------------------------------
LOGS_DIR = (Path(__file__).parent.parent / "logs").resolve()
PROMPTS_DIR = LOGS_DIR / "prompts"
MODEL_OUTPUTS_DIR = LOGS_DIR / "model_outputs"
RETRIEVAL_DIR = LOGS_DIR / "retrieval"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
RETRIEVAL_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_DEBUG_LOG_PATH = LOGS_DIR / "backend_debug.log"
ERRORS_LOG_PATH = LOGS_DIR / "errors.log"
DEBUG_LOG_PATH = LOGS_DIR / "pipeline_debug.jsonl"
CONFIG_PATH = (Path(__file__).parent.parent / "config.yaml").resolve()

# ---------------------------------------------------------------------------
# Requirement 9: Startup Output (Paths)
# ---------------------------------------------------------------------------
print("Backend Debug Log:", flush=True)
print(str(BACKEND_DEBUG_LOG_PATH), flush=True)
print("Prompt Log Folder:", flush=True)
print(str(PROMPTS_DIR), flush=True)
print("Model Output Folder:", flush=True)
print(str(MODEL_OUTPUTS_DIR), flush=True)
print("Retrieval Folder:", flush=True)
print(str(RETRIEVAL_DIR), flush=True)

# ---------------------------------------------------------------------------
# Requirement 2: Python RotatingFileHandler Setup
# ---------------------------------------------------------------------------
_file_handler = RotatingFileHandler(
    BACKEND_DEBUG_LOG_PATH,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,             # keep last 5 logs
    encoding="utf-8"
)
_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_file_handler.setFormatter(_formatter)

logger = logging.getLogger("DocumentRAG")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(_file_handler)

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
    """Generate a unique request ID for tracking across all stages."""
    return str(uuid.uuid4())


def append_debug_log(entry: Dict[str, Any]):
    """Appends a structured JSON entry to logs/pipeline_debug.jsonl in a thread-safe manner."""
    try:
        with _log_lock:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        sys.stderr.write(f"[DEBUG_LOGGER ERROR] Failed to write log: {e}\n")


def log_msg(message: str, level: str = "info"):
    """
    Duplicate message to stdout AND backend_debug.log (Requirement 3).
    """
    print(message, flush=True)
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


def log_stage(
    request_id: str,
    stage_num: int,
    stage_name: str,
    data: Dict[str, Any],
    latency_ms: float = 0.0,
    print_to_console: bool = True
):
    """
    Log a pipeline stage to JSONL, RotatingFileHandler backend_debug.log, and stdout.
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
    
    # Requirement 3 & 4: Log formatted message to backend_debug.log & stdout
    sep = "=" * 60
    lines = [
        f"{sep}",
        f"STAGE {stage_num}: {stage_name.upper()} (Request: {request_id[:8]})",
        f"Latency: {latency_ms:.2f} ms",
        f"{sep}"
    ]
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            formatted_v = json.dumps(v, indent=2, default=str)
            if len(formatted_v) > 2000 and stage_num not in (9, 10, 11, 14):
                formatted_v = formatted_v[:2000] + "\n...[truncated for display]"
            lines.append(f"{k}:\n{formatted_v}")
        else:
            lines.append(f"{k}: {v}")
            
    formatted_output = "\n".join(lines)
    
    # Write to RotatingFileHandler (logs/backend_debug.log)
    logger.info(formatted_output)
    
    # Output to stdout
    if print_to_console and is_debug_mode():
        print("\n" + formatted_output, flush=True)


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
    
    sep = "=" * 60
    msg = (
        f"\n{sep}\n"
        f"STAGE 12: GROUNDING VALIDATION (EARLY EXIT DETECTED)\n"
        f"{sep}\n"
        f"FILE        : {file_path}\n"
        f"FUNCTION    : {function_name}\n"
        f"LINE NUMBER : {line_number}\n"
        f"REASON      : {reason}\n"
        f"CONDITION   : {condition}\n"
        f"EVIDENCE    : {json.dumps(evidence, default=str)}\n"
        f"RESPONSE    : \"I cannot find this information in the uploaded documents.\"\n"
        f"{sep}\n"
    )
    logger.info(msg)
    if is_debug_mode():
        print(msg, flush=True)


# ---------------------------------------------------------------------------
# Requirement 5: Save prompt separately (logs/prompts/timestamp_prompt.txt)
# ---------------------------------------------------------------------------
def save_prompt_artifact(request_id: str, prompt_text: str):
    """
    Save FULL PROMPT exactly as sent to Qwen without truncation to logs/prompts/
    """
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{request_id[:8]}_prompt.txt"
        file_path = PROMPTS_DIR / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        logger.info(f"Saved prompt artifact to {file_path}")
    except Exception as e:
        log_exception(e, "save_prompt_artifact")


# ---------------------------------------------------------------------------
# Requirement 6: Save raw model output (logs/model_outputs/timestamp_response.txt)
# ---------------------------------------------------------------------------
def save_model_output_artifact(request_id: str, raw_response: str):
    """
    Save raw response before any parsing to logs/model_outputs/
    """
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{request_id[:8]}_response.txt"
        file_path = MODEL_OUTPUTS_DIR / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(raw_response or "")
        logger.info(f"Saved model output artifact to {file_path}")
    except Exception as e:
        log_exception(e, "save_model_output_artifact")


# ---------------------------------------------------------------------------
# Requirement 7: Save retrieval JSON (logs/retrieval/timestamp.json)
# ---------------------------------------------------------------------------
def save_retrieval_json_artifact(
    request_id: str,
    question: str,
    top_retrieved_chunks: List[Dict[str, Any]],
    scores: Dict[str, Any],
    metadata: Dict[str, Any],
    cross_encoder_scores: List[Dict[str, Any]],
    selected_chunks: List[Dict[str, Any]]
):
    """
    Save retrieval JSON containing question, top retrieved chunks, scores, metadata, cross encoder scores, selected chunks.
    """
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{request_id[:8]}.json"
        file_path = RETRIEVAL_DIR / filename
        data = {
            "request_id": request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "question": question,
            "top_retrieved_chunks": top_retrieved_chunks,
            "scores": scores,
            "metadata": metadata,
            "cross_encoder_scores": cross_encoder_scores,
            "selected_chunks": selected_chunks
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved retrieval JSON artifact to {file_path}")
    except Exception as e:
        log_exception(e, "save_retrieval_json_artifact")


# ---------------------------------------------------------------------------
# Requirement 8: Exception traceback logging (logs/errors.log)
# ---------------------------------------------------------------------------
def log_exception(e: Exception, context: str = ""):
    """
    Save full exception traceback to logs/errors.log and backend_debug.log.
    """
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        tb_str = traceback.format_exc()
        msg = f"[{ts}] EXCEPTION in {context}:\n{e}\nTraceback:\n{tb_str}\n"
        with _log_lock:
            with open(ERRORS_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        logger.error(msg)
        sys.stderr.write(msg + "\n")
    except Exception as err:
        sys.stderr.write(f"Failed to log exception: {err}\n")
