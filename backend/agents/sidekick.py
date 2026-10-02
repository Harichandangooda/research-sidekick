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
    # Acquisition is handled explicitly before analysis; the coordinator cannot
    # accidentally search when the user only supplied files.
    agent = coordinator_agent.clone(
        instructions=COORDINATOR_INSTRUCTION.replace("Use the Search Agent to discover relevant papers, ", "Use ")
        + "\nDiscovery is handled before this call. Use provided paper context. For discovered papers, distinguish summary-based observations from claims requiring full-text evidence.",
        tools=[tool for tool in get_tools() if tool.name != "search_agent"],
    )
    return Runner.run_sync(agent, user_input)

