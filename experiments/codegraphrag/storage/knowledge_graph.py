import os
import json
import networkx as nx
from typing import List, Dict, Any

class KnowledgeGraphManager:
    _graphs = {}

    def __init__(self):
        self.graph = nx.DiGraph()
        self._current_path = None

    def build_from_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Build the Knowledge Graph from parser/chunker output.
        Nodes: Functions, Classes, Files, Modules
        Edges: Calls, Imports, Inherits, Uses, Creates, Reads, Writes
        """
        for chunk in chunks:
            meta = chunk["metadata"]
            file_path = meta.get("file")
            class_name = meta.get("class")
            func_name = meta.get("function")
            language = meta.get("language")
            
            # 1. Add nodes
            if file_path:
                self.graph.add_node(file_path, type="File", language=language, file=file_path)
                
            if class_name:
                self.graph.add_node(class_name, type="Class", file=file_path)
                # Link Class to File
                self.graph.add_edge(class_name, file_path, type="Uses")
                
            if func_name:
                full_func_name = f"{class_name}.{func_name}" if class_name else func_name
                self.graph.add_node(full_func_name, type="Function", file=file_path)
                # Link Function to File
                self.graph.add_edge(full_func_name, file_path, type="Uses")
                if class_name:
                    # Link Function to Class
                    self.graph.add_edge(full_func_name, class_name, type="Uses")
                    
            # 2. Add edges from dependencies
            deps = meta.get("dependencies", [])
            for dep in deps:
                target = dep.get("target")
                dep_type = dep.get("type") # imports, inherits, calls
                
                # Map to capitalized edge types matching the schema
                edge_type = dep_type.capitalize() if dep_type else "Uses"
                if edge_type not in ["Calls", "Imports", "Inherits", "Uses", "Creates", "Reads", "Writes"]:
                    edge_type = "Uses"
                    
                # Determine source node
                if func_name:
                    source = f"{class_name}.{func_name}" if class_name else func_name
                elif class_name:
                    source = class_name
                else:
                    source = file_path
                    
                if target:
                    if not self.graph.has_node(target):
                        if edge_type == "Imports":
                            self.graph.add_node(target, type="Module")
                        elif edge_type == "Inherits":
                            self.graph.add_node(target, type="Class")
                        else:
                            self.graph.add_node(target, type="Function")
                            
                    self.graph.add_edge(source, target, type=edge_type)

    def save_to_json(self, path: str):
        data = nx.readwrite.json_graph.node_link_data(self.graph, edges="links")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        KnowledgeGraphManager._graphs[path] = self.graph

    def load_from_json(self, path: str):
        if path in KnowledgeGraphManager._graphs:
            self.graph = KnowledgeGraphManager._graphs[path]
            self._current_path = path
            return

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.graph = nx.readwrite.json_graph.node_link_graph(data, edges="links")
            KnowledgeGraphManager._graphs[path] = self.graph
            self._current_path = path

    def prune_nodes(self, file_paths: List[str]):
        """
        Removes all nodes (and implicitly their edges) that belong to the given file paths.
        """
        if not file_paths:
            return
            
        nodes_to_remove = []
        for node, data in self.graph.nodes(data=True):
            if node in file_paths:
                nodes_to_remove.append(node)
            elif data.get("file") in file_paths:
                nodes_to_remove.append(node)
                
        for node in nodes_to_remove:
            self.graph.remove_node(node)
            
        # Update cache if bound to a path
        if self._current_path and self._current_path in KnowledgeGraphManager._graphs:
            KnowledgeGraphManager._graphs[self._current_path] = self.graph
