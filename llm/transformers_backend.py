import os
import time
import torch
import yaml
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
from llm.backend_factory import LLMBackend

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

class HFTransformersBackend(LLMBackend):
    def __init__(self, model_name: str = None):
        self._gen_config = self._load_gen_config()
        
        # Model selection precedence:
        # 1. model_name parameter
        # 2. Environment variables: HF_MODEL or LLM_MODEL
        # 3. config.yaml (hf_model)
        # 4. Default: "Qwen/Qwen2.5-3B-Instruct"
        if not model_name:
            model_name = os.environ.get("HF_MODEL") or os.environ.get("LLM_MODEL")
        if not model_name:
            cfg_model = self._gen_config.get("hf_model") or self._gen_config.get("model") or self._gen_config.get("doc_agent_model")
            if cfg_model and "/" in str(cfg_model):
                model_name = str(cfg_model)
        if not model_name:
            model_name = "Qwen/Qwen2.5-3B-Instruct"
            
        self.model_name = model_name

        # Automatic device and dtype selection
        if torch.cuda.is_available():
            self.device = "cuda"
            self.gpu_name = torch.cuda.get_device_name(0)
            self.dtype = torch.float16
            self.dtype_str = "float16"
        else:
            self.device = "cpu"
            self.gpu_name = "N/A"
            self.dtype = torch.float32
            self.dtype_str = "float32"

        # Lazy loading attributes for singleton model & tokenizer
        self.tokenizer = None
        self.model = None

    def _ensure_loaded(self):
        """Lazy load tokenizer and model on first generation call."""
        if self.model is not None and self.tokenizer is not None:
            return

        # Startup logging
        print("=" * 40)
        print(f"LLM Backend : transformers")
        print(f"Model       : {self.model_name}")
        print(f"Device      : {self.device}")
        if self.device == "cuda":
            print(f"GPU         : {self.gpu_name}")
            print(f"dtype       : {self.dtype_str}")
        print("=" * 40)

        # Load Tokenizer & Model exactly ONCE into memory
        print(f"Loading HuggingFace tokenizer '{self.model_name}'...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        print(f"Loading HuggingFace model '{self.model_name}' on {self.device} ({self.dtype_str})...")
        if self.device == "cuda":
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=self.dtype,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=self.dtype,
                trust_remote_code=True
            ).to(self.device)
            
        self.model.eval()
        print("HuggingFace Transformers model loaded successfully.")

    def _load_gen_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                return cfg if cfg else {}
            except Exception:
                return {}
        return {}

    def generate(self, prompt: str, model: str = None, request_id: str = "default") -> str:
        """
        Generate text response using HuggingFace Transformers model.
        """
        self._ensure_loaded()
        from storage.pipeline_logger import log_stage

        t_tok_start = time.perf_counter()
        messages = [{"role": "user", "content": prompt}]
        try:
            text_input = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        except Exception:
            text_input = prompt

        inputs = self.tokenizer(text_input, return_tensors="pt")
        inputs = {k: v.to(self.device) if hasattr(v, "to") else v for k, v in inputs.items()}
        input_length = inputs["input_ids"].shape[1]
        t_tok_end = time.perf_counter()

        # QUESTION 8 CHECK: If prompt exceeds model context, STOP immediately and raise RuntimeError
        max_context_length = getattr(self.model.config, "max_position_embeddings", 32768) if self.model else 32768
        if input_length > max_context_length:
            raise RuntimeError(
                f"PROMPT EXCEEDS MODEL CONTEXT LIMIT: {input_length} tokens > max {max_context_length} tokens! "
                f"Halting execution immediately without truncation."
            )

        cuda_device_str = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A (CPU Mode)"
        input_tensor_device = str(inputs["input_ids"].device)
        model_device = str(next(self.model.parameters()).device) if self.model else self.device

        # Configurable generation parameters
        gen_section = self._gen_config.get("generation", {})
        max_new_tokens = int(gen_section.get("num_predict", 1024))
        temperature = float(gen_section.get("temperature", 0.0))
        top_p = float(gen_section.get("top_p", 0.9))
        top_k_param = int(gen_section.get("top_k", 50))
        repetition_penalty = float(gen_section.get("repetition_penalty", 1.0))

        gen_kwargs = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }

        if temperature > 0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
        else:
            gen_kwargs["do_sample"] = False

        if repetition_penalty != 1.0:
            gen_kwargs["repetition_penalty"] = repetition_penalty

        print(f"\n==================================================", flush=True)
        print(f"STAGE 10: STAGE 10 INVOCATION (HFTransformersBackend)", flush=True)
        print(f"==================================================", flush=True)
        print(f"Device: {self.device} ({cuda_device_str}) | dtype: {self.dtype_str}", flush=True)
        print(f"Generation Config: max_new_tokens={max_new_tokens}, temp={temperature}, top_p={top_p}, do_sample={gen_kwargs.get('do_sample')}", flush=True)
        print(f"Input Token Count: {input_length} | Prompt Chars: {len(prompt)}", flush=True)
        print("BEGIN GENERATION...", flush=True)

        t_gen_start = time.perf_counter()

        import threading
        stop_heartbeat = threading.Event()
        def _heartbeat():
            elapsed_sec = 0
            while not stop_heartbeat.wait(2.0):
                elapsed_sec += 2
                print(f"      │  [LLM Progress] Generating tokens... elapsed: {elapsed_sec}s", flush=True)

        ticker = threading.Thread(target=_heartbeat, daemon=True)
        ticker.start()
        try:
            with torch.inference_mode():
                output_ids = self.model.generate(**inputs, **gen_kwargs)
        finally:
            stop_heartbeat.set()
            ticker.join(timeout=1.0)

        t_gen_end = time.perf_counter()
        gen_ms = (t_gen_end - t_gen_start) * 1000
        gen_sec = gen_ms / 1000.0
        generated_token_count = len(output_ids[0]) - input_length
        tokens_per_sec = (generated_token_count / gen_sec) if gen_sec > 0 else 0.0

        eos_reached = bool(output_ids[0][-1] == self.tokenizer.eos_token_id)
        max_tokens_reached = bool(generated_token_count >= max_new_tokens)

        t_dec_start = time.perf_counter()
        generated_ids = output_ids[0][input_length:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        t_dec_end = time.perf_counter()
        dec_ms = (t_dec_end - t_dec_start) * 1000

        # QUESTION 2 REQUIREMENT: Save raw generation to logs/raw_generation.txt
        raw_gen_path = Path(__file__).parent.parent / "logs" / "raw_generation.txt"
        try:
            with open(raw_gen_path, "w", encoding="utf-8") as f:
                f.write(response)
        except Exception:
            pass

        stage10_data = {
            "device": self.device,
            "gpu_name": cuda_device_str,
            "dtype": self.dtype_str,
            "generation_config": {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k_param,
                "do_sample": gen_kwargs.get("do_sample"),
                "repetition_penalty": repetition_penalty
            },
            "input_token_count": input_length,
            "prompt_length_chars": len(prompt),
            "generation_time_ms": round(gen_ms, 2),
            "generated_token_count": generated_token_count,
            "tokens_per_sec": round(tokens_per_sec, 2),
            "eos_reached": eos_reached,
            "max_new_tokens_reached": max_tokens_reached,
            "stop_reason": "EOS token reached" if eos_reached else ("max_new_tokens limit reached" if max_tokens_reached else "completed")
        }

        log_stage(request_id, 10, "HFTransformersBackend.generate", stage10_data, latency_ms=gen_ms)

        print(f"Generation finished in {gen_ms:.2f} ms ({generated_token_count} tokens @ {tokens_per_sec:.2f} tok/s)", flush=True)
        print(f"Stop Reason: {stage10_data['stop_reason']}", flush=True)

        return response.strip()

    def generate_stream(self, prompt: str, model: str = None):
        """
        Stream generated text using TextIteratorStreamer.
        """
        self._ensure_loaded()

        from transformers import TextIteratorStreamer
        from threading import Thread

        messages = [{"role": "user", "content": prompt}]
        try:
            text_input = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        except Exception:
            text_input = prompt

        inputs = self.tokenizer(text_input, return_tensors="pt")
        inputs = {k: v.to(self.device) if hasattr(v, "to") else v for k, v in inputs.items()}

        gen_section = self._gen_config.get("generation", {})
        max_new_tokens = int(gen_section.get("num_predict", 1024))
        temperature = float(gen_section.get("temperature", 0.7))
        top_p = float(gen_section.get("top_p", 0.9))

        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        gen_kwargs = {
            **inputs,
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
            "streamer": streamer,
        }

        if temperature > 0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
        else:
            gen_kwargs["do_sample"] = False

        def _generate_worker():
            with torch.inference_mode():
                self.model.generate(**gen_kwargs)

        thread = Thread(target=_generate_worker)
        thread.start()

        for new_text in streamer:
            yield new_text

# Standalone function for backward compatibility
def generate(prompt: str, model: str) -> str:
    from llm.backend_factory import get_backend
    backend = get_backend("transformers")
    return backend.generate(prompt, model)
