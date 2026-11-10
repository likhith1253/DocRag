# Experiment results

Each protocol-compliant run is stored in its own timestamped directory. `raw.json` contains per-question predictions/rankings, metrics, frozen dataset revision/hash, configuration hash, model/runtime metadata, evaluator SHA-256, and the Git commit. Never edit result files by hand.

Runs made before the evaluator and research protocol were frozen are local exploratory smoke checks and are ignored by Git. They are not included in paper tables or headline results. The first 25-question validation prefix is only a performance/schema smoke check.

A development run on the validation split may guide implementation choices. The official test split can only be run with `--allow-test`, after the protocol and code are frozen. Preserve every test output. Failure counts, confidence intervals, paired tests, and paper tables must be generated from raw files.

There are no final study results here yet.
