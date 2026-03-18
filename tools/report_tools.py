"""
report_tools.py — Tools for the Report Generation Agent.

These functions gather all the data the report agent needs.
The key design principle: feed the LLM REAL data so it cannot hallucinate.
This is RAG (Retrieval-Augmented Generation) in its simplest form.
"""
import json
import os
import sys
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_match_details(match_id: str) -> dict:
    """Get full match information.

    Returns:
        Dict with match name, teams, venue, date, status, scores.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, name, match_type, status, venue, date, teams, score
        FROM matches
        WHERE id = %s
    """, (match_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {}

    return {
        "match_id": row["id"],
        "name": row["name"],
        "match_type": row["match_type"],
        "status": row["status"],
        "venue": row["venue"],
        "date": str(row["date"]) if row["date"] else "TBD",
        "teams": row["teams"] or [],
        "score": row["score"] if row["score"] else [],
    }


def get_prediction_with_explanation(match_id: str) -> dict:
    """Get the model prediction AND the explainer agent's explanation.

    Returns:
        Dict with win probabilities and explanation text.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT team_a, team_b, team_a_win_prob, team_b_win_prob,
               explanation, model_version, predicted_at
        FROM predictions
        WHERE match_id = %s
        ORDER BY predicted_at DESC
        LIMIT 1
    """, (match_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {"error": "No prediction found for this match"}

    return {
        "team_a": row["team_a"],
        "team_b": row["team_b"],
        "team_a_win_prob": float(row["team_a_win_prob"]),
        "team_b_win_prob": float(row["team_b_win_prob"]),
        "explanation": row["explanation"] or "No explanation generated yet",
        "model_version": row["model_version"],
        "predicted_at": str(row["predicted_at"]),
    }


def get_weather_summary(match_id: str) -> dict:
    """Get weather data and the Weather Agent's impact analysis.

    Returns:
        Dict with raw weather numbers and the agent's cricket-specific summary.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT temperature, humidity, wind_speed, precipitation,
               dew_point, weather_code, weather_summary
        FROM match_weather
        WHERE match_id = %s
    """, (match_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {"error": "No weather data for this match"}

    return {
        "temperature_c": float(row["temperature"]) if row["temperature"] else None,
        "humidity_pct": int(row["humidity"]) if row["humidity"] else None,
        "wind_speed_kmh": float(row["wind_speed"]) if row["wind_speed"] else None,
        "precipitation_mm": float(row["precipitation"]) if row["precipitation"] else None,
        "dew_point_c": float(row["dew_point"]) if row["dew_point"] else None,
        "weather_summary": row["weather_summary"] or "No weather analysis available",
    }


def get_player_form(team: str) -> list[dict]:
    """Get recent performance stats for a team's players.

    Looks at the last 5 matches for each player on the team.

    Args:
        team: Team name (e.g., "India")

    Returns:
        List of dicts with player name and recent stats.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            pl.name as player_name,
            pl.player_role,
            COUNT(*) as matches_played,
            COALESCE(AVG(pp.runs_scored), 0) as avg_runs,
            COALESCE(AVG(pp.strike_rate), 0) as avg_strike_rate,
            COALESCE(AVG(pp.wickets), 0) as avg_wickets,
            COALESCE(AVG(pp.economy), 0) as avg_economy,
            COALESCE(SUM(pp.runs_scored), 0) as total_runs,
            COALESCE(SUM(pp.wickets), 0) as total_wickets
        FROM player_performances pp
        JOIN players pl ON pp.player_id = pl.id
        WHERE pp.team = %s
        AND pp.match_id IN (
            SELECT id FROM matches
            WHERE teams @> ARRAY[%s]::text[]
            ORDER BY date DESC
            LIMIT 5
        )
        GROUP BY pl.name, pl.player_role
        ORDER BY COALESCE(AVG(pp.runs_scored), 0) DESC
        LIMIT 15
    """, (team, team))

    players = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()

    for p in players:
        p["avg_runs"] = round(float(p["avg_runs"]), 1)
        p["avg_strike_rate"] = round(float(p["avg_strike_rate"]), 1)
        p["avg_wickets"] = round(float(p["avg_wickets"]), 1)
        p["avg_economy"] = round(float(p["avg_economy"]), 1)

    return players


def save_report(match_id: str, report_type: str, report_text: str,
                model_used: str, prompt_tokens: int = 0,
                completion_tokens: int = 0) -> str:
    """Save a generated report to the ai_reports table.

    Args:
        match_id: The match this report is for
        report_type: "pre_match", "innings_break", or "post_match"
        report_text: The full report content
        model_used: Which LLM generated this (e.g., "claude-sonnet-4-6")
        prompt_tokens: Input token count (for cost tracking)
        completion_tokens: Output token count (for cost tracking)

    Returns:
        Confirmation string.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_reports (match_id, report_type, report_text, model_used,
                                prompt_tokens, completion_tokens)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id, report_type) DO UPDATE SET
            report_text = EXCLUDED.report_text,
            model_used = EXCLUDED.model_used,
            prompt_tokens = EXCLUDED.prompt_tokens,
            completion_tokens = EXCLUDED.completion_tokens,
            generated_at = NOW()
    """, (match_id, report_type, report_text, model_used,
          prompt_tokens, completion_tokens))
    conn.commit()
    cur.close()
    conn.close()
    return f"Report saved: {report_type} for match {match_id}"


# ─────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Testing Report Tools ===\n")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT p.match_id, m.name, p.team_a, p.team_b
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        ORDER BY p.predicted_at DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        print("No predictions yet. Run Week 3's predict.py first.")
        exit(1)

    match_id, name, team_a, team_b = row
    print(f"Testing with: {name} ({match_id})\n")

    print("1. Match details:")
    details = get_match_details(match_id)
    for k, v in details.items():
        print(f"   {k}: {v}")

    print("\n2. Prediction + explanation:")
    pred = get_prediction_with_explanation(match_id)
    for k, v in pred.items():
        val_str = str(v)[:100]
        print(f"   {k}: {val_str}")

    print("\n3. Weather summary:")
    weather = get_weather_summary(match_id)
    for k, v in weather.items():
        print(f"   {k}: {v}")

    print(f"\n4. Player form for {team_a}:")
    players = get_player_form(team_a)
    if players:
        for p in players[:5]:
            print(f"   {p['player_name']}: avg {p['avg_runs']} runs, SR {p['avg_strike_rate']}")
    else:
        print("   No player data yet (need scorecards from Week 2)")
