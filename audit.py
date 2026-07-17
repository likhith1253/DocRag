import ast
import os
import glob
from collections import defaultdict

def scan_files():
    base_dirs = ['agents', 'api', 'ingestion', 'llm', 'retrieval', 'storage']
    files = []
    for d in base_dirs:
        files.extend(glob.glob(f"{d}/**/*.py", recursive=True))
    
    matrix = {}
    calls = defaultdict(list)
    
    for file in files:
        if '__init__.py' in file:
            continue
            
        with open(file, 'r', encoding='utf-8') as f:
            try:
                content = f.read()
                tree = ast.parse(content)
                
                classes = []
                functions = []
                imports = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                        functions.append(node.name)
                        for inner in ast.walk(node):
                            if isinstance(inner, ast.Call):
                                if isinstance(inner.func, ast.Name):
                                    calls[node.name].append(inner.func.id)
                                elif isinstance(inner.func, ast.Attribute):
                                    calls[node.name].append(inner.func.attr)
                    elif isinstance(node, ast.Import):
                        for n in node.names:
                            imports.append(n.name)
                    elif isinstance(node, ast.ImportFrom):
                        imports.append(node.module)
                        
                matrix[file] = {
                    "classes": classes,
                    "functions": functions,
                    "imports": imports
                }
            except Exception as e:
                print(f"Error parsing {file}: {e}")
                
    return matrix, calls

matrix, calls = scan_files()
with open("feature_matrix.txt", "w") as f:
    for file, data in matrix.items():
        f.write(f"File: {file}\n")
        f.write(f"  Classes: {data['classes']}\n")
        f.write(f"  Functions: {data['functions']}\n")
        f.write(f"  Dependencies: {data['imports']}\n")
        
with open("call_graph_raw.txt", "w") as f:
    for caller, callee in calls.items():
        f.write(f"{caller} -> {set(callee)}\n")
        
print("Analysis complete.")
