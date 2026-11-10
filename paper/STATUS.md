# Draft status: preprint draft; owner review required

The paper has a registered question, two independently verified benchmark sources, frozen splits, one-shot held-out runs, generated analysis artifacts, and documented negative results. It is a complete research draft, not a guaranteed Q1 journal result and not ready for submission without the project owner's review.

## Required owner review

**The project owner must personally verify every manuscript claim, every generated value, and every bibliographic reference against its primary source before any arXiv submission. Unchecked AI-generated content or references can result in serious consequences, including an arXiv submission ban.** The owner must also fill in author identities and affiliations, confirm contribution statements and acknowledgments, and check all dataset and software terms.

The draft reports a large gap between per-question quote recall and exact complete evidence-set coverage on MMDocRAG, especially for cross-modal questions. The held-out score-calibration comparison on MMDocRAG is not significant. The SPIQA result is restricted to 73 fully aligned items; 155 test-B examples are excluded by the preregistered rule. No answer-generation, raw-image understanding, human answer grading, or citation-faithfulness result is claimed.

## Build

From this directory, with a LaTeX distribution installed:

```bash
latexmk -pdf main.tex
```

The manuscript tables and figure are generated from the committed raw results by running `uv run python scripts/reproduce_multimodal.py` from the repository root. LaTeX compilation is **NOT VERIFIED** in the current environment because `latexmk` is unavailable.

## Submission gate

Before submission, the owner must review all references, the validity of strict SPIQA exclusions, the statistical interpretation, authorship, code/data licensing, and fit with the chosen venue. Journal acceptance and Q1 classification are outside this project's control.
