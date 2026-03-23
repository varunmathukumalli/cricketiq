"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getMatch, getPrediction, getReport, Prediction, Report } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function MatchPage() {
  const params = useParams();
  const matchId = params.id as string;
  const [matchData, setMatchData] = useState<any>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const match = await getMatch(matchId);
        setMatchData(match);
        try { setPrediction(await getPrediction(matchId)); } catch {}
        try { setReport(await getReport(matchId)); } catch {}
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    fetchData();
  }, [matchId]);

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="relative w-16 h-16">
        <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-emerald-400 animate-spin" />
      </div>
    </div>
  );

  if (!matchData?.match) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="text-center">
        <p className="text-4xl mb-4">🏏</p>
        <p className="text-slate-400 text-lg mb-4">Match not found</p>
        <Link href="/" className="text-emerald-400 hover:text-emerald-300 text-sm">
          &larr; Back to matches
        </Link>
      </div>
    </div>
  );

  const match = matchData.match;
  const performances = matchData.performances || [];
  const chartData = prediction ? [
    { name: prediction.team_a, probability: prediction.team_a_win_prob * 100 },
    { name: prediction.team_b, probability: prediction.team_b_win_prob * 100 },
  ] : [];

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 -left-40 w-80 h-80 bg-blue-500/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative border-b border-white/5 bg-[#0a0a0f]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 py-5">
          <Link href="/" className="text-emerald-400 hover:text-emerald-300 text-xs uppercase tracking-wider flex items-center gap-1.5 mb-4 group">
            <span className="group-hover:-translate-x-0.5 transition-transform">&larr;</span> Back to matches
          </Link>
          <h1 className="text-2xl font-bold">
            <span className="bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">{match.name}</span>
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <span className="px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/10">
              {match.match_type}
            </span>
            <span className="text-sm text-slate-500">{match.venue}</span>
            <span className="text-slate-700">&middot;</span>
            <span className="text-sm text-slate-600">{match.status}</span>
          </div>
        </div>
      </header>

      <div className="relative max-w-5xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Win Probability */}
          {prediction && (
            <Card title="Win Probability" icon="📊">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} layout="vertical">
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="#334155" fontSize={11} />
                  <YAxis type="category" dataKey="name" width={80} stroke="#64748b" fontSize={12} />
                  <Tooltip
                    formatter={(v) => `${Number(v).toFixed(1)}%`}
                    contentStyle={{ backgroundColor: "#12121a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", color: "#e2e8f0", fontSize: "12px" }}
                    labelStyle={{ color: "#94a3b8" }}
                    cursor={{ fill: "rgba(255,255,255,0.02)" }}
                  />
                  <Bar dataKey="probability" radius={[0, 6, 6, 0]}>
                    <Cell fill="#10b981" /><Cell fill="#3b82f6" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              {/* Probability badges */}
              <div className="flex gap-3 mt-4">
                <div className="flex-1 bg-emerald-500/10 border border-emerald-500/10 rounded-xl p-3 text-center">
                  <p className="text-xs text-emerald-400/70 mb-0.5">{prediction.team_a}</p>
                  <p className="text-2xl font-bold text-emerald-400 tabular-nums">{(prediction.team_a_win_prob * 100).toFixed(0)}%</p>
                </div>
                <div className="flex-1 bg-blue-500/10 border border-blue-500/10 rounded-xl p-3 text-center">
                  <p className="text-xs text-blue-400/70 mb-0.5">{prediction.team_b}</p>
                  <p className="text-2xl font-bold text-blue-400 tabular-nums">{(prediction.team_b_win_prob * 100).toFixed(0)}%</p>
                </div>
              </div>

              {prediction.explanation && (
                <div className="mt-4 text-sm text-slate-400 bg-white/[0.02] border border-white/5 p-4 rounded-xl">
                  <p className="font-medium text-emerald-400 text-xs uppercase tracking-wider mb-2">Agent Explanation</p>
                  <p className="whitespace-pre-wrap leading-relaxed text-slate-300">{prediction.explanation}</p>
                </div>
              )}
            </Card>
          )}

          {/* Weather */}
          {match.temperature && (
            <Card title="Weather Conditions" icon="🌤">
              <div className="grid grid-cols-3 gap-3">
                <WeatherStat value={`${match.temperature}°C`} label="Temperature" color="text-orange-400" />
                <WeatherStat value={`${match.humidity}%`} label="Humidity" color="text-blue-400" />
                <WeatherStat value={match.wind_speed} label="Wind (km/h)" color="text-slate-300" />
              </div>
              {match.weather_summary && (
                <p className="mt-4 text-sm text-slate-400 bg-white/[0.02] border border-white/5 p-3 rounded-xl leading-relaxed">
                  {match.weather_summary}
                </p>
              )}
            </Card>
          )}
        </div>

        {/* AI Report */}
        {report && (
          <Card title="AI Match Report" icon="📝" className="mt-6">
            <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{report.report_text}</div>
            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/5">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
              <p className="text-[11px] text-slate-600">Generated by Claude Sonnet &middot; {report.generated_at}</p>
            </div>
          </Card>
        )}

        {/* Player Performances */}
        {performances.length > 0 && (
          <Card title="Player Performances" icon="🏏" className="mt-6">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left">
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium">Player</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium">Team</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Runs</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">SR</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Wickets</th>
                  </tr>
                </thead>
                <tbody>
                  {performances.map((p: any, i: number) => (
                    <tr key={i} className="border-b border-white/[0.03] last:border-0 hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 font-medium text-white">{p.player_name}</td>
                      <td className="py-3 text-slate-500">{p.team}</td>
                      <td className="py-3 text-right text-slate-300 tabular-nums">{p.runs_scored ?? "-"}</td>
                      <td className="py-3 text-right text-slate-300 tabular-nums">{p.strike_rate ?? "-"}</td>
                      <td className="py-3 text-right text-slate-300 tabular-nums">{p.wickets ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* No data state */}
        {!prediction && !report && performances.length === 0 && (
          <div className="text-center py-20 border border-white/5 rounded-2xl bg-white/[0.02] mt-6">
            <p className="text-4xl mb-4">📊</p>
            <p className="text-slate-400 text-lg mb-2">No predictions or reports yet</p>
            <p className="text-slate-600 text-sm">Run the agent pipeline to generate analytics for this match</p>
          </div>
        )}
      </div>
    </main>
  );
}

function Card({ title, icon, className = "", children }: { title: string; icon: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={`group relative ${className}`}>
      <div className="absolute -inset-px bg-gradient-to-b from-white/10 to-transparent rounded-2xl opacity-0 group-hover:opacity-100 transition duration-500 pointer-events-none" />
      <div className="relative bg-white/[0.03] border border-white/5 rounded-2xl p-6 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-lg">{icon}</span>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">{title}</h2>
        </div>
        {children}
      </div>
    </div>
  );
}

function WeatherStat({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div className="bg-white/[0.03] border border-white/5 rounded-xl p-3 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-[10px] text-slate-600 mt-1 uppercase tracking-wider">{label}</p>
    </div>
  );
}
