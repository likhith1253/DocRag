"""
PDF Parser for DocumentRAG.
Extracts text blocks, page numbers, section headings, and paper metadata
from research paper PDFs using PyMuPDF (fitz).

Graceful fallbacks:
  - If PyMuPDF is unavailable, tries pdfminer.six
  - If text extraction fails, logs and returns empty result
  - If metadata fields are missing, uses filename-derived defaults
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend selection — PyMuPDF preferred, pdfminer fallback
# ---------------------------------------------------------------------------
_FITZ_AVAILABLE = False
_PDFMINER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    _FITZ_AVAILABLE = True
except ImportError:
    pass

import importlib.util
_PDFMINER_AVAILABLE = importlib.util.find_spec("pdfminer") is not None


# ---------------------------------------------------------------------------
# Heading detection heuristics
# ---------------------------------------------------------------------------

# Common academic section headings (case-insensitive prefix match)
_HEADING_KEYWORDS = [
    r"^abstract",
    r"^introduction",
    r"^related work",
    r"^background",
    r"^methodology",
    r"^methods?",
    r"^experimental? (setup|results?)?",
    r"^results? (and discussion)?",
    r"^discussion",
    r"^conclusion",
    r"^future work",
    r"^acknowledgments?",
    r"^references?",
    r"^appendix",
    r"^evaluation",
    r"^approach",
    r"^system (overview|design)?",
    r"^implementation",
    r"^dataset",
    r"^training",
    r"^analysis",
    r"^limitations?",
    r"^\d+\.\s+[A-Z][a-z]+",     # e.g. "1. Introduction" or "2. Methods"
    r"^\d+\.\d+\.?\s+[A-Z][a-z]+", # e.g. "2.1 Dataset"
]
_HEADING_RE = re.compile("|".join(_HEADING_KEYWORDS), re.IGNORECASE)


# Characters that reliably indicate a body-text line (not a section heading)
_NON_HEADING_PREFIX_RE = re.compile(
    r'^(?:'
    r'\[|'                          # reference bracket [1], [Author et al.]
    r'\(|'                          # parenthetical lines
    r'\d+\.\s+[a-z]|'              # numbered list item starting lowercase: "1. however..."
    r'\d{4}|'                       # bare year: "2020"
    r'http|'                        # URLs
    r'\|'                           # table row fragment
    r')',
    re.IGNORECASE
)


def _is_heading(text: str, font_size: float, avg_body_size: float) -> bool:
    """
    Heuristic: a text block is a section heading if it matches keyword
    patterns OR has a noticeably larger font size than body text.

    Threshold raised to 1.25x (was 1.10x) to prevent bold body text,
    table captions, and numbered references from being promoted to headings.
    Additional exclusion rules prevent reference list lines from being misclassified.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > 200:
        return False
    # Exclude lines that are clearly body text, affiliations, emails, or references
    if _NON_HEADING_PREFIX_RE.match(stripped):
        return False
    if re.search(r'university|laboratory|department|school|college|institute|email|http|@|proceedings|ieee|acm|vol\.|no\.|tandon|key lab', stripped, re.IGNORECASE):
        return False
    if _HEADING_RE.match(stripped):
        return True
    # Font-size heuristic: heading font must be > 25% larger than body average
    # (raised from 10% to reduce false positives on bold body text)
    if avg_body_size > 0 and font_size > avg_body_size * 1.25 and len(stripped) < 100:
        return True
    return False


def _extract_pdf_metadata(doc) -> Dict[str, str]:
    """Extract title, authors, year from PDF metadata dictionary."""
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()
    # Year from creation/modification date: format is "D:YYYYMMDDHHmmss..."
    year = ""
    for field in ("creationDate", "modDate"):
        val = meta.get(field, "")
        m = re.search(r"D:(\d{4})", val)
        if m:
            year = m.group(1)
            break
    return {"title": title, "authors": author, "year": year}


def _extract_tables_from_page(page) -> List[str]:
    """
    Extract tables from a PDF page using PyMuPDF's table detection.
    Returns list of table content as formatted strings.
    """
    tables = []
    try:
        # Try to find tables using PyMuPDF's find_tables
        table_finder = page.find_tables()
        if table_finder.tables:
            for table in table_finder.tables:
                # Extract table content
                table_content = []
                for r_idx, row in enumerate(table.extract()):
                    # Clean up cell content and format as Markdown table
                    row_text = "| " + " | ".join(str(cell).strip().replace('\n', ' ') if cell else "" for cell in row) + " |"
                    table_content.append(row_text)
                    if r_idx == 0:
                        separator = "| " + " | ".join("---" for _ in row) + " |"
                        table_content.append(separator)
                if table_content:
                    tables.append("\n".join(table_content))
    except Exception as e:
        logger.debug(f"Table extraction failed for page: {e}")
    return tables


def _fitz_parse(pdf_path: str) -> Dict[str, Any]:
    """
    Parse PDF using PyMuPDF.
    Returns:
        {
            "title": str,
            "authors": str,
            "year": str,
            "pages": [
                {
                    "page": int,          # 1-indexed
                    "blocks": [           # ordered text blocks
                        {"text": str, "font_size": float, "bbox": tuple}
                    ],
                    "tables": [str]       # extracted table content
                }
            ]
        }
    """
    doc = fitz.open(pdf_path)
    meta = _extract_pdf_metadata(doc)

    pages_data = []
    all_font_sizes = []

    for page_num, page in enumerate(doc, start=1):
        # Extract text blocks
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE, sort=True).get("blocks", [])
        page_blocks = []
        for block in blocks:
            if block.get("type") != 0:  # type 0 = text
                continue
            for line in block.get("lines", []):
                line_text_parts = []
                max_size = 0.0
                for span in line.get("spans", []):
                    line_text_parts.append(span.get("text", ""))
                    sz = span.get("size", 0.0)
                    if sz > max_size:
                        max_size = sz
                line_text = "".join(line_text_parts).strip()
                if line_text:
                    page_blocks.append({
                        "text": line_text,
                        "font_size": max_size,
                        "bbox": block.get("bbox", (0, 0, 0, 0))
                    })
                    all_font_sizes.append(max_size)
        
        # Extract tables
        tables = _extract_tables_from_page(page)
        
        pages_data.append({"page": page_num, "blocks": page_blocks, "tables": tables})

    doc.close()

    # Compute median body font size (excluding very small sizes like footnotes)
    if all_font_sizes:
        filtered = sorted(s for s in all_font_sizes if s > 4)
        avg_body = filtered[len(filtered) // 2] if filtered else 10.0
    else:
        avg_body = 10.0

    return {**meta, "pages": pages_data, "avg_body_font_size": avg_body}


def _pdfminer_parse(pdf_path: str) -> Dict[str, Any]:
    """Fallback parser using pdfminer — no font metadata, page breaks via formfeed."""
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    full_text = pdfminer_extract_text(pdf_path) or ""
    page_texts = full_text.split("\f")  # pdfminer uses \f as page delimiter

    pages_data = []
    for page_num, page_text in enumerate(page_texts, start=1):
        blocks = []
        for line in page_text.splitlines():
            stripped = line.strip()
            if stripped:
                blocks.append({"text": stripped, "font_size": 10.0, "bbox": (0, 0, 0, 0)})
        if blocks:
            pages_data.append({"page": page_num, "blocks": blocks})

    basename = os.path.splitext(os.path.basename(pdf_path))[0]
    return {
        "title": basename,
        "authors": "",
        "year": "",
        "pages": pages_data,
        "avg_body_font_size": 10.0
    }


def parse_pdf(pdf_path: str, filename_hint: str = None) -> Dict[str, Any]:
    """
    Main entry point: parse a PDF research paper.

    Args:
        pdf_path: Absolute path to the PDF file.
        filename_hint: Used as fallback title if PDF metadata has none.

    Returns:
        {
            "title": str,
            "authors": str,
            "year": str,
            "pages": [...],
            "avg_body_font_size": float
        }
    
    Raises:
        RuntimeError if no PDF backend is available.
        Exception propagated if parsing fails completely.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    result = None
    parse_error = None

    if _FITZ_AVAILABLE:
        try:
            result = _fitz_parse(pdf_path)
        except Exception as e:
            parse_error = e
            logger.warning(f"[PDFParser] PyMuPDF failed for {pdf_path}: {e}")

    if result is None and _PDFMINER_AVAILABLE:
        try:
            result = _pdfminer_parse(pdf_path)
        except Exception as e:
            parse_error = e
            logger.warning(f"[PDFParser] pdfminer failed for {pdf_path}: {e}")

    if result is None:
        if not _FITZ_AVAILABLE and not _PDFMINER_AVAILABLE:
            raise RuntimeError(
                "No PDF parsing backend available. "
                "Install PyMuPDF: pip install pymupdf  OR  pdfminer.six: pip install pdfminer.six"
            )
        raise RuntimeError(f"PDF parsing failed for {pdf_path}: {parse_error}")

    # Derive title from filename if PDF metadata has none
    if not result.get("title"):
        hint = filename_hint or os.path.splitext(os.path.basename(pdf_path))[0]
        result["title"] = hint.replace("_", " ").replace("-", " ")

    return result


def get_sections_with_pages(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Post-process parsed PDF output into sections with page ranges.

    Returns list of:
        {
            "heading": str,       # Section heading text (or "Body" for preamble)
            "page_start": int,    # First page this section appears on
            "page_end": int,      # Last page this section appears on (inclusive)
            "content": str,       # Full text of the section (including tables)
            "tables": List[str]   # Extracted table content for this section
        }
    """
    avg_size = parsed.get("avg_body_font_size", 10.0)
    pages = parsed.get("pages", [])

    sections: List[Dict[str, Any]] = []
    current_heading = "Body"
    current_page_start = 1
    current_page_end = 1
    current_lines: List[str] = []
    current_line_pages: List[int] = []
    current_tables: List[str] = []

    def _flush_section():
        nonlocal current_heading, current_page_start, current_page_end, current_lines, current_line_pages, current_tables
        text = "\n".join(current_lines).strip()
        # Add tables to content
        if current_tables:
            table_text = "\n\n".join(current_tables)
            text = f"{text}\n\n{table_text}" if text else table_text
        if text or current_tables:
            sections.append({
                "heading": current_heading,
                "page_start": current_page_start,
                "page_end": current_page_end,
                "content": text,
                "line_pages": current_line_pages,
                "tables": current_tables.copy()
            })
        current_lines = []
        current_line_pages = []
        current_tables = []

    for page_data in pages:
        page_num = page_data["page"]
        page_tables = page_data.get("tables", [])
        
        for block in page_data["blocks"]:
            text = block["text"]
            font_size = block["font_size"]
            if _is_heading(text, font_size, avg_size):
                _flush_section()
                current_heading = text.strip()
                current_page_start = page_num
                current_page_end = page_num
                # RC-3 fix: include the heading text as the first line of the
                # new section's content so no words are silently dropped.
                current_lines.append(text.strip())
                current_line_pages.append(page_num)
            else:
                current_lines.append(text)
                current_line_pages.append(page_num)
                current_page_end = page_num
        
        # Add tables from this page to current section
        current_tables.extend(page_tables)

    _flush_section()  # flush last section

    # If no sections were found at all, return the full text as one section
    if not sections and pages:
        all_lines = []
        all_line_pages = []
        all_tables = []
        first_page = pages[0]["page"]
        last_page = pages[-1]["page"]
        for pd in pages:
            for bl in pd["blocks"]:
                all_lines.append(bl["text"])
                all_line_pages.append(pd["page"])
            all_tables.extend(pd.get("tables", []))
        
        content = "\n".join(all_lines)
        if all_tables:
            table_text = "\n\n".join(all_tables)
            content = f"{content}\n\n{table_text}" if content else table_text
            
        sections.append({
            "heading": "Body",
            "page_start": first_page,
            "page_end": last_page,
            "content": content,
            "line_pages": all_line_pages,
            "tables": all_tables
        })

    return sections
