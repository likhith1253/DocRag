import unittest
from unittest.mock import patch, MagicMock

from storage.vector_store import (
    _load_with_gpu_fallback,
    _get_embedding_batch_size,
    _get_embedding_device,
)


class TestGpuEmbeddingSelection(unittest.TestCase):
    def test_cpu_preferred_device_never_touches_cuda(self):
        calls = []
        model, device = _load_with_gpu_fallback(
            "Embedding", "fake-model", "cpu", lambda d: calls.append(d) or f"model-{d}"
        )
        self.assertEqual(device, "cpu")
        self.assertEqual(calls, ["cpu"])

    @patch("torch.cuda.is_available", return_value=False)
    def test_cuda_requested_but_unavailable_falls_back_to_cpu(self, mock_avail):
        calls = []
        model, device = _load_with_gpu_fallback(
            "Embedding", "fake-model", "cuda", lambda d: calls.append(d) or f"model-{d}"
        )
        self.assertEqual(device, "cpu")
        self.assertEqual(calls, ["cpu"])

    @patch("torch.cuda.get_device_name", return_value="Tesla V100-PCIE-16GB")
    @patch("torch.cuda.is_available", return_value=True)
    def test_cuda_used_when_available_and_load_succeeds(self, mock_avail, mock_name):
        calls = []
        model, device = _load_with_gpu_fallback(
            "Embedding", "fake-model", "cuda", lambda d: calls.append(d) or f"model-{d}"
        )
        self.assertEqual(device, "cuda")
        self.assertEqual(calls, ["cuda"])
        self.assertEqual(model, "model-cuda")

    @patch("torch.cuda.is_available", return_value=True)
    def test_cuda_load_failure_gracefully_falls_back_to_cpu(self, mock_avail):
        def flaky_loader(d):
            if d == "cuda":
                raise RuntimeError("CUDA out of memory")
            return f"model-{d}"

        model, device = _load_with_gpu_fallback("Embedding", "fake-model", "cuda", flaky_loader)
        self.assertEqual(device, "cpu")
        self.assertEqual(model, "model-cpu")

    def test_embedding_batch_size_default(self):
        self.assertEqual(_get_embedding_batch_size({"embedding": {}}), 32)
        self.assertEqual(_get_embedding_batch_size({}), 32)

    def test_embedding_batch_size_configured(self):
        self.assertEqual(_get_embedding_batch_size({"embedding": {"batch_size": 64}}), 64)

    def test_embedding_batch_size_invalid_value_falls_back_to_default(self):
        self.assertEqual(_get_embedding_batch_size({"embedding": {"batch_size": "not-a-number"}}), 32)

    def test_embedding_device_auto_resolves_by_cuda_availability(self):
        with patch("torch.cuda.is_available", return_value=True):
            self.assertEqual(_get_embedding_device({"embedding": {"device": "auto"}}), "cuda")
        with patch("torch.cuda.is_available", return_value=False):
            self.assertEqual(_get_embedding_device({"embedding": {"device": "auto"}}), "cpu")

    def test_embedding_device_explicit_cpu_overrides_auto_default(self):
        self.assertEqual(_get_embedding_device({"embedding": {"device": "cpu"}, "device": "auto"}), "cpu")


if __name__ == "__main__":
    unittest.main()
