import json

import pytest

from eval import qasper_study
from eval.failure_analysis import write_examples, write_tex
from eval.paper_table import generate as generate_paper_table
from eval.qasper_study import _holm_adjust, _paired_inference, _rank_metrics, _rrf, normalize, _questions


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


def test_holm_adjustment_is_monotonic_in_sorted_p_value_order():
    adjusted = _holm_adjust({"small": 0.01, "middle": 0.03, "large": 0.2})
    assert adjusted == {"small": 0.03, "middle": 0.06, "large": 0.2}


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


def test_test_protocol_requires_a_frozen_evaluator_hash():
    with pytest.raises(RuntimeError, match="not recorded"):
        qasper_study.verify_test_protocol({})


def test_paper_table_is_generated_from_saved_raw_json(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps({
        "summary": {"bm25": {"recall@5": 0.25, "recall@10": 0.5, "mrr": 0.3, "ndcg@10": 0.4}},
        "config": {"systems": ["bm25"]}, "config_sha256": "config-hash", "git_commit": "commit-hash",
        "paired_comparisons": {"structure_minus_mmr_table_figure": {
            "mean_difference": 0.125, "bootstrap_95_ci": [0.02, 0.2],
            "paired_randomization_p": 0.01, "n": 12,
        }, "pairwise_recall10_overall": {"comparisons": {
            "structure_minus_mmr": {
                "mean_difference": 0.125, "bootstrap_95_ci": [0.02, 0.2],
                "paired_randomization_p": 0.01, "holm_adjusted_p": 0.02, "n": 12,
            },
        }}},
    }), encoding="utf-8")
    csv_path, tex_path, pairwise_path = generate_paper_table(raw)
    assert "Recall@10" in tex_path.read_text(encoding="utf-8")
    assert "0.500" in tex_path.read_text(encoding="utf-8")
    assert r"\Delta Recall@10=0.125" in tex_path.read_text(encoding="utf-8")
    assert r"95\% CI [0.020, 0.200]" in tex_path.read_text(encoding="utf-8")
    assert "0.020" in pairwise_path.read_text(encoding="utf-8")
    assert "0.0200" in pairwise_path.read_text(encoding="utf-8")
    assert csv_path.exists()
    assert (tmp_path / "summary_metadata.json").exists()


def test_failure_analysis_latex_is_generated_with_escape_and_example(tmp_path):
    report = {
        "counts": {"structure": {
            "retrieval_miss_at_10": 2, "partial_evidence_retrieval_at_10": 3,
            "all_mapped_evidence_retrieved_at_10": 4,
            "table_figure_reference_miss_at_10": 1, "table_figure_reference_questions": 5,
        }},
        "representative_retrieval_misses": {"structure": [{
            "question_id": "q_1", "question": "What is A & B?", "gold_evidence_text": ["Value is 5%"],
        }]},
    }
    table = tmp_path / "failure_analysis.tex"
    examples = tmp_path / "failure_examples.tex"
    write_tex(report, table)
    write_examples(report, examples)
    assert "2 & 3 & 4 & 1/5" in table.read_text(encoding="utf-8")
    example_text = examples.read_text(encoding="utf-8")
    assert "A \\& B" in example_text
    assert "5\\%" in example_text


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
