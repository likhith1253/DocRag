import os
import sys
import uuid
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app
from storage.registry import RepositoryRegistry, Repository, RepoStatus
from storage.vector_store import VectorStoreManager
from storage.knowledge_graph import KnowledgeGraphManager
from storage.metadata_store import MetadataStoreManager
from llm.ollama_backend import generate
from retrieval.cross_encoder_rerank import rerank_cross_encoder

client = TestClient(app)

def test_singletons():
    # Insert a dummy repo
    registry = RepositoryRegistry()
    repo_id = str(uuid.uuid4())
    repo = Repository(
        repo_id=repo_id,
        name="test",
        branch="main",
        language="python",
        framework="none",
        vector_collection=f"collection_{repo_id}",
        knowledge_graph=f"graph_{repo_id}",
        metadata=f"metadata_{repo_id}",
        embedding_model="auto",
        parser_version="1.0",
        status=RepoStatus.READY,
        indexed_at=None
    )
    registry.register(repo)
    
    # We will trace how many times KnowledgeGraphManager.__init__ is called
    kg_inits = []
    original_kg_init = KnowledgeGraphManager.__init__
    def mock_kg_init(self, *args, **kwargs):
        kg_inits.append(id(self))
        original_kg_init(self, *args, **kwargs)
        
    # Trace VectorStoreManager.__init__
    vsm_inits = []
    original_vsm_init = VectorStoreManager.__init__
    def mock_vsm_init(self, *args, **kwargs):
        vsm_inits.append(id(self))
        original_vsm_init(self, *args, **kwargs)
        
    KnowledgeGraphManager.__init__ = mock_kg_init
    VectorStoreManager.__init__ = mock_vsm_init

    # Make multiple queries
    for i in range(3):
        res = client.post("/query", json={"question": f"test query {i}", "repo_id": repo_id})
        print(f"Query {i} response: {res.json()}")
        
    # Restore
    KnowledgeGraphManager.__init__ = original_kg_init
    VectorStoreManager.__init__ = original_vsm_init

    print(f"VectorStoreManager instantiations: {len(vsm_inits)}")
    print(f"VectorStoreManager _clients keys: {len(VectorStoreManager._clients)}")
    print(f"KnowledgeGraphManager instantiations: {len(kg_inits)}")

if __name__ == "__main__":
    test_singletons()
