import os
import ast
import subprocess

repos = {
    "textual": "https://github.com/Textualize/textual",
    "rich": "https://github.com/Textualize/rich",
    "typer": "https://github.com/tiangolo/typer",
    "click": "https://github.com/pallets/click"
}

os.makedirs("d:\\Document_RAG\\eval\\external_benchmark\\repos", exist_ok=True)
os.chdir("d:\\Document_RAG\\eval\\external_benchmark\\repos")

def analyze_repo(repo_name, repo_url):
    print(f"Analyzing {repo_name}...")
    if not os.path.exists(repo_name):
        subprocess.run(["git", "clone", "--depth", "1", repo_url, repo_name], check=True, capture_output=True)
    
    num_files = 0
    num_functions = 0
    num_classes = 0
    
    for root, _, files in os.walk(repo_name):
        for file in files:
            if file.endswith(".py"):
                num_files += 1
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                            num_functions += 1
                        elif isinstance(node, ast.ClassDef):
                            num_classes += 1
                except Exception:
                    pass
    print(f"{repo_name}: {num_files} files, {num_functions} functions, {num_classes} classes")
    return num_files, num_functions, num_classes

for name, url in repos.items():
    analyze_repo(name, url)
