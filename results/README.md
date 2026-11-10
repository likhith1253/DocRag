# Experiment results

Each protocol-compliant run is stored in its own timestamped directory. `raw.json` contains per-question predictions/rankings, metrics, frozen dataset revision/hash, configuration hash, model/runtime metadata, evaluator SHA-256, and the Git commit. Never edit result files by hand.

Runs made before the evaluator and research protocol were frozen are exploratory checks and are not included in paper tables or headline results. The timestamped single-condition BM25 validation run is retained as a development artifact; it is not compared with the later six-condition run. A small validation prefix was used only as a performance/schema smoke check.

A development run on the validation split may guide implementation choices. The official test split can only be run with `--allow-test`, after the protocol and code are frozen. Preserve every test output. Failure counts, confidence intervals, paired tests, and paper tables must be generated from raw files.

Final study results are added only after the clean, frozen test evaluation. Dataset statistics and local verification logs are separate from retrieval metrics and carry their own timestamp, configuration hash, and Git commit.

The clean protocol-code validation run is `20261110T051423Z_validation_7fc2c2d087`. Its `raw.json` has `git_worktree_dirty=false`, evaluator SHA-256 `2f34158c765cef7f8857d031d4519466ebb3d7fb5e55689a039f802c6a119864`, and is development evidence only. It is not a source for manuscript result claims.
# Research output provenance

Only runs whose protocol commit, evaluator hash, configuration, and dataset hash are explicitly frozen should be cited in the manuscript. The timestamped `*_validation_*` directories generated before the protocol commit are development artifacts only. In particular, `20261110T015105Z_validation_32a16e63d2` is a short schema/performance smoke run and `20261110T041025Z_validation_7fc2c2d087` is a full validation run captured with a dirty worktree. Neither supports paper claims. The clean protocol-commit validation rerun and guarded test run are separate artifacts.

