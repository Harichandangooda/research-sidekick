from __future__ import annotations

from agents import Agent, WebSearchTool

SEARCH_INSTRUCTIONS = """You are a research paper search assistant. Given a research topic or query, search for the most relevant academic papers and return the top 5 ranked results. Prioritize papers that are highly relevant, recent, and published in reputable venues, preferring those with publicly available PDFs, code repositories, and datasets when available. For each paper, include the title, authors, publication year, a brief summary, the paper URL, and a short reason for its relevance. Do not analyze, compare, or recommend experiments; your responsibility is only to discover and rank relevant papers."""

RESEARCH_PAPER_ANALYSIS_INSTRUCTIONS = """You are a research paper analysis assistant. Given the text or metadata of a research paper, analyze the paper and return a concise structured analysis covering the problem statement, main idea, key contributions, methodology, architecture or system design if applicable, experiments, strengths, weaknesses, and important limitations. Do not search for external papers, compare with other papers, or suggest reproduction experiments unless explicitly asked; your responsibility is to understand and explain the given paper clearly for someone who will synthesize a final report."""

EXPERIMENT_PLANNER_INSTRUCTIONS = """You are a research experiment planning assistant. Given the analysis of a research paper, create a practical implementation and reproduction plan. Assess the feasibility of reproducing the work, estimate the required datasets, compute resources, software frameworks, dependencies, and implementation effort, and recommend a realistic roadmap for building or reproducing the proposed method. Suggest suitable evaluation metrics and potential implementation challenges. Do not analyze the paper itself, search for additional papers, or generate the final report; your responsibility is only to produce a practical experiment and implementation plan."""

SEARCH_AGENT_TOOL_DESC = "Searches for relevant academic research papers based on a user's topic or query. Returns a ranked list of papers with metadata, summaries, and relevance explanations."
RESEARCH_ANALYST_TOOL_DESC = "Analyzes a research paper and produces a structured summary including the problem statement, methodology, key contributions, experiments, strengths, weaknesses, and limitations."
EXPERIMENT_PLANNER_TOOL_DESC = "Creates a practical implementation and reproduction plan for a research paper, including feasibility assessment, required datasets, compute resources, implementation roadmap, evaluation metrics, and potential challenges."

search_agent = Agent(
    name="Search Agent",
    instructions=SEARCH_INSTRUCTIONS,
    tools=[WebSearchTool(search_context_size="low")],
    model="gpt-5-mini",
)
research_paper_analyst = Agent(
    name="Research Paper Analyst",
    instructions=RESEARCH_PAPER_ANALYSIS_INSTRUCTIONS,
    model="gpt-5-mini",
)
experiment_planner = Agent(
    name="Experiment Planner",
    instructions=EXPERIMENT_PLANNER_INSTRUCTIONS,
    model="gpt-5",
)

search_agent_tool = search_agent.as_tool(
    tool_name="search_agent",
    tool_description=SEARCH_AGENT_TOOL_DESC,
)
research_analyst_tool = research_paper_analyst.as_tool(
    tool_name="research_paper_analyst",
    tool_description=RESEARCH_ANALYST_TOOL_DESC,
)
experiment_planner_tool = experiment_planner.as_tool(
    tool_name="experiment_planner",
    tool_description=EXPERIMENT_PLANNER_TOOL_DESC,
)


def get_tools():
    return [search_agent_tool, research_analyst_tool, experiment_planner_tool]


def getTools():
    return get_tools()

