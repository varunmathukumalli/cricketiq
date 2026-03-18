"""
ml/features.py — Feature Engineering for CricketIQ

PURPOSE: Extracts numerical features from match, player, and weather data
         to feed into the XGBoost model. This is the most important file
         for model accuracy — better features beat better algorithms.

INPUTS:  matches, match_weather tables (via PostgreSQL)
OUTPUTS: A pandas DataFrame with one row per match and columns for each feature

FEATURES COMPUTED:
  - team_a_form:        Team A win rate in last 10 matches
  - team_b_form:        Team B win rate in last 10 matches
  - head_to_head:       Team A win rate vs Team B in last 10 encounters
  - venue_form:         Team A win rate at this venue (last 5 matches)
  - temperature:        Temperature at match time (Celsius)
  - humidity:           Humidity percentage
  - wind_speed:         Wind speed (km/h)
  - dew_point:          Dew point temperature (Celsius)
  - form_diff:          team_a_form minus team_b_form (derived)
  - is_t20:             1 if T20, 0 otherwise
  - is_odi:             1 if ODI, 0 otherwise
"""
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


# ─────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────

def load_matches_dataframe() -> pd.DataFrame:
    """Load all completed matches with weather data into a pandas DataFrame.

    Joins matches with match_weather so we have everything in one table.
    Only includes matches that have a date (needed for time-based splitting).

    Returns:
        DataFrame with columns: id, name, match_type, status, venue, date,
        teams, temperature, humidity, wind_speed, dew_point, precipitation
    """
    conn = psycopg2.connect(DATABASE_URL)

    query = """
        SELECT
            m.id,
            m.name,
            m.match_type,
            m.status,
            m.venue,
            m.date,
            m.teams,
            mw.temperature,
            mw.humidity,
            mw.wind_speed,
            mw.dew_point,
            mw.precipitation
        FROM matches m
        LEFT JOIN match_weather mw ON m.id = mw.match_id
        WHERE m.status NOT ILIKE '%%not started%%'
        AND m.date IS NOT NULL
        ORDER BY m.date
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(f"Loaded {len(df)} completed matches from database")
    return df


# ─────────────────────────────────────────────────
# HELPER: EXTRACT WINNER FROM STATUS STRING
# ─────────────────────────────────────────────────

def extract_winner(status: str, teams: list) -> str | None:
    """Parse the status string to determine which team won.

    The CricketData API returns status like:
      "India won by 7 wickets"
      "Australia won by 23 runs"

    We match each team name against the status to find the winner.

    Args:
        status: The match status string from the API
        teams:  List of team names, e.g. ["India", "Australia"]

    Returns:
        The winning team name, or None for draws/no result/abandoned
    """
    if not status or not teams:
        return None

    status_lower = status.lower()

    for team in teams:
        if team.lower() in status_lower and "won" in status_lower:
            return team

    return None  # Draw, tie, no result, or abandoned


# ─────────────────────────────────────────────────
# FEATURE FUNCTIONS
# Each computes ONE feature for ONE match.
# ─────────────────────────────────────────────────

def compute_team_form(df: pd.DataFrame, team: str, current_date, window: int = 10) -> float:
    """Calculate a team's win rate in their last N matches before current_date.

    This is the single most important feature. A team that has been winning
    recently is more likely to win again.

    Args:
        df:           Full matches DataFrame (must have 'winner' column)
        team:         Team name to compute form for
        current_date: Only look at matches BEFORE this date (prevents data leakage)
        window:       How many recent matches to consider (default 10)

    Returns:
        Win rate between 0.0 and 1.0. Returns 0.5 if no history (assume 50/50).
    """
    past = df[
        (df["date"] < current_date) &
        (df["teams"].apply(lambda t: team in t if t else False))
    ].tail(window)

    if len(past) == 0:
        return 0.5  # No history — assume coin flip

    wins = sum(past["winner"] == team)
    return wins / len(past)


def compute_head_to_head(df: pd.DataFrame, team_a: str, team_b: str,
                         current_date, window: int = 10) -> float:
    """Win rate of team_a against team_b in their last N encounters.

    Head-to-head record captures matchup-specific dynamics that general
    form does not. Some teams consistently beat others regardless of form.

    Args:
        df:           Full matches DataFrame (must have 'winner' column)
        team_a:       First team (we compute THEIR win rate)
        team_b:       Second team
        current_date: Only look at matches BEFORE this date
        window:       How many recent encounters to consider

    Returns:
        team_a's win rate against team_b (0.0 to 1.0). Returns 0.5 if no history.
    """
    past = df[
        (df["date"] < current_date) &
        (df["teams"].apply(lambda t: team_a in t and team_b in t if t else False))
    ].tail(window)

    if len(past) == 0:
        return 0.5

    wins = sum(past["winner"] == team_a)
    return wins / len(past)


def compute_venue_form(df: pd.DataFrame, team: str, venue: str,
                       current_date, window: int = 5) -> float:
    """Win rate of a team at a specific venue.

    Some teams perform dramatically better at certain grounds (home advantage,
    pitch familiarity, altitude, crowd support).

    Args:
        df:           Full matches DataFrame (must have 'winner' column)
        team:         Team name
        venue:        Venue name to filter by
        current_date: Only look at matches BEFORE this date
        window:       How many recent venue matches to consider (default 5)

    Returns:
        Win rate at venue (0.0 to 1.0). Returns 0.5 if no venue history.
    """
    past = df[
        (df["date"] < current_date) &
        (df["venue"] == venue) &
        (df["teams"].apply(lambda t: team in t if t else False))
    ].tail(window)

    if len(past) == 0:
        return 0.5

    wins = sum(past["winner"] == team)
    return wins / len(past)


# ─────────────────────────────────────────────────
# BUILD THE FULL FEATURE MATRIX
# ─────────────────────────────────────────────────

def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Build the full feature matrix — one row per match, one column per feature.

    This is the main function that ties everything together. For each match:
    1. Determine the winner (target variable)
    2. Compute all features using ONLY data from BEFORE that match
    3. Assemble into a single row

    The "only data from before" part is critical — it prevents DATA LEAKAGE.
    If you accidentally use future data to predict the past, your accuracy
    will look amazing but the model will be useless in production.

    Args:
        df: Raw matches DataFrame from load_matches_dataframe()

    Returns:
        DataFrame with feature columns + 'team_a_won' target column.
        One row per match where we can determine a winner.
    """
    # Step 1: Compute the winner for each match
    df = df.copy()
    df["winner"] = df.apply(
        lambda row: extract_winner(row["status"], row["teams"]), axis=1
    )

    # Drop matches where we cannot determine a winner (draws, no result, abandoned)
    df_valid = df[df["winner"].notna()].copy()
    print(f"Matches with clear winner: {len(df_valid)} out of {len(df)}")

    if len(df_valid) == 0:
        print("ERROR: No matches with a clear winner found.")
        print("Make sure you have completed matches in the database.")
        return pd.DataFrame()

    # Step 2: Compute features for each match
    features_list = []

    for idx, row in df_valid.iterrows():
        teams = row["teams"]
        if not teams or len(teams) < 2:
            continue

        team_a, team_b = teams[0], teams[1]

        # Compute each feature
        team_a_form = compute_team_form(df, team_a, row["date"])
        team_b_form = compute_team_form(df, team_b, row["date"])

        feature_row = {
            # Identifiers (NOT features — excluded during training)
            "match_id": row["id"],
            "date": row["date"],
            "team_a": team_a,
            "team_b": team_b,

            # TARGET VARIABLE: did team_a win? (1 = yes, 0 = no)
            "team_a_won": 1 if row["winner"] == team_a else 0,

            # ── Team form features ──
            "team_a_form": team_a_form,
            "team_b_form": team_b_form,

            # ── Head-to-head ──
            "head_to_head": compute_head_to_head(df, team_a, team_b, row["date"]),

            # ── Venue form ──
            "venue_form": compute_venue_form(df, team_a, row["venue"], row["date"]),

            # ── Weather features (fill missing with reasonable defaults) ──
            "temperature": float(row["temperature"]) if pd.notna(row["temperature"]) else 25.0,
            "humidity": float(row["humidity"]) if pd.notna(row["humidity"]) else 60.0,
            "wind_speed": float(row["wind_speed"]) if pd.notna(row["wind_speed"]) else 10.0,
            "dew_point": float(row["dew_point"]) if pd.notna(row["dew_point"]) else 15.0,

            # ── Derived features ──
            "form_diff": team_a_form - team_b_form,
            "is_t20": 1 if row["match_type"] == "t20" else 0,
            "is_odi": 1 if row["match_type"] == "odi" else 0,
        }

        features_list.append(feature_row)

    features_df = pd.DataFrame(features_list)
    print(f"Feature matrix: {features_df.shape[0]} rows x {features_df.shape[1]} columns")
    return features_df


# ─────────────────────────────────────────────────
# FEATURE COLUMN LIST
# Used by train.py and predict.py to know which columns are features
# ─────────────────────────────────────────────────

FEATURE_COLUMNS = [
    "team_a_form",
    "team_b_form",
    "head_to_head",
    "venue_form",
    "temperature",
    "humidity",
    "wind_speed",
    "dew_point",
    "form_diff",
    "is_t20",
    "is_odi",
]


# ─────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Feature Engineering — CricketIQ")
    print("=" * 60)

    # Load data from database
    df = load_matches_dataframe()

    if len(df) == 0:
        print("\nNo matches in database. Run the fetch agent first (Week 1).")
        exit(1)

    # Build features
    features = build_feature_matrix(df)

    if len(features) == 0:
        print("\nNo features could be built. Check your match data.")
        exit(1)

    # Show what we built
    print("\n--- Feature Matrix Preview (first 5 rows) ---")
    print(features[FEATURE_COLUMNS + ["team_a_won"]].head().to_string())

    print("\n--- Feature Statistics ---")
    print(features[FEATURE_COLUMNS].describe().round(3).to_string())

    print("\n--- Target Distribution ---")
    counts = features["team_a_won"].value_counts()
    print(f"  Team A won: {counts.get(1, 0)} matches")
    print(f"  Team B won: {counts.get(0, 0)} matches")

    # Save to CSV for manual inspection
    features.to_csv("ml/features_output.csv", index=False)
    print("\nSaved to ml/features_output.csv — open in a spreadsheet to inspect!")