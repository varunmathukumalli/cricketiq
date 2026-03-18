"""
orchestrator.py — Orchestrator Agent

ROLE: The "manager" that checks database state and decides which agents
      to invoke, in what order. Handles errors and retries.

LLM: Gemini 2.0 Flash (Google)
     Why Gemini Flash? The Orchestrator runs the most frequently and its job
     is decision-making, not writing. Gemini Flash is the cheapest option and
     fast enough for routing decisions.

PATTERN: Decision-making agent with tool-based execution.
         The Orchestrator does not DO the work — it DECIDES what work to do
         and delegates to other agents.

LANGGRAPH CONCEPTS TAUGHT:
  - Graph orchestration (one agent managing others)
  - Conditional execution (run agents only when needed)
  - Error handling (retry, skip, or escalate)
  - State inspection (checking database to make decisions)
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

load_dotenv()

# Import database tools for state inspection
from tools.database import get_database_status, query_database

# Import the agent runners
from agents.explainer_agent import run_explainer
from agents.report_agent import run_report_agent


# ─────────────────────────────────────────────────
# Orchestrator tools
# ─────────────────────────────────────────────────
# These tools let the Orchestrator inspect state and invoke other agents.

@tool
def tool_check_database_status() -> str:
    """Check the current state of the CricketIQ database.
    Shows how many matches, predictions, reports, etc. we have.
    Use this FIRST to decide what needs to be done."""
    status = get_database_status()

    lines = ["Database Status:"]
    for table, count in status.items():
        lines.append(f"  {table}: {count}")

    # Add more detailed state information
    try:
        # Matches without predictions
        no_pred = query_database("""
            SELECT COUNT(*) as count FROM matches m
            LEFT JOIN predictions p ON m.id = p.match_id
            WHERE p.id IS NULL
            AND m.status ILIKE '%%not started%%'
        """)
        lines.append(f"\n  Upcoming matches without predictions: {no_pred[0]['count'] if no_pred else 0}")

        # Predictions without explanations
        no_expl = query_database("""
            SELECT COUNT(*) as count FROM predictions
            WHERE explanation IS NULL
        """)
        lines.append(f"  Predictions without explanations: {no_expl[0]['count'] if no_expl else 0}")

        # Matches with predictions but no reports
        no_report = query_database("""
            SELECT COUNT(*) as count FROM predictions p
            LEFT JOIN ai_reports r ON p.match_id = r.match_id
            WHERE r.id IS NULL
        """)
        lines.append(f"  Predictions without reports: {no_report[0]['count'] if no_report else 0}")

        # Stale data check
        stale = query_database("""
            SELECT COUNT(*) as count FROM matches
            WHERE updated_at < NOW() - INTERVAL '6 hours'
            AND status NOT ILIKE '%%completed%%'
            AND status NOT ILIKE '%%abandoned%%'
        """)
        lines.append(f"  Stale match records (>6 hours old): {stale[0]['count'] if stale else 0}")

    except Exception as e:
        lines.append(f"\n  (Could not get detailed status: {e})")

    return "\n".join(lines)


@tool
def tool_invoke_fetch_pipeline() -> str:
    """Invoke the data fetch pipeline to get new match data.
    This runs the Fetch Agent from Week 1 to update the matches table.
    Only call this if the database has stale or missing match data."""
    try:
        from agents.fetch_agent import create_fetch_agent

        agent = create_fetch_agent()
        result = agent.invoke({
            "messages": [("user", "Fetch the latest cricket match data.")]
        })

        # Extract the last message as a summary
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content:
                return f"Fetch pipeline completed: {msg.content[:300]}"
        return "Fetch pipeline completed (no summary available)"

    except Exception as e:
        return f"Fetch pipeline FAILED: {str(e)}"


@tool
def tool_invoke_predictions(match_id: str) -> str:
    """Run the ML prediction pipeline for a specific match.
    This generates win probabilities using the trained XGBoost model.
    Only call this for matches that do not have predictions yet.

    Args:
        match_id: The match ID to predict
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

        from predict import load_model, predict_match, save_predictions
        from features import load_matches_dataframe, extract_winner

        model, metadata = load_model()
        historical_df = load_matches_dataframe()
        historical_df["winner"] = historical_df.apply(
            lambda row: extract_winner(row["status"], row["teams"]), axis=1
        )

        # Get the specific match
        from tools.database import query_database
        matches = query_database(
            "SELECT id, name, match_type, venue, date, teams FROM matches WHERE id = %s",
            (match_id,)
        )
        if not matches:
            return f"Match {match_id} not found in database"

        m = matches[0]
        match_tuple = (m["id"], m["name"], m["match_type"], m["venue"], m["date"], m["teams"])
        pred = predict_match(model, metadata, historical_df, match_tuple)

        if pred:
            save_predictions([pred])
            return (
                f"Prediction generated: {pred['team_a']} {pred['team_a_prob']:.1%} vs "
                f"{pred['team_b']} {pred['team_b_prob']:.1%}"
            )
        else:
            return f"Could not generate prediction for match {match_id} (missing team data)"

    except Exception as e:
        return f"Prediction FAILED: {str(e)}\n{traceback.format_exc()[:200]}"


@tool
def tool_invoke_explainer(match_id: str) -> str:
    """Run the Prediction Explainer Agent (GPT-4o-mini) for a match.
    This generates a human-readable explanation of WHY the model predicted
    what it did. Only call this for matches that have predictions but no explanations.

    Args:
        match_id: The match ID to explain
    """
    try:
        result = run_explainer(match_id)

        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content and len(msg.content) > 50:
                return f"Explanation generated: {msg.content[:300]}"
        return "Explainer completed (no summary available)"

    except Exception as e:
        return f"Explainer FAILED: {str(e)}"


@tool
def tool_invoke_report_agent(match_id: str) -> str:
    """Run the Report Generation Agent (Claude Sonnet) for a match.
    This generates a polished pre-match analysis report.
    Only call this for matches that have predictions AND explanations
    but no reports yet.

    Args:
        match_id: The match ID to write a report for
    """
    try:
        result = run_report_agent(match_id)

        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.content and len(msg.content) > 100:
                return f"Report generated: {msg.content[:300]}"
        return "Report agent completed (no summary available)"

    except Exception as e:
        return f"Report generation FAILED: {str(e)}"


@tool
def tool_get_actionable_matches() -> str:
    """Get a list of matches that need work done on them.
    Shows matches at each stage: need predictions, need explanations, need reports.
    Use this after check_database_status to decide what to work on."""
    lines = []

    try:
        # Matches that need predictions
        need_pred = query_database("""
            SELECT m.id, m.name FROM matches m
            LEFT JOIN predictions p ON m.id = p.match_id
            WHERE p.id IS NULL
            AND (m.status ILIKE '%%not started%%' OR m.status ILIKE '%%upcoming%%')
            ORDER BY m.date
            LIMIT 5
        """)
        lines.append(f"Matches needing PREDICTIONS ({len(need_pred)}):")
        for m in need_pred:
            lines.append(f"  - {m['name']} (ID: {m['id']})")

        # Predictions that need explanations
        need_expl = query_database("""
            SELECT p.match_id, m.name, p.team_a, p.team_b FROM predictions p
            JOIN matches m ON p.match_id = m.id
            WHERE p.explanation IS NULL
            ORDER BY p.predicted_at DESC
            LIMIT 5
        """)
        lines.append(f"\nPredictions needing EXPLANATIONS ({len(need_expl)}):")
        for m in need_expl:
            lines.append(f"  - {m['name']} (ID: {m['match_id']})")

        # Predictions with explanations but no reports
        need_report = query_database("""
            SELECT p.match_id, m.name FROM predictions p
            JOIN matches m ON p.match_id = m.id
            LEFT JOIN ai_reports r ON p.match_id = r.match_id
            WHERE p.explanation IS NOT NULL
            AND r.id IS NULL
            ORDER BY p.predicted_at DESC
            LIMIT 5
        """)
        lines.append(f"\nMatches needing REPORTS ({len(need_report)}):")
        for m in need_report:
            lines.append(f"  - {m['name']} (ID: {m['match_id']})")

    except Exception as e:
        lines.append(f"Error getting actionable matches: {e}")

    return "\n".join(lines) if lines else "No actionable matches found."


# ─────────────────────────────────────────────────
# Orchestrator system prompt
# ─────────────────────────────────────────────────
ORCHESTRATOR_SYSTEM_PROMPT = """You are the CricketIQ Orchestrator Agent. You are the manager of the entire
CricketIQ pipeline. Your job is to inspect the current state of the system
and decide what needs to be done.

WORKFLOW:
1. Call tool_check_database_status to see the current state
2. Call tool_get_actionable_matches to find matches that need work
3. Decide what to do based on the state
4. Execute the needed actions in the correct order

DECISION RULES:
- If there are stale match records (>6 hours old), invoke the fetch pipeline first
- If there are matches without predictions, invoke predictions for them
- If there are predictions without explanations, invoke the explainer
- If there are predictions with explanations but no reports, invoke the report agent
- Process AT MOST 3 matches per run to avoid hitting API rate limits
- Process each match through ALL stages before moving to the next match

EXECUTION ORDER (for each match):
  Prediction -> Explanation -> Report
  (Never generate a report for a match that has no explanation)

ERROR HANDLING:
- If a tool fails, log the error and SKIP that match — move to the next one
- If the fetch pipeline fails, continue with existing data
- NEVER retry more than once — if it fails twice, skip it
- At the end, summarize what you did and what failed

COST AWARENESS:
- Each agent call costs money (Explainer = GPT-4o-mini, Report = Claude Sonnet)
- Do not invoke agents for matches that already have outputs
- Prioritize recent/upcoming matches over old ones
"""


# ─────────────────────────────────────────────────
# Create the Orchestrator
# ─────────────────────────────────────────────────
def create_orchestrator():
    """Create the Orchestrator agent with Gemini Flash."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,   # Low temperature — we want consistent decisions
    )

    tools = [
        tool_check_database_status,
        tool_get_actionable_matches,
        tool_invoke_fetch_pipeline,
        tool_invoke_predictions,
        tool_invoke_explainer,
        tool_invoke_report_agent,
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    )
    return agent


def run_orchestrator() -> dict:
    """Run the Orchestrator.

    This is the main entry point for the entire CricketIQ pipeline.
    The Orchestrator inspects state, decides what to do, and delegates.

    Returns:
        Dict with the agent's messages and decisions
    """
    agent = create_orchestrator()
    result = agent.invoke({
        "messages": [
            ("user",
             "Check the CricketIQ system state and process any matches that need "
             "predictions, explanations, or reports. Summarize what you did.")
        ]
    })
    return result


# ─────────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("CricketIQ Orchestrator Agent (Gemini 2.0 Flash)")
    print("=" * 60)
    print()
    print("The Orchestrator will:")
    print("  1. Check database state")
    print("  2. Find matches that need work")
    print("  3. Invoke other agents as needed")
    print("  4. Summarize what it did")
    print()
    print("This may call multiple LLMs (Gemini + GPT-4o-mini + Claude).")
    print("Estimated cost: $0.01-0.15 depending on how many matches need work.")
    print()

    result = run_orchestrator()

    # Print the full reasoning trace
    print("\n" + "=" * 60)
    print("ORCHESTRATOR TRACE")
    print("=" * 60)
    for msg in result["messages"]:
        role = msg.__class__.__name__
        if hasattr(msg, "content") and msg.content:
            print(f"\n[{role}]")
            # Print full content for the orchestrator's reasoning
            print(msg.content[:800] if len(msg.content) > 800 else msg.content)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                args_str = str(tc.get("args", {}))[:100]
                print(f"  -> Called: {tc['name']}({args_str})")