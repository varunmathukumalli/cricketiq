-- CricketIQ Database Schema
-- Run: psql cricketiq -f src/schema.sql

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    match_type TEXT,
    status TEXT,
    venue TEXT,
    date TIMESTAMP,
    teams TEXT[],
    score JSONB,
    api_response JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    date_of_birth TEXT,
    player_role TEXT,
    batting_style TEXT,
    bowling_style TEXT,
    api_response JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_performances (
    id SERIAL PRIMARY KEY,
    match_id TEXT REFERENCES matches(id),
    player_id TEXT REFERENCES players(id),
    team TEXT,
    runs_scored INTEGER,
    balls_faced INTEGER,
    fours INTEGER,
    sixes INTEGER,
    strike_rate DECIMAL,
    overs_bowled DECIMAL,
    runs_conceded INTEGER,
    wickets INTEGER,
    economy DECIMAL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(match_id, player_id)
);

CREATE TABLE IF NOT EXISTS venues (
    name TEXT PRIMARY KEY,
    city TEXT,
    country TEXT,
    latitude DECIMAL,
    longitude DECIMAL
);

CREATE TABLE IF NOT EXISTS match_weather (
    id SERIAL PRIMARY KEY,
    match_id TEXT REFERENCES matches(id),
    temperature DECIMAL,
    humidity INTEGER,
    wind_speed DECIMAL,
    precipitation DECIMAL,
    dew_point DECIMAL,
    weather_code INTEGER,
    weather_summary TEXT,          -- Agent's analysis of cricket impact
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(match_id)
);

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    match_id TEXT REFERENCES matches(id),
    team_a TEXT,
    team_b TEXT,
    team_a_win_prob DECIMAL,
    team_b_win_prob DECIMAL,
    explanation TEXT,              -- Explainer agent's output
    model_version TEXT,
    predicted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(match_id, model_version)
);

CREATE TABLE IF NOT EXISTS ai_reports (
    id SERIAL PRIMARY KEY,
    match_id TEXT REFERENCES matches(id),
    report_type TEXT,
    report_text TEXT,
    model_used TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    generated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(match_id, report_type)
);

-- Common venue coordinates
INSERT INTO venues (name, city, country, latitude, longitude) VALUES
    ('Wankhede Stadium', 'Mumbai', 'India', 18.9389, 72.8258),
    ('Eden Gardens', 'Kolkata', 'India', 22.5646, 88.3433),
    ('M Chinnaswamy Stadium', 'Bangalore', 'India', 12.9788, 77.5996),
    ('Melbourne Cricket Ground', 'Melbourne', 'Australia', -37.8200, 144.9834),
    ('Lords', 'London', 'England', 51.5294, -0.1727),
    ('Sydney Cricket Ground', 'Sydney', 'Australia', -33.8918, 151.2249),
    ('Arun Jaitley Stadium', 'Delhi', 'India', 28.6368, 77.2434),
    ('MA Chidambaram Stadium', 'Chennai', 'India', 13.0627, 80.2792)
ON CONFLICT (name) DO NOTHING;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_perf_match ON player_performances(match_id);
CREATE INDEX IF NOT EXISTS idx_perf_player ON player_performances(player_id);
