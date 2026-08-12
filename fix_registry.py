import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.registry import Registry
r = Registry()
repo = r.register_repository("Artificial Intelligence", "repo_ai_001")
r.update_status("repo_ai_001", "READY")