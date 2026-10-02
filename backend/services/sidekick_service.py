from __future__ import annotations

import re
import hashlib
import json
from threading import Lock

from backend.agents.sidekick import run_analysis
from backend.services.rag_service import retrieve_relevant_chunks, retrieve_relevant_session_chunks
from backend.storage import session_store
from backend.services.discovery_service import discover_papers
from backend.limits import MAX_AGENT_INPUT_CHARACTERS, MAX_PROMPT_CHARACTERS

# Serialize turns in a session in this local, single-process server. A bounded
# pool avoids retaining one lock for every session ever created.
_session_locks = [Lock() for _ in range(64)]


def requests_external_research(prompt: str) -> bool:
    # Require an explicit discovery action; comparisons alone do not opt in.
    clauses = re.split(r"[.!?;\n]+", prompt.lower())
    for clause in clauses:
        if re.search(r"\b(?:do not|don't|no|without|never)\b.*\b(?:search|find|look|research|discover|browse)\b", clause):
            continue
        if re.search(r"\b(?:search|find|discover|look up|look for|browse)\b.*\b(?:online|web|external|internet)\b", clause):
            return True
        if re.search(r"\b(?:search|find|discover|look up|look for|browse)\s+(?:(?:for|the|some|more|new|additional|other|recent|latest|relevant|related|similar|academic|research|scholarly|published)\s+)*(?:papers|studies|literature|related work)\b", clause):
            return True
        if re.search(r"\b(?:conduct|perform|do|include|use)\b.*\b(?:external|online|web)\s+research\b", clause):
            return True
        if re.search(r"\b(?:research externally|research online|external research|online research)\b", clause):
            return True
    return False


def title_from_prompt(prompt: str, max_length: int = 60) -> str:
    title = re.sub(r"\s+", " ", prompt).strip()
    if len(title) <= max_length:
        return title
    return f"{title[: max_length - 3].rstrip(' ,.;:-')}..."


def build_agent_input(session_id: str, prompt: str, paper_id: int | None = None,
                      discovered_ids: tuple[int, ...] = ()) -> str:
    recent_messages = session_store.get_recent_messages(session_id, limit=8)
    history = []
    remaining = 12_000
    for message in reversed(recent_messages):
        entry = f"{message['role'].upper()}:\n{message['content']}"
        if len(entry) > remaining:
            if remaining > 100:
                history.append(entry[:remaining - 30] + "\n[History truncated]")
            break
        history.append(entry)
        remaining -= len(entry) + 2
    user_input = f"User Request:\n{prompt}\n\nRecent Conversation:\n" + "\n\n".join(reversed(history))
    papers = session_store.get_papers(session_id)
    if paper_id is not None:
        if not any(paper["id"] == paper_id for paper in papers):
            raise ValueError("Paper not found for this session")
        papers = [paper for paper in papers if paper["id"] == paper_id or paper["id"] in discovered_ids]
    contexts = []
    uploads = {paper["id"]: paper for paper in papers if paper["source"] == "uploaded_pdf"}
    if paper_id in uploads:
        chunks = retrieve_relevant_chunks(paper_id=paper_id, query=prompt, top_k=5)
        if chunks:
            contexts.append((uploads[paper_id], "\n\n---\n\n".join(chunks)))
    elif paper_id is None and uploads:
        evidence = retrieve_relevant_session_chunks(session_id, prompt, list(uploads), top_k=5)
        grouped = {}
        for chunk in evidence[:5]:
            if chunk["paper_id"] in uploads and chunk["text"]:
                grouped.setdefault(chunk["paper_id"], []).append(chunk["text"])
        contexts.extend((uploads[identifier], "\n\n---\n\n".join(chunks)) for identifier, chunks in grouped.items())
    for paper in papers:
        if paper["source"] == "online_discovery" and (paper["id"] == paper_id or paper["id"] in discovered_ids):
            context = json.dumps({key: paper.get(key) for key in
                                  ("title", "authors", "year", "url", "relevance", "relevance_reason", "summary")},
                                 ensure_ascii=False)
            contexts.append((paper, context))
    if not contexts:
        return user_input
    per_paper = (MAX_AGENT_INPUT_CHARACTERS - len(user_input)) // len(contexts)
    for paper, context in contexts:
        if paper["source"] == "online_discovery":
            header = f"\n\nDiscovered Paper: {paper['file_name'][:300]}\nMetadata and summary only; full text has not been retrieved.\n"
        else:
            header = f"\n\nUploaded Paper: {paper['file_name'][:300]}\n"
        allowance = max(0, per_paper - len(header))
        if len(context) > allowance:
            marker = "\n[Paper context truncated]"
            context = context[:max(0, allowance - len(marker))] + marker
        user_input += header + context
    return user_input


def run_chat(session_id: str, prompt: str, paper_id: int | None = None,
             upload_attempted: bool = False, request_id: str | None = None) -> dict:
    with _session_locks[hash(session_id) % len(_session_locks)]:
        return _run_chat(session_id, prompt, paper_id, upload_attempted, request_id)


def _run_chat(session_id: str, prompt: str, paper_id: int | None,
              upload_attempted: bool, request_id: str | None) -> dict:
    if len(prompt) > MAX_PROMPT_CHARACTERS:
        raise ValueError("Prompts must be 10,000 characters or fewer")
    prompt = prompt.strip()
    fingerprint = hashlib.sha256(json.dumps([prompt, paper_id, upload_attempted]).encode()).hexdigest()
    if request_id:
        cached = session_store.get_chat_request(session_id, request_id, fingerprint)
        if cached:
            return cached
    papers = session_store.get_papers(session_id)
    uploads = [paper for paper in papers if paper["source"] == "uploaded_pdf"]
    if not prompt:
        if not uploads:
            raise ValueError("Please enter a prompt or upload at least one file.")
        return {"response": f"{len(uploads)} uploaded paper(s) indexed and associated with this session.", "report_id": None}
    discovered = []
    if (not uploads and not upload_attempted and paper_id is None) or requests_external_research(prompt):
        discovered = discover_papers(session_id, prompt)
    user_input = build_agent_input(session_id, prompt, paper_id, tuple(paper["id"] for paper in discovered))
    result = run_analysis(user_input)
    response = result.final_output
    return session_store.save_chat_result(session_id, prompt, response, title_from_prompt(prompt),
                                          request_id, fingerprint)
