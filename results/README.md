# Experiment results

Each protocol-compliant run is stored in its own timestamped directory. `raw.json` contains per-question predictions/rankings, metrics, frozen dataset revision/hash, configuration hash, model/runtime metadata, evaluator SHA-256, and the Git commit. Never edit result files by hand.

Runs made before the evaluator and research protocol were frozen are exploratory checks and are not included in paper tables or headline results. The timestamped single-condition BM25 validation run is retained as a development artifact; it is not compared with the later six-condition run. A small validation prefix was used only as a performance/schema smoke check.

A development run on the validation split may guide implementation choices. The official test split can only be run with `--allow-test`, after the protocol and code are frozen. Preserve every test output. Failure counts, confidence intervals, paired tests, and paper tables must be generated from raw files.

Final study results are added only after the clean, frozen test evaluation. Dataset statistics and local verification logs are separate from retrieval metrics and carry their own timestamp, configuration hash, and Git commit.
