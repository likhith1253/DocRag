import os
import subprocess
import hashlib
from typing import Dict, List, Tuple
from storage.snapshot import RepositorySnapshot

def _hash_file(filepath: str) -> str:
    """Compute SHA-256 of a file."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""

def _is_git_repo(path: str) -> bool:
    return os.path.exists(os.path.join(path, ".git"))

def _git_diff(target_path: str, old_commit: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Returns (added, modified, deleted) relative file paths using Git.
    """
    added, modified, deleted = [], [], []
    try:
        # Get name-status diff
        result = subprocess.run(
            ["git", "diff", "--name-status", old_commit, "HEAD"],
            cwd=target_path,
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.splitlines():
            if not line:
                continue
            parts = line.split('\t')
            status = parts[0][0]
            
            if status == 'A':
                added.append(parts[1])
            elif status == 'M':
                modified.append(parts[1])
            elif status == 'D':
                deleted.append(parts[1])
            elif status == 'R':
                # Renamed: Old path is deleted, new path is added
                deleted.append(parts[1])
                added.append(parts[2])
                
        return added, modified, deleted
    except Exception as e:
        print(f"Git diff failed: {e}. Falling back to hash diff.")
        return None, None, None

def _hash_diff(target_path: str, old_hashes: Dict[str, str]) -> Tuple[List[str], List[str], List[str], Dict[str, str]]:
    """
    Fallback diffing using SHA-256. Supports semicolon-separated multiple paths.
    Returns (added, modified, deleted, current_hashes)
    """
    binary_extensions = {
        '.pyc', '.pyo', '.pyd', '.db', '.png', '.jpg', '.jpeg', '.gif',
        '.zip', '.tar', '.gz', '.tgz', '.exe', '.dll', '.so', '.dylib', '.woff',
        '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.wav', '.ico'
        # NOTE: .pdf intentionally NOT excluded — DocumentRAG must track PDF changes
    }

    def is_binary_ext(filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in binary_extensions

    current_hashes = {}
    added, modified, deleted = [], [], []
    
    paths = [p.strip() for p in target_path.split(";") if p.strip()]
    
    for path in paths:
        if not os.path.exists(path):
            continue
        base_name = os.path.basename(os.path.normpath(path))
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.startswith('.') or is_binary_ext(file):
                    continue
                full_path = os.path.join(root, file)
                sub_rel = os.path.relpath(full_path, path).replace('\\', '/')
                if len(paths) > 1:
                    rel_path = f"{base_name}/{sub_rel}"
                else:
                    rel_path = sub_rel
                
                file_hash = _hash_file(full_path)
                if not file_hash:
                    continue
                    
                current_hashes[rel_path] = file_hash
            
    # Compute delta
    for rel_path, file_hash in current_hashes.items():
        if rel_path not in old_hashes:
            added.append(rel_path)
        elif old_hashes[rel_path] != file_hash:
            modified.append(rel_path)
            
    for rel_path in old_hashes.keys():
        if rel_path not in current_hashes:
            deleted.append(rel_path)
            
    return added, modified, deleted, current_hashes

def compute_file_diff(target_path: str, snapshot: RepositorySnapshot) -> Tuple[List[str], List[str], List[str], Dict[str, str]]:
    """
    Compute file-level changes.
    Returns: (added_files, modified_files, deleted_files, new_file_hashes)
    """
    old_hashes = snapshot.file_hashes or {}
    
    # If the snapshot is completely empty, treat everything as added
    if not old_hashes:
        _, _, _, current_hashes = _hash_diff(target_path, {})
        return list(current_hashes.keys()), [], [], current_hashes

    if snapshot.indexed_commit and _is_git_repo(target_path):
        added, modified, deleted = _git_diff(target_path, snapshot.indexed_commit)
        if added is not None:
            # We still need to update current_hashes for the snapshot
            # To be efficient, we can just copy old hashes and update the deltas
            current_hashes = old_hashes.copy()
            for a in added:
                current_hashes[a] = _hash_file(os.path.join(target_path, a))
            for m in modified:
                current_hashes[m] = _hash_file(os.path.join(target_path, m))
            for d in deleted:
                current_hashes.pop(d, None)
            return added, modified, deleted, current_hashes

    # Hash fallback
    return _hash_diff(target_path, old_hashes)
