"""Structured discovery using the existing academic search agent and tracing."""
from agents import Runner
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, field_validator

from backend.agents.tools import search_agent
from backend.storage import session_store


class DiscoveredPaper(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    authors: str = Field(max_length=2000)
    year: int | None
    summary: str = Field(max_length=10000)
    # HttpUrl emits format="uri", which OpenAI Structured Outputs rejects.
    url: str
    relevance: float = Field(ge=0, le=1)
    relevance_reason: str = Field(max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return str(TypeAdapter(HttpUrl).validate_python(value))


class SearchResults(BaseModel):
    papers: list[DiscoveredPaper] = Field(max_length=10)


def discover_papers(session_id: str, prompt: str) -> list[dict]:
    agent = search_agent.clone(
        output_type=SearchResults,
        instructions=search_agent.instructions + "\nFor this structured acquisition call, return up to 10 candidate academic papers when available, with a relevance score from 0 to 1 for each. Score by relevance to the user's prompt. Only return verified paper URLs; do not invent results.",
    )
    result = Runner.run_sync(agent, prompt).final_output
    ranked = sorted(result.papers, key=lambda paper: paper.relevance, reverse=True)
    selected = []
    seen = set()
    for paper in ranked:
        if str(paper.url) in seen:
            continue
        seen.add(str(paper.url))
        selected.append(paper)
        if len(selected) == 5:
            break
    saved = []
    for paper in selected:
        paper_id = session_store.save_discovered_paper(session_id, paper.model_dump(mode="json"))
        saved.append({"id": paper_id, **paper.model_dump(mode="json")})
    return saved
