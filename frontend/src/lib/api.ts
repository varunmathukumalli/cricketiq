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
