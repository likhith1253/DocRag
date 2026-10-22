# System Architecture V2 (CodeGraphRAG Production)

## 1. High-Level Concept
The fundamental shift from research to production transforms the pipeline from a single-repository hardcoded flow to a dynamic, multi-tenant capable architecture managed by a `Repository Registry`.

### Current Research Architecture
```
Question → Retriever → LLM
```

### Proposed Production Architecture (V2)
```
Repositories → Repository Registry → Retriever → Knowledge Graph → Planner → LLM
```

## 2. Core Components

### 2.1. Repository Registry
The heart of the new system. It manages the lifecycle and state of multiple repositories concurrently.
- **State tracking**: Tracks `repo_id`, `branch`, `commit`, `language`, `status` (indexing, ready, offline).
- **Resource isolation**: Maintains separate graphs, vector collections, and metadata for each repository to prevent cross-contamination.
- **Hot Loading**: Handles ZIP/Tar uploads or git-pulls, indexing the new repository in the background without requiring a server restart.

### 2.2. Incremental Indexing Engine
Instead of rebuilding the entire AST and Knowledge Graph on every change, this engine:
- Computes git diffs to identify modified, added, and deleted files.
- Selectively updates vector embeddings and graph nodes/edges.

### 2.3. The Retriever Layer
The Retriever no longer blindly searches a global Qdrant index.
- First, the query context selects the active repository.
- Retrieval operations are scoped strictly to the selected `repo_id`'s vector collection.
- Lookups against Qdrant will use cached ID matching to avoid full-database scrolls.

### 2.4. Knowledge Graph (Singleton)
- The Knowledge Graph becomes a long-lived, in-memory singleton.
- Loading from JSON happens once (per repository or globally segmented).
- Neighbor lookups are optimized to O(1) or O(log n) via proper hash maps rather than full edge scans.

### 2.5. Planner / Router
The system introduces a Planner (Agentic Orchestrator) step before the final LLM synthesis:
- **Routing**: Determines if a query requires code search, data extraction, or deep reasoning.
- **Planner**: Coordinates multi-step queries (e.g., retrieving a file, then traversing the graph to find its dependencies).

## 3. Data Flow
1. **Ingestion**: `POST /repository` → Registry → Incremental Indexing → Qdrant/KG/Metadata → Ready
2. **Query**: `POST /query` → Registry (Auth/Select) → Retriever (Vectors) → Graph Traversal → Planner (LangGraph) → Synthesis (LLM) → Response

## 4. Hardware and Constraints
- Retains local inference constraint (Ollama/Transformers).
- Heavy models (`SentenceTransformer`, `CrossEncoder`, `LLM`) are loaded strictly ONCE at startup and shared across all repository contexts.
