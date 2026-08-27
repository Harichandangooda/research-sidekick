from __future__ import annotations

import os
from html import escape
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

APP_TITLE = "Research Paper Sidekick"
APP_SUBTITLE = (
    "Ask a question, attach a paper if you have one, and let the coordinator "
    "route the work to the right research workflow."
)
API_BASE_URL = os.getenv("SIDEKICK_API_BASE_URL", "http://127.0.0.1:8000")

EXAMPLE_PROMPTS = [
    "Summarize this paper and explain the core contribution.",
    "Find recent papers that extend JEPA-style representation learning.",
    "Compare this paper with V-JEPA and identify practical differences.",
    "Suggest a reproduction plan with datasets, metrics, and milestones.",
]


def configure_page() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="R",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp { background: #f7f9fc; }
            .block-container {
                max-width: 1180px;
                padding-top: 2rem;
                padding-bottom: 2rem;
            }
            section[data-testid="stSidebar"] {
                background: #fbfcff;
                border-right: 1px solid #e5eaf2;
            }
            section[data-testid="stSidebar"] .stButton > button {
                background: transparent;
                border: 1px solid transparent;
                box-shadow: none;
                color: #475569;
                justify-content: flex-start;
                font-weight: 500;
            }
            section[data-testid="stSidebar"] .stButton > button:hover {
                background: #f1f5f9;
                border-color: #e2e8f0;
                color: #0f172a;
            }
            section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
                background: #e8eef8;
                border-color: #cbd7ea;
                color: #0f172a;
            }
            div[data-testid="stVerticalBlock"] > div:has(> .sidekick-card) {
                background: #ffffff;
                border: 1px solid #e5eaf2;
                border-radius: 8px;
                padding: 1.15rem;
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
            }
            .sidekick-card { height: 0; margin: 0; padding: 0; }
            .subtitle {
                color: #52627a;
                font-size: 1rem;
                margin-top: -0.45rem;
                margin-bottom: 1.2rem;
            }
            .muted { color: #64748b; font-size: 0.9rem; }
            .file-box {
                margin-top: 0.65rem;
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                border: 1px solid #e5eaf2;
                border-radius: 8px;
                background: #fbfdff;
                padding: 0.85rem 0.95rem;
            }
            .file-name { color: #0f172a; font-weight: 650; }
            .status { color: #15803d; font-weight: 700; }
            .upload-heading {
                color: #0f172a;
                font-weight: 750;
                margin-top: 1rem;
                margin-bottom: 0.15rem;
            }
            .upload-subtitle {
                color: #64748b;
                font-size: 0.9rem;
                margin-bottom: 0.55rem;
            }
            div[data-testid="stFileUploaderDropzone"] {
                align-items: center;
                background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
                border: 1px dashed #c7d2e5;
                border-radius: 8px;
                display: flex;
                justify-content: center;
                min-height: 175px;
                padding: 1.25rem;
                text-align: center;
            }
            .st-key-answer_response_container [data-testid="stMarkdownContainer"],
            .st-key-answer_response_container [data-testid="stMarkdownContainer"] p,
            .st-key-answer_response_container [data-testid="stMarkdownContainer"] li {
                max-width: 100%;
                overflow-wrap: anywhere;
                word-break: normal;
            }
            .st-key-answer_response_container [data-testid="stMarkdownContainer"] table,
            .st-key-answer_response_container [data-testid="stMarkdownContainer"] pre {
                display: block;
                max-width: 100%;
                overflow-x: auto;
            }
            .st-key-answer_response_container [data-testid="stMarkdownContainer"] img {
                height: auto;
                max-width: 100%;
            }
            .st-key-chat_history_container [data-testid="stMarkdownContainer"],
            .st-key-chat_history_container [data-testid="stMarkdownContainer"] p,
            .st-key-chat_history_container [data-testid="stMarkdownContainer"] li {
                max-width: 100%;
                overflow-wrap: anywhere;
                word-break: normal;
            }
            .st-key-chat_history_container [data-testid="stMarkdownContainer"] table,
            .st-key-chat_history_container [data-testid="stMarkdownContainer"] pre {
                display: block;
                max-width: 100%;
                overflow-x: auto;
            }
            .st-key-chat_history_container [data-testid="stMarkdownContainer"] img {
                height: auto;
                max-width: 100%;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_state() -> None:
    st.session_state.setdefault("access_token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("selected_paper_id", None)
    st.session_state.setdefault("selected_report_id", None)
    st.session_state.setdefault("prompt", "")
    st.session_state.setdefault("last_response", None)
    st.session_state.setdefault("editing_session_id", None)
    st.session_state.setdefault("deleting_session_id", None)


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{API_BASE_URL}{path}"
    headers = dict(kwargs.pop("headers", {}) or {})
    if st.session_state.get("access_token"):
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    try:
        response = requests.request(method, url, timeout=180, headers=headers, **kwargs)
        if response.status_code == 401:
            clear_auth_state()
            raise RuntimeError("Session expired. Please log in again.")
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Could not connect to backend at {API_BASE_URL}. Start it with "
            "`uv run uvicorn backend.main:app --reload`."
        ) from exc
    except requests.HTTPError as exc:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        raise RuntimeError(str(detail)) from exc

    if not response.content:
        return None
    return response.json()


def clear_auth_state() -> None:
    st.session_state.access_token = None
    st.session_state.user = None
    st.session_state.session_id = None
    st.session_state.selected_paper_id = None
    st.session_state.selected_report_id = None
    st.session_state.last_response = None
    st.session_state.editing_session_id = None
    st.session_state.deleting_session_id = None


def register(email: str, password: str) -> dict[str, Any]:
    return api_request("POST", "/auth/register", json={"email": email, "password": password})


def login(email: str, password: str) -> dict[str, Any]:
    return api_request("POST", "/auth/login", json={"email": email, "password": password})


def get_current_user() -> dict[str, Any]:
    return api_request("GET", "/auth/me")


def apply_auth(auth_response: dict[str, Any]) -> None:
    st.session_state.access_token = auth_response["access_token"]
    st.session_state.user = auth_response["user"]
    st.session_state.session_id = None
    st.session_state.selected_paper_id = None
    st.session_state.selected_report_id = None
    st.session_state.last_response = None


def create_session() -> dict[str, Any]:
    return api_request("POST", "/sessions")


def list_sessions() -> list[dict[str, Any]]:
    return api_request("GET", "/sessions")


def rename_session(session_id: str, title: str) -> dict[str, Any]:
    return api_request("PATCH", f"/sessions/{session_id}", json={"title": title})


def delete_session(session_id: str) -> None:
    api_request("DELETE", f"/sessions/{session_id}")


def list_messages(session_id: str) -> list[dict[str, Any]]:
    return api_request("GET", f"/sessions/{session_id}/messages")


def list_papers(session_id: str) -> list[dict[str, Any]]:
    return api_request("GET", f"/sessions/{session_id}/papers")


def list_reports(session_id: str) -> list[dict[str, Any]]:
    return api_request("GET", f"/sessions/{session_id}/reports")


def get_report(report_id: int) -> dict[str, Any]:
    return api_request("GET", f"/reports/{report_id}")


def upload_paper(session_id: str, uploaded_file: Any) -> dict[str, Any]:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/pdf",
        )
    }
    return api_request("POST", f"/sessions/{session_id}/papers", files=files)


def run_sidekick(session_id: str, prompt: str, paper_id: int | None) -> dict[str, Any]:
    payload = {"prompt": prompt, "paper_id": paper_id}
    return api_request("POST", f"/sessions/{session_id}/chat", json=payload)


def ensure_session() -> bool:
    try:
        sessions = list_sessions()
        if st.session_state.session_id is None:
            if sessions:
                st.session_state.session_id = sessions[0]["id"]
            else:
                session = create_session()
                st.session_state.session_id = session["id"]
        return True
    except RuntimeError as exc:
        st.error(str(exc))
        return False


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def set_prompt(prompt: str) -> None:
    st.session_state.prompt = prompt


def activate_session(session_id: str) -> None:
    st.session_state.session_id = session_id
    st.session_state.selected_paper_id = None
    st.session_state.selected_report_id = None
    st.session_state.last_response = None
    st.session_state.editing_session_id = None
    st.session_state.deleting_session_id = None


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Research Paper Sidekick")
        if st.session_state.user:
            st.caption(st.session_state.user["email"])
        if st.button("Logout", use_container_width=True):
            clear_auth_state()
            st.rerun()

        st.divider()

        if st.button("+ New Session", use_container_width=True):
            try:
                session = create_session()
                activate_session(session["id"])
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

        st.divider()

        try:
            sessions = list_sessions()
            if sessions:
                st.markdown("### Conversations")
                for session in sessions:
                    session_id = session["id"]
                    is_active = session_id == st.session_state.session_id
                    title_col, rename_col, delete_col = st.columns(
                        [0.72, 0.14, 0.14], gap="small"
                    )
                    with title_col:
                        label = f"● {session['title']}" if is_active else session["title"]
                        if st.button(
                            label,
                            key=f"open_session_{session_id}",
                            type="primary" if is_active else "secondary",
                            use_container_width=True,
                            help=session["title"],
                        ):
                            activate_session(session_id)
                            st.rerun()
                    with rename_col:
                        if st.button(
                            "✎",
                            key=f"rename_session_{session_id}",
                            help=f"Rename {session['title']}",
                        ):
                            st.session_state.editing_session_id = session_id
                            st.session_state.deleting_session_id = None
                            st.rerun()
                    with delete_col:
                        if st.button(
                            "×",
                            key=f"delete_session_{session_id}",
                            help=f"Delete {session['title']}",
                        ):
                            st.session_state.deleting_session_id = session_id
                            st.session_state.editing_session_id = None
                            st.rerun()

                    if st.session_state.editing_session_id == session_id:
                        with st.form(f"rename_form_{session_id}"):
                            new_title = st.text_input(
                                "Conversation title",
                                value=session["title"],
                                max_chars=80,
                            )
                            save_col, cancel_col = st.columns(2)
                            save_rename = save_col.form_submit_button(
                                "Save", use_container_width=True
                            )
                            cancel_rename = cancel_col.form_submit_button(
                                "Cancel", use_container_width=True
                            )
                        if save_rename:
                            try:
                                rename_session(session_id, new_title)
                                st.session_state.editing_session_id = None
                                st.rerun()
                            except RuntimeError as exc:
                                st.error(str(exc))
                        if cancel_rename:
                            st.session_state.editing_session_id = None
                            st.rerun()

                    if st.session_state.deleting_session_id == session_id:
                        st.warning(f"Delete “{session['title']}” and its contents?")
                        confirm_col, cancel_col = st.columns(2)
                        if confirm_col.button(
                            "Delete",
                            key=f"confirm_delete_{session_id}",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                delete_session(session_id)
                                remaining = [
                                    item for item in sessions if item["id"] != session_id
                                ]
                                if is_active:
                                    if remaining:
                                        activate_session(remaining[0]["id"])
                                    else:
                                        replacement = create_session()
                                        activate_session(replacement["id"])
                                st.session_state.deleting_session_id = None
                                st.rerun()
                            except RuntimeError as exc:
                                st.error(str(exc))
                        if cancel_col.button(
                            "Cancel",
                            key=f"cancel_delete_{session_id}",
                            use_container_width=True,
                        ):
                            st.session_state.deleting_session_id = None
                            st.rerun()

            if st.session_state.session_id is None:
                return

            papers = list_papers(st.session_state.session_id)
            if papers:
                paper_ids = [paper["id"] for paper in papers]
                current_paper = (
                    paper_ids.index(st.session_state.selected_paper_id)
                    if st.session_state.selected_paper_id in paper_ids
                    else 0
                )
                selected_paper_id = st.selectbox(
                    "Active Paper",
                    options=paper_ids,
                    index=current_paper,
                    format_func=lambda pid: next(
                        paper["file_name"] for paper in papers if paper["id"] == pid
                    ),
                )
                st.session_state.selected_paper_id = selected_paper_id
            else:
                st.caption("No papers uploaded in this session yet.")

            st.markdown("### Saved Reports")
            reports = list_reports(st.session_state.session_id)
            if reports:
                report_ids = [report["id"] for report in reports]
                current_report = (
                    report_ids.index(st.session_state.selected_report_id)
                    if st.session_state.selected_report_id in report_ids
                    else 0
                )
                selected_report_id = st.selectbox(
                    "Reports",
                    options=report_ids,
                    index=current_report,
                    format_func=lambda rid: next(
                        report["title"] for report in reports if report["id"] == rid
                    ),
                )
                st.session_state.selected_report_id = selected_report_id
            else:
                st.caption("No saved reports yet.")
        except RuntimeError as exc:
            st.error(str(exc))


def render_header() -> None:
    st.title(APP_TITLE)
    st.markdown(f'<div class="subtitle">{APP_SUBTITLE}</div>', unsafe_allow_html=True)


def render_auth_screen() -> None:
    render_header()
    st.markdown('<div class="sidekick-card"></div>', unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
        if submitted:
            try:
                auth_response = login(email, password)
                apply_auth(auth_response)
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

    with register_tab:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        if submitted:
            try:
                auth_response = register(email, password)
                apply_auth(auth_response)
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))


def render_input_card() -> None:
    st.markdown('<div class="sidekick-card"></div>', unsafe_allow_html=True)
    st.subheader("Ask Sidekick")

    prompt = st.text_area(
        "Research request",
        key="prompt",
        height=150,
        placeholder=(
            "Ask about a paper, topic, method, benchmark, or experiment plan...\n\n"
            "Example: Find recent papers that extend JEPA and suggest which one I should reproduce."
        ),
        label_visibility="collapsed",
    )

    with st.expander("Example prompts"):
        for index, example in enumerate(EXAMPLE_PROMPTS):
            st.button(
                example,
                key=f"example_{index}",
                on_click=set_prompt,
                args=(example,),
                use_container_width=True,
            )

    st.markdown(
        """
        <div class="upload-heading">Upload Paper (Optional)</div>
        <div class="upload-subtitle">Drag and drop a PDF here, or browse files.</div>
        """,
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Drag & drop a PDF here",
        type=["pdf"],
        accept_multiple_files=False,
        label_visibility="collapsed",
    )

    if uploaded_file is not None and st.button("Upload and Index PDF", use_container_width=True):
        try:
            with st.spinner("Parsing and indexing paper..."):
                uploaded = upload_paper(st.session_state.session_id, uploaded_file)
            st.session_state.selected_paper_id = uploaded["paper_id"]
            st.success(f"Indexed {uploaded['chunk_count']} chunks for retrieval.")
            render_uploaded_file(uploaded["file_name"], uploaded["file_size"])
        except RuntimeError as exc:
            st.error(f"Could not upload this PDF: {exc}")

    run_clicked = st.button("Run Sidekick", type="primary", use_container_width=True)
    if run_clicked:
        if not prompt.strip():
            st.warning("Enter a research request first.")
            return
        try:
            with st.spinner("Running coordinator..."):
                result = run_sidekick(
                    st.session_state.session_id,
                    prompt.strip(),
                    st.session_state.selected_paper_id,
                )
            st.session_state.last_response = result["response"]
            st.session_state.selected_report_id = result.get("report_id")
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))


def render_uploaded_file(file_name: str, file_size: int) -> None:
    st.markdown(
        f"""
        <div class="file-box">
            <div>
                <div class="file-name">{escape(file_name)}</div>
                <div class="muted">{escape(format_file_size(file_size))}</div>
            </div>
            <div class="status">Attached</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat() -> None:
    try:
        messages = list_messages(st.session_state.session_id)
    except RuntimeError as exc:
        st.error(str(exc))
        return

    with st.container(
        height=520,
        border=True,
        key="chat_history_container",
    ):
        if not messages:
            st.info("No messages in this conversation yet.")
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    follow_up = st.chat_input("Ask a follow-up about this research session...")
    if follow_up:
        try:
            with st.spinner("Running coordinator..."):
                result = run_sidekick(
                    st.session_state.session_id,
                    follow_up,
                    st.session_state.selected_paper_id,
                )
            st.session_state.last_response = result["response"]
            st.session_state.selected_report_id = result.get("report_id")
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))


def render_output_card() -> None:
    st.markdown('<div class="sidekick-card"></div>', unsafe_allow_html=True)
    st.subheader("Workspace")

    answer_tab, papers_tab, reports_tab, chat_tab = st.tabs(
        ["Answer", "Papers", "Reports", "Chat"]
    )

    with answer_tab:
        with st.container(
            height=520,
            border=True,
            key="answer_response_container",
        ):
            if st.session_state.selected_report_id is not None:
                try:
                    report = get_report(st.session_state.selected_report_id)
                    st.success("Report generated successfully.")
                    st.subheader(report["title"])
                    st.caption(report["created_at"])
                    st.markdown(report["content"])
                except RuntimeError as exc:
                    st.error(str(exc))
            elif st.session_state.last_response:
                st.markdown(st.session_state.last_response)
            else:
                st.info("Run Sidekick to preview the workspace.")

    with papers_tab:
        render_papers()

    with reports_tab:
        render_reports()

    with chat_tab:
        render_chat()


def render_papers() -> None:
    try:
        papers = list_papers(st.session_state.session_id)
    except RuntimeError as exc:
        st.error(str(exc))
        return

    if not papers:
        st.info("No papers uploaded in this session yet.")
        return

    for paper in papers:
        st.markdown(
            f"**{paper['file_name']}**  \n"
            f"{format_file_size(paper['file_size'])} | {paper['created_at']}"
        )


def render_reports() -> None:
    try:
        reports = list_reports(st.session_state.session_id)
    except RuntimeError as exc:
        st.error(str(exc))
        return

    if not reports:
        st.info("No saved reports yet.")
        return

    for report in reports:
        with st.expander(report["title"]):
            st.caption(report["created_at"])
            st.markdown(report["content"])


def main() -> None:
    configure_page()
    inject_styles()
    initialize_state()

    if st.session_state.access_token and st.session_state.user is None:
        try:
            st.session_state.user = get_current_user()
        except RuntimeError:
            clear_auth_state()

    if st.session_state.access_token is None:
        render_auth_screen()
        return

    if not ensure_session():
        return

    render_sidebar()
    render_header()

    input_col, output_col = st.columns([0.95, 1.05], gap="large")
    with input_col:
        render_input_card()

    with output_col:
        render_output_card()


if __name__ == "__main__":
    main()
