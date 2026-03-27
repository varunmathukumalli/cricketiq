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

# ─────────────────────────────────────────────────
# Match priority filter
# ─────────────────────────────────────────────────
# Major leagues and ICC events we care about
MAJOR_SERIES_KEYWORDS = [
    # ICC events
    "world cup", "champions trophy", "world test championship", "wtc",
    # Bilateral internationals (detected by team names + "tour of")
    "tour of",
    # Major T20 leagues
    "indian premier league", "ipl",
    "big bash", "bbl",
    "pakistan super league", "psl",
    "caribbean premier league", "cpl",
    "sa20",
    "the hundred",
    "international league t20", "ilt20",
    "bangladesh premier league", "bpl",
    "major league cricket", "mlc",
    "lanka premier league", "lpl",
]

# ICC Full Member teams (for filtering bilateral tours)
ICC_FULL_MEMBERS = {
    "india", "australia", "england", "south africa", "new zealand",
    "pakistan", "sri lanka", "bangladesh", "west indies", "afghanistan",
    "ireland", "zimbabwe",
}

# Teams to exclude even if they appear in tours
EXCLUDE_KEYWORDS = [
    "ranji trophy", "sheffield shield", "county championship",
    "provincial", "plunket shield", "quaid-e-azam",
    "vijay hazare", "syed mushtaq ali",
    "kalahari", "quadrangular t20i series",
    "lesotho tour", "botswana", "bhutan", "brazil women",
    "sierra leone", "mozambique", "zambia", "malawi",
    "sub regional qualifier", "regional qualifier",
]


def is_major_match(match: dict) -> bool:
    """Check if a match is a major international or franchise league match.

    Returns True for ICC events, Full Member bilaterals, and major leagues.
    Returns False for domestic competitions and minor associate matches.
    """
    name = (match.get("name") or "").lower()

    # Exclude known domestic/minor competitions first
    for kw in EXCLUDE_KEYWORDS:
        if kw in name:
            return False

    # Check against major series keywords
    for kw in MAJOR_SERIES_KEYWORDS:
        if kw in name:
            # For "tour of" matches, verify at least one team is a Full Member
            if kw == "tour of":
                teams = [t.lower() for t in match.get("teams", [])]
                if any(member in team for team in teams for member in ICC_FULL_MEMBERS):
                    return True
                return False
            return True

    return False


def fetch_current_matches(filter_major: bool = True) -> list[dict]:
    """Fetch currently active and recent matches.

    Args:
        filter_major: If True, only return major international/league matches.

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
        match = {
            "id": m.get("id"),
            "name": m.get("name", "Unknown"),
            "match_type": m.get("matchType"),
            "status": m.get("status"),
            "venue": m.get("venue"),
            "date": m.get("date"),
            "teams": m.get("teams", []),
            "score": m.get("score", []),
        }
        if filter_major and not is_major_match(match):
            continue
        cleaned.append(match)
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


def fetch_match_list(offset: int = 0, filter_major: bool = True) -> list[dict]:
    """Fetch historical matches from the /v1/matches endpoint.

    Returns up to 25 matches per call (paginated). After filtering,
    the actual count may be lower.

    Args:
        offset: Pagination offset (0, 25, 50, ...)
        filter_major: If True, only return major international/league matches.

    Returns:
        List of match dicts in our standard format
    """
    url = f"{BASE_URL}/matches?apikey={CRICKET_API_KEY}&offset={offset}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "success":
        return []

    matches = data.get("data", [])

    cleaned = []
    for m in matches:
        match = {
            "id": m.get("id"),
            "name": m.get("name", "Unknown"),
            "match_type": m.get("matchType"),
            "status": m.get("status"),
            "venue": m.get("venue"),
            "date": m.get("date"),
            "teams": m.get("teams", []),
            "score": m.get("score", []),
        }
        if filter_major and not is_major_match(match):
            continue
        cleaned.append(match)
    return cleaned


def fetch_ipl_matches() -> list[dict]:
    """Fetch IPL 2026 matches from the /v1/matches search endpoint.

    The currentMatches endpoint doesn't include scheduled IPL matches.
    This uses the search endpoint to find them.
    """
    IPL_FRANCHISES = {
        "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bengaluru",
        "Kolkata Knight Riders", "Rajasthan Royals", "Delhi Capitals",
        "Punjab Kings", "Gujarat Titans", "Sunrisers Hyderabad", "Lucknow Super Giants",
    }

    all_matches = []
    for offset in [0, 25, 50]:
        url = f"{BASE_URL}/matches?apikey={CRICKET_API_KEY}&offset={offset}&search=Indian Premier League 2026"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success":
                break
            for m in data.get("data", []):
                teams = set(m.get("teams", []))
                # Only include if both teams are IPL franchises
                if teams.issubset(IPL_FRANCHISES) and len(teams) == 2:
                    all_matches.append({
                        "id": m.get("id"),
                        "name": m.get("name", "Unknown"),
                        "match_type": m.get("matchType"),
                        "status": m.get("status"),
                        "venue": m.get("venue"),
                        "date": m.get("date"),
                        "teams": m.get("teams", []),
                        "score": m.get("score", []),
                    })
        except Exception as e:
            print(f"  fetch_ipl_matches offset={offset}: {e}")
            break

    return all_matches


def get_api_calls_remaining() -> str:
    """Check how many API calls we have left today.
    Returns a description string the agent can reason about."""
    # The free tier is 100/day. We don't have an endpoint to check,
    # so we estimate based on database records.
    return "Free tier: 100 calls/day. Track usage manually."


# Test
if __name__ == "__main__":
    print("Fetching current matches (all)...")
    all_matches = fetch_current_matches(filter_major=False)
    print(f"  Total from API: {len(all_matches)}")

    major = [m for m in all_matches if is_major_match(m)]
    minor = [m for m in all_matches if not is_major_match(m)]

    print(f"  Major (kept):   {len(major)}")
    for m in major:
        print(f"    + {m['name']}")

    print(f"  Minor (filtered out): {len(minor)}")
    for m in minor:
        print(f"    - {m['name']}")
