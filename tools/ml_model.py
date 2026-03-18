"""
tools/ml_model.py — ML Model as LangChain Tools

PURPOSE: Wraps the trained XGBoost model as @tool functions that
         LangGraph agents can call. This is the "code-as-tool" pattern.

WHY TOOLS, NOT AGENTS?
  The model is deterministic — given the same input, it produces the same output.
  There is no "reasoning" needed. An agent calling the model just needs the
  match_id and the tool does the rest.

  The agent's job is to DECIDE when to call this tool, and to EXPLAIN
  the results to the user in natural language. The math stays in code.

TOOLS PROVIDED:
  - get_prediction(match_id):    Get win probability for a specific match
  - get_feature_importance():    Get which features the model relies on most
  - get_model_accuracy():        Get the model's accuracy and metadata
"""
import xgboost as xgb
import pandas as pd
import psycopg2
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


# ─────────────────────────────────────────────────
# INTERNAL HELPERS (not exposed as tools)
# ─────────────────────────────────────────────────

def _load_model():
    """Load the trained model and metadata. Returns (model, metadata) or raises."""
    model_path = "models/model.json"
    metadata_path = "models/metadata.json"

    if not os.path.exists(model_path) or not os.path.exists(metadata_path):
        raise FileNotFoundError("Model not found. Run 'python ml/train.py' first.")

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    with open(metadata_path) as f:
        metadata = json.load(f)

    return model, metadata


def _get_match_info(match_id: str) -> dict | None:
    """Get match info from the database."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, match_type, venue, date, teams, status FROM matches WHERE id = %s",
        (match_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0], "name": row[1], "match_type": row[2],
        "venue": row[3], "date": row[4], "teams": row[5], "status": row[6],
    }


def _get_existing_prediction(match_id: str) -> dict | None:
    """Check if we already have a prediction for this match."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """SELECT team_a, team_b, team_a_win_prob, team_b_win_prob,
                  model_version, predicted_at
           FROM predictions WHERE match_id = %s
           ORDER BY predicted_at DESC LIMIT 1""",
        (match_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "team_a": row[0], "team_b": row[1],
        "team_a_win_prob": float(row[2]), "team_b_win_prob": float(row[3]),
        "model_version": row[4], "predicted_at": str(row[5]),
    }


# ─────────────────────────────────────────────────
# TOOL 1: GET PREDICTION
# ─────────────────────────────────────────────────

@tool
def get_prediction(match_id: str) -> str:
    """Get the win probability prediction for a specific cricket match.

    Returns the predicted win probabilities for both teams, along with
    which team is favored and the model version used.

    Args:
        match_id: The match ID from the database (e.g., "abc123")

    Returns:
        A formatted string with the prediction details, or an error message.
    """
    try:
        # First, check if we already have a prediction saved
        existing = _get_existing_prediction(match_id)
        if existing:
            match_info = _get_match_info(match_id)
            match_name = match_info.get("name", "") if match_info else ""
            fav = existing["team_a"] if existing["team_a_win_prob"] > existing["team_b_win_prob"] else existing["team_b"]
            fav_prob = max(existing["team_a_win_prob"], existing["team_b_win_prob"])
            return (
                f"Prediction for {existing['team_a']} vs {existing['team_b']}:\n"
                f"  Match: {match_name}\n"
                f"  {existing['team_a']}: {existing['team_a_win_prob']:.1%} win probability\n"
                f"  {existing['team_b']}: {existing['team_b_win_prob']:.1%} win probability\n"
                f"  Favorite: {fav} ({fav_prob:.1%})\n"
                f"  Model version: {existing['model_version']}\n"
                f"  Predicted at: {existing['predicted_at']}"
            )

        # No existing prediction — try to generate one live
        match_info = _get_match_info(match_id)
        if not match_info:
            return f"Match '{match_id}' not found in the database."

        # Don't predict completed matches
        status = match_info.get("status", "")
        completed_keywords = ["won by", "match drawn", "no result", "tied", "abandoned"]
        if any(kw in status.lower() for kw in completed_keywords):
            match_name = match_info.get("name", "")
            return (
                f"Match already completed — no prediction needed.\n"
                f"  Match: {match_name}\n"
                f"  Result: {status}"
            )

        teams = match_info.get("teams")
        if not teams or len(teams) < 2:
            return f"Match '{match_id}' does not have two teams listed."

        # Import and run the prediction pipeline
        from ml.features import (
            load_matches_dataframe, extract_winner,
            compute_team_form, compute_head_to_head, compute_venue_form,
            FEATURE_COLUMNS,
        )

        model, metadata = _load_model()
        historical_df = load_matches_dataframe()
        historical_df = historical_df.copy()
        historical_df["winner"] = historical_df.apply(
            lambda row: extract_winner(row["status"], row["teams"]), axis=1
        )

        team_a, team_b = teams[0], teams[1]
        match_date = match_info.get("date", datetime.now())

        team_a_form = compute_team_form(historical_df, team_a, match_date)
        team_b_form = compute_team_form(historical_df, team_b, match_date)

        features = {
            "team_a_form": team_a_form,
            "team_b_form": team_b_form,
            "head_to_head": compute_head_to_head(historical_df, team_a, team_b, match_date),
            "venue_form": compute_venue_form(historical_df, team_a, match_info.get("venue", ""), match_date),
            "temperature": 25.0,
            "humidity": 60.0,
            "wind_speed": 10.0,
            "dew_point": 15.0,
            "form_diff": team_a_form - team_b_form,
            "is_t20": 1 if match_info.get("match_type") == "t20" else 0,
            "is_odi": 1 if match_info.get("match_type") == "odi" else 0,
        }

        feature_cols = metadata.get("feature_columns", FEATURE_COLUMNS)
        X = pd.DataFrame([features])[feature_cols]
        proba = model.predict_proba(X)[0]

        team_a_prob = float(proba[1])
        team_b_prob = float(proba[0])
        fav = team_a if team_a_prob > team_b_prob else team_b
        fav_prob = max(team_a_prob, team_b_prob)

        match_name = match_info.get("name", "")
        return (
            f"Prediction for {team_a} vs {team_b}:\n"
            f"  Match: {match_name}\n"
            f"  {team_a}: {team_a_prob:.1%} win probability\n"
            f"  {team_b}: {team_b_prob:.1%} win probability\n"
            f"  Favorite: {fav} ({fav_prob:.1%})\n"
            f"  Model version: {metadata.get('model_version', 'unknown')}\n"
            f"  Generated: live (not cached)"
        )

    except FileNotFoundError as e:
        return f"Model not available: {e}"
    except Exception as e:
        return f"Error generating prediction: {e}"


# ─────────────────────────────────────────────────
# TOOL 2: GET FEATURE IMPORTANCE
# ─────────────────────────────────────────────────

@tool
def get_feature_importance() -> str:
    """Get the feature importance ranking from the trained ML model.

    Shows which features (team form, weather, etc.) have the most
    influence on the model's predictions. Useful for understanding
    WHY the model makes certain predictions.

    Returns:
        A formatted string listing features from most to least important.
    """
    try:
        model, metadata = _load_model()
        feature_cols = metadata.get("feature_columns", [])

        if not feature_cols:
            return "No feature columns found in model metadata."

        importance = dict(zip(feature_cols, model.feature_importances_))
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        lines = ["Feature Importance (most to least):"]
        for i, (name, value) in enumerate(sorted_features, 1):
            bar = "#" * int(value * 40)
            lines.append(f"  {i}. {name:25s} {value:.3f}  {bar}")

        lines.append(f"\nModel version: {metadata.get('model_version', 'unknown')}")
        lines.append(f"Model accuracy: {metadata.get('accuracy', 0):.1%}")

        return "\n".join(lines)

    except FileNotFoundError as e:
        return f"Model not available: {e}"
    except Exception as e:
        return f"Error loading feature importance: {e}"


# ─────────────────────────────────────────────────
# TOOL 3: GET MODEL ACCURACY
# ─────────────────────────────────────────────────

@tool
def get_model_accuracy() -> str:
    """Get the accuracy and metadata for the trained ML model.

    Returns accuracy, log loss, training date, hyperparameters,
    and the list of features used. Useful for agents that need
    to communicate model reliability to users.

    Returns:
        A formatted string with model performance metrics and metadata.
    """
    try:
        _, metadata = _load_model()

        lines = [
            "CricketIQ ML Model Status:",
            f"  Version:       {metadata.get('model_version', 'unknown')}",
            f"  Trained at:    {metadata.get('trained_at', 'unknown')}",
            f"  Accuracy:      {metadata.get('accuracy', 0):.1%}",
            f"  Log Loss:      {metadata.get('log_loss', 0):.4f}",
            f"  Features used: {len(metadata.get('feature_columns', []))}",
            "",
            "Hyperparameters:",
        ]

        hyperparams = metadata.get("hyperparameters", {})
        for key, value in hyperparams.items():
            lines.append(f"  {key}: {value}")

        lines.append("")
        lines.append(f"Features: {', '.join(metadata.get('feature_columns', []))}")

        notes = metadata.get("notes", "")
        if notes:
            lines.append(f"\nNotes: {notes}")

        return "\n".join(lines)

    except FileNotFoundError as e:
        return f"Model not available: {e}"
    except Exception as e:
        return f"Error loading model metadata: {e}"


# ─────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Testing ML Model Tools")
    print("=" * 60)

    # Test get_model_accuracy
    print("\n--- Tool: get_model_accuracy ---")
    print(get_model_accuracy.invoke({}))

    # Test get_feature_importance
    print("\n--- Tool: get_feature_importance ---")
    print(get_feature_importance.invoke({}))

    # Test get_prediction with the first match in the database
    print("\n--- Tool: get_prediction ---")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT id FROM matches LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        print(get_prediction.invoke({"match_id": row[0]}))
    else:
        print("No matches in database to test with.")