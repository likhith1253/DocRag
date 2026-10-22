# Engineering Change Log

## [2026-07-22] Session 1 Fixes & Enhancements

### Change 1: Raised PDF Heading Threshold and Section Heading Retention
- **Timestamp**: 2026-07-22T16:30:00Z
- **Reason**: Prevent false positive section boundaries and maintain header text in chunks.
- **Root Cause**: Heading regex/threshold (1.10x font scale) split single paragraphs into multiple sections and discarded title text.
- **Files Modified**: `ingestion/pdf_parser.py`
- **Expected Effect**: Cohesive sections with intact headings.
- **Regression Result**: Zero regressions across existing unit test suite.

### Change 2: Content-Aware Repository Router Implementation
- **Timestamp**: 2026-07-22T17:15:00Z
- **Reason**: Route queries accurately based on indexed paper titles and abstract summaries.
- **Root Cause**: Router matched solely on string collection names, causing routing misfires on paper-level queries.
- **Files Modified**: `retrieval/repository_router.py`, `ingestion/worker.py`
- **Expected Effect**: 100% routing accuracy for multi-repo paper queries.
- **Regression Result**: Verified against 14 benchmark questions.

### Change 3: Cross-Encoder Type Preference Re-balancing
- **Timestamp**: 2026-07-22T18:00:00Z
- **Reason**: Prevent metadata preferences from masking semantic relevance.
- **Root Cause**: Reranker type-preference weight was set to 30%.
- **Files Modified**: `retrieval/cross_encoder_rerank.py`
- **Expected Effect**: Top-k reranking accurately preserves highest semantic similarity chunks.
- **Regression Result**: Passed Q1 and Q2 verification.
