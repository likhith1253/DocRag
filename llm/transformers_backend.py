import os
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
            cfg_model = self._gen_config.get("hf_model") or self._gen_config.get("model")
            if cfg_model and "/" in str(cfg_model):
                model_name = cfg_model
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
                return cfg.get("generation", {}) if cfg else {}
            except Exception:
                return {}
        return {}

    def generate(self, prompt: str, model: str = None) -> str:
        """
        Generate text response using HuggingFace Transformers model.
        """
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

        # Configurable generation parameters
        max_new_tokens = int(self._gen_config.get("num_predict", 1024))
        temperature = float(self._gen_config.get("temperature", 0.7))
        top_p = float(self._gen_config.get("top_p", 0.9))

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

        with torch.inference_mode():
            output_ids = self.model.generate(**inputs, **gen_kwargs)

        generated_ids = output_ids[0][input_length:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        return response.strip()

    def generate_stream(self, prompt: str, model: str = None):
        """
        Stream generated text using TextIteratorStreamer.
        """
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

        max_new_tokens = int(self._gen_config.get("num_predict", 1024))
        temperature = float(self._gen_config.get("temperature", 0.7))
        top_p = float(self._gen_config.get("top_p", 0.9))

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
