"""
state.py — Shared state definition for the CricketIQ agent graph.

CONCEPT: State is a TypedDict that flows through the graph.
         Every node reads from it and writes to it.
         Think of it as a shared clipboard all agents pass around.
"""
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class CricketIQState(TypedDict):
    # Messages (conversation/reasoning history)
    messages: Annotated[list, add_messages]

    # Data pipeline state
    matches_fetched: list[dict]
    validation_result: dict
    weather_data: list[dict]

    # ML state
    predictions: list[dict]
    explanations: list[dict]

    # Content state
    reports: list[dict]

    # Control flow
    current_task: str
    errors: list[str]
    should_continue: bool
