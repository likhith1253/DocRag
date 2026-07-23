"""
DocumentRAG — Research Paper Q&A Interface.
Streamlit UI for uploading research paper collections and asking questions.

Workflow:
  1. User specifies a folder path containing PDFs.
  2. System indexes folder as an isolated collection.
  3. User selects a collection and asks questions.
  4. System answers with inline citations (paper, section, page).

UI design principles:
  - Stable progress panel: single placeholder blocks, no full-page flicker.
  - Progress shows elapsed time, papers/min, worker count, failed count.
  - Minimal, professional layout — no flashy animations.
  - All API calls have explicit error handling.
"""

import streamlit as st
import requests
import time
import os

# ---------------------------------------------------------------------------
# Page config  — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DocumentRAG — Research Paper Q&A",
    page_icon="📚",
    layout="wide",
)

API_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Minimal CSS fixes — spacing, overflow, stable layout
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Prevent long paths from breaking the collection manager layout */
    .stMarkdown small { word-break: break-all; }
    /* Tighten metric display */
    [data-testid="metric-container"] { padding: 0.25rem 0; }
    /* Remove excessive top padding from the main block */
    .block-container { padding-top: 1.5rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📚 DocumentRAG — Research Paper Q&A")
st.caption(
    "Upload a folder of research papers · Ask questions · Get cited answers — locally, privately."
)

# ---------------------------------------------------------------------------
# Sidebar: System status + cache clear + how-to
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ System")
    try:
        health = requests.get(f"{API_URL}/health", timeout=2).json()
        st.success(f"API: {health.get('status', 'ok').upper()}")
    except Exception:
        st.error("API offline — start: `uvicorn api.main:app --port 8000`")

    st.divider()
    st.header("🧹 Cache")
    if st.button(
        "Clear System Cache",
        use_container_width=True,
        help="Wipe semantic cache, embedding cache, and LLM prompt cache",
    ):
        try:
            res = requests.post(f"{API_URL}/cache/clear", timeout=10)
            if res.status_code == 200:
                st.success("All caches cleared.")
            else:
                st.error(f"Failed: {res.text}")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.markdown(
        "**How to use:**\n"
        "1. Select sample dataset(s) or enter folder path(s)\n"
        "2. Click **Index Collection**\n"
        "3. Select the collection below\n"
        "4. Ask any question about the papers\n"
        "5. Answers include page-level citations"
    )

# ---------------------------------------------------------------------------
# Section 1 — Index Research Paper Collection(s)
# ---------------------------------------------------------------------------
st.header("1. Index Research Paper Collection(s)")

# Pre-existing datasets for convenience
st.markdown("#### 📂 Sample Datasets in Workspace")
sample_datasets = {
    "AI Dataset": r"d:\DocRag\dataset\AI",
    "CV Dataset": r"d:\DocRag\dataset\ComputerVision",
    "ML Dataset": r"d:\DocRag\dataset\MachineLearning",
    "NLP Dataset": r"d:\DocRag\dataset\NLP",
    "RAG Dataset": r"d:\DocRag\dataset\RAG",
    "AI Papers": r"d:\DocRag\papers\AI",
    "CV Papers": r"d:\DocRag\papers\ComputerVision",
    "GraphML Papers": r"d:\DocRag\papers\GraphML",
    "LLM Papers": r"d:\DocRag\papers\LLM",
    "MedicalAI Papers": r"d:\DocRag\papers\MedicalAI",
    "RAG Papers": r"d:\DocRag\papers\RAG",
    "Robotics Papers": r"d:\DocRag\papers\Robotics",
}

selected_samples = st.multiselect(
    "Select sample dataset(s) to auto-fill paths",
    options=list(sample_datasets.keys()),
    default=[],
)

default_folders = ""
if selected_samples:
    default_folders = "; ".join([sample_datasets[s] for s in selected_samples])

folder_path = st.text_input(
    "Folder paths containing PDF research papers (separate with `;` or `,`)",
    value=default_folders,
    placeholder=r"e.g.  d:\DocRag\dataset\AI; d:\DocRag\dataset\NLP",
    key="folder_path_input",
)

collection_name_input = st.text_input(
    "Custom collection name (optional — defaults to folder name)",
    placeholder="e.g. AI_and_NLP_Papers",
    key="collection_name_input",
)

index_btn = st.button("📥 Index Collection", use_container_width=True)

if index_btn:
    if not folder_path.strip():
        st.warning("Please enter at least one folder path.")
    else:
        raw_paths = [
            p.strip()
            for p in folder_path.replace(",", ";").split(";")
            if p.strip()
        ]

        valid = True
        validated_paths = []
        pdf_count = 0

        for path in raw_paths:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                st.error(f"Path does not exist: `{abs_path}`")
                valid = False
            elif not os.path.isdir(abs_path):
                st.error(f"Not a directory: `{abs_path}`")
                valid = False
            else:
                validated_paths.append(abs_path)
                pdf_count += sum(
                    1
                    for _, _, fs in os.walk(abs_path)
                    for f in fs
                    if f.lower().endswith(".pdf")
                )

        if valid:
            if pdf_count == 0:
                st.warning("No PDF files found in the specified folder(s).")
            else:
                if collection_name_input.strip():
                    collection_name = collection_name_input.strip()
                elif len(validated_paths) > 1:
                    collection_name = " + ".join(
                        os.path.basename(p) or "collection" for p in validated_paths
                    )
                else:
                    collection_name = os.path.basename(validated_paths[0]) or "collection"

                abs_paths_str = ";".join(validated_paths)
                st.info(
                    f"Found **{pdf_count} PDF(s)**. "
                    f"Registering collection **'{collection_name}'**…"
                )

                try:
                    res = requests.post(
                        f"{API_URL}/repository/",
                        json={
                            "name": collection_name,
                            "branch": "main",
                            "source_path": abs_paths_str,
                        },
                        timeout=10,
                    )
                    if res.status_code == 200:
                        repo_data = res.json()
                        repo_id = repo_data["repo_id"]
                        st.session_state["indexing_repo_id"] = repo_id
                        st.session_state["indexing_repo_name"] = collection_name
                        st.success(
                            "Collection registered. Indexing started in background."
                        )
                        st.rerun()
                    else:
                        st.error(
                            f"Failed to register: "
                            f"{res.json().get('detail', 'Unknown error')}"
                        )
                except Exception as e:
                    st.error(f"Could not connect to API: {e}")

st.divider()

# ---------------------------------------------------------------------------
# Active Indexing Progress Panel
# Stable: uses a single set of st.empty() placeholders so Streamlit
# does not re-create the entire widget tree on every rerun, which was
# the root cause of flickering.
# ---------------------------------------------------------------------------
if "indexing_repo_id" in st.session_state:
    repo_id = st.session_state["indexing_repo_id"]
    repo_name = st.session_state["indexing_repo_name"]

    st.subheader(f"⏳ Indexing: {repo_name}")

    # All UI slots created once — updated in-place
    slot_bar   = st.empty()
    slot_stage = st.empty()
    slot_row1  = st.empty()
    slot_row2  = st.empty()
    slot_msg   = st.empty()

    try:
        status_res = requests.get(
            f"{API_URL}/indexing/status/{repo_id}", timeout=5
        )
        if status_res.status_code == 200:
            d = status_res.json()
            stage          = d.get("stage", "")
            pct            = d.get("percentage", 0.0)
            files_done     = d.get("files_processed", 0)
            files_total    = d.get("files_total", 0)
            chunks_done    = d.get("chunks_processed", 0)
            chunks_total   = d.get("chunks_total", 0)
            emb_rate       = d.get("embedding_rate", 0.0)
            eta_sec        = d.get("eta_seconds", -1.0)
            status         = d.get("status", "")
            elapsed        = d.get("elapsed_seconds", 0.0)
            failed_f       = d.get("failed_files", 0)
            papers_min     = d.get("papers_per_minute", 0.0)
            parse_workers  = d.get("parse_workers", 1)
            current_file   = d.get("current_file", "")

            # Progress bar
            slot_bar.progress(min(1.0, max(0.0, pct / 100.0)))

            # Stage + query availability
            query_allowed = status in ("READY", "INDEXING_TIER1", "INDEXING_TIER2")
            query_badge = (
                "🟢 Querying **enabled** — ask questions below while indexing completes."
                if query_allowed
                else "🟡 Querying **disabled** — waiting for metadata stage."
            )
            slot_stage.markdown(
                f"**Stage:** `{stage.upper()}` · **Status:** `{status}` · "
                f"**Progress:** {pct:.1f}%  \n{query_badge}"
            )

            # Metrics row 1
            elapsed_str = (
                f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                if elapsed >= 60
                else f"{int(elapsed)}s"
            )
            eta_str = (
                f"{int(eta_sec // 60)}m {int(eta_sec % 60)}s"
                if eta_sec >= 60
                else (f"{int(eta_sec)}s" if eta_sec >= 0 else "estimating…")
            )

            slot_row1.markdown(
                f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| 📄 Documents parsed | `{files_done}` / `{files_total}`"
                + (f" _(current: {current_file})_" if current_file else "")
                + f" |\n"
                f"| 🧩 Chunks embedded | `{chunks_done}` / `{chunks_total}` |\n"
                f"| ⚡ Embed speed | `{emb_rate:.1f}` chunks/s |\n"
            )

            slot_row2.markdown(
                f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| ⏱ Elapsed | `{elapsed_str}` |\n"
                f"| ⏳ ETA | `{eta_str}` |\n"
                f"| 🚀 Throughput | `{papers_min:.1f}` papers/min |\n"
                f"| 👷 Parse workers | `{parse_workers}` |\n"
                + (
                    f"| ⚠️ Failed PDFs | `{failed_f}` |\n"
                    if failed_f > 0
                    else ""
                )
            )

            # Terminal states
            if status == "READY" or stage == "completed":
                slot_msg.success(
                    f"✅ Collection **'{repo_name}'** fully indexed! Ready to query."
                )
                del st.session_state["indexing_repo_id"]
                del st.session_state["indexing_repo_name"]
                st.rerun()
            elif status == "FAILED" or stage == "failed":
                slot_msg.error(
                    f"❌ Indexing failed for **'{repo_name}'**. "
                    f"Check `logs/indexing.log` for details."
                )
                del st.session_state["indexing_repo_id"]
                del st.session_state["indexing_repo_name"]
                st.rerun()
            else:
                time.sleep(2.0)   # stable 2s poll — less flicker than 1.5s
                st.rerun()
        else:
            st.error(f"Status fetch failed: {status_res.text}")
            del st.session_state["indexing_repo_id"]
            del st.session_state["indexing_repo_name"]

    except Exception as e:
        st.warning(f"Waiting for API… ({e})")
        time.sleep(2)
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Ask a Question
# ---------------------------------------------------------------------------
st.header("2. Ask a Question")

# Fetch available collections
try:
    repos_res = requests.get(f"{API_URL}/repository/", timeout=5)
    repos_list = repos_res.json() if repos_res.status_code == 200 else []
except Exception:
    repos_list = []

ready_repos = [
    r
    for r in repos_list
    if r.get("status") in ("READY", "INDEXING_TIER1", "INDEXING_TIER2")
]

selected_repo_id = None
if ready_repos:
    repo_options = {
        f"📄 {r['name']}  (ID: {r['repo_id'][:8]}…)": r["repo_id"]
        for r in ready_repos
    }
    col_q1, col_q2 = st.columns([3, 1])
    with col_q1:
        selected_repo_name = st.selectbox(
            "Select collection to query",
            list(repo_options.keys()),
            key="collection_select",
        )
        selected_repo_id = repo_options[selected_repo_name]
    with col_q2:
        st.write("")
        st.caption(f"ID: `{selected_repo_id}`")
else:
    st.info("No indexed collections available. Index a folder above to get started.")

question = st.text_area(
    "Your question",
    placeholder="e.g. What method does the paper use for data augmentation?",
    height=100,
    key="question_input",
)

ask_btn = st.button(
    "🔍 Ask",
    use_container_width=False,
    disabled=(not ready_repos),
)

if ask_btn:
    if not question or not question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Searching papers and generating answer…"):
            try:
                payload = {"question": question.strip()}
                if selected_repo_id:
                    payload["collection_id"] = selected_repo_id

                res = requests.post(
                    f"{API_URL}/query", json=payload, timeout=120
                )
                if res.status_code == 200:
                    data = res.json()
                    ans = data.get("answer", "")
                    citations = data.get("citations", [])
                    sources = data.get("sources", [])
                    chunks = data.get("chunks", [])
                    latency = data.get("latency", 0.0)

                    # Answer
                    st.subheader("💬 Answer")
                    if "cannot find this information" in ans.lower():
                        st.warning(ans)
                    else:
                        st.markdown(ans)
                    st.caption(f"⏱ Query time: {latency:.2f}s")

                    # Citations
                    if citations:
                        st.subheader("📖 Sources")
                        for cit in citations:
                            title = cit.get("paper_title") or cit.get("file", "Unknown")
                            authors = cit.get("authors", "")
                            year = cit.get("year", "")
                            section = cit.get("section", "")
                            page_start = cit.get("page_start")
                            page_end = cit.get("page_end")

                            if page_start and page_end and page_start != page_end:
                                page_str = f"Pages {page_start}–{page_end}"
                            elif page_start:
                                page_str = f"Page {page_start}"
                            else:
                                page_str = ""

                            meta_parts = [p for p in [authors, year, section, page_str] if p]
                            meta_str = " · ".join(meta_parts)
                            st.markdown(
                                f"- **{title}**"
                                + (f"  \n  _{meta_str}_" if meta_str else "")
                            )
                    elif sources:
                        st.subheader("📄 Source Files")
                        for s in sources:
                            st.markdown(f"- `{s}`")

                    # Retrieved chunks (expandable)
                    if chunks:
                        st.subheader("🔎 Retrieved Excerpts")
                        for idx, chunk in enumerate(chunks, 1):
                            meta = chunk.get("metadata", {})
                            title = meta.get("paper_title") or meta.get("file", "unknown")
                            section = meta.get("section", "")
                            page_start = meta.get("page_start", "?")
                            label = f"Excerpt {idx}: {title}"
                            if section:
                                label += f" — {section}"
                            if page_start:
                                label += f" (p. {page_start})"
                            with st.expander(label):
                                st.text(chunk.get("content", ""))
                                with st.expander("Metadata"):
                                    st.json(meta)
                else:
                    st.error(
                        f"Query error: {res.json().get('detail', 'Unknown error')}"
                    )
            except Exception as e:
                st.error(f"Could not connect to API: {e}")

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Manage Collections
# ---------------------------------------------------------------------------
st.header("3. Manage Collections")

try:
    all_repos = requests.get(f"{API_URL}/repository/", timeout=5).json()
except Exception:
    all_repos = []

if all_repos:
    STATUS_ICON = {
        "READY": "✅",
        "INDEXING": "⏳",
        "INDEXING_TIER0": "⏳",
        "INDEXING_TIER1": "⏳",
        "INDEXING_TIER2": "⏳",
        "FAILED": "❌",
        "DELETED": "🗑️",
    }
    for repo in all_repos:
        status = repo.get("status", "")
        icon = STATUS_ICON.get(status, "❓")

        col_a, col_b, col_c = st.columns([4, 3, 1])
        with col_a:
            st.markdown(
                f"{icon} **{repo['name']}**  \n"
                f"<small>ID: `{repo['repo_id']}`&nbsp;&nbsp;·&nbsp;&nbsp;"
                f"Status: **{status}**&nbsp;&nbsp;·&nbsp;&nbsp;"
                f"Indexed: {repo.get('indexed_at', 'N/A')}</small>",
                unsafe_allow_html=True,
            )
        with col_b:
            src = repo.get("source_path", "")
            if src:
                # Truncate very long paths gracefully
                display_src = src if len(src) <= 60 else "…" + src[-57:]
                st.markdown(
                    f"<small style='word-break:break-all'>`{display_src}`</small>",
                    unsafe_allow_html=True,
                )
        with col_c:
            if st.button("🗑 Delete", key=f"del_{repo['repo_id']}"):
                try:
                    del_res = requests.delete(
                        f"{API_URL}/repository/{repo['repo_id']}", timeout=10
                    )
                    if del_res.status_code == 200:
                        st.success(f"Deleted '{repo['name']}'.")
                        st.rerun()
                    else:
                        st.error(f"Delete failed: {del_res.text}")
                except Exception as e:
                    st.error(f"Error: {e}")
        st.divider()
else:
    st.info("No collections found. Index a folder above.")
