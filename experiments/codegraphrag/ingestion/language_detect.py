import os

def detect_language(file_path: str) -> str:
    """
    Detect the programming language of a file based on its extension.
    
    Args:
        file_path: The path or name of the file.
        
    Returns:
        The detected language string (e.g. 'python', 'javascript'), or 'unknown'.
    """
    _, ext = os.path.splitext(file_path.lower())
    
    mappings = {
        '.py': 'python',
        '.pyw': 'python',
        
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
        
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.mts': 'typescript',
        '.cts': 'typescript',
        
        '.json': 'json',
        '.md': 'markdown',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        
        '.yaml': 'yaml',
        '.yml': 'yaml',
        
        '.sh': 'bash',
        '.bash': 'bash',
        
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.hpp': 'cpp',
        '.cc': 'cpp',
        
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust'
    }
    
    return mappings.get(ext, 'unknown')
