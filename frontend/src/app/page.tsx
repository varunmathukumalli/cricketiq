"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMatches, getPredictions, getAgentStatus, triggerAgents, Match, Prediction, CategorizedMatches } from "@/lib/api";

export default function Home() {
  const [matchData, setMatchData] = useState<CategorizedMatches | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [agentStatus, setAgentStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentRunning, setAgentRunning] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const [m, p, s] = await Promise.all([getMatches(50), getPredictions(), getAgentStatus()]);
        setMatchData(m);
        setPredictions(p);
        setAgentStatus(s);
      } catch (err) {
        setError("Failed to connect to the API.");
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
        const [m, s] = await Promise.all([getMatches(50), getAgentStatus()]);
        setMatchData(m);
        setAgentStatus(s);
        setAgentRunning(false);
      }, 10000);
    } catch {
      setAgentRunning(false);
    }
  }

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="text-center">
        <div className="relative w-16 h-16 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-emerald-400 animate-spin" />
          <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-blue-400 animate-spin" style={{ animationDirection: "reverse", animationDuration: "1.5s" }} />
        </div>
        <p className="text-slate-500 text-sm tracking-widest uppercase">Loading CricketIQ</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="relative">
        <div className="absolute -inset-1 bg-red-500/20 rounded-2xl blur-xl" />
        <div className="relative bg-[#12121a] border border-red-500/30 rounded-2xl p-8 max-w-md">
          <h2 className="text-red-400 font-bold text-xl mb-2">Connection Error</h2>
          <p className="text-red-300/70">{error}</p>
        </div>
      </div>
    </div>
  );

  const statusConfig: Record<string, { label: string; icon: string; color: string }> = {
    matches: { label: "Matches", icon: "🏏", color: "from-emerald-500/20 to-emerald-500/5" },
    predictions: { label: "Predictions", icon: "📊", color: "from-blue-500/20 to-blue-500/5" },
    ai_reports: { label: "AI Reports", icon: "📝", color: "from-purple-500/20 to-purple-500/5" },
    match_weather: { label: "Weather", icon: "🌤", color: "from-amber-500/20 to-amber-500/5" },
  };

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Ambient background glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -left-40 w-80 h-80 bg-blue-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-72 h-72 bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative border-b border-white/5 bg-[#0a0a0f]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 py-5 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500 to-blue-500 rounded-xl opacity-50 blur group-hover:opacity-75 transition" />
              <div className="relative w-10 h-10 bg-[#0a0a0f] rounded-xl flex items-center justify-center border border-white/10">
                <span className="text-lg font-bold bg-gradient-to-r from-emerald-400 to-blue-400 bg-clip-text text-transparent">C</span>
              </div>
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">
                <span className="bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">CricketIQ</span>
              </h1>
              <p className="text-[11px] text-slate-500 tracking-wider uppercase">Multi-agent AI analytics</p>
            </div>
          </div>
          <button
            onClick={handleRunAgents}
            disabled={agentRunning}
            className="group relative px-5 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-xl opacity-90 group-hover:opacity-100 transition" />
            <div className="absolute inset-0 bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-xl blur-lg opacity-0 group-hover:opacity-40 transition" />
            <span className="relative flex items-center gap-2 text-white">
              {agentRunning && <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />}
              {agentRunning ? "Agents running..." : "Run Agent Pipeline"}
            </span>
          </button>
        </div>
      </header>

      <div className="relative max-w-6xl mx-auto px-6 py-10">
        {/* Stats Grid */}
        {agentStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            {Object.entries(agentStatus.agent_data || {}).map(([key, val]) => {
              const config = statusConfig[key] || { label: key, icon: "📦", color: "from-slate-500/20 to-slate-500/5" };
              return (
                <div key={key} className="group relative">
                  <div className="absolute -inset-px bg-gradient-to-b from-white/10 to-transparent rounded-2xl opacity-0 group-hover:opacity-100 transition duration-500" />
                  <div className={`relative bg-gradient-to-b ${config.color} border border-white/5 rounded-2xl p-5 text-center backdrop-blur-sm`}>
                    <p className="text-3xl mb-1">{config.icon}</p>
                    <p className="text-3xl font-bold text-white tabular-nums">{String(val)}</p>
                    <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest">{config.label}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Live Matches */}
        {matchData && matchData.live.length > 0 && (
          <MatchSection
            title="Live Now"
            accentColor="red"
            dotPulse
            matches={matchData.live}
            getPredForMatch={getPredForMatch}
          />
        )}

        {/* Upcoming Matches */}
        {matchData && matchData.upcoming.length > 0 && (
          <MatchSection
            title="Upcoming"
            accentColor="amber"
            matches={matchData.upcoming}
            getPredForMatch={getPredForMatch}
          />
        )}

        {/* Completed Matches */}
        {matchData && matchData.completed.length > 0 && (
          <MatchSection
            title="Completed"
            accentColor="slate"
            matches={matchData.completed}
            getPredForMatch={getPredForMatch}
          />
        )}

        {/* Empty State */}
        {matchData && matchData.total === 0 && (
          <div className="text-center py-20 border border-white/5 rounded-2xl bg-white/[0.02]">
            <p className="text-4xl mb-4">🏏</p>
            <p className="text-slate-400 text-lg mb-2">No matches yet</p>
            <p className="text-slate-600 text-sm">Click &ldquo;Run Agent Pipeline&rdquo; to fetch live cricket data</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="relative border-t border-white/5 mt-16">
        <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col md:flex-row justify-between items-center gap-3">
          <p className="text-[11px] text-slate-600">
            Powered by <span className="text-slate-500">LangGraph</span> + <span className="text-slate-500">Gemini</span> + <span className="text-slate-500">GPT-4o</span> + <span className="text-slate-500">Claude Sonnet</span>
          </p>
          <div className="flex gap-1">
            {["Fetch", "Validate", "Weather", "Predict", "Explain", "Report"].map((step) => (
              <span key={step} className="px-2 py-0.5 text-[9px] uppercase tracking-wider bg-white/5 text-slate-500 rounded-full border border-white/5">
                {step}
              </span>
            ))}
          </div>
        </div>
      </footer>
    </main>
  );
}

const accentColors: Record<string, { dot: string; badge: string; border: string }> = {
  red: { dot: "bg-red-500", badge: "bg-red-500/10 text-red-400 border-red-500/20", border: "hover:border-red-500/30" },
  amber: { dot: "bg-amber-500", badge: "bg-amber-500/10 text-amber-400 border-amber-500/20", border: "hover:border-amber-500/30" },
  slate: { dot: "bg-slate-500", badge: "bg-slate-500/10 text-slate-400 border-slate-500/20", border: "hover:border-slate-500/30" },
};

function MatchSection({
  title,
  accentColor,
  dotPulse,
  matches,
  getPredForMatch,
}: {
  title: string;
  accentColor: string;
  dotPulse?: boolean;
  matches: Match[];
  getPredForMatch: (id: string) => Prediction | undefined;
}) {
  const colors = accentColors[accentColor] || accentColors.slate;

  return (
    <div className="mb-12">
      <div className="flex items-center gap-3 mb-5">
        <div className="relative flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${colors.dot} ${dotPulse ? "animate-pulse" : ""}`} />
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider">{title}</h2>
        </div>
        <div className="flex-1 h-px bg-gradient-to-r from-white/10 to-transparent" />
        <span className={`px-2.5 py-1 text-[10px] font-medium rounded-full border ${colors.badge}`}>
          {matches.length}
        </span>
      </div>

      <div className="space-y-2">
        {matches.map((match, index) => {
          const pred = getPredForMatch(match.id);
          return (
            <Link key={match.id} href={`/match/${match.id}`}>
              <div
                className={`group relative bg-white/[0.02] border border-white/5 rounded-xl p-5 ${colors.border} transition-all duration-300 cursor-pointer hover:bg-white/[0.04]`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Hover glow */}
                <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-emerald-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                <div className="relative flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/10">
                        {match.match_type}
                      </span>
                      <span className="text-xs text-slate-600">
                        {match.date ? new Date(match.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""}
                      </span>
                    </div>
                    <h3 className="text-[15px] font-medium text-slate-200 group-hover:text-white transition-colors truncate pr-4">
                      {match.name}
                    </h3>
                    <p className="text-xs text-slate-600 mt-1">{match.venue}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">{match.status}</p>
                  </div>

                  {pred && (
                    <div className="ml-4 min-w-[150px] space-y-2.5">
                      <PredictionBar team={pred.team_a} prob={pred.team_a_win_prob} color="emerald" />
                      <PredictionBar team={pred.team_b} prob={pred.team_b_win_prob} color="blue" />
                    </div>
                  )}
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function PredictionBar({ team, prob, color }: { team: string; prob: number; color: string }) {
  const pct = prob * 100;
  const barColor = color === "emerald" ? "bg-emerald-500" : "bg-blue-500";
  const textColor = color === "emerald" ? "text-emerald-400" : "text-blue-400";

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className={`${textColor} font-medium truncate mr-2`}>{team}</span>
        <span className={`${textColor} font-bold tabular-nums`}>{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
        <div className={`h-full ${barColor} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
