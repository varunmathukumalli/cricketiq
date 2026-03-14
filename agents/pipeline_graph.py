"""
pipeline_graph.py — The Fetch → Validate → Weather pipeline.

CONCEPT: Connecting multiple agents into a single graph.
         Each agent becomes a node. The graph orchestrates the flow.
         This is how you build complex multi-agent systems in LangGraph.

Pipeline:
  fetch_data → validate_data → get_weather → END

Flagged matches are auto-approved (logged for review later).
Rejected matches are dropped.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import json

load_dotenv()

from tools.cricket_api import fetch_current_matches
from tools.database import save_matches, save_weather, query_database
from tools.weather_api import fetch_weather_for_venue, describe_weather_code
from agents.validation_agent import validate_match, validate_batch
from src.models import ValidationStatus


# ─────────────────────────────────────────────────
# Pipeline State
# ─────────────────────────────────────────────────

class PipelineState(TypedDict):
    messages: Annotated[list, add_messages]

    # Fetch stage
    raw_matches: list[dict]
    fetch_summary: str

    # Validation stage
    valid_matches: list[dict]
    flagged_matches: list[dict]
    rejected_matches: list[dict]

    # Weather stage
    weather_results: list[dict]

    # Final
    clean_matches: list[dict]  # Matches that passed validation (ready for ML)
    pipeline_summary: str


# ─────────────────────────────────────────────────
# Node 1: Fetch Data
# ─────────────────────────────────────────────────

def fetch_data_node(state: PipelineState) -> dict:
    """Fetch current cricket matches from the API and save to database."""
    print("[fetch_data] Fetching current matches from CricketData.org...")

    try:
        matches = fetch_current_matches()
    except Exception as e:
        return {
            "messages": [("assistant", f"Fetch failed: {str(e)}")],
            "raw_matches": [],
            "fetch_summary": f"Error: {str(e)}",
        }

    if not matches:
        # Fall back to database if API returns nothing
        print("[fetch_data] API returned no matches. Checking database...")
        db_matches = query_database(
            "SELECT id, name, match_type, status, venue, date::text, teams, score::text "
            "FROM matches ORDER BY updated_at DESC LIMIT 10"
        )
        matches = db_matches if db_matches else []

    if matches:
        # Save to database (handles duplicates via upsert)
        try:
            result = save_matches(matches)
            summary = f"Fetched {len(matches)} matches (inserted: {result['inserted']}, updated: {result['updated']})"
        except Exception:
            summary = f"Fetched {len(matches)} matches (save to DB failed, continuing with raw data)"
    else:
        summary = "No matches available from API or database."

    print(f"[fetch_data] {summary}")
    return {
        "messages": [("assistant", summary)],
        "raw_matches": matches,
        "fetch_summary": summary,
    }


# ─────────────────────────────────────────────────
# Node 2: Validate Data
# ─────────────────────────────────────────────────

def validate_data_node(state: PipelineState) -> dict:
    """Run validation on all fetched matches.

    Flagged matches are auto-approved and included in clean matches.
    Only REJECTED matches are dropped.
    """
    matches = state.get("raw_matches", [])

    if not matches:
        print("[validate_data] No matches to validate.")
        return {
            "messages": [("assistant", "No matches to validate.")],
            "valid_matches": [],
            "flagged_matches": [],
            "rejected_matches": [],
        }

    print(f"[validate_data] Validating {len(matches)} matches...")

    valid = []
    flagged = []
    rejected = []

    for match in matches:
        try:
            result = validate_match(match)

            if result.status == ValidationStatus.VALID:
                valid.append(match)
            elif result.status == ValidationStatus.FLAGGED:
                # Auto-approve flagged matches — log for awareness but don't block
                print(f"  [auto-approved] {match.get('name', '?')}: {result.summary}")
                flagged.append(match)
            else:
                print(f"  [rejected] {match.get('name', '?')}: {result.summary}")
                rejected.append(match)

        except Exception as e:
            print(f"  [error] {match.get('id', '?')}: {e}")
            # Treat validation errors as flagged (auto-approve)
            flagged.append(match)

    summary = f"Validation: {len(valid)} valid, {len(flagged)} auto-approved, {len(rejected)} rejected"
    print(f"[validate_data] {summary}")

    return {
        "messages": [("assistant", summary)],
        "valid_matches": valid,
        "flagged_matches": flagged,
        "rejected_matches": rejected,
    }


# ─────────────────────────────────────────────────
# Node 3: Get Weather
# ─────────────────────────────────────────────────

def get_weather_node(state: PipelineState) -> dict:
    """Fetch weather data for all clean matches (valid + auto-approved)."""
    # Combine valid + flagged (auto-approved)
    clean_matches = list(state.get("valid_matches", []))
    clean_matches.extend(state.get("flagged_matches", []))

    if not clean_matches:
        print("[get_weather] No clean matches for weather lookup.")
        return {
            "messages": [("assistant", "No matches to fetch weather for.")],
            "weather_results": [],
            "clean_matches": [],
            "pipeline_summary": "Pipeline complete. No clean matches produced.",
        }

    print(f"[get_weather] Fetching weather for {len(clean_matches)} matches...")

    weather_results = []
    for match in clean_matches:
        venue = match.get("venue")
        if not venue:
            weather_results.append({
                "match_id": match.get("id"),
                "error": "No venue — cannot fetch weather",
            })
            continue

        # Extract date
        date_str = None
        raw_date = match.get("date")
        if raw_date:
            date_str = str(raw_date)[:10]

        try:
            weather = fetch_weather_for_venue(venue, date_str)

            if "error" not in weather:
                avg = weather.get("match_hours_avg", {})
                code = avg.get("weather_code")
                conditions = describe_weather_code(code) if code is not None else "Unknown"

                # Generate cricket impact summary
                humidity = avg.get("humidity_pct", 0)
                temp = avg.get("temperature_c", 0)
                wind = avg.get("wind_speed_kmh", 0)
                precip = avg.get("precipitation_mm", 0)
                dew_risk = weather.get("dew_risk", {})

                impact_parts = []
                if humidity and humidity > 70:
                    impact_parts.append(f"High humidity ({humidity}%) favors swing bowlers")
                if temp and temp > 35:
                    impact_parts.append(f"Hot conditions ({temp}C) — fatigue factor")
                if wind and wind > 20:
                    impact_parts.append(f"Strong wind ({wind} km/h) affects ball flight")
                if precip and precip > 0:
                    impact_parts.append(f"Rain expected ({precip}mm) — delays possible")
                dew_humidity_8pm = dew_risk.get("humidity_8pm")
                if dew_humidity_8pm and dew_humidity_8pm > 80:
                    impact_parts.append("Evening dew likely — advantage batting second")

                if not impact_parts:
                    impact_parts.append(f"{conditions}, good conditions for cricket")

                weather_summary = ". ".join(impact_parts) + "."

                weather_results.append({
                    "match_id": match.get("id"),
                    "match_name": match.get("name"),
                    "venue": venue,
                    "temperature_c": avg.get("temperature_c"),
                    "humidity_pct": avg.get("humidity_pct"),
                    "wind_speed_kmh": avg.get("wind_speed_kmh"),
                    "precipitation_mm": avg.get("precipitation_mm"),
                    "dew_point_c": avg.get("dew_point_c"),
                    "conditions": conditions,
                    "cricket_impact": weather_summary,
                })
            else:
                weather_results.append({
                    "match_id": match.get("id"),
                    "error": weather["error"],
                })

        except Exception as e:
            weather_results.append({
                "match_id": match.get("id"),
                "error": str(e),
            })

    successful = [w for w in weather_results if "error" not in w]
    failed = [w for w in weather_results if "error" in w]

    # Save weather data to database
    if successful:
        try:
            save_result = save_weather(weather_results)
            print(f"[get_weather] Saved to DB: {save_result['inserted']} inserted, {save_result['updated']} updated, {save_result['skipped']} skipped")
        except Exception as e:
            print(f"[get_weather] Failed to save weather to DB: {e}")

    summary = (
        f"Pipeline complete! "
        f"{len(clean_matches)} matches validated, "
        f"{len(successful)} weather reports generated, "
        f"{len(failed)} weather lookups failed."
    )
    print(f"[get_weather] {summary}")

    return {
        "messages": [("assistant", summary)],
        "weather_results": weather_results,
        "clean_matches": clean_matches,
        "pipeline_summary": summary,
    }


# ─────────────────────────────────────────────────
# Build the pipeline
# ─────────────────────────────────────────────────

def build_pipeline():
    """Build the Fetch -> Validate -> Weather pipeline graph.

    No HITL — flagged matches are auto-approved, rejected matches are dropped.

    Returns:
        Compiled graph.
    """
    graph_builder = StateGraph(PipelineState)

    # Add nodes
    graph_builder.add_node("fetch_data", fetch_data_node)
    graph_builder.add_node("validate_data", validate_data_node)
    graph_builder.add_node("get_weather", get_weather_node)

    # Linear pipeline: fetch → validate → weather → END
    graph_builder.add_edge(START, "fetch_data")
    graph_builder.add_edge("fetch_data", "validate_data")
    graph_builder.add_edge("validate_data", "get_weather")
    graph_builder.add_edge("get_weather", END)

    graph = graph_builder.compile()
    return graph


# ─────────────────────────────────────────────────
# Run the full pipeline
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("CricketIQ Pipeline: Fetch -> Validate -> Weather")
    print("=" * 60)

    pipeline = build_pipeline()

    initial_state = {
        "messages": [],
        "raw_matches": [],
        "fetch_summary": "",
        "valid_matches": [],
        "flagged_matches": [],
        "rejected_matches": [],
        "weather_results": [],
        "clean_matches": [],
        "pipeline_summary": "",
    }

    # ── Run the pipeline (no interrupts, runs straight through) ──
    print("\n[Pipeline] Starting...")
    result = pipeline.invoke(initial_state)

    # ── Print final results ──
    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"\n{result.get('pipeline_summary', 'No summary')}")

    weather = result.get("weather_results", [])
    if weather:
        successful = [w for w in weather if "error" not in w]
        failed = [w for w in weather if "error" in w]

        if successful:
            print(f"\nWeather Reports ({len(successful)}):")
            for w in successful[:5]:
                print(f"  {w.get('match_name', '?')} at {w.get('venue', '?')}:")
                print(f"    {w.get('temperature_c')}C, {w.get('humidity_pct')}% humidity, {w.get('conditions')}")
                print(f"    Impact: {w.get('cricket_impact', 'N/A')}")

        if failed:
            print(f"\nFailed lookups ({len(failed)}):")
            for w in failed[:5]:
                print(f"  {w.get('match_id', '?')}: {w['error']}")

    print(f"\nGraph: START -> fetch_data -> validate_data -> get_weather -> END")
