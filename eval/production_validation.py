"""
Production Validation Script

Internal engineering tool to verify the system works correctly for real developers.
NOT a formal research benchmark - this is for sanity checking and bug detection.
"""
import os
import sys
import time
import json
import psutil
from typing import List, Dict, Any

_PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)

from storage.vector_store import VectorStoreManager
from storage.knowledge_graph import KnowledgeGraphManager
from storage.registry import RepositoryRegistry, Repository
from agents.orchestrator import Orchestrator
from agents.query_planner import plan_structural_query

# Add benchmark to path for evidence collector
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "benchmark"))
from evidence_collector import EvidenceCollector
from hallucination_checker import HallucinationChecker
from question_generator import QuestionGenerator


class ProductionValidator:
    """Validate production readiness using manual test questions."""
    
    def __init__(self, repo_path: str, repo_id: str):
        self.repo_path = repo_path
        self.repo_id = repo_id
        self.results = []
        self.process = psutil.Process(os.getpid())
        
        # Initialize evidence collector
        self.evidence = EvidenceCollector(
            benchmark_name=f"production_validation_{repo_id}",
            output_dir=os.path.join(_PROJECT_ROOT, "benchmark_results")
        )
        self.evidence.set_config({
            "repo_id": repo_id,
            "repo_path": repo_path,
            "validation_type": "production"
        })
        
        # Initialize hallucination checker
        self.hallucination_checker = HallucinationChecker(repo_id)
        
        # Initialize question generator
        self.question_generator = QuestionGenerator(repo_id)
        
    def ingest_repository(self) -> Dict[str, Any]:
        """Ingest repository using proper ingestion pipeline and measure performance."""
        print(f"\n=== Ingesting {self.repo_id} ===")
        
        # Start measurement
        ingest_id = self.evidence.start_measurement(
            name="ingest_repository",
            source="background_ingest_repository",
            repo=self.repo_id
        )
        
        # Memory baseline
        mem_before = self.process.memory_info().rss / (1024 * 1024)
        peak_mem = mem_before
        
        # Clear answer cache to force fresh retrieval
        cache_path = os.path.join(_PROJECT_ROOT, "semantic_cache.db")
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("  Cleared semantic cache")
            self.evidence.log_raw("cache_cleared", {"cache": "semantic_cache.db"})
        
        # Register repository first
        registry = RepositoryRegistry()
        from datetime import datetime, timezone
        from storage.registry import RepoStatus
        repo = Repository(
            repo_id=self.repo_id,
            name=self.repo_id,
            source_path=self.repo_path,
            branch="main",
            vector_collection=f"col_{self.repo_id}",
            knowledge_graph=f"{self.repo_id}_graph",
            metadata=f"{self.repo_id}_metadata",
            embedding_model="intfloat/e5-base-v2",
            parser_version="1.0",
            status=RepoStatus.READY,
            indexed_at=datetime.now(timezone.utc)
        )
        registry.register(repo)
        self.evidence.log_raw("repository_registered", {"repo_id": self.repo_id})
        
        # Use proper ingestion pipeline
        from ingestion.worker import background_ingest_repository
        
        t_start = time.perf_counter()
        
        background_ingest_repository(self.repo_id, self.repo_path, registry)
        
        # Track peak memory
        mem_after = self.process.memory_info().rss / (1024 * 1024)
        peak_mem = max(peak_mem, mem_after)
        
        duration = time.perf_counter() - t_start
        
        # Count chunks
        v_manager = VectorStoreManager(collection_name=f"col_{self.repo_id}")
        chunks = v_manager.get_all_chunks()
        
        # Count KG nodes and edges
        kg_manager = KnowledgeGraphManager()
        kg_manager.load_from_json(os.path.join(_PROJECT_ROOT, "kg_storage", f"{self.repo_id}_graph.json"))
        kg_nodes = kg_manager.graph.number_of_nodes()
        kg_edges = kg_manager.graph.number_of_edges()
        
        # Get Qdrant collection size
        qdrant_size = v_manager.collection_count if hasattr(v_manager, 'collection_count') else len(chunks)
        
        # Get metadata size
        metadata_path = os.path.join(_PROJECT_ROOT, "metadata_storage", f"{self.repo_id}_metadata.json")
        metadata_size_mb = os.path.getsize(metadata_path) / (1024 * 1024) if os.path.exists(metadata_path) else 0
        
        # Get KG size
        kg_path = os.path.join(_PROJECT_ROOT, "kg_storage", f"{self.repo_id}_graph.json")
        kg_size_mb = os.path.getsize(kg_path) / (1024 * 1024) if os.path.exists(kg_path) else 0
        
        print(f"  Files processed: {len(chunks)} chunks")
        print(f"  Indexing time: {duration:.2f}s")
        print(f"  Memory delta: {mem_after - mem_before:.1f} MB")
        print(f"  Peak memory: {peak_mem:.1f} MB")
        
        result = {
            "chunks_indexed": len(chunks),
            "indexing_time": duration,
            "memory_delta_mb": mem_after - mem_before,
            "peak_memory_mb": peak_mem,
            "kg_nodes": kg_nodes,
            "kg_edges": kg_edges,
            "qdrant_count": qdrant_size,
            "metadata_size_mb": metadata_size_mb,
            "kg_size_mb": kg_size_mb
        }
        
        # Update measurement with memory metrics
        for m in self.evidence.measurements:
            if m["measurement_id"] == ingest_id:
                m["memory_metrics"] = {
                    "rss_before_mb": mem_before,
                    "rss_after_mb": mem_after,
                    "peak_rss_mb": peak_mem,
                    "heap_delta_mb": mem_after - mem_before,
                    "graph_memory_mb": kg_size_mb,
                    "metadata_memory_mb": metadata_size_mb,
                    "qdrant_count": qdrant_size
                }
                break
        
        self.evidence.end_measurement(ingest_id, result)
        self.evidence.log_raw("ingestion_complete", result)
        
        return result
    
    def run_question(self, question: str, expected_type: str) -> Dict[str, Any]:
        """Run a single question and measure performance."""
        print(f"\n  Q: {question}")
        
        # Start measurement
        query_id = self.evidence.start_measurement(
            name="run_question",
            source="query_planner_orchestrator",
            repo=self.repo_id
        )
        
        t_start = time.perf_counter()
        mem_before = self.process.memory_info().rss / (1024 * 1024)
        
        self.evidence.log_raw("question_started", {"question": question, "expected_type": expected_type})
        
        # Latency breakdown
        latency_breakdown = {
            "planner_ms": 0,
            "metadata_ms": 0,
            "graph_ms": 0,
            "vector_ms": 0,
            "reranker_ms": 0,
            "llm_ms": 0,
            "total_ms": 0
        }
        
        try:
            # Try structural query first
            from storage.registry import RepositoryRegistry
            
            t_planner_start = time.perf_counter()
            structural_result = plan_structural_query(
                question, 
                repo_id=self.repo_id,
                registry=RepositoryRegistry()
            )
            t_planner_end = time.perf_counter()
            latency_breakdown["planner_ms"] = (t_planner_end - t_planner_start) * 1000
            
            if structural_result and structural_result.get("answer") and "No definitions found" not in structural_result["answer"]:
                answer = structural_result["answer"]
                used_vector_search = False
                strategy = structural_result.get("strategy", "unknown")
                print(f"  A (structural): {answer[:100]}...")
                self.evidence.log_raw("structural_answer", {
                    "strategy": strategy,
                    "answer_preview": answer[:100],
                    "used_vector_search": False
                })
                duration = time.perf_counter() - t_start
                mem_after = self.process.memory_info().rss / (1024 * 1024)
                latency_breakdown["total_ms"] = duration * 1000
            else:
                # Fall back to full retrieval
                orchestrator = Orchestrator()
                response = orchestrator.answer(question, repo_id=self.repo_id)
                
                # Use the detailed breakdown from orchestrator
                if "latency_breakdown" in response:
                    for key in latency_breakdown:
                        if key in response["latency_breakdown"]:
                            latency_breakdown[key] = response["latency_breakdown"][key]
                
                answer = response["answer"]
                sources = response.get("sources", [])
                used_vector_search = True
                strategy = response.get("agent", "unknown")
                print(f"  A (full): {answer[:100]}...")
                if sources:
                    print(f"  Sources: {len(sources)} files")
                self.evidence.log_raw("full_answer", {
                    "strategy": strategy,
                    "answer_preview": answer[:100],
                    "used_vector_search": True,
                    "sources_count": len(sources)
                })
                
                duration = time.perf_counter() - t_start
                mem_after = self.process.memory_info().rss / (1024 * 1024)
                
            result = {
                "question": question,
                "expected_type": expected_type,
                "answer": answer,
                "latency_ms": duration * 1000,
                "memory_delta_mb": mem_after - mem_before,
                "used_vector_search": used_vector_search,
                "strategy": strategy,
                "latency_breakdown": latency_breakdown,
                "success": True
            }
            
            # Validate expected routing
            if expected_type == "structural" and used_vector_search:
                print(f"  ⚠️ WARNING: Structural question used vector search")
                result["routing_correct"] = False
            elif expected_type == "semantic" and not used_vector_search:
                print(f"  ⚠️ WARNING: Semantic question didn't use vector search")
                result["routing_correct"] = False
            else:
                result["routing_correct"] = True
            
            print(f"  Latency: {duration*1000:.1f}ms")
            
            # Verify answer for hallucinations
            hallucination_check = self.hallucination_checker.verify_answer(answer)
            result["hallucination_check"] = hallucination_check
            
            if hallucination_check["status"] == "FAIL":
                print(f"  ⚠️ WARNING: Potential hallucinations detected: {hallucination_check['hallucination_count']}")
            
            # Update measurement with latency breakdown
            for m in self.evidence.measurements:
                if m["measurement_id"] == query_id:
                    m["latency_breakdown"] = latency_breakdown
                    m["hallucination_check"] = hallucination_check
                    break
            
            self.evidence.end_measurement(query_id, result)
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            result = {
                "question": question,
                "expected_type": expected_type,
                "error": str(e),
                "success": False
            }
            self.evidence.fail_measurement(query_id, str(e))
        
        return result
    
    def validate_repository(self, questions: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Run full validation on repository."""
        print(f"\n{'='*60}")
        print(f"PRODUCTION VALIDATION: {self.repo_id}")
        print(f"{'='*60}")
        
        # Auto-generate questions if not provided
        if questions is None:
            print(f"\n=== Auto-generating questions from metadata ===")
            questions = self.question_generator.generate_dataset(
                definition_count=6,
                callers_count=2,
                imports_count=2
            )
            print(f"  Generated {len(questions)} questions")
            
            # Save generated dataset
            dataset_path = os.path.join(_PROJECT_ROOT, "benchmark_results", f"{self.repo_id}_questions.json")
            self.question_generator.save_dataset(dataset_path)
            print(f"  Dataset saved to {dataset_path}")
        
        # Ingest
        indexing_stats = self.ingest_repository()
        
        # Run questions
        print(f"\n=== Running Questions ===")
        question_results = []
        for q in questions:
            result = self.run_question(q["question"], q["type"])
            question_results.append(result)
        
        # Summary
        print(f"\n=== Validation Summary ===")
        successful = sum(1 for r in question_results if r.get("success"))
        total = len(question_results)
        print(f"  Success rate: {successful}/{total} ({successful/total*100:.1f}%)")
        
        latencies = [r["latency_ms"] for r in question_results if r.get("success")]
        if successful > 0:
            print(f"  Avg latency: {sum(latencies)/len(latencies):.1f}ms")
            print(f"  P95 latency: {sorted(latencies)[int(len(latencies)*0.95)]:.1f}ms")
        
        routing_correct = sum(1 for r in question_results if r.get("routing_correct"))
        print(f"  Routing correct: {routing_correct}/{total}")
        
        hallucination_pass = sum(1 for r in question_results if r.get("hallucination_check", {}).get("status") == "PASS")
        print(f"  Hallucination check: {hallucination_pass}/{total}")
        
        result = {
            "repo_id": self.repo_id,
            "indexing_stats": indexing_stats,
            "question_results": question_results,
            "summary": {
                "success_rate": successful / total if total > 0 else 0,
                "avg_latency_ms": sum(latencies)/len(latencies) if latencies else 0,
                "p95_latency_ms": sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0,
                "routing_correct_rate": routing_correct / total if total > 0 else 0,
                "hallucination_pass_rate": hallucination_pass / total if total > 0 else 0
            }
        }
        
        # Save evidence files
        evidence_paths = self.evidence.save()
        print(f"\n✅ Evidence saved:")
        for name, path in evidence_paths.items():
            print(f"  {name}: {path}")
        
        return result


def load_manual_questions() -> Dict[str, List[Dict[str, str]]]:
    """Load manual test questions from markdown file."""
    
    # Parse the markdown file to extract questions
    # For now, return hardcoded structure based on the file we created
    return {
        "Requests": [
            {"question": "Where is Session defined?", "type": "structural"},
            {"question": "Who calls Session?", "type": "structural"},
            {"question": "What imports requests?", "type": "structural"},
            {"question": "Where is HTTPAdapter defined?", "type": "structural"},
            {"question": "Where is Request defined?", "type": "structural"},
            {"question": "Where is Response defined?", "type": "structural"},
        ],
        "CodeGraphRAG": [
            {"question": "Where is RepositoryRegistry defined?", "type": "structural"},
            {"question": "Who calls RepositoryRegistry?", "type": "structural"},
            {"question": "What imports vector_store?", "type": "structural"},
            {"question": "Where is VectorStoreManager defined?", "type": "structural"},
            {"question": "Where is Orchestrator defined?", "type": "structural"},
            {"question": "Where is QueryPlanner defined?", "type": "structural"},
        ],
        "Pydantic": [
            {"question": "Where is BaseModel defined?", "type": "structural"},
            {"question": "Where is Field defined?", "type": "structural"},
            {"question": "Where is validator defined?", "type": "structural"},
            {"question": "Where is ValidationError defined?", "type": "structural"},
            {"question": "Where is ConfigDict defined?", "type": "structural"},
            {"question": "Where is RootModel defined?", "type": "structural"},
        ],
        "smalltest": [
            {"question": "Where is main defined?", "type": "structural"},
            {"question": "Where is process_data defined?", "type": "structural"},
            {"question": "Who calls process_data?", "type": "structural"},
        ]
    }


def main():
    """Run production validation on test repositories."""
    # Clear semantic cache before validation
    cache_path = os.path.join(_PROJECT_ROOT, "semantic_cache.db")
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("Cleared semantic cache")
    
    # Get manual questions
    all_manual_questions = load_manual_questions()
    
    # Validate smalltest with manual questions (small repo, fast ingest)
    smalltest_path = os.path.join(_PROJECT_ROOT, "test_repos", "smalltest")
    if os.path.exists(smalltest_path):
        validator = ProductionValidator(smalltest_path, "smalltest")
        smalltest_results = validator.validate_repository(questions=all_manual_questions["smalltest"])
        
        # Save results
        results_path = os.path.join(_PROJECT_ROOT, "eval", "production_validation_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({"smalltest": smalltest_results}, f, indent=2)
        
        print(f"\n✅ Results saved to {results_path}")
    else:
        print(f"❌ Pydantic repository not found at {pydantic_path}")


if __name__ == "__main__":
    main()
