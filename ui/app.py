"""
DocumentRAG — Research Paper Q&A Interface.
Streamlit UI for uploading research paper collections and asking questions.

Workflow:
  1. User specifies a folder path containing PDFs.
  2. System indexes folder as an isolated collection.
  3. User selects a collection and asks questions.
  4. System answers with inline citations (paper, section, page).

Preserved infrastructure:
  - Progress bar with stage/ETA display
  - Collection list and selection
  - Chunk inspection expanders
  - API polling loop
"""

import streamlit as st
import requests
import time
import os

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DocumentRAG — Research Paper Q&A",
    page_icon="📚",
    layout="wide",
)

st.title("📚 DocumentRAG — Research Paper Q&A")
st.caption("Upload a folder of research papers. Ask questions. Get cited answers — locally, privately.")

API_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Sidebar: System status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ System")
    try:
        health = requests.get(f"{API_URL}/health", timeout=2).json()
        st.success(f"API: {health.get('status', 'ok').upper()}")
    except Exception:
        st.error("API offline — start with: uvicorn api.main:app --port 8000")

    st.divider()
    st.markdown(
        "**How to use:**\n"
        "1. Enter the path to a folder of PDFs\n"
        "2. Click **Index Collection**\n"
        "3. Select the collection\n"
        "4. Ask any question about the papers\n"
        "5. Answers include citations"
    )

# ---------------------------------------------------------------------------
# Section 1: Upload and Index a Folder
# ---------------------------------------------------------------------------
st.header("1. Index a Research Paper Collection")

col1, col2 = st.columns([3, 1])
with col1:
    folder_path = st.text_input(
        "Folder path containing PDF research papers",
        placeholder="e.g.  C:\\Users\\you\\papers  or  /home/you/papers",
        key="folder_path_input",
    )
with col2:
    st.write("")
    st.write("")
    index_btn = st.button("📥 Index Collection", use_container_width=True)

if index_btn:
    if not folder_path:
        st.warning("Please enter a folder path.")
    else:
        abs_path = os.path.abspath(folder_path)
        if not os.path.exists(abs_path):
            st.error(f"Path does not exist: `{abs_path}`")
        elif not os.path.isdir(abs_path):
            st.error(f"Path is not a directory: `{abs_path}`")
        else:
            # Count PDFs
            pdf_count = sum(
                1 for _, _, fs in os.walk(abs_path)
                for f in fs if f.lower().endswith(".pdf")
            )
            if pdf_count == 0:
                st.warning("No PDF files found in the specified folder.")
            else:
                collection_name = os.path.basename(abs_path) or "collection"
                st.info(
                    f"Found **{pdf_count} PDF(s)** in `{abs_path}`. "
                    f"Registering as collection **'{collection_name}'**..."
                )

                try:
                    # Register collection → triggers background indexing
                    res = requests.post(
                        f"{API_URL}/repository/",
                        json={
                            "name": collection_name,
                            "branch": "main",
                            "source_path": abs_path,
                        },
                        timeout=10,
                    )

                    if res.status_code == 200:
                        repo_data = res.json()
                        repo_id = repo_data["repo_id"]
                        st.info(
                            f"Collection registered (ID: `{repo_id}`). Indexing started…"
                        )

                        # Progress display
                        progress_bar = st.progress(0.0)
                        status_text = st.empty()
                        metrics_text = st.empty()

                        while True:
                            time.sleep(1.5)
                            try:
                                status_res = requests.get(
                                    f"{API_URL}/indexing/status/{repo_id}",
                                    timeout=5,
                                )
                            except Exception:
                                st.error("Lost connection to API during indexing.")
                                break

                            if status_res.status_code != 200:
                                st.error(f"Status error: {status_res.text}")
                                break

                            status_data = status_res.json()
                            stage = status_data.get("stage", "")
                            percentage = status_data.get("percentage", 0.0)
                            files_processed = status_data.get("files_processed", 0)
                            files_total = status_data.get("files_total", 0)
                            chunks_processed = status_data.get("chunks_processed", 0)
                            chunks_total = status_data.get("chunks_total", 0)
                            embedding_rate = status_data.get("embedding_rate", 0.0)
                            eta_seconds = status_data.get("eta_seconds", -1.0)
                            status = status_data.get("status", "")

                            progress_bar.progress(
                                min(1.0, max(0.0, percentage / 100.0))
                            )
                            eta_str = (
                                f"{eta_seconds:.0f}s"
                                if eta_seconds >= 0
                                else "estimating…"
                            )
                            status_text.markdown(
                                f"**Stage:** {stage.upper()} · **Status:** {status}"
                            )
                            metrics_text.markdown(
                                f"- **Progress:** {percentage:.1f}%\n"
                                f"- **Papers parsed:** {files_processed} / {files_total}\n"
                                f"- **Chunks embedded:** {chunks_processed} / {chunks_total}\n"
                                f"- **Embedding rate:** {embedding_rate:.1f} chunks/s\n"
                                f"- **ETA:** {eta_str}"
                            )

                            if status == "READY" or stage == "completed":
                                progress_bar.progress(1.0)
                                st.success(
                                    f"✅ Collection **'{collection_name}'** indexed "
                                    f"({chunks_total} chunks). Ready to query!"
                                )
                                break
                            elif status == "FAILED" or stage == "failed":
                                st.error(
                                    f"❌ Indexing failed for collection **'{collection_name}'**."
                                )
                                break
                    else:
                        st.error(
                            f"Failed to register collection: "
                            f"{res.json().get('detail', 'Unknown error')}"
                        )
                except Exception as e:
                    st.error(f"Could not connect to API: {e}")

st.divider()

# ---------------------------------------------------------------------------
# Section 2: Query
# ---------------------------------------------------------------------------
st.header("2. Ask a Question")

# Fetch available collections
try:
    repos_res = requests.get(f"{API_URL}/repository/", timeout=5)
    repos_list = repos_res.json() if repos_res.status_code == 200 else []
except Exception:
    repos_list = []

# Filter to READY collections only
ready_repos = [
    r for r in repos_list
    if r.get("status") in ("READY", "INDEXING_TIER1", "INDEXING_TIER2")
]

selected_repo_id = None
if ready_repos:
    repo_options = {
        f"📄 {r['name']}  (ID: {r['repo_id'][:8]}…)": r["repo_id"]
        for r in ready_repos
    }
    col_q1, col_q2 = st.columns([2, 1])
    with col_q1:
        selected_repo_name = st.selectbox(
            "Select collection to query",
            list(repo_options.keys()),
            key="collection_select",
        )
        selected_repo_id = repo_options[selected_repo_name]
    with col_q2:
        st.write("")
        st.write("")
        st.info(f"ID: `{selected_repo_id}`")
else:
    st.info(
        "No indexed collections available. Index a folder above to get started."
    )

question = st.text_area(
    "Your question",
    placeholder="e.g. What method does the paper use for data augmentation?",
    height=100,
    key="question_input",
)

ask_btn = st.button("🔍 Ask", use_container_width=False, disabled=(not ready_repos))

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

                            page_str = ""
                            if page_start and page_end and page_start != page_end:
                                page_str = f"Pages {page_start}–{page_end}"
                            elif page_start:
                                page_str = f"Page {page_start}"

                            meta_parts = [p for p in [authors, year, section, page_str] if p]
                            meta_str = " · ".join(meta_parts)

                            st.markdown(f"- **{title}**" + (f"  \n  _{meta_str}_" if meta_str else ""))
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
# Section 3: Manage Collections
# ---------------------------------------------------------------------------
st.header("3. Manage Collections")

try:
    all_repos = requests.get(f"{API_URL}/repository/", timeout=5).json()
except Exception:
    all_repos = []

if all_repos:
    for repo in all_repos:
        status = repo.get("status", "")
        status_icon = {
            "READY": "✅",
            "INDEXING": "⏳",
            "INDEXING_TIER0": "⏳",
            "INDEXING_TIER1": "⏳",
            "INDEXING_TIER2": "⏳",
            "FAILED": "❌",
            "DELETED": "🗑️",
        }.get(status, "❓")

        col_a, col_b, col_c = st.columns([4, 2, 1])
        with col_a:
            st.markdown(
                f"{status_icon} **{repo['name']}**  \n"
                f"<small>ID: `{repo['repo_id']}`  "
                f"· Status: **{status}**  "
                f"· Indexed at: {repo.get('indexed_at', 'N/A')}</small>",
                unsafe_allow_html=True,
            )
        with col_b:
            if repo.get("source_path"):
                st.markdown(
                    f"<small>`{repo['source_path']}`</small>",
                    unsafe_allow_html=True,
                )
        with col_c:
            if st.button("🗑 Delete", key=f"del_{repo['repo_id']}"):
                try:
                    del_res = requests.delete(
                        f"{API_URL}/repository/{repo['repo_id']}", timeout=10
                    )
                    if del_res.status_code == 200:
                        st.success(f"Deleted collection '{repo['name']}'.")
                        st.rerun()
                    else:
                        st.error(f"Delete failed: {del_res.text}")
                except Exception as e:
                    st.error(f"Error: {e}")
        st.divider()
else:
    st.info("No collections found. Index a folder above.")
