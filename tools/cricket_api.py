"""
cricket_api.py — CricketData.org API functions.

Plain Python functions that fetch cricket data.
Agents call these as tools.
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()
CRICKET_API_KEY = os.getenv("CRICKET_API_KEY")
BASE_URL = "https://api.cricapi.com/v1"


def fetch_current_matches() -> list[dict]:
    """Fetch currently active and recent matches.

    Returns:
        List of match dicts from the API
    """
    url = f"{BASE_URL}/currentMatches?apikey={CRICKET_API_KEY}&offset=0"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "success":
        return []

    matches = data.get("data", [])

    # Transform to our format
    cleaned = []
    for m in matches:
        cleaned.append({
            "id": m.get("id"),
            "name": m.get("name", "Unknown"),
            "match_type": m.get("matchType"),
            "status": m.get("status"),            
            "venue": m.get("venue"),
            "date": m.get("date"),
            "teams": m.get("teams", []),
            "score": m.get("score", []),
        })
    return cleaned


def fetch_match_scorecard(match_id: str) -> dict:
    """Fetch detailed scorecard for a match.

    Args:
        match_id: The match ID from the API

    Returns:
        Full scorecard dict
    """
    url = f"{BASE_URL}/match_scorecard?apikey={CRICKET_API_KEY}&id={match_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json().get("data", {})


def get_api_calls_remaining() -> str:
    """Check how many API calls we have left today.
    Returns a description string the agent can reason about."""
    # The free tier is 100/day. We don't have an endpoint to check,
    # so we estimate based on database records.
    return "Free tier: 100 calls/day. Track usage manually."


# Test
if __name__ == "__main__":
    print("Fetching current matches...")
    matches = fetch_current_matches()
    print(f"Got {len(matches)} matches")
    if matches:
        print(f"First match: {matches[0]['name']}")
