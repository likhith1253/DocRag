# Auditor Report: CodeGraphRAG Architectural Compliance Audit

**Auditor Role:** Independent Reproducibility & Compliance Auditor  
**Audit Scope:** CodeGraphRAG Specification compliance (v2) vs. Active Workspace Codebase  

---

## 1. Executive Summary & Audit Protocol

This audit verifies all technical claims made in the CodeGraphRAG specification ([PROJECT_SPEC.md](file:///d:/Document_RAG/PROJECT_SPEC.md)) against the actual codebase files. 

For every claim, the auditor requires concrete, line-level code evidence and categorizes the capability into three distinct states:
1. **Experimentally Demonstrated (ED):** The capability is fully implemented in the code, was executed during evaluation, and is validated by data in the results directory (`eval/results/`).
2. **Implemented (I):** The code exists in the repository, but has not been directly measured or validated in the baseline results.
3. **Supported by Design (SD):** The interfaces, configuration files, or database schemas support this capability, but there is no functional code that implements it or no data demonstrating its execution.

> [!IMPORTANT]
> **Auditor Rule:** Any capability that exists in the schema or specification but has not been demonstrated experimentally is marked as **UNRESOLVED**. Claims without code-level evidence are classified as **UNSUPPORTED**.

---

## 2. Capability Audit Matrix

| System Component | Specification Claim | Code Evidence | Audit Category | Status |
|---|---|---|---|---|
| **Repository Ingestion** | Zip/Tar upload streaming to prevent memory exhaustion | [loader.py:L6-L128](file:///d:/Document_RAG/ingestion/loader.py#L6-L128) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **Language Detection** | File extension language mappings prior to parsing | [language_detect.py:L3-L53](file:///d:/Document_RAG/ingestion/language_detect.py#L3-L53) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **AST Parsing** | Extraction of classes, functions, imports, and calls | [parser.py:L40-L244](file:///d:/Document_RAG/ingestion/parser.py#L40-L244) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **AST-Aware Chunking** | AST-boundary chunking with sliding overlap & metadata | [chunker.py:L56-L421](file:///d:/Document_RAG/ingestion/chunker.py#L56-L421) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **KG Nodes** | File, Class, Function, Module graph nodes | [knowledge_graph.py:L23-L40](file:///d:/Document_RAG/storage/knowledge_graph.py#L23-L40) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **KG Edges (Basic)** | Calls, Imports, Inherits, Uses graph edges | [knowledge_graph.py:L41-L69](file:///d:/Document_RAG/storage/knowledge_graph.py#L41-L69) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **KG Edges (Advanced)** | Creates, Reads, Writes graph edges | [knowledge_graph.py:L49-L50](file:///d:/Document_RAG/storage/knowledge_graph.py#L49-L50) | **Supported by Design (SD)** | **UNRESOLVED** |
| **Hybrid Routing** | Keyword rule-scoring + routing to specialized agents | [router.py:L12-L85](file:///d:/Document_RAG/agents/router.py#L12-L85) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **Lightweight Router Classifier** | Machine Learning model for query classification routing | [config.yaml:L135](file:///d:/Document_RAG/config.yaml#L135) | **Supported by Design (SD)** | **UNRESOLVED** |
| **Orchestration** | Multi-agent state machine coordination via LangGraph | [orchestrator.py](file:///d:/Document_RAG/agents/orchestrator.py) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **Retrieval Pipeline** | Vector $\rightarrow$ KG $\rightarrow$ Filtering $\rightarrow$ MMR $\rightarrow$ Cross-Rerank | [codegraphrag.py:L64-L101](file:///d:/Document_RAG/eval/benchmark/systems/codegraphrag.py#L64-L101) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **Hardware Measurement** | Peak RSS memory and CPU latency tracking | [evaluator.py:L59-L120](file:///d:/Document_RAG/eval/benchmark/evaluator.py#L59-L120) | **Experimentally Demonstrated (ED)** | **RESOLVED** |
| **Integrity Verification** | Recomputability audit, NaN check, hash validation | [integrity.py:L186-L379](file:///d:/Document_RAG/eval/benchmark/artifacts/integrity.py#L186-L379) | **Experimentally Demonstrated (ED)** | **RESOLVED** |

---

## 3. Detailed Audit Findings & Evidentiary Review

### 3.1. AST-Aware Parsing & Chunking
* **Claim:** The system parses AST structures to identify class, function, and import boundaries, and uses this to construct semantic chunks.
* **Evidence:**
  * [parser.py:L40](file:///d:/Document_RAG/ingestion/parser.py#L40) implements `parse_code(code, language)` which invokes the `tree-sitter` library to parse python, javascript, typescript, and tsx.
  * [chunker.py:L102](file:///d:/Document_RAG/ingestion/chunker.py#L102) implements `chunk_file(file_path, content, language)` which integrates the AST nodes to build code-contextualized chunks.
* **Data Verification:** The `No AST` baseline (`NoASTSystem`) evaluates naive fixed-size chunking. The experimental data confirms that AST-aware chunking increases retrieval accuracy, as shown in `eval/results/baseline_results.json` (`No AST` F1 is 0.75 vs. full `CodeGraphRAG` F1 of 1.0).
* **Audit Verdict:** **RESOLVED** (Experimentally Demonstrated).

### 3.2. Knowledge Graph Schema
* **Claim:** Nodes: Functions, Classes, Files, Modules. Edges: Calls, Imports, Inherits, Uses, Creates, Reads, Writes.
* **Evidence:**
  * [knowledge_graph.py:L10](file:///d:/Document_RAG/storage/knowledge_graph.py#L10) implements `build_from_chunks(chunks)`.
  * Node creation for Files (L25), Classes (L28), Functions (L34), and Modules (L63) is fully implemented.
  * Edge creation maps dependencies to capitalized types `Calls`, `Imports`, `Inherits`, and `Uses` (L45-L69).
* **Vulnerability (Creates, Reads, Writes):**
  * Line 49 lists `Creates`, `Reads`, and `Writes` as valid edge types.
  * However, a search of [parser.py](file:///d:/Document_RAG/ingestion/parser.py) reveals that the `tree-sitter` node traversal **never extracts creates, reads, or writes relationships** (e.g. variable assignments, file writes, database inserts). The parser only extracts class definitions, function definitions, imports, and calls.
  * Consequently, the edges `Creates`, `Reads`, and `Writes` **never exist in the generated knowledge graph** in any experiment. They are supported in the validation schema but are not populated.
* **Audit Verdict:** **UNRESOLVED** (Supported by Design only). These edge types must not be claimed as active capabilities in the evaluation.

### 3.3. Hybrid Routing & Classifier escalation
* **Claim:** A rule-based first pass + lightweight classifier routes queries to agents. If confidence is below a threshold, the system escalates queries to `reasoning_agent`.
* **Evidence:**
  * [router.py:L57](file:///d:/Document_RAG/agents/router.py#L57) implements `route(query)`.
  * Keyword rules are mapped in `RULES` (L19-L43).
  * Confidence is computed as the normalized best-agent signal score (L76-L79).
  * If confidence is below the threshold (configured in `config.yaml` as `router.confidence_threshold`), the query escalates to `reasoning_agent` (L82-L83).
* **Vulnerability (Lightweight Classifier Model):**
  * The configuration [config.yaml:L135](file:///d:/Document_RAG/config.yaml#L135) sets `router_classifier_model: null`.
  * The routing logic in `router.py` does not contain any code to load, run, or query a classifier model (such as a small BERT classifier or a fasttext model). The routing is 100% keyword rule-based with confidence scoring.
  * Therefore, the "lightweight classifier" portion of the hybrid routing is un-coded and un-evaluated.
* **Audit Verdict:** **UNRESOLVED** (Supported by Design only).

### 3.4. Local Hardware Measurement
* **Claim:** Latency and memory are measured under identical, controlled conditions using CPU-only memory limits.
* **Evidence:**
  * [evaluator.py:L59](file:///d:/Document_RAG/eval/benchmark/evaluator.py#L59) implements `_measure_memory_mb()` using Windows `GetProcessMemoryInfo` (WorkingSetSize) and Unix `resource.getrusage` (ru_maxrss).
  * [evaluator.py:L91](file:///d:/Document_RAG/eval/benchmark/evaluator.py#L91) implements `_run_with_measurement(system, question)` which wraps system executions in a time-differential context (`time.perf_counter()`) and memory-differential context.
* **Data Verification:** Metrics are saved in `eval/results/metrics.csv` showing Average Latency is 3.0s and Average Peak Memory is 248MB.
* **Audit Verdict:** **RESOLVED** (Experimentally Demonstrated).

### 3.5. Strict Artifact Integrity Verification
* **Claim:** A reproducibility audit runs automatically after every experiment to verify raw data consistency.
* **Evidence:**
  * [integrity.py:L186](file:///d:/Document_RAG/eval/benchmark/artifacts/integrity.py#L186) implements `verify_experiment_artifacts()`.
  * The evaluator calls this function immediately after writing results [evaluator.py:L13](file:///d:/Document_RAG/eval/benchmark/evaluator.py#L13).
  * If the recomputed metrics (e.g. Recall@5, Token F1) differ from the stored metrics by more than the tolerance ($1e-4$), a hard `IntegrityError` is raised, failing the run.
* **Data Verification:** All runs in `eval/results/` generate an `integrity_report.json` showing `"passed": true`.
* **Audit Verdict:** **RESOLVED** (Experimentally Demonstrated).

---

## 4. Auditor Action Items & Unresolved Features List

The following features reside in the system specifications but **must not be presented as resolved** in academic reviews due to the absence of implementation code or experimental proof:

1. **Creates, Reads, and Writes KG Edges:**
   * *Status:* **Unresolved**.
   * *Correction Required:* The ingestion parser must be extended to parse variable assignments, file operations, and instantiation logic to establish these edges, or the claim must be removed from the paper.
2. **Lightweight Router Classifier Model:**
   * *Status:* **Unresolved**.
   * *Correction Required:* A training and inference script for a classifier model (such as a lightweight logistic regression or DistilBERT model) must be written and integrated into `agents/router.py` to replace the `null` placeholder.
3. **Cross-Repository Validation:**
   * *Status:* **Unresolved**.
   * *Correction Required:* The benchmark must register and evaluate on at least one external, unseen repository (e.g. `repo_id: "requests_lib"`), storing its results in the metrics output to substantiate generalization claims.
