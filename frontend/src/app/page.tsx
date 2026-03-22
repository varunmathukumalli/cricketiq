"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMatches, getPredictions, getAgentStatus, triggerAgents, Match, Prediction } from "@/lib/api";

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [agentStatus, setAgentStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentRunning, setAgentRunning] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const [m, p, s] = await Promise.all([getMatches(20), getPredictions(), getAgentStatus()]);
        setMatches(m);
        setPredictions(p);
        setAgentStatus(s);
      } catch (err) {
        setError("Failed to connect. Is the FastAPI backend running on :8000?");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  function getPredForMatch(matchId: string) {
    return predictions.find((p) => p.match_id === matchId);
  }

  async function handleRunAgents() {
    setAgentRunning(true);
    try {
      await triggerAgents();
      setTimeout(async () => {
        const s = await getAgentStatus();
        setAgentStatus(s);
        setAgentRunning(false);
      }, 5000);
    } catch {
      setAgentRunning(false);
    }
  }

  if (loading) return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400 text-lg">Loading CricketIQ...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
      <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-8 max-w-md">
        <h2 className="text-red-400 font-bold text-xl mb-2">Connection Error</h2>
        <p className="text-red-300">{error}</p>
      </div>
    </div>
  );

  const statusLabels: Record<string, string> = {
    matches: "Matches",
    predictions: "Predictions",
    ai_reports: "AI Reports",
    match_weather: "Weather",
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center text-white font-bold text-lg">C</div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">CricketIQ</h1>
              <p className="text-xs text-slate-400">Multi-agent AI analytics</p>
            </div>
          </div>
          <button
            onClick={handleRunAgents}
            disabled={agentRunning}
            className="bg-emerald-600 text-white px-5 py-2.5 rounded-lg hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm font-medium flex items-center gap-2"
          >
            {agentRunning && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            {agentRunning ? "Agents running..." : "Run Agent Pipeline"}
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Agent Status Cards */}
        {agentStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {Object.entries(agentStatus.agent_data || {}).map(([key, val]) => (
              <div key={key} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                <p className="text-3xl font-bold text-white">{String(val)}</p>
                <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider">{statusLabels[key] || key}</p>
              </div>
            ))}
          </div>
        )}

        {/* Section Title */}
        <div className="flex items-center gap-3 mb-6">
          <h2 className="text-lg font-semibold text-white">Recent Matches</h2>
          <div className="flex-1 h-px bg-slate-700/50" />
          <span className="text-xs text-slate-500">{matches.length} matches</span>
        </div>

        {/* Match Cards */}
        {matches.length === 0 ? (
          <div className="text-center py-16 bg-slate-800/30 rounded-xl border border-slate-700/30">
            <p className="text-slate-400 text-lg mb-2">No matches yet</p>
            <p className="text-slate-500 text-sm">Click &ldquo;Run Agent Pipeline&rdquo; to fetch cricket data</p>
          </div>
        ) : (
          <div className="space-y-3">
            {matches.map((match) => {
              const pred = getPredForMatch(match.id);
              return (
                <Link key={match.id} href={`/match/${match.id}`}>
                  <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 hover:bg-slate-800 hover:border-emerald-500/30 transition-all cursor-pointer group">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 rounded-full">
                            {match.match_type}
                          </span>
                          <span className="text-xs text-slate-500">{match.date ? new Date(match.date).toLocaleDateString() : ""}</span>
                        </div>
                        <h3 className="text-white font-semibold group-hover:text-emerald-400 transition-colors">{match.name}</h3>
                        <p className="text-sm text-slate-400 mt-1">{match.venue}</p>
                        <p className="text-xs text-slate-500 mt-1">{match.status}</p>
                      </div>
                      {pred && (
                        <div className="text-right ml-6 min-w-[140px]">
                          <div className="space-y-2">
                            <div>
                              <div className="flex justify-between text-sm mb-1">
                                <span className="text-emerald-400 font-medium">{pred.team_a}</span>
                                <span className="text-emerald-400 font-bold">{(pred.team_a_win_prob * 100).toFixed(0)}%</span>
                              </div>
                              <div className="w-full h-1.5 bg-slate-700 rounded-full">
                                <div className="h-1.5 bg-emerald-500 rounded-full transition-all" style={{ width: `${pred.team_a_win_prob * 100}%` }} />
                              </div>
                            </div>
                            <div>
                              <div className="flex justify-between text-sm mb-1">
                                <span className="text-blue-400 font-medium">{pred.team_b}</span>
                                <span className="text-blue-400 font-bold">{(pred.team_b_win_prob * 100).toFixed(0)}%</span>
                              </div>
                              <div className="w-full h-1.5 bg-slate-700 rounded-full">
                                <div className="h-1.5 bg-blue-500 rounded-full transition-all" style={{ width: `${pred.team_b_win_prob * 100}%` }} />
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-700/50 mt-12">
        <div className="max-w-6xl mx-auto px-6 py-4 text-center text-xs text-slate-500">
          Powered by LangGraph + Gemini + GPT-4o + Claude Sonnet
        </div>
      </footer>
    </main>
  );
}
