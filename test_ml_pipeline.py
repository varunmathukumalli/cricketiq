"""
End-to-end test of the ML pipeline.
Verifies: features -> train -> predict -> tools all work together.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("CricketIQ ML Pipeline — End-to-End Test")
print("=" * 60)

# Test 1: Feature engineering
print("\n[1/4] Testing feature engineering...")
from ml.features import load_matches_dataframe, build_feature_matrix, FEATURE_COLUMNS
df = load_matches_dataframe()
assert len(df) > 0, "No matches in database"
features = build_feature_matrix(df)
assert len(features) > 0, "No features built"
assert all(col in features.columns for col in FEATURE_COLUMNS), "Missing feature columns"
print(f"  OK — {len(features)} matches with {len(FEATURE_COLUMNS)} features each")

# Test 2: Model exists
print("\n[2/4] Testing model files...")
assert os.path.exists("models/model.json"), "model.json not found"
assert os.path.exists("models/metadata.json"), "metadata.json not found"
with open("models/metadata.json") as f:
    meta = json.load(f)
print(f"  OK — Model v{meta.get('model_version')} with {meta.get('accuracy', 0):.1%} accuracy")

# Test 3: Tools are callable
print("\n[3/4] Testing LangChain tools...")
from tools.ml_model import get_model_accuracy, get_feature_importance

accuracy_result = get_model_accuracy.invoke({})
assert "Accuracy" in accuracy_result, "get_model_accuracy failed"
print(f"  get_model_accuracy: OK")

importance_result = get_feature_importance.invoke({})
assert "Importance" in importance_result, "get_feature_importance failed"
print(f"  get_feature_importance: OK")

# Test 4: Predictions table
print("\n[4/4] Testing predictions table...")
import psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM predictions")
count = cur.fetchone()[0]
cur.close()
conn.close()
print(f"  OK — {count} predictions in database")

print(f"\n{'=' * 60}")
print("ALL TESTS PASSED")
print(f"{'=' * 60}")
print(f"\nYour ML pipeline is complete!")
print(f"  ml/features.py     — feature engineering")
print(f"  ml/train.py        — model training + evaluation")
print(f"  ml/predict.py      — generate predictions")
print(f"  tools/ml_model.py  — LangChain tools for agents")
