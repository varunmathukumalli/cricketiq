"""
models.py — Shared Pydantic models for the CricketIQ project.

All structured data shapes used across agents, tools, and the API live here.
When you pass a Pydantic model to an LLM via .with_structured_output(),
the LLM is forced to return data matching that shape.
"""
from pydantic import BaseModel, Field
from enum import Enum


# ─────────────────────────────────────────────────
# Validation models
# ─────────────────────────────────────────────────

class ValidationStatus(str, Enum):
    """The three possible outcomes of data validation."""
    VALID = "valid"         # Data is clean, proceed to next step
    FLAGGED = "flagged"     # Data has issues, needs human review
    REJECTED = "rejected"   # Data is unusable, re-fetch or discard


class FieldIssue(BaseModel):
    """A single issue found in a data field."""
    field_name: str = Field(description="Name of the problematic field (e.g., 'score', 'venue')")
    issue_type: str = Field(description="Type of issue: 'missing', 'anomaly', 'format_error', 'out_of_range'")
    description: str = Field(description="Human-readable description of the issue")
    severity: str = Field(description="'low', 'medium', or 'high'")


class MatchValidationResult(BaseModel):
    """Structured output from the Validation Agent for a single match.

    The LLM MUST fill in every field. This ensures consistent, actionable results.
    """
    match_id: str = Field(description="The match ID being validated")
    match_name: str = Field(description="Human-readable match name")
    status: ValidationStatus = Field(description="Overall validation result")
    confidence: float = Field(
        description="Agent's confidence in this assessment (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    issues: list[FieldIssue] = Field(
        default_factory=list,
        description="List of specific issues found. Empty if status is 'valid'."
    )
    summary: str = Field(description="One-sentence summary of the validation result")
    suggested_action: str = Field(
        description="What to do next: 'proceed', 'review_and_approve', 're_fetch', or 'discard'"
    )


class BatchValidationResult(BaseModel):
    """Structured output for validating a batch of matches."""
    total_matches: int = Field(description="Total number of matches validated")
    valid_count: int = Field(description="Number of matches that passed validation")
    flagged_count: int = Field(description="Number of matches flagged for review")
    rejected_count: int = Field(description="Number of matches rejected")
    results: list[MatchValidationResult] = Field(description="Individual results per match")
    overall_summary: str = Field(description="Summary of the entire batch")


# Test the models
if __name__ == "__main__":
    # Create a sample result to verify the model works
    sample = MatchValidationResult(
        match_id="test-123",
        match_name="India vs Australia, 1st Test",
        status=ValidationStatus.FLAGGED,
        confidence=0.78,
        issues=[
            FieldIssue(
                field_name="score",
                issue_type="anomaly",
                description="Team scored 950/2 — unusually high for 50 overs",
                severity="high",
            ),
            FieldIssue(
                field_name="venue",
                issue_type="missing",
                description="Venue field is empty",
                severity="medium",
            ),
        ],
        summary="Match has a suspiciously high score and missing venue data.",
        suggested_action="review_and_approve",
    )

    print("Sample validation result:")
    print(sample.model_dump_json(indent=2))
    print()
    print(f"Status: {sample.status.value}")
    print(f"Issues: {len(sample.issues)}")
    print(f"Action: {sample.suggested_action}")
