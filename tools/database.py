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
