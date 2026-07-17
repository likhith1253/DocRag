# Known Limitations

DocumentRAG v1.0 has been extensively validated for end-to-end production readiness. However, to ensure full transparency and to set accurate expectations for real-world academic research retrieval, we acknowledge the following known limitations in the current architecture:

### 1. Table Extraction and Formatting
PyMuPDF currently extracts text from tables by flattening them into sequential lines (typically reading left-to-right, row-by-row). While the raw text is captured, the structural relationships and column boundaries of complex tables are lost. Queries that require strict tabular comprehension may return suboptimal context blocks.

### 2. Mathematical Equations
Mathematical formulas and equations—especially those rendered as LaTeX blocks, embedded fonts, or vector graphics—may not be extracted accurately. They often parse as garbled unicode or missing characters, reducing the effectiveness of querying highly mathematical papers.

### 3. Horizontal Scalability (Qdrant Local)
The current vector storage backend utilizes Qdrant running in local file-mode (`qdrant_storage/`). Because this implementation relies on strict file locks, DocumentRAG cannot be horizontally scaled (e.g., launching multiple API worker processes via `uvicorn --workers N`). The system is strictly intended for single-node deployments. Scaling requires migrating to a dedicated Qdrant Docker container.

### 4. Mid-Batch Resume Indexing
While the ingestion pipeline implements a snapshotting mechanism to support incremental indexing across subsequent runs, resuming an ingestion job that is forcefully interrupted mid-batch was not fully validated before the release candidate freeze.
