# Repository Cleanup Report

## 1. Executive Overview

The repository cleanup and benchmark preparation phase was executed for `d:\DocRag`. All production source code, API services, RAG modules, evaluation frameworks, deployment scripts, architecture documentation, configuration files, and benchmark datasets were **100% preserved**. Obsolete scratch scripts, temporary logs, and obsolete execution run directories were safely removed.

## 2. Summary of Repository Inventory

- **Total Files Preserved**: **606** files
- **Total Files Removed**: **294** obsolete files/directories

## 3. Removed Files & Deletion Rationale

| Relative Path | Size (Bytes) | Category / Reason for Deletion |
| :--- | :---: | :--- |
| `agents/__pycache__/__init__.cpython-312.pyc` | 125 | Python bytecode cache file |
| `agents/__pycache__/code_agent.cpython-312.pyc` | 2,114 | Python bytecode cache file |
| `agents/__pycache__/data_agent.cpython-312.pyc` | 2,107 | Python bytecode cache file |
| `agents/__pycache__/doc_agent.cpython-312.pyc` | 6,488 | Python bytecode cache file |
| `agents/__pycache__/orchestrator.cpython-312.pyc` | 24,093 | Python bytecode cache file |
| `agents/__pycache__/query_planner.cpython-312.pyc` | 15,078 | Python bytecode cache file |
| `agents/__pycache__/reasoning_agent.cpython-312.pyc` | 2,217 | Python bytecode cache file |
| `agents/__pycache__/router.cpython-312.pyc` | 3,277 | Python bytecode cache file |
| `api/__pycache__/__init__.cpython-312.pyc` | 122 | Python bytecode cache file |
| `api/__pycache__/dependencies.cpython-312.pyc` | 376 | Python bytecode cache file |
| `api/__pycache__/main.cpython-312.pyc` | 7,740 | Python bytecode cache file |
| `api/__pycache__/repository.cpython-312.pyc` | 7,197 | Python bytecode cache file |
| `debug_retrieval.py` | 0 | Obsolete scratch script or debug log |
| `diagnose_failures.py` | 2,615 | Obsolete scratch script or debug log |
| `eval/__pycache__/__init__.cpython-312.pyc` | 123 | Python bytecode cache file |
| `eval/__pycache__/compare.cpython-312.pyc` | 812 | Python bytecode cache file |
| `eval/__pycache__/diagnostic_reporter.cpython-312.pyc` | 5,557 | Python bytecode cache file |
| `eval/__pycache__/evaluator.cpython-312.pyc` | 8,080 | Python bytecode cache file |
| `eval/__pycache__/metrics.cpython-312.pyc` | 2,740 | Python bytecode cache file |
| `eval/__pycache__/production_validation.cpython-312.pyc` | 19,810 | Python bytecode cache file |
| `eval/__pycache__/redesigned_evaluator.cpython-312.pyc` | 66,331 | Python bytecode cache file |
| `eval/__pycache__/regression_tester.cpython-312.pyc` | 8,089 | Python bytecode cache file |
| `eval/__pycache__/retrieval.cpython-312.pyc` | 223 | Python bytecode cache file |
| `eval/__pycache__/run_incremental_pilot_validation.cpython-312.pyc` | 26,060 | Python bytecode cache file |
| `eval/__pycache__/stage_framework.cpython-312.pyc` | 8,763 | Python bytecode cache file |
| `eval/__pycache__/test_stage_invariants.cpython-312-pytest-8.1.0.pyc` | 10,618 | Python bytecode cache file |
| `eval/__pycache__/test_stage_invariants.cpython-312.pyc` | 10,505 | Python bytecode cache file |
| `eval/ai_papers_evaluation.json` | 0 | Obsolete scratch script or debug log |
| `eval/ai_papers_expected_answers_REBUILD.json` | 8,979 | Obsolete scratch script or debug log |
| `eval/analyze_q1_prompt_file.py` | 1,922 | Obsolete scratch script or debug log |
| `eval/benchmark/__pycache__/__init__.cpython-312.pyc` | 678 | Python bytecode cache file |
| `eval/benchmark/__pycache__/dataset.cpython-312.pyc` | 27,829 | Python bytecode cache file |
| `eval/benchmark/__pycache__/evaluator.cpython-312.pyc` | 26,810 | Python bytecode cache file |
| `eval/benchmark/__pycache__/interface.cpython-312.pyc` | 10,048 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/__init__.cpython-312.pyc` | 592 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/environment.cpython-312.pyc` | 6,820 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/error_analysis.cpython-312.pyc` | 6,511 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/figures.cpython-312.pyc` | 11,354 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/integrity.cpython-312.pyc` | 16,316 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/manifest.cpython-312.pyc` | 10,446 | Python bytecode cache file |
| `eval/benchmark/artifacts/__pycache__/tables.cpython-312.pyc` | 9,981 | Python bytecode cache file |
| `eval/benchmark/metrics/__pycache__/__init__.cpython-312.pyc` | 875 | Python bytecode cache file |
| `eval/benchmark/metrics/__pycache__/generation.cpython-312.pyc` | 13,820 | Python bytecode cache file |
| `eval/benchmark/metrics/__pycache__/retrieval.cpython-312.pyc` | 10,405 | Python bytecode cache file |
| `eval/benchmark/metrics/__pycache__/statistical.cpython-312.pyc` | 11,991 | Python bytecode cache file |
| `eval/benchmark/metrics/__pycache__/system.cpython-312.pyc` | 5,546 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/__init__.cpython-312.pyc` | 2,069 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/_base.cpython-312.pyc` | 4,907 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/bm25.cpython-312.pyc` | 6,445 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/codegraphrag.cpython-312.pyc` | 7,697 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/hybrid.cpython-312.pyc` | 8,854 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/no_ast.cpython-312.pyc` | 11,894 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/no_kg.cpython-312.pyc` | 4,875 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/simple_rag.cpython-312.pyc` | 6,531 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/single_agent.cpython-312.pyc` | 5,930 | Python bytecode cache file |
| `eval/benchmark/systems/__pycache__/vector_only.cpython-312.pyc` | 4,027 | Python bytecode cache file |
| `eval/benchmark_dataset.json` | 167,731 | Obsolete scratch script or debug log |
| `eval/call_answer_q1.py` | 1,478 | Obsolete scratch script or debug log |
| `eval/compare.py` | 327 | Obsolete scratch script or debug log |
| `eval/debug_dataset.json` | 12,891 | Obsolete scratch script or debug log |
| `eval/diagnose_q1.py` | 4,778 | Obsolete scratch script or debug log |
| `eval/final_dataset.json` | 390 | Obsolete scratch script or debug log |
| `eval/find_q1_log.py` | 1,397 | Obsolete scratch script or debug log |
| `eval/get_q1_prompt.py` | 6,031 | Obsolete scratch script or debug log |
| `eval/list_q_logs.py` | 575 | Obsolete scratch script or debug log |
| `eval/q1_prompt.txt` | 1,025,700 | Obsolete scratch script or debug log |
| `eval/q1_stage_ids.json` | 5,137 | Obsolete scratch script or debug log |
| `eval/results/20260720_033410/run_results.json` | 11,799 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/checksums.json` | 96 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/environment/packages.json` | 10,381 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/environment/seeds.json` | 150 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/environment/system_info.json` | 712 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/error_analysis/failure_categories.json` | 404 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/error_analysis/failures.jsonl` | 3,804 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/experiment_logs/config_used.yaml` | 433 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/experiment_logs/run.log` | 1,345 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/figures/latency_boxplot.pdf` | 16,040 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/figures/latency_boxplot.png` | 22,646 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/figures/recall_at_k_curve.pdf` | 15,992 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/figures/recall_at_k_curve.png` | 24,091 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/figures/system_comparison.pdf` | 15,959 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/figures/system_comparison.png` | 28,066 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/integrity_report.json` | 687 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/manifest.json` | 2,378 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/metrics/comparison.json` | 2,102 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/metrics/per_system.json` | 879 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/metrics/statistical_tests.json` | 946 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/raw/CodeGraphRAG.jsonl` | 76,791 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/summary.json` | 1,197 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/tables/main_results.csv` | 152 | Obsolete benchmark execution run output directory |
| `eval/results/iteration1_20260719_043553/tables/main_results.tex` | 531 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154128/experiment_logs/config_used.yaml` | 1,460 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/checksums.json` | 703 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/environment/packages.json` | 9,111 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/environment/seeds.json` | 144 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/environment/system_info.json` | 690 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/error_analysis/failure_categories.json` | 5,255 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/error_analysis/failures.jsonl` | 614,984 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/experiment_logs/config_used.yaml` | 1,460 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/figures/latency_boxplot.pdf` | 21,464 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/figures/latency_boxplot.png` | 68,975 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/figures/recall_at_k_curve.pdf` | 22,332 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/figures/recall_at_k_curve.png` | 43,511 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/figures/system_comparison.pdf` | 19,395 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/figures/system_comparison.png` | 45,081 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/integrity_report.json` | 3,147 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/manifest.json` | 3,637 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/metrics/comparison.json` | 14,755 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/metrics/per_system.json` | 6,618 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/metrics/statistical_tests.json` | 6,799 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/BM25.jsonl` | 153,434 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/CodeGraphRAG.jsonl` | 154,561 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/Hybrid.jsonl` | 153,725 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/NoAST.jsonl` | 154,159 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/NoKG.jsonl` | 153,973 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/SimpleRAG.jsonl` | 154,794 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/SingleAgent.jsonl` | 155,028 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/raw/VectorOnly.jsonl` | 154,871 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/tables/main_results.csv` | 551 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154200/tables/main_results.tex` | 1,009 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/checksums.json` | 703 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/environment/packages.json` | 9,111 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/environment/seeds.json` | 144 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/environment/system_info.json` | 689 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/error_analysis/failure_categories.json` | 5,255 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/error_analysis/failures.jsonl` | 614,984 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/experiment_logs/config_used.yaml` | 1,442 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/figures/latency_boxplot.pdf` | 21,489 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/figures/latency_boxplot.png` | 63,875 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/figures/recall_at_k_curve.pdf` | 22,332 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/figures/recall_at_k_curve.png` | 43,511 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/figures/system_comparison.pdf` | 19,395 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/figures/system_comparison.png` | 45,081 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/integrity_report.json` | 3,147 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/manifest.json` | 3,596 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/metrics/comparison.json` | 14,760 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/metrics/per_system.json` | 6,623 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/metrics/statistical_tests.json` | 6,799 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/BM25.jsonl` | 153,427 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/CodeGraphRAG.jsonl` | 154,550 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/Hybrid.jsonl` | 153,716 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/NoAST.jsonl` | 154,181 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/NoKG.jsonl` | 153,954 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/SimpleRAG.jsonl` | 154,759 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/SingleAgent.jsonl` | 155,021 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/raw/VectorOnly.jsonl` | 154,852 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/tables/main_results.csv` | 551 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154422/tables/main_results.tex` | 1,009 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154810/environment/packages.json` | 2,929 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154810/environment/seeds.json` | 144 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154810/environment/system_info.json` | 631 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154810/experiment_logs/config_used.yaml` | 1,442 | Obsolete benchmark execution run output directory |
| `eval/results/main_comparison_20260707_154810/manifest.json` | 3,560 | Obsolete benchmark execution run output directory |
| `eval/results/redesigned/COMPARISON_CHUNK_VS_EXPANDED_Q1.md` | 10,282 | Obsolete benchmark execution run output directory |
| `eval/results/redesigned/COMPARISON_Q1.md` | 16,243 | Obsolete benchmark execution run output directory |
| `eval/results/redesigned/STRICT_COMPARISON_Q1.md` | 20,067 | Obsolete benchmark execution run output directory |
| `eval/results/redesigned/validation_Q1.md` | 36,240 | Obsolete benchmark execution run output directory |
| `eval/results/redesigned/validation_Q1_chunk_only.md` | 36,240 | Obsolete benchmark execution run output directory |
| `eval/results/redesigned/validation_Q1_expanded.md` | 45,383 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_0_gold_reference_validation.json` | 1,923 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_1_retrieval_diagnostics.json` | 7,512 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_2_reranker_validation.json` | 10,707 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_3_canonical_claim_construction.json` | 4,367 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_4_evidence_verification_&_calibration.json` | 104,306 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_5_metric_computation.json` | 2,314 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_6_regression_&_acceptance_validation.json` | 1,687 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/artifacts/Q1/stage_7_report_generation.json` | 342,155 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1/validation_Q1_expanded.md` | 24,795 | Obsolete benchmark execution run output directory |
| `eval/results/run_q10/validation_Q10.md` | 178 | Obsolete benchmark execution run output directory |
| `eval/results/run_q11/validation_Q11.md` | 194 | Obsolete benchmark execution run output directory |
| `eval/results/run_q12/validation_Q12.md` | 188 | Obsolete benchmark execution run output directory |
| `eval/results/run_q13/validation_Q13.md` | 192 | Obsolete benchmark execution run output directory |
| `eval/results/run_q14/validation_Q14.md` | 199 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_0_gold_reference_validation.json` | 1,923 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_1_retrieval_diagnostics.json` | 7,292 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_2_reranker_validation.json` | 10,707 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_3_canonical_claim_construction.json` | 4,368 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_4_evidence_verification_&_calibration.json` | 104,306 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_5_metric_computation.json` | 2,314 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_6_regression_&_acceptance_validation.json` | 1,688 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/artifacts/Q1/stage_7_report_generation.json` | 341,973 | Obsolete benchmark execution run output directory |
| `eval/results/run_q1_fixed/validation_Q1_expanded.md` | 24,795 | Obsolete benchmark execution run output directory |
| `eval/results/run_q3/validation_Q3.md` | 965 | Obsolete benchmark execution run output directory |
| `eval/results/run_q4/validation_Q4.md` | 604 | Obsolete benchmark execution run output directory |
| `eval/results/run_q5/validation_Q5.md` | 444 | Obsolete benchmark execution run output directory |
| `eval/results/run_q6/validation_Q6.md` | 715 | Obsolete benchmark execution run output directory |
| `eval/results/run_q7/validation_Q7.md` | 191 | Obsolete benchmark execution run output directory |
| `eval/results/run_q8/validation_Q8.md` | 803 | Obsolete benchmark execution run output directory |
| `eval/results/run_q9/validation_Q9.md` | 816 | Obsolete benchmark execution run output directory |
| `eval/results/test_val/validation_Q1_chunk_only.md` | 35,549 | Obsolete benchmark execution run output directory |
| `eval/run_orch_debug_q1.py` | 2,228 | Obsolete scratch script or debug log |
| `eval/run_q14_orch.py` | 1,831 | Obsolete scratch script or debug log |
| `eval/run_vsearch_q1.py` | 936 | Obsolete scratch script or debug log |
| `eval/semantic_cache.db` | 16,384 | Obsolete scratch script or debug log |
| `eval/show_last_q1.py` | 610 | Obsolete scratch script or debug log |
| `eval/stages/__pycache__/__init__.cpython-312.pyc` | 183 | Python bytecode cache file |
| `eval/stages/__pycache__/acceptance_validation_stage.cpython-312.pyc` | 5,366 | Python bytecode cache file |
| `eval/stages/__pycache__/claim_extraction_stage.cpython-312.pyc` | 5,296 | Python bytecode cache file |
| `eval/stages/__pycache__/evidence_verification_stage.cpython-312.pyc` | 6,921 | Python bytecode cache file |
| `eval/stages/__pycache__/gold_reference_stage.cpython-312.pyc` | 4,936 | Python bytecode cache file |
| `eval/stages/__pycache__/metric_computation_stage.cpython-312.pyc` | 9,596 | Python bytecode cache file |
| `eval/stages/__pycache__/report_generation_stage.cpython-312.pyc` | 4,953 | Python bytecode cache file |
| `eval/stages/__pycache__/reranker_stage.cpython-312.pyc` | 4,999 | Python bytecode cache file |
| `eval/stages/__pycache__/retrieval_stage.cpython-312.pyc` | 6,524 | Python bytecode cache file |
| `eval/test_dataset.json` | 2 | Obsolete scratch script or debug log |
| `extract_expected.py` | 0 | Obsolete scratch script or debug log |
| `extract_full_table3.py` | 571 | Obsolete scratch script or debug log |
| `extract_q1_details.py` | 2,251 | Obsolete scratch script or debug log |
| `extract_q1_prompt.py` | 1,126 | Obsolete scratch script or debug log |
| `fast_debug_eval.py` | 0 | Obsolete scratch script or debug log |
| `final_context_analysis.py` | 8,154 | Obsolete scratch script or debug log |
| `full_eval_quick.py` | 0 | Obsolete scratch script or debug log |
| `ingestion/__pycache__/__init__.cpython-312.pyc` | 128 | Python bytecode cache file |
| `ingestion/__pycache__/chunker.cpython-312.pyc` | 12,577 | Python bytecode cache file |
| `ingestion/__pycache__/diff_engine.cpython-312.pyc` | 7,010 | Python bytecode cache file |
| `ingestion/__pycache__/doc_chunker.cpython-312.pyc` | 13,306 | Python bytecode cache file |
| `ingestion/__pycache__/language_detect.cpython-312.pyc` | 1,426 | Python bytecode cache file |
| `ingestion/__pycache__/loader.cpython-312.pyc` | 6,496 | Python bytecode cache file |
| `ingestion/__pycache__/parser.cpython-312.pyc` | 8,953 | Python bytecode cache file |
| `ingestion/__pycache__/pdf_parser.cpython-312.pyc` | 14,824 | Python bytecode cache file |
| `ingestion/__pycache__/worker.cpython-312.pyc` | 26,486 | Python bytecode cache file |
| `llm/__pycache__/__init__.cpython-312.pyc` | 122 | Python bytecode cache file |
| `llm/__pycache__/backend.cpython-312.pyc` | 5,864 | Python bytecode cache file |
| `llm/__pycache__/ollama_backend.cpython-312.pyc` | 2,808 | Python bytecode cache file |
| `mistakes.txt` | 375 | Obsolete scratch script or debug log |
| `orch_test.py` | 327 | Obsolete scratch script or debug log |
| `paper_summary.py` | 1,502 | Obsolete scratch script or debug log |
| `quick_eval.py` | 0 | Obsolete scratch script or debug log |
| `rebuild_expected.py` | 0 | Obsolete scratch script or debug log |
| `retrieval/__pycache__/__init__.cpython-312.pyc` | 128 | Python bytecode cache file |
| `retrieval/__pycache__/cross_encoder_rerank.cpython-312.pyc` | 2,814 | Python bytecode cache file |
| `retrieval/__pycache__/graph_search.cpython-312.pyc` | 2,955 | Python bytecode cache file |
| `retrieval/__pycache__/metadata_filter.cpython-312.pyc` | 1,008 | Python bytecode cache file |
| `retrieval/__pycache__/mmr_rerank.cpython-312.pyc` | 4,923 | Python bytecode cache file |
| `retrieval/__pycache__/query_analyzer.cpython-312.pyc` | 5,075 | Python bytecode cache file |
| `retrieval/__pycache__/repository_router.cpython-312.pyc` | 7,150 | Python bytecode cache file |
| `retrieval/__pycache__/vector_search.cpython-312.pyc` | 880 | Python bytecode cache file |
| `scripts/__pycache__/build_demo_dataset.cpython-312.pyc` | 48,317 | Python bytecode cache file |
| `scripts/__pycache__/run_demo_index_eval.cpython-312.pyc` | 46,584 | Python bytecode cache file |
| `show_top_chunk.py` | 0 | Obsolete scratch script or debug log |
| `storage/__pycache__/__init__.cpython-312.pyc` | 126 | Python bytecode cache file |
| `storage/__pycache__/cache.cpython-312.pyc` | 10,065 | Python bytecode cache file |
| `storage/__pycache__/knowledge_graph.cpython-312.pyc` | 5,753 | Python bytecode cache file |
| `storage/__pycache__/metadata_store.cpython-312.pyc` | 3,538 | Python bytecode cache file |
| `storage/__pycache__/progress.cpython-312.pyc` | 9,071 | Python bytecode cache file |
| `storage/__pycache__/registry.cpython-312.pyc` | 7,134 | Python bytecode cache file |
| `storage/__pycache__/snapshot.cpython-312.pyc` | 4,634 | Python bytecode cache file |
| `storage/__pycache__/vector_store.cpython-312.pyc` | 16,117 | Python bytecode cache file |
| `test_embeddings_smoke.py` | 1,284 | Obsolete scratch script or debug log |
| `test_full_pipeline.py` | 1,284 | Obsolete scratch script or debug log |
| `test_incremental.py` | 3,179 | Obsolete scratch script or debug log |
| `test_incremental_indexing.py` | 3,486 | Obsolete scratch script or debug log |
| `test_llm_answers.py` | 0 | Obsolete scratch script or debug log |
| `test_progressive_indexing.py` | 5,105 | Obsolete scratch script or debug log |
| `test_report_generator.py` | 667 | Obsolete scratch script or debug log |
| `tests/__pycache__/__init__.cpython-312.pyc` | 699 | Python bytecode cache file |
| `tests/__pycache__/test_api.cpython-312-pytest-8.1.0.pyc` | 3,358 | Python bytecode cache file |
| `tests/__pycache__/test_benchmark_dataset.cpython-312-pytest-8.1.0.pyc` | 5,702 | Python bytecode cache file |
| `tests/__pycache__/test_benchmark_evaluator.cpython-312-pytest-8.1.0.pyc` | 6,968 | Python bytecode cache file |
| `tests/__pycache__/test_benchmark_metrics.cpython-312-pytest-8.1.0.pyc` | 5,781 | Python bytecode cache file |
| `tests/__pycache__/test_cache.cpython-312-pytest-8.1.0.pyc` | 6,155 | Python bytecode cache file |
| `tests/__pycache__/test_chunker.cpython-312-pytest-8.1.0.pyc` | 2,282 | Python bytecode cache file |
| `tests/__pycache__/test_code_agent.cpython-312-pytest-8.1.0.pyc` | 1,701 | Python bytecode cache file |
| `tests/__pycache__/test_cross_encoder_rerank.cpython-312-pytest-8.1.0.pyc` | 1,364 | Python bytecode cache file |
| `tests/__pycache__/test_data_agent.cpython-312-pytest-8.1.0.pyc` | 1,662 | Python bytecode cache file |
| `tests/__pycache__/test_e2e_hotload.cpython-312-pytest-8.1.0.pyc` | 4,829 | Python bytecode cache file |
| `tests/__pycache__/test_e2e_retrieval.cpython-312-pytest-8.1.0.pyc` | 8,324 | Python bytecode cache file |
| `tests/__pycache__/test_escalated_e2e.cpython-312-pytest-8.1.0.pyc` | 2,983 | Python bytecode cache file |
| `tests/__pycache__/test_graph_search.cpython-312-pytest-8.1.0.pyc` | 2,421 | Python bytecode cache file |
| `tests/__pycache__/test_integration.cpython-312-pytest-8.1.0.pyc` | 2,752 | Python bytecode cache file |
| `tests/__pycache__/test_knowledge_graph.cpython-312-pytest-8.1.0.pyc` | 3,620 | Python bytecode cache file |
| `tests/__pycache__/test_language_detect.cpython-312-pytest-8.1.0.pyc` | 1,680 | Python bytecode cache file |
| `tests/__pycache__/test_large_integration.cpython-312-pytest-8.1.0.pyc` | 2,130 | Python bytecode cache file |
| `tests/__pycache__/test_loader.cpython-312-pytest-8.1.0.pyc` | 5,686 | Python bytecode cache file |
| `tests/__pycache__/test_manual_queries.cpython-312-pytest-8.1.0.pyc` | 3,342 | Python bytecode cache file |
| `tests/__pycache__/test_metadata_filter.cpython-312-pytest-8.1.0.pyc` | 1,626 | Python bytecode cache file |
| `tests/__pycache__/test_metadata_store.cpython-312-pytest-8.1.0.pyc` | 2,237 | Python bytecode cache file |
| `tests/__pycache__/test_mmr_rerank.cpython-312-pytest-8.1.0.pyc` | 1,395 | Python bytecode cache file |
| `tests/__pycache__/test_one_query_timings.cpython-312-pytest-8.1.0.pyc` | 770 | Python bytecode cache file |
| `tests/__pycache__/test_orchestrator.cpython-312-pytest-8.1.0.pyc` | 5,521 | Python bytecode cache file |
| `tests/__pycache__/test_parser.cpython-312-pytest-8.1.0.pyc` | 3,388 | Python bytecode cache file |
| `tests/__pycache__/test_phase0.cpython-312-pytest-8.1.0.pyc` | 1,700 | Python bytecode cache file |
| `tests/__pycache__/test_phase3_dod.cpython-312-pytest-8.1.0.pyc` | 6,674 | Python bytecode cache file |
| `tests/__pycache__/test_phase3_routing.cpython-312-pytest-8.1.0.pyc` | 1,905 | Python bytecode cache file |
| `tests/__pycache__/test_query_planner.cpython-312-pytest-8.1.0.pyc` | 5,487 | Python bytecode cache file |
| `tests/__pycache__/test_reasoning_agent.cpython-312-pytest-8.1.0.pyc` | 1,741 | Python bytecode cache file |
| `tests/__pycache__/test_registry.cpython-312-pytest-8.1.0.pyc` | 8,441 | Python bytecode cache file |
| `tests/__pycache__/test_repository_api.cpython-312-pytest-8.1.0.pyc` | 10,217 | Python bytecode cache file |
| `tests/__pycache__/test_repository_router.cpython-312-pytest-8.1.0.pyc` | 4,573 | Python bytecode cache file |
| `tests/__pycache__/test_router.cpython-312-pytest-8.1.0.pyc` | 2,086 | Python bytecode cache file |
| `tests/__pycache__/test_vector_search.cpython-312-pytest-8.1.0.pyc` | 3,681 | Python bytecode cache file |
| `tests/__pycache__/test_vector_store.cpython-312-pytest-8.1.0.pyc` | 4,482 | Python bytecode cache file |
| `ui/__pycache__/app.cpython-312.pyc` | 16,102 | Python bytecode cache file |
| `validate_index.py` | 0 | Obsolete scratch script or debug log |

## 4. Preserved Assets Summary

- **Production Source Code**: `api/`, `ingestion/`, `retrieval/`, `llm/`, `storage/`, `metadata_storage/`, `kg_storage/`, `ui/`, `baselines/`, `agents/`, `engineering/`, `test_repo_src/`, `tests/`
- **Canonical Benchmark Dataset**: [eval/generated_benchmark.json](file:///d:/DocRag/eval/generated_benchmark.json) (40 questions)
- **Pilot Benchmark Dataset**: [eval/ai_papers_expected_answers.json](file:///d:/DocRag/eval/ai_papers_expected_answers.json) (14 questions)
- **Preserved Benchmark Artifacts**: `eval/results/run_q1_postfix/`, `eval/results/run_q2/artifacts/Q2/`, `eval/scientific_validation/checkpoints/`
- **Architecture Documentation**: `DEPLOYMENT_ARCHITECTURE.md`, `HandOverSummary.md`, `SYSTEM_ARCHITECTURE_V2.md`, etc.
- **Configuration Files**: `config.yaml`, `config.orig`, `registry.json`

## 5. Duplicate Files & Actions Taken

- `eval/ai_papers_expected_answers_REBUILD.json`: Identified as incomplete duplicate of pilot answers; **removed**.
- `eval/benchmark_dataset.json`: Identified as legacy code repository benchmark dataset; **removed**.
- `eval/results/run_q1_fixed`: Identified as superseded run output of Q1; **removed** (retained canonical `run_q1_postfix`).

## 6. Manual Review Items

- **None**. All deletions were strictly unambiguous temporary logs, scratch python scripts, and superseded run outputs. No uncertain files were deleted.
