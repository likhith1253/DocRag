# Deployment Architecture

## 1. Constraints and Environment
- **Hardware**: CPU-only deployment (no GPU dependency hardcoded).
- **External Dependencies**: Local models only (Ollama, HuggingFace Transformers). No cloud APIs.
- **Service Layout**: Monolithic FastAPI backend acting as the API, with an integrated LangGraph orchestrator.

## 2. Process Layout

### API Process (FastAPI)
- Handles HTTP requests.
- Contains the Repository Registry and holds the Singletons (Models, Graph) in memory.
- Exposes metrics on `/metrics` (Prometheus).

### Storage Layer
- **Vectors**: Embedded Qdrant instance running natively within the process (or locally alongside it), writing to `./qdrant_storage`.
- **Graphs**: JSON files stored in `./graphs/`.
- **Metadata**: SQLite or JSON store in `./metadata/`.

### Background Workers (Future-proofing)
- While initially the indexing will happen asynchronously within the FastAPI event loop, the architecture should allow shifting to a Celery/Redis queue if CPU contention between queries and indexing becomes too high.

## 3. Observability
- **Prometheus Metrics**: `query_latency_seconds`, `memory_usage_bytes`, `cache_hit_ratio`, `agent_escalation_count`.
- **Logging**: JSON structured logging writing to stdout, easily consumable by Fluentd/Logstash.

## 4. Configuration Management
- Environment variables override `config.yaml`.
- Example mappings:
  - `LLM_BACKEND` -> `llm_backend`
  - `ROUTER_CONFIDENCE_THRESHOLD` -> `router.confidence_threshold`
