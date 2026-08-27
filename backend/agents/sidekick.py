from __future__ import annotations

from agents import Agent, Runner

from backend.agents.tools import get_tools

COORDINATOR_INSTRUCTION = """You are the coordinator for a research paper assistant. Your responsibility is to understand the user's request, determine which specialist tools are needed, invoke them in the appropriate order, and synthesize their outputs into a clear, well-structured final report. Use the Search Agent to discover relevant papers, the Paper Analysis Agent to analyze uploaded or selected papers, and the Experiment Planner Agent to create implementation and reproduction plans. Invoke only the tools necessary for the user's request, avoid redundant tool calls, and combine their outputs into a coherent response. If the user's request is ambiguous or lacks sufficient information, ask for clarification before proceeding."""

coordinator_agent = Agent(
    name="Coordinator",
    instructions=COORDINATOR_INSTRUCTION,
    tools=get_tools(),
    model="gpt-5",
)


def run_analysis(user_input: str):
    return Runner.run_sync(coordinator_agent, user_input)

