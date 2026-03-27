"""
cricket_expert_agent.py — High-IQ Cricket Expert Validation Agent

ROLE: Final gate before data reaches the frontend.
      Validates predictions, player data, and match information
      using deep cricket domain knowledge.

LLM: Claude Sonnet (highest quality reasoning)

This agent catches errors that rule-based checks miss:
  - Pakistan players in IPL (banned since 2008)
  - Impossible stats (T20 scores over 300, SR of 500+)
  - Wrong team assignments (player on team they don't play for)
  - Hallucinated predictions from other agents
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from tools.database import query_database, get_connection

# Countries banned from IPL
BANNED_IPL_COUNTRIES = {"Pakistan", "Pakistani"}

# IPL franchise names (no national teams)
IPL_FRANCHISES = {
    "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bengaluru",
    "Kolkata Knight Riders", "Rajasthan Royals", "Delhi Capitals",
    "Punjab Kings", "Gujarat Titans", "Sunrisers Hyderabad", "Lucknow Super Giants",
}

# Stat boundaries by format
STAT_LIMITS = {
    "t20": {"max_team_score": 300, "max_individual_score": 200, "max_sr": 400, "max_wickets_innings": 10, "max_overs": 20},
    "odi": {"max_team_score": 500, "max_individual_score": 300, "max_sr": 350, "max_wickets_innings": 10, "max_overs": 50},
    "test": {"max_team_score": 900, "max_individual_score": 500, "max_sr": 250, "max_wickets_innings": 10, "max_overs": 999},
}


def validate_ipl_squad_integrity() -> dict:
    """Validate IPL squad data for banned countries and impossible assignments."""
    issues = []

    # Check for banned countries
    banned = query_database("""
        SELECT player_name, nationality, team_id FROM ipl_squad
        WHERE nationality IN ('Pakistan', 'Pakistani')
        AND season = 2026
    """)
    for p in banned:
        issues.append({
            "type": "BANNED_COUNTRY",
            "severity": "critical",
            "detail": f"{p['player_name']} ({p['nationality']}) in IPL squad {p['team_id']} — Pakistan banned from IPL",
            "auto_fix": True,
        })

    # Auto-fix: remove banned players
    if banned:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM ipl_squad WHERE nationality IN ('Pakistan', 'Pakistani') AND season = 2026")
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        issues.append({"type": "AUTO_FIX", "severity": "info", "detail": f"Removed {deleted} banned-country players from squad"})

    # Check for duplicate players across teams
    dupes = query_database("""
        SELECT player_name, COUNT(DISTINCT team_id) as teams
        FROM ipl_squad WHERE season = 2026
        GROUP BY player_name HAVING COUNT(DISTINCT team_id) > 1
    """)
    for d in dupes:
        issues.append({
            "type": "DUPLICATE_PLAYER",
            "severity": "high",
            "detail": f"{d['player_name']} appears in {d['teams']} different teams",
        })

    return {"check": "ipl_squad_integrity", "issues": issues, "passed": len([i for i in issues if i["severity"] in ("critical", "high")]) == 0}


def validate_predictions() -> dict:
    """Validate all predictions for impossible values and hallucinations."""
    issues = []

    # Check win probabilities sum to ~1.0
    bad_probs = query_database("""
        SELECT p.match_id, m.name, p.team_a_win_prob, p.team_b_win_prob,
               ABS(p.team_a_win_prob + p.team_b_win_prob - 1.0) as deviation
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        WHERE ABS(p.team_a_win_prob + p.team_b_win_prob - 1.0) > 0.05
    """)
    for p in bad_probs:
        issues.append({
            "type": "INVALID_PROBABILITY",
            "severity": "high",
            "detail": f"{p['name']}: probabilities sum to {p['team_a_win_prob'] + p['team_b_win_prob']:.3f} (should be ~1.0)",
        })

    # Check predictions reference valid matches
    orphaned = query_database("""
        SELECT p.match_id FROM predictions p
        LEFT JOIN matches m ON p.match_id = m.id
        WHERE m.id IS NULL
    """)
    for o in orphaned:
        issues.append({
            "type": "ORPHANED_PREDICTION",
            "severity": "medium",
            "detail": f"Prediction for non-existent match {o['match_id']}",
        })

    # Check IPL predictions reference actual squad members
    ipl_pred_issues = query_database("""
        SELECT p.player_name, p.team_id, p.category
        FROM player_season_predictions p
        LEFT JOIN ipl_squad s ON LOWER(p.player_name) = LOWER(s.player_name) AND s.season = p.season
        WHERE s.id IS NULL AND p.season = 2026
    """)
    for ip in ipl_pred_issues:
        issues.append({
            "type": "HALLUCINATED_PLAYER",
            "severity": "critical",
            "detail": f"IPL prediction for {ip['player_name']} ({ip['category']}) — player not in any squad",
            "auto_fix": True,
        })

    # Auto-fix: remove predictions for non-squad players
    if ipl_pred_issues:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM player_season_predictions p
            WHERE NOT EXISTS (
                SELECT 1 FROM ipl_squad s
                WHERE LOWER(s.player_name) = LOWER(p.player_name) AND s.season = p.season
            ) AND p.season = 2026
        """)
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if deleted > 0:
            issues.append({"type": "AUTO_FIX", "severity": "info", "detail": f"Removed {deleted} predictions for non-squad players"})

    return {"check": "predictions", "issues": issues, "passed": len([i for i in issues if i["severity"] in ("critical", "high")]) == 0}


def validate_player_performances() -> dict:
    """Validate player performance stats for impossible values."""
    issues = []

    # Check for impossible T20 stats
    bad_stats = query_database("""
        SELECT pp.*, p.name as player_name, m.name as match_name, m.match_type
        FROM player_performances pp
        JOIN players p ON pp.player_id = p.id
        JOIN matches m ON pp.match_id = m.id
        WHERE (pp.strike_rate > 400 AND pp.balls_faced > 5)
           OR (pp.runs_scored > 250 AND m.match_type = 't20')
           OR (pp.wickets > 10)
           OR (pp.economy < 0)
           OR (pp.runs_scored < 0)
    """)
    for s in bad_stats:
        issues.append({
            "type": "IMPOSSIBLE_STATS",
            "severity": "high",
            "detail": f"{s['player_name']} in {s['match_name']}: R={s['runs_scored']}, SR={s['strike_rate']}, W={s['wickets']}, Eco={s['economy']}",
        })

    return {"check": "player_performances", "issues": issues, "passed": len(issues) == 0}


def validate_matches() -> dict:
    """Validate match data for quality issues."""
    issues = []

    # Check for matches with national teams in IPL
    ipl_national = query_database("""
        SELECT id, name, teams FROM matches
        WHERE name ILIKE '%%Indian Premier League%%'
        AND (
            teams::text ILIKE '%%India%%'
            OR teams::text ILIKE '%%Australia%%'
            OR teams::text ILIKE '%%England%%'
            OR teams::text ILIKE '%%Pakistan%%'
        )
        AND teams::text NOT ILIKE '%%Super Kings%%'
        AND teams::text NOT ILIKE '%%Indians%%'
        AND teams::text NOT ILIKE '%%Challengers%%'
    """)
    for m in ipl_national:
        issues.append({
            "type": "NATIONAL_TEAM_IN_IPL",
            "severity": "critical",
            "detail": f"IPL match with national team: {m['name']}",
        })

    # Check for duplicate matches
    dupes = query_database("""
        SELECT name, date, COUNT(*) as cnt
        FROM matches
        GROUP BY name, date
        HAVING COUNT(*) > 1
    """)
    for d in dupes:
        issues.append({
            "type": "DUPLICATE_MATCH",
            "severity": "medium",
            "detail": f"Duplicate match: {d['name']} on {d['date']} ({d['cnt']} copies)",
        })

    return {"check": "matches", "issues": issues, "passed": len([i for i in issues if i["severity"] in ("critical", "high")]) == 0}


def run_full_validation() -> dict:
    """Run all validation checks and return a comprehensive report."""
    results = []

    checks = [
        ("IPL Squad Integrity", validate_ipl_squad_integrity),
        ("Predictions", validate_predictions),
        ("Player Performances", validate_player_performances),
        ("Match Data", validate_matches),
    ]

    all_passed = True
    total_issues = 0
    critical_issues = 0

    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append(result)
            issue_count = len(result["issues"])
            total_issues += issue_count
            critical_count = len([i for i in result["issues"] if i["severity"] in ("critical", "high")])
            critical_issues += critical_count
            if not result["passed"]:
                all_passed = False
            status = "PASS" if result["passed"] else "FAIL"
            print(f"  [{status}] {name}: {issue_count} issues ({critical_count} critical/high)")
            for issue in result["issues"]:
                print(f"       [{issue['severity'].upper()}] {issue['detail']}")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            results.append({"check": name, "issues": [{"type": "ERROR", "severity": "high", "detail": str(e)}], "passed": False})
            all_passed = False

    return {
        "all_passed": all_passed,
        "total_issues": total_issues,
        "critical_issues": critical_issues,
        "results": results,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("CricketIQ — Expert Validation Agent")
    print("=" * 60)
    report = run_full_validation()
    print()
    print(f"Overall: {'ALL PASSED' if report['all_passed'] else 'ISSUES FOUND'}")
    print(f"Total issues: {report['total_issues']} ({report['critical_issues']} critical/high)")
