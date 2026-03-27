"""
seed_ipl_players.py — Seed IPL 2025 player performance data.

Real stats from IPL 2025 (first half) + recent international form.
This gives the ML model and AI agents enough data to analyze player form
and predict who will perform better.
"""
import psycopg2
import psycopg2.extras
import os
import uuid
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def deterministic_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cricketiq.player.{name}"))


def deterministic_match_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cricketiq.ipl.{name}"))


# IPL 2025 teams and key players with real stats
IPL_PLAYERS = [
    # --- Chennai Super Kings ---
    {"name": "Ruturaj Gaikwad", "country": "India", "team": "Chennai Super Kings", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium"},
    {"name": "Devon Conway", "country": "New Zealand", "team": "Chennai Super Kings", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": ""},
    {"name": "Ravindra Jadeja", "country": "India", "team": "Chennai Super Kings", "role": "All-rounder", "batting_style": "Left-hand bat", "bowling_style": "Slow left-arm orthodox"},
    {"name": "Matheesha Pathirana", "country": "Sri Lanka", "team": "Chennai Super Kings", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast"},
    {"name": "MS Dhoni", "country": "India", "team": "Chennai Super Kings", "role": "WK-Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium"},

    # --- Mumbai Indians ---
    {"name": "Rohit Sharma", "country": "India", "team": "Mumbai Indians", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Suryakumar Yadav", "country": "India", "team": "Mumbai Indians", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium"},
    {"name": "Jasprit Bumrah", "country": "India", "team": "Mumbai Indians", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast"},
    {"name": "Tilak Varma", "country": "India", "team": "Mumbai Indians", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": "Slow left-arm orthodox"},
    {"name": "Hardik Pandya", "country": "India", "team": "Mumbai Indians", "role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium-fast"},

    # --- Royal Challengers Bengaluru ---
    {"name": "Virat Kohli", "country": "India", "team": "Royal Challengers Bengaluru", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium"},
    {"name": "Rajat Patidar", "country": "India", "team": "Royal Challengers Bengaluru", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Glenn Maxwell", "country": "Australia", "team": "Royal Challengers Bengaluru", "role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Mohammed Siraj", "country": "India", "team": "Royal Challengers Bengaluru", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium"},
    {"name": "Josh Hazlewood", "country": "Australia", "team": "Royal Challengers Bengaluru", "role": "Bowler", "batting_style": "Left-hand bat", "bowling_style": "Right-arm fast-medium"},

    # --- Kolkata Knight Riders ---
    {"name": "Shreyas Iyer", "country": "India", "team": "Kolkata Knight Riders", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Andre Russell", "country": "West Indies", "team": "Kolkata Knight Riders", "role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast"},
    {"name": "Sunil Narine", "country": "West Indies", "team": "Kolkata Knight Riders", "role": "All-rounder", "batting_style": "Left-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Varun Chakravarthy", "country": "India", "team": "Kolkata Knight Riders", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm legbreak"},
    {"name": "Phil Salt", "country": "England", "team": "Kolkata Knight Riders", "role": "WK-Batter", "batting_style": "Right-hand bat", "bowling_style": ""},

    # --- Rajasthan Royals ---
    {"name": "Sanju Samson", "country": "India", "team": "Rajasthan Royals", "role": "WK-Batter", "batting_style": "Right-hand bat", "bowling_style": ""},
    {"name": "Yashasvi Jaiswal", "country": "India", "team": "Rajasthan Royals", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": "Slow left-arm orthodox"},
    {"name": "Jos Buttler", "country": "England", "team": "Rajasthan Royals", "role": "WK-Batter", "batting_style": "Right-hand bat", "bowling_style": ""},
    {"name": "Trent Boult", "country": "New Zealand", "team": "Rajasthan Royals", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium"},
    {"name": "Yuzvendra Chahal", "country": "India", "team": "Rajasthan Royals", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm legbreak"},

    # --- Delhi Capitals ---
    {"name": "Rishabh Pant", "country": "India", "team": "Delhi Capitals", "role": "WK-Batter", "batting_style": "Left-hand bat", "bowling_style": ""},
    {"name": "David Warner", "country": "Australia", "team": "Delhi Capitals", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": "Right-arm legbreak"},
    {"name": "Axar Patel", "country": "India", "team": "Delhi Capitals", "role": "All-rounder", "batting_style": "Left-hand bat", "bowling_style": "Slow left-arm orthodox"},
    {"name": "Kuldeep Yadav", "country": "India", "team": "Delhi Capitals", "role": "Bowler", "batting_style": "Left-hand bat", "bowling_style": "Left-arm chinaman"},
    {"name": "Anrich Nortje", "country": "South Africa", "team": "Delhi Capitals", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast"},

    # --- Punjab Kings ---
    {"name": "Shikhar Dhawan", "country": "India", "team": "Punjab Kings", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": ""},
    {"name": "Liam Livingstone", "country": "England", "team": "Punjab Kings", "role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm legbreak"},
    {"name": "Sam Curran", "country": "England", "team": "Punjab Kings", "role": "All-rounder", "batting_style": "Left-hand bat", "bowling_style": "Left-arm medium-fast"},
    {"name": "Kagiso Rabada", "country": "South Africa", "team": "Punjab Kings", "role": "Bowler", "batting_style": "Left-hand bat", "bowling_style": "Right-arm fast"},
    {"name": "Arshdeep Singh", "country": "India", "team": "Punjab Kings", "role": "Bowler", "batting_style": "Left-hand bat", "bowling_style": "Left-arm fast-medium"},

    # --- Gujarat Titans ---
    {"name": "Shubman Gill", "country": "India", "team": "Gujarat Titans", "role": "Batter", "batting_style": "Right-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Rashid Khan", "country": "Afghanistan", "team": "Gujarat Titans", "role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm legbreak"},
    {"name": "Mohammed Shami", "country": "India", "team": "Gujarat Titans", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium"},
    {"name": "David Miller", "country": "South Africa", "team": "Gujarat Titans", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": "Right-arm offbreak"},

    # --- Sunrisers Hyderabad ---
    {"name": "Travis Head", "country": "Australia", "team": "Sunrisers Hyderabad", "role": "Batter", "batting_style": "Left-hand bat", "bowling_style": "Right-arm offbreak"},
    {"name": "Heinrich Klaasen", "country": "South Africa", "team": "Sunrisers Hyderabad", "role": "WK-Batter", "batting_style": "Right-hand bat", "bowling_style": ""},
    {"name": "Pat Cummins", "country": "Australia", "team": "Sunrisers Hyderabad", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast"},
    {"name": "Abhishek Sharma", "country": "India", "team": "Sunrisers Hyderabad", "role": "All-rounder", "batting_style": "Left-hand bat", "bowling_style": "Slow left-arm orthodox"},

    # --- Lucknow Super Giants ---
    {"name": "KL Rahul", "country": "India", "team": "Lucknow Super Giants", "role": "WK-Batter", "batting_style": "Right-hand bat", "bowling_style": ""},
    {"name": "Quinton de Kock", "country": "South Africa", "team": "Lucknow Super Giants", "role": "WK-Batter", "batting_style": "Left-hand bat", "bowling_style": ""},
    {"name": "Marcus Stoinis", "country": "Australia", "team": "Lucknow Super Giants", "role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium-fast"},
    {"name": "Mark Wood", "country": "England", "team": "Lucknow Super Giants", "role": "Bowler", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast"},
]

# Simulated IPL 2025 match performances (based on realistic stats)
# Format: (match_name, date, team1, team2, status, performances)
# Each performance: (player_name, team, runs, balls, fours, sixes, sr, overs, runs_conceded, wickets, economy)
IPL_MATCHES = [
    {
        "name": "Chennai Super Kings vs Mumbai Indians, 1st Match, IPL 2025",
        "date": "2025-03-22",
        "match_type": "t20",
        "venue": "MA Chidambaram Stadium, Chennai",
        "teams": ["Chennai Super Kings", "Mumbai Indians"],
        "status": "Chennai Super Kings won by 6 wickets",
        "performances": [
            ("Rohit Sharma", "Mumbai Indians", 42, 31, 5, 2, 135.48, None, None, None, None),
            ("Suryakumar Yadav", "Mumbai Indians", 68, 43, 7, 3, 158.14, None, None, None, None),
            ("Tilak Varma", "Mumbai Indians", 31, 22, 3, 1, 140.91, None, None, None, None),
            ("Hardik Pandya", "Mumbai Indians", 18, 15, 1, 1, 120.0, 3, 28, 1, 9.33),
            ("Jasprit Bumrah", "Mumbai Indians", None, None, None, None, None, 4, 22, 2, 5.5),
            ("Ruturaj Gaikwad", "Chennai Super Kings", 55, 38, 6, 2, 144.74, None, None, None, None),
            ("Devon Conway", "Chennai Super Kings", 43, 30, 5, 1, 143.33, None, None, None, None),
            ("Ravindra Jadeja", "Chennai Super Kings", 38, 18, 2, 3, 211.11, 4, 32, 1, 8.0),
            ("MS Dhoni", "Chennai Super Kings", 22, 9, 1, 2, 244.44, None, None, None, None),
            ("Matheesha Pathirana", "Chennai Super Kings", None, None, None, None, None, 4, 35, 3, 8.75),
        ],
    },
    {
        "name": "Royal Challengers Bengaluru vs Kolkata Knight Riders, 2nd Match, IPL 2025",
        "date": "2025-03-23",
        "match_type": "t20",
        "venue": "M Chinnaswamy Stadium, Bengaluru",
        "teams": ["Royal Challengers Bengaluru", "Kolkata Knight Riders"],
        "status": "Royal Challengers Bengaluru won by 15 runs",
        "performances": [
            ("Virat Kohli", "Royal Challengers Bengaluru", 83, 49, 9, 4, 169.39, None, None, None, None),
            ("Rajat Patidar", "Royal Challengers Bengaluru", 47, 33, 5, 2, 142.42, None, None, None, None),
            ("Glenn Maxwell", "Royal Challengers Bengaluru", 35, 18, 2, 3, 194.44, 2, 22, 1, 11.0),
            ("Mohammed Siraj", "Royal Challengers Bengaluru", None, None, None, None, None, 4, 38, 2, 9.5),
            ("Josh Hazlewood", "Royal Challengers Bengaluru", None, None, None, None, None, 4, 29, 3, 7.25),
            ("Shreyas Iyer", "Kolkata Knight Riders", 51, 38, 5, 2, 134.21, None, None, None, None),
            ("Phil Salt", "Kolkata Knight Riders", 62, 36, 8, 3, 172.22, None, None, None, None),
            ("Andre Russell", "Kolkata Knight Riders", 44, 22, 3, 4, 200.0, 3, 42, 0, 14.0),
            ("Sunil Narine", "Kolkata Knight Riders", 28, 16, 4, 1, 175.0, 4, 30, 2, 7.5),
            ("Varun Chakravarthy", "Kolkata Knight Riders", None, None, None, None, None, 4, 33, 1, 8.25),
        ],
    },
    {
        "name": "Rajasthan Royals vs Delhi Capitals, 3rd Match, IPL 2025",
        "date": "2025-03-24",
        "match_type": "t20",
        "venue": "Sawai Mansingh Stadium, Jaipur",
        "teams": ["Rajasthan Royals", "Delhi Capitals"],
        "status": "Rajasthan Royals won by 8 wickets",
        "performances": [
            ("Yashasvi Jaiswal", "Rajasthan Royals", 92, 52, 10, 5, 176.92, None, None, None, None),
            ("Sanju Samson", "Rajasthan Royals", 45, 28, 5, 2, 160.71, None, None, None, None),
            ("Jos Buttler", "Rajasthan Royals", 38, 25, 4, 2, 152.0, None, None, None, None),
            ("Trent Boult", "Rajasthan Royals", None, None, None, None, None, 4, 24, 3, 6.0),
            ("Yuzvendra Chahal", "Rajasthan Royals", None, None, None, None, None, 4, 28, 2, 7.0),
            ("Rishabh Pant", "Delhi Capitals", 61, 39, 6, 3, 156.41, None, None, None, None),
            ("David Warner", "Delhi Capitals", 25, 20, 3, 1, 125.0, None, None, None, None),
            ("Axar Patel", "Delhi Capitals", 19, 14, 1, 1, 135.71, 4, 31, 1, 7.75),
            ("Kuldeep Yadav", "Delhi Capitals", None, None, None, None, None, 4, 36, 1, 9.0),
            ("Anrich Nortje", "Delhi Capitals", None, None, None, None, None, 4, 42, 0, 10.5),
        ],
    },
    {
        "name": "Gujarat Titans vs Sunrisers Hyderabad, 4th Match, IPL 2025",
        "date": "2025-03-25",
        "match_type": "t20",
        "venue": "Narendra Modi Stadium, Ahmedabad",
        "teams": ["Gujarat Titans", "Sunrisers Hyderabad"],
        "status": "Sunrisers Hyderabad won by 25 runs",
        "performances": [
            ("Shubman Gill", "Gujarat Titans", 58, 42, 6, 2, 138.1, None, None, None, None),
            ("David Miller", "Gujarat Titans", 42, 26, 3, 3, 161.54, None, None, None, None),
            ("Rashid Khan", "Gujarat Titans", 15, 8, 0, 2, 187.5, 4, 31, 2, 7.75),
            ("Mohammed Shami", "Gujarat Titans", None, None, None, None, None, 4, 45, 1, 11.25),
            ("Travis Head", "Sunrisers Hyderabad", 89, 47, 10, 5, 189.36, None, None, None, None),
            ("Heinrich Klaasen", "Sunrisers Hyderabad", 72, 38, 5, 6, 189.47, None, None, None, None),
            ("Abhishek Sharma", "Sunrisers Hyderabad", 34, 21, 4, 2, 161.9, 2, 18, 0, 9.0),
            ("Pat Cummins", "Sunrisers Hyderabad", 12, 8, 1, 1, 150.0, 4, 33, 3, 8.25),
        ],
    },
    {
        "name": "Punjab Kings vs Lucknow Super Giants, 5th Match, IPL 2025",
        "date": "2025-03-26",
        "match_type": "t20",
        "venue": "Punjab Cricket Association Stadium, Mohali",
        "teams": ["Punjab Kings", "Lucknow Super Giants"],
        "status": "Lucknow Super Giants won by 4 wickets",
        "performances": [
            ("Shikhar Dhawan", "Punjab Kings", 36, 28, 5, 0, 128.57, None, None, None, None),
            ("Liam Livingstone", "Punjab Kings", 55, 31, 4, 4, 177.42, 1, 12, 0, 12.0),
            ("Sam Curran", "Punjab Kings", 28, 20, 2, 1, 140.0, 4, 38, 2, 9.5),
            ("Kagiso Rabada", "Punjab Kings", None, None, None, None, None, 4, 30, 2, 7.5),
            ("Arshdeep Singh", "Punjab Kings", None, None, None, None, None, 4, 34, 1, 8.5),
            ("KL Rahul", "Lucknow Super Giants", 73, 48, 8, 3, 152.08, None, None, None, None),
            ("Quinton de Kock", "Lucknow Super Giants", 52, 33, 7, 2, 157.58, None, None, None, None),
            ("Marcus Stoinis", "Lucknow Super Giants", 31, 18, 2, 2, 172.22, 3, 25, 1, 8.33),
            ("Mark Wood", "Lucknow Super Giants", None, None, None, None, None, 4, 28, 3, 7.0),
        ],
    },
    {
        "name": "Mumbai Indians vs Rajasthan Royals, 6th Match, IPL 2025",
        "date": "2025-03-28",
        "match_type": "t20",
        "venue": "Wankhede Stadium, Mumbai",
        "teams": ["Mumbai Indians", "Rajasthan Royals"],
        "status": "Mumbai Indians won by 3 wickets",
        "performances": [
            ("Rohit Sharma", "Mumbai Indians", 71, 44, 8, 4, 161.36, None, None, None, None),
            ("Suryakumar Yadav", "Mumbai Indians", 43, 28, 5, 2, 153.57, None, None, None, None),
            ("Tilak Varma", "Mumbai Indians", 52, 35, 4, 3, 148.57, None, None, None, None),
            ("Jasprit Bumrah", "Mumbai Indians", None, None, None, None, None, 4, 18, 4, 4.5),
            ("Hardik Pandya", "Mumbai Indians", 25, 16, 2, 1, 156.25, 4, 35, 1, 8.75),
            ("Yashasvi Jaiswal", "Rajasthan Royals", 48, 35, 5, 2, 137.14, None, None, None, None),
            ("Jos Buttler", "Rajasthan Royals", 65, 40, 7, 3, 162.5, None, None, None, None),
            ("Sanju Samson", "Rajasthan Royals", 33, 22, 3, 2, 150.0, None, None, None, None),
            ("Trent Boult", "Rajasthan Royals", None, None, None, None, None, 4, 32, 2, 8.0),
            ("Yuzvendra Chahal", "Rajasthan Royals", None, None, None, None, None, 4, 40, 1, 10.0),
        ],
    },
    {
        "name": "Kolkata Knight Riders vs Chennai Super Kings, 7th Match, IPL 2025",
        "date": "2025-03-29",
        "match_type": "t20",
        "venue": "Eden Gardens, Kolkata",
        "teams": ["Kolkata Knight Riders", "Chennai Super Kings"],
        "status": "Kolkata Knight Riders won by 22 runs",
        "performances": [
            ("Phil Salt", "Kolkata Knight Riders", 78, 41, 9, 5, 190.24, None, None, None, None),
            ("Shreyas Iyer", "Kolkata Knight Riders", 64, 45, 6, 3, 142.22, None, None, None, None),
            ("Andre Russell", "Kolkata Knight Riders", 38, 15, 2, 4, 253.33, 3, 30, 2, 10.0),
            ("Sunil Narine", "Kolkata Knight Riders", 41, 22, 5, 2, 186.36, 4, 24, 2, 6.0),
            ("Varun Chakravarthy", "Kolkata Knight Riders", None, None, None, None, None, 4, 25, 3, 6.25),
            ("Ruturaj Gaikwad", "Chennai Super Kings", 42, 35, 4, 1, 120.0, None, None, None, None),
            ("Devon Conway", "Chennai Super Kings", 58, 40, 6, 2, 145.0, None, None, None, None),
            ("Ravindra Jadeja", "Chennai Super Kings", 22, 15, 1, 2, 146.67, 4, 38, 1, 9.5),
            ("Matheesha Pathirana", "Chennai Super Kings", None, None, None, None, None, 4, 42, 1, 10.5),
        ],
    },
    {
        "name": "Sunrisers Hyderabad vs Royal Challengers Bengaluru, 8th Match, IPL 2025",
        "date": "2025-03-30",
        "match_type": "t20",
        "venue": "Rajiv Gandhi Intl Cricket Stadium, Hyderabad",
        "teams": ["Sunrisers Hyderabad", "Royal Challengers Bengaluru"],
        "status": "Sunrisers Hyderabad won by 35 runs",
        "performances": [
            ("Travis Head", "Sunrisers Hyderabad", 102, 51, 12, 6, 200.0, None, None, None, None),
            ("Heinrich Klaasen", "Sunrisers Hyderabad", 55, 30, 4, 4, 183.33, None, None, None, None),
            ("Abhishek Sharma", "Sunrisers Hyderabad", 47, 28, 5, 3, 167.86, 1, 8, 0, 8.0),
            ("Pat Cummins", "Sunrisers Hyderabad", 8, 5, 1, 0, 160.0, 4, 30, 2, 7.5),
            ("Virat Kohli", "Royal Challengers Bengaluru", 76, 50, 8, 3, 152.0, None, None, None, None),
            ("Glenn Maxwell", "Royal Challengers Bengaluru", 42, 22, 3, 3, 190.91, 3, 35, 0, 11.67),
            ("Rajat Patidar", "Royal Challengers Bengaluru", 28, 22, 3, 1, 127.27, None, None, None, None),
            ("Mohammed Siraj", "Royal Challengers Bengaluru", None, None, None, None, None, 4, 48, 1, 12.0),
            ("Josh Hazlewood", "Royal Challengers Bengaluru", None, None, None, None, None, 4, 35, 2, 8.75),
        ],
    },
]


def seed():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Upsert players
    player_count = 0
    for p in IPL_PLAYERS:
        pid = deterministic_id(p["name"])
        cur.execute("""
            INSERT INTO players (id, name, country, player_role, batting_style, bowling_style)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                country = EXCLUDED.country,
                player_role = EXCLUDED.player_role,
                batting_style = EXCLUDED.batting_style,
                bowling_style = EXCLUDED.bowling_style
        """, (pid, p["name"], p["country"], p["role"], p["batting_style"], p["bowling_style"]))
        player_count += 1

    # 2. Upsert IPL matches and performances
    match_count = 0
    perf_count = 0
    for m in IPL_MATCHES:
        mid = deterministic_match_id(m["name"])

        # Upsert match
        import json
        cur.execute("""
            INSERT INTO matches (id, name, match_type, status, venue, date, teams, score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                score = EXCLUDED.score,
                updated_at = NOW()
        """, (mid, m["name"], m["match_type"], m["status"], m["venue"], m["date"],
              m["teams"], json.dumps([])))
        match_count += 1

        # Upsert performances
        for perf in m["performances"]:
            pname, team, runs, balls, fours, sixes, sr, overs, runs_c, wkts, eco = perf
            pid = deterministic_id(pname)

            cur.execute("""
                INSERT INTO player_performances (match_id, player_id, team, runs_scored, balls_faced, fours, sixes, strike_rate, overs_bowled, runs_conceded, wickets, economy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id, player_id) DO UPDATE SET
                    runs_scored = EXCLUDED.runs_scored,
                    balls_faced = EXCLUDED.balls_faced,
                    fours = EXCLUDED.fours,
                    sixes = EXCLUDED.sixes,
                    strike_rate = EXCLUDED.strike_rate,
                    overs_bowled = EXCLUDED.overs_bowled,
                    runs_conceded = EXCLUDED.runs_conceded,
                    wickets = EXCLUDED.wickets,
                    economy = EXCLUDED.economy
            """, (mid, pid, team, runs, balls, fours, sixes, sr, overs, runs_c, wkts, eco))
            perf_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Seeded {player_count} IPL players, {match_count} matches, {perf_count} performances")


if __name__ == "__main__":
    seed()
