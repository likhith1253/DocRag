import os
import re
import yaml
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any

from ingestion.parser import parse_code

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")

def load_chunking_config() -> tuple:
    """
    Load chunking config from config.yaml.
    Returns (max_chunk_tokens, overlap_tokens).
    """
    max_chunk_tokens = 512
    overlap_tokens = 64
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            chunking = config.get("chunking", {})
            max_chunk_tokens = chunking.get("max_chunk_tokens", 512)
            overlap_tokens = chunking.get("overlap_tokens", 64)
        except Exception:
            pass
    return max_chunk_tokens, overlap_tokens

def count_tokens(text: str) -> int:
    """
    Approximate token count using a fast regex tokenizer.
    Splits by words and non-whitespace punctuation.
    """
    if not text:
        return 0
    return len(re.findall(r'\w+|[^\w\s]', text))

def get_clean_header(header_text: str, max_tokens: int) -> str:
    """
    Truncate class header to fit within max_tokens if needed.
    """
    if count_tokens(header_text) <= max_tokens:
        return header_text
    lines = header_text.splitlines()
    short_lines = []
    curr_tokens = 0
    for line in lines:
        t = count_tokens(line)
        if curr_tokens + t > max_tokens:
            break
        short_lines.append(line)
        curr_tokens += t
    return "\n".join(short_lines)

def chunk_text_sliding_window(text: str, start_line: int, max_tokens: int, overlap_tokens: int) -> List[Dict[str, Any]]:
    """
    Splits text into chunks of lines, respecting max_tokens and overlap_tokens.
    Returns list of dicts: {"content": str, "start_line": int, "end_line": int}
    """
    lines = text.splitlines()
    if not lines:
        return []
        
    line_token_counts = [count_tokens(l) for l in lines]
    chunks = []
    
    i = 0
    n = len(lines)
    while i < n:
        current_lines = []
        current_tokens = 0
        j = i
        
        while j < n:
            tokens = line_token_counts[j]
            if current_tokens + tokens <= max_tokens or not current_lines:
                current_lines.append(lines[j])
                current_tokens += tokens
                j += 1
            else:
                break
                
        chunk_text = "\n".join(current_lines)
        chunks.append({
            "content": chunk_text,
            "start_line": start_line + i,
            "end_line": start_line + j - 1
        })
        
        if j == n:
            break
            
        overlap_collected = 0
        backtrack_idx = j - 1
        while backtrack_idx >= i and overlap_collected + line_token_counts[backtrack_idx] <= overlap_tokens:
            overlap_collected += line_token_counts[backtrack_idx]
            backtrack_idx -= 1
            
        next_i = backtrack_idx + 1
        if next_i <= i:
            next_i = i + 1
        i = next_i
        
    return chunks

def extract_dependencies(start_line: int, end_line: int, parsed_ast: Dict[str, Any], current_class: str, current_function: str) -> List[Dict[str, str]]:
    """
    Extract dependencies/links (imports, inherits, calls) that occur within the chunk's line range.
    """
    deps = []
    seen = set()

    # 1. Imports
    for imp in parsed_ast.get("imports", []):
        if start_line <= imp["start_line"] <= end_line:
            target = imp["module"] if imp["module"] else ""
            for name in imp["names"]:
                t = f"{target}.{name}" if target else name
                if t and t not in seen:
                    deps.append({"target": t, "type": "imports"})
                    seen.add(t)

    # 2. Inherits
    if current_class:
        for cls in parsed_ast.get("classes", []):
            if cls["name"] == current_class:
                for parent in cls.get("inherits", []):
                    if parent not in seen:
                        deps.append({"target": parent, "type": "inherits"})
                        seen.add(parent)

    # 3. Calls
    for call in parsed_ast.get("calls", []):
        if start_line <= call["line"] <= end_line:
            callee = call["callee"]
            if callee and callee not in seen:
                deps.append({"target": callee, "type": "calls"})
                seen.add(callee)

    return deps

def chunk_file(file_path: str, content: str, repo_name: str, branch: str, language: str) -> List[Dict[str, Any]]:
    """
    Perform AST-aware semantic chunking on a file's content.
    
    Returns:
        List of chunk dicts containing content and metadata.
    """
    max_chunk_tokens, overlap_tokens = load_chunking_config()
    
    # Parse AST
    parsed = parse_code(content, language)
    classes = parsed.get("classes", [])
    functions = parsed.get("functions", [])
    
    # Filter global functions
    global_funcs = [f for f in functions if f["class_name"] is None]
    
    chunks_raw = [] # list of dicts: {content, start_line, end_line, class, function}

    # Fallback to pure sliding window if no AST elements found
    if not classes and not global_funcs:
        sw_chunks = chunk_text_sliding_window(content, 1, max_chunk_tokens, overlap_tokens)
        for c in sw_chunks:
            chunks_raw.append({
                "content": c["content"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "class": None,
                "function": None
            })
    else:
        # Partition the file into top-level logical units
        lines = content.splitlines()
        total_lines = len(lines)
        
        occupied = []
        for c in classes:
            occupied.append((c["start_line"], c["end_line"], "class", c))
        for f in global_funcs:
            occupied.append((f["start_line"], f["end_line"], "function", f))
            
        occupied.sort(key=lambda x: x[0])
        
        partition = []
        current_line = 1
        
        for start, end, utype, data in occupied:
            if start > current_line:
                gap_lines = lines[current_line - 1 : start - 1]
                partition.append({
                    "type": "global",
                    "name": None,
                    "start_line": current_line,
                    "end_line": start - 1,
                    "text": "\n".join(gap_lines)
                })
            partition.append({
                "type": utype,
                "name": data["name"],
                "start_line": start,
                "end_line": end,
                "text": data["text"]
            })
            current_line = end + 1
            
        if current_line <= total_lines:
            gap_lines = lines[current_line - 1 : total_lines]
            partition.append({
                "type": "global",
                "name": None,
                "start_line": current_line,
                "end_line": total_lines,
                "text": "\n".join(gap_lines)
            })

        # Process each partition unit
        for unit in partition:
            unit_text = unit["text"]
            unit_start = unit["start_line"]
            unit_end = unit["end_line"]
            
            if unit["type"] == "global":
                sw = chunk_text_sliding_window(unit_text, unit_start, max_chunk_tokens, overlap_tokens)
                for c in sw:
                    chunks_raw.append({
                        "content": c["content"],
                        "start_line": c["start_line"],
                        "end_line": c["end_line"],
                        "class": None,
                        "function": None
                    })
            elif unit["type"] == "function":
                tokens_count = count_tokens(unit_text)
                if tokens_count <= max_chunk_tokens:
                    chunks_raw.append({
                        "content": unit_text,
                        "start_line": unit_start,
                        "end_line": unit_end,
                        "class": None,
                        "function": unit["name"]
                    })
                else:
                    sw = chunk_text_sliding_window(unit_text, unit_start, max_chunk_tokens, overlap_tokens)
                    for c in sw:
                        chunks_raw.append({
                            "content": c["content"],
                            "start_line": c["start_line"],
                            "end_line": c["end_line"],
                            "class": None,
                            "function": unit["name"]
                        })
            elif unit["type"] == "class":
                class_name = unit["name"]
                # Find all methods belonging to this class
                class_methods = [f for f in functions if f["class_name"] == class_name]
                class_methods.sort(key=lambda x: x["start_line"])
                
                # Check if entire class fits
                if count_tokens(unit_text) <= max_chunk_tokens:
                    chunks_raw.append({
                        "content": unit_text,
                        "start_line": unit_start,
                        "end_line": unit_end,
                        "class": class_name,
                        "function": None
                    })
                elif not class_methods:
                    # No methods, just slide window over class body
                    sw = chunk_text_sliding_window(unit_text, unit_start, max_chunk_tokens, overlap_tokens)
                    for c in sw:
                        chunks_raw.append({
                            "content": c["content"],
                            "start_line": c["start_line"],
                            "end_line": c["end_line"],
                            "class": class_name,
                            "function": None
                        })
                else:
                    # We have methods. Determine class header.
                    first_method_start = class_methods[0]["start_line"]
                    
                    # Header is from class_start to first_method_start - 1
                    header_lines = lines[unit_start - 1 : first_method_start - 1]
                    header_text = "\n".join(header_lines)
                    
                    # Ensure class header isn't too large
                    clean_header = get_clean_header(header_text, max_chunk_tokens - 100)
                    header_tokens = count_tokens(clean_header)
                    
                    # Partition the class body using methods
                    class_body_partition = []
                    curr_body_line = unit_start
                    
                    # Class header chunk
                    if clean_header.strip():
                        class_body_partition.append({
                            "type": "class_header",
                            "name": None,
                            "start_line": unit_start,
                            "end_line": first_method_start - 1,
                            "text": clean_header
                        })
                        
                    curr_body_line = first_method_start
                    for method in class_methods:
                        m_start = method["start_line"]
                        m_end = method["end_line"]
                        
                        if m_start > curr_body_line:
                            gap_m_lines = lines[curr_body_line - 1 : m_start - 1]
                            class_body_partition.append({
                                "type": "class_gap",
                                "name": None,
                                "start_line": curr_body_line,
                                "end_line": m_start - 1,
                                "text": "\n".join(gap_m_lines)
                            })
                            
                        class_body_partition.append({
                            "type": "method",
                            "name": method["name"],
                            "start_line": m_start,
                            "end_line": m_end,
                            "text": method["text"]
                        })
                        curr_body_line = m_end + 1
                        
                    if curr_body_line <= unit_end:
                        tail_lines = lines[curr_body_line - 1 : unit_end]
                        class_body_partition.append({
                            "type": "class_gap",
                            "name": None,
                            "start_line": curr_body_line,
                            "end_line": unit_end,
                            "text": "\n".join(tail_lines)
                        })
                        
                    for part in class_body_partition:
                        ptype = part["type"]
                        ptext = part["text"]
                        pstart = part["start_line"]
                        pend = part["end_line"]
                        
                        if ptype == "method":
                            # Prepend class header
                            combined_text = clean_header + "\n" + ptext
                            combined_tokens = count_tokens(combined_text)
                            
                            if combined_tokens <= max_chunk_tokens:
                                chunks_raw.append({
                                    "content": combined_text,
                                    "start_line": pstart,
                                    "end_line": pend,
                                    "class": class_name,
                                    "function": part["name"]
                                })
                            else:
                                # Slide window over method text, prepending class header to each chunk
                                remaining_tokens = max_chunk_tokens - header_tokens
                                if remaining_tokens < 50:
                                    remaining_tokens = 50 # safety fallback
                                sw = chunk_text_sliding_window(ptext, pstart, remaining_tokens, overlap_tokens)
                                for c in sw:
                                    chunks_raw.append({
                                        "content": clean_header + "\n" + c["content"],
                                        "start_line": c["start_line"],
                                        "end_line": c["end_line"],
                                        "class": class_name,
                                        "function": part["name"]
                                    })
                        else:
                            # class header or gap
                            sw = chunk_text_sliding_window(ptext, pstart, max_chunk_tokens, overlap_tokens)
                            for c in sw:
                                chunks_raw.append({
                                    "content": c["content"],
                                    "start_line": c["start_line"],
                                    "end_line": c["end_line"],
                                    "class": class_name,
                                    "function": None
                                })

    # Generate final chunks with metadata and dependency linking
    final_chunks = []
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    for raw in chunks_raw:
        content_str = raw["content"]
        s_line = raw["start_line"]
        e_line = raw["end_line"]
        cls = raw["class"]
        func = raw["function"]
        
        # Calculate SHA-256 hash of content
        content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        
        # Extract dependency-aware links
        deps = extract_dependencies(s_line, e_line, parsed, cls, func)
        
        metadata = {
            "repository": repo_name,
            "branch": branch,
            "language": language,
            "file": file_path,
            "class": cls,
            "function": func,
            "lines": f"{s_line}-{e_line}",
            "hash": content_hash,
            "timestamp": timestamp,
            "dependencies": deps
        }
        
        final_chunks.append({
            "content": content_str,
            "metadata": metadata
        })
        
    return final_chunks
