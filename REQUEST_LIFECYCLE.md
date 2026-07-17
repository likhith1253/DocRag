# Request Lifecycle

## 1. Initialization (Startup)
When the FastAPI application starts:
1. **Load Configuration**: Parses `config.yaml` or env vars once.
2. **Initialize Singletons**: 
   - `SentenceTransformer` and `CrossEncoder` are loaded into memory.
   - Database connections (Qdrant client) are established once.
   - LLM Backend is initialized.
3. **Repository Registry Recovery**:
   - The registry scans its storage directory to discover already-indexed repositories.
   - It re-loads the Knowledge Graph for these repositories into memory.
   - Marks their status as `ready`.

## 2. Query Lifecycle (`POST /query`)
1. **Validation & Context Loading**:
   - The request contains `question` and `repo_id`.
   - The API validates that `repo_id` exists and is `ready`.
   - Fetches the `RepoContext` which contains pointers to the specific Qdrant collection and the in-memory graph.
2. **Routing / Planning**:
   - The query is analyzed to determine if it requires deep graph traversal or just simple vector retrieval.
3. **Retrieval Pipeline**:
   - **Vector Search**: Embeds the query (using the singleton model) and queries Qdrant specifically within `repo_id`'s namespace.
   - **Graph Traversal**: Uses the in-memory singleton graph to find adjacent nodes (callers, callees, definitions) in O(1) or O(log n) time.
   - **Reranking**: Passes the union of chunks to the singleton CrossEncoder.
4. **LLM Synthesis**:
   - The Planner constructs the final prompt and sends it to the LLM backend.
5. **Logging & Observability**:
   - The total latency, memory usage, selected agent, and token counts are emitted to Prometheus metrics and JSON logs.
   - The response is returned to the user.

## 3. Graceful Shutdown
1. Ongoing queries are allowed a grace period to complete.
2. The Repository Registry flushes any pending metadata changes to disk.
3. Qdrant client connections are safely closed.
4. Memory is released.
