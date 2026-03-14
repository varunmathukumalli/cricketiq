"""
validation_agent.py — Data Validation Agent

ROLE: Checks data quality of fetched cricket matches.
      Detects anomalies, missing fields, and format issues.
LLM: Gemini 2.0 Flash (structured output mode)

CONCEPTS TAUGHT:
  1. Structured output — forcing the LLM to return MatchValidationResult
  2. Tool schemas — giving the LLM tools to inspect the database
  3. How structured output differs from free-form agent reasoning

The agent receives match data and returns one of:
  - VALID: data is clean, proceed
  - FLAGGED: data has issues, needs human review
  - REJECTED: data is unusable
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

from src.models import (
    MatchValidationResult,
    BatchValidationResult,
    ValidationStatus,
    FieldIssue,
)
from tools.database import query_database


# ─────────────────────────────────────────────────
# Validation rules (plain Python — no LLM needed)
# ─────────────────────────────────────────────────

def pre_validate_match(match: dict) -> list[dict]:
    """Run rule-based checks before asking the LLM.

    These are deterministic checks that don't need AI.
    The LLM handles the fuzzier, judgment-based checks.

    Returns:
        List of issue dicts (empty if all checks pass).
    """
    issues = []

    # Check required fields
    required_fields = ["id", "name", "status"]
    for field in required_fields:
        if not match.get(field):
            issues.append({
                "field_name": field,
                "issue_type": "missing",
                "description": f"Required field '{field}' is missing or empty",
                "severity": "high",
            })

    # Check score format
    score = match.get("score")
    if score:
        if isinstance(score, str):
            try:
                score = json.loads(score)
            except json.JSONDecodeError:
                issues.append({
                    "field_name": "score",
                    "issue_type": "format_error",
                    "description": "Score field is not valid JSON",
                    "severity": "high",
                })
                score = None

        if isinstance(score, list):
            for entry in score:
                # Check for negative runs
                inning_str = entry.get("r") or entry.get("runs")
                if inning_str is not None:
                    try:
                        runs = int(inning_str) if isinstance(inning_str, str) else inning_str
                        if runs < 0:
                            issues.append({
                                "field_name": "score",
                                "issue_type": "out_of_range",
                                "description": f"Negative runs detected: {runs}",
                                "severity": "high",
                            })
                    except (ValueError, TypeError):
                        pass

    # Check venue exists
    if not match.get("venue"):
        issues.append({
            "field_name": "venue",
            "issue_type": "missing",
            "description": "Venue is missing — weather agent cannot run without it",
            "severity": "medium",
        })

    # Check date exists
    if not match.get("date"):
        issues.append({
            "field_name": "date",
            "issue_type": "missing",
            "description": "Date is missing",
            "severity": "medium",
        })

    # Check teams
    teams = match.get("teams")
    if not teams or (isinstance(teams, list) and len(teams) < 2):
        issues.append({
            "field_name": "teams",
            "issue_type": "missing",
            "description": "Fewer than 2 teams listed",
            "severity": "high",
        })

    return issues


# ─────────────────────────────────────────────────
# LLM-powered validation (for judgment calls)
# ─────────────────────────────────────────────────

def create_validation_llm():
    """Create a Gemini Flash LLM configured for structured output.

    CONCEPT: .with_structured_output(MatchValidationResult) forces the LLM
             to return data matching our Pydantic model exactly.
             No parsing, no regex, no hoping the format is right.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

    # This is the key line — structured output
    structured_llm = llm.with_structured_output(MatchValidationResult)

    return structured_llm


def validate_match(match: dict) -> MatchValidationResult:
    """Validate a single match using rule-based checks + LLM judgment.

    Args:
        match: Match dict from the database.

    Returns:
        MatchValidationResult with status, issues, and suggested action.
    """
    # Step 1: Run deterministic rule-based checks
    rule_issues = pre_validate_match(match)

    # Step 2: If rule-based checks found high-severity issues, skip the LLM entirely.
    # Why waste an API call (and hit rate limits) on data that's clearly broken?
    high_severity_issues = [i for i in rule_issues if i["severity"] == "high"]
    if high_severity_issues:
        return MatchValidationResult(
            match_id=match.get("id", "unknown"),
            match_name=match.get("name", "Unknown"),
            status=ValidationStatus.REJECTED,
            confidence=1.0,
            issues=[FieldIssue(**issue) for issue in rule_issues],
            summary=f"Rejected by rule-based checks: {len(high_severity_issues)} high-severity issue(s) found. LLM call skipped.",
            suggested_action="discard",
        )

    # Step 3: Ask the LLM for judgment-based validation (fuzzy checks)
    structured_llm = create_validation_llm()

    prompt = f"""You are a cricket data quality expert with high Cricket IQ and knowledge of cricket. 
    Validate this match data and make sure the data is correct and complete.

MATCH DATA:
{json.dumps(match, indent=2, default=str)}

RULE-BASED ISSUES ALREADY FOUND:
{json.dumps(rule_issues, indent=2) if rule_issues else "None — all basic checks passed."}

YOUR JOB:
1. Review the match data for anomalies a rule can't catch:
   - Does the score make sense for the match type? (T20: typically 100-250 runs, ODI: 150-400, Test: 100-800)
   - Are team names real cricket teams?
   - Does the status field make sense?
   - Any other data quality issues?

2. Combine your findings with the rule-based issues above.

3. Determine the overall status:
   - VALID: No issues, or only minor cosmetic issues
   - FLAGGED: Has issues that need human review but data might be usable
   - REJECTED: Data is clearly wrong or unusable

4. Set confidence between 0.0 and 1.0 based on how sure you are.

5. Suggest an action: 'proceed', 'review_and_approve', 're_fetch', or 'discard'.
"""

    # Retry with exponential backoff for Gemini rate limits (429 errors).
    # Free tier has low RPM limits, so we wait and retry instead of crashing.
    messages = [
        SystemMessage(content="You are a cricket data validation specialist with very high Cricket IQ and knowledge of cricket. \
            Validate the match data and make sure the data is correct and complete. \
            Return structured validation results with the following fields: match_id, match_name, status, confidence, issues, summary, suggested_action."),
        HumanMessage(content=prompt),
    ]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = structured_llm.invoke(messages)
            break  # Success — exit retry loop
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                print(f"  Rate limited (429). Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait_time)
            else:
                raise  # Non-429 error or final attempt — let it propagate

    # Gemini may return None for structured output on very malformed data
    if result is None:
        return MatchValidationResult(
            match_id=match.get("id", "unknown"),
            match_name=match.get("name", "Unknown"),
            status=ValidationStatus.REJECTED,
            confidence=0.0,
            issues=[FieldIssue(
                field_name="llm_response",
                issue_type="format_error",
                description="LLM returned no structured output — data likely too malformed to parse",
                severity="high",
            )],
            summary="LLM could not produce a structured validation result for this data.",
            suggested_action="discard",
        )

    return result


def validate_batch(matches: list[dict]) -> BatchValidationResult:
    """Validate a batch of matches.

    Args:
        matches: List of match dicts.

    Returns:
        BatchValidationResult with individual and aggregate results.
    """
    results = []
    for match in matches:
        try:
            result = validate_match(match)
            results.append(result)
        except Exception as e:
            # If validation itself fails, mark as flagged
            results.append(MatchValidationResult(
                match_id=match.get("id", "unknown"),
                match_name=match.get("name", "Unknown"),
                status=ValidationStatus.FLAGGED,
                confidence=0.0,
                issues=[FieldIssue(
                    field_name="validation_error",
                    issue_type="format_error",
                    description=f"Validation failed with error: {str(e)}",
                    severity="high",
                )],
                summary=f"Validation process failed: {str(e)}",
                suggested_action="review_and_approve",
            ))

    valid_count = sum(1 for r in results if r.status == ValidationStatus.VALID)
    flagged_count = sum(1 for r in results if r.status == ValidationStatus.FLAGGED)
    rejected_count = sum(1 for r in results if r.status == ValidationStatus.REJECTED)

    return BatchValidationResult(
        total_matches=len(results),
        valid_count=valid_count,
        flagged_count=flagged_count,
        rejected_count=rejected_count,
        results=results,
        overall_summary=(
            f"Validated {len(results)} matches: "
            f"{valid_count} valid, {flagged_count} flagged, {rejected_count} rejected."
        ),
    )


# ─────────────────────────────────────────────────
# LangChain tool wrappers (for use in graphs)
# ─────────────────────────────────────────────────

@tool
def tool_validate_recent_matches() -> str:
    """Validate the most recently fetched matches in the database.
    Returns a structured summary of validation results."""
    matches = query_database("""
        SELECT id, name, match_type, status, venue, date,
               teams, score::text, api_response::text
        FROM matches
        ORDER BY updated_at DESC
        LIMIT 5
    """)

    if not matches:
        return "No matches found in database to validate."

    batch_result = validate_batch(matches)
    return batch_result.model_dump_json(indent=2)


@tool
def tool_validate_single_match(match_id: str) -> str:
    """Validate a specific match by its ID.

    Args:
        match_id: The match ID to validate.
    """
    matches = query_database(
        "SELECT id, name, match_type, status, venue, date, teams, score::text FROM matches WHERE id = %s",
        (match_id,)
    )
    if not matches:
        return f"Match {match_id} not found."

    result = validate_match(matches[0])
    return result.model_dump_json(indent=2)


# ─────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Testing Data Validation Agent")
    print("=" * 50)

    # Test with synthetic data first (no database needed)
    test_match_good = {
        "id": "test-001",
        "name": "India vs Australia, 3rd ODI",
        "match_type": "odi",
        "status": "Match over",
        "venue": "Wankhede Stadium",
        "date": "2025-01-15",
        "teams": ["India", "Australia"],
        "score": [
            {"team": "India", "runs": 287, "wickets": 6, "overs": 50},
            {"team": "Australia", "runs": 245, "wickets": 10, "overs": 47.3},
        ],
    }

    test_match_bad = {
        "id": "test-002",
        "name": "Unknown Match",
        "match_type": "t20",
        "status": "",
        "venue": "",
        "date": None,
        "teams": ["TeamX"],
        "score": [
            {"team": "TeamX", "runs": 850, "wickets": 2, "overs": 20},
        ],
    }

    print("\nValidating GOOD match...")
    result1 = validate_match(test_match_good)
    print(f"  Status: {result1.status.value}")
    print(f"  Confidence: {result1.confidence}")
    print(f"  Issues: {len(result1.issues)}")
    print(f"  Summary: {result1.summary}")

    print("\nValidating BAD match...")
    result2 = validate_match(test_match_bad)
    print(f"  Status: {result2.status.value}")
    print(f"  Confidence: {result2.confidence}")
    print(f"  Issues: {len(result2.issues)}")
    for issue in result2.issues:
        print(f"    - [{issue.severity}] {issue.field_name}: {issue.description}")
    print(f"  Summary: {result2.summary}")
    print(f"  Action: {result2.suggested_action}")