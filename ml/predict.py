"""
ml/predict.py — Generate Win Probability Predictions

PURPOSE: Uses the trained XGBoost model to predict outcomes for upcoming matches.
         Computes features for each upcoming match, runs the model, and saves
         predictions to the database.

INPUTS:  - models/model.json (trained model)
         - models/metadata.json (feature list)
         - Upcoming matches from database
         - Historical match data (for computing form features)

OUTPUTS: Rows in the predictions table
"""
import xgboost as xgb
import pandas as pd
import psycopg2
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Import feature computation functions
from ml.features import (
    load_matches_dataframe,
    extract_winner,
    compute_team_form,
    compute_head_to_head,
    compute_venue_form,
    FEATURE_COLUMNS,
)


def load_model() -> tuple:
    """Load the trained model and its metadata.

  Returns:
        Tuple of (XGBClassifier, metadata_dict)

    Raises:
        FileNotFoundError: If model files do not exist (run train.py first)
    """
    project_root = os.path.join(os.path.dirname(__file__), "..")
    model_path = os.path.join(project_root, "models", "model.json")
    metadata_path = os.path.join(project_root, "models", "metadata.json")

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model not found at {model_path}. Run 'python ml/train.py' first."
        )

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    with open(metadata_path) as f:
        metadata = json.load(f)

    print(f"Loaded model {metadata.get('model_version', 'unknown')}")
    print(f"  Trained at: {metadata.get('trained_at', 'unknown')}")
    print(f"  Accuracy:   {metadata.get('accuracy', 0):.1%}")

    return model, metadata


def get_upcoming_matches() -> list[dict]:
    """Get upcoming/in-progress major matches from the database.

    Filters out domestic and minor matches using the same logic as cricket_api.py.

    Returns:
        List of dicts with keys: id, name, match_type, venue, date, teams
    """
    from tools.cricket_api import is_major_match

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, match_type, venue, date, teams
        FROM matches
        WHERE status ILIKE '%%not started%%'
           OR status ILIKE '%%upcoming%%'
           OR status ILIKE '%%opt to b%%'
           OR status ILIKE '%%opt to bat%%'
        ORDER BY date
    """)

    columns = ["id", "name", "match_type", "venue", "date", "teams"]
    all_matches = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    # Filter to major matches only
    matches = [m for m in all_matches if is_major_match(m)]
    if len(matches) < len(all_matches):
        print(f"  Filtered: {len(all_matches)} total → {len(matches)} major matches")

    return matches


def predict_match(model: xgb.XGBClassifier, metadata: dict,
                  historical_df: pd.DataFrame, match: dict) -> dict | None:
    """Generate a win probability prediction for a single upcoming match.

    Computes features using historical data (same features as training),
    then runs the model to get P(team_a wins).

    Args:
        model:         Trained XGBClassifier
        metadata:      Model metadata (contains feature_columns)
        historical_df: All past matches with 'winner' column computed
        match:         Dict with upcoming match info

    Returns:
        Dict with match_id, team_a, team_b, team_a_prob, team_b_prob
        or None if the match cannot be predicted (e.g., missing teams)
    """
    teams = match.get("teams")
    if not teams or len(teams) < 2:
        return None

    team_a, team_b = teams[0], teams[1]
    match_date = match.get("date", datetime.now())

    # Compute features for this match using ONLY historical data
    team_a_form = compute_team_form(historical_df, team_a, match_date)
    team_b_form = compute_team_form(historical_df, team_b, match_date)

    features = {
        "team_a_form": team_a_form,
        "team_b_form": team_b_form,
        "head_to_head": compute_head_to_head(historical_df, team_a, team_b, match_date),
        "venue_form": compute_venue_form(historical_df, team_a, match.get("venue", ""), match_date),
        "temperature": 25.0,    # Default — will be improved with weather forecast API
        "humidity": 60.0,
        "wind_speed": 10.0,
        "dew_point": 15.0,
        "form_diff": team_a_form - team_b_form,
      "is_t20": 1 if match.get("match_type") == "t20" else 0,
        "is_odi": 1 if match.get("match_type") == "odi" else 0,
    }

    # Create a DataFrame with the same columns the model was trained on
    feature_cols = metadata.get("feature_columns", FEATURE_COLUMNS)
    X = pd.DataFrame([features])[feature_cols]

    # Get probabilities: [P(team_b wins), P(team_a wins)]
    proba = model.predict_proba(X)[0]

    return {
        "match_id": match["id"],
        "team_a": team_a,
        "team_b": team_b,
        "team_a_prob": round(float(proba[1]), 4),
        "team_b_prob": round(float(proba[0]), 4),
    }


def save_predictions(predictions: list[dict], model_version: str = "v1"):
    """Save predictions to the predictions table in PostgreSQL.

    Uses INSERT ... ON CONFLICT to update existing predictions
    for the same match and model version.

    Args:
        predictions:   List of prediction dicts from predict_match()
        model_version: Version tag for this model (e.g., "v1")
    """
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    for pred in predictions:
        cur.execute("""
            INSERT INTO predictions
                (match_id, team_a, team_b, team_a_win_prob, team_b_win_prob, model_version)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (match_id, model_version) DO UPDATE SET
                team_a_win_prob = EXCLUDED.team_a_win_prob,
                team_b_win_prob = EXCLUDED.team_b_win_prob,
                predicted_at = NOW()
        """, (
            pred["match_id"], pred["team_a"], pred["team_b"],
            pred["team_a_prob"], pred["team_b_prob"], model_version,
        ))

    conn.commit()
    cur.close()
    conn.close()
    print(f"Saved {len(predictions)} predictions to database (version: {model_version})")


# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("CricketIQ — Win Probability Predictions")
    print("=" * 60)

    # Load model
    print("\n[1/4] Loading trained model...")
    model, metadata = load_model()

    # Load historical data for feature computation
    print("\n[2/4] Loading historical match data...")
    historical_df = load_matches_dataframe()
    historical_df = historical_df.copy()
    historical_df["winner"] = historical_df.apply(
        lambda row: extract_winner(row["status"], row["teams"]), axis=1
    )

    # Get upcoming matches
    print("\n[3/4] Finding upcoming matches...")
    upcoming = get_upcoming_matches()
    print(f"Found {len(upcoming)} upcoming matches")

    if len(upcoming) == 0:
        print("\nNo upcoming matches found in the database.")
        print("Run the fetch agent to get new match data.")
        exit(0)

    # Generate predictions
    print("\n[4/4] Generating predictions...\n")
    predictions = []
    for match in upcoming:
        pred = predict_match(model, metadata, historical_df, match)
        if pred:
            predictions.append(pred)
            # Pretty print
            fav = pred["team_a"] if pred["team_a_prob"] > pred["team_b_prob"] else pred["team_b"]
            fav_prob = max(pred["team_a_prob"], pred["team_b_prob"])
            print(f"  {pred['team_a']} vs {pred['team_b']}")
            print(f"    {pred['team_a']:>20s}: {pred['team_a_prob']:.1%}")
            print(f"    {pred['team_b']:>20s}: {pred['team_b_prob']:.1%}")
            print(f"    Favorite: {fav} ({fav_prob:.1%})")
            print()

    # Save to database
    if predictions:
        save_predictions(predictions, metadata.get("model_version", "v1"))
    else:
        print("No predictions could be generated.")

    print("Done!")
