#!/usr/bin/env python3
"""
build_demo_dataset.py — Professional Demo Dataset Builder for DocumentRAG.

Run from d:/DocRag/:
    python scripts/build_demo_dataset.py

Phases 1-7: Dataset construction (download, validate, rename, metadata, questions).
Phases 8-11 handled by run_demo_index_eval.py after this completes.
"""

import os, sys, json, time, shutil, re, logging, threading, xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(r"d:/DocRag")
PAPERS_SRC   = PROJECT_ROOT / "papers"
DEMO_ROOT    = PROJECT_ROOT / "demo_dataset"
OLD_DATASET  = PROJECT_ROOT / "dataset"
LOG_DIR      = PROJECT_ROOT / "logs"
CHECKPOINT   = PROJECT_ROOT / "logs" / "demo_build_checkpoint.json"

LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "build_demo_dataset.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Category definitions ─────────────────────────────────────────────────────
CATEGORIES = [
    "Artificial_Intelligence",
    "Machine_Learning",
    "Computer_Vision",
    "Natural_Language_Processing",
    "Retrieval_Augmented_Generation",
]

CATEGORY_SOURCE = {
    "Artificial_Intelligence":        PAPERS_SRC / "AI",
    "Machine_Learning":               PAPERS_SRC / "GraphML",
    "Computer_Vision":                PAPERS_SRC / "ComputerVision",
    "Natural_Language_Processing":    PAPERS_SRC / "LLM",
    "Retrieval_Augmented_Generation": PAPERS_SRC / "RAG",
}

# ─── arXiv papers to download (id, clean_title) per category ─────────────────
ARXIV_PAPERS = {
    "Artificial_Intelligence": [
        ("1706.03762", "Attention Is All You Need"),
        ("1312.5602",  "Playing Atari with Deep Reinforcement Learning"),
        ("1707.06347", "Proximal Policy Optimization Algorithms"),
        ("1312.6114",  "Auto-Encoding Variational Bayes"),
        ("1406.2661",  "Generative Adversarial Nets"),
        ("2005.14165", "Language Models are Few-Shot Learners"),
        ("1602.01783", "Asynchronous Methods for Deep Reinforcement Learning"),
        ("1803.10122", "World Models"),
        ("1503.02531", "Distilling the Knowledge in a Neural Network"),
        ("1801.01290", "Soft Actor-Critic - Off-Policy Maximum Entropy Deep Reinforcement Learning"),
    ],
    "Machine_Learning": [
        ("1412.6980",  "Adam - A Method for Stochastic Optimization"),
        ("1502.03167", "Batch Normalization - Accelerating Deep Network Training"),
        ("1603.02754", "XGBoost - A Scalable Tree Boosting System"),
        ("2006.11239", "Denoising Diffusion Probabilistic Models"),
        ("2106.09685", "LoRA - Low-Rank Adaptation of Large Language Models"),
        ("1705.07874", "A Unified Approach to Interpreting Model Predictions"),
        ("1611.01578", "Neural Architecture Search with Reinforcement Learning"),
        ("1207.0580",  "Improving Neural Networks by Preventing Co-Adaptation of Feature Detectors"),
        ("1607.06450", "Layer Normalization"),
        ("1611.03530", "Understanding Deep Learning Requires Rethinking Generalization"),
    ],
    "Computer_Vision": [
        ("1512.03385", "Deep Residual Learning for Image Recognition"),
        ("1506.02640", "You Only Look Once - Unified Real-Time Object Detection"),
        ("1703.06870", "Mask R-CNN"),
        ("1505.04597", "U-Net - Convolutional Networks for Biomedical Image Segmentation"),
        ("2010.11929", "An Image is Worth 16x16 Words - Transformers for Image Recognition at Scale"),
        ("2103.00020", "Learning Transferable Visual Models From Natural Language Supervision"),
        ("1905.11946", "EfficientNet - Rethinking Model Scaling for Convolutional Neural Networks"),
        ("2005.12872", "End-to-End Object Detection with Transformers"),
        ("2304.07193", "DINOv2 - Learning Robust Visual Features without Supervision"),
        ("1612.03144", "Feature Pyramid Networks for Object Detection"),
    ],
    "Natural_Language_Processing": [
        ("1810.04805", "BERT - Pre-training of Deep Bidirectional Transformers for Language Understanding"),
        ("1907.11692", "RoBERTa - A Robustly Optimized BERT Pretraining Approach"),
        ("1910.10683", "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer"),
        ("1906.08237", "XLNet - Generalized Autoregressive Pretraining for Language Understanding"),
        ("1908.10084", "Sentence-BERT - Sentence Embeddings using Siamese BERT-Networks"),
        ("1301.3781",  "Efficient Estimation of Word Representations in Vector Space"),
        ("1910.13461", "BART - Denoising Sequence-to-Sequence Pre-training for Natural Language Generation"),
        ("1907.10529", "SpanBERT - Improving Pre-training by Representing and Predicting Spans"),
        ("2003.10555", "ELECTRA - Pre-training Text Encoders as Discriminators Rather Than Generators"),
        ("1909.11942", "ALBERT - A Lite BERT for Self-supervised Learning of Language Representations"),
    ],
    "Retrieval_Augmented_Generation": [
        ("2005.11401", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"),
        ("2002.08909", "REALM - Retrieval-Augmented Language Model Pre-Training"),
        ("2004.04906", "Dense Passage Retrieval for Open-Domain Question Answering"),
        ("2212.10496", "Precise Zero-Shot Dense Retrieval without Relevance Labels"),
        ("2310.11511", "Self-RAG - Learning to Retrieve Generate and Reflect"),
        ("2305.06983", "Active Retrieval Augmented Generation"),
        ("2007.01282", "Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering"),
        ("2208.03299", "Atlas - Few-shot Learning with Retrieval Augmented Language Models"),
        ("2401.15884", "Corrective Retrieval Augmented Generation"),
        ("2112.04426", "Improving Language Models by Retrieving from Trillions of Tokens"),
    ],
}

# Backup papers if primaries fail validation
BACKUP_ARXIV = {
    "Artificial_Intelligence": [("2303.08774", "GPT-4 Technical Report"), ("1511.05952", "Prioritized Experience Replay")],
    "Machine_Learning": [("1906.02629", "Momentum Contrast for Unsupervised Visual Representation Learning"), ("2010.09714", "An Image is Worth 16x16 Words")],
    "Computer_Vision": [("1703.06211", "Deformable Convolutional Networks"), ("1608.06993", "Densely Connected Convolutional Networks")],
    "Natural_Language_Processing": [("2109.01652", "Finetuned Language Models Are Zero-Shot Learners"), ("2204.02311", "PaLM - Scaling Language Modeling with Pathways")],
    "Retrieval_Augmented_Generation": [("2401.16380", "RAG vs Fine-tuning"), ("2305.14283", "SAIL - Search-Augmented Instruction Learning")],
}

TARGET   = 20
DL_WAIT  = 2.0   # polite delay between arXiv requests (seconds)
DL_WORKERS = 3   # parallel download threads
QA_WORKERS = 2   # parallel question-generation threads

VALIDATION_MIN_PAGES    = 5
VALIDATION_MIN_CHARS    = 500
VALIDATION_MIN_SIZE_KB  = 80

# ─── Checkpoint ───────────────────────────────────────────────────────────────
_cp_lock = threading.Lock()

def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_checkpoint(data: dict):
    with _cp_lock:
        existing = load_checkpoint()
        existing.update(data)
        CHECKPOINT.write_text(json.dumps(existing, indent=2), encoding="utf-8")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def sanitize_filename(title: str) -> str:
    """Convert paper title to clean Windows filename."""
    bad = r'\/:*?"<>|'
    for c in bad:
        title = title.replace(c, "")
    title = re.sub(r"\s+", " ", title).strip(". ")
    if len(title) > 120:
        title = title[:117].rstrip() + "..."
    return title + ".pdf"


def validate_pdf(path: Path) -> dict:
    """
    Validate a PDF and return a result dict.
    Returns {"ok": True, "pages": N, "chars": N, "has_abstract": bool}
    or      {"ok": False, "reason": str}
    """
    try:
        size_kb = path.stat().st_size // 1024
        if size_kb < VALIDATION_MIN_SIZE_KB:
            return {"ok": False, "reason": f"Too small ({size_kb}KB < {VALIDATION_MIN_SIZE_KB}KB)"}

        doc = fitz.open(str(path))
        pages = doc.page_count
        if pages < VALIDATION_MIN_PAGES:
            doc.close()
            return {"ok": False, "reason": f"Too short ({pages} pages < {VALIDATION_MIN_PAGES})"}

        # Extract text from first 5 pages
        text = ""
        for i in range(min(5, pages)):
            text += doc[i].get_text()
        doc.close()

        if len(text.strip()) < VALIDATION_MIN_CHARS:
            return {"ok": False, "reason": "Text extraction failed / scanned PDF"}

        has_abstract = bool(re.search(r"\bAbstract\b", text, re.IGNORECASE))
        return {"ok": True, "pages": pages, "chars": len(text), "has_abstract": has_abstract, "size_kb": size_kb}

    except Exception as e:
        return {"ok": False, "reason": f"fitz error: {e}"}


def get_arxiv_metadata(arxiv_id: str) -> dict:
    """Fetch title, authors, abstract, year from arXiv API."""
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return {}
        title = entry.findtext("atom:title", namespaces=ns) or ""
        title = re.sub(r"\s+", " ", title).strip()
        abstract = entry.findtext("atom:summary", namespaces=ns) or ""
        abstract = re.sub(r"\s+", " ", abstract).strip()
        authors = [a.findtext("atom:name", namespaces=ns) or ""
                   for a in entry.findall("atom:author", ns)]
        published = entry.findtext("atom:published", namespaces=ns) or ""
        year = published[:4] if published else ""
        categories = [c.get("term", "") for c in entry.findall("atom:category", ns)]
        return {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "year": year,
            "categories": categories,
            "arxiv_id": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
        }
    except Exception as e:
        log.warning(f"arXiv API error for {arxiv_id}: {e}")
        return {}


def download_arxiv_pdf(arxiv_id: str, dest: Path, title_hint: str) -> bool:
    """Download a PDF from arXiv. Returns True on success."""
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "DocumentRAG-Research/1.0"}, allow_redirects=True)
        if r.status_code != 200 or len(r.content) < 10_000:
            log.warning(f"  [DL] {arxiv_id} HTTP {r.status_code} or too small ({len(r.content)} bytes)")
            return False
        if not r.content[:4] == b"%PDF":
            # Sometimes returns HTML error page
            log.warning(f"  [DL] {arxiv_id} response is not a PDF")
            return False
        dest.write_bytes(r.content)
        log.info(f"  [DL] {arxiv_id} → {dest.name} ({len(r.content)//1024}KB)")
        return True
    except Exception as e:
        log.warning(f"  [DL] {arxiv_id} failed: {e}")
        return False


def extract_sections_from_pdf(path: Path) -> dict:
    """Extract key sections from a PDF for question generation context."""
    try:
        from ingestion.pdf_parser import parse_pdf, get_sections_with_pages
        parsed = parse_pdf(str(path), filename_hint=path.stem)
        sections = get_sections_with_pages(parsed)
        section_map = {}
        for sec in sections:
            h = sec.get("heading", "").lower()
            content = sec.get("content", "").strip()
            if not content:
                continue
            for key in ["abstract", "introduction", "related", "method", "approach",
                        "experiment", "result", "limitation", "conclusion", "future"]:
                if key in h and key not in section_map:
                    section_map[key] = {
                        "heading": sec.get("heading", ""),
                        "content": content[:2000],
                        "page_start": sec.get("page_start", 1),
                    }
        return {
            "title": parsed.get("title", path.stem.replace("_", " ")),
            "authors": parsed.get("authors", ""),
            "year": parsed.get("year", ""),
            "pages": parsed.get("pages", 0),
            "sections": section_map,
        }
    except Exception as e:
        log.warning(f"  [PARSE] {path.name}: {e}")
        return {}


# ─── Phase 1: Setup ───────────────────────────────────────────────────────────

def phase1_setup():
    log.info("=" * 60)
    log.info("PHASE 1: Setup & Cleanup")
    log.info("=" * 60)

    # Remove old stale dataset entirely
    if OLD_DATASET.exists():
        shutil.rmtree(OLD_DATASET, ignore_errors=True)
        log.info(f"  Removed: {OLD_DATASET}")

    # Create fresh demo_dataset with 5 category folders
    DEMO_ROOT.mkdir(exist_ok=True)
    for cat in CATEGORIES:
        (DEMO_ROOT / cat).mkdir(exist_ok=True)
    log.info(f"  Created: {DEMO_ROOT}")
    for cat in CATEGORIES:
        log.info(f"    └── {cat}/")


# ─── Phase 2: Migrate Existing Valid PDFs ─────────────────────────────────────

def phase2_migrate():
    log.info("=" * 60)
    log.info("PHASE 2: Migrate Existing Valid PDFs")
    log.info("=" * 60)

    migrated = {}
    for cat, src_folder in CATEGORY_SOURCE.items():
        dest_folder = DEMO_ROOT / cat
        migrated[cat] = []
        if not src_folder.exists():
            log.warning(f"  Source missing: {src_folder}")
            continue
        for pdf_path in sorted(src_folder.glob("*.pdf")):
            v = validate_pdf(pdf_path)
            if not v.get("ok"):
                log.info(f"  [SKIP] {pdf_path.name}: {v.get('reason')}")
                continue
            dest = dest_folder / pdf_path.name
            shutil.copy2(pdf_path, dest)
            migrated[cat].append(dest)
            log.info(f"  [COPY] {cat}/{pdf_path.name} ({v.get('pages')}pg)")
        log.info(f"  {cat}: {len(migrated[cat])} papers migrated")

    save_checkpoint({"migrated": {k: [str(p) for p in v] for k, v in migrated.items()}})
    return migrated


# ─── Phase 3: Download arXiv Papers ──────────────────────────────────────────

def _download_one(cat: str, arxiv_id: str, title_hint: str, dest_folder: Path) -> tuple:
    """Download one arXiv paper. Returns (ok, path, metadata)."""
    safe_name = sanitize_filename(title_hint)
    dest = dest_folder / safe_name
    if dest.exists():
        v = validate_pdf(dest)
        if v.get("ok"):
            log.info(f"  [CACHED] {cat}/{dest.name}")
            meta = get_arxiv_metadata(arxiv_id)
            return True, dest, meta
        else:
            dest.unlink()

    time.sleep(DL_WAIT)  # polite rate limiting
    ok = download_arxiv_pdf(arxiv_id, dest, title_hint)
    if not ok:
        return False, None, {}

    v = validate_pdf(dest)
    if not v.get("ok"):
        log.warning(f"  [INVALID] {dest.name}: {v.get('reason')}")
        if dest.exists():
            dest.unlink()
        return False, None, {}

    meta = get_arxiv_metadata(arxiv_id)
    return True, dest, meta


def phase3_download(migrated: dict) -> dict:
    log.info("=" * 60)
    log.info("PHASE 3: Download arXiv Papers")
    log.info("=" * 60)

    downloaded_meta = {}  # cat -> list of {path, meta}
    arxiv_cache = {}      # arxiv_id -> metadata

    for cat in CATEGORIES:
        dest_folder = DEMO_ROOT / cat
        existing_count = len(list(dest_folder.glob("*.pdf")))
        needed = TARGET - existing_count
        log.info(f"  {cat}: {existing_count} existing, need {needed} more")

        if needed <= 0:
            log.info(f"  {cat}: already at target — skipping downloads")
            downloaded_meta[cat] = []
            continue

        papers_to_try = list(ARXIV_PAPERS.get(cat, []))
        backups = list(BACKUP_ARXIV.get(cat, []))

        # Skip IDs already downloaded (by checking if safe filename exists)
        already_names = {p.name for p in dest_folder.glob("*.pdf")}
        papers_to_try = [
            (aid, title) for aid, title in papers_to_try
            if sanitize_filename(title) not in already_names
        ]

        downloaded_meta[cat] = []
        acquired = 0

        with ThreadPoolExecutor(max_workers=DL_WORKERS) as ex:
            futures = {
                ex.submit(_download_one, cat, aid, title, dest_folder): (aid, title)
                for aid, title in papers_to_try[:needed + len(backups)]
            }
            for future in as_completed(futures):
                if acquired >= needed:
                    future.cancel()
                    continue
                aid, title = futures[future]
                try:
                    ok, path, meta = future.result()
                    if ok and path:
                        downloaded_meta[cat].append({"path": str(path), "arxiv_id": aid, "meta": meta})
                        arxiv_cache[aid] = meta
                        acquired += 1
                        log.info(f"  [OK] {cat}/{path.name} ({acquired}/{needed})")
                except Exception as e:
                    log.warning(f"  [ERROR] {futures[future]}: {e}")

        # Try backups if still short
        existing_now = len(list(dest_folder.glob("*.pdf")))
        if existing_now < TARGET:
            for aid, title in backups:
                if existing_now >= TARGET:
                    break
                safe_name = sanitize_filename(title)
                if (dest_folder / safe_name).exists():
                    existing_now += 1
                    continue
                time.sleep(DL_WAIT)
                ok, path, meta = _download_one(cat, aid, title, dest_folder)
                if ok:
                    downloaded_meta[cat].append({"path": str(path), "arxiv_id": aid, "meta": meta})
                    existing_now += 1

        final = len(list(dest_folder.glob("*.pdf")))
        log.info(f"  {cat}: {final}/{TARGET} papers")

    save_checkpoint({"arxiv_downloaded": {k: [x["path"] for x in v] for k, v in downloaded_meta.items()}})
    return downloaded_meta


# ─── Phase 4: Validate All PDFs ──────────────────────────────────────────────

def phase4_validate():
    log.info("=" * 60)
    log.info("PHASE 4: Validate All PDFs")
    log.info("=" * 60)

    rejected = []
    for cat in CATEGORIES:
        folder = DEMO_ROOT / cat
        for pdf in sorted(folder.glob("*.pdf")):
            v = validate_pdf(pdf)
            if not v.get("ok"):
                log.warning(f"  [REJECT] {cat}/{pdf.name}: {v.get('reason')}")
                pdf.unlink()
                rejected.append({"category": cat, "file": pdf.name, "reason": v.get("reason")})
            else:
                log.info(f"  [VALID] {cat}/{pdf.name}: {v.get('pages')}pg {v.get('size_kb')}KB")

    summary = {cat: len(list((DEMO_ROOT / cat).glob("*.pdf"))) for cat in CATEGORIES}
    log.info("\n  Validation Summary:")
    for cat, n in summary.items():
        status = "✓" if n >= TARGET else f"⚠ NEEDS {TARGET - n} MORE"
        log.info(f"    {cat}: {n}/{TARGET}  {status}")

    save_checkpoint({"validation_rejected": rejected, "counts_after_validation": summary})
    return summary


# ─── Phase 5: Rename to Proper Titles ────────────────────────────────────────

def phase5_rename():
    log.info("=" * 60)
    log.info("PHASE 5: Rename Files to Proper Paper Titles")
    log.info("=" * 60)

    all_papers = []

    for cat in CATEGORIES:
        folder = DEMO_ROOT / cat
        for pdf in sorted(folder.glob("*.pdf")):
            # Skip already properly named files (not starting with W2/W3/W4/local_/clone_)
            stem = pdf.stem
            needs_rename = any(stem.startswith(p) for p in ["W2", "W3", "W4", "local_", "clone_"])

            if needs_rename:
                # Try to extract title from PDF metadata
                try:
                    doc = fitz.open(str(pdf))
                    meta = doc.metadata
                    doc.close()
                    title = (meta.get("title") or "").strip()
                    if len(title) < 10:
                        # Fall back to first page text heuristic
                        doc = fitz.open(str(pdf))
                        first_page_text = doc[0].get_text()[:800]
                        doc.close()
                        lines = [l.strip() for l in first_page_text.splitlines() if len(l.strip()) > 20]
                        title = lines[0] if lines else stem.replace("_", " ")
                    new_name = sanitize_filename(title)
                    new_path = folder / new_name
                    if new_path != pdf and not new_path.exists():
                        pdf.rename(new_path)
                        log.info(f"  [RENAME] {pdf.name[:40]} → {new_name[:60]}")
                        pdf = new_path
                except Exception as e:
                    log.warning(f"  [RENAME-FAIL] {pdf.name}: {e}")

            all_papers.append({"category": cat, "path": str(pdf), "filename": pdf.name})

    save_checkpoint({"all_papers": all_papers})
    log.info(f"\n  Total papers after rename: {len(all_papers)}")
    return all_papers


# ─── Phase 6: Generate metadata.json ─────────────────────────────────────────

def phase6_metadata(all_papers: list) -> dict:
    log.info("=" * 60)
    log.info("PHASE 6: Generate metadata.json")
    log.info("=" * 60)

    metadata = {}

    for paper in all_papers:
        path = Path(paper["path"])
        cat  = paper["category"]

        if not path.exists():
            continue

        parsed = extract_sections_from_pdf(path)
        title  = parsed.get("title") or path.stem.replace("_", " ")

        # Extract sections list
        section_names = list(parsed.get("sections", {}).keys())

        # Try PDF metadata for authors/year
        try:
            doc = fitz.open(str(path))
            pdf_meta = doc.metadata
            pages = doc.page_count
            doc.close()
        except Exception:
            pdf_meta = {}
            pages = parsed.get("pages", 0)

        authors = parsed.get("authors") or pdf_meta.get("author") or "Unknown"
        year    = parsed.get("year") or pdf_meta.get("creationDate", "")[:4] or "N/A"

        # Determine venue heuristic from category
        venue_map = {
            "Artificial_Intelligence":        "NeurIPS / ICML / ICLR",
            "Machine_Learning":               "NeurIPS / ICML / ICLR",
            "Computer_Vision":                "CVPR / ICCV / ECCV",
            "Natural_Language_Processing":    "ACL / EMNLP / NAACL",
            "Retrieval_Augmented_Generation": "ACL / EMNLP / NeurIPS",
        }

        entry = {
            "title":             title,
            "authors":           authors,
            "year":              year,
            "venue":             venue_map.get(cat, "arXiv"),
            "pages":             pages,
            "category":          cat,
            "filename":          path.name,
            "path":              str(path.relative_to(PROJECT_ROOT)),
            "abstract":          parsed.get("sections", {}).get("abstract", {}).get("content", "")[:500],
            "detected_sections": section_names,
            "indexed_at":        datetime.now(timezone.utc).isoformat(),
        }
        metadata[path.name] = entry
        log.info(f"  [META] {path.name[:60]} — {pages}pg, sections: {len(section_names)}")

    meta_path = DEMO_ROOT / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"\n  Saved: {meta_path}  ({len(metadata)} entries)")
    save_checkpoint({"metadata_count": len(metadata)})
    return metadata


# ─── Phase 7: Generate Questions ─────────────────────────────────────────────

QUESTION_PROMPT = """You are an expert research curator creating evaluation questions for a local RAG system.
Generate EXACTLY 10 high-quality, non-trivial, analytical questions and expected answers for the paper "{title}".
The questions must require deep understanding of the paper. Never ask about title, authors, or publication year.

Below is the extracted context from key sections of the paper:
{content}

For each of the following 10 types, generate exactly 1 question and its corresponding expected answer:
1. "methodology" (How the proposed method/approach works in detail)
2. "architecture" (System architecture, model design, or pipeline)
3. "algorithm" (Specific algorithm, training procedure, or mathematical formulation)
4. "experimental_setup" (Datasets, baselines, metrics, and conditions)
5. "results" (Key quantitative results or performance improvements)
6. "limitation" (Limitations or failure cases acknowledged)
7. "future_work" (Future research directions suggested)
8. "figure_table" (What a specific figure, table, or diagram shows)
9. "multi_section" (Requires reasoning across multiple sections)
10. "analytical" (Expert-level analytical question about the novel contribution/significance)

For each question, the expected answer must include:
- A concise expert answer (2-4 sentences)
- The section name where the answer is found
- Approximate page number
- A direct supporting evidence quote (15-30 words verbatim from the content)

Respond with ONLY a valid JSON array of exactly 10 objects, like this:
[
  {{
    "type": "methodology",
    "question": "...",
    "expected_answer": "...",
    "evidence": "... verbatim quote from text ...",
    "section": "...",
    "page": 1
  }},
  ...
]
Do not wrap in markdown or backticks. Return ONLY the raw JSON array.
"""


def _build_context(sections: dict) -> str:
    """Build a compact context string from parsed sections."""
    parts = []
    priority = ["abstract", "introduction", "method", "approach", "experiment", "result", "limitation", "conclusion"]
    for key in priority:
        if key in sections:
            sec = sections[key]
            snippet = sec["content"][:600]
            parts.append(f"[{sec['heading']} (p.{sec['page_start']})]\n{snippet}")
    if not parts:
        # Fallback: use all available
        for key, sec in list(sections.items())[:4]:
            parts.append(f"[{sec['heading']}]\n{sec['content'][:600]}")
    return "\n\n".join(parts)[:3500]


def _generate_negative_question_item() -> dict:
    import random
    negatives = [
        {"q": "What accuracy did GPT-5 achieve in this work?", "a": "This information is not present in the paper."},
        {"q": "How does the paper's methodology compare with Llama-4-Instruct?", "a": "This information is not present in the paper."},
        {"q": "Which quantum computing framework was used for the experiments?", "a": "This information is not present in the paper."}
    ]
    selected = random.choice(negatives)
    return {
        "type": "hallucination",
        "question": selected["q"],
        "expected_answer": selected["a"],
        "evidence": "N/A",
        "section": "N/A",
        "page": -1
    }


def _generate_local_heuristic_questions(path: Path, title: str, category: str, sections: dict) -> list:
    qs = []
    for sname, sec in list(sections.items())[:8]:
        content = sec["content"].strip().replace("\n", " ")
        if len(content) < 150:
            continue
        words = content.split()
        evidence = " ".join(words[:25])
        qs.append({
            "type": sname,
            "paper": title,
            "category": category,
            "filename": path.name,
            "question": f"Detail the context and key points presented in the section '{sec['heading']}' of the work.",
            "expected_answer": f"In the '{sec['heading']}' section, the authors discuss the following: {content[:200]}...",
            "evidence": evidence,
            "section": sec["heading"],
            "page": sec.get("page_start", 1)
        })
    # Add negative
    neg = _generate_negative_question_item()
    neg["paper"] = title
    neg["category"] = category
    neg["filename"] = path.name
    qs.append(neg)
    return qs


def _generate_paper_questions(paper_info: tuple) -> list:
    """Generate 10 questions for one paper. Runs in a thread."""
    from llm.backend import generate
    import random
    path, title, category, sections = paper_info

    content = _build_context(sections)
    if len(content.strip()) < 100:
        return []

    prompt = QUESTION_PROMPT.format(
        title=title,
        category=category,
        content=content,
    )

    for attempt in range(3):
        try:
            # Add salt on retry to bypass LLM cache for failures
            salt = f"\nSalt: {attempt} ({random.random()})" if attempt > 0 else ""
            prompt_with_salt = prompt + salt

            raw = generate(prompt_with_salt, model_key="doc_agent_model").strip()
            # Strip markdown fences
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            data = json.loads(raw)
            if not isinstance(data, list) or len(data) == 0:
                continue

            valid_qs = []
            trivial_patterns = ["what is the title", "who are the authors", "when was it published", "what year"]

            for item in data:
                # Lenient check: only question and expected_answer are strictly required
                if not all(k in item for k in ("question", "expected_answer")):
                    continue
                if len(item["question"].strip()) < 15 or len(item["expected_answer"].strip()) < 15:
                    continue
                if any(p in item["question"].lower() for p in trivial_patterns):
                    continue

                # Default missing metadata fields
                qtype = item.get("type", "general")
                evidence = item.get("evidence", "N/A").strip()
                section = item.get("section") or item.get("heading")
                if not section or len(str(section).strip()) < 2:
                    section = category
                
                page = item.get("page") or item.get("page_number") or 1
                try:
                    page = int(page)
                except Exception:
                    page = 1

                valid_qs.append({
                    "type":            qtype,
                    "paper":           title,
                    "category":        category,
                    "filename":        path.name,
                    "question":        item["question"].strip(),
                    "expected_answer": item["expected_answer"].strip(),
                    "evidence":        evidence,
                    "section":         str(section).strip(),
                    "page":            page,
                })

            if len(valid_qs) >= 5:
                # Add negative question
                neg = _generate_negative_question_item()
                neg["paper"] = title
                neg["category"] = category
                neg["filename"] = path.name
                valid_qs.append(neg)

                log.info(f"  [QA] {title[:50]}: {len(valid_qs)}/11 questions generated (attempt {attempt+1})")
                return valid_qs
            else:
                log.warning(f"  [QA-REJECT] {title[:30]}: only {len(valid_qs)} valid questions parsed")
        except Exception as e:
            log.debug(f"  [QA-ERR] {title[:30]} attempt {attempt+1}: {e}")
            time.sleep(0.5)

    log.warning(f"  [QA-FALLBACK] Heuristic fallback for {title[:50]}")
    return _generate_local_heuristic_questions(path, title, category, sections)


def phase7_questions(metadata: dict) -> list:
    log.info("=" * 60)
    log.info("PHASE 7: Generate Questions (10 per paper, parallel)")
    log.info("=" * 60)

    # Load existing questions checkpoint if available
    questions_path = DEMO_ROOT / "questions.json"
    existing_questions = {}
    if questions_path.exists():
        try:
            existing = json.loads(questions_path.read_text(encoding="utf-8"))
            existing_questions = {q["filename"]: True for q in existing}
            log.info(f"  Resuming: {len(existing_questions)} papers already have questions")
        except Exception:
            existing = []
    else:
        existing = []

    # Build work list
    work_items = []
    for filename, meta in metadata.items():
        if filename in existing_questions:
            continue
        path = PROJECT_ROOT / meta["path"]
        if not path.exists():
            continue
        parsed = extract_sections_from_pdf(path)
        sections = parsed.get("sections", {})
        if not sections:
            log.warning(f"  [QA-SKIP] No sections extracted from {filename}")
            continue
        work_items.append((path, meta["title"], meta["category"], sections))

    log.info(f"  Papers to process: {len(work_items)}")

    all_questions = list(existing)
    done = 0

    with ThreadPoolExecutor(max_workers=QA_WORKERS) as ex:
        futures = {ex.submit(_generate_paper_questions, item): item[0].name for item in work_items}
        for future in as_completed(futures):
            fname = futures[future]
            try:
                qs = future.result()
                all_questions.extend(qs)
                done += 1
                # Save checkpoint on every paper for progress visibility and resume safety
                questions_path.write_text(
                    json.dumps(all_questions, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                log.info(f"  Progress: {done}/{len(work_items)} papers ({len(all_questions)} questions)")

                # Stop when we have completed 40 papers total
                completed_papers = len(set(q["filename"] for q in all_questions))
                if completed_papers >= 40:
                    log.info(f"  [STOP] Reached target limit of {completed_papers} papers. Stopping question generation.")
                    for fut in futures:
                        if not fut.done():
                            fut.cancel()
                    break
            except Exception as e:
                log.warning(f"  [QA-ERR] {fname}: {e}")

    # Final cleanup to keep only the completed 40 papers in metadata and PDF directories
    completed_filenames = set(q["filename"] for q in all_questions)

    # 1. Filter metadata.json
    meta_path = DEMO_ROOT / "metadata.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            filtered_meta = {k: v for k, v in meta.items() if k in completed_filenames}
            meta_path.write_text(json.dumps(filtered_meta, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info(f"  [CLEANUP] Filtered metadata.json to {len(filtered_meta)} entries.")
        except Exception as e:
            log.warning(f"  [CLEANUP-FAIL] metadata.json: {e}")

    # 2. Delete other PDFs from demo_dataset/
    deleted_count = 0
    for cat in CATEGORIES:
        folder = DEMO_ROOT / cat
        for pdf in folder.glob("*.pdf"):
            if pdf.name not in completed_filenames:
                try:
                    pdf.unlink()
                    deleted_count += 1
                except Exception:
                    pass
    if deleted_count > 0:
        log.info(f"  [CLEANUP] Deleted {deleted_count} unused PDFs from demo_dataset.")

    # Final save
    questions_path.write_text(json.dumps(all_questions, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"\n  Saved: {questions_path}")
    log.info(f"  Total questions generated: {len(all_questions)}")
    save_checkpoint({"question_count": len(all_questions)})
    return all_questions


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║  DocumentRAG — Professional Demo Dataset Builder     ║")
    log.info("╚══════════════════════════════════════════════════════╝")
    log.info(f"  Output: {DEMO_ROOT}")
    log.info(f"  Target: {len(CATEGORIES)} categories × {TARGET} papers = {len(CATEGORIES) * TARGET} total")
    log.info("")

    t0 = time.perf_counter()

    phase1_setup()
    migrated      = phase2_migrate()
    downloaded    = phase3_download(migrated)
    counts        = phase4_validate()
    all_papers    = phase5_rename()
    metadata      = phase6_metadata(all_papers)
    questions     = phase7_questions(metadata)

    elapsed = time.perf_counter() - t0
    log.info("")
    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║  Phases 1-7 Complete                                 ║")
    log.info("╚══════════════════════════════════════════════════════╝")
    log.info(f"  Elapsed: {elapsed/60:.1f} min")
    log.info(f"  Papers:  {sum(counts.values())}")
    log.info(f"  Questions: {len(questions)}")
    log.info("")
    log.info("  Next: run  python scripts/run_demo_index_eval.py")


if __name__ == "__main__":
    main()
