"""
validation_graph.py — Validation Agent as a LangGraph graph with human-in-the-loop.

CONCEPTS TAUGHT:
  1. interrupt_before — pausing the graph for human approval
  2. Conditional edges — routing based on validation status
  3. State management — passing validation results through the graph
  4. Resuming a graph after interruption

The graph flow:
  validate_matches → [if flagged] → INTERRUPT → human_review → route
                   → [if all valid] → pass_through → END
                   → [if rejected] → handle_rejected → END
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import json

load_dotenv()

from agents.validation_agent import validate_match, pre_validate_match
from src.models import ValidationStatus, MatchValidationResult
from tools.database import query_database


# ─────────────────────────────────────────────────
# State for the validation graph
# ─────────────────────────────────────────────────

class ValidationGraphState(TypedDict):
    messages: Annotated[list, add_messages]

    # Input
    matches_to_validate: list[dict]

    # Validation results
    valid_matches: list[dict]
    flagged_matches: list[dict]
    rejected_matches: list[dict]
    validation_results: list[dict]

    # Human review
    human_approved: list[str]   # Match IDs approved by human
    human_rejected: list[str]   # Match IDs rejected by human

    # Output
    matches_for_weather: list[dict]  # Clean matches ready for weather agent
    summary: str


# ─────────────────────────────────────────────────
# Node: Validate all matches
# ─────────────────────────────────────────────────

def validate_matches_node(state: ValidationGraphState) -> dict:
    """Run validation on all matches. Sort into valid/flagged/rejected."""
    matches = state.get("matches_to_validate", [])
    if not matches:
        return {
            "messages": [("assistant", "No matches to validate.")],
            "valid_matches": [],
            "flagged_matches": [],
            "rejected_matches": [],
            "validation_results": [],
            "summary": "No matches provided.",
        }

    valid = []
    flagged = []
    rejected = []
    results = []

    for match in matches:
        try:
            result = validate_match(match)
            result_dict = result.model_dump()
            results.append(result_dict)

            # Debug: show what the LLM classified each match as
            print(f"  {match.get('id')}: {result.status.value} "
                  f"(confidence: {result.confidence}, action: {result.suggested_action})")
            if result.issues:
                for issue in result.issues:
                    print(f"    - [{issue.severity}] {issue.field_name}: {issue.description}")

            if result.status == ValidationStatus.VALID:
                valid.append(match)
            elif result.status == ValidationStatus.FLAGGED:
                flagged.append({**match, "_validation": result_dict})
            else:
                rejected.append({**match, "_validation": result_dict})

        except Exception as e:
            # Validation itself failed — flag for review
            flagged.append({
                **match,
                "_validation": {
                    "status": "flagged",
                    "summary": f"Validation error: {str(e)}",
                    "issues": [{"description": str(e), "severity": "high"}],
                },
            })

    summary = (
        f"Validated {len(matches)} matches: "
        f"{len(valid)} valid, {len(flagged)} flagged, {len(rejected)} rejected."
    )

    return {
        "messages": [("assistant", summary)],
        "valid_matches": valid,
        "flagged_matches": flagged,
        "rejected_matches": rejected,
        "validation_results": results,
        "summary": summary,
    }


# ─────────────────────────────────────────────────
# Node: Human review (uses interrupt)
# ─────────────────────────────────────────────────

def human_review_node(state: ValidationGraphState) -> dict:
    """Pause the graph and ask a human to review flagged matches.

    CONCEPT: interrupt() pauses the graph. When you call graph.invoke() again
             with the same thread_id, it resumes from here with the human's input.

    In a real app, this would show a UI. For now, it prints to the console.
    """
    flagged = state.get("flagged_matches", [])

    if not flagged:
        return {
            "human_approved": [],
            "human_rejected": [],
            "messages": [("assistant", "No flagged matches to review.")],
        }

    # Build a review summary for the human
    review_items = []
    for match in flagged:
        validation = match.get("_validation", {})
        review_items.append({
            "match_id": match.get("id", "unknown"),
            "match_name": match.get("name", "Unknown"),
            "issues": validation.get("issues", []),
            "summary": validation.get("summary", "No summary"),
            "suggested_action": validation.get("suggested_action", "review_and_approve"),
        })

    # ── THIS IS THE KEY LINE ──
    # interrupt() pauses the graph and returns the review data to the caller.
    # The caller (your script or UI) shows this to the human and collects their decision.
    # When the graph is resumed, the human's response is returned by interrupt().
    human_response = interrupt({
        "type": "review_flagged_matches",
        "message": "The following matches have data quality issues. Please review.",
        "flagged_matches": review_items,
        "instructions": (
            "Respond with a JSON object: "
            '{"approved": ["match-id-1", ...], "rejected": ["match-id-2", ...]}'
        ),
    })

    # Parse the human's response
    approved_ids = []
    rejected_ids = []

    if isinstance(human_response, dict):
        approved_ids = human_response.get("approved", [])
        rejected_ids = human_response.get("rejected", [])
    elif isinstance(human_response, str):
        try:
            parsed = json.loads(human_response)
            approved_ids = parsed.get("approved", [])
            rejected_ids = parsed.get("rejected", [])
        except json.JSONDecodeError:
            # If human just said "approve all" or similar
            if "approve" in human_response.lower():
                approved_ids = [m.get("id", "") for m in flagged]
            else:
                rejected_ids = [m.get("id", "") for m in flagged]

    return {
        "human_approved": approved_ids,
        "human_rejected": rejected_ids,
        "messages": [(
            "assistant",
            f"Human review complete: {len(approved_ids)} approved, {len(rejected_ids)} rejected.",
        )],
    }


# ─────────────────────────────────────────────────
# Node: Compile final list of clean matches
# ─────────────────────────────────────────────────

def compile_results_node(state: ValidationGraphState) -> dict:
    """Combine valid matches + human-approved matches into the final clean list."""
    clean_matches = list(state.get("valid_matches", []))

    # Add human-approved flagged matches
    approved_ids = set(state.get("human_approved", []))
    for match in state.get("flagged_matches", []):
        if match.get("id") in approved_ids:
            # Remove the _validation metadata before passing downstream
            clean = {k: v for k, v in match.items() if not k.startswith("_")}
            clean_matches.append(clean)

    rejected_count = (
        len(state.get("rejected_matches", []))
        + len(state.get("human_rejected", []))
    )

    summary = (
        f"Final result: {len(clean_matches)} matches ready for weather analysis. "
        f"{rejected_count} matches rejected."
    )

    return {
        "matches_for_weather": clean_matches,
        "summary": summary,
        "messages": [("assistant", summary)],
    }


# ─────────────────────────────────────────────────
# Routing function (conditional edge)
# ─────────────────────────────────────────────────

def route_after_validation(state: ValidationGraphState) -> str:
    """Decide what to do after validation.

    CONCEPT: Conditional edge — the graph branches based on results.
    """
    flagged = state.get("flagged_matches", [])

    if flagged:
        # There are flagged matches — go to human review
        return "human_review"
    else:
        # No flagged matches — skip straight to compiling results
        return "compile_results"


# ─────────────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────────────

def build_validation_graph():
    """Build and compile the validation graph with human-in-the-loop.

    Graph structure:
        START → validate_matches → [conditional] → human_review → compile_results → END
                                                 → compile_results → END
    """
    graph_builder = StateGraph(ValidationGraphState)

    # Add nodes
    graph_builder.add_node("validate_matches", validate_matches_node)
    graph_builder.add_node("human_review", human_review_node)
    graph_builder.add_node("compile_results", compile_results_node)

    # Add edges
    graph_builder.add_edge(START, "validate_matches")

    # Conditional edge: after validation, go to human review or skip it
    graph_builder.add_conditional_edges(
        "validate_matches",
        route_after_validation,
        {
            "human_review": "human_review",
            "compile_results": "compile_results",
        },
    )

    graph_builder.add_edge("human_review", "compile_results")
    graph_builder.add_edge("compile_results", END)

    # Compile with interrupt_before on the human_review node
    # This means the graph will PAUSE before entering human_review
    graph = graph_builder.compile(
        interrupt_before=["human_review"],
    )

    return graph


# ─────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    from langgraph.checkpoint.memory import MemorySaver

    print("=" * 60)
    print("Validation Graph with Human-in-the-Loop")
    print("=" * 60)

    # We need a checkpointer to support interrupts.
    # MemorySaver stores graph state in memory (for production, use a database).
    checkpointer = MemorySaver()

    # Rebuild with checkpointer
    graph_builder = StateGraph(ValidationGraphState)
    graph_builder.add_node("validate_matches", validate_matches_node)
    graph_builder.add_node("human_review", human_review_node)
    graph_builder.add_node("compile_results", compile_results_node)
    graph_builder.add_edge(START, "validate_matches")
    graph_builder.add_conditional_edges(
        "validate_matches",
        route_after_validation,
        {"human_review": "human_review", "compile_results": "compile_results"},
    )
    graph_builder.add_edge("human_review", "compile_results")
    graph_builder.add_edge("compile_results", END)

    graph = graph_builder.compile(
        interrupt_before=["human_review"],
        checkpointer=checkpointer,
    )

    # Test data: one good match, one suspicious match
    test_matches = [
        {
            "id": "test-good-001",
            "name": "India vs England, 2nd T20I",
            "match_type": "t20",
            "status": "Match over",
            "venue": "M Chinnaswamy Stadium",
            "date": "2025-01-20",
            "teams": ["India", "England"],
            "score": [
                {"team": "India", "runs": 212, "wickets": 4, "overs": 20},
                {"team": "England", "runs": 198, "wickets": 8, "overs": 20},
            ],
        },
        # This match passes rule-based checks but has SUBTLE data issues
        # that require human judgment (the LLM should FLAG, not REJECT):
        # - match_type says "t20" but scores show 50 overs (ODI-level overs)
        # - This is a data quality mismatch, not clearly wrong data
        # - Could be a data entry error — needs human review
        {
            "id": "test-flag-002",
            "name": "Australia vs South Africa, 1st T20I",
            "match_type": "t20",
            "status": "Match over",
            "venue": "Melbourne Cricket Ground",
            "date": "2025-02-10",
            "teams": ["Australia", "South Africa"],
            "score": [
                {"team": "Australia", "runs": 310, "wickets": 7, "overs": 50},
                {"team": "South Africa", "runs": 285, "wickets": 10, "overs": 48.3},
            ],
        },
    ]

    # Thread config is required for checkpointing
    config = {"configurable": {"thread_id": "validation-test-1"}}

    # ── FIRST RUN: Graph will validate, then PAUSE at human_review ──
    print("\n[Step 1] Running validation...")
    result = graph.invoke(
        {
            "matches_to_validate": test_matches,
            "messages": [],
            "valid_matches": [],
            "flagged_matches": [],
            "rejected_matches": [],
            "validation_results": [],
            "human_approved": [],
            "human_rejected": [],
            "matches_for_weather": [],
            "summary": "",
        },
        config,
    )

    print(f"\nGraph paused. State so far:")
    print(f"  Valid: {len(result.get('valid_matches', []))}")
    print(f"  Flagged: {len(result.get('flagged_matches', []))}")
    print(f"  Rejected: {len(result.get('rejected_matches', []))}")

    # Check if the graph is waiting for human input
    snapshot = graph.get_state(config)
    if snapshot.next:
        print(f"\n  Graph is paused before: {snapshot.next}")
        print("  In a real app, you'd show a UI here.")

        # ── SECOND RUN: Ask the human what to do ──
        print("\n[Step 2] Human review required!")
        print("-" * 40)
        flagged = result.get("flagged_matches", [])
        for match in flagged:
            v = match.get("_validation", {})
            print(f"\n  Match: {match.get('name')} (ID: {match.get('id')})")
            print(f"  Type:  {match.get('match_type')}")
            print(f"  Score: {match.get('score')}")
            issues = v.get("issues", [])
            for issue in issues:
                desc = issue.get("description", "") if isinstance(issue, dict) else issue.description
                print(f"  Issue: {desc}")
            print(f"  Suggested action: {v.get('suggested_action', 'unknown')}")

        print(f"\n  Enter 'approve' or 'reject' for each flagged match.")
        approved_ids = []
        rejected_ids = []
        for match in flagged:
            mid = match.get("id", "unknown")
            while True:
                choice = input(f"  {mid} — approve or reject? ").strip().lower()
                if choice in ("approve", "a"):
                    approved_ids.append(mid)
                    break
                elif choice in ("reject", "r"):
                    rejected_ids.append(mid)
                    break
                else:
                    print("    Please type 'approve' or 'reject'.")

        print(f"\n  Your decision: {len(approved_ids)} approved, {len(rejected_ids)} rejected")

        # Resume the graph with the human's actual response
        result = graph.invoke(
            Command(resume={"approved": approved_ids, "rejected": rejected_ids}),
            config,
        )

    print(f"\n[Step 3] Final result:")
    print(f"  Matches ready for weather: {len(result.get('matches_for_weather', []))}")
    print(f"  Summary: {result.get('summary', '')}")

    print("\nGraph structure:")
    print("  START -> validate_matches -> [conditional] -> human_review -> compile_results -> END")
    print("                                             -> compile_results -> END")