"""
explainer_agent.py — Prediction Explainer Agent

ROLE: Takes the ML model's raw probability output and generates a human-readable
      explanation of WHY the model predicted what it did.

LLM: GPT-4o-mini (OpenAI)
     Why GPT-4o-mini? It's excellent at structured, analytical explanations and
     very cheap. This agent runs once per prediction, so cost matters.

PATTERN: Tool-calling agent with structured output.
         The agent gathers data via tools, then writes the explanation.

LANGGRAPH CONCEPTS TAUGHT:
  - Multi-model routing (this agent uses a DIFFERENT LLM than the others)
  - Prompt templates (injecting data into a carefully designed prompt)
  - Structured output (the explanation has defined sections)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

load_dotenv()

# Import our plain-code tools
from tools.ml_model import (
    get_prediction as _get_prediction,
    get_feature_values as _get_feature_values,
    get_model_feature_importance as _get_model_feature_importance,
    save_explanation as _save_explanation,
)


# ─────────────────────────────────────────────────
# Wrap plain functions as LangChain tools
# ─────────────────────────────────────────────────
# The @tool decorator tells LangGraph these are callable.
# The docstrings are critical — the LLM reads them to decide
# which tool to use and what arguments to pass.

@tool
def tool_get_prediction(match_id: str) -> str:
    """Get the ML model's win probability prediction for a match.
    Returns team names and their predicted win percentages.
    Call this first to see what the model predicted."""
    pred = _get_prediction(match_id)
    if not pred:
        return f"No prediction found for match {match_id}"
    return (
        f"Prediction for {pred['team_a']} vs {pred['team_b']}:\n"
        f"  {pred['team_a']}: {pred['team_a_win_prob']:.1%} win probability\n"
        f"  {pred['team_b']}: {pred['team_b_win_prob']:.1%} win probability\n"
        f"  Model version: {pred['model_version']}\n"
        f"  Predicted at: {pred['predicted_at']}"
    )


@tool
def tool_get_feature_values(match_id: str) -> str:
    """Get the actual feature values the model used for this prediction.
    Shows team form, head-to-head record, weather conditions, etc.
    Call this after getting the prediction to understand what drove it."""
    features = _get_feature_values(match_id)
    if not features:
        return f"No feature data found for match {match_id}"

    lines = ["Feature values used for prediction:"]
    for key, value in features.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


@tool
def tool_get_model_feature_importance() -> str:
    """Get the global feature importance scores from the trained model.
    Shows which features the model considers most important overall.
    Use this to explain which factors carry the most weight."""
    importance = _get_model_feature_importance()
    if "error" in importance:
        return importance["error"]

    lines = ["Model feature importance (most to least important):"]
    for feat, score in importance.items():
        pct = score * 100
        lines.append(f"  {feat}: {pct:.1f}%")
    return "\n".join(lines)


@tool
def tool_save_explanation(match_id: str, explanation: str) -> str:
    """Save the generated explanation to the database.
    Call this LAST, after you have written the full explanation.
    The explanation should be clear, structured, and cite specific numbers."""
    return _save_explanation(match_id, explanation)


# ─────────────────────────────────────────────────
# Agent system prompt
# ─────────────────────────────────────────────────
EXPLAINER_SYSTEM_PROMPT = """You are the CricketIQ Prediction Explainer Agent. Your job is to take
a machine learning model's win probability prediction and explain WHY the model
predicted what it did, in clear language that a cricket fan can understand.

STEPS (follow this exact order):
1. Call tool_get_prediction to get the raw prediction (win probabilities)
2. Call tool_get_feature_values to see the actual data the model used
3. Call tool_get_model_feature_importance to see which features matter most
4. Write a structured explanation (format below)
5. Call tool_save_explanation to save your explanation to the database

EXPLANATION FORMAT (follow this structure):
---
**Prediction:** [Team A] [X]% vs [Team B] [Y]%

**Key factors driving this prediction:**

1. **Recent Form:** [Which team has better form and by how much. Cite the
   actual W-L record, e.g., "India: W-W-W-L-W (4/5 wins)"]

2. **Head-to-Head:** [How the teams have performed against each other recently.
   Cite the actual record, e.g., "India leads 3-2 in the last 5 meetings"]

3. **Venue Factor:** [Any venue-specific advantage. Cite the stat.]

4. **Conditions:** [How weather/pitch conditions favor one team. Cite temperature,
   humidity, dew point if relevant.]

**Model confidence note:** [Is the prediction close to 50-50 (low confidence) or
strongly favoring one team (high confidence)? What would change the prediction?]
---

RULES:
- Always cite SPECIFIC numbers from the feature values — never make up stats
- If a feature value is missing or default (0.5), say "insufficient data" rather than guessing
- Keep the explanation under 300 words
- Use plain language — explain what "form 0.8" means ("won 4 of last 5 matches")
- If the prediction is close to 50-50, say so honestly
"""


# ─────────────────────────────────────────────────
# Create the agent
# ─────────────────────────────────────────────────
def create_explainer_agent():
    """Create the Prediction Explainer agent with GPT-4o-mini."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

    tools = [
        tool_get_prediction,
        tool_get_feature_values,
        tool_get_model_feature_importance,
        tool_save_explanation,
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=EXPLAINER_SYSTEM_PROMPT,
    )
    return agent


def run_explainer(match_id: str) -> dict:
    """Run the Explainer Agent for a specific match.

    This is the function other agents (like the Orchestrator) will call.

    Args:
        match_id: The match to explain

    Returns:
        Dict with the agent's messages and the explanation
    """
    agent = create_explainer_agent()
    result = agent.invoke(
        {"messages": [
            ("user", f"Explain the prediction for match ID: {match_id}")
        ]},
        config={"recursion_limit": 25},
    )
    return result


# ─────────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    import psycopg2
    import os

    print("=" * 60)
    print("Prediction Explainer Agent (GPT-4o-mini)")
    print("=" * 60)

    # Find a match that has a prediction
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT match_id, team_a, team_b, team_a_win_prob
        FROM predictions
        ORDER BY predicted_at DESC
        LIMIT 5
    """)
    predictions = cur.fetchall()
    cur.close()
    conn.close()

    if not predictions:
        print("\nNo predictions in database. Run Week 3's predict.py first:")
        print("  cd src && python predict.py && cd ..")
        exit(1)

    print(f"\nFound {len(predictions)} predictions. Using the most recent one.\n")
    match_id = predictions[0][0]
    team_a, team_b = predictions[0][1], predictions[0][2]
    prob = predictions[0][3]
    print(f"Match: {team_a} vs {team_b} ({float(prob):.1%} / {1-float(prob):.1%})")
    print(f"Match ID: {match_id}\n")

    print("Running agent...\n")
    result = run_explainer(match_id)

    # Print the agent's reasoning chain
    print("\n" + "=" * 60)
    print("AGENT REASONING TRACE")
    print("=" * 60)
    for msg in result["messages"]:
        role = msg.__class__.__name__
        if hasattr(msg, "content") and msg.content:
            print(f"\n[{role}]")
            print(msg.content)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  -> Called: {tc['name']}({tc.get('args', {})})")