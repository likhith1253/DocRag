"""Regenerate v2 tables, failure counts, and figure from frozen raw runs."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from eval.multimodal_selection import BUDGETS, MANIFEST, POLICIES, PROTOCOL, ROOT, sha256, summarize


def find_test_raw(dataset: str, manifest: dict[str, Any]) -> Path:
    candidates = sorted((ROOT / "results").glob(f"*_{dataset}_test_*/raw.json"))
    for candidate in reversed(candidates):
        data = json.loads(candidate.read_text(encoding="utf-8"))
        expected = manifest["datasets"][dataset]["test"]["sha256"]
        if (data.get("split") == "test" and data.get("dataset_sha256") == expected
                and data.get("protocol_sha256") == sha256(PROTOCOL)
                and data.get("evaluator_sha256") == manifest["evaluator_sha256"]):
            return candidate
    raise FileNotFoundError(f"No frozen protocol-compliant {dataset} test raw.json found")


def tex_escape(text: str) -> str:
    return text.replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    input_paths = {dataset: find_test_raw(dataset, manifest) for dataset in ("mmdocrag", "spiqa")}
    input_hashes = {dataset: sha256(path) for dataset, path in input_paths.items()}
    outputs: dict[str, Any] = {}
    rows_csv: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    failure_examples: list[dict[str, Any]] = []
    policy_tests: list[dict[str, Any]] = []

    for dataset, path in input_paths.items():
        raw = json.loads(path.read_text(encoding="utf-8"))
        metric_rows, inference = summarize(raw["records"], tuple(BUDGETS))
        outputs[dataset] = {"raw": raw, "metrics": metric_rows, "inference": inference}
        policy_tests.extend({"dataset": dataset, **row}
                            for row in inference["exploratory_policy_comparisons"])
        for row in metric_rows:
            rows_csv.append({"dataset": dataset, **row})
        groups = {"all": raw["records"],
                  "cross_modal": [record for record in raw["records"] if record["cross_modal"]],
                  "single_modal": [record for record in raw["records"] if not record["cross_modal"]]}
        for group_name, group_records in groups.items():
            for budget in BUDGETS:
                for policy in POLICIES:
                    counts = {"complete": 0, "partial": 0, "none": 0}
                    for record in group_records:
                        metric = record["metrics"][policy][str(budget)]
                        if metric["complete"]:
                            counts["complete"] += 1
                        elif metric["hits"] == 0:
                            counts["none"] += 1
                        else:
                            counts["partial"] += 1
                    failure_rows.append({"dataset": dataset, "subset": group_name, "budget": budget,
                                         "policy": policy, "complete": counts["complete"],
                                         "partial": counts["partial"], "no_gold_retrieved": counts["none"],
                                         "n": len(group_records)})
        for record in groups["cross_modal"]:
            metric = record["metrics"]["global_bm25"]["10"]
            if metric["complete"]:
                category = "complete"
            elif metric["hits"] == 0:
                category = "no_gold_retrieved"
            else:
                category = "partial"
            selected = set(record["selected_by_budget"]["global_bm25"]["10"])
            failure_examples.append({"dataset": dataset, "question_id": record["id"],
                                     "system": "global_bm25", "budget": 10, "category": category,
                                     "gold_count": len(record["gold_ids"]), "retrieved_gold_count": metric["hits"],
                                     "missed_gold_ids": ";".join(sorted(set(record["gold_ids"]) - selected))})

    generated = ROOT / "paper/generated"
    generated.mkdir(parents=True, exist_ok=True)
    with (generated / "v2_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows_csv[0]))
        writer.writeheader()
        writer.writerows(rows_csv)
    with (generated / "v2_failure_analysis.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(failure_rows[0]))
        writer.writeheader()
        writer.writerows(failure_rows)
    with (generated / "v2_failure_examples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(failure_examples[0]))
        writer.writeheader()
        writer.writerows(failure_examples)
    with (generated / "v2_policy_tests.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(policy_tests[0]))
        writer.writeheader()
        writer.writerows(policy_tests)

    row_end = " \\\\"
    main_tex = [r"\begin{tabular}{llrrrr}", r"\toprule",
                "Dataset & Policy & k & Complete & Recall & F1" + row_end, r"\midrule"]
    for row in rows_csv:
        main_tex.append(f"{tex_escape(row['dataset'])} & {tex_escape(row['policy'])} & {row['budget']} & "
                        f"{row['complete_evidence_coverage']:.3f} & {row['micro_evidence_recall']:.3f} & "
                        f"{row['mean_example_f1']:.3f}" + row_end)
    main_tex.extend((r"\bottomrule", r"\end{tabular}"))
    (generated / "v2_results.tex").write_text("\n".join(main_tex) + "\n", encoding="utf-8")

    primary_tex = [r"\begin{tabular}{lrrrr}", r"\toprule",
                   "Dataset / subset & n & Mean gap & 95\\% CI & p" + row_end, r"\midrule"]
    for dataset, values in outputs.items():
        infer = values["inference"]
        comparisons = [("Cross-modal", infer["primary_evidence_sufficiency_gap"]),
                       ("All answerable", infer["overall_evidence_sufficiency_gap"])]
        for label, item in comparisons:
            if item.get("n"):
                interval = item["bootstrap_95_ci"]
                primary_tex.append(f"{tex_escape(dataset)} {label} & {item['n']} & "
                                   f"{item['mean_example_recall_minus_complete_coverage']:.3f} & "
                                   f"[{interval[0]:.3f}, {interval[1]:.3f}] & "
                                   f"{item['paired_sign_randomization_p_vs_zero']:.4g}" + row_end)
        subgroup = infer["cross_modal_vs_single_modal_gap"]
        if "mean_difference" in subgroup:
            interval = subgroup["bootstrap_95_ci"]
            primary_tex.append(f"{tex_escape(dataset)} cross-modal minus single & "
                               f"{subgroup['n_cross_modal']}+{subgroup['n_single_modal']} & "
                               f"{subgroup['mean_difference']:.3f} & [{interval[0]:.3f}, {interval[1]:.3f}] & "
                               f"{subgroup['permutation_p']:.4g}" + row_end)
    primary_tex.extend((r"\bottomrule", r"\end{tabular}"))
    (generated / "v2_primary.tex").write_text("\n".join(primary_tex) + "\n", encoding="utf-8")

    failure_tex = [r"\begin{tabular}{llrrrr}", r"\toprule",
                   "Dataset & Subset & n & Complete & Partial & No gold" + row_end, r"\midrule"]
    for dataset, values in outputs.items():
        n = len([record for record in values["raw"]["records"] if record["cross_modal"]])
        counts = {"complete": 0, "partial": 0, "none": 0}
        for record in values["raw"]["records"]:
            if not record["cross_modal"]:
                continue
            metric = record["metrics"]["global_bm25"]["10"]
            if metric["complete"]:
                counts["complete"] += 1
            elif metric["hits"] == 0:
                counts["none"] += 1
            else:
                counts["partial"] += 1
        failure_tex.append(f"{tex_escape(dataset)} & Cross-modal & {n} & {counts['complete']} & "
                           f"{counts['partial']} & {counts['none']}" + row_end)
    failure_tex.extend((r"\bottomrule", r"\end{tabular}"))
    (generated / "v2_failures.tex").write_text("\n".join(failure_tex) + "\n", encoding="utf-8")

    policy_tex = [r"\begin{tabular}{llrrrr}", r"\toprule",
                  "Dataset & Policy vs BM25 & n & Complete coverage Δ & 95\\% CI & Holm p" + row_end,
                  r"\midrule"]
    for row in policy_tests:
        low, high = row["bootstrap_95_ci"]
        policy_tex.append(f"{tex_escape(row['dataset'])} & {tex_escape(row['policy'])} & {row['n']} & "
                          f"{row['mean_complete_coverage_difference']:.3f} & [{low:.3f}, {high:.3f}] & "
                          f"{row['holm_adjusted_p']:.4g}" + row_end)
    policy_tex.extend((r"\bottomrule", r"\end{tabular}"))
    (generated / "v2_policy_tests.tex").write_text("\n".join(policy_tex) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors = {"mmdocrag": "#285f8f", "spiqa": "#bd5b32"}
    for dataset, values in outputs.items():
        gaps = values["inference"]["evidence_sufficiency_gap_curves"]["cross_modal"]
        points = [gaps[str(k)]["global_bm25"]["mean_example_recall_minus_complete_coverage"]
                  for k in BUDGETS]
        ax.plot(BUDGETS, points, marker="o", linewidth=2, color=colors[dataset], label=dataset.upper())
    ax.set(xlabel="Evidence quote budget (k)", ylabel="Mean per-question recall − complete-set coverage",
           xticks=BUDGETS, ylim=(0, 1))
    ax.grid(axis="y", alpha=.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(generated / "v2_evidence_gap.png", dpi=220)
    plt.close(fig)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    worktree_dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                                         capture_output=True, text=True).stdout.strip())
    evaluation_commits = sorted({values["raw"]["git_commit"] for values in outputs.values()})
    metadata = {"schema_version": 1, "result_sources": {key: str(path.relative_to(ROOT))
                                                          for key, path in input_paths.items()},
                "raw_sha256": input_hashes, "protocol_sha256": sha256(PROTOCOL),
                "evaluator_sha256": manifest["evaluator_sha256"],
                "reproduction_script_sha256": sha256(Path(__file__)),
                "config_hash": hashlib.sha256(json.dumps(input_hashes, sort_keys=True).encode()).hexdigest()[:12],
                "reproduction_code_commit": commit, "reproduction_worktree_dirty": worktree_dirty,
                "evaluation_commits": evaluation_commits}
    (generated / "v2_reproduction_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
