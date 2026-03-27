"""
api.py — FastAPI backend serving agent-generated data.

This API does NOT run agents directly in request handlers (too slow).
Instead, it reads from the database where agents have already written results.
One endpoint triggers agent runs asynchronously.

RUN: cd src && uvicorn api:app --reload
DOCS: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(
    title="CricketIQ API",
    description="AI-powered cricket analytics — served by a multi-agent system",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://cricketiq-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


@app.get("/debug")
def debug():
    """Temporary debug endpoint."""
    db_url = os.getenv("DATABASE_URL")
    has_url = db_url is not None and len(db_url) > 0
    # Show first 30 chars only for security
    preview = db_url[:30] + "..." if db_url and len(db_url) > 30 else db_url
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1 as test")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return {"db": "connected", "has_url": has_url, "url_preview": preview}
    except Exception as e:
        return {"db": "error", "has_url": has_url, "url_preview": preview, "detail": str(e)}


# ──────────────────────────────────────
# DATA ENDPOINTS (reads from DB)
# ──────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "CricketIQ Agentic API"}


@app.get("/matches")
def list_matches(limit: int = 50, match_type: str = None):
    conn = get_db()
    cur = conn.cursor()

    where_clauses = []
    params = []
    if match_type:
        where_clauses.append("match_type = %s")
        params.append(match_type)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Deduplicate by name+date, keeping the row with the most informative status
    query = f"""
        SELECT DISTINCT ON (name, date) id, name, match_type, status, venue, date
        FROM matches
        {where_sql}
        ORDER BY name, date, CASE WHEN status LIKE '%%Match starts%%' THEN 1 ELSE 0 END ASC
    """
    cur.execute(query, params)
    all_matches = cur.fetchall()

    live = []
    completed = []
    upcoming = []

    for m in all_matches:
        status = (m.get("status") or "").lower()
        if "match starts" in status or "not started" in status:
            upcoming.append(m)
        elif "won" in status or "drawn" in status or "tied" in status or "no result" in status:
            completed.append(m)
        else:
            live.append(m)

    # Sort: upcoming earliest first, completed most recent first
    upcoming.sort(key=lambda x: x.get("date") or "")
    completed.sort(key=lambda x: x.get("date") or "", reverse=True)
    live.sort(key=lambda x: x.get("date") or "", reverse=True)

    cur.close()
    conn.close()
    return {
        "live": live,
        "upcoming": upcoming[:limit],
        "completed": completed[:limit],
        "total": len(all_matches),
    }


@app.get("/matches/{match_id}")
def get_match(match_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, mw.temperature, mw.humidity, mw.wind_speed, mw.weather_summary
        FROM matches m
        LEFT JOIN match_weather mw ON m.id = mw.match_id
        WHERE m.id = %s
    """, (match_id,))
    match = cur.fetchone()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    cur.execute("""
        SELECT pp.*, p.name as player_name, p.country
        FROM player_performances pp
        JOIN players p ON pp.player_id = p.id
        WHERE pp.match_id = %s
        ORDER BY pp.runs_scored DESC NULLS LAST
    """, (match_id,))
    performances = cur.fetchall()
    cur.close()
    conn.close()
    return {"match": match, "performances": performances}


@app.get("/predictions")
def list_predictions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, m.name as match_name, m.venue, m.date
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        ORDER BY m.date DESC
    """)
    predictions = cur.fetchall()
    cur.close()
    conn.close()
    return {"predictions": predictions}


@app.get("/predictions/{match_id}")
def get_prediction(match_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, m.name as match_name
        FROM predictions p JOIN matches m ON p.match_id = m.id
        WHERE p.match_id = %s ORDER BY p.predicted_at DESC LIMIT 1
    """, (match_id,))
    prediction = cur.fetchone()
    cur.close()
    conn.close()
    if not prediction:
        raise HTTPException(status_code=404, detail="No prediction found")
    return prediction


@app.get("/reports/{match_id}")
def get_report(match_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM ai_reports
        WHERE match_id = %s ORDER BY generated_at DESC LIMIT 1
    """, (match_id,))
    report = cur.fetchone()
    cur.close()
    conn.close()
    if not report:
        raise HTTPException(status_code=404, detail="No report found")
    return report


# ──────────────────────────────────────
# AGENT STATUS ENDPOINT
# ──────────────────────────────────────

@app.get("/agents/status")
def agent_status():
    """Show what data the agents have produced."""
    conn = get_db()
    cur = conn.cursor()
    stats = {}
    for table in ["matches", "predictions", "ai_reports", "match_weather"]:
        cur.execute(f"SELECT COUNT(*) as count FROM {table}")
        stats[table] = cur.fetchone()["count"]
    cur.close()
    conn.close()
    return {"agent_data": stats}


# ──────────────────────────────────────
# TRIGGER AGENT PIPELINE (async)
# ──────────────────────────────────────

pipeline_last_error = None

def run_agent_pipeline():
    """Run the full agent pipeline in the background."""
    global pipeline_last_error
    pipeline_last_error = None
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from tools.cricket_api import fetch_current_matches, fetch_ipl_matches
        from tools.database import save_matches, query_database

        # Step 1: Fetch current matches (live, recent, upcoming internationals)
        matches = fetch_current_matches(filter_major=True)
        fetch_count = 0
        if matches:
            save_matches(matches)
            fetch_count = len(matches)

        # Step 2: Fetch IPL 2026 matches specifically
        ipl_matches = fetch_ipl_matches()
        ipl_count = 0
        if ipl_matches:
            save_matches(ipl_matches)
            ipl_count = len(ipl_matches)

        # Step 3: Batch-predict all IPL matches that don't have predictions yet
        ipl_predicted = 0
        try:
            from ml.predict import load_model, predict_match, save_predictions
            from ml.features import load_matches_dataframe, extract_winner

            ipl_unpredicted = query_database("""
                SELECT m.id, m.name, m.match_type, m.venue, m.date, m.teams
                FROM matches m
                LEFT JOIN predictions p ON m.id = p.match_id
                WHERE p.id IS NULL
                  AND (m.name ILIKE '%%IPL%%' OR m.name ILIKE '%%Indian Premier League%%')
                ORDER BY m.date ASC
            """)
            if ipl_unpredicted:
                model, metadata = load_model()
                historical_df = load_matches_dataframe()
                historical_df["winner"] = historical_df.apply(
                    lambda row: extract_winner(row["status"], row["teams"]), axis=1
                )
                ipl_preds = []
                for m in ipl_unpredicted:
                    pred = predict_match(model, metadata, historical_df, m)
                    if pred:
                        ipl_preds.append(pred)
                if ipl_preds:
                    save_predictions(ipl_preds)
                    ipl_predicted = len(ipl_preds)
        except Exception as e:
            print(f"IPL batch prediction error: {e}")

        # Step 4: Run full pipeline on non-IPL matches that need processing
        from agents.graph import run_pipeline
        db_matches = query_database("""
            SELECT m.id FROM matches m
            LEFT JOIN predictions p ON m.id = p.match_id
            WHERE p.id IS NULL
              AND m.name NOT ILIKE '%%IPL%%'
              AND m.name NOT ILIKE '%%Indian Premier League%%'
            ORDER BY m.date DESC NULLS LAST
            LIMIT 5
        """)
        pipeline_errors = []
        for m in db_matches:
            try:
                run_pipeline(m["id"])
            except Exception as e:
                pipeline_errors.append(f"{m['id']}: {e}")

        # Step 4: Run expert validation on all data
        validation_summary = ""
        try:
            from agents.cricket_expert_agent import run_full_validation
            report = run_full_validation()
            validation_summary = (
                f" | Validation: {report['total_issues']} issues "
                f"({report['critical_issues']} critical/high), "
                f"{'PASSED' if report['all_passed'] else 'ISSUES FOUND'}"
            )
        except Exception as e:
            validation_summary = f" | Validation error: {e}"

        if pipeline_errors:
            pipeline_last_error = (
                f"Fetched {fetch_count} matches + {ipl_count} IPL. "
                f"Predicted {ipl_predicted} IPL matches. "
                f"Pipeline errors: {'; '.join(pipeline_errors)}{validation_summary}"
            )
        else:
            pipeline_last_error = (
                f"OK: Fetched {fetch_count} matches + {ipl_count} IPL, "
                f"predicted {ipl_predicted} IPL matches, "
                f"ran pipeline on {len(db_matches)}{validation_summary}"
            )
    except Exception as e:
        import traceback
        pipeline_last_error = traceback.format_exc()
        print(f"Agent pipeline error: {e}")


@app.get("/agents/last-error")
def agent_last_error():
    return {"error": pipeline_last_error}


@app.get("/agents/validation")
def agent_validation():
    """Run the cricket expert validation agent and return results."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from agents.cricket_expert_agent import run_full_validation
        return run_full_validation()
    except Exception as e:
        return {"all_passed": False, "total_issues": 1, "critical_issues": 1,
                "results": [{"check": "error", "issues": [{"type": "ERROR", "severity": "high", "detail": str(e)}], "passed": False}]}


@app.post("/agents/run")
def trigger_agents(background_tasks: BackgroundTasks):
    """Trigger the agent pipeline to fetch new data, validate, predict, and report.
    Runs in the background — returns immediately."""
    background_tasks.add_task(run_agent_pipeline)
    return {"status": "Agent pipeline started", "message": "Check /agents/status for progress"}


# ──────────────────────────────────────
# IPL 2026 PLAYER ENDPOINTS
# ──────────────────────────────────────

@app.get("/ipl/teams")
def get_ipl_teams():
    """Return all 10 IPL 2026 franchises."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ipl_teams ORDER BY name")
    teams = cur.fetchall()
    cur.close()
    conn.close()
    return {"teams": teams}


@app.get("/ipl/players")
def get_ipl_players(season: int = 2026):
    """Return all IPL players grouped by team (men's IPL only)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, t.name as team_name, t.short_name, t.primary_color, t.secondary_color, t.city, t.home_ground
        FROM ipl_squad s
        JOIN ipl_teams t ON s.team_id = t.id
        WHERE s.season = %s
        ORDER BY t.name, s.player_role, s.player_name
    """, (season,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Group by team — use "id" and "name" to match frontend IPLTeam interface
    teams: dict = {}
    for row in rows:
        tid = row["team_id"]
        if tid not in teams:
            teams[tid] = {
                "id": tid,
                "name": row["team_name"],
                "short_name": row["short_name"],
                "primary_color": row["primary_color"],
                "secondary_color": row["secondary_color"],
                "city": row["city"],
                "home_ground": row.get("home_ground", ""),
                "players": [],
            }
        teams[tid]["players"].append({
            "id": row["id"],
            "player_name": row["player_name"],
            "player_role": row["player_role"],
            "batting_style": row["batting_style"],
            "bowling_style": row["bowling_style"],
            "nationality": row["nationality"],
            "is_overseas": row["is_overseas"],
        })
    return {"season": season, "teams": list(teams.values())}


@app.get("/ipl/players/{team_id}")
def get_ipl_team_players(team_id: str, season: int = 2026):
    """Return squad for a specific IPL team."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ipl_teams WHERE id = %s", (team_id,))
    team = cur.fetchone()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    cur.execute("""
        SELECT * FROM ipl_squad
        WHERE team_id = %s AND season = %s
        ORDER BY player_role, player_name
    """, (team_id, season))
    players = cur.fetchall()
    cur.close()
    conn.close()
    return {"team": team, "players": players, "season": season}


@app.get("/ipl/predictions")
def get_ipl_predictions(season: int = 2026):
    """Return stored AI predictions for IPL season top performers."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, t.name as team_name, t.short_name, t.primary_color
        FROM player_season_predictions p
        LEFT JOIN ipl_teams t ON p.team_id = t.id
        WHERE p.season = %s
        ORDER BY p.category, p.confidence DESC, p.predicted_runs DESC NULLS LAST
    """, (season,))
    predictions = cur.fetchall()
    cur.close()
    conn.close()

    grouped: dict = {}
    for pred in predictions:
        cat = pred["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(pred)
    return {"season": season, "predictions": grouped}


def _generate_ipl_predictions(season: int):
    """Background task: use Claude Sonnet to generate IPL season predictions."""
    try:
        import anthropic

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()

        # Fetch all squad members for context
        cur.execute("""
            SELECT s.player_name, s.player_role, s.nationality, s.is_overseas,
                   s.batting_style, s.bowling_style, t.name as team_name, t.id as team_id
            FROM ipl_squad s
            JOIN ipl_teams t ON s.team_id = t.id
            WHERE s.season = %s
            ORDER BY t.name, s.player_role
        """, (season,))
        squad_data = cur.fetchall()

        # Fetch any existing performance stats
        cur.execute("""
            SELECT p.player_name, COUNT(*) as matches,
                   SUM(pp.runs_scored) as total_runs,
                   SUM(pp.wickets) as total_wickets,
                   AVG(pp.strike_rate) as avg_sr
            FROM ipl_squad p
            LEFT JOIN player_performances pp ON pp.team = p.team_id
            WHERE p.season = %s
            GROUP BY p.player_name
            HAVING SUM(pp.runs_scored) > 0 OR SUM(pp.wickets) > 0
        """, (season,))
        perf_data = cur.fetchall()

        squad_summary = "\n".join([
            f"- {r['player_name']} ({r['team_name']}, {r['player_role']}, {r['nationality']})"
            for r in squad_data
        ])
        perf_summary = "\n".join([
            f"- {r['player_name']}: {r['total_runs']} runs, {r['total_wickets']} wickets in {r['matches']} matches"
            for r in perf_data
        ]) if perf_data else "No match performance data available yet for this season."

        # Build a set of valid player names for post-validation
        valid_players = {r["player_name"].lower() for r in squad_data}
        valid_team_ids = {r["team_id"] for r in squad_data}
        player_team_map = {r["player_name"].lower(): r["team_id"] for r in squad_data}

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=(
                "You are a cricket analytics expert. Analyze IPL squad data and predict "
                "top performers for the season. Respond ONLY with valid JSON."
            ),
            messages=[{
                "role": "user",
                "content": f"""Analyze the IPL {season} squads and predict top performers.

CRITICAL RULES:
- ONLY use players from the SQUADS list below. Do NOT invent or hallucinate players.
- Pakistan players are BANNED from IPL. Never include any Pakistani player.
- Every player_name and team_id MUST exactly match the squad data provided.
- If a player is not in the list, do NOT include them.

SQUADS:
{squad_summary}

SEASON STATS SO FAR:
{perf_summary}

Respond with JSON in this exact format:
{{
  "orange_cap": [
    {{
      "player_name": "Name",
      "team_id": "mi",
      "predicted_runs": 650,
      "predicted_strike_rate": 148.5,
      "confidence": "High",
      "reasoning": "Brief reason"
    }}
  ],
  "purple_cap": [
    {{
      "player_name": "Name",
      "team_id": "mi",
      "predicted_wickets": 24,
      "confidence": "High",
      "reasoning": "Brief reason"
    }}
  ],
  "breakout": [
    {{
      "player_name": "Name",
      "team_id": "mi",
      "confidence": "Medium",
      "reasoning": "Brief reason why this player will break out"
    }}
  ]
}}

Provide top 5 for orange_cap and purple_cap, top 3 for breakout.
Base predictions on known player quality, recent international form, and role in team."""
            }],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        predictions_data = json.loads(raw)

        # Validate and store predictions — reject any player not in the squad
        rejected = []
        for category, preds in predictions_data.items():
            for pred in preds:
                pname = pred.get("player_name", "")
                pname_lower = pname.lower()

                # Validation: player must exist in squad
                if pname_lower not in valid_players:
                    rejected.append(f"{pname} ({category}) — not in squad")
                    continue

                # Validation: fix team_id to match actual squad data
                correct_team = player_team_map.get(pname_lower)
                if correct_team:
                    pred["team_id"] = correct_team

                cur.execute("""
                    INSERT INTO player_season_predictions
                        (season, player_name, team_id, category,
                         predicted_runs, predicted_wickets, predicted_strike_rate,
                         confidence, reasoning)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_name, season, category) DO UPDATE SET
                        team_id = EXCLUDED.team_id,
                        predicted_runs = EXCLUDED.predicted_runs,
                        predicted_wickets = EXCLUDED.predicted_wickets,
                        predicted_strike_rate = EXCLUDED.predicted_strike_rate,
                        confidence = EXCLUDED.confidence,
                        reasoning = EXCLUDED.reasoning,
                        generated_at = NOW()
                """, (
                    season,
                    pname,
                    pred.get("team_id"),
                    category,
                    pred.get("predicted_runs"),
                    pred.get("predicted_wickets"),
                    pred.get("predicted_strike_rate"),
                    pred.get("confidence", "Medium"),
                    pred.get("reasoning"),
                ))
        if rejected:
            print(f"IPL predictions: REJECTED {len(rejected)} invalid entries: {rejected}")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        import traceback
        print(f"IPL predictions error: {traceback.format_exc()}")


@app.post("/ipl/predictions/generate")
def generate_ipl_predictions(background_tasks: BackgroundTasks, season: int = 2026):
    """Trigger Claude Sonnet to generate IPL season performance predictions.
    Runs in background — check /ipl/predictions for results."""
    background_tasks.add_task(_generate_ipl_predictions, season)
    return {"status": "started", "message": f"Generating IPL {season} predictions with Claude Sonnet"}


@app.get("/ipl/player-stats/{player_name}")
def get_player_stats(player_name: str):
    """Return profile + match-by-match performance history for an IPL squad member."""
    conn = get_db()
    cur = conn.cursor()

    # Squad profile (from ipl_squad)
    cur.execute("""
        SELECT s.*, t.name as team_name, t.short_name, t.primary_color, t.city
        FROM ipl_squad s
        JOIN ipl_teams t ON s.team_id = t.id
        WHERE LOWER(s.player_name) = LOWER(%s)
        ORDER BY s.season DESC
        LIMIT 1
    """, (player_name,))
    squad_row = cur.fetchone()

    # Also check the legacy players table
    cur.execute("""
        SELECT * FROM players WHERE LOWER(name) = LOWER(%s) LIMIT 1
    """, (player_name,))
    legacy_row = cur.fetchone()

    # Build player profile from whichever source has data
    if squad_row:
        player = {
            "name": squad_row["player_name"],
            "player_role": squad_row["player_role"],
            "batting_style": squad_row["batting_style"],
            "bowling_style": squad_row["bowling_style"],
            "country": squad_row["nationality"],
            "team": squad_row["team_name"],
            "short_name": squad_row["short_name"],
            "primary_color": squad_row["primary_color"],
        }
    elif legacy_row:
        player = {
            "name": legacy_row["name"],
            "player_role": legacy_row["player_role"],
            "batting_style": legacy_row["batting_style"],
            "bowling_style": legacy_row["bowling_style"],
            "country": legacy_row["country"],
            "team": None,
        }
    else:
        raise HTTPException(status_code=404, detail="Player not found")

    # Match-by-match performances
    cur.execute("""
        SELECT pp.*, m.name as match_name, m.date as match_date
        FROM player_performances pp
        JOIN players pl ON pp.player_id = pl.id
        JOIN matches m ON pp.match_id = m.id
        WHERE LOWER(pl.name) = LOWER(%s)
        ORDER BY m.date DESC
    """, (player_name,))
    performances = cur.fetchall()

    # Aggregate stats
    cur.execute("""
        SELECT
            COUNT(*) as innings,
            COALESCE(SUM(pp.runs_scored), 0) as total_runs,
            CASE WHEN COUNT(pp.runs_scored) > 0
                THEN ROUND(AVG(pp.runs_scored)::numeric, 1) ELSE 0 END as batting_avg,
            COALESCE(SUM(pp.wickets), 0) as total_wickets,
            CASE WHEN SUM(pp.overs_bowled) > 0
                THEN ROUND((SUM(pp.runs_conceded) / SUM(pp.overs_bowled))::numeric, 2) ELSE 0 END as bowling_economy,
            COALESCE(MAX(pp.runs_scored), 0) as highest_score,
            COALESCE(MAX(pp.wickets), 0) as best_wickets
        FROM player_performances pp
        JOIN players pl ON pp.player_id = pl.id
        WHERE LOWER(pl.name) = LOWER(%s)
    """, (player_name,))
    aggregate = cur.fetchone()

    cur.close()
    conn.close()
    return {"player": player, "performances": performances, "aggregate": aggregate}