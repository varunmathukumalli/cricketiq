import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "https://cricketiq-production.up.railway.app",
  timeout: 10000,
});

export interface Match {
  id: string;
  name: string;
  match_type: string;
  status: string;
  venue: string;
  date: string;
}

export interface Prediction {
  match_id: string;
  match_name: string;
  team_a: string;
  team_b: string;
  team_a_win_prob: number;
  team_b_win_prob: number;
  explanation: string;
}

export interface Report {
  match_id: string;
  report_text: string;
  generated_at: string;
}

export interface CategorizedMatches {
  live: Match[];
  upcoming: Match[];
  completed: Match[];
  total: number;
}

export async function getMatches(limit = 50): Promise<CategorizedMatches> {
  const res = await api.get(`/matches?limit=${limit}`);
  return res.data;
}

export async function getMatch(id: string) {
  const res = await api.get(`/matches/${id}`);
  return res.data;
}

export async function getPredictions(): Promise<Prediction[]> {
  const res = await api.get("/predictions");
  return res.data.predictions;
}

export async function getPrediction(matchId: string): Promise<Prediction> {
  const res = await api.get(`/predictions/${matchId}`);
  return res.data;
}

export async function getReport(matchId: string): Promise<Report> {
  const res = await api.get(`/reports/${matchId}`);
  return res.data;
}

export async function getAgentStatus() {
  const res = await api.get("/agents/status");
  return res.data;
}

export async function triggerAgents() {
  const res = await api.post("/agents/run");
  return res.data;
}

export async function getAgentLastError(): Promise<{ error: string | null }> {
  const res = await api.get("/agents/last-error");
  return res.data;
}

// ── IPL 2026 Players ──────────────────────────────────────────────────────

export interface IPLTeam {
  id: string;
  name: string;
  short_name: string;
  home_ground: string;
  city: string;
  primary_color: string;
  secondary_color: string;
}

export interface IPLPlayer {
  id: number;
  player_name: string;
  player_role: "Batsman" | "Bowler" | "All-rounder" | "WK-Batsman";
  batting_style: string | null;
  bowling_style: string | null;
  nationality: string;
  is_overseas: boolean;
}

export interface IPLTeamSquad extends IPLTeam {
  players: IPLPlayer[];
}

export interface IPLPrediction {
  player_name: string;
  team_id: string;
  team_name: string;
  short_name: string;
  primary_color: string;
  category: string;
  predicted_runs: number | null;
  predicted_wickets: number | null;
  predicted_strike_rate: number | null;
  confidence: "High" | "Medium" | "Low";
  reasoning: string;
  generated_at: string;
}

export async function getIPLTeams(): Promise<IPLTeam[]> {
  const res = await api.get("/ipl/teams");
  return res.data.teams;
}

export async function getIPLPlayers(season = 2026): Promise<{ season: number; teams: IPLTeamSquad[] }> {
  const res = await api.get(`/ipl/players?season=${season}`);
  return res.data;
}

export async function getIPLPredictions(season = 2026): Promise<{ season: number; predictions: Record<string, IPLPrediction[]> }> {
  const res = await api.get(`/ipl/predictions?season=${season}`);
  return res.data;
}

export async function generateIPLPredictions(season = 2026) {
  const res = await api.post(`/ipl/predictions/generate?season=${season}`);
  return res.data;
}

// ── Player detail stats ───────────────────────────────────────────────────

export interface PlayerPerformance {
  match_name: string;
  match_date: string;
  team: string;
  runs_scored: number | null;
  balls_faced: number | null;
  fours: number | null;
  sixes: number | null;
  strike_rate: number | null;
  overs_bowled: number | null;
  wickets: number | null;
  economy: number | null;
}

export async function getPlayerStats(playerName: string) {
  const res = await api.get(`/ipl/player-stats/${encodeURIComponent(playerName)}`);
  return res.data;
}
