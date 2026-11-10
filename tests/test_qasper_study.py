import json

import pytest

from eval import qasper_study
from eval.qasper_study import _paired_inference, _rank_metrics, _rrf, normalize, _questions


def test_normalize_is_unicode_and_punctuation_stable():
    assert normalize("Café—TABLE 2!") == "café table 2"


def test_rank_metrics_count_all_annotated_relevant_units():
    metrics = _rank_metrics(["p2", "p1", "p3"], {"p1", "p3"}, 2)
    assert metrics["recall"] == 0.5
    assert metrics["mrr"] == 0.5
    assert metrics["ndcg"] > 0


def test_reciprocal_rank_fusion_is_deterministic():
    assert _rrf([["a", "b"], ["b", "a"]]) == ["a", "b"]


def test_paired_inference_is_seeded_and_excludes_missing_queries():
    records = [
        {"mappable": True, "gold_types": ["table_reference"], "metrics": {
            "structure": {"recall@10": 1.0}, "mmr": {"recall@10": 0.0},
        }},
        {"mappable": True, "gold_types": [], "metrics": {
            "structure": {"recall@10": 0.0}, "mmr": {"recall@10": 0.0},
        }},
        {"mappable": False},
    ]
    first = _paired_inference(records, "structure", "mmr", subset="table_figure", n_resamples=200)
    second = _paired_inference(records, "structure", "mmr", subset="table_figure", n_resamples=200)
    assert first == second
    assert first["n"] == 1
    assert first["mean_difference"] == 1.0


def test_test_split_requires_explicit_opt_in(monkeypatch, tmp_path):
    data = tmp_path / "test.parquet"
    data.write_bytes(b"frozen")
    manifest = tmp_path / "manifest.json"
    import hashlib

    manifest.write_text(json.dumps({
        "revision": "fixed",
        "files": {"test": {"sha256": hashlib.sha256(b"frozen").hexdigest()}},
    }), encoding="utf-8")
    monkeypatch.setattr(qasper_study, "MANIFEST", manifest)
    monkeypatch.setattr(qasper_study, "DATA_DIR", tmp_path)
    monkeypatch.setattr(qasper_study, "ALLOW_TEST", False)
    with pytest.raises(PermissionError, match="--allow-test"):
        qasper_study.evaluate("test", ["bm25"], 10, 40)


def test_qasper_annotation_extraction_handles_nested_arrays():
    import numpy as np

    row = {
        "id": "paper-1",
        "qas": {
            "question": np.array(["Where is the result?"], dtype=object),
            "question_id": np.array(["q-1"], dtype=object),
            "answers": np.array([{
                "answer": np.array([{
                    "unanswerable": False,
                    "highlighted_evidence": np.array(["Table 1 shows 5."], dtype=object),
                    "evidence": np.array([], dtype=object),
                }], dtype=object),
            }], dtype=object),
        },
    }
    question = _questions(row)[0]
    assert question.id == "q-1"
    assert question.gold_evidence == ("Table 1 shows 5.",)
    assert question.unanswerable is False
