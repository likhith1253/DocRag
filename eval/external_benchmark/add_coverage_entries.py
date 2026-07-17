#!/usr/bin/env python3
"""
Append additional entries to the benchmark to address coverage gaps
identified by reviewer (css/, layouts/ subsystems missing).
Adds 8 new entries to reach ~88 total.
"""

import ast
import os
import json
import hashlib

REPO_ROOT = "d:/Document_RAG/eval/external_benchmark/repos/textual"
SRC_ROOT = os.path.join(REPO_ROOT, "src", "textual")
BENCHMARK_PATH = "d:/Document_RAG/eval/external_benchmark/full_benchmark.json"

def rel(abs_path):
    return os.path.relpath(abs_path, REPO_ROOT).replace("\\", "/")

def sha_id(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]

def make_chunk_id(evidence_file, start, end):
    return sha_id(f"{evidence_file}:{start}:{end}")

def get_class_method(path, class_name, method_name):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return item.lineno, item.end_lineno
    return None

def get_function(path, func_name):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node.lineno, node.end_lineno
    return None

def get_class(path, class_name):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node.lineno, node.end_lineno
    return None

def make_entry(id_, question, path, start, end, cap, comp, diff, notes,
               sec_path=None, sec_start=None, sec_end=None):
    ev_file = rel(path)
    cid = make_chunk_id(ev_file, start, end)
    chunks = [cid]
    entry = {
        "id": id_,
        "question": question,
        "evidence_file": ev_file,
        "evidence_lines": f"{start}-{end}",
        "ground_truth_chunks": chunks,
        "reasoning_capability": cap,
        "retrieval_complexity": comp,
        "difficulty": diff,
        "verification_metadata": {
            "verified": True,
            "verifier": "AST_Parser_v2",
            "notes": notes
        }
    }
    if sec_path and sec_start and sec_end:
        sec_file = rel(sec_path)
        entry["secondary_evidence_file"] = sec_file
        entry["secondary_evidence_lines"] = f"{sec_start}-{sec_end}"
        chunks.append(make_chunk_id(sec_file, sec_start, sec_end))
        entry["ground_truth_chunks"] = chunks
    return entry

def main():
    css_dir = os.path.join(SRC_ROOT, "css")
    lay_dir = os.path.join(SRC_ROOT, "layouts")

    match_path = os.path.join(css_dir, "match.py")
    stylesheet_path = os.path.join(css_dir, "stylesheet.py")
    scalar_path = os.path.join(css_dir, "scalar.py")
    styles_path = os.path.join(css_dir, "styles.py")
    vert_path = os.path.join(lay_dir, "vertical.py")
    grid_path = os.path.join(lay_dir, "grid.py")

    new_entries = []

    # css/match.py: match()
    r = get_function(match_path, "match")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_css_01",
            "How does the `match()` function in `css/match.py` evaluate CSS selectors against a DOM node?",
            match_path, s, e,
            "control-flow reasoning", "single-hop", "hard",
            "Single-hop: match() is self-contained in css/match.py."
        ))

    # css/match.py: _check_selectors()
    r = get_function(match_path, "_check_selectors")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_css_02",
            "How does `_check_selectors()` iterate over selector sets to determine if a node matches a CSS rule?",
            match_path, s, e,
            "control-flow reasoning", "single-hop", "hard",
            "Single-hop: _check_selectors is self-contained in css/match.py."
        ))

    # css/stylesheet.py: Stylesheet.apply()
    r = get_class_method(stylesheet_path, "Stylesheet", "apply")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_css_03",
            "How does `Stylesheet.apply()` propagate computed styles to all nodes in the DOM tree?",
            stylesheet_path, s, e,
            "data-flow reasoning", "multi-hop", "hard",
            "Multi-hop: apply() iterates DOM nodes and resolves styles, crossing dom.py."
        ))

    # css/stylesheet.py: Stylesheet.parse()
    r = get_class_method(stylesheet_path, "Stylesheet", "parse")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_css_04",
            "What is the parsing pipeline inside `Stylesheet.parse()` for converting CSS source text into rules?",
            stylesheet_path, s, e,
            "data-flow reasoning", "single-hop", "medium",
            "Single-hop: parse() is in css/stylesheet.py."
        ))

    # css/scalar.py: Scalar.resolve()
    r = get_class_method(scalar_path, "Scalar", "resolve")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_css_05",
            "How does `Scalar.resolve()` convert a CSS scalar value (%, fr, cells) to a concrete pixel value?",
            scalar_path, s, e,
            "configuration reasoning", "single-hop", "hard",
            "Single-hop: Scalar.resolve() is in css/scalar.py."
        ))

    # css/scalar.py: Scalar.parse()
    r = get_class_method(scalar_path, "Scalar", "parse")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_css_06",
            "How does `Scalar.parse()` tokenize and interpret a CSS scalar string like '1fr' or '50%'?",
            scalar_path, s, e,
            "data-flow reasoning", "single-hop", "medium",
            "Single-hop: Scalar.parse() is self-contained in css/scalar.py."
        ))

    # layouts/vertical.py: VerticalLayout.arrange()
    r = get_class_method(vert_path, "VerticalLayout", "arrange")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_lay_01",
            "How does `VerticalLayout.arrange()` compute and assign positions to child widgets in a vertical stack?",
            vert_path, s, e,
            "architectural reasoning", "single-hop", "hard",
            "Single-hop: VerticalLayout.arrange is self-contained in layouts/vertical.py."
        ))

    # layouts/grid.py: GridLayout.arrange()
    r = get_class_method(grid_path, "GridLayout", "arrange")
    if r:
        s, e = r
        new_entries.append(make_entry(
            "textual_lay_02",
            "How does `GridLayout.arrange()` allocate row and column spans to child widgets in a grid layout?",
            grid_path, s, e,
            "architectural reasoning", "single-hop", "hard",
            "Single-hop: GridLayout.arrange is self-contained in layouts/grid.py."
        ))

    # Load existing and append
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)

    existing_ids = {e["id"] for e in existing}
    added = 0
    for entry in new_entries:
        if entry["id"] not in existing_ids:
            existing.append(entry)
            added += 1
            print(f"  Added: {entry['id']} ({entry['evidence_lines']})")

    with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    print(f"\nAdded {added} entries. Total: {len(existing)}")

if __name__ == "__main__":
    main()
