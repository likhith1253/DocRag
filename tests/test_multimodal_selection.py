from __future__ import annotations

import json

import numpy as np

from eval.multimodal_selection import (
    example_metrics,
    load_mmdoc,
    load_spiqa,
    select_indices,
)


def test_mmdoc_loader_checks_candidate_gold_alignment(tmp_path) -> None:
    row = {
        "q_id": 1,
        "question": "Which treatment is supported?",
        "text_quotes": [{"quote_id": "text1", "text": "Treatment A improved survival."}],
        "img_quotes": [{"quote_id": "image1", "img_description": "Plot of survival by group."}],
        "gold_quotes": ["text1", "image1"],
    }
    path = tmp_path / "sample.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    loaded, unanswerable = load_mmdoc(path)
    assert unanswerable == 0
    assert loaded[0]["gold"] == {"text1", "image1"}
    assert [candidate["modality"] for candidate in loaded[0]["candidates"]] == ["text", "image"]


def test_spiqa_dev_adapter_maps_caption_reference(tmp_path) -> None:
    path = tmp_path / "spiqa_dev.json"
    path.write_text(json.dumps({"paper": {
        "all_figures": {"fig1": "Figure one caption", "fig2": "Figure two caption"},
        "qa": [{"question": "What peaks?", "reference": "fig2"}],
    }}), encoding="utf-8")
    loaded = load_spiqa(path, "dev")
    assert len(loaded) == 1
    assert loaded[0]["gold"] == {"fig2"}


def test_spiqa_test_adapter_requires_context_to_map_to_passage(tmp_path) -> None:
    path = tmp_path / "spiqa_test.json"
    path.write_text(json.dumps({"paper": {
        "all_figures_tables": {"fig1": "Plot of results"},
        "question": ["What changed?"],
        "referred_figures_tables": [["fig1"]],
        "evidential_info": [[{"context": "Treatment improved survival."}]],
        "passages": ["The study finds that treatment improved survival."],
    }}), encoding="utf-8")
    loaded = load_spiqa(path, "test")
    assert loaded[0]["alignment_complete"] is True
    assert loaded[0]["cross_modal"] is True
    assert loaded[0]["gold"] == {"fig1", "text:p0"}


def test_balanced_policy_uses_equal_quota_at_even_budget() -> None:
    candidates = [
        {"id": "t1", "modality": "text"}, {"id": "t2", "modality": "text"},
        {"id": "i1", "modality": "image"}, {"id": "i2", "modality": "image"},
    ]
    selected = select_indices("balanced_bm25", candidates, np.array([4., 3., 2., 1.]), {"t1", "i1"}, 2)
    assert {candidates[index]["modality"] for index in selected} == {"text", "image"}


def test_oracle_allocates_by_gold_modality_and_complete_metric_is_exact() -> None:
    candidates = [
        {"id": "t1", "modality": "text"}, {"id": "t2", "modality": "text"},
        {"id": "i1", "modality": "image"}, {"id": "i2", "modality": "image"},
    ]
    scores = np.array([1., 9., 8., 7.])
    gold = {"t1", "i1", "i2"}
    selected = select_indices("oracle", candidates, scores, gold, 3)
    assert len(selected) == 3
    assert sum(candidates[index]["modality"] == "text" for index in selected) == 1
    assert sum(candidates[index]["modality"] == "image" for index in selected) == 2
    assert example_metrics([0, 2, 3], candidates, gold)["complete"] == 1.0
