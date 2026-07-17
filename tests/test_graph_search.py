import unittest
from storage.knowledge_graph import KnowledgeGraphManager
from retrieval.graph_search import expand_by_graph

class TestGraphSearch(unittest.TestCase):
    def test_expand_by_graph(self):
        # 1. Create a dummy knowledge graph
        kg = KnowledgeGraphManager()
        # class A uses file B, class A inherits from class C, function D calls function E
        kg.graph.add_node("A", type="Class")
        kg.graph.add_node("B", type="File")
        kg.graph.add_node("C", type="Class")
        kg.graph.add_node("D", type="Function")
        kg.graph.add_node("E", type="Function")
        
        kg.graph.add_edge("A", "B", type="Uses")
        kg.graph.add_edge("A", "C", type="Inherits")
        kg.graph.add_edge("D", "E", type="Calls")
        
        # Chunks in the store
        all_chunks = [
            {
                "content": "class A",
                "metadata": {"hash": "h1", "class": "A", "file": "B", "function": None}
            },
            {
                "content": "class C",
                "metadata": {"hash": "h2", "class": "C", "file": "X.py", "function": None}
            },
            {
                "content": "function D",
                "metadata": {"hash": "h3", "class": None, "file": "Y.py", "function": "D"}
            },
            {
                "content": "function E",
                "metadata": {"hash": "h4", "class": None, "file": "Z.py", "function": "E"}
            }
        ]
        
        # Initially retrieved chunks: only h1 (class A)
        retrieved = [all_chunks[0]]
        
        # Expand
        expanded = expand_by_graph(retrieved, kg, all_chunks=all_chunks)
        
        # Since class A connects to C (Inherits), h2 (class C) should be added
        hashes = {c["metadata"]["hash"] for c in expanded}
        self.assertIn("h1", hashes)
        self.assertIn("h2", hashes)
        self.assertNotIn("h3", hashes)
        self.assertNotIn("h4", hashes)

if __name__ == "__main__":
    unittest.main()
