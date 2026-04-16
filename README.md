# CricketIQ — Multi-Agent Cricket Analytics

> A production-grade multi-agent system built with LangGraph that predicts cricket match outcomes,
> analyzes weather impact, and generates AI-powered match reports.
>
> **This is a learning project** — every step teaches an Agentic AI concept.

---

## What Makes This Different

This isn't a regular cricket app. Every major task is handled by an **AI agent** that reasons about what to do:

| Agent | LLM | What It Does |
|-------|-----|-------------|
| Orchestrator | Gemini 2.0 Flash | Manages the full pipeline — decides what runs, when |
| Data Fetch | Gemini 2.0 Flash | Decides what cricket data to fetch based on DB state |
| Data Validation | Gemini 2.0 Flash | Detects anomalies, flags suspicious data |
| Weather | Gemini 2.0 Flash | Fetches weather + reasons about cricket impact |
| Prediction Explainer | GPT-4o-mini | Explains WHY the ML model predicted what it did |
| Report Generation | Claude Sonnet | Writes polished pre-match analysis reports |

ML training and feature engineering are **plain code** (not agents) — because math doesn't need reasoning.

See [agents.md](./agents.md) for full architecture.

---

## How to Use These Docs

**Two types of files:**

1. **Concept docs** (numbered `01-13`) — explain *why* things work
2. **Step-by-step guides** (in `guides/`) — tell you exactly *what to type*

**Start with the build order, then follow the weekly guides.**

### Build Guides (follow these to build)

| Week | Guide | What You'll Build | LangGraph Concepts |
|------|-------|-------------------|--------------------|
| 0 | [00-build-order.md](./00-build-order.md) | Your roadmap — read FIRST | — |
| 1 | [guides/week1-setup-langgraph.md](./guides/week1-setup-langgraph.md) | Environment, LangGraph basics, fetch agent | Nodes, Edges, State, Tool calling |
| 2 | [guides/week2-validation-weather-agents.md](./guides/week2-validation-weather-agents.md) | Validation + weather agents, mini pipeline | Structured output, Conditional edges, Human-in-the-loop |
| 3 | [guides/week3-ml-pipeline.md](./guides/week3-ml-pipeline.md) | XGBoost model, ML wrapped as agent tools | Code-as-tool pattern |
| 4 | [guides/week4-content-agents.md](./guides/week4-content-agents.md) | Explainer + report agents, orchestrator, full graph | Multi-model routing, RAG, Subgraphs |
| 5 | [guides/week5-api-frontend.md](./guides/week5-api-frontend.md) | FastAPI + Next.js dashboard | Serving agents via API, Streaming |
| 6 | [guides/week6-observability-deploy.md](./guides/week6-observability-deploy.md) | LangSmith, cost tracking, deploy | Checkpointing, Tracing, Production patterns |

### Concept Docs (read for understanding)

| # | File | What You'll Learn |
|---|------|-------------------|
| 1 | [01-project-overview.md](./01-project-overview.md) | What we're building and why |
| 2 | [02-how-the-web-works.md](./02-how-the-web-works.md) | APIs, HTTP, JSON |
| 3 | [03-data-pipeline.md](./03-data-pipeline.md) | How data flows through agents into your database |
| 4 | [04-database-design.md](./04-database-design.md) | PostgreSQL schema design |
| 5 | [05-machine-learning-intro.md](./05-machine-learning-intro.md) | What ML actually is |
| 7 | [07-weather-integration.md](./07-weather-integration.md) | Why weather matters in cricket |
| 8 | [08-ai-report-generation.md](./08-ai-report-generation.md) | Using LLMs for match analysis |
| 13 | [13-glossary.md](./13-glossary.md) | Every term explained |

---

## Architecture

```
                        ┌──────────────────────┐
                        │   ORCHESTRATOR AGENT  │
                        │   (Gemini Flash)      │
                        └──────────┬───────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                 │                  │
                 ▼                 ▼                  ▼
    ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  DATA PIPELINE │  │  ML PIPELINE     │  │  CONTENT         │
    │                │  │  (Plain Code)    │  │                  │
    │  Fetch Agent   │  │  Feature Eng.    │  │  Report Agent    │
    │  Validation    │  │  XGBoost Model   │  │  (Claude)        │
    │  Weather Agent │  │  Predictions     │  │  Explainer Agent │
    │  (Gemini)      │  │                  │  │  (GPT-4o-mini)   │
    └────────────────┘  └──────────────────┘  └──────────────────┘
           │                     │                     │
           └─────────────────────┴─────────────────────┘
                                 │
                         ┌───────┴───────┐
                         │  PostgreSQL   │
                         └───────┬───────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
             ┌─────────────┐          ┌─────────────┐
             │   FastAPI   │◄─────────│   Next.js   │
             │   Backend   │          │   Frontend  │
             └─────────────┘          └─────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Agent Framework | LangGraph | Industry-standard agent orchestration |
| Cheap Reasoning | Gemini 2.0 Flash | $0.075/1M tokens — handles orchestration, validation, weather |
| Explanations | GPT-4o-mini | Good structured output, cheap |
| Quality Writing | Claude Sonnet | Best writing for user-facing reports |
| ML | XGBoost + scikit-learn | Win probability — deterministic, no LLM needed |
| Database | PostgreSQL | Local dev, deploy to Neon/Supabase later |
| API | FastAPI | Serves agent outputs |
| Frontend | Next.js + Tailwind | Dashboard |
| Observability | LangSmith | Agent tracing and debugging |

---

## Folder Structure

```
cricketiq/
├── agents/
│   ├── state.py              ← Shared LangGraph state
│   ├── graph.py              ← Main graph definition
│   ├── orchestrator.py       ← Orchestrator agent
│   ├── fetch_agent.py        ← Data fetch agent
│   ├── validation_agent.py   ← Data validation agent
│   ├── weather_agent.py      ← Weather analysis agent
│   ├── explainer_agent.py    ← Prediction explainer agent
│   └── report_agent.py       ← Report generation agent
├── tools/
│   ├── cricket_api.py        ← CricketData.org API
│   ├── weather_api.py        ← Open-Meteo API
│   ├── database.py           ← PostgreSQL read/write
│   ├── ml_model.py           ← ML model as agent tool
│   └── cost_tracker.py       ← Token/cost tracking
├── ml/
│   ├── features.py           ← Feature engineering
│   ├── train.py              ← Model training
│   └── predict.py            ← Predictions
├── src/
│   ├── models.py             ← Shared Pydantic models (validation, etc.)
│   ├── api.py                ← FastAPI app
│   └── schema.sql            ← Database schema
├── frontend/                  ← Next.js dashboard
├── guides/                    ← Step-by-step command guides
├── agents.md                  ← Agent architecture doc
├── 00-build-order.md          ← Build roadmap
└── .env                       ← API keys (never commit!)
```

---

## Estimated Costs

| Agent | Model | Est. Cost/Month |
|-------|-------|----------------|
| Orchestrator + Fetch + Validation + Weather | Gemini Flash | ~$0.50 |
| Prediction Explainer | GPT-4o-mini | ~$1.00 |
| Report Generation | Claude Sonnet | ~$3.00 |
| **Total** | | **~$5-10/month** |

---

## Quick Start

```bash
# 1. Set up environment
python3 -m venv venv && source venv/bin/activate
pip install langgraph langchain langchain-anthropic langchain-google-genai langchain-openai

# 2. Set up database
createdb cricketiq && psql cricketiq -f src/schema.sql

# 3. Configure API keys
cp .env.example .env  # Fill in your keys

# 4. Run your first agent
python agents/fetch_agent.py

# 5. Follow the weekly guides in guides/
```

---

> Built as a learning project for Agentic AI concepts using LangGraph.
> Every agent teaches a real concept that companies are actively hiring for.
