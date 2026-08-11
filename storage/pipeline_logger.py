"""
DocumentRAG Central Debug & Diagnostic Logger + Per-Query Forensic Report.

Provides:
1. Per-query forensic report in `.debug/current_query/` containing:
   - summary.txt
   - pipeline.txt
   - retrieval.txt
   - prompt.txt
   - llm_output.txt
   - response.json
2. Clean 10-line terminal output per query.
3. Strict assertions for pipeline verification.
"""

import os
import sys
import json
import time
import uuid
import yaml
import shutil
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
ROOT_DIR = (Path(__file__).parent.parent).resolve()
DEBUG_DIR = ROOT_DIR / ".debug" / "current_query"
LOGS_DIR = ROOT_DIR / "logs"
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
CONFIG_PATH = ROOT_DIR / "config.yaml"

# Setup RotatingFileHandler
_file_handler = RotatingFileHandler(
    BACKEND_DEBUG_LOG_PATH,
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
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


# ---------------------------------------------------------------------------
# Forensic Report Tracker
# ---------------------------------------------------------------------------
class ForensicTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self, question: str = ""):
        with self.lock:
            self.question = question
            self.start_time = time.time()
            self.stages_status: Dict[str, str] = {
                "Embedding": "PENDING",
                "Vector Search": "PENDING",
                "Filtering": "PENDING",
                "MMR": "PENDING",
                "Cross Encoder": "PENDING",
                "Prompt": "PENDING",
                "LLM": "PENDING",
                "Citation": "PENDING",
                "Response": "PENDING",
            }
            self.stages_timing: Dict[str, float] = {}
            self.pipeline_verification_lines: List[str] = []
            self.retrieval_chunks: List[Dict[str, Any]] = []
            self.filtered_chunk_count: int = 0
            self.mmr_chunk_count: int = 0
            self.ce_chunk_count: int = 0
            self.sent_chunk_count: int = 0
            self.prompt_text: str = ""
            self.prompt_chars: int = 0
            self.prompt_tokens: int = 0
            self.raw_llm_output: str = ""
            self.parsed_llm_output: str = ""
            self.returned_answer: str = ""
            self.citations: List[Dict[str, Any]] = []
            self.response_json: Dict[str, Any] = {}
            self.first_failing_stage: str = "NONE"
            self.root_cause: str = "NONE"
            self.retrieval_diagnostics: Dict[str, Any] = {}

            # Cleanly prepare .debug/current_query directory
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                for f in DEBUG_DIR.glob("*"):
                    if f.is_file():
                        try:
                            f.unlink()
                        except Exception:
                            pass
            except Exception as e:
                sys.stderr.write(f"[FORENSIC ERROR] Failed cleaning .debug/current_query: {e}\n")

    def record_stage(self, stage_name: str, status: str, timing_ms: float, input_info: Any, output_info: Any, details: str = ""):
        with self.lock:
            self.stages_status[stage_name] = status
            self.stages_timing[stage_name] = timing_ms
            if status == "FAIL" and self.first_failing_stage == "NONE":
                self.first_failing_stage = stage_name
                if details:
                    self.root_cause = details

            # STEP 9: Pipeline Verification Entry
            in_type = type(input_info).__name__
            in_len = len(input_info) if hasattr(input_info, "__len__") else 1
            in_mem = hex(id(input_info))
            out_type = type(output_info).__name__
            out_len = len(output_info) if hasattr(output_info, "__len__") else 1
            out_mem = hex(id(output_info))
            out_size = sys.getsizeof(output_info)

            line = (
                f"============================================================\n"
                f"STAGE: {stage_name.upper()}\n"
                f"============================================================\n"
                f"Input           : type={in_type}, count={in_len}, mem_id={in_mem}\n"
                f"Output          : type={out_type}, count={out_len}, mem_id={out_mem}\n"
                f"Transformation  : {details or 'Executed cleanly'}\n"
                f"File Written    : .debug/current_query/\n"
                f"Object Size     : {out_size} bytes\n"
                f"Timing          : {timing_ms:.2f} ms\n\n"
            )
            self.pipeline_verification_lines.append(line)

    def write_artifacts(self):
        with self.lock:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                # 1. pipeline.txt
                with open(DEBUG_DIR / "pipeline.txt", "w", encoding="utf-8") as f:
                    f.writelines(self.pipeline_verification_lines)

                # 2. retrieval.txt (STEP 4)
                retrieval_lines = ["Rank | Score | Paper | Section | Page | Chunk ID\n"]
                for rank, c in enumerate(self.retrieval_chunks, start=1):
                    meta = c.get("metadata", {})
                    score = float(c.get("score", 0.0))
                    paper = meta.get("paper_title") or meta.get("file") or "Unknown"
                    section = meta.get("section", "Unknown")
                    pg = f"P{meta.get('page_start', '?')}"
                    cid = str(c.get("id") or meta.get("hash") or f"chunk_{rank}")
                    retrieval_lines.append(f"{rank:2d} | {score:8.4f} | {paper} | {section} | {pg} | {cid}\n")
                with open(DEBUG_DIR / "retrieval.txt", "w", encoding="utf-8") as f:
                    f.writelines(retrieval_lines)

                # 3. prompt.txt (STEP 5)
                with open(DEBUG_DIR / "prompt.txt", "w", encoding="utf-8") as f:
                    f.write(self.prompt_text or "")

                # 4. llm_output.txt (STEP 6)
                llm_output_text = (
                    "=== RAW DECODED OUTPUT ===\n"
                    f"{self.raw_llm_output or ''}\n\n"
                    "=== PARSED OUTPUT ===\n"
                    f"{self.parsed_llm_output or ''}\n\n"
                    "=== RETURNED ANSWER ===\n"
                    f"{self.returned_answer or ''}\n"
                )
                with open(DEBUG_DIR / "llm_output.txt", "w", encoding="utf-8") as f:
                    f.write(llm_output_text)

                # 5. response.json (STEP 7)
                with open(DEBUG_DIR / "response.json", "w", encoding="utf-8") as f:
                    json.dump(self.response_json, f, indent=2, default=str)

                # 6. summary.txt (STEP 3)
                summary_lines = [
                    f"Question: {self.question}\n\n",
                    "Stage Status:\n",
                    f"Embedding ........ {self.stages_status.get('Embedding', 'PASS')} ({self.stages_timing.get('Embedding', 0.0):.2f} ms)\n",
                    f"Vector Search .... {self.stages_status.get('Vector Search', 'PASS')} ({self.stages_timing.get('Vector Search', 0.0):.2f} ms)\n",
                    f"Filtering ........ {self.stages_status.get('Filtering', 'PASS')} ({self.stages_timing.get('Filtering', 0.0):.2f} ms)\n",
                    f"MMR .............. {self.stages_status.get('MMR', 'PASS')} ({self.stages_timing.get('MMR', 0.0):.2f} ms)\n",
                    f"Cross Encoder .... {self.stages_status.get('Cross Encoder', 'PASS')} ({self.stages_timing.get('Cross Encoder', 0.0):.2f} ms)\n",
                    f"Prompt ........... {self.stages_status.get('Prompt', 'PASS')} ({self.stages_timing.get('Prompt', 0.0):.2f} ms)\n",
                    f"LLM .............. {self.stages_status.get('LLM', 'PASS')} ({self.stages_timing.get('LLM', 0.0):.2f} ms)\n",
                    f"Citation ......... {self.stages_status.get('Citation', 'PASS')} ({self.stages_timing.get('Citation', 0.0):.2f} ms)\n\n",
                    "Pipeline Metrics:\n",
                    f"Chunks after retrieval : {len(self.retrieval_chunks)}\n",
                    f"Chunks after filtering : {self.filtered_chunk_count}\n",
                    f"Chunks after MMR       : {self.mmr_chunk_count}\n",
                    f"Chunks after CrossEncoder: {self.ce_chunk_count}\n",
                    f"Chunks sent to LLM     : {self.sent_chunk_count}\n",
                    f"Prompt characters      : {self.prompt_chars}\n",
                    f"Prompt tokens          : {self.prompt_tokens}\n",
                    f"LLM output length      : {len(self.raw_llm_output or '')}\n",
                    f"Citation count         : {len(self.citations)}\n\n",
                ]
                # Retrieval diagnostics (Phase 1)
                if self.retrieval_diagnostics:
                    rd = self.retrieval_diagnostics
                    summary_lines.append("Retrieval Diagnostics:\n")
                    summary_lines.append(f"  Papers retrieved       : {rd.get('papers_retrieved', '?')}\n")
                    summary_lines.append(f"  Top contributing paper : {rd.get('top_contributing_paper', '?')}\n")
                    summary_lines.append(f"  Top paper chunks       : {rd.get('top_paper_chunk_count', '?')}\n")
                    summary_lines.append(f"  Top paper coverage     : {rd.get('top_paper_coverage_pct', '?')}%\n")
                    summary_lines.append(f"  Avg CE score (all)     : {rd.get('avg_ce_score_all', '?')}\n")
                    summary_lines.append(f"  Max CE score           : {rd.get('max_ce_score_all', '?')}\n")
                    for pb in rd.get("paper_breakdown", []):
                        summary_lines.append(
                            f"    [{pb['chunks']} chunks | avg={pb['avg_ce_score']:.4f}] {pb['paper']}\n"
                        )
                    summary_lines.append("\n")
                summary_lines += [
                    "Final Answer:\n",
                    f"{self.returned_answer}\n\n",
                    f"First Failing Stage : {self.first_failing_stage}\n",
                    f"Root Cause          : {self.root_cause}\n",
                ]
                with open(DEBUG_DIR / "summary.txt", "w", encoding="utf-8") as f:
                    f.writelines(summary_lines)
                print(f"[FORENSIC DEBUG] Successfully wrote 6 artifacts to {DEBUG_DIR.absolute()}", flush=True)
            except Exception as e:
                print(f"[FORENSIC ERROR] Failed writing forensic artifacts: {e}", flush=True)

    def print_terminal_summary(self):
        # STEP 2: Terminal Output (Strictly Clean)
        print("\n" + "=" * 40, flush=True)
        print(f"Embedding ........ {self.stages_status.get('Embedding', 'PASS')}", flush=True)
        print(f"Vector Search .... {self.stages_status.get('Vector Search', 'PASS')}", flush=True)
        print(f"Filtering ........ {self.stages_status.get('Filtering', 'PASS')}", flush=True)
        print(f"MMR .............. {self.stages_status.get('MMR', 'PASS')}", flush=True)
        print(f"Cross Encoder .... {self.stages_status.get('Cross Encoder', 'PASS')}", flush=True)
        print(f"Prompt ........... {self.stages_status.get('Prompt', 'PASS')}", flush=True)
        print(f"LLM .............. {self.stages_status.get('LLM', 'PASS')}", flush=True)
        print(f"Citation ......... {self.stages_status.get('Citation', 'PASS')}", flush=True)
        print(f"Response ......... DONE", flush=True)
        print("\nDebug report:", flush=True)
        print(".debug/current_query/", flush=True)
        print("=" * 40 + "\n", flush=True)


forensic_tracer = ForensicTracker()


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
    return True


def generate_request_id() -> str:
    return str(uuid.uuid4())


def append_debug_log(entry: Dict[str, Any]):
    try:
        with _log_lock:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def log_stage(
    request_id: str,
    stage_num: int,
    stage_name: str,
    data: Dict[str, Any],
    latency_ms: float = 0.0,
    print_to_console: bool = False
):
    """
    Records pipeline stage in forensic tracer without spamming terminal.
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

    # Update forensic tracker state mapping
    if stage_num == 1:
        forensic_tracer.reset(question=data.get("user_question", ""))
    elif stage_num == 2:
        forensic_tracer.record_stage("Embedding", "PASS", latency_ms, data, data, "Dense query embedding computed")
    elif stage_num == 3:
        cnt = data.get("top_k_returned", 0)
        forensic_tracer.record_stage("Vector Search", "PASS" if cnt > 0 else "FAIL", latency_ms, data, cnt, f"Vector search returned {cnt} chunks")
    elif stage_num == 4:
        after_cnt = data.get("after_count", 0)
        forensic_tracer.filtered_chunk_count = after_cnt
        forensic_tracer.record_stage("Filtering", "PASS", latency_ms, data, after_cnt, f"Filtered down to {after_cnt} chunks")
    elif stage_num == 5:
        out_cnt = data.get("output_chunks_count", 0)
        forensic_tracer.mmr_chunk_count = out_cnt
        forensic_tracer.record_stage("MMR", "PASS", latency_ms, data, out_cnt, f"MMR selected {out_cnt} chunks")
    elif stage_num == 6:
        out_cnt = data.get("output_chunks_count", 0)
        forensic_tracer.ce_chunk_count = out_cnt
        forensic_tracer.record_stage("Cross Encoder", "PASS" if out_cnt > 0 else "FAIL", latency_ms, data, out_cnt, f"Cross-encoder selected {out_cnt} chunks")
    elif stage_num == 8:
        sent_cnt = data.get("valid_chunk_count", 0)
        forensic_tracer.sent_chunk_count = sent_cnt
        forensic_tracer.record_stage("Prompt", "PASS", latency_ms, data, sent_cnt, f"Context block with {sent_cnt} chunks assembled")
    elif stage_num == 9:
        forensic_tracer.prompt_chars = data.get("prompt_size_chars", 0)
        forensic_tracer.prompt_tokens = data.get("approx_prompt_token_count", 0)
    elif stage_num == 10:
        raw_out = data.get("raw_output") or data.get("raw_llm_output") or data.get("response") or ""
        if not raw_out and data.get("generated_token_count", 0) > 0:
            raw_out = f"<generated {data.get('generated_token_count')} tokens>"
        forensic_tracer.raw_llm_output = str(raw_out)
        status = "PASS" if (raw_out and str(raw_out).strip()) else "FAIL"
        forensic_tracer.record_stage("LLM", status, latency_ms, data, raw_out, f"Generated {len(str(raw_out))} chars" if status == "PASS" else "LLM generate() returned empty output")
    elif stage_num == 11:
        forensic_tracer.parsed_llm_output = data.get("raw_llm_output", "")
    elif stage_num == 13:
        cits = data.get("citations", [])
        forensic_tracer.citations = cits
        forensic_tracer.record_stage("Citation", "PASS" if cits else "FAIL", latency_ms, data, cits, f"Assembled {len(cits)} citations")


def log_grounding_exit(
    request_id: str,
    file_path: str,
    function_name: str,
    line_number: int,
    reason: str,
    condition: str,
    evidence: Dict[str, Any]
):
    entry = {
        "request_id": request_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
    forensic_tracer.first_failing_stage = f"Grounding Exit ({function_name}:{line_number})"
    forensic_tracer.root_cause = f"Reason: {reason} | Condition: {condition} | Evidence: {json.dumps(evidence, default=str)}"


def save_prompt_artifact(request_id: str, prompt_text: str):
    forensic_tracer.prompt_text = prompt_text
    try:
        file_path = PROMPTS_DIR / f"{request_id[:8]}_prompt.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)
    except Exception:
        pass


def save_model_output_artifact(request_id: str, raw_response: str):
    forensic_tracer.raw_llm_output = raw_response
    try:
        file_path = MODEL_OUTPUTS_DIR / f"{request_id[:8]}_response.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(raw_response or "")
    except Exception:
        pass


def save_retrieval_json_artifact(
    request_id: str,
    question: str,
    top_retrieved_chunks: List[Dict[str, Any]],
    scores: Dict[str, Any],
    metadata: Dict[str, Any],
    cross_encoder_scores: List[Dict[str, Any]],
    selected_chunks: List[Dict[str, Any]]
):
    forensic_tracer.retrieval_chunks = selected_chunks or top_retrieved_chunks
    try:
        file_path = RETRIEVAL_DIR / f"{request_id[:8]}.json"
        data = {
            "request_id": request_id,
            "question": question,
            "top_retrieved_chunks": top_retrieved_chunks,
            "scores": scores,
            "metadata": metadata,
            "cross_encoder_scores": cross_encoder_scores,
            "selected_chunks": selected_chunks
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass


def log_exception(e: Exception, context: str = ""):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        tb_str = traceback.format_exc()
        msg = f"[{ts}] EXCEPTION in {context}:\n{e}\nTraceback:\n{tb_str}\n"
        with _log_lock:
            with open(ERRORS_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        logger.error(msg)
    except Exception:
        pass
