from __future__ import annotations

import re

from backend.agents.sidekick import run_analysis
from backend.services.rag_service import retrieve_relevant_chunks
from backend.storage import session_store


def title_from_prompt(prompt: str, max_length: int = 60) -> str:
    title = re.sub(r"\s+", " ", prompt).strip()
    if len(title) <= max_length:
        return title
    return f"{title[: max_length - 3].rstrip(' ,.;:-')}..."


def build_agent_input(session_id: str, prompt: str, paper_id: int | None = None) -> str:
    recent_messages = session_store.get_recent_messages(session_id, limit=8)
    chat_context = "\n\n".join(
        f"{message['role'].upper()}:\n{message['content']}" for message in recent_messages
    )

    user_input = f"""
Recent Conversation:
{chat_context}

User Request:
{prompt}
""".strip()

    if paper_id is not None:
        chunks = retrieve_relevant_chunks(paper_id=paper_id, query=prompt, top_k=5)
        relevant_context = "\n\n---\n\n".join(chunks)
        user_input += f"""

Relevant Paper Context:
{relevant_context}
"""

    return user_input


def run_chat(session_id: str, prompt: str, paper_id: int | None = None) -> dict:
    user_input = build_agent_input(session_id, prompt, paper_id)
    session_store.set_initial_session_title(session_id, title_from_prompt(prompt))
    session_store.save_message(session_id, "user", prompt)

    result = run_analysis(user_input)
    response = result.final_output

    session_store.save_message(session_id, "assistant", response)
    report_title = prompt[:80] if prompt else "Generated Report"
    report_id = session_store.save_report(session_id, report_title, response)

    return {"response": response, "report_id": report_id}
