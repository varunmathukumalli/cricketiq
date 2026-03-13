"""
fetch_agent.py — Data Fetch Agent

ROLE: Decides what cricket data to fetch and loads it into the database.
LLM: Gemini 2.0 Flash (cheapest — this runs frequently)

CONCEPT: Tool-calling agent. The LLM decides WHICH tools to call and WITH WHAT
         arguments based on the current state of the database.

This is different from a script that always does the same thing.
The agent REASONS about what to fetch:
  - "Do I have recent data? No → fetch current matches"
  - "Are there completed matches without scorecards? Yes → fetch those"
  - "Am I close to the API rate limit? Yes → prioritize important fetches"
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

load_dotenv()

# Import our plain-code tools
from tools.cricket_api import fetch_current_matches, fetch_match_scorecard
from tools.database import save_matches, query_database, get_database_status


# ─────────────────────────────────────────────────
# Wrap plain functions as LangChain "tools"
# The @tool decorator tells LangGraph these are callable tools
# ─────────────────────────────────────────────────

@tool
def tool_fetch_current_matches() -> str:
    """Fetch current/recent cricket matches from the CricketData.org API.
    Returns a summary of what was fetched."""
    matches = fetch_current_matches()
    if not matches:
        return "No matches returned from API."
    result = save_matches(matches)
    return f"Fetched {len(matches)} matches. Inserted: {result['inserted']}, Updated: {result['updated']}."


@tool
def tool_check_database() -> str:
    """Check the current state of the database — how many matches, last update, etc.
    Use this to decide what needs to be fetched."""
    status = get_database_status()
    lines = [f"{table}: {count}" for table, count in status.items()]
    return "Database status:\n" + "\n".join(lines)


@tool
def tool_find_matches_needing_scorecards() -> str:
    """Find completed matches that don't have scorecard data yet."""
    results = query_database("""
        SELECT m.id, m.name FROM matches m
        LEFT JOIN player_performances pp ON m.id = pp.match_id
        WHERE m.status NOT ILIKE '%%not started%%'
        AND pp.id IS NULL
        LIMIT 10
    """)
    if not results:
        return "All completed matches have scorecards."
    names = [r["name"] for r in results]
    ids = [r["id"] for r in results]
    return f"Found {len(results)} matches without scorecards:\n" + \
           "\n".join(f"  {name} (id: {mid})" for name, mid in zip(names[:5], ids[:5]))


@tool
def tool_fetch_scorecard(match_id: str) -> str:
    """Fetch the detailed scorecard for a specific match and save player performances.
    Use this after finding matches that need scorecards.

    Args:
        match_id: The match ID to fetch the scorecard for
    """
    scorecard = fetch_match_scorecard(match_id)
    if not scorecard:
        return f"No scorecard data returned for match {match_id}."
    # TODO: Parse scorecard and save to player_performances table in Week 2
    return f"Fetched scorecard for match {match_id}. Keys: {list(scorecard.keys())[:5]}"


# ─────────────────────────────────────────────────
# Create the agent
# ─────────────────────────────────────────────────

def create_fetch_agent():
    """Create the data fetch agent with Gemini Flash and our tools."""
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

    tools = [
        tool_fetch_current_matches,
        tool_check_database,
        tool_find_matches_needing_scorecards,
        tool_fetch_scorecard,
    ]

    # create_react_agent is a LangGraph helper that builds a ReAct agent.
    # ReAct = Reason + Act: the agent thinks about what to do, then does it.
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=(
            "You are the CricketIQ Data Fetch Agent and have high knowledge of cricket. Your job is to keep the cricket "
            "database up to date.\n\n"
            "STEPS:\n"
            "1. First, check the database status to see what we have\n"
            "2. Fetch current matches from the API\n"
            "3. Check if any completed matches need scorecards\n"
            "4. Summarize what you did\n\n"
            "Be efficient with API calls — we have 100/day on the free tier."
        ),
    )
    return agent


# ─────────────────────────────────────────────────
# Run the agent
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Running Data Fetch Agent (Gemini Flash)")
    print("=" * 50)

    agent = create_fetch_agent()

    # The agent will reason about what to do and call tools
    result = agent.invoke({
        "messages": [("user", "Check the database and fetch any new cricket data we need.")]
    })

    # Print the agent's reasoning and actions
    print("\n--- Agent Reasoning ---")
    for msg in result["messages"]:
        if hasattr(msg, "content") and msg.content:
            role = msg.__class__.__name__
            print(f"[{role}] {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  → Called tool: {tc['name']}")