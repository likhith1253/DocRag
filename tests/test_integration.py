import os
import unittest
from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file

class TestIntegration(unittest.TestCase):
    def test_end_to_end_pipeline(self):
        # We will point the loader to the current workspace root directory.
        # It has mixed files (Python, YAML, Markdown, JSON, etc.) and is large.
        workspace_path = "d:/Document_RAG"
        
        all_chunks = []
        files_processed = 0
        
        # Iterate over files in the workspace (this will stream them one by one)
        for file_info in load_repository(workspace_path):
            file_path = file_info["file_path"]
            
            # Skip virtualenv files to keep test run duration reasonable, 
            # but allow testing on all project-specific files.
            if file_path.replace("\\", "/").startswith(".venv/"):
                continue
                
            content = file_info["content"]
            repo_name = file_info["repo_name"]
            branch = file_info["branch"]
            
            # 1. Detect language
            lang = detect_language(file_path)
            
            # 2. Chunk file (this internally parses using parser.py)
            chunks = chunk_file(file_path, content, repo_name, branch, lang)
            all_chunks.extend(chunks)
            files_processed += 1
            
        print(f"\nProcessed {files_processed} files, generated {len(all_chunks)} chunks.")
        
        # Verify Phase 1 DoD:
        # Every chunk must contain the required metadata keys: 
        # repository, branch, language, file, class, function, lines, hash, timestamp, and dependencies
        required_keys = {
            "repository", "branch", "language", "file", "class", 
            "function", "lines", "hash", "timestamp", "dependencies"
        }
        
        self.assertTrue(len(all_chunks) > 0, "No chunks were produced!")
        
        for chunk in all_chunks:
            self.assertIn("content", chunk)
            self.assertIn("metadata", chunk)
            
            meta = chunk["metadata"]
            for key in required_keys:
                self.assertIn(key, meta, f"Metadata key '{key}' is missing in chunk for file: {meta.get('file')}")
                
            # Verify lines format is '{start}-{end}'
            lines_val = meta["lines"]
            self.assertTrue(re.match(r"^\d+-\d+$", lines_val), f"Lines metadata '{lines_val}' is invalid format")
            
            # Verify hash is a valid 64-character hex string
            self.assertEqual(len(meta["hash"]), 64)
            
            # Verify timestamp is not empty
            self.assertTrue(meta["timestamp"])

import re
if __name__ == "__main__":
    unittest.main()
