"""
database.py — PostgreSQL read/write tools.

These are plain Python functions, NOT agents.
Agents will call these as tools.
"""
import psycopg2
import psycopg2.extras
import json
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def query_database(sql: str, params: tuple = None) -> list[dict]:
    """Run a SELECT query and return results as list of dicts.

    Args:
        sql: The SQL query to run
        params: Optional parameters for the query

    Returns:
        List of dictionaries, one per row
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params)
    results = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return results


def save_matches(matches: list[dict]) -> dict:
    """Insert or update matchein the database.

    Args:
        matches: List of match dicts with keys: id, name, match_type, status, venue, date, teams, score

    Returns:
        Dict with counts: {"inserted": N, "updated": N}
    """
    conn = get_connection()
    cur = conn.cursor()
    inserted, updated = 0, 0

    for match in matches:
        if not match.get("id"):
            continue

        cur.execute("""
            INSERT INTO matches (id, name, match_type, status, venue, date, teams, score, api_response)
            VALUES (%(id)s, %(name)s, %(match_type)s, %(status)s, %(venue)s, %(date)s,
                    %(teams)s, %(score)s, %(api_response)s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                score = EXCLUDED.score,
                api_response = EXCLUDED.api_response,
                updated_at = NOW()
            RETURNING (xmax = 0) AS is_insert
        """, {
            "id": match["id"],
            "name": match.get("name", "Unknown"),
            "match_type": match.get("match_type"),
            "status": match.get("status"),
            "venue": match.get("venue"),
            "date": match.get("date"),
            "teams": match.get("teams", []),
            "score": json.dumps(match.get("score", [])),
            "api_response": json.dumps(match),
        })
        result = cur.fetchone()
        if result[0]:
            inserted += 1
        else:
            updated += 1

    conn.commit()
    cur.close()
    conn.close()
    return {"inserted": inserted, "updated": updated}


def save_weather(weather_results: list[dict]) -> dict:
    """Insert or update weather data in match_weather table.

    Args:
        weather_results: List of weather dicts with keys:
            match_id, temperature_c, humidity_pct, wind_speed_kmh,
            precipitation_mm, dew_point_c, conditions (weather_code not available, stored as NULL),
            cricket_impact (stored as weather_summary)

    Returns:
        Dict with counts: {"inserted": N, "updated": N, "skipped": N}
    """
    conn = get_connection()
    cur = conn.cursor()
    inserted, updated, skipped = 0, 0, 0

    for w in weather_results:
        if "error" in w or not w.get("match_id"):
            skipped += 1
            continue

        cur.execute("""
            INSERT INTO match_weather (match_id, temperature, humidity, wind_speed,
                                       precipitation, dew_point, weather_summary)
            VALUES (%(match_id)s, %(temperature)s, %(humidity)s, %(wind_speed)s,
                    %(precipitation)s, %(dew_point)s, %(weather_summary)s)
            ON CONFLICT (match_id) DO UPDATE SET
                temperature = EXCLUDED.temperature,
                humidity = EXCLUDED.humidity,
                wind_speed = EXCLUDED.wind_speed,
                precipitation = EXCLUDED.precipitation,
                dew_point = EXCLUDED.dew_point,
                weather_summary = EXCLUDED.weather_summary,
                fetched_at = NOW()
            RETURNING (xmax = 0) AS is_insert
        """, {
            "match_id": w["match_id"],
            "temperature": w.get("temperature_c"),
            "humidity": w.get("humidity_pct"),
            "wind_speed": w.get("wind_speed_kmh"),
            "precipitation": w.get("precipitation_mm"),
            "dew_point": w.get("dew_point_c"),
            "weather_summary": w.get("cricket_impact"),
        })
        result = cur.fetchone()
        if result[0]:
            inserted += 1
        else:
            updated += 1

    conn.commit()
    cur.close()
    conn.close()
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def save_player_performances(match_id: str, scorecard_data: dict) -> int:
    """Parse a CricData scorecard response and save player performances.

    Args:
        match_id: The match ID
        scorecard_data: Raw response from fetch_match_scorecard()

    Returns:
        Number of player performance rows saved
    """
    scorecard = scorecard_data.get("scorecard", [])
    if not scorecard:
        return 0

    teams = scorecard_data.get("teams", [])
    conn = get_connection()
    cur = conn.cursor()
    count = 0

    for innings_idx, innings in enumerate(scorecard):
        # Determine team name for this innings
        team_name = teams[innings_idx] if innings_idx < len(teams) else f"Team {innings_idx + 1}"

        # Process batters
        for b in innings.get("batting", []):
            batsman = b.get("batsman", {})
            player_id = batsman.get("id")
            player_name = batsman.get("name")
            if not player_id or not player_name:
                continue

            # Upsert player
            cur.execute("""
                INSERT INTO players (id, name, country)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """, (player_id, player_name, team_name))

            # Upsert batting performance
            cur.execute("""
                INSERT INTO player_performances (match_id, player_id, team, runs_scored, balls_faced, fours, sixes, strike_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id, player_id) DO UPDATE SET
                    runs_scored = EXCLUDED.runs_scored,
                    balls_faced = EXCLUDED.balls_faced,
                    fours = EXCLUDED.fours,
                    sixes = EXCLUDED.sixes,
                    strike_rate = EXCLUDED.strike_rate
            """, (
                match_id, player_id, team_name,
                b.get("r"), b.get("b"), b.get("4s"), b.get("6s"), b.get("sr"),
            ))
            count += 1

        # Process bowlers
        for bw in innings.get("bowling", []):
            bowler = bw.get("bowler", {})
            player_id = bowler.get("id")
            player_name = bowler.get("name")
            if not player_id or not player_name:
                continue

            # The bowling team is the OTHER team
            bowling_team = teams[1 - innings_idx] if innings_idx < len(teams) and len(teams) > 1 else team_name

            # Upsert player
            cur.execute("""
                INSERT INTO players (id, name, country)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """, (player_id, player_name, bowling_team))

            # Upsert bowling data — merge with any existing batting row
            cur.execute("""
                INSERT INTO player_performances (match_id, player_id, team, overs_bowled, runs_conceded, wickets, economy)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id, player_id) DO UPDATE SET
                    overs_bowled = EXCLUDED.overs_bowled,
                    runs_conceded = EXCLUDED.runs_conceded,
                    wickets = EXCLUDED.wickets,
                    economy = EXCLUDED.economy
            """, (
                match_id, player_id, bowling_team,
                bw.get("o"), bw.get("r"), bw.get("w"), bw.get("eco"),
            ))
            count += 1

    conn.commit()
    cur.close()
    conn.close()
    return count


def get_database_status() -> dict:
    """Get a summary of what's in the database. Used by the Orchestrator."""
    conn = get_connection()
    cur = conn.cursor()

    stats = {}
    for table in ["matches", "players", "player_performances", "match_weather", "predictions", "ai_reports"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]
        except Exception:
            stats[table] = 0
            conn.rollback()

    # Last update time
    try:
        cur.execute("SELECT MAX(updated_at) FROM matches")
        stats["last_match_update"] = str(cur.fetchone()[0])
    except Exception:
        stats["last_match_update"] = "never"
        conn.rollback()

    cur.close()
    conn.close()
    return stats


# Test
if __name__ == "__main__":
    print("Database status:")
    status = get_database_status()
    for table, count in status.items():
        print(f"  {table}: {count}")
