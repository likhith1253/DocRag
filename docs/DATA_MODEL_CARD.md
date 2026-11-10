# Data and model card

## Intended use

Research prototype for retrieval of evidence in English scientific papers and engineering experiments in document-grounded QA. Not validated for medical, legal, or other high-stakes decision support.

## Evaluation data

Primary data: QASPER, from the pinned `allenai/qasper` revision in `data/frozen/qasper_manifest.json`. The [pinned dataset card](https://huggingface.co/datasets/allenai/qasper/blob/b3777208796afdd8e7459dff4e6a28294c6ae3af/README.md) identifies CC BY 4.0 and describes expert-generated question/answer annotations over NLP papers. The original dataset paper is Dasigi et al., NAACL-HLT 2021, DOI 10.18653/v1/2021.naacl-main.365. The split files are downloaded by `scripts/download_qasper.py`, verified against the manifest, and are not committed. The official train split is unused; validation is development; test is held out.

Known limitations include NLP-domain concentration, potential incompleteness of highlighted evidence, text-only access to figure/table captions, and an evidence mapping that only credits exact normalized containment. The project does not claim that this benchmark represents all sciences or all real user queries.

## Models

The primary retrieval embedding is [`intfloat/e5-small-v2`](https://huggingface.co/intfloat/e5-small-v2), pinned to revision `ffb93f3bd4047442299a41ebb6fa998a38507c52`; its official Hugging Face model card reports MIT licensing. The reranker is [`cross-encoder/ms-marco-MiniLM-L-6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2), pinned to `233902d25c440f23af6f7d6e94d2946bac0bee0a`; its official model card identifies Apache-2.0 licensing. The application defaults to [`Qwen/Qwen2.5-0.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) at revision `7ae557604adf67be50417f59c2c2f167def9a775`; its official model card identifies Apache-2.0 licensing. Generation quality and quantized parity have not been evaluated in this study. The application generation-cache key records this revision. The model card identifies `Qwen/Qwen2.5-1.5B-Instruct` as Apache-2.0 if operators override the setting. The 0.5B CPU generation smoke was executed; it is not an answer-quality evaluation.

## Risks and limitations

Embeddings and rerankers can miss evidence with unusual wording or document structure. A clean numerical risk scan is not proof of entailment. QASPER contains text evidence and references to tables/figures, but this pipeline does not visually interpret figures. Inference and indexing are CPU-first; latency and memory depend on hardware and model caches. No user data should be uploaded to third-party services without explicit review.

## Licensing status

QASPER is attributed under CC BY 4.0 per the pinned dataset card. The source PDFs retained locally from the former demo corpus have unresolved licenses and are excluded. The repository itself has no license file; code ownership and license must be reviewed before redistribution.

## Reproduction

Run `uv run python scripts/dataset_stats.py` to generate aggregate statistics without exporting question text, answers, or rankings. The frozen test evaluation, generated paper tables, and retrieval failure analysis are produced by `make reproduce` after the protocol guard is frozen. The V100 generation job and university Slurm run remain **NOT VERIFIED** until executed on that cluster.
