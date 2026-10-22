# Repository Inventory

This document provides a complete inventory of all files in the `d:\DocRag` repository categorized into 12 functional categories.

## Summary Statistics

| Category | Preserved File Count | Description |
| :--- | :---: | :--- |
| **Source Code** | 90 | Production RAG pipeline, API, ingestion, retrieval, LLM, storage, UI, agents, baselines, and unit tests |
| **Benchmark Scripts** | 87 | Evaluation framework harnesses, stage runners, and benchmark scripts |
| **Benchmark Datasets** | 102 | Canonical 40-question benchmark dataset, pilot dataset, and source paper PDFs |
| **Benchmark Outputs** | 37 | Preserved benchmark evaluation artifacts for Q1, Q2, and Q1-Q5 checkpoints |
| **Verification Reports** | 7 | Root cause reports, ground truth analysis, and release verification reports |
| **Audit Reports** | 7 | Independent audit summaries and pipeline diagnostic notes |
| **Validation Logs** | 9 | Ingestion, indexing, and LLM call execution logs |
| **Documentation** | 30 | Architecture documents, specifications, and handover summary |
| **Deployment Files** | 6 | Repository release scripts, verification shell scripts, and git configuration |
| **Configuration Files** | 3 | System configuration parameters and collection registry |
| **Generated Artifacts** | 118 | Persisted Qdrant vector database, embedding cache, semantic cache, and snapshot stores |
| **Temporary Files** | 110 | Temporary scratch files retained for manual review (if any) |

---

## Detailed Inventory by Category

### Source Code (90 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [agents/__init__.py](file:///d:/DocRag/agents/__init__.py) | 0 |
| [agents/code_agent.py](file:///d:/DocRag/agents/code_agent.py) | 1,364 |
| [agents/data_agent.py](file:///d:/DocRag/agents/data_agent.py) | 1,387 |
| [agents/doc_agent.py](file:///d:/DocRag/agents/doc_agent.py) | 5,689 |
| [agents/orchestrator.py](file:///d:/DocRag/agents/orchestrator.py) | 23,851 |
| [agents/query_planner.py](file:///d:/DocRag/agents/query_planner.py) | 11,210 |
| [agents/reasoning_agent.py](file:///d:/DocRag/agents/reasoning_agent.py) | 1,509 |
| [agents/router.py](file:///d:/DocRag/agents/router.py) | 3,110 |
| [api/__init__.py](file:///d:/DocRag/api/__init__.py) | 0 |
| [api/dependencies.py](file:///d:/DocRag/api/dependencies.py) | 190 |
| [api/main.py](file:///d:/DocRag/api/main.py) | 6,678 |
| [api/query.py](file:///d:/DocRag/api/query.py) | 1,972 |
| [api/repository.py](file:///d:/DocRag/api/repository.py) | 5,090 |
| [baselines/__init__.py](file:///d:/DocRag/baselines/__init__.py) | 0 |
| [baselines/no_ast.py](file:///d:/DocRag/baselines/no_ast.py) | 72 |
| [baselines/no_kg.py](file:///d:/DocRag/baselines/no_kg.py) | 71 |
| [baselines/simple_rag.py](file:///d:/DocRag/baselines/simple_rag.py) | 76 |
| [baselines/single_agent.py](file:///d:/DocRag/baselines/single_agent.py) | 78 |
| [baselines/vector_only.py](file:///d:/DocRag/baselines/vector_only.py) | 77 |
| [ingestion/__init__.py](file:///d:/DocRag/ingestion/__init__.py) | 0 |
| [ingestion/chunker.py](file:///d:/DocRag/ingestion/chunker.py) | 16,785 |
| [ingestion/diff_engine.py](file:///d:/DocRag/ingestion/diff_engine.py) | 5,307 |
| [ingestion/doc_chunker.py](file:///d:/DocRag/ingestion/doc_chunker.py) | 11,372 |
| [ingestion/language_detect.py](file:///d:/DocRag/ingestion/language_detect.py) | 1,178 |
| [ingestion/loader.py](file:///d:/DocRag/ingestion/loader.py) | 5,534 |
| [ingestion/parser.py](file:///d:/DocRag/ingestion/parser.py) | 9,297 |
| [ingestion/pdf_parser.py](file:///d:/DocRag/ingestion/pdf_parser.py) | 14,126 |
| [ingestion/worker.py](file:///d:/DocRag/ingestion/worker.py) | 23,085 |
| [llm/__init__.py](file:///d:/DocRag/llm/__init__.py) | 0 |
| [llm/backend.py](file:///d:/DocRag/llm/backend.py) | 3,922 |
| [llm/ollama_backend.py](file:///d:/DocRag/llm/ollama_backend.py) | 2,465 |
| [llm/transformers_backend.py](file:///d:/DocRag/llm/transformers_backend.py) | 189 |
| [retrieval/__init__.py](file:///d:/DocRag/retrieval/__init__.py) | 0 |
| [retrieval/cross_encoder_rerank.py](file:///d:/DocRag/retrieval/cross_encoder_rerank.py) | 2,575 |
| [retrieval/graph_search.py](file:///d:/DocRag/retrieval/graph_search.py) | 2,627 |
| [retrieval/metadata_filter.py](file:///d:/DocRag/retrieval/metadata_filter.py) | 720 |
| [retrieval/mmr_rerank.py](file:///d:/DocRag/retrieval/mmr_rerank.py) | 4,375 |
| [retrieval/query_analyzer.py](file:///d:/DocRag/retrieval/query_analyzer.py) | 5,331 |
| [retrieval/repository_router.py](file:///d:/DocRag/retrieval/repository_router.py) | 5,375 |
| [retrieval/vector_search.py](file:///d:/DocRag/retrieval/vector_search.py) | 509 |
| [run_all.py](file:///d:/DocRag/run_all.py) | 3,998 |
| [storage/__init__.py](file:///d:/DocRag/storage/__init__.py) | 0 |
| [storage/cache.py](file:///d:/DocRag/storage/cache.py) | 7,049 |
| [storage/knowledge_graph.py](file:///d:/DocRag/storage/knowledge_graph.py) | 4,628 |
| [storage/metadata_store.py](file:///d:/DocRag/storage/metadata_store.py) | 1,725 |
| [storage/progress.py](file:///d:/DocRag/storage/progress.py) | 6,878 |
| [storage/registry.py](file:///d:/DocRag/storage/registry.py) | 4,629 |
| [storage/snapshot.py](file:///d:/DocRag/storage/snapshot.py) | 2,431 |
| [storage/vector_store.py](file:///d:/DocRag/storage/vector_store.py) | 13,914 |
| [test_repo_src/main.py](file:///d:/DocRag/test_repo_src/main.py) | 34 |
| [tests/__init__.py](file:///d:/DocRag/tests/__init__.py) | 449 |
| [tests/test_api.py](file:///d:/DocRag/tests/test_api.py) | 2,039 |
| [tests/test_benchmark_dataset.py](file:///d:/DocRag/tests/test_benchmark_dataset.py) | 4,131 |
| [tests/test_benchmark_evaluator.py](file:///d:/DocRag/tests/test_benchmark_evaluator.py) | 5,103 |
| [tests/test_benchmark_metrics.py](file:///d:/DocRag/tests/test_benchmark_metrics.py) | 4,579 |
| [tests/test_cache.py](file:///d:/DocRag/tests/test_cache.py) | 1,607 |
| [tests/test_chunker.py](file:///d:/DocRag/tests/test_chunker.py) | 1,410 |
| [tests/test_code_agent.py](file:///d:/DocRag/tests/test_code_agent.py) | 1,013 |
| [tests/test_cross_encoder_rerank.py](file:///d:/DocRag/tests/test_cross_encoder_rerank.py) | 740 |
| [tests/test_data_agent.py](file:///d:/DocRag/tests/test_data_agent.py) | 977 |
| [tests/test_e2e_hotload.py](file:///d:/DocRag/tests/test_e2e_hotload.py) | 1,222 |
| [tests/test_e2e_retrieval.py](file:///d:/DocRag/tests/test_e2e_retrieval.py) | 6,550 |
| [tests/test_escalated_e2e.py](file:///d:/DocRag/tests/test_escalated_e2e.py) | 2,146 |
| [tests/test_graph_search.py](file:///d:/DocRag/tests/test_graph_search.py) | 2,017 |
| [tests/test_integration.py](file:///d:/DocRag/tests/test_integration.py) | 2,824 |
| [tests/test_knowledge_graph.py](file:///d:/DocRag/tests/test_knowledge_graph.py) | 1,994 |
| [tests/test_language_detect.py](file:///d:/DocRag/tests/test_language_detect.py) | 810 |
| [tests/test_large_integration.py](file:///d:/DocRag/tests/test_large_integration.py) | 1,553 |
| [tests/test_loader.py](file:///d:/DocRag/tests/test_loader.py) | 2,833 |
| [tests/test_manual_queries.py](file:///d:/DocRag/tests/test_manual_queries.py) | 1,959 |
| [tests/test_metadata_filter.py](file:///d:/DocRag/tests/test_metadata_filter.py) | 1,022 |
| [tests/test_metadata_store.py](file:///d:/DocRag/tests/test_metadata_store.py) | 1,171 |
| [tests/test_mmr_rerank.py](file:///d:/DocRag/tests/test_mmr_rerank.py) | 1,043 |
| [tests/test_one_query_timings.py](file:///d:/DocRag/tests/test_one_query_timings.py) | 284 |
| [tests/test_orchestrator.py](file:///d:/DocRag/tests/test_orchestrator.py) | 4,154 |
| [tests/test_parser.py](file:///d:/DocRag/tests/test_parser.py) | 1,951 |
| [tests/test_phase0.py](file:///d:/DocRag/tests/test_phase0.py) | 1,050 |
| [tests/test_phase3_dod.py](file:///d:/DocRag/tests/test_phase3_dod.py) | 5,735 |
| [tests/test_phase3_routing.py](file:///d:/DocRag/tests/test_phase3_routing.py) | 1,473 |
| [tests/test_query_planner.py](file:///d:/DocRag/tests/test_query_planner.py) | 2,850 |
| [tests/test_reasoning_agent.py](file:///d:/DocRag/tests/test_reasoning_agent.py) | 1,063 |
| [tests/test_registry.py](file:///d:/DocRag/tests/test_registry.py) | 2,165 |
| [tests/test_repository_api.py](file:///d:/DocRag/tests/test_repository_api.py) | 2,287 |
| [tests/test_repository_router.py](file:///d:/DocRag/tests/test_repository_router.py) | 1,772 |
| [tests/test_router.py](file:///d:/DocRag/tests/test_router.py) | 1,048 |
| [tests/test_vector_search.py](file:///d:/DocRag/tests/test_vector_search.py) | 2,371 |
| [tests/test_vector_store.py](file:///d:/DocRag/tests/test_vector_store.py) | 3,082 |
| [tests/verification.py](file:///d:/DocRag/tests/verification.py) | 3,761 |
| [ui/__init__.py](file:///d:/DocRag/ui/__init__.py) | 0 |
| [ui/app.py](file:///d:/DocRag/ui/app.py) | 20,489 |

### Benchmark Scripts (87 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [eval/__init__.py](file:///d:/DocRag/eval/__init__.py) | 0 |
| [eval/accuracy.py](file:///d:/DocRag/eval/accuracy.py) | 45 |
| [eval/archive/comprehensive_eval.py](file:///d:/DocRag/eval/archive/comprehensive_eval.py) | 6,479 |
| [eval/archive/debug_retrieval.py](file:///d:/DocRag/eval/archive/debug_retrieval.py) | 1,434 |
| [eval/archive/eval_ai.py](file:///d:/DocRag/eval/archive/eval_ai.py) | 1,674 |
| [eval/archive/eval_ai_papers.py](file:///d:/DocRag/eval/archive/eval_ai_papers.py) | 1,433 |
| [eval/archive/eval_retrieval.py](file:///d:/DocRag/eval/archive/eval_retrieval.py) | 2,198 |
| [eval/archive/extract_expected.py](file:///d:/DocRag/eval/archive/extract_expected.py) | 2,467 |
| [eval/archive/fast_debug_eval.py](file:///d:/DocRag/eval/archive/fast_debug_eval.py) | 1,784 |
| [eval/archive/full_eval_quick.py](file:///d:/DocRag/eval/archive/full_eval_quick.py) | 2,618 |
| [eval/archive/quick_eval.py](file:///d:/DocRag/eval/archive/quick_eval.py) | 1,325 |
| [eval/archive/rebuild_expected.py](file:///d:/DocRag/eval/archive/rebuild_expected.py) | 4,398 |
| [eval/archive/run_eval_auto.py](file:///d:/DocRag/eval/archive/run_eval_auto.py) | 325 |
| [eval/archive/run_full_eval_pipeline.py](file:///d:/DocRag/eval/archive/run_full_eval_pipeline.py) | 4,393 |
| [eval/audit_checkpoints.py](file:///d:/DocRag/eval/audit_checkpoints.py) | 2,829 |
| [eval/benchmark/__init__.py](file:///d:/DocRag/eval/benchmark/__init__.py) | 532 |
| [eval/benchmark/artifacts/__init__.py](file:///d:/DocRag/eval/benchmark/artifacts/__init__.py) | 491 |
| [eval/benchmark/artifacts/environment.py](file:///d:/DocRag/eval/benchmark/artifacts/environment.py) | 4,609 |
| [eval/benchmark/artifacts/error_analysis.py](file:///d:/DocRag/eval/benchmark/artifacts/error_analysis.py) | 6,031 |
| [eval/benchmark/artifacts/figures.py](file:///d:/DocRag/eval/benchmark/artifacts/figures.py) | 9,010 |
| [eval/benchmark/artifacts/integrity.py](file:///d:/DocRag/eval/benchmark/artifacts/integrity.py) | 14,152 |
| [eval/benchmark/artifacts/manifest.py](file:///d:/DocRag/eval/benchmark/artifacts/manifest.py) | 7,698 |
| [eval/benchmark/artifacts/tables.py](file:///d:/DocRag/eval/benchmark/artifacts/tables.py) | 8,379 |
| [eval/benchmark/dataset.py](file:///d:/DocRag/eval/benchmark/dataset.py) | 21,015 |
| [eval/benchmark/evaluator.py](file:///d:/DocRag/eval/benchmark/evaluator.py) | 24,593 |
| [eval/benchmark/interface.py](file:///d:/DocRag/eval/benchmark/interface.py) | 8,369 |
| [eval/benchmark/metrics/__init__.py](file:///d:/DocRag/eval/benchmark/metrics/__init__.py) | 850 |
| [eval/benchmark/metrics/generation.py](file:///d:/DocRag/eval/benchmark/metrics/generation.py) | 12,301 |
| [eval/benchmark/metrics/retrieval.py](file:///d:/DocRag/eval/benchmark/metrics/retrieval.py) | 8,801 |
| [eval/benchmark/metrics/statistical.py](file:///d:/DocRag/eval/benchmark/metrics/statistical.py) | 10,334 |
| [eval/benchmark/metrics/system.py](file:///d:/DocRag/eval/benchmark/metrics/system.py) | 4,040 |
| [eval/benchmark/systems/__init__.py](file:///d:/DocRag/eval/benchmark/systems/__init__.py) | 1,890 |
| [eval/benchmark/systems/_base.py](file:///d:/DocRag/eval/benchmark/systems/_base.py) | 3,376 |
| [eval/benchmark/systems/bm25.py](file:///d:/DocRag/eval/benchmark/systems/bm25.py) | 4,321 |
| [eval/benchmark/systems/codegraphrag.py](file:///d:/DocRag/eval/benchmark/systems/codegraphrag.py) | 5,721 |
| [eval/benchmark/systems/hybrid.py](file:///d:/DocRag/eval/benchmark/systems/hybrid.py) | 6,222 |
| [eval/benchmark/systems/no_ast.py](file:///d:/DocRag/eval/benchmark/systems/no_ast.py) | 9,030 |
| [eval/benchmark/systems/no_kg.py](file:///d:/DocRag/eval/benchmark/systems/no_kg.py) | 3,218 |
| [eval/benchmark/systems/simple_rag.py](file:///d:/DocRag/eval/benchmark/systems/simple_rag.py) | 4,594 |
| [eval/benchmark/systems/single_agent.py](file:///d:/DocRag/eval/benchmark/systems/single_agent.py) | 4,007 |
| [eval/benchmark/systems/vector_only.py](file:///d:/DocRag/eval/benchmark/systems/vector_only.py) | 2,356 |
| [eval/check_final_contexts.py](file:///d:/DocRag/eval/check_final_contexts.py) | 1,231 |
| [eval/comprehensive_evaluator.py](file:///d:/DocRag/eval/comprehensive_evaluator.py) | 36,102 |
| [eval/diagnostic_reporter.py](file:///d:/DocRag/eval/diagnostic_reporter.py) | 3,928 |
| [eval/evaluate.py](file:///d:/DocRag/eval/evaluate.py) | 45 |
| [eval/evaluator.py](file:///d:/DocRag/eval/evaluator.py) | 6,300 |
| [eval/final_campaign_runner.py](file:///d:/DocRag/eval/final_campaign_runner.py) | 3,799 |
| [eval/generate_audit_data.py](file:///d:/DocRag/eval/generate_audit_data.py) | 2,031 |
| [eval/generate_dataset.py](file:///d:/DocRag/eval/generate_dataset.py) | 14,709 |
| [eval/independent_auditor.py](file:///d:/DocRag/eval/independent_auditor.py) | 11,275 |
| [eval/latency.py](file:///d:/DocRag/eval/latency.py) | 44 |
| [eval/memory.py](file:///d:/DocRag/eval/memory.py) | 43 |
| [eval/metrics.py](file:///d:/DocRag/eval/metrics.py) | 2,023 |
| [eval/phase10_reviewer_report.py](file:///d:/DocRag/eval/phase10_reviewer_report.py) | 2,488 |
| [eval/phase11_auditor_report.py](file:///d:/DocRag/eval/phase11_auditor_report.py) | 2,222 |
| [eval/phase5_retrieval_only.py](file:///d:/DocRag/eval/phase5_retrieval_only.py) | 4,086 |
| [eval/phase6_difficulty_calibration.py](file:///d:/DocRag/eval/phase6_difficulty_calibration.py) | 4,113 |
| [eval/phase7_statistical_analysis.py](file:///d:/DocRag/eval/phase7_statistical_analysis.py) | 4,146 |
| [eval/phase8_error_analysis.py](file:///d:/DocRag/eval/phase8_error_analysis.py) | 2,285 |
| [eval/phase9_figures.py](file:///d:/DocRag/eval/phase9_figures.py) | 2,489 |
| [eval/production_validation.py](file:///d:/DocRag/eval/production_validation.py) | 18,535 |
| [eval/redesigned_evaluator.py](file:///d:/DocRag/eval/redesigned_evaluator.py) | 57,825 |
| [eval/regression_tester.py](file:///d:/DocRag/eval/regression_tester.py) | 7,303 |
| [eval/retrieval.py](file:///d:/DocRag/eval/retrieval.py) | 46 |
| [eval/run.py](file:///d:/DocRag/eval/run.py) | 937 |
| [eval/run_experiment.py](file:///d:/DocRag/eval/run_experiment.py) | 6,947 |
| [eval/run_incremental_pilot_validation.py](file:///d:/DocRag/eval/run_incremental_pilot_validation.py) | 21,824 |
| [eval/run_scientific_validation.py](file:///d:/DocRag/eval/run_scientific_validation.py) | 39,190 |
| [eval/stage_framework.py](file:///d:/DocRag/eval/stage_framework.py) | 5,459 |
| [eval/stage_harness.py](file:///d:/DocRag/eval/stage_harness.py) | 4,691 |
| [eval/stages/__init__.py](file:///d:/DocRag/eval/stages/__init__.py) | 43 |
| [eval/stages/acceptance_validation_stage.py](file:///d:/DocRag/eval/stages/acceptance_validation_stage.py) | 4,983 |
| [eval/stages/claim_extraction_stage.py](file:///d:/DocRag/eval/stages/claim_extraction_stage.py) | 4,080 |
| [eval/stages/evidence_verification_stage.py](file:///d:/DocRag/eval/stages/evidence_verification_stage.py) | 6,452 |
| [eval/stages/gold_reference_stage.py](file:///d:/DocRag/eval/stages/gold_reference_stage.py) | 4,728 |
| [eval/stages/metric_computation_stage.py](file:///d:/DocRag/eval/stages/metric_computation_stage.py) | 8,913 |
| [eval/stages/report_generation_stage.py](file:///d:/DocRag/eval/stages/report_generation_stage.py) | 4,410 |
| [eval/stages/reranker_stage.py](file:///d:/DocRag/eval/stages/reranker_stage.py) | 4,177 |
| [eval/stages/retrieval_stage.py](file:///d:/DocRag/eval/stages/retrieval_stage.py) | 5,705 |
| [eval/targeted_benchmark.py](file:///d:/DocRag/eval/targeted_benchmark.py) | 5,389 |
| [eval/test_stage_invariants.py](file:///d:/DocRag/eval/test_stage_invariants.py) | 5,916 |
| [eval/verify_benchmark.py](file:///d:/DocRag/eval/verify_benchmark.py) | 773 |
| [eval/verify_environment.py](file:///d:/DocRag/eval/verify_environment.py) | 1,089 |
| [eval_ai_papers.py](file:///d:/DocRag/eval_ai_papers.py) | 0 |
| [eval_retrieval.py](file:///d:/DocRag/eval_retrieval.py) | 0 |
| [reindex_ai_papers.py](file:///d:/DocRag/reindex_ai_papers.py) | 2,538 |
| [run_http_benchmark.py](file:///d:/DocRag/run_http_benchmark.py) | 4,772 |

### Benchmark Datasets (102 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [demo_dataset/Artificial_Intelligence/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf) | 910,612 |
| [demo_dataset/Artificial_Intelligence/Asynchronous Methods for Deep Reinforcement Learning.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Asynchronous Methods for Deep Reinforcement Learning.pdf) | 2,302,720 |
| [demo_dataset/Artificial_Intelligence/Attention Is All You Need.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Attention Is All You Need.pdf) | 2,215,244 |
| [demo_dataset/Artificial_Intelligence/Auto-Encoding Variational Bayes.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Auto-Encoding Variational Bayes.pdf) | 3,926,758 |
| [demo_dataset/Artificial_Intelligence/Compliance_Generation_for_Privacy_Documents_under_.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Compliance_Generation_for_Privacy_Documents_under_.pdf) | 150,935 |
| [demo_dataset/Artificial_Intelligence/Distilling the Knowledge in a Neural Network.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Distilling the Knowledge in a Neural Network.pdf) | 106,630 |
| [demo_dataset/Artificial_Intelligence/DynamicK_Recommendation_with_Personalized_Decision.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/DynamicK_Recommendation_with_Personalized_Decision.pdf) | 538,965 |
| [demo_dataset/Artificial_Intelligence/Fuzzy_Commitments_Offer_Insufficient_Protection_to.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Fuzzy_Commitments_Offer_Insufficient_Protection_to.pdf) | 682,516 |
| [demo_dataset/Artificial_Intelligence/Generalization_in_portfoliobased_algorithm_selecti.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Generalization_in_portfoliobased_algorithm_selecti.pdf) | 928,885 |
| [demo_dataset/Artificial_Intelligence/Generative Adversarial Nets.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Generative Adversarial Nets.pdf) | 530,482 |
| [demo_dataset/Artificial_Intelligence/I_like_fish_especially_dolphins_Addressing_Contrad.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/I_like_fish_especially_dolphins_Addressing_Contrad.pdf) | 9,326,917 |
| [demo_dataset/Artificial_Intelligence/Language Models are Few-Shot Learners.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Language Models are Few-Shot Learners.pdf) | 6,768,044 |
| [demo_dataset/Artificial_Intelligence/Modelling_Human_Routines_Conceptualising_Social_Pr.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Modelling_Human_Routines_Conceptualising_Social_Pr.pdf) | 728,372 |
| [demo_dataset/Artificial_Intelligence/Overview_of_FPGA_deep_learning_acceleration_based_.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Overview_of_FPGA_deep_learning_acceleration_based_.pdf) | 615,285 |
| [demo_dataset/Artificial_Intelligence/Playing Atari with Deep Reinforcement Learning.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Playing Atari with Deep Reinforcement Learning.pdf) | 483,443 |
| [demo_dataset/Artificial_Intelligence/Proximal Policy Optimization Algorithms.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Proximal Policy Optimization Algorithms.pdf) | 2,923,532 |
| [demo_dataset/Artificial_Intelligence/Rethink_AIbased_Power_Grid_Control_Diving_Into_Alg.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Rethink_AIbased_Power_Grid_Control_Diving_Into_Alg.pdf) | 1,539,450 |
| [demo_dataset/Artificial_Intelligence/Skeletonbased_Approaches_based_on_Machine_Vision_A.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Skeletonbased_Approaches_based_on_Machine_Vision_A.pdf) | 273,435 |
| [demo_dataset/Artificial_Intelligence/Soft Actor-Critic - Off-Policy Maximum Entropy Deep Reinforcement Learning.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/Soft Actor-Critic - Off-Policy Maximum Entropy Deep Reinforcement Learning.pdf) | 4,388,102 |
| [demo_dataset/Artificial_Intelligence/World Models.pdf](file:///d:/DocRag/demo_dataset/Artificial_Intelligence/World Models.pdf) | 3,147,467 |
| [demo_dataset/Computer_Vision/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf](file:///d:/DocRag/demo_dataset/Computer_Vision/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf) | 910,612 |
| [demo_dataset/Computer_Vision/Mask R-CNN.pdf](file:///d:/DocRag/demo_dataset/Computer_Vision/Mask R-CNN.pdf) | 7,723,886 |
| [demo_dataset/Machine_Learning/A Unified Approach to Interpreting Model Predictions.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/A Unified Approach to Interpreting Model Predictions.pdf) | 1,014,198 |
| [demo_dataset/Machine_Learning/A_Comparative_Analysis_of_Bias_Amplification_in_Gr.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/A_Comparative_Analysis_of_Bias_Amplification_in_Gr.pdf) | 1,396,190 |
| [demo_dataset/Machine_Learning/Adam - A Method for Stochastic Optimization.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Adam - A Method for Stochastic Optimization.pdf) | 584,641 |
| [demo_dataset/Machine_Learning/Batch Normalization - Accelerating Deep Network Training.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Batch Normalization - Accelerating Deep Network Training.pdf) | 173,548 |
| [demo_dataset/Machine_Learning/Denoising Diffusion Probabilistic Models.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Denoising Diffusion Probabilistic Models.pdf) | 10,267,274 |
| [demo_dataset/Machine_Learning/Enhancing_Genetic_Algorithms_with_Graph_Neural_Net.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Enhancing_Genetic_Algorithms_with_Graph_Neural_Net.pdf) | 887,673 |
| [demo_dataset/Machine_Learning/Graph_Neural_Network_Encoding_for_Community_Detect.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Graph_Neural_Network_Encoding_for_Community_Detect.pdf) | 924,209 |
| [demo_dataset/Machine_Learning/Graph_Neural_Network_Training_Systems_A_Performanc.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Graph_Neural_Network_Training_Systems_A_Performanc.pdf) | 1,431,482 |
| [demo_dataset/Machine_Learning/Graph_Neural_Networks_for_RFIDBased_Spatial_Geomet.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Graph_Neural_Networks_for_RFIDBased_Spatial_Geomet.pdf) | 11,667,665 |
| [demo_dataset/Machine_Learning/Graph_neural_network_for_colliding_particles_with_.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Graph_neural_network_for_colliding_particles_with_.pdf) | 5,689,593 |
| [demo_dataset/Machine_Learning/Improving Neural Networks by Preventing Co-Adaptation of Feature Detectors.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Improving Neural Networks by Preventing Co-Adaptation of Feature Detectors.pdf) | 1,665,256 |
| [demo_dataset/Machine_Learning/Layer Normalization.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Layer Normalization.pdf) | 612,446 |
| [demo_dataset/Machine_Learning/LoRA - Low-Rank Adaptation of Large Language Models.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/LoRA - Low-Rank Adaptation of Large Language Models.pdf) | 1,609,513 |
| [demo_dataset/Machine_Learning/Neural Architecture Search with Reinforcement Learning.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Neural Architecture Search with Reinforcement Learning.pdf) | 733,204 |
| [demo_dataset/Machine_Learning/Optimizing_Age_of_Information_in_Vehicular_Edge_Co.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Optimizing_Age_of_Information_in_Vehicular_Edge_Co.pdf) | 847,908 |
| [demo_dataset/Machine_Learning/Proficient_Graph_Neural_Network_Design_by_Accumula.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Proficient_Graph_Neural_Network_Design_by_Accumula.pdf) | 2,685,989 |
| [demo_dataset/Machine_Learning/Trading_Graph_Neural_Network.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Trading_Graph_Neural_Network.pdf) | 6,275,974 |
| [demo_dataset/Machine_Learning/Understanding Deep Learning Requires Rethinking Generalization.pdf](file:///d:/DocRag/demo_dataset/Machine_Learning/Understanding Deep Learning Requires Rethinking Generalization.pdf) | 403,563 |
| [eval/ai_papers_expected_answers.json](file:///d:/DocRag/eval/ai_papers_expected_answers.json) | 9,044 |
| [eval/generated_benchmark.json](file:///d:/DocRag/eval/generated_benchmark.json) | 67,836 |
| [papers/AI/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf](file:///d:/DocRag/papers/AI/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf) | 910,612 |
| [papers/AI/Compliance_Generation_for_Privacy_Documents_under_.pdf](file:///d:/DocRag/papers/AI/Compliance_Generation_for_Privacy_Documents_under_.pdf) | 150,935 |
| [papers/AI/DynamicK_Recommendation_with_Personalized_Decision.pdf](file:///d:/DocRag/papers/AI/DynamicK_Recommendation_with_Personalized_Decision.pdf) | 538,965 |
| [papers/AI/Fuzzy_Commitments_Offer_Insufficient_Protection_to.pdf](file:///d:/DocRag/papers/AI/Fuzzy_Commitments_Offer_Insufficient_Protection_to.pdf) | 682,516 |
| [papers/AI/Generalization_in_portfoliobased_algorithm_selecti.pdf](file:///d:/DocRag/papers/AI/Generalization_in_portfoliobased_algorithm_selecti.pdf) | 928,885 |
| [papers/AI/I_like_fish_especially_dolphins_Addressing_Contrad.pdf](file:///d:/DocRag/papers/AI/I_like_fish_especially_dolphins_Addressing_Contrad.pdf) | 9,326,917 |
| [papers/AI/Modelling_Human_Routines_Conceptualising_Social_Pr.pdf](file:///d:/DocRag/papers/AI/Modelling_Human_Routines_Conceptualising_Social_Pr.pdf) | 728,372 |
| [papers/AI/Overview_of_FPGA_deep_learning_acceleration_based_.pdf](file:///d:/DocRag/papers/AI/Overview_of_FPGA_deep_learning_acceleration_based_.pdf) | 615,285 |
| [papers/AI/Rethink_AIbased_Power_Grid_Control_Diving_Into_Alg.pdf](file:///d:/DocRag/papers/AI/Rethink_AIbased_Power_Grid_Control_Diving_Into_Alg.pdf) | 1,539,450 |
| [papers/AI/Skeletonbased_Approaches_based_on_Machine_Vision_A.pdf](file:///d:/DocRag/papers/AI/Skeletonbased_Approaches_based_on_Machine_Vision_A.pdf) | 273,435 |
| [papers/ComputerVision/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf](file:///d:/DocRag/papers/ComputerVision/A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf) | 910,612 |
| [papers/ComputerVision/AppearanceInvariant_6DoF_Visual_Localization_using.pdf](file:///d:/DocRag/papers/ComputerVision/AppearanceInvariant_6DoF_Visual_Localization_using.pdf) | 12,197,314 |
| [papers/ComputerVision/Flexible_deep_transfer_learning_by_separate_featur.pdf](file:///d:/DocRag/papers/ComputerVision/Flexible_deep_transfer_learning_by_separate_featur.pdf) | 899,167 |
| [papers/ComputerVision/General_Domain_Adaptation_Through_Proportional_Pro.pdf](file:///d:/DocRag/papers/ComputerVision/General_Domain_Adaptation_Through_Proportional_Pro.pdf) | 1,761,707 |
| [papers/ComputerVision/Image_to_Bengali_Caption_Generation_Using_Deep_CNN.pdf](file:///d:/DocRag/papers/ComputerVision/Image_to_Bengali_Caption_Generation_Using_Deep_CNN.pdf) | 386,419 |
| [papers/ComputerVision/Leaf_Segmentation_and_Counting_with_Deep_Learning_.pdf](file:///d:/DocRag/papers/ComputerVision/Leaf_Segmentation_and_Counting_with_Deep_Learning_.pdf) | 1,914,293 |
| [papers/ComputerVision/PointINet_Point_Cloud_Frame_Interpolation_Network.pdf](file:///d:/DocRag/papers/ComputerVision/PointINet_Point_Cloud_Frame_Interpolation_Network.pdf) | 2,094,371 |
| [papers/ComputerVision/Prediction_of_Chronic_Kidney_Disease_Using_Deep_Ne.pdf](file:///d:/DocRag/papers/ComputerVision/Prediction_of_Chronic_Kidney_Disease_Using_Deep_Ne.pdf) | 321,245 |
| [papers/ComputerVision/Randomized_RX_for_target_detection.pdf](file:///d:/DocRag/papers/ComputerVision/Randomized_RX_for_target_detection.pdf) | 2,467,835 |
| [papers/ComputerVision/Underwater_image_filtering_methods_datasets_and_ev.pdf](file:///d:/DocRag/papers/ComputerVision/Underwater_image_filtering_methods_datasets_and_ev.pdf) | 19,600,441 |
| [papers/GraphML/A_Comparative_Analysis_of_Bias_Amplification_in_Gr.pdf](file:///d:/DocRag/papers/GraphML/A_Comparative_Analysis_of_Bias_Amplification_in_Gr.pdf) | 1,396,190 |
| [papers/GraphML/Enhancing_Genetic_Algorithms_with_Graph_Neural_Net.pdf](file:///d:/DocRag/papers/GraphML/Enhancing_Genetic_Algorithms_with_Graph_Neural_Net.pdf) | 887,673 |
| [papers/GraphML/Graph_Neural_Network_Encoding_for_Community_Detect.pdf](file:///d:/DocRag/papers/GraphML/Graph_Neural_Network_Encoding_for_Community_Detect.pdf) | 924,209 |
| [papers/GraphML/Graph_Neural_Network_Training_Systems_A_Performanc.pdf](file:///d:/DocRag/papers/GraphML/Graph_Neural_Network_Training_Systems_A_Performanc.pdf) | 1,431,482 |
| [papers/GraphML/Graph_Neural_Networks_for_RFIDBased_Spatial_Geomet.pdf](file:///d:/DocRag/papers/GraphML/Graph_Neural_Networks_for_RFIDBased_Spatial_Geomet.pdf) | 11,667,665 |
| [papers/GraphML/Graph_neural_network_for_colliding_particles_with_.pdf](file:///d:/DocRag/papers/GraphML/Graph_neural_network_for_colliding_particles_with_.pdf) | 5,689,593 |
| [papers/GraphML/Heterogeneous_Information_Networkbased_Interest_Co.pdf](file:///d:/DocRag/papers/GraphML/Heterogeneous_Information_Networkbased_Interest_Co.pdf) | 1,398,110 |
| [papers/GraphML/Optimizing_Age_of_Information_in_Vehicular_Edge_Co.pdf](file:///d:/DocRag/papers/GraphML/Optimizing_Age_of_Information_in_Vehicular_Edge_Co.pdf) | 847,908 |
| [papers/GraphML/Proficient_Graph_Neural_Network_Design_by_Accumula.pdf](file:///d:/DocRag/papers/GraphML/Proficient_Graph_Neural_Network_Design_by_Accumula.pdf) | 2,685,989 |
| [papers/GraphML/Trading_Graph_Neural_Network.pdf](file:///d:/DocRag/papers/GraphML/Trading_Graph_Neural_Network.pdf) | 6,275,974 |
| [papers/LLM/Demystifying_Instruction_Mixing_for_Finetuning_Lar.pdf](file:///d:/DocRag/papers/LLM/Demystifying_Instruction_Mixing_for_Finetuning_Lar.pdf) | 557,017 |
| [papers/LLM/Evolutionary_Computation_in_the_Era_of_Large_Langu.pdf](file:///d:/DocRag/papers/LLM/Evolutionary_Computation_in_the_Era_of_Large_Langu.pdf) | 463,962 |
| [papers/LLM/Exploring_Advanced_Large_Language_Models_with_LLMs.pdf](file:///d:/DocRag/papers/LLM/Exploring_Advanced_Large_Language_Models_with_LLMs.pdf) | 3,989,183 |
| [papers/LLM/Jais_and_Jaischat_ArabicCentric_Foundation_and_Ins.pdf](file:///d:/DocRag/papers/LLM/Jais_and_Jaischat_ArabicCentric_Foundation_and_Ins.pdf) | 1,134,944 |
| [papers/LLM/LOLA__An_OpenSource_Massively_Multilingual_Large_L.pdf](file:///d:/DocRag/papers/LLM/LOLA__An_OpenSource_Massively_Multilingual_Large_L.pdf) | 1,888,027 |
| [papers/LLM/Large_Language_Model_Evaluation_Via_Multi_AI_Agent.pdf](file:///d:/DocRag/papers/LLM/Large_Language_Model_Evaluation_Via_Multi_AI_Agent.pdf) | 327,556 |
| [papers/LLM/Learning_From_Failure_Integrating_Negative_Example.pdf](file:///d:/DocRag/papers/LLM/Learning_From_Failure_Integrating_Negative_Example.pdf) | 585,083 |
| [papers/LLM/PBLLM_Partially_Binarized_Large_Language_Models.pdf](file:///d:/DocRag/papers/LLM/PBLLM_Partially_Binarized_Large_Language_Models.pdf) | 959,389 |
| [papers/LLM/PediatricsGPT_Large_Language_Models_as_Chinese_Med.pdf](file:///d:/DocRag/papers/LLM/PediatricsGPT_Large_Language_Models_as_Chinese_Med.pdf) | 2,786,689 |
| [papers/LLM/WizardCoder_Empowering_Code_Large_Language_Models_.pdf](file:///d:/DocRag/papers/LLM/WizardCoder_Empowering_Code_Large_Language_Models_.pdf) | 1,273,887 |
| [papers/RAG/A_Collaborative_MultiAgent_Approach_to_RetrievalAu.pdf](file:///d:/DocRag/papers/RAG/A_Collaborative_MultiAgent_Approach_to_RetrievalAu.pdf) | 1,157,800 |
| [papers/RAG/A_Reproducibility_Study_of_Metacognitive_Retrieval.pdf](file:///d:/DocRag/papers/RAG/A_Reproducibility_Study_of_Metacognitive_Retrieval.pdf) | 770,954 |
| [papers/RAG/Automated_Literature_Review_Using_NLP_Techniques_a.pdf](file:///d:/DocRag/papers/RAG/Automated_Literature_Review_Using_NLP_Techniques_a.pdf) | 664,722 |
| [papers/RAG/Context_Awareness_Gate_For_Retrieval_Augmented_Gen.pdf](file:///d:/DocRag/papers/RAG/Context_Awareness_Gate_For_Retrieval_Augmented_Gen.pdf) | 223,905 |
| [papers/RAG/Engineering_the_RAG_Stack_A_Comprehensive_Review_o.pdf](file:///d:/DocRag/papers/RAG/Engineering_the_RAG_Stack_A_Comprehensive_Review_o.pdf) | 2,917,925 |
| [papers/RAG/FAIRRAG_Faithful_Adaptive_Iterative_Refinement_for.pdf](file:///d:/DocRag/papers/RAG/FAIRRAG_Faithful_Adaptive_Iterative_Refinement_for.pdf) | 2,367,153 |
| [papers/RAG/GFMRAG_Graph_Foundation_Model_for_Retrieval_Augmen.pdf](file:///d:/DocRag/papers/RAG/GFMRAG_Graph_Foundation_Model_for_Retrieval_Augmen.pdf) | 1,148,983 |
| [papers/RAG/Investigating_RetrievalAugmented_Generation_in_Qur.pdf](file:///d:/DocRag/papers/RAG/Investigating_RetrievalAugmented_Generation_in_Qur.pdf) | 545,201 |
| [papers/RAG/Overview_of_the_TREC_2025_Retrieval_Augmented_Gene.pdf](file:///d:/DocRag/papers/RAG/Overview_of_the_TREC_2025_Retrieval_Augmented_Gene.pdf) | 3,652,650 |
| [papers/RAG/Riddle_Me_This_Stealthy_Membership_Inference_for_R.pdf](file:///d:/DocRag/papers/RAG/Riddle_Me_This_Stealthy_Membership_Inference_for_R.pdf) | 1,693,722 |
| [papers/Robotics/Accurate_Energetic_Constraints_for_Passive_Grasp_S.pdf](file:///d:/DocRag/papers/Robotics/Accurate_Energetic_Constraints_for_Passive_Grasp_S.pdf) | 2,915,753 |
| [papers/Robotics/Analysis_of_Safe_Ultrawideband_HumanRobot_Communic.pdf](file:///d:/DocRag/papers/Robotics/Analysis_of_Safe_Ultrawideband_HumanRobot_Communic.pdf) | 1,697,077 |
| [papers/Robotics/GISBased_Estimation_of_Seasonal_Solar_Energy_Poten.pdf](file:///d:/DocRag/papers/Robotics/GISBased_Estimation_of_Seasonal_Solar_Energy_Poten.pdf) | 784,406 |
| [papers/Robotics/HighSpeed_Robot_Navigation_using_Predicted_Occupan.pdf](file:///d:/DocRag/papers/Robotics/HighSpeed_Robot_Navigation_using_Predicted_Occupan.pdf) | 1,696,974 |
| [papers/Robotics/MAVSec_Securing_the_MAVLink_Protocol_for_Ardupilot.pdf](file:///d:/DocRag/papers/Robotics/MAVSec_Securing_the_MAVLink_Protocol_for_Ardupilot.pdf) | 1,141,962 |
| [papers/Robotics/Modeling_Dispositional_and_Initial_learned_Trust_i.pdf](file:///d:/DocRag/papers/Robotics/Modeling_Dispositional_and_Initial_learned_Trust_i.pdf) | 2,367,452 |
| [papers/Robotics/Modeling_Vibration_Control_and_Trajectory_Tracking.pdf](file:///d:/DocRag/papers/Robotics/Modeling_Vibration_Control_and_Trajectory_Tracking.pdf) | 3,358,130 |
| [papers/Robotics/OneShot_Object_Localization_Using_Learnt_Visual_Cu.pdf](file:///d:/DocRag/papers/Robotics/OneShot_Object_Localization_Using_Learnt_Visual_Cu.pdf) | 2,924,721 |
| *... and 2 additional files* | |

### Benchmark Outputs (37 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_0_gold_reference_validation.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_0_gold_reference_validation.json) | 1,923 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_1_retrieval_diagnostics.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_1_retrieval_diagnostics.json) | 7,293 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_2_reranker_validation.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_2_reranker_validation.json) | 10,708 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_3_canonical_claim_construction.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_3_canonical_claim_construction.json) | 4,367 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_4_evidence_verification_&_calibration.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_4_evidence_verification_&_calibration.json) | 104,305 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_5_metric_computation.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_5_metric_computation.json) | 2,313 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_6_regression_&_acceptance_validation.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_6_regression_&_acceptance_validation.json) | 1,687 |
| [eval/results/run_q1_postfix/artifacts/Q1/stage_7_report_generation.json](file:///d:/DocRag/eval/results/run_q1_postfix/artifacts/Q1/stage_7_report_generation.json) | 341,970 |
| [eval/results/run_q1_postfix/validation_Q1_expanded.md](file:///d:/DocRag/eval/results/run_q1_postfix/validation_Q1_expanded.md) | 24,795 |
| [eval/results/run_q2/artifacts/Q2/stage_0_gold_reference_validation.json](file:///d:/DocRag/eval/results/run_q2/artifacts/Q2/stage_0_gold_reference_validation.json) | 1,924 |
| [eval/scientific_validation/checkpoints/Q1/claim_verification.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q1/claim_verification.json) | 8,411 |
| [eval/scientific_validation/checkpoints/Q1/expanded_evidence.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q1/expanded_evidence.json) | 65,980 |
| [eval/scientific_validation/checkpoints/Q1/metrics.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q1/metrics.json) | 542 |
| [eval/scientific_validation/checkpoints/Q1/question.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q1/question.json) | 704 |
| [eval/scientific_validation/checkpoints/Q1/retrieved_chunks.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q1/retrieved_chunks.json) | 9,344 |
| [eval/scientific_validation/checkpoints/Q2/claim_verification.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q2/claim_verification.json) | 19,973 |
| [eval/scientific_validation/checkpoints/Q2/expanded_evidence.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q2/expanded_evidence.json) | 460,477 |
| [eval/scientific_validation/checkpoints/Q2/metrics.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q2/metrics.json) | 541 |
| [eval/scientific_validation/checkpoints/Q2/question.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q2/question.json) | 745 |
| [eval/scientific_validation/checkpoints/Q2/retrieved_chunks.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q2/retrieved_chunks.json) | 13,612 |
| [eval/scientific_validation/checkpoints/Q3/claim_verification.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q3/claim_verification.json) | 2,194 |
| [eval/scientific_validation/checkpoints/Q3/expanded_evidence.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q3/expanded_evidence.json) | 56,588 |
| [eval/scientific_validation/checkpoints/Q3/metrics.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q3/metrics.json) | 539 |
| [eval/scientific_validation/checkpoints/Q3/question.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q3/question.json) | 606 |
| [eval/scientific_validation/checkpoints/Q3/retrieved_chunks.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q3/retrieved_chunks.json) | 16,252 |
| [eval/scientific_validation/checkpoints/Q4/claim_verification.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q4/claim_verification.json) | 5,021 |
| [eval/scientific_validation/checkpoints/Q4/expanded_evidence.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q4/expanded_evidence.json) | 25,605 |
| [eval/scientific_validation/checkpoints/Q4/metrics.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q4/metrics.json) | 541 |
| [eval/scientific_validation/checkpoints/Q4/question.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q4/question.json) | 673 |
| [eval/scientific_validation/checkpoints/Q4/retrieved_chunks.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q4/retrieved_chunks.json) | 17,541 |
| [eval/scientific_validation/checkpoints/Q5/claim_verification.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q5/claim_verification.json) | 15,582 |
| [eval/scientific_validation/checkpoints/Q5/expanded_evidence.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q5/expanded_evidence.json) | 117,723 |
| [eval/scientific_validation/checkpoints/Q5/metrics.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q5/metrics.json) | 543 |
| [eval/scientific_validation/checkpoints/Q5/question.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q5/question.json) | 734 |
| [eval/scientific_validation/checkpoints/Q5/retrieved_chunks.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q5/retrieved_chunks.json) | 14,783 |
| [eval/scientific_validation/checkpoints/Q6/question.json](file:///d:/DocRag/eval/scientific_validation/checkpoints/Q6/question.json) | 690 |
| [scripts/paper_benchmarks.json](file:///d:/DocRag/scripts/paper_benchmarks.json) | 20,498 |

### Verification Reports (7 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [eval/pilot_validation_report.md](file:///d:/DocRag/eval/pilot_validation_report.md) | 55,228 |
| [eval/scientific_validation_report.md](file:///d:/DocRag/eval/scientific_validation_report.md) | 142,393 |
| [ground_truth_final_report.md](file:///d:/DocRag/ground_truth_final_report.md) | 8,888 |
| [llm_failure_decomposition_report.md](file:///d:/DocRag/llm_failure_decomposition_report.md) | 11,809 |
| [root_cause_final_report.md](file:///d:/DocRag/root_cause_final_report.md) | 6,917 |
| [scripts/release_verification.json](file:///d:/DocRag/scripts/release_verification.json) | 270 |
| [scripts/validation_report.json](file:///d:/DocRag/scripts/validation_report.json) | 4,593 |

### Audit Reports (7 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [eval/audit_summary.txt](file:///d:/DocRag/eval/audit_summary.txt) | 110,576 |
| [eval/pilot_engineering_todo.md](file:///d:/DocRag/eval/pilot_engineering_todo.md) | 1,076 |
| [eval/pilot_metric_audit.md](file:///d:/DocRag/eval/pilot_metric_audit.md) | 1,521 |
| [eval/pilot_pipeline_diagnosis.md](file:///d:/DocRag/eval/pilot_pipeline_diagnosis.md) | 849 |
| [eval/pilot_root_cause_analysis.md](file:///d:/DocRag/eval/pilot_root_cause_analysis.md) | 1,834 |
| [eval/pilot_runtime_analysis.md](file:///d:/DocRag/eval/pilot_runtime_analysis.md) | 3,181 |
| [eval/pilot_summary.md](file:///d:/DocRag/eval/pilot_summary.md) | 2,360 |

### Validation Logs (9 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [logs/auto_optimizer.log](file:///d:/DocRag/logs/auto_optimizer.log) | 26,777 |
| [logs/build_demo_dataset.log](file:///d:/DocRag/logs/build_demo_dataset.log) | 225,689 |
| [logs/demo_build_checkpoint.json](file:///d:/DocRag/logs/demo_build_checkpoint.json) | 32,644 |
| [logs/indexing.log](file:///d:/DocRag/logs/indexing.log) | 71,316 |
| [logs/llm_call_metrics.jsonl](file:///d:/DocRag/logs/llm_call_metrics.jsonl) | 1,918,121 |
| [logs/llm_prompt_cache.json](file:///d:/DocRag/logs/llm_prompt_cache.json) | 1,333,148 |
| [logs/query_logs.jsonl](file:///d:/DocRag/logs/query_logs.jsonl) | 1,334,688 |
| [logs/retrieve_debug.jsonl](file:///d:/DocRag/logs/retrieve_debug.jsonl) | 70,241 |
| [logs/run_demo_index_eval.log](file:///d:/DocRag/logs/run_demo_index_eval.log) | 138,920 |

### Documentation (30 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [DEPLOYMENT_ARCHITECTURE.md](file:///d:/DocRag/DEPLOYMENT_ARCHITECTURE.md) | 1,497 |
| [HandOverSummary.md](file:///d:/DocRag/HandOverSummary.md) | 4,286 |
| [KNOWN_LIMITATIONS.md](file:///d:/DocRag/KNOWN_LIMITATIONS.md) | 1,740 |
| [MULTI_REPOSITORY_ARCHITECTURE.md](file:///d:/DocRag/MULTI_REPOSITORY_ARCHITECTURE.md) | 1,705 |
| [PERFORMANCE_BASELINE.md](file:///d:/DocRag/PERFORMANCE_BASELINE.md) | 1,209 |
| [PROJECT_SPEC.md](file:///d:/DocRag/PROJECT_SPEC.md) | 12,487 |
| [REQUEST_LIFECYCLE.md](file:///d:/DocRag/REQUEST_LIFECYCLE.md) | 1,927 |
| [SEQUENCE_DIAGRAMS.md](file:///d:/DocRag/SEQUENCE_DIAGRAMS.md) | 1,728 |
| [SYSTEM_ARCHITECTURE_V2.md](file:///d:/DocRag/SYSTEM_ARCHITECTURE_V2.md) | 2,749 |
| [docs/evaluation_stage_validation.md](file:///d:/DocRag/docs/evaluation_stage_validation.md) | 7,245 |
| [docs/master_technical_documentation.md](file:///d:/DocRag/docs/master_technical_documentation.md) | 27,091 |
| [engineering/CHANGELOG.md](file:///d:/DocRag/engineering/CHANGELOG.md) | 1,574 |
| [engineering/HANDOVER.md](file:///d:/DocRag/engineering/HANDOVER.md) | 3,719 |
| [engineering/decisions.md](file:///d:/DocRag/engineering/decisions.md) | 1,320 |
| [engineering/lessons_learned.md](file:///d:/DocRag/engineering/lessons_learned.md) | 1,294 |
| [eval/results/comprehensive/question_Q1.md](file:///d:/DocRag/eval/results/comprehensive/question_Q1.md) | 9,636 |
| [eval/results/comprehensive/question_Q10.md](file:///d:/DocRag/eval/results/comprehensive/question_Q10.md) | 8,719 |
| [eval/results/comprehensive/question_Q11.md](file:///d:/DocRag/eval/results/comprehensive/question_Q11.md) | 9,986 |
| [eval/results/comprehensive/question_Q12.md](file:///d:/DocRag/eval/results/comprehensive/question_Q12.md) | 10,265 |
| [eval/results/comprehensive/question_Q13.md](file:///d:/DocRag/eval/results/comprehensive/question_Q13.md) | 9,395 |
| [eval/results/comprehensive/question_Q14.md](file:///d:/DocRag/eval/results/comprehensive/question_Q14.md) | 9,422 |
| [eval/results/comprehensive/question_Q2.md](file:///d:/DocRag/eval/results/comprehensive/question_Q2.md) | 10,238 |
| [eval/results/comprehensive/question_Q3.md](file:///d:/DocRag/eval/results/comprehensive/question_Q3.md) | 9,020 |
| [eval/results/comprehensive/question_Q4.md](file:///d:/DocRag/eval/results/comprehensive/question_Q4.md) | 9,082 |
| [eval/results/comprehensive/question_Q5.md](file:///d:/DocRag/eval/results/comprehensive/question_Q5.md) | 9,243 |
| [eval/results/comprehensive/question_Q6.md](file:///d:/DocRag/eval/results/comprehensive/question_Q6.md) | 9,176 |
| [eval/results/comprehensive/question_Q7.md](file:///d:/DocRag/eval/results/comprehensive/question_Q7.md) | 9,774 |
| [eval/results/comprehensive/question_Q8.md](file:///d:/DocRag/eval/results/comprehensive/question_Q8.md) | 8,816 |
| [eval/results/comprehensive/question_Q9.md](file:///d:/DocRag/eval/results/comprehensive/question_Q9.md) | 10,259 |
| [eval/results/comprehensive/summary.md](file:///d:/DocRag/eval/results/comprehensive/summary.md) | 687 |

### Deployment Files (6 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [.gitignore](file:///d:/DocRag/.gitignore) | 213 |
| [scripts/build_40_benchmark.py](file:///d:/DocRag/scripts/build_40_benchmark.py) | 10,971 |
| [scripts/build_demo_dataset.py](file:///d:/DocRag/scripts/build_demo_dataset.py) | 39,675 |
| [scripts/download_arxiv.py](file:///d:/DocRag/scripts/download_arxiv.py) | 3,560 |
| [scripts/final_report.md](file:///d:/DocRag/scripts/final_report.md) | 8,242 |
| [scripts/run_final_validation.py](file:///d:/DocRag/scripts/run_final_validation.py) | 20,976 |

### Configuration Files (3 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [config.orig](file:///d:/DocRag/config.orig) | 560 |
| [config.yaml](file:///d:/DocRag/config.yaml) | 537 |
| [registry.json](file:///d:/DocRag/registry.json) | 54,750 |

### Generated Artifacts (118 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [embedding_cache.db](file:///d:/DocRag/embedding_cache.db) | 318,930,944 |
| [metadata_storage/metadata_124b83f1-7ff8-40ea-851a-dce7a75c2ddc.json](file:///d:/DocRag/metadata_storage/metadata_124b83f1-7ff8-40ea-851a-dce7a75c2ddc.json) | 518,847 |
| [metadata_storage/metadata_136fb565-818b-4f76-bea2-d614d9210a32.json](file:///d:/DocRag/metadata_storage/metadata_136fb565-818b-4f76-bea2-d614d9210a32.json) | 404,660 |
| [metadata_storage/metadata_200e4604-d1f4-4974-b648-77a8f18cefad.json](file:///d:/DocRag/metadata_storage/metadata_200e4604-d1f4-4974-b648-77a8f18cefad.json) | 191,791 |
| [metadata_storage/metadata_317b1fba-8cd9-4ab3-952d-9127605ee755.json](file:///d:/DocRag/metadata_storage/metadata_317b1fba-8cd9-4ab3-952d-9127605ee755.json) | 159,215 |
| [metadata_storage/metadata_3c518178-ff93-4e62-9b4f-6a9d792f8ec9.json](file:///d:/DocRag/metadata_storage/metadata_3c518178-ff93-4e62-9b4f-6a9d792f8ec9.json) | 467,591 |
| [metadata_storage/metadata_45fd01bb-8746-4957-b757-d6e8e8694225.json](file:///d:/DocRag/metadata_storage/metadata_45fd01bb-8746-4957-b757-d6e8e8694225.json) | 423,063 |
| [metadata_storage/metadata_5534d897-d89e-415b-8aad-172fcc3fa10f.json](file:///d:/DocRag/metadata_storage/metadata_5534d897-d89e-415b-8aad-172fcc3fa10f.json) | 416,844 |
| [metadata_storage/metadata_71e2cffe-8756-4ff3-b35c-52fc94babdd4.json](file:///d:/DocRag/metadata_storage/metadata_71e2cffe-8756-4ff3-b35c-52fc94babdd4.json) | 409,581 |
| [metadata_storage/metadata_8ef4eadb-9a6f-4b03-b70d-b392ffb0dfb9.json](file:///d:/DocRag/metadata_storage/metadata_8ef4eadb-9a6f-4b03-b70d-b392ffb0dfb9.json) | 409,581 |
| [metadata_storage/metadata_a9a2c333-3ecd-4f15-abff-c92a0563ec14.json](file:///d:/DocRag/metadata_storage/metadata_a9a2c333-3ecd-4f15-abff-c92a0563ec14.json) | 176,827 |
| [metadata_storage/metadata_b87b1922-36e4-4dbd-b107-2e24ae93a2b5.json](file:///d:/DocRag/metadata_storage/metadata_b87b1922-36e4-4dbd-b107-2e24ae93a2b5.json) | 26,308 |
| [metadata_storage/metadata_b87d234c-f2c4-4b22-a9e8-79d799ab04e2.json](file:///d:/DocRag/metadata_storage/metadata_b87d234c-f2c4-4b22-a9e8-79d799ab04e2.json) | 1,362,915 |
| [metadata_storage/metadata_b96544f2-7b61-4a45-af92-adac99a4a9c9.json](file:///d:/DocRag/metadata_storage/metadata_b96544f2-7b61-4a45-af92-adac99a4a9c9.json) | 188,425 |
| [metadata_storage/metadata_c47a259d-b199-4190-a271-ab59ddf5fb96.json](file:///d:/DocRag/metadata_storage/metadata_c47a259d-b199-4190-a271-ab59ddf5fb96.json) | 174,706 |
| [metadata_storage/metadata_cb2a0884-3ab4-449a-8d8d-44aa527a3d74.json](file:///d:/DocRag/metadata_storage/metadata_cb2a0884-3ab4-449a-8d8d-44aa527a3d74.json) | 191,791 |
| [metadata_storage/metadata_d3c5308f-c1af-4c7b-a980-311377790226.json](file:///d:/DocRag/metadata_storage/metadata_d3c5308f-c1af-4c7b-a980-311377790226.json) | 358,474 |
| [metadata_storage/metadata_e16b3da1-c6cb-41a1-984d-864b12c10a5e.json](file:///d:/DocRag/metadata_storage/metadata_e16b3da1-c6cb-41a1-984d-864b12c10a5e.json) | 26,308 |
| [metadata_storage/metadata_ebf3f09f-395f-4357-9007-67838bf71b2b.json](file:///d:/DocRag/metadata_storage/metadata_ebf3f09f-395f-4357-9007-67838bf71b2b.json) | 176,827 |
| [metadata_storage/metadata_ec211752-7c44-4991-9993-d3d892e6f4fb.json](file:///d:/DocRag/metadata_storage/metadata_ec211752-7c44-4991-9993-d3d892e6f4fb.json) | 159,215 |
| [metadata_store.json](file:///d:/DocRag/metadata_store.json) | 200,367 |
| [qdrant_storage/.lock](file:///d:/DocRag/qdrant_storage/.lock) | 13 |
| [qdrant_storage/collection/chunks/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/chunks/storage.sqlite) | 3,440,640 |
| [qdrant_storage/collection/collection_063a6ee8-679c-480f-8553-3862d39436a9/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_063a6ee8-679c-480f-8553-3862d39436a9/storage.sqlite) | 8,642,560 |
| [qdrant_storage/collection/collection_09785ba9-5e86-4c61-9109-b554303bb0f1/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_09785ba9-5e86-4c61-9109-b554303bb0f1/storage.sqlite) | 311,296 |
| [qdrant_storage/collection/collection_0b8cd185-4036-4fb8-bf44-a29cafa573a6/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_0b8cd185-4036-4fb8-bf44-a29cafa573a6/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_124b83f1-7ff8-40ea-851a-dce7a75c2ddc/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_124b83f1-7ff8-40ea-851a-dce7a75c2ddc/storage.sqlite) | 8,298,496 |
| [qdrant_storage/collection/collection_136fb565-818b-4f76-bea2-d614d9210a32/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_136fb565-818b-4f76-bea2-d614d9210a32/storage.sqlite) | 6,152,192 |
| [qdrant_storage/collection/collection_168a92a5-8ef0-431e-b333-94bf04f870d7/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_168a92a5-8ef0-431e-b333-94bf04f870d7/storage.sqlite) | 7,733,248 |
| [qdrant_storage/collection/collection_168ebbd9-77cb-4e3b-92bc-d1f1d973b746/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_168ebbd9-77cb-4e3b-92bc-d1f1d973b746/storage.sqlite) | 499,712 |
| [qdrant_storage/collection/collection_200e4604-d1f4-4974-b648-77a8f18cefad/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_200e4604-d1f4-4974-b648-77a8f18cefad/storage.sqlite) | 3,338,240 |
| [qdrant_storage/collection/collection_204c4fbd-e3b8-45b6-a7bd-fcc433771b91/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_204c4fbd-e3b8-45b6-a7bd-fcc433771b91/storage.sqlite) | 7,725,056 |
| [qdrant_storage/collection/collection_2086394b-7cbd-4d12-ac80-daa0138ba618/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_2086394b-7cbd-4d12-ac80-daa0138ba618/storage.sqlite) | 311,296 |
| [qdrant_storage/collection/collection_317b1fba-8cd9-4ab3-952d-9127605ee755/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_317b1fba-8cd9-4ab3-952d-9127605ee755/storage.sqlite) | 2,875,392 |
| [qdrant_storage/collection/collection_33e2ecb8-baa5-4cac-95f2-15d01e8c0878/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_33e2ecb8-baa5-4cac-95f2-15d01e8c0878/storage.sqlite) | 8,638,464 |
| [qdrant_storage/collection/collection_34b44d3b-7443-41e8-9aae-5c4804b60f5d/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_34b44d3b-7443-41e8-9aae-5c4804b60f5d/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_3c518178-ff93-4e62-9b4f-6a9d792f8ec9/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_3c518178-ff93-4e62-9b4f-6a9d792f8ec9/storage.sqlite) | 7,639,040 |
| [qdrant_storage/collection/collection_3f7366d4-4954-4f97-a7e8-bf4989940885/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_3f7366d4-4954-4f97-a7e8-bf4989940885/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_4143b2c2-27d4-45ef-8b61-f6f74f2a89f6/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_4143b2c2-27d4-45ef-8b61-f6f74f2a89f6/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_42680c4d-0017-4c53-931b-9e1758c6ec5f/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_42680c4d-0017-4c53-931b-9e1758c6ec5f/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_4412efb7-551d-4551-b3bc-369e99b5b875/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_4412efb7-551d-4551-b3bc-369e99b5b875/storage.sqlite) | 8,634,368 |
| [qdrant_storage/collection/collection_45947803-9858-4a87-9271-fd8ef35edad6/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_45947803-9858-4a87-9271-fd8ef35edad6/storage.sqlite) | 516,096 |
| [qdrant_storage/collection/collection_4643bbdd-8b0f-4c2e-9f30-67a20dc9884e/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_4643bbdd-8b0f-4c2e-9f30-67a20dc9884e/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_4a2977ee-18b3-45d2-825c-00e91a257e02/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_4a2977ee-18b3-45d2-825c-00e91a257e02/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_4dad3df5-2994-4988-949d-2e88f0762c3b/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_4dad3df5-2994-4988-949d-2e88f0762c3b/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_4fd70863-3d47-4a86-b199-2b4d078f932c/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_4fd70863-3d47-4a86-b199-2b4d078f932c/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_5534d897-d89e-415b-8aad-172fcc3fa10f/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_5534d897-d89e-415b-8aad-172fcc3fa10f/storage.sqlite) | 7,356,416 |
| [qdrant_storage/collection/collection_5d16c1fb-5cbd-4891-81a5-cf2bb6685acb/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_5d16c1fb-5cbd-4891-81a5-cf2bb6685acb/storage.sqlite) | 8,638,464 |
| [qdrant_storage/collection/collection_5fc5bf70-ce26-4919-9c1e-9d0da3c7b792/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_5fc5bf70-ce26-4919-9c1e-9d0da3c7b792/storage.sqlite) | 647,168 |
| [qdrant_storage/collection/collection_6ed40a3b-7c48-4ff0-9a22-7541966de668/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_6ed40a3b-7c48-4ff0-9a22-7541966de668/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_6ef6d306-d261-4dea-9506-8c9fc2dab777/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_6ef6d306-d261-4dea-9506-8c9fc2dab777/storage.sqlite) | 634,880 |
| [qdrant_storage/collection/collection_7149cf7d-80c6-43ee-bb42-e896e164f5b6/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_7149cf7d-80c6-43ee-bb42-e896e164f5b6/storage.sqlite) | 516,096 |
| [qdrant_storage/collection/collection_71e2cffe-8756-4ff3-b35c-52fc94babdd4/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_71e2cffe-8756-4ff3-b35c-52fc94babdd4/storage.sqlite) | 7,176,192 |
| [qdrant_storage/collection/collection_7c3d0472-292a-4a8e-ba50-b38526698a0a/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_7c3d0472-292a-4a8e-ba50-b38526698a0a/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_855239ac-4f94-4a39-81ab-a56da31abe55/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_855239ac-4f94-4a39-81ab-a56da31abe55/storage.sqlite) | 8,634,368 |
| [qdrant_storage/collection/collection_86192ea4-2d0e-42dc-a6a3-e215080f3e16/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_86192ea4-2d0e-42dc-a6a3-e215080f3e16/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_88c07576-18f1-468c-a776-70f2ad1487dc/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_88c07576-18f1-468c-a776-70f2ad1487dc/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_8aa9b57f-bdd1-4c6e-b4c5-1277c715fcbd/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_8aa9b57f-bdd1-4c6e-b4c5-1277c715fcbd/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_8c0b078a-b56b-4c02-990d-5520fa48f722/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_8c0b078a-b56b-4c02-990d-5520fa48f722/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_8c0f144e-e5df-4efa-89ed-807fa8e0e7da/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_8c0f144e-e5df-4efa-89ed-807fa8e0e7da/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_8ef4eadb-9a6f-4b03-b70d-b392ffb0dfb9/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_8ef4eadb-9a6f-4b03-b70d-b392ffb0dfb9/storage.sqlite) | 7,188,480 |
| [qdrant_storage/collection/collection_9284d724-0450-4b2a-b36b-70a30a232817/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_9284d724-0450-4b2a-b36b-70a30a232817/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_93a46c66-74fe-4f9d-a542-11e6e114cef4/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_93a46c66-74fe-4f9d-a542-11e6e114cef4/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_9d42adf0-616c-4cd7-9969-badda6c2d81c/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_9d42adf0-616c-4cd7-9969-badda6c2d81c/storage.sqlite) | 8,458,240 |
| [qdrant_storage/collection/collection_a9a2c333-3ecd-4f15-abff-c92a0563ec14/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_a9a2c333-3ecd-4f15-abff-c92a0563ec14/storage.sqlite) | 3,055,616 |
| [qdrant_storage/collection/collection_b79e8506-c69b-406f-b967-3093ffea6918/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_b79e8506-c69b-406f-b967-3093ffea6918/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_b87b1922-36e4-4dbd-b107-2e24ae93a2b5/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_b87b1922-36e4-4dbd-b107-2e24ae93a2b5/storage.sqlite) | 491,520 |
| [qdrant_storage/collection/collection_b87d234c-f2c4-4b22-a9e8-79d799ab04e2/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_b87d234c-f2c4-4b22-a9e8-79d799ab04e2/storage.sqlite) | 18,440,192 |
| [qdrant_storage/collection/collection_b889baa3-98f3-44a0-b69f-cf386d3c04a3/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_b889baa3-98f3-44a0-b69f-cf386d3c04a3/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_b96544f2-7b61-4a45-af92-adac99a4a9c9/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_b96544f2-7b61-4a45-af92-adac99a4a9c9/storage.sqlite) | 3,215,360 |
| [qdrant_storage/collection/collection_c18a1ab7-af97-444c-bd22-31b6a0855978/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_c18a1ab7-af97-444c-bd22-31b6a0855978/storage.sqlite) | 7,729,152 |
| [qdrant_storage/collection/collection_c327831e-b150-4309-8d7e-476e9e7e5fc3/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_c327831e-b150-4309-8d7e-476e9e7e5fc3/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_c47a259d-b199-4190-a271-ab59ddf5fb96/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_c47a259d-b199-4190-a271-ab59ddf5fb96/storage.sqlite) | 3,170,304 |
| [qdrant_storage/collection/collection_c5bcaad6-87b1-4581-adb8-280cd716e39e/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_c5bcaad6-87b1-4581-adb8-280cd716e39e/storage.sqlite) | 7,725,056 |
| [qdrant_storage/collection/collection_cb2a0884-3ab4-449a-8d8d-44aa527a3d74/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_cb2a0884-3ab4-449a-8d8d-44aa527a3d74/storage.sqlite) | 3,338,240 |
| [qdrant_storage/collection/collection_cfb92056-5527-4117-8e96-de30a97686f4/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_cfb92056-5527-4117-8e96-de30a97686f4/storage.sqlite) | 7,393,280 |
| [qdrant_storage/collection/collection_d3c5308f-c1af-4c7b-a980-311377790226/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_d3c5308f-c1af-4c7b-a980-311377790226/storage.sqlite) | 4,931,584 |
| [qdrant_storage/collection/collection_d567dc4a-6b28-422d-b945-d6a0ac44c434/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_d567dc4a-6b28-422d-b945-d6a0ac44c434/storage.sqlite) | 516,096 |
| [qdrant_storage/collection/collection_db305fa6-2d0a-4f31-851d-6dc2e4cb18be/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_db305fa6-2d0a-4f31-851d-6dc2e4cb18be/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_dd930d73-37d4-4fea-b181-1ae94debc516/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_dd930d73-37d4-4fea-b181-1ae94debc516/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_deab1205-90cf-4421-acec-6b82a2ee191e/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_deab1205-90cf-4421-acec-6b82a2ee191e/storage.sqlite) | 7,733,248 |
| [qdrant_storage/collection/collection_e16b3da1-c6cb-41a1-984d-864b12c10a5e/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_e16b3da1-c6cb-41a1-984d-864b12c10a5e/storage.sqlite) | 491,520 |
| [qdrant_storage/collection/collection_e8196d64-fb90-4c51-a2e1-6fd9af1213c4/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_e8196d64-fb90-4c51-a2e1-6fd9af1213c4/storage.sqlite) | 516,096 |
| [qdrant_storage/collection/collection_eb3c416e-482a-43b1-b0f9-f7e26c8585c2/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_eb3c416e-482a-43b1-b0f9-f7e26c8585c2/storage.sqlite) | 516,096 |
| [qdrant_storage/collection/collection_ebf3f09f-395f-4357-9007-67838bf71b2b/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_ebf3f09f-395f-4357-9007-67838bf71b2b/storage.sqlite) | 3,051,520 |
| [qdrant_storage/collection/collection_ec91ee74-7fdb-488a-b052-d5352e1297e4/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_ec91ee74-7fdb-488a-b052-d5352e1297e4/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_ef579180-ae4c-492b-a1f2-333ceede1e03/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_ef579180-ae4c-492b-a1f2-333ceede1e03/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_f1560ca4-070d-4aa0-9748-f965e1fa87c7/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_f1560ca4-070d-4aa0-9748-f965e1fa87c7/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_f21b67d4-cc19-4d9b-962b-58796f4e0096/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_f21b67d4-cc19-4d9b-962b-58796f4e0096/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_f31e6e62-a465-40e8-9fe7-73a40c23801e/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_f31e6e62-a465-40e8-9fe7-73a40c23801e/storage.sqlite) | 7,729,152 |
| [qdrant_storage/collection/collection_f3ae269c-8417-45d8-be2e-80f8d03ab70f/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_f3ae269c-8417-45d8-be2e-80f8d03ab70f/storage.sqlite) | 8,634,368 |
| [qdrant_storage/collection/collection_f7616c37-1199-453a-b2eb-ad966f8c766a/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_f7616c37-1199-453a-b2eb-ad966f8c766a/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_fa35a62e-4ad0-40ad-a379-3c5fe0249e06/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_fa35a62e-4ad0-40ad-a379-3c5fe0249e06/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_fb7050e4-aadc-4e63-9ab7-a7427cbb97bb/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_fb7050e4-aadc-4e63-9ab7-a7427cbb97bb/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/collection_fe6b9167-c96e-4d0c-9345-f69dc8c9b421/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/collection_fe6b9167-c96e-4d0c-9345-f69dc8c9b421/storage.sqlite) | 516,096 |
| [qdrant_storage/collection/test_dim_collection/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/test_dim_collection/storage.sqlite) | 12,288 |
| [qdrant_storage/collection/test_indexing/storage.sqlite](file:///d:/DocRag/qdrant_storage/collection/test_indexing/storage.sqlite) | 16,384 |
| [qdrant_storage/meta.json](file:///d:/DocRag/qdrant_storage/meta.json) | 37,586 |
| [semantic_cache.db](file:///d:/DocRag/semantic_cache.db) | 151,552 |
| [snapshot_storage/124b83f1-7ff8-40ea-851a-dce7a75c2ddc.json](file:///d:/DocRag/snapshot_storage/124b83f1-7ff8-40ea-851a-dce7a75c2ddc.json) | 136,929 |
| *... and 18 additional files* | |

### Temporary Files (110 files)

| Relative Path | Size (Bytes) |
| :--- | :---: |
| [agents/doc_agent.orig](file:///d:/DocRag/agents/doc_agent.orig) | 5,892 |
| [engineering/benchmark_status.json](file:///d:/DocRag/engineering/benchmark_status.json) | 6,736 |
| [engineering/progress.json](file:///d:/DocRag/engineering/progress.json) | 502 |
| [engineering/regression_history.json](file:///d:/DocRag/engineering/regression_history.json) | 516 |
| [eval/artifacts/Q1/stage_0_gold_reference_validation.json](file:///d:/DocRag/eval/artifacts/Q1/stage_0_gold_reference_validation.json) | 1,498 |
| [eval/artifacts/Q1/stage_6_regression_&_acceptance_validation.json](file:///d:/DocRag/eval/artifacts/Q1/stage_6_regression_&_acceptance_validation.json) | 981 |
| [eval/artifacts/Q10/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q10/stage_6_acceptance.json) | 1,033 |
| [eval/artifacts/Q11/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q11/stage_6_acceptance.json) | 1,049 |
| [eval/artifacts/Q12/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q12/stage_6_acceptance.json) | 1,061 |
| [eval/artifacts/Q13/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q13/stage_6_acceptance.json) | 1,027 |
| [eval/artifacts/Q14/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q14/stage_6_acceptance.json) | 1,067 |
| [eval/artifacts/Q3/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q3/stage_6_acceptance.json) | 1,292 |
| [eval/artifacts/Q4/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q4/stage_6_acceptance.json) | 1,211 |
| [eval/artifacts/Q5/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q5/stage_6_acceptance.json) | 1,039 |
| [eval/artifacts/Q6/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q6/stage_6_acceptance.json) | 1,326 |
| [eval/artifacts/Q7/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q7/stage_6_acceptance.json) | 1,046 |
| [eval/artifacts/Q8/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q8/stage_6_acceptance.json) | 1,482 |
| [eval/artifacts/Q9/stage_6_acceptance.json](file:///d:/DocRag/eval/artifacts/Q9/stage_6_acceptance.json) | 1,501 |
| [eval/claims_summary.json](file:///d:/DocRag/eval/claims_summary.json) | 15,807 |
| [eval/dataset/ai_papers.json](file:///d:/DocRag/eval/dataset/ai_papers.json) | 9,044 |
| [eval/experiments/ablation_ast.yaml](file:///d:/DocRag/eval/experiments/ablation_ast.yaml) | 571 |
| [eval/experiments/ablation_kg.yaml](file:///d:/DocRag/eval/experiments/ablation_kg.yaml) | 624 |
| [eval/experiments/ablation_routing.yaml](file:///d:/DocRag/eval/experiments/ablation_routing.yaml) | 618 |
| [eval/experiments/embedding_ablation.yaml](file:///d:/DocRag/eval/experiments/embedding_ablation.yaml) | 701 |
| [eval/experiments/iteration1.yaml](file:///d:/DocRag/eval/experiments/iteration1.yaml) | 399 |
| [eval/experiments/main_comparison.yaml](file:///d:/DocRag/eval/experiments/main_comparison.yaml) | 1,490 |
| [eval/qdrant_storage/.lock](file:///d:/DocRag/eval/qdrant_storage/.lock) | 13 |
| [eval/qdrant_storage/collection/chunks/storage.sqlite](file:///d:/DocRag/eval/qdrant_storage/collection/chunks/storage.sqlite) | 12,288 |
| [eval/qdrant_storage/meta.json](file:///d:/DocRag/eval/qdrant_storage/meta.json) | 506 |
| [eval/results/.gitkeep](file:///d:/DocRag/eval/results/.gitkeep) | 0 |
| [eval/results/20260719_175325/run_results.json](file:///d:/DocRag/eval/results/20260719_175325/run_results.json) | 1,129 |
| [eval/results/20260719_175549/run_results.json](file:///d:/DocRag/eval/results/20260719_175549/run_results.json) | 14,004 |
| [eval/results/20260720_024620/run_results.json](file:///d:/DocRag/eval/results/20260720_024620/run_results.json) | 17,999 |
| [eval/results/20260720_025730/run_results.json](file:///d:/DocRag/eval/results/20260720_025730/run_results.json) | 17,994 |
| [eval/results/20260720_025857/run_results.json](file:///d:/DocRag/eval/results/20260720_025857/run_results.json) | 18,573 |
| [eval/results/20260720_030011/run_results.json](file:///d:/DocRag/eval/results/20260720_030011/run_results.json) | 19,639 |
| [eval/results/20260720_030147/run_results.json](file:///d:/DocRag/eval/results/20260720_030147/run_results.json) | 4 |
| [eval/results/20260720_030302/run_results.json](file:///d:/DocRag/eval/results/20260720_030302/run_results.json) | 4 |
| [eval/results/20260720_030529/run_results.json](file:///d:/DocRag/eval/results/20260720_030529/run_results.json) | 19,646 |
| [eval/results/20260720_031558/run_results.json](file:///d:/DocRag/eval/results/20260720_031558/run_results.json) | 19,646 |
| [eval/results/20260720_031658/run_results.json](file:///d:/DocRag/eval/results/20260720_031658/run_results.json) | 10,896 |
| [eval/results/20260720_031759/run_results.json](file:///d:/DocRag/eval/results/20260720_031759/run_results.json) | 10,896 |
| [eval/results/20260720_031924/run_results.json](file:///d:/DocRag/eval/results/20260720_031924/run_results.json) | 10,896 |
| [eval/results/20260720_032337/run_results.json](file:///d:/DocRag/eval/results/20260720_032337/run_results.json) | 11,796 |
| [eval/results/20260720_033222/run_results.json](file:///d:/DocRag/eval/results/20260720_033222/run_results.json) | 11,799 |
| [eval/results/20260720_033557/run_results.json](file:///d:/DocRag/eval/results/20260720_033557/run_results.json) | 11,796 |
| [eval/results/20260720_033738/run_results.json](file:///d:/DocRag/eval/results/20260720_033738/run_results.json) | 11,799 |
| [eval/results/20260720_035823/run_results.json](file:///d:/DocRag/eval/results/20260720_035823/run_results.json) | 877 |
| [eval/results/20260720_040150/run_results.json](file:///d:/DocRag/eval/results/20260720_040150/run_results.json) | 11,797 |
| [eval/results/20260721_123119/run_results.json](file:///d:/DocRag/eval/results/20260721_123119/run_results.json) | 11,801 |
| [eval/results/20260722_023541/run_results.json](file:///d:/DocRag/eval/results/20260722_023541/run_results.json) | 20,883 |
| [eval/results/comprehensive/results.json](file:///d:/DocRag/eval/results/comprehensive/results.json) | 452,062 |
| [eval/results/diagnosis.json](file:///d:/DocRag/eval/results/diagnosis.json) | 11,219 |
| [eval/results/experiment_20260720_185529_edc42be3/environment/packages.json](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/environment/packages.json) | 10,381 |
| [eval/results/experiment_20260720_185529_edc42be3/environment/seeds.json](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/environment/seeds.json) | 150 |
| [eval/results/experiment_20260720_185529_edc42be3/environment/system_info.json](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/environment/system_info.json) | 712 |
| [eval/results/experiment_20260720_185529_edc42be3/experiment_logs/config_used.yaml](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/experiment_logs/config_used.yaml) | 1,500 |
| [eval/results/experiment_20260720_185529_edc42be3/experiment_logs/run.log](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/experiment_logs/run.log) | 1,572 |
| [eval/results/experiment_20260720_185529_edc42be3/experiment_manifest.json](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/experiment_manifest.json) | 295 |
| [eval/results/experiment_20260720_185529_edc42be3/manifest.json](file:///d:/DocRag/eval/results/experiment_20260720_185529_edc42be3/manifest.json) | 3,902 |
| [eval/results/final_context_analysis.json](file:///d:/DocRag/eval/results/final_context_analysis.json) | 17,938 |
| [eval/results/iteration1_20260719_034710/checksums.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/checksums.json) | 96 |
| [eval/results/iteration1_20260719_034710/environment/packages.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/environment/packages.json) | 10,381 |
| [eval/results/iteration1_20260719_034710/environment/seeds.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/environment/seeds.json) | 150 |
| [eval/results/iteration1_20260719_034710/environment/system_info.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/environment/system_info.json) | 712 |
| [eval/results/iteration1_20260719_034710/error_analysis/failure_categories.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/error_analysis/failure_categories.json) | 691 |
| [eval/results/iteration1_20260719_034710/error_analysis/failures.jsonl](file:///d:/DocRag/eval/results/iteration1_20260719_034710/error_analysis/failures.jsonl) | 105,460 |
| [eval/results/iteration1_20260719_034710/experiment_logs/config_used.yaml](file:///d:/DocRag/eval/results/iteration1_20260719_034710/experiment_logs/config_used.yaml) | 423 |
| [eval/results/iteration1_20260719_034710/experiment_logs/run.log](file:///d:/DocRag/eval/results/iteration1_20260719_034710/experiment_logs/run.log) | 1,135 |
| [eval/results/iteration1_20260719_034710/figures/latency_boxplot.pdf](file:///d:/DocRag/eval/results/iteration1_20260719_034710/figures/latency_boxplot.pdf) | 16,614 |
| [eval/results/iteration1_20260719_034710/figures/latency_boxplot.png](file:///d:/DocRag/eval/results/iteration1_20260719_034710/figures/latency_boxplot.png) | 26,266 |
| [eval/results/iteration1_20260719_034710/figures/recall_at_k_curve.pdf](file:///d:/DocRag/eval/results/iteration1_20260719_034710/figures/recall_at_k_curve.pdf) | 15,992 |
| [eval/results/iteration1_20260719_034710/figures/recall_at_k_curve.png](file:///d:/DocRag/eval/results/iteration1_20260719_034710/figures/recall_at_k_curve.png) | 24,091 |
| [eval/results/iteration1_20260719_034710/figures/system_comparison.pdf](file:///d:/DocRag/eval/results/iteration1_20260719_034710/figures/system_comparison.pdf) | 15,959 |
| [eval/results/iteration1_20260719_034710/figures/system_comparison.png](file:///d:/DocRag/eval/results/iteration1_20260719_034710/figures/system_comparison.png) | 28,072 |
| [eval/results/iteration1_20260719_034710/integrity_report.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/integrity_report.json) | 762 |
| [eval/results/iteration1_20260719_034710/manifest.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/manifest.json) | 2,361 |
| [eval/results/iteration1_20260719_034710/metrics/comparison.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/metrics/comparison.json) | 2,120 |
| [eval/results/iteration1_20260719_034710/metrics/per_system.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/metrics/per_system.json) | 893 |
| [eval/results/iteration1_20260719_034710/metrics/statistical_tests.json](file:///d:/DocRag/eval/results/iteration1_20260719_034710/metrics/statistical_tests.json) | 950 |
| [eval/results/iteration1_20260719_034710/raw/CodeGraphRAG.jsonl](file:///d:/DocRag/eval/results/iteration1_20260719_034710/raw/CodeGraphRAG.jsonl) | 1,281,685 |
| [eval/results/iteration1_20260719_034710/tables/main_results.csv](file:///d:/DocRag/eval/results/iteration1_20260719_034710/tables/main_results.csv) | 154 |
| [eval/results/iteration1_20260719_034710/tables/main_results.tex](file:///d:/DocRag/eval/results/iteration1_20260719_034710/tables/main_results.tex) | 533 |
| [eval/results/iteration1_20260719_043233/checksums.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/checksums.json) | 96 |
| [eval/results/iteration1_20260719_043233/environment/packages.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/environment/packages.json) | 10,381 |
| [eval/results/iteration1_20260719_043233/environment/seeds.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/environment/seeds.json) | 150 |
| [eval/results/iteration1_20260719_043233/environment/system_info.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/environment/system_info.json) | 712 |
| [eval/results/iteration1_20260719_043233/error_analysis/failure_categories.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/error_analysis/failure_categories.json) | 404 |
| [eval/results/iteration1_20260719_043233/error_analysis/failures.jsonl](file:///d:/DocRag/eval/results/iteration1_20260719_043233/error_analysis/failures.jsonl) | 3,804 |
| [eval/results/iteration1_20260719_043233/experiment_logs/config_used.yaml](file:///d:/DocRag/eval/results/iteration1_20260719_043233/experiment_logs/config_used.yaml) | 433 |
| [eval/results/iteration1_20260719_043233/experiment_logs/run.log](file:///d:/DocRag/eval/results/iteration1_20260719_043233/experiment_logs/run.log) | 1,345 |
| [eval/results/iteration1_20260719_043233/figures/latency_boxplot.pdf](file:///d:/DocRag/eval/results/iteration1_20260719_043233/figures/latency_boxplot.pdf) | 16,839 |
| [eval/results/iteration1_20260719_043233/figures/latency_boxplot.png](file:///d:/DocRag/eval/results/iteration1_20260719_043233/figures/latency_boxplot.png) | 23,440 |
| [eval/results/iteration1_20260719_043233/figures/recall_at_k_curve.pdf](file:///d:/DocRag/eval/results/iteration1_20260719_043233/figures/recall_at_k_curve.pdf) | 15,992 |
| [eval/results/iteration1_20260719_043233/figures/recall_at_k_curve.png](file:///d:/DocRag/eval/results/iteration1_20260719_043233/figures/recall_at_k_curve.png) | 24,091 |
| [eval/results/iteration1_20260719_043233/figures/system_comparison.pdf](file:///d:/DocRag/eval/results/iteration1_20260719_043233/figures/system_comparison.pdf) | 15,959 |
| [eval/results/iteration1_20260719_043233/figures/system_comparison.png](file:///d:/DocRag/eval/results/iteration1_20260719_043233/figures/system_comparison.png) | 28,066 |
| [eval/results/iteration1_20260719_043233/integrity_report.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/integrity_report.json) | 687 |
| [eval/results/iteration1_20260719_043233/manifest.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/manifest.json) | 2,378 |
| [eval/results/iteration1_20260719_043233/metrics/comparison.json](file:///d:/DocRag/eval/results/iteration1_20260719_043233/metrics/comparison.json) | 2,102 |
| *... and 10 additional files* | |

