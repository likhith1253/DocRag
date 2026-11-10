"""One-shot CUDA diagnostic for the unresolved V100 generation path."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer


def _memory() -> dict[str, int]:
    return {
        "allocated_bytes": int(torch.cuda.memory_allocated()),
        "reserved_bytes": int(torch.cuda.memory_reserved()),
        "peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
        "peak_reserved_bytes": int(torch.cuda.max_memory_reserved()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--prompt-tokens", type=int, default=7400)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--attention", choices=("eager", "sdpa"), default="eager")
    parser.add_argument("--output-root", type=Path, default=Path("results/v100_diagnostics"))
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable; run this only on the V100 node.")

    torch.cuda.init()
    device = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    record = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model, "attention": args.attention,
        "torch": torch.__version__, "torch_cuda": torch.version.cuda,
        "transformers": transformers.__version__,
        "python": platform.python_version(), "platform": platform.platform(),
        "device": device, "compute_capability": list(capability),
        "prompt_token_target": args.prompt_tokens,
        "max_new_tokens": args.max_new_tokens, "stages": {},
    }
    try:
        record["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True
        ).strip()
        record["git_worktree_dirty"] = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=Path(__file__).resolve().parents[1], text=True
        ).strip())
    except (OSError, subprocess.CalledProcessError):
        record["git_commit"] = "unknown"
        record["git_worktree_dirty"] = True
    config = {key: record[key] for key in (
        "model", "attention", "torch", "torch_cuda", "transformers", "python",
        "device", "compute_capability", "prompt_token_target", "max_new_tokens",
    )}
    record["config_sha256"] = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    model_load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16,
        attn_implementation=args.attention, low_cpu_mem_usage=False,
    ).to("cuda").eval()
    record["model_load_seconds"] = time.perf_counter() - model_load_start
    record["stages"]["after_load"] = _memory()

    fragment = "The paper reports a method, evidence passage, and quantitative result. "
    tokens = tokenizer(fragment, add_special_tokens=False, return_tensors="pt")["input_ids"]
    repeats = (args.prompt_tokens + tokens.shape[1] - 1) // tokens.shape[1]
    input_ids = tokens.repeat(1, repeats)[:, :args.prompt_tokens].to("cuda")
    record["prompt_tokens_actual"] = int(input_ids.shape[1])

    try:
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        with torch.inference_mode():
            full = model(input_ids=input_ids, use_cache=True, return_dict=True)
        record["stages"]["full_sequence_logits"] = {
            **_memory(), "seconds": time.perf_counter() - start,
            "logits_shape": list(full.logits.shape),
        }
        del full
        torch.cuda.empty_cache()

        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        with torch.inference_mode():
            hidden = model.model(input_ids=input_ids, use_cache=True, return_dict=True)
        record["stages"]["base_model_without_lm_head"] = {
            **_memory(), "seconds": time.perf_counter() - start,
            "hidden_shape": list(hidden.last_hidden_state.shape),
        }
        del hidden
        torch.cuda.empty_cache()

        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                input_ids=input_ids, max_new_tokens=args.max_new_tokens,
                do_sample=False, use_cache=True,
            )
        record["stages"]["generation"] = {
            **_memory(), "seconds": time.perf_counter() - start,
            "generated_tokens": int(generated.shape[1] - input_ids.shape[1]),
        }
        record["status"] = "completed"
    except Exception as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        record["error"] = str(exc)
        record["failure_memory"] = _memory()
        try:
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            record["cuda_context_recovered"] = True
        except Exception as recovery_error:
            record["cuda_context_recovered"] = False
            record["recovery_error"] = f"{type(recovery_error).__name__}: {recovery_error}"

    run_dir = args.output_root / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_" + record["config_sha256"][:12]
        + "_" + record["git_commit"][:10]
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    output_path = run_dir / "diagnostic.json"
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    record["output_file"] = str(output_path)
    print(json.dumps(record, indent=2))
    if record["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
