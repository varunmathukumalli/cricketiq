"""
ml_model.py — Tools for reading ML model predictions and feature data.

These are plain Python functions. The Explainer Agent will call them as tools
to gather the information it needs to write an explanation.
"""
import json
import os
import xgboost as xgb
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ─────────────────────────────────────────────────
# Paths — adjust if your project structure differs
# ─────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "model.json")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "metadata.json")


def get_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_prediction(match_id: str) -> dict:
    """Get stored prediction for a match. Returns dict with teams and win probabilities, or empty dict if not found."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT match_id, team_a, team_b, team_a_win_prob, team_b_win_prob,
               model_version, predicted_at
        FROM predictions
        WHERE match_id = %s
        ORDER BY predicted_at DESC
        LIMIT 1
    """, (match_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if not result:
        return {}

    return {
        "match_id": result["match_id"],
        "team_a": result["team_a"],
        "team_b": result["team_b"],
        "team_a_win_prob": float(result["team_a_win_prob"]),
        "team_b_win_prob": float(result["team_b_win_prob"]),
        "model_version": result["model_version"],
        "predicted_at": str(result["predicted_at"]),
    }


def get_feature_values(match_id: str) -> dict:
    """Reconstruct the feature values that were used to make a prediction.

    This queries the same data the predict.py script used, so the Explainer
    can say things like 'India's recent form is 80% (4 wins in last 5)'.

    Returns:
        Dict of feature names to their values for this match.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get the match details
    cur.execute("""
        SELECT m.id, m.name, m.match_type, m.venue, m.date, m.teams,
               mw.temperature, mw.humidity, mw.wind_speed, mw.dew_point,
               p.team_a, p.team_b, p.team_a_win_prob, p.team_b_win_prob
        FROM matches m
        LEFT JOIN match_weather mw ON m.id = mw.match_id
        LEFT JOIN predictions p ON m.id = p.match_id
        WHERE m.id = %s
    """, (match_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {}

    # Build the feature dict (mirrors what predict.py computes)
    team_a = row.get("team_a") or (row["teams"][0] if row.get("teams") else "Unknown")
    team_b = row.get("team_b") or (row["teams"][1] if row.get("teams") and len(row["teams"]) > 1 else "Unknown")

    features = {
        "match_name": row["name"],
        "team_a": team_a,
        "team_b": team_b,
        "match_type": row["match_type"],
        "venue": row["venue"],
        "temperature": float(row["temperature"]) if row.get("temperature") else 25.0,
        "humidity": float(row["humidity"]) if row.get("humidity") else 60.0,
        "wind_speed": float(row["wind_speed"]) if row.get("wind_speed") else 10.0,
        "dew_point": float(row["dew_point"]) if row.get("dew_point") else 15.0,
    }

    # Compute form features from historical data
    # We query recent results for each team
    conn2 = get_connection()
    cur2 = conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    for team_key, team_name in [("team_a", team_a), ("team_b", team_b)]:
        cur2.execute("""
            SELECT status, teams FROM matches
            WHERE teams @> ARRAY[%s]::text[]
            AND date < (SELECT date FROM matches WHERE id = %s)
            AND status NOT ILIKE '%%not started%%'
            ORDER BY date DESC
            LIMIT 10
        """, (team_name, match_id))
        recent = cur2.fetchall()

        wins = 0
        results_list = []
        for m in recent:
            won = team_name.lower() in (m["status"] or "").lower() and "won" in (m["status"] or "").lower()
            if won:
                wins += 1
                results_list.append("W")
            else:
                results_list.append("L")

        form_rate = wins / len(recent) if recent else 0.5
        features[f"{team_key}_form"] = round(form_rate, 3)
        features[f"{team_key}_recent_results"] = "-".join(results_list[:5]) if results_list else "N/A"
        features[f"{team_key}_wins_last_10"] = wins
        features[f"{team_key}_matches_last_10"] = len(recent)

    # Head-to-head
    cur2.execute("""
        SELECT status, teams FROM matches
        WHERE teams @> ARRAY[%s, %s]::text[]
        AND date < (SELECT date FROM matches WHERE id = %s)
        AND status NOT ILIKE '%%not started%%'
        ORDER BY date DESC
        LIMIT 10
    """, (team_a, team_b, match_id))
    h2h = cur2.fetchall()
    h2h_a_wins = sum(
        1 for m in h2h
        if team_a.lower() in (m["status"] or "").lower() and "won" in (m["status"] or "").lower()
    )
    features["head_to_head_a_wins"] = h2h_a_wins
    features["head_to_head_b_wins"] = len(h2h) - h2h_a_wins
    features["head_to_head_total"] = len(h2h)

    cur2.close()
    conn2.close()

    return features


def get_model_feature_importance() -> dict:
    """Load the trained model and return global feature importance scores.

    Returns:
        Dict mapping feature names to importance scores (0 to 1), sorted highest first.
    """
    if not os.path.exists(MODEL_PATH) or not os.path.exists(METADATA_PATH):
        return {"error": "Model files not found. Train the model first (Week 3)."}

    model = xgb.XGBClassifier()
    model.load_model(MODEL_PATH)

    with open(METADATA_PATH) as f:
        metadata = json.load(f)

    feature_columns = metadata.get("feature_columns", [])
    importances = model.feature_importances_

    # Pair names with scores, sort by importance
    importance_dict = {}
    for name, score in sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True):
        importance_dict[name] = round(float(score), 4)

    return importance_dict


def save_explanation(match_id: str, explanation: str) -> str:
    """Save the generated explanation to the predictions table.

    Args:
        match_id: The match to update
        explanation: The human-readable explanation text

    Returns:
        Confirmation string
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE predictions
        SET explanation = %s
        WHERE match_id = %s
        AND predicted_at = (
            SELECT MAX(predicted_at) FROM predictions WHERE match_id = %s
        )
    """, (explanation, match_id, match_id))
    rows_updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    if rows_updated > 0:
        return f"Explanation saved for match {match_id}"
    else:
        return f"No prediction found for match {match_id} — cannot save explanation"


# ─────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Testing ML Model Tools ===\n")

    print("1. Feature importance:")
    importance = get_model_feature_importance()
    if "error" in importance:
        print(f"   {importance['error']}")
    else:
        for feat, score in importance.items():
            bar = "█" * int(score * 40)
            print(f"   {feat:25s} {score:.4f} {bar}")

    print("\n2. Checking for predictions in database:")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT match_id FROM predictions ORDER BY predicted_at DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        mid = row[0]
        print(f"   Testing with match: {mid}")
        pred = get_prediction(mid)
        print(f"   Prediction: {pred.get('team_a')} {pred.get('team_a_win_prob'):.1%} vs "
              f"{pred.get('team_b')} {pred.get('team_b_win_prob'):.1%}")
        features = get_feature_values(mid)
        print(f"   Features: {len(features)} values loaded")
        for k, v in features.items():
            print(f"     {k}: {v}")
    else:
        print("   No predictions yet — run Week 3's predict.py first")
