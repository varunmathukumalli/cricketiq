"""Quick tests for the validation agent."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.validation_agent import validate_match, pre_validate_match
from src.models import ValidationStatus


def test_pre_validation_catches_missing_fields():
    """Rule-based checks should catch missing required fields."""
    bad_match = {"id": "", "name": "", "status": ""}
    issues = pre_validate_match(bad_match)
    assert len(issues) >= 3, f"Expected at least 3 issues, got {len(issues)}"
    print("  PASS: missing fields detected")


def test_pre_validation_passes_good_data():
    """Good data should produce no rule-based issues."""
    good_match = {
        "id": "abc-123",
        "name": "India vs Australia, 1st T20I",
        "status": "Match over",
        "venue": "Wankhede Stadium",
        "date": "2025-06-01",
        "teams": ["India", "Australia"],
        "score": [{"runs": 180, "wickets": 5}],
    }
    issues = pre_validate_match(good_match)
    assert len(issues) == 0, f"Expected 0 issues, got {len(issues)}: {issues}"
    print("  PASS: good data passes")


def test_pre_validation_catches_negative_runs():
    """Negative runs should be flagged."""
    match = {
        "id": "neg-001",
        "name": "Test Match",
        "status": "Live",
        "venue": "Lords",
        "date": "2025-06-01",
        "teams": ["A", "B"],
        "score": [{"r": -50}],
    }
    issues = pre_validate_match(match)
    negative_issues = [i for i in issues if i["issue_type"] == "out_of_range"]
    assert len(negative_issues) >= 1, f"Expected negative runs flagged, got: {issues}"
    print("  PASS: negative runs caught")


if __name__ == "__main__":
    print("Running validation tests...")
    test_pre_validation_catches_missing_fields()
    test_pre_validation_passes_good_data()
    test_pre_validation_catches_negative_runs()
    print("\nAll tests passed!")
