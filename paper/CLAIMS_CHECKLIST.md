# Claim-to-evidence checklist

The final held-out run is `results/20261110T125049Z_test_b266b19c27/`. Before submission, the project owner must still inspect every item and independently verify all references.

| Manuscript claim | Required supporting artifact | Status |
|---|---|---|
| Benchmark provenance, split hashes, model and software versions | `data/frozen/qasper_manifest.json`; test run `raw.json` | Recorded; owner review pending |
| Ranking metrics for every retrieval condition | Test run `raw.json` and `paper/generated/main_results.tex` | Generated from raw run |
| Structure-aware vs MMR table/figure subset estimate, 95% CI, paired p-value, and n | Test run `raw.json` key `paired_comparisons.structure_minus_mmr_table_figure` | H1 not supported; see raw run |
| Overall structure-aware vs MMR estimate and non-inferiority assessment | Test run `raw.json` key `paired_comparisons.structure_minus_mmr_all` | H2 margin met; see raw run |
| Retrieval failure counts and representative misses | Test run `failure_analysis.json` and generated table | Generated from raw run |
| Dataset and benchmark description | Verified QASPER and HQDR entries in `references.bib` and frozen data manifest | Sources verified; owner review pending |

Do not infer answer quality, faithfulness, or general scientific QA performance from retrieval metrics. The owner must verify every claim and reference before any submission.
