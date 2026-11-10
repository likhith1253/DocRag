"""Generate manuscript tables from one saved retrieval run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


LABELS = {
    "bm25": "BM25",
    "dense": "Dense",
    "hybrid": "BM25 + Dense (RRF)",
    "rerank": "Hybrid + Cross-Encoder",
    "mmr": "Hybrid + Reranker + MMR",
    "structure": "MMR + Structure",
}
METRICS = ("recall@5", "recall@10", "mrr", "ndcg@10")


def generate(raw_path: Path) -> tuple[Path, Path, Path]:
    run = json.loads(raw_path.read_text(encoding="utf-8"))
    systems = run["config"]["systems"]
    rows = []
    for system in systems:
        summary = run["summary"][system]
        rows.append({"system": LABELS.get(system, system), **summary})

    csv_path = raw_path.parent / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["system", *METRICS])
        writer.writeheader()
        writer.writerows(rows)
    (raw_path.parent / "summary_metadata.json").write_text(json.dumps({
        "source_raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "config_sha256": run["config_sha256"],
        "git_commit": run["git_commit"],
    }, indent=2) + "\n", encoding="utf-8")

    tex_path = raw_path.parent / "main_results.tex"
    with tex_path.open("w", encoding="utf-8") as stream:
        stream.write("% Generated from raw.json. Do not edit by hand.\n")
        stream.write(f"% config_sha256={run['config_sha256']}\n")
        stream.write("\\begin{tabular}{lrrrr}\n")
        stream.write("\\toprule\nSystem & Recall@5 & Recall@10 & MRR & nDCG@10 \\\\\n")
        stream.write("\\midrule\n")
        for row in rows:
            values = [row["system"], *[f"{row[m]:.3f}" if row[m] is not None else "--" for m in METRICS]]
            stream.write(" & ".join(values) + " \\\\\n")
        stream.write("\\bottomrule\n\\end{tabular}\n")
        comparison = run.get("paired_comparisons", {}).get("structure_minus_mmr_table_figure")
        if comparison:
            ci = comparison.get("bootstrap_95_ci")
            if ci:
                stream.write(
                    "\\par\\smallskip\\footnotesize "
                    "Structure-aware minus MMR on the predeclared table/figure subset: "
                    f"\\Delta Recall@10={comparison['mean_difference']:.3f}, "
                    f"95\\% CI [{ci[0]:.3f}, {ci[1]:.3f}], "
                    f"paired randomization \\emph{{p}}={comparison['paired_randomization_p']:.4f}; "
                    f"n={comparison['n']}.\n"
                )
        overall = run.get("paired_comparisons", {}).get("structure_minus_mmr_all")
        if overall and overall.get("bootstrap_95_ci"):
            ci = overall["bootstrap_95_ci"]
            stream.write(
                "\\par\\footnotesize Overall structure-aware minus MMR: "
                f"\\Delta Recall@10={overall['mean_difference']:.3f}, "
                f"95\\% CI [{ci[0]:.3f}, {ci[1]:.3f}], "
                f"paired randomization \\emph{{p}}={overall['paired_randomization_p']:.4f}; "
                f"n={overall['n']}.\n"
            )
    pairwise_path = raw_path.parent / "pairwise_comparisons.tex"
    pairwise = run.get("paired_comparisons", {}).get("pairwise_recall10_overall", {}).get("comparisons", {})
    with pairwise_path.open("w", encoding="utf-8") as stream:
        stream.write("% Generated from raw.json. Do not edit by hand.\n")
        stream.write("\\begin{tabular}{lrrrr}\n\\toprule\n")
        stream.write("Contrast & Mean difference & 95\\% CI & Holm adjusted \\emph{p} & n \\\\\n")
        stream.write("\\midrule\n")
        for name, comparison in pairwise.items():
            ci = comparison.get("bootstrap_95_ci")
            if ci is None:
                continue
            first, _, second = name.partition("_minus_")
            label = f"{LABELS.get(first, first)} $-$ {LABELS.get(second, second)}"
            stream.write(
                f"{label} & {comparison['mean_difference']:.3f} "
                f"& [{ci[0]:.3f}, {ci[1]:.3f}] "
                f"& {comparison.get('holm_adjusted_p', comparison['paired_randomization_p']):.4f} "
                f"& {comparison['n']} \\\\\n"
            )
        stream.write("\\bottomrule\n\\end{tabular}\n")
    return csv_path, tex_path, pairwise_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_json", type=Path)
    args = parser.parse_args()
    for path in generate(args.raw_json.resolve()):
        print(path)


if __name__ == "__main__":
    main()
