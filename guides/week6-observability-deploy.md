# Week 6: Step-by-Step Commands — Observability + Production

> **Prerequisite:** Your full pipeline works (Week 5) — agents run, API serves data, frontend displays it.
> This week you add monitoring, cost tracking, and ship it.

**What you are building this week:**
- **LangSmith tracing** — see every agent decision, tool call, and LLM response in a dashboard
- **Cost tracking** — know how much each agent costs per run
- **Health monitoring** — Prometheus metrics + basic alerting
- **Production deployment** — scheduled agent runs, error recovery

**LangGraph concepts you will learn:**
- Checkpointing (save/resume graph state)
- Tracing and observability
- Production patterns (retries, timeouts, graceful degradation)

---

## Day 36: LangSmith Tracing

### What is LangSmith?

LangSmith is LangChain's observability platform. It records every:
- LLM call (prompt, response, tokens, latency)
- Tool call (input, output)
- Agent decision (reasoning trace)

Think of it as "developer tools" for agents — like Chrome DevTools but for LLM workflows.

**Free tier:** 5,000 traces/month (more than enough for development).

### Step 1: Set up LangSmith

```bash
# 1. Go to https://smith.langchain.com and create a free account
# 2. Create a new project called "cricketiq"
# 3. Get your API key from Settings → API Keys

# Add to your .env file
cat <<'EOF' >> .env

# === LangSmith (Observability) ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=cricketiq
EOF
```

> **That's it.** LangGraph automatically sends traces to LangSmith when these env vars are set. No code changes needed.

### Step 2: Run your pipeline and check traces

```bash
source venv/bin/activate

# Run the full pipeline (fetches matches, then runs pipeline on each)
python -c "
from tools.cricket_api import fetch_current_matches
from tools.database import save_matches, query_database
from agents.graph import run_pipeline

# Fetch matches first
matches = fetch_current_matches()
if matches:
    save_matches(matches)
    print(f'Fetched {len(matches)} matches')

# Run pipeline on matches without predictions
db_matches = query_database('''
    SELECT m.id, m.name FROM matches m
    LEFT JOIN predictions p ON m.id = p.match_id
    WHERE p.id IS NULL
    ORDER BY m.date DESC NULLS LAST LIMIT 3
''')
for m in db_matches:
    print(f'Running pipeline for: {m[\"name\"]}')
    run_pipeline(m['id'])
"

# Now go to https://smith.langchain.com → cricketiq project
# You should see traces for every agent run
```

### Step 3: What to look for in LangSmith

When you open a trace, you'll see:
1. **The graph execution** — which nodes ran and in what order
2. **Each LLM call** — the exact prompt sent, response received, token count, latency
3. **Tool calls** — what tools the agent called and what they returned
4. **Errors** — if anything failed, you'll see exactly where

This is incredibly valuable for debugging. Instead of adding print statements, you get a full visual trace.

---

## Day 37: Cost Tracking

### Step 1: Create a cost tracker

```bash
cat <<'PYEOF' > tools/cost_tracker.py
"""
cost_tracker.py — Track LLM API costs per agent run.

Logs token usage and estimated cost to the database.
"""
import os
from datetime import datetime
from tools.database import get_connection


# Approximate pricing per 1M tokens (as of 2025)
PRICING = {
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
}


def setup_cost_table():
    """Create the cost tracking table if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_costs (
            id SERIAL PRIMARY KEY,
            agent_name TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            estimated_cost DECIMAL DEFAULT 0,
            run_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def log_cost(agent_name: str, model: str, input_tokens: int, output_tokens: int):
    """Log the cost of an agent run."""
    pricing = PRICING.get(model, {"input": 1.0, "output": 1.0})
    cost = (input_tokens * pricing["input"] / 1_000_000) + \
           (output_tokens * pricing["output"] / 1_000_000)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO agent_costs (agent_name, model, input_tokens, output_tokens, estimated_cost)
        VALUES (%s, %s, %s, %s, %s)
    """, (agent_name, model, input_tokens, output_tokens, cost))
    conn.commit()
    cur.close()
    conn.close()
    return cost


def get_cost_summary(days: int = 30) -> dict:
    """Get cost summary for the last N days."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            agent_name,
            model,
            COUNT(*) as runs,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(estimated_cost) as total_cost
        FROM agent_costs
        WHERE run_at > NOW() - INTERVAL '%s days'
        GROUP BY agent_name, model
        ORDER BY total_cost DESC
    """, (days,))

    results = cur.fetchall()
    cur.close()
    conn.close()

    summary = []
    total = 0
    for row in results:
        entry = {
            "agent": row[0],
            "model": row[1],
            "runs": row[2],
            "input_tokens": row[3],
            "output_tokens": row[4],
            "cost": float(row[5]),
        }
        summary.append(entry)
        total += entry["cost"]

    return {"agents": summary, "total_cost": total, "period_days": days}


# Initialize
if __name__ == "__main__":
    setup_cost_table()
    print("Cost tracking table created.")
    print("\nCurrent cost summary:")
    summary = get_cost_summary()
    if summary["agents"]:
        for agent in summary["agents"]:
            print(f"  {agent['agent']} ({agent['model']}): ${agent['cost']:.4f} over {agent['runs']} runs")
        print(f"\n  Total: ${summary['total_cost']:.4f}")
    else:
        print("  No runs recorded yet.")
PYEOF

# Set up the table
python tools/cost_tracker.py
```

### Step 2: Add cost tracking to your agents

Add a LangChain callback to capture token usage. In your `agents/graph.py`, after each agent runs:

```python
# Example: after the fetch agent runs, log its cost
from tools.cost_tracker import log_cost

# In your node function, after the agent returns:
# result = agent.invoke(...)
# Extract token usage from the result's response metadata
# log_cost("fetch_agent", "gemini-2.0-flash", input_tokens, output_tokens)
```

> **Note:** LangSmith also tracks costs automatically if you're using it. This local tracker is for when you want to query costs from your own database.

### Step 3: Add a cost endpoint to FastAPI

```python
# Add to src/api.py

@app.get("/agents/costs")
def agent_costs(days: int = 30):
    """Get agent cost breakdown."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from tools.cost_tracker import get_cost_summary
    return get_cost_summary(days)
```

---

## Day 38: Checkpointing

### What is Checkpointing?

Checkpointing saves the graph state at each step. If the pipeline crashes halfway through (network error, API rate limit), you can **resume from where it stopped** instead of starting over.

### Step 1: Add a checkpointer to your graph

```bash
cat <<'PYEOF' > agents/checkpointed_graph.py
"""
checkpointed_graph.py — Your graph with persistence.

CONCEPT: Checkpointing saves state after each node runs.
         If the graph crashes, you can resume from the last checkpoint.
         This is critical for production — agent pipelines can take minutes,
         and you don't want to restart from scratch on every failure.
"""
from langgraph.checkpoint.memory import MemorySaver
from agents.graph import build_graph  # your existing graph builder

# MemorySaver stores checkpoints in memory (good for development)
# For production, use SqliteSaver or PostgresSaver
memory = MemorySaver()

# Compile with checkpointer
graph = build_graph().compile(checkpointer=memory)


def run_with_checkpointing():
    """Run the graph with checkpointing enabled."""
    # thread_id identifies this particular run
    # If the graph crashes, re-invoke with the same thread_id to resume
    config = {"configurable": {"thread_id": "pipeline-run-1"}}

    result = graph.invoke(
        {
            "messages": [("user", "Run the full CricketIQ pipeline")],
            "matches_fetched": [],
            "validation_result": {},
            "weather_data": [],
            "predictions": [],
            "explanations": [],
            "reports": [],
            "current_task": "",
            "errors": [],
            "should_continue": True,
        },
        config=config,
    )
    return result


def get_graph_state(thread_id: str = "pipeline-run-1"):
    """Inspect the saved state of a graph run."""
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    return {
        "current_node": state.next,  # What node is next
        "values": {k: type(v).__name__ for k, v in state.values.items()},
        "created_at": str(state.created_at) if state.created_at else None,
    }


if __name__ == "__main__":
    print("Running graph with checkpointing...")
    result = run_with_checkpointing()
    print(f"\nGraph completed. State keys: {list(result.keys())}")

    print("\nSaved state:")
    state = get_graph_state()
    print(f"  Next node: {state['current_node']}")
    print(f"  State fields: {state['values']}")
PYEOF

python agents/checkpointed_graph.py
```

> **Key concept:** `thread_id` identifies a conversation/run. Same thread_id = resume. New thread_id = fresh start. This is how chat applications remember conversation history.

### Step 2: PostgreSQL checkpointer (production)

For production, use a persistent checkpointer:

```bash
pip install langgraph-checkpoint-postgres
```

```python
# Replace MemorySaver with:
from langgraph.checkpoint.postgres import PostgresSaver
import os

checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
checkpointer.setup()  # Creates the checkpoint tables

graph = build_graph().compile(checkpointer=checkpointer)
```

---

## Day 39: Health Monitoring

### Step 1: Add health metrics to FastAPI

```bash
pip install prometheus-fastapi-instrumentator
```

Add to `src/api.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

# After app = FastAPI(...)
Instrumentator().instrument(app).expose(app)

# This automatically adds a /metrics endpoint with:
# - Request count, latency, error rates
# - Python process metrics (memory, CPU)
```

### Step 2: Add an agent health endpoint

```python
# Add to src/api.py

@app.get("/health")
def health_check():
    """Full health check — database, agents, costs."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from tools.database import get_database_status
    from tools.cost_tracker import get_cost_summary

    db_status = get_database_status()
    costs = get_cost_summary(7)

    # Check if agents have run recently
    from tools.database import query_database
    last_run = query_database(
        "SELECT MAX(run_at) as last_run FROM agent_costs"
    )

    return {
        "status": "healthy",
        "database": db_status,
        "costs_last_7_days": f"${costs['total_cost']:.4f}",
        "last_agent_run": last_run[0]["last_run"] if last_run else "never",
    }
```

### Step 3: Test health endpoints

```bash
# Start the API
cd src && uvicorn api:app --reload

# In another terminal
curl http://localhost:8000/health | python -m json.tool
curl http://localhost:8000/metrics | head -20
curl http://localhost:8000/agents/costs | python -m json.tool
```

---

## Day 40: Error Recovery + Retries

### Step 1: Add retry logic to agent nodes

```python
# Pattern for any agent node — add to your agents
import time

def node_with_retry(state, agent, max_retries=3):
    """Run an agent node with retry on failure."""
    for attempt in range(max_retries):
        try:
            return agent.invoke(state)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"  Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  All {max_retries} attempts failed: {e}")
                return {"errors": state.get("errors", []) + [str(e)]}
```

### Step 2: Add a fallback node

```python
# In your graph, add a fallback node for when agents fail

def fallback_node(state):
    """Handle agent failures gracefully."""
    errors = state.get("errors", [])
    if errors:
        print(f"  Pipeline had {len(errors)} errors: {errors}")
        # Log errors, send notification, etc.
    return {"should_continue": False}

# Add to your graph:
# graph_builder.add_node("fallback", fallback_node)
# Add conditional edge: if errors > 0, go to fallback
```

---

## Day 41: Production Deployment Checklist

### Step 1: Environment variables for production

```bash
cat <<'EOF' > .env.production.example
# === LLM API Keys ===
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
OPENAI_API_KEY=sk-...

# === Cricket Data ===
CRICKET_API_KEY=...

# === Database (use your hosted Postgres URL) ===
DATABASE_URL=postgresql://user:pass@host:5432/cricketiq

# === LangSmith ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=cricketiq-prod

# === Settings ===
ENVIRONMENT=production
LOG_LEVEL=WARNING
EOF
```

### Step 2: Deploy backend to Railway

```bash
# Procfile already created in Week 5
# Push to GitHub and Railway auto-deploys

git add -A
git commit -m "Week 6: observability, cost tracking, checkpointing"
git push origin main
```

Railway dashboard: Add all env vars from `.env.production.example`

### Step 3: Set up scheduled agent runs

Use cron-job.org (free) to call your API:

1. Go to https://cron-job.org → create free account
2. Add a new cron job:
   - URL: `https://your-railway-url.up.railway.app/agents/run`
   - Method: POST
   - Schedule: Every 6 hours (4 times/day)

### Step 4: Final verification

```bash
# Test production endpoints
curl https://your-railway-url.up.railway.app/health
curl https://your-railway-url.up.railway.app/agents/status
curl https://your-railway-url.up.railway.app/agents/costs
curl https://your-railway-url.up.railway.app/matches?limit=3
```

---

## Day 42: Demo Preparation

### Create a demo script

```bash
cat <<'PYEOF' > demo.py
"""
demo.py — Quick demo of the CricketIQ multi-agent system.

Shows: agent pipeline run → data in DB → predictions → report
"""
import time
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("CricketIQ Multi-Agent System Demo")
print("=" * 60)

# 1. Show database state
print("\n1. Current database state:")
from tools.database import get_database_status
status = get_database_status()
for table, count in status.items():
    print(f"   {table}: {count}")

# 2. Fetch matches and run pipeline
print("\n2. Fetching matches and running agent pipeline...")
print("   Fetch → Validate → Weather → ML → Explain (GPT) → Report (Claude)")
from tools.cricket_api import fetch_current_matches
from tools.database import save_matches, query_database
from agents.graph import run_pipeline
start = time.time()

matches = fetch_current_matches()
if matches:
    save_matches(matches)
    print(f"   Fetched {len(matches)} matches")

db_matches = query_database("""
    SELECT m.id, m.name FROM matches m
    LEFT JOIN predictions p ON m.id = p.match_id
    WHERE p.id IS NULL
    ORDER BY m.date DESC NULLS LAST LIMIT 3
""")
for m in db_matches:
    print(f"   Running pipeline for: {m['name']}")
    run_pipeline(m["id"])

elapsed = time.time() - start
print(f"   Pipeline completed in {elapsed:.1f}s")

# 3. Show results
print("\n3. Updated database state:")
status = get_database_status()
for table, count in status.items():
    print(f"   {table}: {count}")

# 4. Show a prediction
print("\n4. Sample prediction:")
from tools.database import query_database
predictions = query_database("""
    SELECT p.*, m.name FROM predictions p
    JOIN matches m ON p.match_id = m.id
    ORDER BY p.predicted_at DESC LIMIT 1
""")
if predictions:
    p = predictions[0]
    print(f"   Match: {p['name']}")
    print(f"   {p['team_a']}: {float(p['team_a_win_prob'])*100:.0f}%")
    print(f"   {p['team_b']}: {float(p['team_b_win_prob'])*100:.0f}%")
    if p.get('explanation'):
        print(f"   Explanation: {p['explanation'][:200]}...")

# 5. Show costs
print("\n5. Cost summary (last 7 days):")
from tools.cost_tracker import get_cost_summary
costs = get_cost_summary(7)
for agent in costs["agents"]:
    print(f"   {agent['agent']} ({agent['model']}): ${agent['cost']:.4f}")
print(f"   Total: ${costs['total_cost']:.4f}")

print("\n" + "=" * 60)
print("Demo complete! Open http://localhost:3000 for the dashboard.")
print("=" * 60)
PYEOF
```

---

## ✅ Week 6 Milestone Checklist

```bash
echo "=== Week 6 Checklist ==="
echo "1. LangSmith traces visible: https://smith.langchain.com"
echo "2. Cost tracking:"
curl -s http://localhost:8000/agents/costs | python -m json.tool
echo "3. Health endpoint:"
curl -s http://localhost:8000/health | python -m json.tool
echo "4. Checkpointing works:"
python agents/checkpointed_graph.py
echo "5. Demo runs end-to-end:"
python demo.py
```

**Targets:**
- LangSmith shows full agent traces
- You know cost-per-run for each agent
- Pipeline recovers from failures (checkpointing)
- Health endpoint reports system status
- You can explain: tracing, checkpointing, cost optimization, production patterns

---

## What You've Built (Complete System)

```
┌──────────────────────────────────────────────────────────┐
│                    CricketIQ System                       │
├──────────────────────────────────────────────────────────┤
│  AGENTS (LangGraph)                                      │
│  ├── Orchestrator (Gemini Flash) — manages pipeline      │
│  ├── Fetch Agent (Gemini Flash) — fetches cricket data   │
│  ├── Validation Agent (Gemini Flash) — data quality      │
│  ├── Weather Agent (Gemini Flash) — weather impact       │
│  ├── Explainer Agent (GPT-4o-mini) — prediction reasons  │
│  └── Report Agent (Claude Sonnet) — match analysis       │
├──────────────────────────────────────────────────────────┤
│  ML PIPELINE (Plain Code)                                │
│  ├── Feature Engineering (pandas)                        │
│  ├── XGBoost Model (scikit-learn)                        │
│  └── Prediction Generation                               │
├──────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE                                          │
│  ├── PostgreSQL (data + checkpoints)                     │
│  ├── FastAPI (REST API)                                  │
│  ├── Next.js (Frontend dashboard)                        │
│  ├── LangSmith (Agent observability)                     │
│  └── Cost Tracker (Budget monitoring)                    │
└──────────────────────────────────────────────────────────┘
```

## Concepts You Can Now Explain

| Concept | You Built It In |
|---------|----------------|
| Nodes, Edges, State | Week 1 (hello_graph.py) |
| Tool Calling | Week 1 (fetch_agent.py) |
| Structured Output | Week 2 (validation_agent.py) |
| Conditional Edges | Week 2 (pipeline graph) |
| Human-in-the-Loop | Week 2 (validation review) |
| Code-as-Tool | Week 3 (ML model as tool) |
| Multi-Model Routing | Week 4 (Gemini + GPT + Claude) |
| RAG Pattern | Week 4 (report_agent.py) |
| Subgraphs | Week 4 (orchestrator) |
| Streaming | Week 5 (FastAPI) |
| Checkpointing | Week 6 |
| Tracing / Observability | Week 6 (LangSmith) |
| Production Patterns | Week 6 (retries, health, costs) |

You built a production-grade multi-agent system. That's not a toy project — that's what companies are building right now.
