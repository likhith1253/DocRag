import os
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Callable, Any
from pydantic import BaseModel

class SubsystemManifest(BaseModel):
    files: List[str]
    dependencies: List[str]
    hashes: Dict[str, str]
    last_verified: str
    tests_executed: List[str]
    performance: Dict[str, Any] = {}
    regression: Dict[str, Any] = {}

class VerificationManager:
    def __init__(self, manifest_path: str = "./verification_manifest.json"):
        self.manifest_path = manifest_path
        self.manifests: Dict[str, SubsystemManifest] = {}
        self._load()
        
    def _load(self):
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.manifests[k] = SubsystemManifest(**v)
            except Exception as e:
                print(f"Warning: Failed to load verification manifest: {e}")
                
    def _save(self):
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            data = {k: v.model_dump() for k, v in self.manifests.items()}
            json.dump(data, f, indent=2)
            
    def _hash_file(self, filepath: str) -> str:
        if not os.path.exists(filepath):
            return ""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
        
    def _compute_hashes(self, files: List[str]) -> Dict[str, str]:
        return {f: self._hash_file(f) for f in files}
        
    def verify(
        self,
        subsystem_name: str,
        files: List[str],
        dependencies: List[str],
        test_func: Callable,
        integration_test_func: Callable = None,
        test_names: List[str] = None
    ) -> bool:
        """
        Executes validation. If hashes match, only runs integration_test_func.
        Otherwise runs test_func and updates the manifest.
        """
        all_files = files + dependencies
        current_hashes = self._compute_hashes(all_files)
        
        needs_full_run = True
        
        if subsystem_name in self.manifests:
            old_manifest = self.manifests[subsystem_name]
            # Check if all hashes match
            if old_manifest.hashes == current_hashes:
                needs_full_run = False
                
        if needs_full_run:
            print(f"[VerificationManager] {subsystem_name}: Hashes changed or no manifest. Running FULL validation.")
            try:
                test_func()
                # If successful, update manifest
                self.manifests[subsystem_name] = SubsystemManifest(
                    files=files,
                    dependencies=dependencies,
                    hashes=current_hashes,
                    last_verified=datetime.now(timezone.utc).isoformat(),
                    tests_executed=test_names or [test_func.__name__]
                )
                self._save()
                return True
            except Exception as e:
                print(f"[VerificationManager] {subsystem_name}: FULL validation FAILED: {e}")
                raise e
        else:
            print(f"[VerificationManager] {subsystem_name}: Unchanged. Running INTEGRATION only.")
            if integration_test_func:
                try:
                    integration_test_func()
                except Exception as e:
                    print(f"[VerificationManager] {subsystem_name}: INTEGRATION validation FAILED: {e}")
                    raise e
            return True
