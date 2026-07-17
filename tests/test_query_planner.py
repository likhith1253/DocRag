import json
import os
from datetime import datetime, timezone

from agents.query_planner import plan_structural_query
from storage.registry import Repository, RepositoryRegistry, RepoStatus


def test_structural_query_planner_answers_without_vector_search():
    registry_path = "./test_registry_query_planner.json"
    metadata_dir = "./metadata_storage"
    graph_dir = "./kg_storage"
    os.makedirs(metadata_dir, exist_ok=True)
    os.makedirs(graph_dir, exist_ok=True)

    registry = RepositoryRegistry(storage_path=registry_path)
    registry.repositories.clear()
    repo = Repository(
        repo_id="repo-planner",
        name="planner-repo",
        branch="main",
        language="python",
        framework="fastapi",
        vector_collection="unused",
        knowledge_graph="graph_repo_planner",
        metadata="metadata_repo_planner",
        embedding_model="auto",
        parser_version="1.0",
        status=RepoStatus.INDEXING_TIER1,
        indexed_at=datetime.now(timezone.utc),
    )
    registry.register(repo)

    metadata_path = os.path.join(metadata_dir, "metadata_repo_planner.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "h1": {
                    "file": "src/service.py",
                    "function": "fetch_user",
                    "class": None,
                    "lines": "10-24",
                }
            },
            f,
            indent=2,
        )

    graph_path = os.path.join(graph_dir, "graph_repo_planner.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "directed": True,
                "multigraph": False,
                "graph": {},
                "nodes": [
                    {"id": "fetch_user", "type": "Function"},
                    {"id": "api.get_user", "type": "Function"},
                ],
                "links": [
                    {"source": "api.get_user", "target": "fetch_user", "type": "Calls"},
                ],
            },
            f,
            indent=2,
        )

    try:
        result = plan_structural_query(
            "Where is fetch_user defined?",
            repo_id="repo-planner",
            registry=registry,
        )
        assert result is not None
        assert "src/service.py" in result["answer"]

        callers = plan_structural_query(
            "Who calls fetch_user?",
            repo_id="repo-planner",
            registry=registry,
        )
        assert callers is not None
        assert "api.get_user" in callers["answer"]
    finally:
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        if os.path.exists(graph_path):
            os.remove(graph_path)
        if os.path.exists(registry_path):
            os.remove(registry_path)
