# Draft status: results complete; owner review required

The frozen test run and generated tables/failure analysis are complete. This draft is not ready for arXiv submission until the owner reviews all claims and references against their raw source files and fills in verified author details.

**The project owner must personally review every claim and every bibliographic reference before submission. Unchecked AI-generated content or references can lead to serious consequences, including an arXiv submission ban.** Confirm author identities, affiliations, contribution statements, data/model terms, and all generated result values before submission.

The paper reports a negative primary result on the held-out table/figure subset and a positive overall structure-versus-MMR contrast, with plain reranking stronger than either. It reports retrieval only and must not be described as evidence for answer-generation accuracy, semantic claim verification, citation faithfulness, or calibrated abstention.

Build from this directory after the guarded test run has generated `paper/generated/main_results.tex`:

```bash
latexmk -pdf main.tex
```

The draft uses the standard `article` class and `plainnat` bibliography style to avoid a conference-template dependency. LaTeX compilation has not yet been verified.
