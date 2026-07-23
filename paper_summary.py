#!/usr/bin/env python3
"""
Check what content exists for each paper in the index.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.metadata_store import MetadataStoreManager

meta_manager = MetadataStoreManager("./metadata_store.json")

print("\nPAPER CONTENT SUMMARY\n" + "="*60)

# Group by paper
papers = {}
for hash_id, meta in meta_manager.store.items():
    paper = meta.get("file", "unknown")
    if paper not in papers:
        papers[paper] = {
            "chunks": 0,
            "sections": set(),
            "pages": []
        }
    papers[paper]["chunks"] += 1
    section = meta.get("section", "")
    if section:
        papers[paper]["sections"].add(section)
    page_start = meta.get("page_start", 0)
    page_end = meta.get("page_end", 0)
    if page_start > 0:
        papers[paper]["pages"].append((page_start, page_end))

for paper in sorted(papers.keys()):
    info = papers[paper]
    name = paper.split("/")[-1][:50]
    chunks = info["chunks"]
    sections = len(info["sections"])
    max_page = max([p[1] for p in info["pages"]]) if info["pages"] else 0
    
    print(f"{name:50} | {chunks:3} chunks | {sections} sections | p.{max_page}")
    
    # Show sections
    for section in sorted(info["sections"])[:3]:
        print(f"  - {section[:40]}")
    if len(info["sections"]) > 3:
        print(f"  ... +{len(info['sections']) - 3} more")
