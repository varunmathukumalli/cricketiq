"""
ipl_seed.py — Seed IPL 2026 team and squad data into the database.

Run: cd src && python ipl_seed.py

Only seeds men's IPL players. WPL (Women's Premier League) players are
excluded — they belong to a separate competition and schema.
"""
import psycopg2
import psycopg2.extras
import os
import sys
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ──────────────────────────────────────────────────────────────────────────
# IPL 2026 — 10 franchises
# ──────────────────────────────────────────────────────────────────────────
IPL_TEAMS = [
    {
        "id": "mi",
        "name": "Mumbai Indians",
        "short_name": "MI",
        "home_ground": "Wankhede Stadium",
        "city": "Mumbai",
        "primary_color": "#004BA0",
        "secondary_color": "#D1AB3E",
    },
    {
        "id": "csk",
        "name": "Chennai Super Kings",
        "short_name": "CSK",
        "home_ground": "MA Chidambaram Stadium",
        "city": "Chennai",
        "primary_color": "#F9CD05",
        "secondary_color": "#0081E9",
    },
    {
        "id": "rcb",
        "name": "Royal Challengers Bengaluru",
        "short_name": "RCB",
        "home_ground": "M Chinnaswamy Stadium",
        "city": "Bengaluru",
        "primary_color": "#EC1C24",
        "secondary_color": "#000000",
    },
    {
        "id": "kkr",
        "name": "Kolkata Knight Riders",
        "short_name": "KKR",
        "home_ground": "Eden Gardens",
        "city": "Kolkata",
        "primary_color": "#3A225D",
        "secondary_color": "#B3A123",
    },
    {
        "id": "dc",
        "name": "Delhi Capitals",
        "short_name": "DC",
        "home_ground": "Arun Jaitley Stadium",
        "city": "Delhi",
        "primary_color": "#17479E",
        "secondary_color": "#EF1C25",
    },
    {
        "id": "pbks",
        "name": "Punjab Kings",
        "short_name": "PBKS",
        "home_ground": "Punjab Cricket Association Stadium",
        "city": "Mohali",
        "primary_color": "#ED1B24",
        "secondary_color": "#A7A9AC",
    },
    {
        "id": "rr",
        "name": "Rajasthan Royals",
        "short_name": "RR",
        "home_ground": "Sawai Mansingh Stadium",
        "city": "Jaipur",
        "primary_color": "#254AA5",
        "secondary_color": "#E8205C",
    },
    {
        "id": "srh",
        "name": "Sunrisers Hyderabad",
        "short_name": "SRH",
        "home_ground": "Rajiv Gandhi International Stadium",
        "city": "Hyderabad",
        "primary_color": "#F26522",
        "secondary_color": "#000000",
    },
    {
        "id": "gt",
        "name": "Gujarat Titans",
        "short_name": "GT",
        "home_ground": "Narendra Modi Stadium",
        "city": "Ahmedabad",
        "primary_color": "#1C1C4E",
        "secondary_color": "#C8A951",
    },
    {
        "id": "lsg",
        "name": "Lucknow Super Giants",
        "short_name": "LSG",
        "home_ground": "BRSABV Ekana Cricket Stadium",
        "city": "Lucknow",
        "primary_color": "#A72056",
        "secondary_color": "#FBCA09",
    },
]

# ──────────────────────────────────────────────────────────────────────────
# IPL 2026 squads are fetched LIVE from the CricData API at seed time.
# No hardcoded player data — avoids stale/incorrect rosters.
# ──────────────────────────────────────────────────────────────────────────
_REMOVED_HARDCODED_SQUADS = {  # Kept as comment reference only
    "mi": [
        {"player_name": "Rohit Sharma",      "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Suryakumar Yadav",  "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Hardik Pandya",     "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Tilak Varma",       "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Jasprit Bumrah",    "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "India",       "is_overseas": False},
        {"player_name": "Ishan Kishan",      "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Naman Dhir",        "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Tim David",         "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "Singapore",   "is_overseas": True},
        {"player_name": "Trent Boult",       "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium",   "nationality": "New Zealand", "is_overseas": True},
        {"player_name": "Ryan Rickelton",    "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "South Africa","is_overseas": True},
        {"player_name": "Corbin Bosch",      "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "South Africa","is_overseas": True},
        {"player_name": "Will Jacks",        "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "England",     "is_overseas": True},
        {"player_name": "Ashwini Kumar",     "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "India",       "is_overseas": False},
        {"player_name": "Reece Topley",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium",   "nationality": "England",     "is_overseas": True},
        {"player_name": "Deepak Chahar",     "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
    ],
    "csk": [
        {"player_name": "MS Dhoni",          "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Ruturaj Gaikwad",   "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Shivam Dube",       "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Ravindra Jadeja",   "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "Matheesha Pathirana","player_role": "Bowler",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "Sri Lanka",   "is_overseas": True},
        {"player_name": "Devon Conway",      "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "New Zealand", "is_overseas": True},
        {"player_name": "Rachin Ravindra",   "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "New Zealand", "is_overseas": True},
        {"player_name": "Sam Curran",        "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm fast-medium",   "nationality": "England",     "is_overseas": True},
        {"player_name": "Tushar Deshpande",  "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Khaleel Ahmed",     "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium",   "nationality": "India",       "is_overseas": False},
        {"player_name": "Shardul Thakur",    "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Ajinkya Rahane",    "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Noor Ahmad",        "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm wrist-spin",    "nationality": "Afghanistan", "is_overseas": True},
        {"player_name": "Moeen Ali",         "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "England",     "is_overseas": True},
    ],
    "rcb": [
        {"player_name": "Virat Kohli",       "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Rajat Patidar",     "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Krunal Pandya",     "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "Mohammed Siraj",    "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Yash Dayal",        "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium",   "nationality": "India",       "is_overseas": False},
        {"player_name": "Phil Salt",         "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "England",     "is_overseas": True},
        {"player_name": "Josh Hazlewood",    "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Liam Livingstone",  "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "England",     "is_overseas": True},
        {"player_name": "Swapnil Singh",     "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "Suyash Prabhudessai","player_role": "Batsman",    "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Lockie Ferguson",   "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "New Zealand", "is_overseas": True},
        {"player_name": "Tim Southee",       "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "New Zealand", "is_overseas": True},
    ],
    "kkr": [
        {"player_name": "Rinku Singh",       "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Venkatesh Iyer",    "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Varun Chakaravarthy","player_role": "Bowler",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm wrist-spin",   "nationality": "India",       "is_overseas": False},
        {"player_name": "Harshit Rana",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "India",       "is_overseas": False},
        {"player_name": "Angkrish Raghuvanshi","player_role": "Batsman",   "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Sunil Narine",      "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Right-arm off-break",    "nationality": "West Indies", "is_overseas": True},
        {"player_name": "Andre Russell",     "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "West Indies", "is_overseas": True},
        {"player_name": "Quinton de Kock",   "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "South Africa","is_overseas": True},
        {"player_name": "Spencer Johnson",   "player_role": "Bowler",      "batting_style": "Left-hand bat",  "bowling_style": "Left-arm fast",          "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Moeen Ali",         "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "England",     "is_overseas": True},
        {"player_name": "Ajinkya Rahane",    "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Manish Pandey",     "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
    ],
    "dc": [
        {"player_name": "KL Rahul",          "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Jake Fraser-McGurk","player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Axar Patel",        "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "Kuldeep Yadav",     "player_role": "Bowler",      "batting_style": "Left-hand bat",  "bowling_style": "Left-arm wrist-spin",    "nationality": "India",       "is_overseas": False},
        {"player_name": "T Natarajan",       "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium",   "nationality": "India",       "is_overseas": False},
        {"player_name": "Tristan Stubbs",    "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "South Africa","is_overseas": True},
        {"player_name": "Faf du Plessis",    "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "South Africa","is_overseas": True},
        {"player_name": "Abhishek Porel",    "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Ashutosh Sharma",   "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Mohit Sharma",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Darshan Nalkande",  "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Donovan Ferreira",  "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "South Africa","is_overseas": True},
    ],
    "pbks": [
        {"player_name": "Shikhar Dhawan",    "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Prabhsimran Singh", "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Arshdeep Singh",    "player_role": "Bowler",      "batting_style": "Left-hand bat",  "bowling_style": "Left-arm fast-medium",   "nationality": "India",       "is_overseas": False},
        {"player_name": "Harshal Patel",     "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Yuzvendra Chahal",  "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Glenn Maxwell",     "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Kagiso Rabada",     "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "South Africa","is_overseas": True},
        {"player_name": "Rilee Rossouw",     "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm off-break",    "nationality": "South Africa","is_overseas": True},
        {"player_name": "Shashank Singh",    "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Ravi Bishnoi",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Azmatullah Omarzai","player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "Afghanistan", "is_overseas": True},
        {"player_name": "Shreyas Iyer",      "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
    ],
    "rr": [
        {"player_name": "Sanju Samson",      "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Riyan Parag",       "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Dhruv Jurel",       "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Sandeep Sharma",    "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Jos Buttler",       "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "England",     "is_overseas": True},
        {"player_name": "Shimron Hetmyer",   "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "West Indies", "is_overseas": True},
        {"player_name": "Jofra Archer",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "England",     "is_overseas": True},
        {"player_name": "Wanindu Hasaranga", "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "Sri Lanka",   "is_overseas": True},
        {"player_name": "Yashasvi Jaiswal",  "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Ravichandran Ashwin","player_role": "All-rounder","batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Avesh Khan",        "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "India",       "is_overseas": False},
        {"player_name": "Maheesh Theekshana","player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "Sri Lanka",   "is_overseas": True},
    ],
    "srh": [
        {"player_name": "Travis Head",       "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm off-break",    "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Abhishek Sharma",   "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "Heinrich Klaasen",  "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "South Africa","is_overseas": True},
        {"player_name": "Pat Cummins",       "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "Australia",   "is_overseas": True},
        # Pakistan players are banned from IPL — Shaheen Shah Afridi removed
        {"player_name": "Nitish Kumar Reddy","player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Rahul Tripathi",    "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Jaydev Unadkat",    "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm fast-medium",   "nationality": "India",       "is_overseas": False},
        {"player_name": "Adam Zampa",        "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Ishan Kishan",      "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
        {"player_name": "Simarjeet Singh",   "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "India",       "is_overseas": False},
    ],
    "gt": [
        {"player_name": "Shubman Gill",      "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Sai Sudharsan",     "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "David Miller",      "player_role": "Batsman",     "batting_style": "Left-hand bat",  "bowling_style": "Right-arm medium",       "nationality": "South Africa","is_overseas": True},
        {"player_name": "Rashid Khan",       "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "Afghanistan", "is_overseas": True},
        {"player_name": "Mohammed Shami",    "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Shahrukh Khan",     "player_role": "Batsman",     "batting_style": "Right-hand bat", "bowling_style": "Right-arm medium",       "nationality": "India",       "is_overseas": False},
        {"player_name": "Rahul Tewatia",     "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Right-arm leg-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Noor Ahmad",        "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Left-arm wrist-spin",    "nationality": "Afghanistan", "is_overseas": True},
        {"player_name": "Jos Buttler",       "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "England",     "is_overseas": True},
        {"player_name": "Azmatullah Omarzai","player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "Afghanistan", "is_overseas": True},
        {"player_name": "Arshad Khan",       "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "India",       "is_overseas": False},
        {"player_name": "Wriddhiman Saha",   "player_role": "WK-Batsman",  "batting_style": "Right-hand bat", "bowling_style": None,                     "nationality": "India",       "is_overseas": False},
    ],
    "lsg": [
        {"player_name": "Nicholas Pooran",   "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "West Indies", "is_overseas": True},
        {"player_name": "Ravi Bishnoi",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm leg-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Marcus Stoinis",    "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Deepak Hooda",      "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Mark Wood",         "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "England",     "is_overseas": True},
        {"player_name": "Quinton de Kock",   "player_role": "WK-Batsman",  "batting_style": "Left-hand bat",  "bowling_style": None,                     "nationality": "South Africa","is_overseas": True},
        {"player_name": "Mayank Yadav",      "player_role": "Bowler",      "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast",         "nationality": "India",       "is_overseas": False},
        {"player_name": "Mohsin Khan",       "player_role": "Bowler",      "batting_style": "Left-hand bat",  "bowling_style": "Left-arm fast",          "nationality": "India",       "is_overseas": False},
        {"player_name": "Ayush Badoni",      "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm off-break",    "nationality": "India",       "is_overseas": False},
        {"player_name": "Krunal Pandya",     "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
        {"player_name": "Mitchell Marsh",    "player_role": "All-rounder", "batting_style": "Right-hand bat", "bowling_style": "Right-arm fast-medium",  "nationality": "Australia",   "is_overseas": True},
        {"player_name": "Prerak Mankad",     "player_role": "All-rounder", "batting_style": "Left-hand bat",  "bowling_style": "Left-arm orthodox",      "nationality": "India",       "is_overseas": False},
    ],
}


def seed_database():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    print("Seeding IPL teams...")
    for team in IPL_TEAMS:
        cur.execute("""
            INSERT INTO ipl_teams (id, name, short_name, home_ground, city, primary_color, secondary_color)
            VALUES (%(id)s, %(name)s, %(short_name)s, %(home_ground)s, %(city)s, %(primary_color)s, %(secondary_color)s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                short_name = EXCLUDED.short_name,
                home_ground = EXCLUDED.home_ground,
                city = EXCLUDED.city,
                primary_color = EXCLUDED.primary_color,
                secondary_color = EXCLUDED.secondary_color
        """, team)
    print(f"  ✓ {len(IPL_TEAMS)} teams seeded")

    # Fetch REAL squads from CricData API (not hardcoded data)
    print("Fetching IPL 2026 squads from CricData API...")
    import requests
    CRICKET_API_KEY = os.getenv("CRICKET_API_KEY")
    IPL_2026_SERIES_ID = "87c62aac-bc3c-4738-ab93-19da0690488f"

    url = f"https://api.cricapi.com/v1/series_squad?apikey={CRICKET_API_KEY}&id={IPL_2026_SERIES_ID}"
    resp = requests.get(url, timeout=15)
    api_data = resp.json()

    if api_data.get("status") != "success":
        print(f"  ERROR: API failed — {api_data.get('reason', 'unknown')}")
        print("  Skipping squad seeding. Fix API key or try again later.")
        conn.commit()
        cur.close()
        conn.close()
        return

    TEAM_ID_MAP = {
        "CSK": "csk", "DC": "dc", "GT": "gt", "RCB": "rcb", "RCBW": "rcb",
        "PBKS": "pbks", "KKR": "kkr", "SRH": "srh", "RR": "rr",
        "LSG": "lsg", "MI": "mi",
    }
    ROLE_MAP = {
        "Batsman": "Batsman", "Batter": "Batsman", "Top order Batter": "Batsman",
        "Middle order Batter": "Batsman", "Opening Batter": "Batsman",
        "Bowler": "Bowler",
        "Bowling Allrounder": "All-rounder", "Batting Allrounder": "All-rounder",
        "Allrounder": "All-rounder",
        "WK-Batsman": "WK-Batsman", "Wicketkeeper Batter": "WK-Batsman",
        "WK-Batter": "WK-Batsman", "Keeper Batter": "WK-Batsman",
    }
    OVERSEAS_COUNTRIES = {
        "Afghanistan", "Australia", "England", "New Zealand", "South Africa",
        "Sri Lanka", "West Indies", "Zimbabwe", "Bangladesh", "Ireland",
        "Scotland", "Netherlands",
    }

    # Clear old squad data first
    cur.execute("DELETE FROM ipl_squad WHERE season = 2026")

    total_players = 0
    for team in api_data.get("data", []):
        short = team.get("shortname", "")
        team_id = TEAM_ID_MAP.get(short, short.lower())

        for p in team.get("players", []):
            raw_role = p.get("role", "Batsman")
            role = ROLE_MAP.get(raw_role, raw_role)
            if role not in ("Batsman", "Bowler", "All-rounder", "WK-Batsman"):
                if "allrounder" in role.lower() or "all" in role.lower():
                    role = "All-rounder"
                elif "bowl" in role.lower():
                    role = "Bowler"
                elif "keep" in role.lower() or "wk" in role.lower():
                    role = "WK-Batsman"
                else:
                    role = "Batsman"

            country = p.get("country", "India")
            cur.execute("""
                INSERT INTO ipl_squad (team_id, player_name, player_role, batting_style, bowling_style, nationality, is_overseas, season)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 2026)
                ON CONFLICT (team_id, player_name, season) DO UPDATE SET
                    player_role = EXCLUDED.player_role,
                    batting_style = EXCLUDED.batting_style,
                    bowling_style = EXCLUDED.bowling_style,
                    nationality = EXCLUDED.nationality,
                    is_overseas = EXCLUDED.is_overseas
            """, (team_id, p.get("name"), role, p.get("battingStyle"), p.get("bowlingStyle"),
                  country, country in OVERSEAS_COUNTRIES))
            total_players += 1
        print(f"  ✓ {team_id.upper()}: {len(team.get('players', []))} players")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. {total_players} IPL 2026 players seeded from CricData API.")


if __name__ == "__main__":
    seed_database()
