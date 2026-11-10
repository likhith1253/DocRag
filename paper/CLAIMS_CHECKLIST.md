# Claim-to-evidence checklist

Complete the result path and check each item against the saved raw output after `make reproduce`.

| Manuscript claim | Required supporting artifact | Status |
|---|---|---|
| Benchmark provenance, split hashes, model and software versions | `data/frozen/qasper_manifest.json`; test run `raw.json` | Pending frozen test run |
| Ranking metrics for every retrieval condition | Test run `raw.json` and generated `main_results.tex` | Pending frozen test run |
| Structure-aware vs MMR table/figure subset estimate, 95% CI, paired p-value, and n | Test run `raw.json` key `paired_comparisons.structure_minus_mmr_table_figure` | Pending frozen test run |
| Overall structure-aware vs MMR estimate and non-inferiority assessment | Test run `raw.json` key `paired_comparisons.structure_minus_mmr_all` | Pending frozen test run |
| Retrieval failure counts and representative misses | Test run `failure_analysis.json` | Pending frozen test run |
| Dataset and benchmark description | Verified QASPER entry in `references.bib` and frozen data manifest | Source verified; author review pending |

Before submission, replace this checklist with the exact result directory and confirm each statement. Remove or weaken any claim not directly supported by that raw output. Do not infer answer quality, faithfulness, or general scientific QA performance from retrieval metrics.
