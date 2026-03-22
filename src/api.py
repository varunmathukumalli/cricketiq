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
def list_matches(limit: int = 20, match_type: str = None):
    conn = get_db()
    cur = conn.cursor()
    query = "SELECT id, name, match_type, status, venue, date FROM matches"
    params = []
    if match_type:
        query += " WHERE match_type = %s"
        params.append(match_type)
    query += " ORDER BY date DESC LIMIT %s"
    params.append(limit)
    cur.execute(query, params)
    matches = cur.fetchall()
    cur.close()
    conn.close()
    return {"matches": matches, "count": len(matches)}


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
        from agents.graph import run_full_pipeline
        run_full_pipeline()
    except Exception as e:
        import traceback
        pipeline_last_error = traceback.format_exc()
        print(f"Agent pipeline error: {e}")


@app.get("/agents/last-error")
def agent_last_error():
    return {"error": pipeline_last_error}


@app.post("/agents/run")
def trigger_agents(background_tasks: BackgroundTasks):
    """Trigger the agent pipeline to fetch new data, validate, predict, and report.
    Runs in the background — returns immediately."""
    background_tasks.add_task(run_agent_pipeline)
    return {"status": "Agent pipeline started", "message": "Check /agents/status for progress"}