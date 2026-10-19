# Multi-Repository Architecture

## 1. The Repository Registry Model
In the research prototype, the system assumed a single global dataset. In the production deployment, the system must act as a multi-tenant service where data isolation is strictly enforced.

The `RepositoryRegistry` class is introduced as the central authority.

```python
class RepositoryRegistry:
    def register(self, repo_url: str) -> str: ...
    def get_context(self, repo_id: str) -> RepoContext: ...
    def delete(self, repo_id: str) -> None: ...
```

## 2. Resource Isolation Strategy

### 2.1. Vector Store (Qdrant)
- **Isolation by Collection**: Each repository will be mapped to a unique Qdrant Collection named `collection_{repo_id}`.
- This ensures that a query meant for "Repo A" cannot accidentally retrieve chunks from "Repo B". It also allows O(1) repository deletion by simply dropping the collection.

### 2.2. Knowledge Graph
- **Segmented Graphs**: Instead of one massive `knowledge_graph.json`, the storage will save `{repo_id}_graph.json`.
- When a query is routed to `repo_id`, the Planner references `RepositoryRegistry.get_context(repo_id).graph`.

### 2.3. Metadata Store
- **Scoped Metadata**: Chunk metadata will be namespaced by `repo_id`. Lookups will only scan the sub-dictionary corresponding to the requested repository.

## 3. Hot Loading
To support zero-downtime additions:
1. `POST /repository` uploads a ZIP or provides a Git URL.
2. A background task spins up, running the Incremental Indexing pipeline.
3. Once indexing finishes, the Registry updates the state of `repo_id` from `INDEXING` to `READY`.
4. The API endpoints will now accept queries for `repo_id`. No server restart is required.
