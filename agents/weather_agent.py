"""
weather_agent.py — Weather Impact Agent

ROLE: Fetches weather data for match venues and interprets
      the cricket impact (dew, humidity, swing, etc.)
LLM: GPT-4o-mini (reliable tool calling, cheap at ~$0.15/M input tokens)
TOOLS: Open-Meteo API via tools/weather_api.py

CONCEPT: Tool schemas — the agent sees the tool's function signature
         and docstring, then decides when and how to call it.
         Unlike the Validation Agent (structured output), this agent
         uses ReAct-style tool calling: think → act → observe → repeat.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

load_dotenv()

from tools.weather_api import (
    fetch_weather_for_venue,
    fetch_weather_for_match,
    describe_weather_code,
    get_venue_coordinates,
)
from tools.database import query_database


# ─────────────────────────────────────────────────
# Tool schemas — wrapping plain functions for LangGraph
# ─────────────────────────────────────────────────
# CONCEPT: When you decorate a function with @tool, LangGraph reads
# its name, docstring, and type hints to create a "tool schema."
# The LLM sees this schema and decides when to call the tool.

@tool
def tool_get_weather(venue_name: str, date: str = None) -> str:
    """Fetch weather data for a cricket venue.

    Args:
        venue_name: Name of the venue (e.g., 'Wankhede Stadium', 'Eden Gardens')
        date: Date in YYYY-MM-DD format. Leave empty for today's weather.

    Returns:
        JSON string with temperature, humidity, dew point, wind, precipitation,
        and dew risk data during match hours (8 AM - midnight).
    """
    result = fetch_weather_for_venue(venue_name, date)
    return json.dumps(result, indent=2, default=str)


@tool
def tool_get_match_weather(match_id: str) -> str:
    """Fetch weather for a specific match by looking up its venue and date automatically.

    Args:
        match_id: The match ID from the database.

    Returns:
        JSON weather data for the match venue on the match date.
    """
    result = fetch_weather_for_match(match_id)
    return json.dumps(result, indent=2, default=str)


@tool
def tool_list_venues() -> str:
    """List all cricket venues in the database with their coordinates.
    Use this to check which venues have coordinate data for weather lookups."""
    venues = query_database("SELECT name, city, country, latitude, longitude FROM venues ORDER BY name")
    if not venues:
        return "No venues in database."
    lines = [f"  {v['name']} ({v['city']}, {v['country']}) — {v['latitude']}, {v['longitude']}" for v in venues]
    return f"Known venues ({len(venues)}):\n" + "\n".join(lines)


@tool
def tool_get_matches_needing_weather() -> str:
    """Find matches that don't have weather data yet.
    Returns match IDs, names, venues, and dates."""
    matches = query_database("""
        SELECT m.id, m.name, m.venue, m.date
        FROM matches m
        LEFT JOIN match_weather mw ON m.id = mw.match_id
        WHERE mw.id IS NULL
        AND m.venue IS NOT NULL
        ORDER BY m.date DESC
        LIMIT 10
    """)
    if not matches:
        return "All matches with venues already have weather data (or no matches exist)."
    lines = [f"  {m['id']}: {m['name']} at {m['venue']} ({m['date']})" for m in matches]
    return f"Matches needing weather ({len(matches)}):\n" + "\n".join(lines)


@tool
def tool_interpret_weather_code(code: int) -> str:
    """Convert a WMO weather code number to a description.

    Args:
        code: The WMO weather code (e.g., 0 = clear, 61 = rain).
    """
    return describe_weather_code(code)


@tool
def tool_save_weather_to_db(
    match_id: str,
    temperature: float,
    humidity: int,
    wind_speed: float,
    precipitation: float,
    dew_point: float,
    weather_code: int,
    weather_summary: str,
) -> str:
    """Save weather data and the agent's cricket impact analysis to the database.

    Args:
        match_id: The match ID.
        temperature: Average temperature in Celsius during match hours.
        humidity: Average humidity percentage during match hours.
        wind_speed: Average wind speed in km/h during match hours.
        precipitation: Total precipitation in mm during match hours.
        dew_point: Average dew point in Celsius during match hours.
        weather_code: WMO weather code for dominant conditions.
        weather_summary: Agent's analysis of how weather affects the cricket match.
    """
    from tools.database import get_connection

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO match_weather (match_id, temperature, humidity, wind_speed,
                                   precipitation, dew_point, weather_code, weather_summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO UPDATE SET
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            wind_speed = EXCLUDED.wind_speed,
            precipitation = EXCLUDED.precipitation,
            dew_point = EXCLUDED.dew_point,
            weather_code = EXCLUDED.weather_code,
            weather_summary = EXCLUDED.weather_summary,
            fetched_at = NOW()
    """, (match_id, temperature, humidity, wind_speed, precipitation, dew_point, weather_code, weather_summary))
    conn.commit()
    cur.close()
    conn.close()
    return f"Weather data saved for match {match_id}."


# ─────────────────────────────────────────────────
# Create the agent
# ─────────────────────────────────────────────────

def create_weather_agent():
    """Create the Weather Impact Agent with Gemini Flash and weather tools."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    tools = [
        tool_get_weather,
        tool_get_match_weather,
        tool_list_venues,
        tool_get_matches_needing_weather,
        tool_interpret_weather_code,
        tool_save_weather_to_db,
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=(
            "You are the CricketIQ Weather Impact Agent with high Cricket IQ and knowledge of cricket. Your job is to fetch weather data "
            "for cricket matches and analyze how weather conditions affect the game.\n\n"
            "CRICKET WEATHER KNOWLEDGE:\n"
            "- High humidity (>70%) helps swing bowlers — the ball moves more in the air\n"
            "- Dew forms on the outfield in evening matches — makes fielding harder and "
            "the ball skids on to the bat (advantage batting second)\n"
            "- Overcast conditions (weather codes 2-3) assist seam bowling\n"
            "- Wind >20 km/h affects ball flight, especially for spinners\n"
            "- Temperature >35C causes player fatigue, especially in Test matches\n"
            "- Any precipitation means play stops (rain delays) and gain any other weather related information that is relevant to the cricket match.\n\n"
            "STEPS:\n"
            "1. Check which matches need weather data\n"
            "2. Fetch weather for each venue\n"
            "3. Analyze the cricket impact\n"
            "4. Save the weather data with your analysis summary to the database\n\n"
            "Your weather_summary should be 2-3 sentences explaining the cricket impact, e.g.:\n"
            "'High humidity (78%) and overcast conditions favor swing bowlers. "
            "Dew expected after 6 PM — team batting second has advantage. "
            "Temperature (32C) manageable but hydration breaks important.'"
        ),
    )
    return agent


# ─────────────────────────────────────────────────
# Test (only runs with: python agents/weather_agent.py)
# When imported by other files, this block is skipped entirely.
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    from langgraph.errors import GraphRecursionError

    print("=" * 50)
    print("Running Weather Impact Agent (GPT-4o-mini)")
    print("=" * 50)

    agent = create_weather_agent()

    # Simple test: ask for weather at a known venue.
    # Avoids database-dependent tools that might cause the agent to loop
    # when DB tables are empty or missing.
    try:
        result = agent.invoke(
            {
                "messages": [(
                    "user",
                    "Get the current weather for Wankhede Stadium "
                    "and tell me how it would affect a T20 match tonight."
                )]
            },
            config={"recursion_limit": 10},
        )
    except GraphRecursionError:
        print("\nAgent hit recursion limit (10 steps). Possible causes:")
        print("  - Venue not in database (add it to the venues table first)")
        print("  - Tool returned an error and the agent kept retrying")
        print("  - Rate limited by Gemini API")
        exit(1)

    # Print the full agent reasoning chain
    print("\n--- Agent Reasoning ---")
    for msg in result["messages"]:
        role = msg.__class__.__name__

        # Tool calls the agent decided to make
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"\n[{role}] Calling tool: {tc['name']}")
                print(f"  Args: {json.dumps(tc.get('args', {}), indent=2)}")

        # Tool results (what the tool returned to the agent)
        elif role == "ToolMessage":
            content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            # Truncate long tool output (full weather JSON can be huge)
            if len(content) > 300:
                print(f"\n[Tool Result] {content[:300]}...")
            else:
                print(f"\n[Tool Result] {content}")

        # Agent's text responses (including the final answer)
        elif hasattr(msg, "content") and msg.content:
            print(f"\n[{role}] {msg.content}")

    # Print the final answer clearly
    final_msg = result["messages"][-1]
    if hasattr(final_msg, "content") and final_msg.content:
        print("\n" + "=" * 50)
        print("FINAL ANALYSIS:")
        print("=" * 50)
        print(final_msg.content)