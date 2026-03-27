"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getPlayerStats, PlayerPerformance } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";

export default function PlayerDetailPage() {
  const params = useParams();
  // id is the URL-encoded player name (e.g. "Virat%20Kohli")
  const playerName = decodeURIComponent(params.id as string);
  const [player, setPlayer] = useState<any>(null);
  const [performances, setPerformances] = useState<PlayerPerformance[]>([]);
  const [aggregate, setAggregate] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getPlayerStats(playerName);
        setPlayer(data.player);
        setPerformances(data.performances);
        setAggregate(data.aggregate);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    fetchData();
  }, [playerName]);

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="relative w-16 h-16">
        <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-emerald-400 animate-spin" />
      </div>
    </div>
  );

  if (!player) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white">
      <div className="text-center">
        <p className="text-4xl mb-4">🏏</p>
        <p className="text-slate-400">Player not found</p>
        <Link href="/players" className="text-emerald-400 hover:text-emerald-300 text-sm mt-4 block">&larr; Back to players</Link>
      </div>
    </div>
  );

  // Chart data: runs across matches (chronological)
  const runsTimeline = [...performances]
    .reverse()
    .filter((p) => p.runs_scored != null)
    .map((p) => ({
      match: p.match_name.replace(/,.*/g, "").substring(0, 20),
      runs: p.runs_scored || 0,
      sr: p.strike_rate || 0,
    }));

  const wicketsTimeline = [...performances]
    .reverse()
    .filter((p) => p.wickets != null && p.wickets > 0)
    .map((p) => ({
      match: p.match_name.replace(/,.*/g, "").substring(0, 20),
      wickets: p.wickets || 0,
      economy: p.economy || 0,
    }));

  const tooltipStyle = {
    backgroundColor: "#12121a",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: "12px",
    color: "#e2e8f0",
    fontSize: "12px",
  };

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 -left-40 w-80 h-80 bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative border-b border-white/5 bg-[#0a0a0f]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 py-5">
          <Link href="/players" className="text-emerald-400 hover:text-emerald-300 text-xs uppercase tracking-wider flex items-center gap-1.5 mb-4 group">
            <span className="group-hover:-translate-x-0.5 transition-transform">&larr;</span> All Players
          </Link>
          <h1 className="text-2xl font-bold">
            <span className="bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">{player.name}</span>
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-sm text-slate-500">{player.country}</span>
            {player.player_role && (
              <>
                <span className="text-slate-700">&middot;</span>
                <span className="px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-purple-500/10 text-purple-400 rounded border border-purple-500/10">
                  {player.player_role}
                </span>
              </>
            )}
            {player.batting_style && (
              <>
                <span className="text-slate-700">&middot;</span>
                <span className="text-xs text-slate-600">{player.batting_style}</span>
              </>
            )}
          </div>
        </div>
      </header>

      <div className="relative max-w-5xl mx-auto px-6 py-10">
        {/* Aggregate Stats */}
        {aggregate && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
            <StatCard label="Matches" value={aggregate.innings} color="text-white" />
            <StatCard label="Total Runs" value={aggregate.total_runs} color="text-emerald-400" />
            <StatCard label="Batting Avg" value={aggregate.batting_avg} color="text-amber-400" />
            <StatCard label="Total Wickets" value={aggregate.total_wickets} color="text-blue-400" />
          </div>
        )}

        {/* Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
          {runsTimeline.length > 0 && (
            <Card title="Runs per Match" icon="📈">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={runsTimeline} margin={{ left: 0, right: 10 }}>
                  <XAxis dataKey="match" stroke="#334155" fontSize={10} angle={-20} textAnchor="end" height={50} />
                  <YAxis stroke="#334155" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
                  <Bar dataKey="runs" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {runsTimeline.length > 1 && (
            <Card title="Strike Rate Trend" icon="⚡">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={runsTimeline} margin={{ left: 0, right: 10 }}>
                  <XAxis dataKey="match" stroke="#334155" fontSize={10} angle={-20} textAnchor="end" height={50} />
                  <YAxis stroke="#334155" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "rgba(255,255,255,0.1)" }} />
                  <Line type="monotone" dataKey="sr" stroke="#f59e0b" strokeWidth={2} dot={{ fill: "#f59e0b", r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {wicketsTimeline.length > 0 && (
            <Card title="Wickets per Match" icon="🎯">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={wicketsTimeline} margin={{ left: 0, right: 10 }}>
                  <XAxis dataKey="match" stroke="#334155" fontSize={10} angle={-20} textAnchor="end" height={50} />
                  <YAxis stroke="#334155" fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
                  <Bar dataKey="wickets" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {wicketsTimeline.length > 1 && (
            <Card title="Economy Rate Trend" icon="📉">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={wicketsTimeline} margin={{ left: 0, right: 10 }}>
                  <XAxis dataKey="match" stroke="#334155" fontSize={10} angle={-20} textAnchor="end" height={50} />
                  <YAxis stroke="#334155" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "rgba(255,255,255,0.1)" }} />
                  <Line type="monotone" dataKey="economy" stroke="#8b5cf6" strokeWidth={2} dot={{ fill: "#8b5cf6", r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>

        {/* Match-by-match table */}
        {performances.length > 0 && (
          <Card title="Match History" icon="📋">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left">
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium">Match</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Runs</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Balls</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">4s</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">6s</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">SR</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Overs</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Wkts</th>
                    <th className="pb-3 text-[11px] uppercase tracking-wider text-slate-500 font-medium text-right">Eco</th>
                  </tr>
                </thead>
                <tbody>
                  {performances.map((p, i) => (
                    <tr key={i} className="border-b border-white/[0.03] last:border-0 hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 pr-4">
                        <p className="text-white text-xs font-medium">{p.match_name.replace(/,.*/g, "")}</p>
                        <p className="text-[10px] text-slate-600">{p.match_date ? new Date(p.match_date).toLocaleDateString() : ""}</p>
                      </td>
                      <td className="py-3 text-right text-white font-medium tabular-nums">{p.runs_scored ?? "—"}</td>
                      <td className="py-3 text-right text-slate-500 tabular-nums">{p.balls_faced ?? "—"}</td>
                      <td className="py-3 text-right text-slate-500 tabular-nums">{p.fours ?? "—"}</td>
                      <td className="py-3 text-right text-slate-500 tabular-nums">{p.sixes ?? "—"}</td>
                      <td className="py-3 text-right text-emerald-400/80 tabular-nums">{p.strike_rate ?? "—"}</td>
                      <td className="py-3 text-right text-slate-500 tabular-nums">{p.overs_bowled ?? "—"}</td>
                      <td className="py-3 text-right text-blue-400/80 tabular-nums">{p.wickets ?? "—"}</td>
                      <td className="py-3 text-right text-slate-500 tabular-nums">{p.economy ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </main>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="group relative">
      <div className="absolute -inset-px bg-gradient-to-b from-white/10 to-transparent rounded-2xl opacity-0 group-hover:opacity-100 transition duration-500 pointer-events-none" />
      <div className="relative bg-white/[0.03] border border-white/5 rounded-2xl p-5 text-center backdrop-blur-sm">
        <p className={`text-3xl font-bold ${color} tabular-nums`}>{value}</p>
        <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest">{label}</p>
      </div>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="group relative">
      <div className="absolute -inset-px bg-gradient-to-b from-white/10 to-transparent rounded-2xl opacity-0 group-hover:opacity-100 transition duration-500 pointer-events-none" />
      <div className="relative bg-white/[0.03] border border-white/5 rounded-2xl p-6 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">{icon}</span>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">{title}</h2>
        </div>
        {children}
      </div>
    </div>
  );
}
