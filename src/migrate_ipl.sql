-- IPL 2026 Players Schema Migration
-- Run: psql cricketiq -f src/migrate_ipl.sql

-- IPL franchise teams
CREATE TABLE IF NOT EXISTS ipl_teams (
    id TEXT PRIMARY KEY,          -- e.g. 'mi', 'csk', 'rcb'
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    home_ground TEXT,
    city TEXT,
    primary_color TEXT DEFAULT '#10b981',
    secondary_color TEXT DEFAULT '#ffffff'
);

-- IPL 2026 squad (men's IPL only — no WPL players)
CREATE TABLE IF NOT EXISTS ipl_squad (
    id SERIAL PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES ipl_teams(id),
    player_name TEXT NOT NULL,
    player_role TEXT NOT NULL,    -- 'Batsman', 'Bowler', 'All-rounder', 'WK-Batsman'
    batting_style TEXT,           -- 'Right-hand bat', 'Left-hand bat'
    bowling_style TEXT,           -- e.g. 'Right-arm fast', 'Left-arm spin', etc.
    nationality TEXT NOT NULL,
    is_overseas BOOLEAN DEFAULT FALSE,
    season INTEGER NOT NULL DEFAULT 2026,
    UNIQUE(team_id, player_name, season)
);

-- AI-generated predictions for IPL 2026 season
CREATE TABLE IF NOT EXISTS player_season_predictions (
    id SERIAL PRIMARY KEY,
    season INTEGER NOT NULL DEFAULT 2026,
    player_name TEXT NOT NULL,
    team_id TEXT REFERENCES ipl_teams(id),
    category TEXT NOT NULL,       -- 'orange_cap', 'purple_cap', 'breakout'
    predicted_runs INTEGER,
    predicted_wickets INTEGER,
    predicted_strike_rate DECIMAL,
    confidence TEXT DEFAULT 'Medium',  -- 'High', 'Medium', 'Low'
    reasoning TEXT,
    generated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(player_name, season, category)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ipl_squad_team ON ipl_squad(team_id, season);
CREATE INDEX IF NOT EXISTS idx_ipl_squad_role ON ipl_squad(player_role);
CREATE INDEX IF NOT EXISTS idx_player_preds_season ON player_season_predictions(season, category);
