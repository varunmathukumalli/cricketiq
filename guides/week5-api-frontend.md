# Week 5: Step-by-Step Commands — FastAPI + Frontend

> **Prerequisite:** Your full agent pipeline works end-to-end (Week 4).
> This week you serve agent outputs through an API and build the dashboard.

---

## Day 29-30: FastAPI Backend

### Step 1: Create the API

The API serves data that agents have already generated. It also lets you trigger agent runs on demand.

```bash
cat <<'PYEOF' > src/api.py
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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


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

def run_agent_pipeline():
    """Run the full agent pipeline in the background."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from agents.graph import run_full_pipeline
        run_full_pipeline()
    except Exception as e:
        print(f"Agent pipeline error: {e}")


@app.post("/agents/run")
def trigger_agents(background_tasks: BackgroundTasks):
    """Trigger the agent pipeline to fetch new data, validate, predict, and report.
    Runs in the background — returns immediately."""
    background_tasks.add_task(run_agent_pipeline)
    return {"status": "Agent pipeline started", "message": "Check /agents/status for progress"}
PYEOF
```

### Step 2: Test the API

```bash
cd src
uvicorn api:app --reload
```

In another terminal:

```bash
curl http://localhost:8000/
curl http://localhost:8000/matches?limit=3
curl http://localhost:8000/predictions
curl http://localhost:8000/agents/status

# Open interactive docs
open http://localhost:8000/docs
```

---

## Day 31-32: Next.js Frontend

### Step 1: Create the app

```bash
cd /Users/varunmathukumalli/projects/cricketiq
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias
cd frontend
npm install recharts axios
```

### Step 2: API client

```bash
mkdir -p src/lib

cat <<'TSEOF' > src/lib/api.ts
import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 10000,
});

export interface Match {
  id: string;
  name: string;
  match_type: string;
  status: string;
  venue: string;
  date: string;
}

export interface Prediction {
  match_id: string;
  match_name: string;
  team_a: string;
  team_b: string;
  team_a_win_prob: number;
  team_b_win_prob: number;
  explanation: string;
}

export interface Report {
  match_id: string;
  report_text: string;
  generated_at: string;
}

export async function getMatches(limit = 20): Promise<Match[]> {
  const res = await api.get(\`/matches?limit=\${limit}\`);
  return res.data.matches;
}

export async function getMatch(id: string) {
  const res = await api.get(\`/matches/\${id}\`);
  return res.data;
}

export async function getPredictions(): Promise<Prediction[]> {
  const res = await api.get("/predictions");
  return res.data.predictions;
}

export async function getPrediction(matchId: string): Promise<Prediction> {
  const res = await api.get(\`/predictions/\${matchId}\`);
  return res.data;
}

export async function getReport(matchId: string): Promise<Report> {
  const res = await api.get(\`/reports/\${matchId}\`);
  return res.data;
}

export async function getAgentStatus() {
  const res = await api.get("/agents/status");
  return res.data;
}

export async function triggerAgents() {
  const res = await api.post("/agents/run");
  return res.data;
}
TSEOF
```

### Step 3: Home page

```bash
cat <<'TSXEOF' > src/app/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMatches, getPredictions, getAgentStatus, triggerAgents, Match, Prediction } from "@/lib/api";

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [agentStatus, setAgentStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentRunning, setAgentRunning] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const [m, p, s] = await Promise.all([getMatches(20), getPredictions(), getAgentStatus()]);
        setMatches(m);
        setPredictions(p);
        setAgentStatus(s);
      } catch (err) {
        setError("Failed to connect. Is the FastAPI backend running on :8000?");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  function getPredForMatch(matchId: string) {
    return predictions.find((p) => p.match_id === matchId);
  }

  async function handleRunAgents() {
    setAgentRunning(true);
    try {
      await triggerAgents();
      setTimeout(async () => {
        const s = await getAgentStatus();
        setAgentStatus(s);
        setAgentRunning(false);
      }, 5000);
    } catch {
      setAgentRunning(false);
    }
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center"><p>Loading...</p></div>;
  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <h2 className="text-red-800 font-bold mb-2">Connection Error</h2>
        <p className="text-red-600">{error}</p>
        <code className="text-sm text-red-500 mt-2 block">cd src && uvicorn api:app --reload</code>
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">CricketIQ</h1>
            <p className="text-gray-600">Multi-agent cricket analytics</p>
          </div>
          <button
            onClick={handleRunAgents}
            disabled={agentRunning}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {agentRunning ? "Agents running..." : "Run Agent Pipeline"}
          </button>
        </div>

        {/* Agent Status Bar */}
        {agentStatus && (
          <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-6 text-sm">
            {Object.entries(agentStatus.agent_data || {}).map(([key, val]) => (
              <div key={key}>
                <span className="text-gray-500">{key}:</span>{" "}
                <span className="font-semibold">{String(val)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Matches */}
        <div className="space-y-4">
          {matches.map((match) => {
            const pred = getPredForMatch(match.id);
            return (
              <Link key={match.id} href={`/match/${match.id}`}>
                <div className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex justify-between items-start">
                    <div>
                      <h2 className="text-lg font-semibold">{match.name}</h2>
                      <p className="text-sm text-gray-500">{match.venue} &middot; {match.match_type?.toUpperCase()}</p>
                      <p className="text-sm text-gray-400 mt-1">{match.status}</p>
                    </div>
                    {pred && (
                      <div className="text-right">
                        <p className="text-sm font-medium text-green-700">{pred.team_a}: {(pred.team_a_win_prob * 100).toFixed(0)}%</p>
                        <p className="text-sm font-medium text-blue-700">{pred.team_b}: {(pred.team_b_win_prob * 100).toFixed(0)}%</p>
                        <div className="w-32 h-2 bg-blue-200 rounded-full mt-2">
                          <div className="h-2 bg-green-500 rounded-full" style={{ width: `${pred.team_a_win_prob * 100}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </main>
  );
}
TSXEOF
```

### Step 4: Match detail page

```bash
mkdir -p src/app/match/\[id\]

cat <<'TSXEOF' > src/app/match/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getMatch, getPrediction, getReport, Prediction, Report } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function MatchPage() {
  const params = useParams();
  const matchId = params.id as string;
  const [matchData, setMatchData] = useState<any>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const match = await getMatch(matchId);
        setMatchData(match);
        try { setPrediction(await getPrediction(matchId)); } catch {}
        try { setReport(await getReport(matchId)); } catch {}
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    fetchData();
  }, [matchId]);

  if (loading) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  if (!matchData?.match) return <div className="min-h-screen flex items-center justify-center">Match not found</div>;

  const match = matchData.match;
  const performances = matchData.performances || [];
  const chartData = prediction ? [
    { name: prediction.team_a, probability: prediction.team_a_win_prob * 100 },
    { name: prediction.team_b, probability: prediction.team_b_win_prob * 100 },
  ] : [];

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="text-blue-600 hover:underline mb-4 block">← Back</Link>
        <h1 className="text-2xl font-bold mb-1">{match.name}</h1>
        <p className="text-gray-500 mb-6">{match.venue} &middot; {match.match_type?.toUpperCase()} &middot; {match.status}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {prediction && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Win Probability</h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} layout="vertical">
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                  <YAxis type="category" dataKey="name" width={80} />
                  <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                  <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
                    <Cell fill="#22c55e" /><Cell fill="#3b82f6" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {prediction.explanation && (
                <div className="mt-4 text-sm text-gray-600 bg-gray-50 p-3 rounded">
                  <p className="font-medium mb-1">Agent Explanation:</p>
                  <p className="whitespace-pre-wrap">{prediction.explanation}</p>
                </div>
              )}
            </div>
          )}

          {match.temperature && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Weather</h2>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-orange-600">{match.temperature}°C</p>
                  <p className="text-sm text-gray-500">Temperature</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-blue-600">{match.humidity}%</p>
                  <p className="text-sm text-gray-500">Humidity</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-600">{match.wind_speed}</p>
                  <p className="text-sm text-gray-500">Wind (km/h)</p>
                </div>
              </div>
              {match.weather_summary && (
                <p className="mt-4 text-sm text-gray-600 bg-gray-50 p-3 rounded">{match.weather_summary}</p>
              )}
            </div>
          )}
        </div>

        {report && (
          <div className="bg-white rounded-lg shadow p-6 mt-6">
            <h2 className="text-lg font-semibold mb-4">AI Match Report</h2>
            <div className="prose prose-sm max-w-none whitespace-pre-wrap">{report.report_text}</div>
            <p className="text-xs text-gray-400 mt-4">Generated by Claude Sonnet &middot; {report.generated_at}</p>
          </div>
        )}

        {performances.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mt-6">
            <h2 className="text-lg font-semibold mb-4">Player Performances</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2">Player</th><th className="pb-2">Team</th>
                  <th className="pb-2 text-right">Runs</th><th className="pb-2 text-right">SR</th>
                  <th className="pb-2 text-right">Wickets</th>
                </tr>
              </thead>
              <tbody>
                {performances.map((p: any, i: number) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="py-2 font-medium">{p.player_name}</td>
                    <td className="py-2 text-gray-500">{p.team}</td>
                    <td className="py-2 text-right">{p.runs_scored ?? "-"}</td>
                    <td className="py-2 text-right">{p.strike_rate ?? "-"}</td>
                    <td className="py-2 text-right">{p.wickets ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
TSXEOF
```

### Step 5: Environment + run

```bash
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
```

Run both servers:

**Terminal 1:** `cd src && uvicorn api:app --reload`
**Terminal 2:** `cd frontend && npm run dev`

Open http://localhost:3000

---

## Day 33-35: Deploy

### Step 1: Deploy FastAPI to Railway

```bash
# In project root
cat <<'EOF' > Procfile
web: cd src && uvicorn api:app --host 0.0.0.0 --port $PORT
EOF

echo "python-3.11" > runtime.txt
```

1. Go to https://railway.app → sign in with GitHub
2. New Project → Deploy from GitHub → select cricketiq
3. Add environment variables from your `.env`
4. Railway deploys automatically

### Step 2: Deploy frontend to Vercel

```bash
cd frontend
npm install -g vercel
vercel
```

Add `NEXT_PUBLIC_API_URL` = your Railway URL in Vercel settings.

### Step 3: Set up scheduled agent runs

Add a cron endpoint to trigger agents daily:

```bash
# Railway supports cron via their dashboard, or use a free service like cron-job.org
# to call POST /agents/run on your Railway URL once per day
```

---

## ✅ Week 5 Milestone Checklist

```bash
echo "=== Week 5 Checklist ==="
echo "1. API running: curl http://localhost:8000/"
echo "2. Frontend running: http://localhost:3000"
echo "3. Agent status endpoint: curl http://localhost:8000/agents/status"
echo "4. Trigger agents: curl -X POST http://localhost:8000/agents/run"
echo "5. Match detail shows: prediction + weather + report + players"
```

**Target: Working website showing agent-generated predictions and reports.**

Next: [Week 6](week6-observability-deploy.md) — Observability + Production.
