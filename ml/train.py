"""
ml/train.py — Train the XGBoost Win Probability Model

PURPOSE: Trains an XGBoost classifier to predict cricket match winners.
         Uses a DATE-BASED train/test split to simulate real-world predictions.

INPUTS:  Feature matrix from ml/features.py
OUTPUTS: - models/model.json       (the trained model)
         - models/metadata.json    (accuracy, feature list, hyperparameters)
         - models/calibration_curve.png
         - models/feature_importance.png
         - models/prediction_distribution.png

WHY DATE-BASED SPLIT?
  Random splitting would let the model "see the future" — matches from 2025
  could end up in training, and 2024 matches in testing. That is data leakage.
  In production, you always predict future matches from past data.
  The date-based split simulates this exactly.
"""
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, log_loss, classification_report
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend (no GUI needed)
import matplotlib.pyplot as plt
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import from our features module
from ml.features import (
    load_matches_dataframe,
    build_feature_matrix,
    FEATURE_COLUMNS,
)


# ─────────────────────────────────────────────────
# STEP 1: PREPARE DATA
# ─────────────────────────────────────────────────

def prepare_data(features_df: pd.DataFrame) -> tuple:
    """Split features into train and test sets BY DATE.

    The first 80% of matches (chronologically) go to training.
    The last 20% go to testing. This simulates real-world usage
    where you train on the past and predict the future.

    Args:
        features_df: Output of build_feature_matrix()

    Returns:
        Tuple of (X_train, X_test, y_train, y_test)
    """
    # Sort by date — critical for time-based splitting
    features_df = features_df.sort_values("date").reset_index(drop=True)

    # Separate features (X) and target (y)
    X = features_df[FEATURE_COLUMNS]
    y = features_df["team_a_won"]

    # Date-based split: first 80% for training, last 20% for testing
    split_idx = int(len(X) * 0.8)

    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]

    print(f"Training set: {len(X_train)} matches (oldest 80%)")
    print(f"Test set:     {len(X_test)} matches (newest 20%)")

    # Check for class imbalance
    train_pos_rate = y_train.mean()
    print(f"Training set win rate: {train_pos_rate:.1%} (should be near 50%)")

    return X_train, X_test, y_train, y_test


# ─────────────────────────────────────────────────
# STEP 2: TRAIN THE MODEL
# ─────────────────────────────────────────────────

def train_model(X_train: pd.DataFrame, y_train: pd.Series) -> xgb.XGBClassifier:
    """Train an XGBoost binary classifier.

    Hyperparameters are set conservatively to avoid overfitting on small datasets.
    As you get more data, you can increase n_estimators and max_depth.

    Args:
        X_train: Training features
        y_train: Training labels (1 = team_a won, 0 = team_b won)

    Returns:
        Trained XGBClassifier
    """
    model = xgb.XGBClassifier(
        n_estimators=100,           # Number of trees (100 is a good starting point)
        max_depth=4,                # Tree depth (4 prevents overfitting on small data)
        learning_rate=0.1,          # Step size (0.1 is standard)
        subsample=0.8,              # Use 80% of data per tree (reduces overfitting)
        colsample_bytree=0.8,       # Use 80% of features per tree
        objective="binary:logistic", # Binary classification — outputs probabilities
        eval_metric="logloss",      # Optimize for calibrated probabilities
        random_state=42,            # Reproducibility — same data = same model
        verbosity=0,                # Suppress XGBoost internal logs
    )

    print("Training XGBoost model...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train)],
        verbose=False,
    )
    print("Training complete.")

    return model


# ─────────────────────────────────────────────────
# STEP 3: EVALUATE THE MODEL
# ─────────────────────────────────────────────────

def evaluate_model(model: xgb.XGBClassifier, X_test: pd.DataFrame,
                   y_test: pd.Series) -> dict:
    """Evaluate the trained model on the test set.

    Computes:
    - Accuracy: what percentage of matches were predicted correctly
    - Log loss: how well-calibrated the probabilities are (lower = better)
    - Classification report: precision, recall, f1-score per class

    Args:
        model:  Trained XGBClassifier
        X_test: Test features
        y_test: Test labels

    Returns:
        Dict with 'accuracy', 'log_loss', 'y_pred', 'y_pred_proba'
    """
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]  # P(team_a wins)

    acc = accuracy_score(y_test, y_pred)
    ll = log_loss(y_test, y_pred_proba)

    print(f"\n{'=' * 60}")
    print(f"MODEL EVALUATION RESULTS")
    print(f"{'=' * 60}")
    print(f"Accuracy:  {acc:.1%}  (target: 62%+)")
    print(f"Log Loss:  {ll:.4f}  (target: < 0.65)")
    print(f"\nDetailed Classification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=["Team B won", "Team A won"],
        digits=3,
    ))

    return {
        "accuracy": float(acc),
        "log_loss": float(ll),
        "y_pred": y_pred,
        "y_pred_proba": y_pred_proba,
    }


# ─────────────────────────────────────────────────
# STEP 4: PLOT EVALUATION CHARTS
# ─────────────────────────────────────────────────

def plot_feature_importance(model: xgb.XGBClassifier, output_path: str):
    """Bar chart of feature importance — which features matter most.

    This tells you WHERE to invest effort. If 'team_a_form' dominates,
    improving form calculation will help more than adding new features.
    """
    importance = dict(zip(FEATURE_COLUMNS, model.feature_importances_))
    sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

    names = [f[0] for f in sorted_features]
    values = [f[1] for f in sorted_features]

    plt.figure(figsize=(10, 6))
    bars = plt.barh(range(len(names)), values, color="#2196F3", edgecolor="white")
    plt.yticks(range(len(names)), names, fontsize=11)
    plt.xlabel("Importance Score", fontsize=12)
    plt.title("Feature Importance — What Drives Predictions?", fontsize=14)
    plt.gca().invert_yaxis()  # Most important at top
    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")

    # Also print to console
    print(f"\nFeature Importance (most to least):")
    for name, value in sorted_features:
        bar = "#" * int(value * 50)
        print(f"  {name:25s} {value:.3f} {bar}")


def plot_calibration_curve(y_test: pd.Series, y_pred_proba: np.ndarray,
                           output_path: str):
    """Calibration curve: when the model says 70%, does the team win 70% of the time?

    A well-calibrated model has points close to the diagonal line.
    - Above the diagonal = model is underconfident (says 60%, actually wins 75%)
    - Below the diagonal = model is overconfident (says 80%, actually wins 60%)
    """
    n_bins = min(5, max(2, len(y_test) // 10))  # Adaptive bins for small datasets
    prob_true, prob_pred = calibration_curve(y_test, y_pred_proba, n_bins=n_bins)

    plt.figure(figsize=(8, 6))
    plt.plot(prob_pred, prob_true, marker="o", linewidth=2, markersize=8,
             label="Our model", color="#4CAF50")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    plt.fill_between([0, 1], [0, 1], alpha=0.05, color="gray")
    plt.xlabel("Predicted Probability", fontsize=12)
    plt.ylabel("Actual Win Rate", fontsize=12)
    plt.title("Calibration Curve — Are Probabilities Trustworthy?", fontsize=14)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")


def plot_prediction_distribution(y_pred_proba: np.ndarray, output_path: str):
    """Histogram of prediction confidence.

    Clustered around 0.5 = model cannot tell teams apart (bad).
    Spread out = model is making confident, decisive predictions (good).
    """
    plt.figure(figsize=(8, 6))
    plt.hist(y_pred_proba, bins=20, edgecolor="white", alpha=0.8, color="#FF9800")
    plt.axvline(x=0.5, color="red", linestyle="--", linewidth=2, label="50% (coin flip)")
    plt.xlabel("Predicted P(Team A Wins)", fontsize=12)
    plt.ylabel("Number of Matches", fontsize=12)
    plt.title("Prediction Distribution — How Confident Is the Model?", fontsize=14)
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")


# ─────────────────────────────────────────────────
# STEP 5: SAVE THE MODEL + METADATA
# ─────────────────────────────────────────────────

def save_model(model: xgb.XGBClassifier, metrics: dict):
    """Save the trained model and metadata to the models/ directory.

    Saves:
    - models/model.json:    The trained XGBoost model (loadable later)
    - models/metadata.json: Accuracy, features, hyperparameters, timestamp

    The metadata file is important — it records which features the model
    expects, so predict.py knows what to compute.
    """
    os.makedirs("models", exist_ok=True)

    # Save the model itself
    model_path = "models/model.json"
    model.save_model(model_path)
    print(f"\nModel saved to {model_path}")

    # Save metadata
    metadata = {
        "model_version": "v1",
        "trained_at": datetime.now().isoformat(),
        "accuracy": metrics["accuracy"],
        "log_loss": metrics["log_loss"],
        "feature_columns": FEATURE_COLUMNS,
        "hyperparameters": {
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth,
            "learning_rate": model.learning_rate,
            "subsample": model.subsample,
            "colsample_bytree": model.colsample_bytree,
        },
        "notes": "Date-based 80/20 split. No data leakage.",
    }

    metadata_path = "models/metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to {metadata_path}")


# ─────────────────────────────────────────────────
# MAIN: RUN THE FULL PIPELINE
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("CricketIQ — XGBoost Model Training")
    print("=" * 60)

    # ── Load data and build features ──
    print("\n[1/5] Loading data from database...")
    df = load_matches_dataframe()

    if len(df) == 0:
        print("No matches in database. Run the fetch agent first (Week 1).")
        exit(1)

    print("\n[2/5] Building feature matrix...")
    features_df = build_feature_matrix(df)

    if len(features_df) < 20:
        print(f"\nOnly {len(features_df)} matches with features.")
        print("Need at least 20 for a meaningful model.")
        print("Fetch more match data and try again.")
        exit(1)

    # ── Split and train ──
    print("\n[3/5] Splitting data (date-based 80/20)...")
    X_train, X_test, y_train, y_test = prepare_data(features_df)

    print("\n[4/5] Training XGBoost model...")
    model = train_model(X_train, y_train)

    # ── Evaluate ──
    print("\n[5/5] Evaluating model...")
    metrics = evaluate_model(model, X_test, y_test)

    # ── Save model ──
    save_model(model, metrics)

    # ── Generate evaluation charts ──
    print("\nGenerating evaluation charts...")
    plot_feature_importance(model, "models/feature_importance.png")
    plot_calibration_curve(y_test, metrics["y_pred_proba"], "models/calibration_curve.png")
    plot_prediction_distribution(metrics["y_pred_proba"], "models/prediction_distribution.png")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"TRAINING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Accuracy:  {metrics['accuracy']:.1%}")
    print(f"  Log Loss:  {metrics['log_loss']:.4f}")
    print(f"  Model:     models/model.json")
    print(f"  Metadata:  models/metadata.json")
    print(f"  Charts:    models/*.png")

    if metrics["accuracy"] < 0.55:
        print(f"\n  Accuracy is below 55%. This usually means:")
        print(f"  - Not enough training data (get more matches)")
        print(f"  - Features are too noisy (need better feature engineering)")
    elif metrics["accuracy"] >= 0.62:
        print(f"\n  You beat the 62% target! The model is working well.")
    else:
        print(f"\n  Decent start. More data and better features will improve this.")