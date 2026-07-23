import os
import sqlite3
import json
import numpy as np
from typing import Dict, Any, Optional, Tuple
import threading
from storage.vector_store import _get_encoder, _get_config

_thread_local = threading.local()

class SemanticCache:
    def __init__(self, db_path: str = "./semantic_cache.db"):
        self.db_path = db_path
        self._init_db()
        
        config = _get_config()
        self.embedding_model_name = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.device = config.get("device", "auto")
        self.encoder = _get_encoder(self.embedding_model_name, self.device)
        self.similarity_threshold = 0.95

    def _get_conn(self):
        if not hasattr(_thread_local, "conn"):
            _thread_local.conn = sqlite3.connect(self.db_path)
        return _thread_local.conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id TEXT NOT NULL,
                query TEXT NOT NULL,
                embedding TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Index for fast repo_id lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repo_id ON cache(repo_id)')
        conn.commit()
        # Do not close, it is cached

    def clear(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cache")
        conn.commit()
        cursor.execute("VACUUM")
        conn.commit()

    def get_cached_answer(self, query: str, repo_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT query, embedding, answer, sources FROM cache WHERE repo_id = ?", (repo_id,))
        rows = cursor.fetchall()
        
        if not rows:
            return None
            
        if "e5" in self.embedding_model_name.lower():
            query_for_encode = f"query: {query}"
        else:
            query_for_encode = query
            
        query_vector = self.encoder.encode(query_for_encode, show_progress_bar=False)
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return None
        query_vector = query_vector / query_norm
        
        best_score = -1.0
        best_match = None
        
        for row in rows:
            cached_query, emb_str, answer, sources_str = row
            # Exact match short-circuit
            if query.strip().lower() == cached_query.strip().lower():
                return {
                    "answer": answer,
                    "sources": json.loads(sources_str),
                    "cached": True
                }
                
            cached_vector = np.array(json.loads(emb_str))
            # norm is already 1 if we normalized before saving, but let's be safe
            norm = np.linalg.norm(cached_vector)
            if norm > 0:
                cached_vector = cached_vector / norm
                score = np.dot(query_vector, cached_vector)
                if score > best_score:
                    best_score = score
                    best_match = (answer, sources_str)
                    
        if best_score >= self.similarity_threshold and best_match:
            return {
                "answer": best_match[0],
                "sources": json.loads(best_match[1]),
                "cached": True,
                "similarity": float(best_score)
            }
            
        return None

    def set_cached_answer(self, query: str, repo_id: str, answer: str, sources: list):
        if "e5" in self.embedding_model_name.lower():
            query_for_encode = f"query: {query}"
        else:
            query_for_encode = query
            
        query_vector = self.encoder.encode(query_for_encode, show_progress_bar=False).tolist()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cache (repo_id, query, embedding, answer, sources) VALUES (?, ?, ?, ?, ?)",
            (repo_id, query, json.dumps(query_vector), answer, json.dumps(sources))
        )
        conn.commit()

    def close(self):
        conn = getattr(_thread_local, "conn", None)
        if conn is not None:
            conn.close()
            delattr(_thread_local, "conn")


class EmbeddingCache:
    """
    Persistent SQLite-based cache for dense embeddings to avoid re-encoding on CPU.
    """
    def __init__(self, db_path: str = "./embedding_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        if not hasattr(_thread_local, "emb_conn"):
            _thread_local.emb_conn = sqlite3.connect(self.db_path)
        return _thread_local.emb_conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emb_cache (
                chunk_hash TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                embedding_json TEXT NOT NULL
            )
        ''')
        conn.commit()

    def get_embeddings(self, chunk_hashes: list[str], model_name: str) -> dict[str, list[float]]:
        if not chunk_hashes:
            return {}
            
        conn = self._get_conn()
        cursor = conn.cursor()
        results = {}
        batch_size = 900
        for i in range(0, len(chunk_hashes), batch_size):
            batch = chunk_hashes[i:i + batch_size]
            placeholders = ",".join(["?"] * len(batch))
            cursor.execute(
                f"SELECT chunk_hash, embedding_json FROM emb_cache WHERE model_name = ? AND chunk_hash IN ({placeholders})",
                [model_name] + batch
            )
            rows = cursor.fetchall()
            for row in rows:
                results[row[0]] = json.loads(row[1])
        return results

    def set_embeddings(self, hash_vector_pairs: list[tuple[str, list[float]]], model_name: str):
        if not hash_vector_pairs:
            return
            
        conn = self._get_conn()
        cursor = conn.cursor()
        rows = [
            (chunk_hash, model_name, json.dumps(vector))
            for chunk_hash, vector in hash_vector_pairs
        ]
        cursor.executemany(
            "INSERT OR REPLACE INTO emb_cache (chunk_hash, model_name, embedding_json) VALUES (?, ?, ?)",
            rows
        )
        conn.commit()

    def clear(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emb_cache")
        conn.commit()
        cursor.execute("VACUUM")
        conn.commit()

    def close(self):
        conn = getattr(_thread_local, "emb_conn", None)
        if conn is not None:
            conn.close()
            delattr(_thread_local, "emb_conn")

