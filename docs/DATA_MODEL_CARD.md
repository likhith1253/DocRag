# Data and model card

## Intended use

Research prototype for retrieval of evidence in English scientific papers and engineering experiments in document-grounded QA. Not validated for medical, legal, or other high-stakes decision support.

## Primary evaluation data (v2)

The lead study uses MMDocRAG and SPIQA, frozen by repository revisions and file hashes in [`data/frozen/multimodal_manifest.json`](../data/frozen/multimodal_manifest.json). MMDocRAG is used under the official repository's CC BY-NC 4.0 terms for non-commercial research; source files are downloaded by `scripts/download_multimodal_benchmarks.py` and are not committed. SPIQA's official card marks the dataset CC BY 4.0. The SPIQA validation set is used only to exercise the figure-caption adapter; test-B is held out. The benchmark source papers are in `references.bib`.

All counts below are from the executed `scripts/multimodal_dataset_stats.py` artifact [`dataset_stats.json`](../results/20261110T142352Z_multimodal_dataset_stats_985534d2cbd2/dataset_stats.json), not hand-counted estimates. MMDocRAG development contains 2,055 question records over 147 unique documents; its test has 2,000 records over 220 unique documents. The test provides an average of about 12 text candidates and 7.87 image-description candidates per question, with an average of 2.91 gold quotes. SPIQA validation contains 2,085 questions from 200 papers; test-B contains 228 questions from 65 papers. Test-B averages 14.05 figure/table caption candidates and 1.61 annotated visual references per question.

The held-out SPIQA adapter retained 73 test-B questions with complete text-context and figure-reference alignment and excluded 155 under the preregistered rule. The test output and excluded IDs are in [`results/20261110T142218Z_spiqa_test_39e8fba05c7f/raw.json`](../results/20261110T142218Z_spiqa_test_39e8fba05c7f/raw.json). This small retained subset limits the transfer claim.

## Historical evaluation data (QASPER)

The prior retrieval study uses QASPER from the pinned `allenai/qasper` revision in `data/frozen/qasper_manifest.json`. The [pinned dataset card](https://huggingface.co/datasets/allenai/qasper/blob/b3777208796afdd8e7459dff4e6a28294c6ae3af/README.md) identifies CC BY 4.0 and describes expert-generated questions and answers over NLP papers. Its results remain a separate negative precursor and are not pooled with v2. QASPER counts and evidence mapping details are documented in its prior raw run.

MMDocRAG provides fixed quote candidates; image candidates are ranked using provided text descriptions. SPIQA uses supplied paper passages and figure/table captions and does not require image downloads. These data do not test raw visual understanding, PDF parsing, generated answers, or real-world query distribution.

## Models

The primary retrieval embedding is [`intfloat/e5-small-v2`](https://huggingface.co/intfloat/e5-small-v2), pinned to revision `ffb93f3bd4047442299a41ebb6fa998a38507c52`; its official Hugging Face model card reports MIT licensing. The reranker is [`cross-encoder/ms-marco-MiniLM-L-6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2), pinned to `233902d25c440f23af6f7d6e94d2946bac0bee0a`; its official model card identifies Apache-2.0 licensing. The application defaults to [`Qwen/Qwen2.5-0.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) at revision `7ae557604adf67be50417f59c2c2f167def9a775`; its official model card identifies Apache-2.0 licensing. Generation quality and quantized parity have not been evaluated in this study. The application generation-cache key records this revision. The model card identifies `Qwen/Qwen2.5-1.5B-Instruct` as Apache-2.0 if operators override the setting. The 0.5B CPU generation smoke was executed; it is not an answer-quality evaluation.

## Risks and limitations

Embeddings and rerankers can miss evidence with unusual wording or document structure. A clean numerical risk scan is not proof of entailment. QASPER contains text evidence and references to tables/figures, but this pipeline does not visually interpret figures. Inference and indexing are CPU-first; latency and memory depend on hardware and model caches. No user data should be uploaded to third-party services without explicit review.

## Licensing status

QASPER is attributed under CC BY 4.0 per the pinned dataset card. The source PDFs retained locally from the former demo corpus have unresolved licenses and are excluded. The repository itself has no license file; code ownership and license must be reviewed before redistribution.

## Reproduction

Run `uv run python scripts/dataset_stats.py` to generate aggregate statistics without exporting question text, answers, or rankings. The frozen test evaluation, generated paper tables, and retrieval failure analysis are produced by `make reproduce` after the protocol guard is frozen. The V100 generation job and university Slurm run remain **NOT VERIFIED** until executed on that cluster.
