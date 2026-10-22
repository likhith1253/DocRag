import os
import zipfile
import tarfile
from typing import Generator, Dict, Any

def load_repository(path: str, allowed_files: set = None) -> Generator[Dict[str, Any], None, None]:
    """
    Stream files from a directory, zip, or tar archive.
    Does not load the entire archive into memory. Filters out binary files.
    
    Args:
        path: Path to the directory or archive file.
        
    Yields:
        Dict containing file_path, content, repo_name, and branch.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path does not exist: {path}")

    # Determine repo name from basename
    repo_name = os.path.splitext(os.path.basename(path))[0]
    if repo_name.endswith('.tar'):
        repo_name = os.path.splitext(repo_name)[0]

    # Helper to check if file is likely binary by extension or content
    binary_extensions = {
        '.pyc', '.pyo', '.pyd', '.db', '.png', '.jpg', '.jpeg', '.gif', '.pdf',
        '.zip', '.tar', '.gz', '.tgz', '.exe', '.dll', '.so', '.dylib', '.woff',
        '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.wav', '.ico'
    }

    def is_binary_ext(filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in binary_extensions

    if os.path.isdir(path):
        # Walk directory
        for root, dirs, files in os.walk(path):
            # Skip hidden files/directories (like .git, .venv, etc.)
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.startswith('.'):
                    continue
                if is_binary_ext(file):
                    continue
                full_path = os.path.join(root, file)
                # Compute relative path from repo root
                rel_path = os.path.relpath(full_path, path).replace('\\', '/')
                if allowed_files is not None and rel_path not in allowed_files:
                    continue
                try:
                    # Stream read
                    with open(full_path, 'r', encoding='utf-8', errors='strict') as f:
                        content = f.read()
                    yield {
                        "file_path": rel_path,
                        "content": content,
                        "repo_name": repo_name,
                        "branch": "main"
                    }
                except (UnicodeDecodeError, PermissionError):
                    continue

    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, 'r') as z:
            # Check for a single top-level directory in the archive
            namelist = z.namelist()
            non_empty_dirs = {name.split('/')[0] for name in namelist if name and '/' in name}
            strip_prefix = ""
            if len(non_empty_dirs) == 1:
                strip_prefix = list(non_empty_dirs)[0] + '/'

            for info in z.infolist():
                if info.is_dir():
                    continue
                filename = info.filename
                if is_binary_ext(filename) or any(part.startswith('.') for part in filename.split('/')):
                    continue
                # Strip prefix if needed
                rel_path = filename
                if strip_prefix and rel_path.startswith(strip_prefix):
                    rel_path = rel_path[len(strip_prefix):]
                
                if allowed_files is not None and rel_path not in allowed_files:
                    continue
                try:
                    with z.open(info) as f:
                        content = f.read().decode('utf-8', errors='strict')
                    yield {
                        "file_path": rel_path,
                        "content": content,
                        "repo_name": repo_name,
                        "branch": "main"
                    }
                except UnicodeDecodeError:
                    continue

    elif tarfile.is_tarfile(path):
        with tarfile.open(path, 'r:*') as t:
            # Check for a single top-level directory in the archive
            members = t.getmembers()
            non_empty_dirs = {m.name.split('/')[0] for m in members if m.name and '/' in m.name}
            strip_prefix = ""
            if len(non_empty_dirs) == 1:
                strip_prefix = list(non_empty_dirs)[0] + '/'

            for member in members:
                if not member.isfile():
                    continue
                filename = member.name
                if is_binary_ext(filename) or any(part.startswith('.') for part in filename.split('/')):
                    continue
                # Strip prefix if needed
                rel_path = filename
                if strip_prefix and rel_path.startswith(strip_prefix):
                    rel_path = rel_path[len(strip_prefix):]
                
                if allowed_files is not None and rel_path not in allowed_files:
                    continue
                try:
                    f = t.extractfile(member)
                    if f is not None:
                        content = f.read().decode('utf-8', errors='strict')
                        yield {
                            "file_path": rel_path,
                            "content": content,
                            "repo_name": repo_name,
                            "branch": "main"
                        }
                except UnicodeDecodeError:
                    continue
    else:
        raise ValueError(f"Unsupported repository file type/format: {path}")
