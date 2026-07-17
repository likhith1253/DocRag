# Reviewer Report: CodeGraphRAG Benchmark Methodology

**Reviewer Focus:** ML Systems / Software Engineering (MLSys / ICSE / FSE perspective)  
**Recommendation:** **Strong Reject** (Pending Major Revision of Evaluation Methodology)

---

## 1. Executive Summary & Reviewer Verdict

While the CodeGraphRAG system proposes an interesting integration of AST-aware chunking, NetworkX-based knowledge graphs, and multi-agent routing (via LangGraph), the evaluation methodology presented is **critically flawed and highly vulnerable to rejection** by experienced reviewers. 

The benchmark evaluation suffers from severe developer/self-evaluation bias, toy-scale testing, lack of comparison with standard repository QA benchmarks, and insufficient statistical power. This report details the key methodological threats and critiques that must be addressed to make the benchmark resilient.

---

## 2. Threats to Validity

To establish a scientific evaluation of CodeGraphRAG, we categorize the threats to validity into internal, external, construct, and conclusion validity.

### 2.1. Internal Validity (System & Evaluation Bias)
* **Self-Evaluation & Data Contamination (Severe):** The benchmark dataset (`eval/benchmark_dataset.json`) is evaluated on exactly one repository: `codegraphrag_main` (the CodeGraphRAG codebase itself). Evaluating a system on its own source code creates a severe conflict of interest. The system developers are the ones who wrote the codebase and designed the questions. This results in "overfitting by design," where the prompts, AST parser rules, and agent logic are implicitly tailored to handle the exact structural patterns of this specific codebase.
* **Instrumentation & Closed-Loop Bias:** The dataset generation script ([generate_dataset.py](file:///d:/Document_RAG/eval/generate_dataset.py)) uses `reasoning_agent_model` (`Qwen2.5-3B-Instruct`) to generate questions, answers, and context chunks. Subsequently, the evaluated systems use the same model family to answer these questions. This creates a self-referential closed-loop where the model generates questions that it natively knows how to answer, ignoring the complex, messy, and ambiguous queries real developers ask.
* **Co-adaptation of Code and Benchmarks:** Because the code and the 64 benchmark questions were co-developed within the same timeline, the risk of manual query tuning is high. No validation is performed on completely unseen codebases of similar scale to isolate this factor.

### 2.2. External Validity (Generalizability)
* **Scale Limitations (Toy Codebase):** The single evaluated codebase is extremely small (a few thousand lines of Python code, under 50MB). Experienced ML Systems reviewers will reject claims of "Repository-level QA" when evaluated on codebases of this scale. Real-world repositories span millions of lines, possess complex multi-tier directory structures, and involve legacy configurations.
* **Language Bias:** The evaluation dataset is restricted entirely to Python-based structure. While the system uses `tree-sitter` which is theoretically language-agnostic, the actual chunking, relationship parsing, and query-answering capabilities have not been evaluated on compiled languages (e.g., C/C++, Rust, Java) or multi-language projects where cross-language bindings exist.
* **Hardware & Model Constraint Bias:** Experiments are restricted to CPU-only execution on a 16GB RAM laptop using small models (`Qwen2.5-Coder-3B-Instruct` and `Qwen2.5-3B-Instruct`). It is unknown how these architectures scale to state-of-the-art large language models (e.g., 70B parameters or API-based frontiers like Claude 3.5 Sonnet). System latency and memory usage metrics measured on a commodity CPU laptop do not generalize to production enterprise servers.

### 2.3. Construct Validity (Measurement Accuracy)
* **Lexical Overlap Metric (Token F1) as a Proxy for Correctness:** The benchmark uses Token F1 (lexical overlap) to measure answer accuracy. Token F1 is highly unreliable for code reasoning and synthesis:
  * *False Positives:* An LLM answer that repeats keywords but gets the core logical operator wrong (e.g., returning "The vector store does *not* load E5" instead of "The vector store *does* load E5") will receive a high Token F1 score despite being factually incorrect and breaking the system.
  * *False Negatives:* A semantically perfect explanation that uses synonyms or alternative variable descriptions will receive a low Token F1 score.
* **Coarse-Grained Retrieval Metrics:** Retrieval is evaluated at `Recall@5` based on *file paths* rather than exact *source code chunks* or *line ranges*. In a real repository, locating the correct file is only the first step. If the retriever yields a 1,000-line file but misses the specific 15-line function containing the answer, a file-level Recall@5 of 1.0 is recorded, which is highly misleading.
* **Synthetic Queries vs. Real Developer Queries:** The benchmark categories (e.g., "Configuration Reasoning", "Bug Localization") are pre-defined categories populated by LLM templates. They do not represent the distribution of actual developer search behaviors, issue tracking queries, or stack trace investigations.

### 2.4. Conclusion Validity (Statistical Power & Rigor)
* **Insufficient Sample Size ($N = 64$):** Evaluating on only 64 questions severely limits the statistical power of the results. 
* **Statistical Power Analysis:** 
  * Assume a two-tailed paired t-test or Wilcoxon signed-rank test comparing CodeGraphRAG to a baseline (e.g., Simple RAG).
  * With $N=64$, to achieve a standard statistical power of $\beta = 0.80$ at a significance level of $\alpha = 0.05$, the minimum detectable effect size (Cohen's $d$) must be $\approx 0.35$ (a medium effect size).
  * If the performance delta between a baseline ablation (e.g., CodeGraphRAG vs. No KG) is small (e.g., F1 difference of 0.05, representing an effect size $d \approx 0.15$), a sample size of $N=64$ is highly likely to result in a Type II error (failing to reject the null hypothesis of no difference).
  * Given multiple comparisons (5 baselines + 3 ablations), applying the Bonferroni correction dramatically increases the family-wise error rate protection, adjusting the alpha level to $\alpha_{adj} = 0.05 / 8 = 0.00625$. At this adjusted alpha, the required sample size to detect a medium effect size ($d = 0.5$) with 80% power jumps to $N \approx 120$. With $N=64$, small but practically meaningful architectural improvements will fail to register as statistically significant.
* **Hardware Variance and Measurement Noise:** Running CPU-based inference locally on a laptop introduces significant thermal throttling, OS background paging, and memory fragmentation. Latency and memory measurements without isolated containers or bare-metal execution are highly noisy, making mean values statistically unreliable unless run for hundreds of iterations per query.

---

## 3. Comparison with Existing Repository QA Benchmarks

Experienced reviewers will ask: *"Why did the authors create a custom 64-question dataset on their own codebase instead of evaluating on established, public repository-level benchmarks?"* 

The table below contrasts the CodeGraphRAG benchmark with SOTA benchmarks:

| Benchmark | Repo Count | Scale (Instances) | Task Formats | Complexity | CodeGraphRAG Comparison |
|---|---|---|---|---|---|
| **SWE-bench** (Jimenez et al., 2023) | 12 repos (active) | 2,294 | Real GitHub issues, PR patch generation | **Extreme:** Requires modifying code across multiple files, running test suites. | SWE-bench tests actual software engineering agent capabilities. CodeGraphRAG's custom benchmark only tests short text Q&A. |
| **RepoBench** (Liu et al., 2023) | Hundreds (Python, Java) | Thousands | Repo-level code completion, Retrieval | **High:** Involves cross-file context retrieval and multi-hop token completion. | RepoBench provides standardized splits for cross-file completion. CodeGraphRAG is single-repo and single-language. |
| **CrossCodeEval** (Ding et al., 2023) | Diverse repositories | Thousands | Cross-file code completion, dependency reasoning | **Medium-High:** Evaluates the necessity of cross-file context to fill in missing logic. | CrossCodeEval isolates whether the model can retrieve dependencies. CodeGraphRAG does not evaluate completion. |
| **CodeSearchNet** (Husain et al., 2019) | Millions | 2M+ code-docstring pairs | Semantic search, retrieval | **Low-Medium:** Function-level search. | Evaluates retrieval only. CodeGraphRAG evaluates reasoning + retrieval, but at a microscopic scale compared to CodeSearchNet. |
| **CodeGraphRAG Custom** | **1 (Internal)** | **64** | Text Q&A, Retrieval | **Low:** Short static questions, self-evaluated on a small internal codebase. | Lacks statistical power, diversity, and cross-repo validation. |

---

## 4. Annotation Methodology Critique

The process described in `eval/generate_dataset.py` relies on a semi-automated pipeline: LLM generation $\rightarrow$ Automated Filter $\rightarrow$ Single Human Verifier ("Likhith"). This is highly vulnerable to reviewer rejection:

1. **No Inter-Annotator Agreement (IAA) Metrics:** Ground truth verification is completed by a single individual (Likhith). Without multiple independent annotators verifying the same Q&A pairs, we cannot compute **Cohen's Kappa** or **Fleiss' Kappa**. The ground truth is subject to individual interpretation, bias, and annotation fatigue.
2. **Ambiguity and Completeness of Ground Truth Answers:** Ground truth answers in the JSON (e.g., `verified_answer`) are short text strings. Codebase-level questions often have multiple valid answers depending on context (e.g., citing a configuration setting or a code chunk). A single verifier cannot anticipate all valid reasoning paths, penalizing alternative correct answers.
3. **Retrieval Ground Truth Completeness:** The `ground_truth_retrieval_chunks` field contains a list of chunk SHA-256 hashes. Because chunking is AST-semantic based, a slight change in the chunker's hyperparameters (e.g., `max_chunk_tokens`) changes the hashes. This invalidates the ground truth hashes, making the dataset extremely fragile and tied to a specific chunker version.

---

## 5. Reproducibility Concerns

ML Systems venues place heavy emphasis on artifact reproducibility. The CodeGraphRAG setup has several reproducibility bottlenecks:

1. **Local Model Non-Determinism:** If Ollama is used, system outputs are subject to server parameter variations, CPU thread scheduling differences, and floating-point non-determinism.
2. **Missing System Seeds in Generation:** Although `manifest.json` tracks random seeds, local Ollama endpoints do not enforce strict seed control by default. Small variations in token generation change the resulting F1 scores.
3. **Dependency Drift:** The packages listed in [manifest.py](file:///d:/Document_RAG/eval/benchmark/artifacts/manifest.py#L98) (e.g., `transformers`, `networkx`, `qdrant_client`) are not locked to strict versions. The absence of a `requirements.txt` with locked versions (e.g. `numpy==1.24.3`) means package updates can break the AST parser or NetworkX graph indexing, causing reproducibility failure.

---

## 6. Actionable Recommendations for Methodology Resiliency

To prevent rejection, the following improvements are recommended (in order of priority):

1. **Acknowledge the Scale and Domain Limitations:** Explicitly position the benchmark as a **"Self-Contained Integration smoke-test & regression suite"** rather than a general-purpose Repository QA benchmark. Do not claim generalization to large-scale multi-million line codebases.
2. **Add a Secondary Unseen Evaluation Repository:** To counter the self-evaluation bias, include at least one external, public, small-scale repository (e.g., a simple utility library like `requests` or `markdown`) in `eval/benchmark_dataset.json` with generated Q&A pairs. This demonstrates that the retrieval and routing pipeline works on code that the developers did not write.
3. **Transition from Token F1 to LLM-as-a-Judge for Answer Semantics:** Supplement Token F1 with a standardized, model-graded semantic accuracy evaluation (e.g., using GPT-4 or Qwen2.5-72B to judge whether the system's response matches the ground truth facts, regardless of lexical overlap).
4. **Expand Sample Size:** Target $N \ge 120$ questions (ideally distributed across the internal repo and an external repo) to satisfy statistical power requirements under Bonferroni adjustments.
5. **Lock Dependencies:** Provide a strict `requirements.txt` pinning all package versions to ensure AST chunking and Graph Search are reproducible across systems.
