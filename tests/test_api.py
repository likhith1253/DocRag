import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch('api.main.load_repository')
    @patch('api.main.chunk_file')
    @patch('api.main.VectorStoreManager')
    @patch('api.main.KnowledgeGraphManager')
    @patch('api.main.MetadataStoreManager')
    def test_upload(self, mock_meta_mgr, mock_kg_mgr, mock_vec_mgr, mock_chunk_file, mock_load_repository):
        mock_load_repository.return_value = [
            {
                "file_path": "main.py",
                "content": "print('hello')",
                "repo_name": "test_repo",
                "branch": "main"
            }
        ]
        mock_chunk_file.return_value = [
            {
                "content": "print('hello')",
                "metadata": {
                    "hash": "h1",
                    "file": "main.py"
                }
            }
        ]
        
        response = self.client.post("/upload", json={"path": "d:/Document_RAG"})
        if response.status_code != 200:
            print("UPLOAD ERROR DETAIL:", response.json())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["repository"], "Document_RAG")
        self.assertEqual(data["files_processed"], 1)

    @patch('api.main.orchestrator.answer')
    def test_query(self, mock_answer):
        mock_answer.return_value = "The project uses tree-sitter."
        
        response = self.client.post("/query", json={"question": "What parser does it use?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "The project uses tree-sitter.")

if __name__ == "__main__":
    unittest.main()
