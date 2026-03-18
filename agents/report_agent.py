"""
report_agent.py — Report Generation Agent

ROLE: Produces polished, publication-quality pre-match analysis reports.
      This is the primary user-facing content agent.

LLM: Claude Sonnet (langchain_anthropic.ChatAnthropic)
     Why Claude Sonnet? It produces the best writing quality among our three LLMs.
     Reports are user-facing, so quality matters more than cost here.

PATTERN: RAG (Retrieval-Augmented Generation)
         The agent retrieves ALL real data from the database via tools, then
         injects it into the prompt. The LLM writes prose, but every fact
         comes from our verified data. This prevents hallucination.

LANGGRAPH CONCEPTS TAUGHT:
  - RAG pattern (retrieve real data, augment prompt, generate)
  - Prompt engineering (detailed instructions produce better output)
  - Token management (tracking usage for cost control)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

load_dotenv()

# Import our plain-code tools
from tools.report_tools import (
    get_match_details as _get_match_details,
    get_prediction_with_explanation as _get_prediction_with_explanation,
    get_weather_summary as _get_weather_summary,
    get_player_form as _get_player_form,
    save_report as _save_report,
)


# ─────────────────────────────────────────────────
# Wrap as LangChain tools
# ─────────────────────────────────────────────────

@tool
def tool_get_match_details(match_id: str) -> str:
    """Get full match information: teams, venue, date, format, status, scores.
    Call this first to understand what match you are writing about."""
    details = _get_match_details(match_id)
    if not details:
        return f"No match found with ID {match_id}"

    lines = ["Match Details:"]
    for k, v in details.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


@tool
def tool_get_prediction_with_explanation(match_id: str) -> str:
    """Get the ML model's win probability AND the Explainer Agent's analysis.
    This gives you both the numbers and the reasoning behind them.
    Call this after getting match details."""
    pred = _get_prediction_with_explanation(match_id)
    if "error" in pred:
        return pred["error"]

    return (
        f"Win Probability:\n"
        f"  {pred['team_a']}: {pred['team_a_win_prob']:.1%}\n"
        f"  {pred['team_b']}: {pred['team_b_win_prob']:.1%}\n"
        f"  Model: {pred['model_version']} (as of {pred['predicted_at']})\n\n"
        f"Explainer Agent's Analysis:\n{pred['explanation']}"
    )


@tool
def tool_get_weather_summary(match_id: str) -> str:
    """Get weather conditions and cricket impact analysis for the match venue.
    Includes temperature, humidity, dew point, and the Weather Agent's summary."""
    weather = _get_weather_summary(match_id)
    if "error" in weather:
        return weather["error"]

    lines = ["Weather Conditions:"]
    if weather.get("temperature_c") is not None:
        lines.append(f"  Temperature: {weather['temperature_c']}°C")
    if weather.get("humidity_pct") is not None:
        lines.append(f"  Humidity: {weather['humidity_pct']}%")
    if weather.get("wind_speed_kmh") is not None:
        lines.append(f"  Wind: {weather['wind_speed_kmh']} km/h")
    if weather.get("dew_point_c") is not None:
        lines.append(f"  Dew Point: {weather['dew_point_c']}°C")
    if weather.get("precipitation_mm") is not None:
        lines.append(f"  Precipitation: {weather['precipitation_mm']} mm")
    lines.append(f"\nCricket Impact Analysis:\n  {weather['weather_summary']}")
    return "\n".join(lines)


@tool
def tool_get_player_form(team: str) -> str:
    """Get recent performance stats for a team's key players.
    Shows batting averages, strike rates, wickets, and economy rates
    from the last 5 matches. Call this once for each team."""
    players = _get_player_form(team)
    if not players:
        return f"No recent player data available for {team}"

    lines = [f"Player Form for {team} (last 5 matches):"]

    # Separate batters and bowlers for clearer output
    batters = [p for p in players if p["avg_runs"] > 0]
    bowlers = [p for p in players if p["avg_wickets"] > 0 or p["avg_economy"] > 0]

    if batters:
        lines.append("\n  Key Batters:")
        for p in batters[:6]:
            lines.append(
                f"    {p['player_name']} ({p.get('player_role', 'N/A')}): "
                f"avg {p['avg_runs']} runs, SR {p['avg_strike_rate']}, "
                f"{p['matches_played']} matches"
            )

    if bowlers:
        lines.append("\n  Key Bowlers:")
        for p in bowlers[:6]:
            lines.append(
                f"    {p['player_name']} ({p.get('player_role', 'N/A')}): "
                f"avg {p['avg_wickets']} wickets, econ {p['avg_economy']}, "
                f"{p['matches_played']} matches"
            )

    return "\n".join(lines)


@tool
def tool_save_report(match_id: str, report_text: str) -> str:
    """Save the finished report to the database.
    Call this LAST, after you have written the complete report.
    The report should be 350-400 words of flowing prose."""
    return _save_report(
        match_id=match_id,
        report_type="pre_match",
        report_text=report_text,
        model_used="claude-sonnet-4-6",
    )


# ─────────────────────────────────────────────────
# Agent system prompt — this is where prompt engineering matters most
# ─────────────────────────────────────────────────
REPORT_SYSTEM_PROMPT = """You are a senior cricket analyst writing for CricketIQ, a premium cricket
analytics platform. Your job is to write pre-match intelligence reports that
are insightful, data-driven, and engaging.

WORKFLOW (follow this exact order):
1. Call tool_get_match_details to get match information
2. Call tool_get_prediction_with_explanation to get the win probability and analysis
3. Call tool_get_weather_summary to get weather conditions
4. Call tool_get_player_form for EACH team (two separate calls)
5. Write the report using ALL the data you gathered
6. Call tool_save_report to save the finished report

REPORT FORMAT:
Write 350-400 words in 5 flowing paragraphs:

Paragraph 1 — THE HEADLINE STORY
Open with the most compelling narrative of this match. Do NOT start with
"In this match..." — be creative. Lead with what makes this specific matchup
interesting right now.

Paragraph 2 — THE PREDICTION
State the win probability and explain WHY. Reference the specific factors:
team form, head-to-head record, venue history. Cite actual numbers.

Paragraph 3 — CONDITIONS FACTOR
How do weather and venue conditions affect this match? Mention temperature,
humidity, dew factor if relevant. Explain what it means in cricket terms.

Paragraph 4 — PLAYERS TO WATCH
Highlight 2-3 key players from each team. Cite their recent stats (from the
player form tool). Identify the matchup within the match.

Paragraph 5 — THE VERDICT
Your prediction with reasoning. Be specific: "We give India a 68% chance,
driven primarily by their superior recent form and home venue advantage."

CRITICAL RULES:
- ONLY use data from the tools. NEVER invent statistics or player names.
- If data is missing (e.g., no player stats), say "limited data available" — do NOT make things up.
- Write in flowing paragraphs, NOT bullet points.
- Every claim must be backed by a specific number from your tools.
- Do NOT start any paragraph with "In this match" or "This match."
- Maintain a professional, analytical tone — like ESPN Cricinfo's analysis pieces.
- Keep it under 400 words.
"""


# ─────────────────────────────────────────────────
# Create the agent
# ─────────────────────────────────────────────────
def create_report_agent():
    """Create the Report Generation agent with Claude Sonnet."""
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0.4,    # Slightly creative but mostly factual
        max_tokens=1500,    # Enough for a 400-word report + reasoning
    )

    tools = [
        tool_get_match_details,
        tool_get_prediction_with_explanation,
        tool_get_weather_summary,
        tool_get_player_form,
        tool_save_report,
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=REPORT_SYSTEM_PROMPT,
    )
    return agent


def run_report_agent(match_id: str) -> dict:
    """Run the Report Agent for a specific match.

    This is the function the Orchestrator will call.

    Args:
        match_id: The match to generate a report for

    Returns:
        Dict with the agent's messages including the final report
    """
    agent = create_report_agent()
    result = agent.invoke({
        "messages": [
            ("user", f"Write a pre-match analysis report for match ID: {match_id}")
        ]
    })
    return result


# ─────────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    import psycopg2
    import os

    print("=" * 60)
    print("Report Generation Agent (Claude Sonnet)")
    print("=" * 60)

    # Find a match with a prediction (ideally with an explanation too)
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.match_id, m.name, p.team_a, p.team_b,
               p.team_a_win_prob,
               CASE WHEN p.explanation IS NOT NULL THEN 'yes' ELSE 'no' END as has_explanation
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        ORDER BY p.predicted_at DESC
        LIMIT 5
    """)
    predictions = cur.fetchall()
    cur.close()
    conn.close()

    if not predictions:
        print("\nNo predictions in database. Run the pipeline first:")
        print("  1. cd src && python predict.py && cd ..")
        print("  2. python agents/explainer_agent.py")
        exit(1)

    # Prefer matches that have explanations
    target = predictions[0]
    for p in predictions:
        if p[5] == "yes":
            target = p
            break

    match_id, name, team_a, team_b, prob, has_expl = target
    print(f"\nMatch: {name}")
    print(f"  {team_a} ({float(prob):.1%}) vs {team_b} ({1-float(prob):.1%})")
    print(f"  Has explanation: {has_expl}")
    print(f"  Match ID: {match_id}\n")

    print("Generating report (this calls Claude Sonnet — may take 10-15 seconds)...\n")
    result = run_report_agent(match_id)

    # Print the final report
    print("\n" + "=" * 60)
    print("GENERATED REPORT")
    print("=" * 60)
    for msg in result["messages"]:
        # The last AI message with substantial content is typically the report
        if hasattr(msg, "content") and msg.content and len(msg.content) > 200:
            print(msg.content)

    print("\n" + "=" * 60)
    print("AGENT TOOL CALLS")
    print("=" * 60)
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                args_preview = str(tc.get("args", {}))[:80]
                print(f"  -> {tc['name']}({args_preview})")