"""
graph.py — The FULL CricketIQ LangGraph Graph

This file connects every agent and code module from Weeks 1-4 into a single
executable graph. This is the complete pipeline:

  Orchestrate → Fetch → Validate → Weather → Predict → Explain → Report

LANGGRAPH CONCEPTS:
  - Full graph composition (many nodes, conditional edges)
  - Subgraphs (fetch→validate→weather as a data pipeline subgraph)
  - Error handling with conditional edges
  - Multi-model routing (Gemini + GPT-4o-mini + Claude in one graph)
  - State management across the entire pipeline
"""
import os
import sys
import traceback
from typing import TypedDict, Annotated, Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────
# RETRY HELPER
# ─────────────────────────────────────────────────
import time

def retry(fn, max_retries=3, description="operation"):
    """Run a function with exponential backoff retries."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"  [retry] {description} attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


# ─────────────────────────────────────────────────
# STEP 1: Define the pipeline state
# ─────────────────────────────────────────────────
# This state flows through the entire graph. Every node can read and write to it.

class PipelineState(TypedDict):
    """State that flows through the complete CricketIQ pipeline."""

    # Conversation / reasoning messages
    messages: Annotated[list, add_messages]

    # Which match we are processing
    match_id: str
    match_name: str

    # Pipeline progress tracking
    data_fetched: bool
    data_validated: bool
    weather_fetched: bool
    prediction_made: bool
    explanation_made: bool
    report_made: bool

    # Error tracking
    errors: list[str]
    should_continue: bool

    # Results from each stage
    fetch_summary: str
    validation_summary: str
    weather_summary: str
    prediction_summary: str
    explanation_summary: str
    report_summary: str


# ─────────────────────────────────────────────────
# STEP 2: Define the node functions
# ─────────────────────────────────────────────────
# Each node is a function that takes the state, does work, and returns updates.

def orchestrate_node(state: PipelineState) -> dict:
    """The Orchestrator node: checks state and decides whether to proceed.

    This is a simplified version for the graph — the full Orchestrator agent
    (agents/orchestrator.py) handles multi-match decisions. This node handles
    single-match flow control.
    """
    match_id = state.get("match_id")
    if not match_id:
        return {
            "should_continue": False,
            "errors": state.get("errors", []) + ["No match_id provided"],
            "messages": [("assistant", "No match ID provided. Cannot proceed.")],
        }

    # Check what work has already been done for this match
    from tools.database import query_database

    has_prediction = bool(query_database(
        "SELECT 1 FROM predictions WHERE match_id = %s", (match_id,)
    ))
    has_explanation = bool(query_database(
        "SELECT 1 FROM predictions WHERE match_id = %s AND explanation IS NOT NULL", (match_id,)
    ))
    has_report = bool(query_database(
        "SELECT 1 FROM ai_reports WHERE match_id = %s", (match_id,)
    ))

    summary = (
        f"Match {match_id}: prediction={'yes' if has_prediction else 'NO'}, "
        f"explanation={'yes' if has_explanation else 'NO'}, "
        f"report={'yes' if has_report else 'NO'}"
    )
    print(f"  [orchestrate] {summary}")

    return {
        "prediction_made": has_prediction,
        "explanation_made": has_explanation,
        "report_made": has_report,
        "should_continue": True,
        "messages": [("assistant", f"Orchestrator check: {summary}")],
    }


def fetch_node(state: PipelineState) -> dict:
    """Fetch the latest data for the match."""
    match_id = state.get("match_id")
    print(f"  [fetch] Updating data for match {match_id}")

    try:
        from tools.cricket_api import fetch_current_matches
        from tools.database import save_matches

        matches = retry(fetch_current_matches, description="cricket API fetch")
        result = save_matches(matches)
        summary = f"Fetched {len(matches)} matches (inserted: {result['inserted']}, updated: {result['updated']})"
        print(f"  [fetch] {summary}")
        return {
            "data_fetched": True,
            "fetch_summary": summary,
            "messages": [("assistant", f"Data fetch: {summary}")],
        }
    except Exception as e:
        error = f"Fetch failed: {str(e)}"
        print(f"  [fetch] {error}")
        return {
            "data_fetched": False,
            "fetch_summary": error,
            "errors": state.get("errors", []) + [error],
            "messages": [("assistant", error)],
        }


def validate_node(state: PipelineState) -> dict:
    """Validate the data for the match.

    For now, this is a basic check. The full Validation Agent (Week 2)
    handles more complex validation with LLM reasoning.
    """
    match_id = state.get("match_id")
    print(f"  [validate] Checking data quality for {match_id}")

    try:
        from tools.database import query_database

        match = query_database("SELECT id, name, teams, status FROM matches WHERE id = %s", (match_id,))
        if not match:
            return {
                "data_validated": False,
                "validation_summary": f"Match {match_id} not found in database",
                "should_continue": False,
                "errors": state.get("errors", []) + [f"Match {match_id} not in database"],
                "messages": [("assistant", f"Validation failed: match {match_id} not found")],
            }

        m = match[0]
        issues = []
        if not m.get("teams") or len(m["teams"]) < 2:
            issues.append("Missing team names")
        if not m.get("name"):
            issues.append("Missing match name")

        if issues:
            summary = f"Validation warnings for {m.get('name', match_id)}: {', '.join(issues)}"
        else:
            summary = f"Validation passed for {m.get('name', match_id)}"

        print(f"  [validate] {summary}")
        return {
            "data_validated": True,
            "match_name": m.get("name", ""),
            "validation_summary": summary,
            "messages": [("assistant", f"Validation: {summary}")],
        }
    except Exception as e:
        error = f"Validation error: {str(e)}"
        print(f"  [validate] {error}")
        return {
            "data_validated": False,
            "validation_summary": error,
            "errors": state.get("errors", []) + [error],
            "messages": [("assistant", error)],
        }


def weather_node(state: PipelineState) -> dict:
    """Fetch and analyze weather for the match venue.

    The full Weather Agent (Week 2) uses an LLM to reason about cricket impact.
    This node calls the weather tools directly.
    """
    match_id = state.get("match_id")
    print(f"  [weather] Getting weather for {match_id}")

    try:
        from tools.report_tools import get_weather_summary
        weather = retry(lambda: get_weather_summary(match_id), description="weather API")

        if "error" in weather:
            summary = f"No weather data available: {weather['error']}"
        else:
            summary = (
                f"Weather: {weather.get('temperature_c', '?')}°C, "
                f"{weather.get('humidity_pct', '?')}% humidity. "
                f"Analysis: {weather.get('weather_summary', 'N/A')[:100]}"
            )

        print(f"  [weather] {summary}")
        return {
            "weather_fetched": True,
            "weather_summary": summary,
            "messages": [("assistant", f"Weather: {summary}")],
        }
    except Exception as e:
        error = f"Weather fetch failed: {str(e)}"
        print(f"  [weather] {error}")
        return {
            "weather_fetched": False,
            "weather_summary": error,
            "errors": state.get("errors", []) + [error],
            "messages": [("assistant", error)],
        }


def predict_node(state: PipelineState) -> dict:
    """Run the ML model to generate win probabilities.

    This is PLAIN CODE, not an agent — the model is deterministic.
    """
    match_id = state.get("match_id")

    # Skip if already predicted
    if state.get("prediction_made"):
        print(f"  [predict] Already has prediction, skipping")
        return {
            "prediction_summary": "Prediction already exists",
            "messages": [("assistant", "Prediction already exists, skipping.")],
        }

    print(f"  [predict] Running ML model for {match_id}")

    try:
        from ml.predict import load_model, predict_match, save_predictions
        from ml.features import load_matches_dataframe, extract_winner
        from tools.database import query_database

        model, metadata = load_model()
        historical_df = load_matches_dataframe()
        historical_df["winner"] = historical_df.apply(
            lambda row: extract_winner(row["status"], row["teams"]), axis=1
        )

        matches = query_database(
            "SELECT id, name, match_type, venue, date, teams FROM matches WHERE id = %s",
            (match_id,)
        )
        if not matches:
            return {
                "prediction_made": False,
                "prediction_summary": "Match not found",
                "messages": [("assistant", "Match not found for prediction.")],
            }

        m = matches[0]
        pred = predict_match(model, metadata, historical_df, m)

        if pred:
            save_predictions([pred])
            summary = f"{pred['team_a']} {pred['team_a_prob']:.1%} vs {pred['team_b']} {pred['team_b_prob']:.1%}"
            print(f"  [predict] {summary}")
            return {
                "prediction_made": True,
                "prediction_summary": summary,
                "messages": [("assistant", f"Prediction: {summary}")],
            }
        else:
            return {
                "prediction_made": False,
                "prediction_summary": "Could not generate prediction (missing data)",
                "messages": [("assistant", "Could not generate prediction.")],
            }

    except Exception as e:
        error = f"Prediction failed: {str(e)}"
        print(f"  [predict] {error}")
        return {
            "prediction_made": False,
            "prediction_summary": error,
            "errors": state.get("errors", []) + [error],
            "messages": [("assistant", error)],
        }


def explain_node(state: PipelineState) -> dict:
    """Run the Prediction Explainer Agent (GPT-4o-mini)."""
    match_id = state.get("match_id")

    # Skip if already explained
    if state.get("explanation_made"):
        print(f"  [explain] Already has explanation, skipping")
        return {
            "explanation_summary": "Explanation already exists",
            "messages": [("assistant", "Explanation already exists, skipping.")],
        }

    # Cannot explain without a prediction
    if not state.get("prediction_made"):
        print(f"  [explain] No prediction to explain, skipping")
        return {
            "explanation_summary": "Skipped — no prediction available",
            "messages": [("assistant", "No prediction to explain.")],
        }

    print(f"  [explain] Running Explainer Agent for {match_id}")

    try:
        from agents.explainer_agent import run_explainer

        result = retry(lambda: run_explainer(match_id), description="GPT-4o explainer")

        # Get the agent's final output
        summary = "Explanation generated"
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content and len(msg.content) > 50:
                summary = msg.content[:200]
                break

        print(f"  [explain] Done")
        return {
            "explanation_made": True,
            "explanation_summary": summary,
            "messages": [("assistant", f"Explanation: {summary[:100]}...")],
        }

    except Exception as e:
        error = f"Explainer failed: {str(e)}"
        print(f"  [explain] {error}")
        return {
            "explanation_made": False,
            "explanation_summary": error,
            "errors": state.get("errors", []) + [error],
            "messages": [("assistant", error)],
        }


def report_node(state: PipelineState) -> dict:
    """Run the Report Generation Agent (Claude Sonnet)."""
    match_id = state.get("match_id")

    # Skip if already has a report
    if state.get("report_made"):
        print(f"  [report] Already has report, skipping")
        return {
            "report_summary": "Report already exists",
            "messages": [("assistant", "Report already exists, skipping.")],
        }

    # Should have at least a prediction before writing a report
    if not state.get("prediction_made"):
        print(f"  [report] No prediction available, skipping report")
        return {
            "report_summary": "Skipped — no prediction available",
            "messages": [("assistant", "Cannot write report without a prediction.")],
        }

    print(f"  [report] Running Report Agent for {match_id}")

    try:
        from agents.report_agent import run_report_agent

        result = retry(lambda: run_report_agent(match_id), description="Claude report agent")

        summary = "Report generated"
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content and len(msg.content) > 100:
                summary = msg.content[:200]
                break

        print(f"  [report] Done")
        return {
            "report_made": True,
            "report_summary": summary,
            "messages": [("assistant", f"Report generated: {summary[:100]}...")],
        }

    except Exception as e:
        error = f"Report generation failed: {str(e)}"
        print(f"  [report] {error}")
        return {
            "report_made": False,
            "report_summary": error,
            "errors": state.get("errors", []) + [error],
            "messages": [("assistant", error)],
        }


# ─────────────────────────────────────────────────
# STEP 3: Conditional edge functions
# ─────────────────────────────────────────────────
# These functions decide what happens next based on the state.

def should_continue_after_orchestrate(state: PipelineState) -> Literal["fetch_data", "__end__"]:
    """After orchestration, continue to fetch or stop."""
    if not state.get("should_continue", True):
        return "__end__"
    return "fetch_data"


def should_continue_after_validate(state: PipelineState) -> Literal["weather", "__end__"]:
    """After validation, continue to weather or stop if data is bad."""
    if not state.get("data_validated", False) and not state.get("should_continue", True):
        return "__end__"
    return "weather"


def should_continue_after_predict(state: PipelineState) -> Literal["explain", "__end__"]:
    """After prediction, continue to explain or stop."""
    if not state.get("prediction_made", False):
        return "__end__"
    return "explain"


def should_continue_after_explain(state: PipelineState) -> Literal["report", "__end__"]:
    """After explanation, continue to report or stop."""
    # Generate report even if explanation failed — the report agent can work with just the prediction
    if not state.get("prediction_made", False):
        return "__end__"
    return "report"


# ─────────────────────────────────────────────────
# STEP 4: Build the graph
# ─────────────────────────────────────────────────

def build_pipeline_graph():
    """Build the complete CricketIQ pipeline graph.

    Graph structure:
      START → orchestrate → fetch_data → validate → weather → predict → explain → report → END

    Conditional edges handle error cases at each stage.
    """
    graph_builder = StateGraph(PipelineState)

    # Add all nodes
    graph_builder.add_node("orchestrate", orchestrate_node)
    graph_builder.add_node("fetch_data", fetch_node)
    graph_builder.add_node("validate", validate_node)
    graph_builder.add_node("weather", weather_node)
    graph_builder.add_node("predict", predict_node)
    graph_builder.add_node("explain", explain_node)
    graph_builder.add_node("report", report_node)

    # Connect with edges
    # START → orchestrate
    graph_builder.add_edge(START, "orchestrate")

    # orchestrate → fetch_data (conditional — may stop if no match_id)
    graph_builder.add_conditional_edges(
        "orchestrate",
        should_continue_after_orchestrate,
        {"fetch_data": "fetch_data", "__end__": END},
    )

    # fetch_data → validate (always — even if fetch failed, we validate existing data)
    graph_builder.add_edge("fetch_data", "validate")

    # validate → weather (conditional — stop if data is bad)
    graph_builder.add_conditional_edges(
        "validate",
        should_continue_after_validate,
        {"weather": "weather", "__end__": END},
    )

    # weather → predict (always — predictions work with or without weather)
    graph_builder.add_edge("weather", "predict")

    # predict → explain (conditional — need a prediction to explain)
    graph_builder.add_conditional_edges(
        "predict",
        should_continue_after_predict,
        {"explain": "explain", "__end__": END},
    )

    # explain → report (conditional — need at least a prediction for report)
    graph_builder.add_conditional_edges(
        "explain",
        should_continue_after_explain,
        {"report": "report", "__end__": END},
    )

    # report → END
    graph_builder.add_edge("report", END)

    # Compile
    graph = graph_builder.compile()
    return graph


# ─────────────────────────────────────────────────
# STEP 5: Create a subgraph (bonus concept)
# ─────────────────────────────────────────────────
# A subgraph is a smaller graph inside the bigger one.
# The data pipeline (fetch → validate → weather) can be a subgraph.

def build_data_subgraph():
    """Build the data pipeline as a standalone subgraph.

    This subgraph handles: fetch → validate → weather.
    You can run it independently or plug it into the main graph.

    CONCEPT: Subgraphs let you modularize your pipeline. You can test the
    data pipeline separately from the ML/content pipeline.
    """
    graph_builder = StateGraph(PipelineState)

    graph_builder.add_node("fetch_data", fetch_node)
    graph_builder.add_node("validate", validate_node)
    graph_builder.add_node("weather", weather_node)

    graph_builder.add_edge(START, "fetch_data")
    graph_builder.add_edge("fetch_data", "validate")
    graph_builder.add_conditional_edges(
        "validate",
        should_continue_after_validate,
        {"weather": "weather", "__end__": END},
    )
    graph_builder.add_edge("weather", END)

    return graph_builder.compile()


# ─────────────────────────────────────────────────
# STEP 6: Run the full pipeline
# ─────────────────────────────────────────────────

def run_pipeline(match_id: str) -> dict:
    """Run the complete CricketIQ pipeline for a single match.

    This is the main entry point. It:
    1. Checks what work is needed (orchestrate)
    2. Fetches/updates data (fetch)
    3. Validates data quality (validate)
    4. Gets weather conditions (weather)
    5. Generates ML predictions (predict)
    6. Explains the prediction (explain — GPT-4o-mini)
    7. Writes the report (report — Claude Sonnet)

    Args:
        match_id: The match ID to process

    Returns:
        The final pipeline state
    """
    graph = build_pipeline_graph()

    initial_state = {
        "messages": [],
        "match_id": match_id,
        "match_name": "",
        "data_fetched": False,
        "data_validated": False,
        "weather_fetched": False,
        "prediction_made": False,
        "explanation_made": False,
        "report_made": False,
        "errors": [],
        "should_continue": True,
        "fetch_summary": "",
        "validation_summary": "",
        "weather_summary": "",
        "prediction_summary": "",
        "explanation_summary": "",
        "report_summary": "",
    }

    print(f"\nRunning full pipeline for match: {match_id}")
    print("=" * 60)

    result = graph.invoke(initial_state)

    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Match:        {result.get('match_name', match_id)}")
    print(f"  Data fetched: {'yes' if result.get('data_fetched') else 'no'}")
    print(f"  Validated:    {'yes' if result.get('data_validated') else 'no'}")
    print(f"  Weather:      {'yes' if result.get('weather_fetched') else 'no'}")
    print(f"  Prediction:   {'yes' if result.get('prediction_made') else 'no'}")
    print(f"  Explanation:  {'yes' if result.get('explanation_made') else 'no'}")
    print(f"  Report:       {'yes' if result.get('report_made') else 'no'}")
    if result.get("errors"):
        print(f"  Errors:       {len(result['errors'])}")
        for err in result["errors"]:
            print(f"    - {err[:100]}")

    return result


# ─────────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    print("=" * 60)
    print("CricketIQ FULL PIPELINE")
    print("=" * 60)
    print()
    print("This runs the COMPLETE pipeline:")
    print("  Orchestrate -> Fetch -> Validate -> Weather -> Predict -> Explain -> Report")
    print()
    print("LLMs used: Gemini Flash (orchestrate) + GPT-4o-mini (explain) + Claude Sonnet (report)")
    print()

    # Find a match to process
    from tools.database import query_database

    # Try to find an upcoming match (exclude completed ones)
    matches = query_database("""
        SELECT m.id, m.name,
               CASE WHEN p.id IS NOT NULL THEN 'has prediction' ELSE 'no prediction' END as pred_status,
               CASE WHEN r.id IS NOT NULL THEN 'has report' ELSE 'no report' END as report_status
        FROM matches m
        LEFT JOIN predictions p ON m.id = p.match_id
        LEFT JOIN ai_reports r ON m.id = r.match_id
        WHERE m.status ILIKE '%%Match starts%%'
           OR m.status ILIKE '%%not started%%'
           OR m.status ILIKE '%%upcoming%%'
           OR m.status ILIKE '%%opt to b%%'
        ORDER BY m.date ASC NULLS LAST
        LIMIT 10
    """)

    if not matches:
        print("No matches in database. Run the fetch agent first:")
        print("  python agents/fetch_agent.py")
        exit(1)

    print("Available matches:")
    for i, m in enumerate(matches):
        print(f"  {i+1}. {m['name']} [{m['pred_status']}, {m['report_status']}]")
        print(f"     ID: {m['id']}")

    # Pick the first match without a report (or the first match)
    target = matches[0]
    for m in matches:
        if m["report_status"] == "no report":
            target = m
            break

    print(f"\nProcessing: {target['name']}")
    print(f"Match ID: {target['id']}")
    print()

    result = run_pipeline(target["id"])