# Draft status: research evaluation pending owner review

This is a draft scaffold. It is not ready for arXiv submission until the frozen test run and generated table/failure analysis have been reviewed and all factual claims have been checked against their raw source files.

**The project owner must personally review every claim and every bibliographic reference before submission. Unchecked AI-generated content or references can lead to serious consequences, including an arXiv submission ban.** Confirm author identities, affiliations, contribution statements, data/model terms, and all generated result values before submission.

The paper reports retrieval only. It must not be described as evidence for answer-generation accuracy, semantic claim verification, citation faithfulness, or calibrated abstention.

Build from this directory after a test run has generated `paper/generated/main_results.tex`:

```bash
latexmk -pdf main.tex
```

The draft uses the standard `article` class and `plainnat` bibliography style to avoid a conference-template dependency. LaTeX compilation has not yet been verified.
