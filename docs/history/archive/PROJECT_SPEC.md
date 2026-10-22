# PROJECT_SPEC.md (v2 — supersedes v1)
## CodeGraphRAG: Hybrid Graph-Augmented Multi-Agent Repository QA

> Single source of truth. If conversation conflicts with this file, THIS FILE WINS.
> `project_doc.tex` is background motivation only — not a build instruction.
> Do not redesign, rename, or add scope beyond what's written here without approval.

---

## 0. Research Question (fixed)

Can hybrid retrieval combining AST-aware chunking, knowledge graph augmentation,
and specialized multi-agent reasoning improve repository question answering over
conventional RAG, while maintaining practical latency on commodity hardware?

---

## 1. Non-Negotiable Constraints

- **Hardware:** Dev on CPU-only laptop (i7 13th gen, 16GB RAM, no GPU). Code must
  never hardcode `cuda` — always `device = "auto"` resolved by the backend.
- **Cost:** Zero paid APIs anywhere in the pipeline. Local inference (Transformers/
  Ollama/llama.cpp) or free-tier Kaggle GPU only.
- **No training/fine-tuning.** All models used pretrained, off-the-shelf.
- **No hardcoded models anywhere in agent code.** Everything model-related loads
  from `config.yaml`.

---

## 2. Tech Stack (updated)

| Component | Tool | Notes |
|---|---|---|
| Orchestration | LangGraph | Router + agents + synthesis node |
| **LLM access** | **Abstraction layer** (`llm/backend.py`) | Code only ever calls `generate(prompt)`. Swappable backend: Transformers / Ollama / vLLM / llama.cpp |
| Code agent model | `Qwen2.5-Coder-3B-Instruct` (config-driven) | Lighter than 7B, faster on CPU |
| Reasoning agent model | `Qwen2.5-3B-Instruct` (config-driven) | Replaces DeepSeek-R1-8B — too heavy for CPU/Kaggle |
| Embeddings | sentence-transformers, config-driven | Default `all-MiniLM-L6-v2`; ablation also tests BGE, E5 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Free, fast; reranks top-30 → top-5 |
| Vector DB | Qdrant (local/embedded) | Disk-based |
| Knowledge graph | NetworkX, richer schema (below) | Stored as JSON |
| Router | Hybrid: rules + lightweight classifier + confidence score | Low confidence → escalate to reasoning agent |
| Code parsing | tree-sitter | Language-agnostic |
| API | FastAPI | |
| UI | Streamlit | Functional only — no polish |
| Eval | Modular scripts, no external frameworks | |

---

## 3. Repo Structure (create exactly this)

```
project-root/
├── PROJECT_SPEC.md
├── mistakes.txt
├── project_doc.tex
├── config.yaml
├── run_all.py                    <- single command, runs full pipeline end to end
├── llm/
│   ├── backend.py                <- abstract interface: generate(prompt)
│   ├── transformers_backend.py
│   └── ollama_backend.py
├── ingestion/
│   ├── loader.py                 <- streamed zip/tar upload
│   ├── language_detect.py        <- detect file language before parsing
│   ├── parser.py                 <- tree-sitter AST parsing
│   └── chunker.py                <- AST + semantic boundary + sliding overlap + dependency-aware linking
├── storage/
│   ├── vector_store.py           <- Qdrant wrapper
│   ├── knowledge_graph.py        <- NetworkX, richer schema (Section 6)
│   └── metadata_store.py         <- per-chunk metadata (Section 7)
├── retrieval/
│   ├── vector_search.py
│   ├── graph_search.py
│   ├── metadata_filter.py
│   ├── mmr_rerank.py
│   └── cross_encoder_rerank.py
├── agents/
│   ├── router.py                 <- hybrid rule+classifier+confidence
│   ├── code_agent.py
│   ├── data_agent.py
│   ├── reasoning_agent.py
│   └── orchestrator.py
├── api/
│   └── main.py
├── ui/
│   └── app.py
├── eval/
│   ├── test_dataset.json
│   ├── generate_dataset.py       <- LLM-assisted generation + human verify step
│   ├── retrieval.py              <- Recall@5, precision, etc.
│   ├── accuracy.py
│   ├── latency.py
│   ├── memory.py
│   ├── evaluate.py               <- orchestrates the above
│   └── results/                  <- timestamped JSON per run
├── baselines/
│   ├── simple_rag.py             <- Baseline 1
│   ├── vector_only.py            <- Baseline 2
│   ├── single_agent.py           <- Baseline 3
│   ├── no_kg.py                  <- Baseline 4
│   └── no_ast.py                 <- Baseline 5
├── logs/
│   └── query_logs.jsonl          <- every query: question, chunks, agent, latency, memory, answer
└── tests/
    └── (per-module unit tests, added as each phase completes)
```

---

## 4. LLM Abstraction Layer (Change 1 + 4)

`llm/backend.py` defines one function signature used everywhere:

```python
def generate(prompt: str, model_key: str) -> str: ...
```

`model_key` maps to a config entry (e.g. `code_agent_model`, `reasoning_agent_model`).
Agents NEVER import Ollama/Transformers directly — only `llm.backend.generate()`.
Backend implementation (Ollama vs Transformers vs llama.cpp) is chosen once in
`config.yaml` and swapped without touching agent code.

---

## 5. config.yaml (all tunables live here — nothing hardcoded elsewhere)

```yaml
device: auto

llm_backend: ollama   # ollama | transformers | llama_cpp

code_agent_model: qwen2.5-coder:3b
reasoning_agent_model: qwen2.5:3b-instruct
router_classifier_model: null   # null = rules-only until Phase 3b

embedding_model: all-MiniLM-L6-v2
reranker_model: cross-encoder/ms-marco-MiniLM-L-6-v2

chunking:
  strategy: ast_semantic_overlap
  max_chunk_tokens: 512
  overlap_tokens: 64

retrieval:
  vector_top_k: 30
  rerank_top_k: 5
  use_mmr: true
  use_graph: true
  use_metadata_filter: true

router:
  confidence_threshold: 0.6

qdrant_path: ./qdrant_storage
ports:
  api: 8000
  ui: 8501
```

---

## 6. Knowledge Graph Schema (Change 8 — richer)

**Nodes:** Functions, Classes, Files, Modules
**Edges:** Calls, Imports, Inherits, Uses, Creates, Reads, Writes

---

## 7. Chunk Metadata (Change 18)

Every chunk stores: `repository, branch, language, file, class, function, lines, hash, timestamp`.

---

## 8. Retrieval Pipeline (Changes 7 + 9)

```
Query → Embedding Search (top 30) → Knowledge Graph expansion
      → Metadata Filtering → MMR rerank → Cross-Encoder rerank (top 5)
      → Agents
```

---

## 9. Router (Change 5)

Rule-based first pass + lightweight classifier + confidence score. If confidence
< `router.confidence_threshold` in config, escalate to reasoning agent regardless
of rule-match. This behavior itself is a metric to report (how often escalation
happens, and whether it improves accuracy).

---

## 10. Evaluation Metrics (Change 10 — full set)

Accuracy, Precision, Recall, F1, Retrieval Recall@5, Latency, Memory, CPU Usage,
Agent Distribution. Each in its own module (`eval/retrieval.py`, `accuracy.py`,
`latency.py`, `memory.py`), orchestrated by `eval/evaluate.py`.

---

## 11. Dataset (Changes 11 + 12)

**Target:** 500+ Q&A pairs, balanced across: Code Search, Data Extraction,
Reasoning, Architecture, Debugging, Dependency, Security, Performance.

**Generation:** `eval/generate_dataset.py` uses an LLM to draft candidate Q&A
pairs from the repo, but every pair must be human-verified (by Likhith) before
being added to `test_dataset.json`. Do not skip the human verification step —
this is a correctness-critical manual gate, not something to automate away.

---

## 12. Baselines (Change 14 — essential, not optional)

Must compare against all 5:
1. Simple RAG (naive chunking + vector search + single generic LLM call)
2. Vector Search only (no graph, no rerank)
3. Single Agent (no routing, one model does everything)
4. No Knowledge Graph (full pipeline minus graph)
5. No AST (fixed-size chunking instead of AST-aware)

---

## 13. Ablations (Change 13, extends Section 12)

Additionally ablate embedding model choice: MiniLM vs BGE vs E5 — compare
retrieval quality only, not full system re-run, to conserve compute/credits.

---

## 14. Logging (Change 16)

Every query, in production or eval, appends one JSON line to
`logs/query_logs.jsonl`: `{question, retrieved_chunks, agent, latency, memory, answer}`.

---

## 15. UI Scope (Change 15 — functional only)

Upload repo, ask question, show: agent selected, retrieved files, graph
visualization (simple), latency, sources. No visual polish beyond this.

---

## 16. Reproducibility (Change 20)

`run_all.py` at repo root runs the entire pipeline (ingest test repo → build
index → run eval → run baselines → run ablations → dump results) in one
command. This is a Phase 8 deliverable, not built incrementally per phase.

---

## 17. Build Phases (strict order, updated)

### Phase 0 — Environment + Abstraction Layer Setup
Verify local inference stack works (Ollama or Transformers — pick one per
`config.yaml`, don't set up both). Pull `qwen2.5-coder:3b` and `qwen2.5:3b-instruct`.
Build `llm/backend.py` with at least one working backend implementation.
Create `config.yaml`, full folder structure from Section 3.
**DoD:** `generate("hello", model_key="code_agent_model")` returns a real
response through the abstraction layer, not a direct Ollama call.

### Phase 1 — Ingestion Pipeline
`loader.py`, `language_detect.py`, `parser.py`, `chunker.py` (AST + semantic
boundary + sliding overlap + dependency-aware linking).
**DoD:** Test repo (~50MB) produces chunks with full metadata (Section 7),
no crash on mixed file types.

### Phase 2 — Storage + Retrieval
`vector_store.py`, `knowledge_graph.py` (richer schema), `metadata_store.py`,
then `retrieval/` folder: vector search, graph search, metadata filter, MMR,
cross-encoder rerank.
**DoD:** Query → top-5 reranked chunks pipeline runs end to end and returns
sane results on the test repo.

### Phase 3 — Agents + Router
`router.py` (hybrid: rules + confidence score — classifier model optional,
can stay rules-only if credits are tight, document choice in config),
`code_agent.py`, `data_agent.py`, `reasoning_agent.py` — all calling
`llm.backend.generate()` only.
**DoD:** 10 hand-written test queries route correctly; low-confidence cases
visibly escalate to reasoning agent.

### Phase 4 — Orchestration
`orchestrator.py` wiring everything via LangGraph, with error handling
(backend timeout, empty retrieval, malformed query). Logging wired in
(`logs/query_logs.jsonl`).
**DoD:** `orchestrator.answer("query")` works end to end on 5 manual
queries, each producing a log entry.

### Phase 5 — API + UI
FastAPI (`/upload`, `/query`, `/health`) + Streamlit UI per Section 15.
**DoD:** Full browser flow works: upload → ask → see agent, sources,
latency.

### Phase 6 — Dataset
`generate_dataset.py` drafts candidates; Likhith manually verifies ≥500
pairs across all 8 categories (Section 11).
**DoD:** `test_dataset.json` complete, validated schema, 30-entry random
sample re-checked.

### Phase 7 — Evaluation + Baselines
Full metric suite (Section 10) run against the system AND all 5 baselines
(Section 12).
**DoD:** Results JSON for system + all baselines saved in `eval/results/`,
summary comparison table produced.

### Phase 8 — Ablations + Reproducibility + Analysis
Run ablations (Section 13, plus KG/router/AST removal). Build `run_all.py`
to reproduce everything in one command.
**DoD:** Ablation comparison table exists. `python run_all.py` runs clean
end to end with no manual steps.

---

## 18. Explicit Non-Goals (do not build unless asked)

No fine-tuning, no cloud deployment/Docker/K8s, no multi-user/auth, no PDF
OCR/vision models, no reinforcement learning, no distributed systems, no
public-benchmark comparison (revisit only if time/credits remain after
Phase 8).

---

## 19. mistakes.txt Protocol (unchanged from v1)

Append-only. Format:
```
[PHASE X] [DATE/TIME]
ISSUE:
CAUSE:
FIX:
AVOID-NEXT-TIME:
---
```
Read the entire file before starting any new task or phase.

---

## 20. Credit-Conservation Rules (unchanged, still applies)

- Don't regenerate files that already meet their phase's DoD.
- Don't explore multiple alternative implementations per component — this
  spec has already decided each one.
- Ask a short clarifying question rather than burning attempts guessing.
- Model-swap (Section 4/5) must go through config.yaml only, and must be
  logged in mistakes.txt with reason.
