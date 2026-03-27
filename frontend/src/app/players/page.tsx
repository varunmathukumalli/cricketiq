"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getIPLPlayers,
  getIPLPredictions,
  generateIPLPredictions,
  IPLPlayer,
  IPLTeamSquad,
  IPLPrediction,
} from "@/lib/api";

const ROLE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  "Batsman":     { label: "BAT",  color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
  "Bowler":      { label: "BOWL", color: "text-blue-400",    bg: "bg-blue-500/10 border-blue-500/20" },
  "All-rounder": { label: "AR",   color: "text-purple-400",  bg: "bg-purple-500/10 border-purple-500/20" },
  "WK-Batsman":  { label: "WK",   color: "text-amber-400",   bg: "bg-amber-500/10 border-amber-500/20" },
};

const CONFIDENCE_CONFIG: Record<string, { color: string; dot: string }> = {
  High:   { color: "text-emerald-400", dot: "bg-emerald-400" },
  Medium: { color: "text-amber-400",   dot: "bg-amber-400" },
  Low:    { color: "text-slate-400",   dot: "bg-slate-400" },
};

const CATEGORY_META: Record<string, { title: string; icon: string; metric: string }> = {
  orange_cap:  { title: "Orange Cap Race", icon: "🏅", metric: "predicted runs" },
  purple_cap:  { title: "Purple Cap Race", icon: "🎯", metric: "predicted wickets" },
  breakout:    { title: "Ones to Watch",   icon: "⚡", metric: "breakout pick" },
};

export default function PlayersPage() {
  const [teamsData, setTeamsData] = useState<IPLTeamSquad[]>([]);
  const [predictions, setPredictions] = useState<Record<string, IPLPrediction[]>>({});
  const [selectedTeam, setSelectedTeam] = useState<string>("all");
  const [selectedRole, setSelectedRole] = useState<string>("all");
  const [activeTab, setActiveTab] = useState<"squads" | "predictions">("squads");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [playersRes, predsRes] = await Promise.all([
          getIPLPlayers(2026),
          getIPLPredictions(2026),
        ]);
        setTeamsData(playersRes.teams);
        setPredictions(predsRes.predictions);
      } catch {
        setError("Failed to load player data. Make sure the backend is running and the DB is seeded.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleGeneratePredictions() {
    setGenerating(true);
    try {
      await generateIPLPredictions(2026);
      // Poll every 3s until predictions appear (max 60s)
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        try {
          const predsRes = await getIPLPredictions(2026);
          if (Object.keys(predsRes.predictions).length > 0) {
            setPredictions(predsRes.predictions);
            setActiveTab("predictions");
            break;
          }
        } catch { /* keep polling */ }
      }
      setGenerating(false);
    } catch {
      setGenerating(false);
    }
  }

  // Flatten all players for "all teams" view
  const allPlayers = teamsData.flatMap((t) =>
    t.players.map((p) => ({ ...p, team_id: t.id, team_name: t.name, short_name: t.short_name, primary_color: t.primary_color }))
  );

  const displayedTeam = selectedTeam === "all" ? null : teamsData.find((t) => t.id === selectedTeam);
  const displayedPlayers = (displayedTeam ? displayedTeam.players.map((p) => ({
    ...p, team_id: displayedTeam.id, team_name: displayedTeam.name, short_name: displayedTeam.short_name, primary_color: displayedTeam.primary_color,
  })) : allPlayers).filter((p) =>
    selectedRole === "all" || p.player_role === selectedRole
  );

  const hasPredictions = Object.keys(predictions).length > 0;

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="text-center">
        <div className="relative w-16 h-16 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-emerald-400 animate-spin" />
          <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-blue-400 animate-spin" style={{ animationDirection: "reverse", animationDuration: "1.5s" }} />
        </div>
        <p className="text-slate-500 text-sm tracking-widest uppercase">Loading IPL 2026 Squads</p>
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -left-40 w-80 h-80 bg-blue-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-72 h-72 bg-purple-500/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative border-b border-white/5 bg-[#0a0a0f]/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 py-5 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-4 group">
              <div className="relative">
                <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500 to-blue-500 rounded-xl opacity-50 blur group-hover:opacity-75 transition" />
                <div className="relative w-10 h-10 bg-[#0a0a0f] rounded-xl flex items-center justify-center border border-white/10">
                  <span className="text-lg font-bold bg-gradient-to-r from-emerald-400 to-blue-400 bg-clip-text text-transparent">C</span>
                </div>
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">
                  <span className="bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">CricketIQ</span>
                </h1>
                <p className="text-[11px] text-slate-500 tracking-wider uppercase">IPL 2026 Players</p>
              </div>
            </Link>
          </div>

          <button
            onClick={handleGeneratePredictions}
            disabled={generating}
            className="group relative px-5 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl opacity-90 group-hover:opacity-100 transition" />
            <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl blur-lg opacity-0 group-hover:opacity-40 transition" />
            <span className="relative flex items-center gap-2 text-white">
              {generating && <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />}
              {generating ? "Generating..." : "AI Predictions"}
            </span>
          </button>
        </div>
      </header>

      <div className="relative max-w-6xl mx-auto px-6 py-10">
        {/* Error state */}
        {error && (
          <div className="mb-8 bg-red-500/10 border border-red-500/20 rounded-2xl p-6 text-center">
            <p className="text-red-400 font-medium mb-1">No player data found</p>
            <p className="text-red-400/60 text-sm">{error}</p>
            <p className="text-slate-600 text-xs mt-3">Run: <code className="text-slate-400">cd src && python ipl_seed.py</code> to seed IPL 2026 squads</p>
          </div>
        )}

        {/* Tab switcher */}
        <div className="flex gap-1 mb-8 bg-white/[0.03] border border-white/5 rounded-xl p-1 w-fit">
          {(["squads", "predictions"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab
                  ? "bg-white/10 text-white"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {tab === "squads" ? "Team Squads" : "AI Predictions"}
              {tab === "predictions" && hasPredictions && (
                <span className="ml-2 px-1.5 py-0.5 text-[9px] bg-purple-500/20 text-purple-400 rounded-full border border-purple-500/20">NEW</span>
              )}
            </button>
          ))}
        </div>

        {/* ── SQUADS TAB ── */}
        {activeTab === "squads" && (
          <>
            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              {[
                { label: "Teams", value: teamsData.length, icon: "🏟", color: "from-emerald-500/20 to-emerald-500/5" },
                { label: "Players", value: allPlayers.length, icon: "🏏", color: "from-blue-500/20 to-blue-500/5" },
                { label: "Overseas", value: allPlayers.filter((p) => p.is_overseas).length, icon: "✈️", color: "from-purple-500/20 to-purple-500/5" },
              ].map(({ label, value, icon, color }) => (
                <div key={label} className={`bg-gradient-to-b ${color} border border-white/5 rounded-2xl p-5 text-center`}>
                  <p className="text-2xl mb-1">{icon}</p>
                  <p className="text-3xl font-bold tabular-nums">{value}</p>
                  <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest">{label}</p>
                </div>
              ))}
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-3 mb-8">
              {/* Team filter */}
              <div className="flex gap-1 flex-wrap">
                <button
                  onClick={() => setSelectedTeam("all")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    selectedTeam === "all"
                      ? "bg-white/10 border-white/20 text-white"
                      : "bg-white/[0.02] border-white/5 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  All Teams
                </button>
                {teamsData.map((team) => (
                  <button
                    key={team.id}
                    onClick={() => setSelectedTeam(team.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      selectedTeam === team.id
                        ? "bg-white/10 border-white/20 text-white"
                        : "bg-white/[0.02] border-white/5 text-slate-400 hover:text-slate-200"
                    }`}
                    style={selectedTeam === team.id ? { borderColor: team.primary_color + "60", color: team.primary_color } : {}}
                  >
                    {team.short_name}
                  </button>
                ))}
              </div>

              {/* Role filter */}
              <div className="flex gap-1 ml-auto">
                {["all", "Batsman", "Bowler", "All-rounder", "WK-Batsman"].map((role) => {
                  const cfg = role !== "all" ? ROLE_CONFIG[role] : null;
                  return (
                    <button
                      key={role}
                      onClick={() => setSelectedRole(role)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        selectedRole === role
                          ? `${cfg?.bg || "bg-white/10 border-white/20"} ${cfg?.color || "text-white"}`
                          : "bg-white/[0.02] border-white/5 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {role === "all" ? "All Roles" : cfg?.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Selected team header */}
            {displayedTeam && (
              <div className="mb-6 flex items-center gap-4">
                <div
                  className="w-1 h-12 rounded-full"
                  style={{ backgroundColor: displayedTeam.primary_color }}
                />
                <div>
                  <h2 className="text-2xl font-bold text-white">{displayedTeam.name}</h2>
                  <p className="text-sm text-slate-500">{displayedTeam.city} · {displayedTeam.home_ground}</p>
                </div>
                <div className="ml-auto text-right">
                  <p className="text-2xl font-bold text-white">{displayedPlayers.length}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest">Players</p>
                </div>
              </div>
            )}

            {/* Player grid */}
            {displayedPlayers.length === 0 ? (
              <div className="text-center py-20 border border-white/5 rounded-2xl bg-white/[0.02]">
                <p className="text-slate-400 text-lg">No players found</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {displayedPlayers.map((player) => {
                  const roleCfg = ROLE_CONFIG[player.player_role] || ROLE_CONFIG["Batsman"];
                  return (
                    <Link
                      key={`${player.team_id}-${player.player_name}`}
                      href={`/players/${encodeURIComponent(player.player_name)}`}
                    >
                    <div
                      className="group relative bg-white/[0.02] border border-white/5 rounded-xl p-4 hover:bg-white/[0.04] hover:border-white/10 transition-all duration-200 cursor-pointer"
                    >
                      {/* Team color accent */}
                      <div
                        className="absolute top-0 left-0 w-1 h-full rounded-l-xl opacity-60"
                        style={{ backgroundColor: (player as any).primary_color || "#10b981" }}
                      />

                      <div className="pl-2">
                        <div className="flex items-start justify-between mb-2">
                          <h3 className="text-sm font-semibold text-white leading-tight">{player.player_name}</h3>
                          <span className={`ml-2 shrink-0 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded border ${roleCfg.bg} ${roleCfg.color}`}>
                            {roleCfg.label}
                          </span>
                        </div>

                        <div className="space-y-1">
                          {selectedTeam === "all" && (
                            <p className="text-[11px] text-slate-400 font-medium">
                              {(player as any).short_name}
                            </p>
                          )}
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${player.is_overseas ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" : "bg-slate-500/10 text-slate-400 border border-slate-500/20"}`}>
                              {player.nationality}
                            </span>
                            {player.is_overseas && (
                              <span className="text-[9px] text-amber-500/70">OVERSEAS</span>
                            )}
                          </div>
                          {player.batting_style && (
                            <p className="text-[10px] text-slate-600">🏏 {player.batting_style}</p>
                          )}
                          {player.bowling_style && (
                            <p className="text-[10px] text-slate-600">🎳 {player.bowling_style}</p>
                          )}
                        </div>
                      </div>
                    </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ── PREDICTIONS TAB ── */}
        {activeTab === "predictions" && (
          <>
            {!hasPredictions ? (
              <div className="text-center py-24 border border-white/5 rounded-2xl bg-white/[0.02]">
                <p className="text-5xl mb-4">🤖</p>
                <p className="text-slate-300 text-xl font-semibold mb-2">No Predictions Yet</p>
                <p className="text-slate-500 text-sm mb-8 max-w-sm mx-auto">
                  Click &ldquo;AI Predictions&rdquo; to have Claude Sonnet analyze the IPL 2026 squads
                  and predict top performers for the season.
                </p>
                <button
                  onClick={handleGeneratePredictions}
                  disabled={generating}
                  className="group relative px-8 py-3 rounded-xl text-sm font-medium"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl opacity-90 group-hover:opacity-100 transition" />
                  <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl blur-lg opacity-0 group-hover:opacity-50 transition" />
                  <span className="relative flex items-center gap-2 text-white">
                    {generating && <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />}
                    {generating ? "Generating predictions..." : "Generate AI Predictions"}
                  </span>
                </button>
              </div>
            ) : (
              <div className="space-y-10">
                {["orange_cap", "purple_cap", "breakout"].map((category) => {
                  const meta = CATEGORY_META[category];
                  const preds = predictions[category] || [];
                  if (preds.length === 0) return null;
                  return (
                    <section key={category}>
                      <div className="flex items-center gap-3 mb-5">
                        <span className="text-2xl">{meta.icon}</span>
                        <h2 className="text-lg font-bold text-white">{meta.title}</h2>
                        <div className="flex-1 h-px bg-gradient-to-r from-white/10 to-transparent" />
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider">{meta.metric}</span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {preds.map((pred, idx) => {
                          const confCfg = CONFIDENCE_CONFIG[pred.confidence] || CONFIDENCE_CONFIG.Medium;
                          return (
                            <div
                              key={pred.player_name}
                              className="relative bg-white/[0.02] border border-white/5 rounded-2xl p-5 hover:bg-white/[0.04] transition-all"
                            >
                              {/* Rank badge */}
                              <div className="absolute -top-2.5 -left-2.5 w-7 h-7 rounded-full bg-[#0a0a0f] border border-white/10 flex items-center justify-center">
                                <span className="text-[11px] font-bold text-slate-400">#{idx + 1}</span>
                              </div>

                              {/* Team accent bar */}
                              {pred.primary_color && (
                                <div
                                  className="absolute top-0 right-0 w-1 h-full rounded-r-2xl opacity-50"
                                  style={{ backgroundColor: pred.primary_color }}
                                />
                              )}

                              <div className="mb-3">
                                <h3 className="text-base font-bold text-white">{pred.player_name}</h3>
                                <p className="text-xs text-slate-500">{pred.team_name || pred.team_id?.toUpperCase()}</p>
                              </div>

                              {/* Key metric */}
                              <div className="flex gap-3 mb-3">
                                {pred.predicted_runs != null && (
                                  <div className="bg-emerald-500/10 border border-emerald-500/10 rounded-xl px-3 py-2 text-center">
                                    <p className="text-xl font-bold text-emerald-400 tabular-nums">{pred.predicted_runs}</p>
                                    <p className="text-[9px] text-emerald-400/60 uppercase tracking-wider">Pred. Runs</p>
                                  </div>
                                )}
                                {pred.predicted_wickets != null && (
                                  <div className="bg-blue-500/10 border border-blue-500/10 rounded-xl px-3 py-2 text-center">
                                    <p className="text-xl font-bold text-blue-400 tabular-nums">{pred.predicted_wickets}</p>
                                    <p className="text-[9px] text-blue-400/60 uppercase tracking-wider">Pred. Wkts</p>
                                  </div>
                                )}
                                {pred.predicted_strike_rate != null && (
                                  <div className="bg-purple-500/10 border border-purple-500/10 rounded-xl px-3 py-2 text-center">
                                    <p className="text-xl font-bold text-purple-400 tabular-nums">{Number(pred.predicted_strike_rate).toFixed(0)}</p>
                                    <p className="text-[9px] text-purple-400/60 uppercase tracking-wider">Pred. SR</p>
                                  </div>
                                )}
                              </div>

                              {/* Confidence */}
                              <div className="flex items-center gap-1.5 mb-3">
                                <span className={`w-1.5 h-1.5 rounded-full ${confCfg.dot}`} />
                                <span className={`text-[10px] font-medium uppercase tracking-wider ${confCfg.color}`}>
                                  {pred.confidence} Confidence
                                </span>
                              </div>

                              {/* Reasoning */}
                              {pred.reasoning && (
                                <p className="text-xs text-slate-500 leading-relaxed">{pred.reasoning}</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}

                {/* Regenerate button */}
                <div className="text-center pt-4">
                  <button
                    onClick={handleGeneratePredictions}
                    disabled={generating}
                    className="group relative px-6 py-2.5 rounded-xl text-sm font-medium text-slate-400 border border-white/5 hover:border-white/10 hover:text-slate-200 transition-all disabled:opacity-40"
                  >
                    {generating ? "Regenerating..." : "Regenerate Predictions"}
                  </button>
                  {predictions.orange_cap?.[0]?.generated_at && (
                    <p className="text-[10px] text-slate-600 mt-2">
                      Last generated: {new Date(predictions.orange_cap[0].generated_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <footer className="relative border-t border-white/5 mt-16">
        <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col md:flex-row justify-between items-center gap-3">
          <p className="text-[11px] text-slate-600">
            IPL 2026 squads · Men&apos;s IPL only · Powered by <span className="text-slate-500">Claude Sonnet</span>
          </p>
          <Link href="/" className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors">
            &larr; Back to matches
          </Link>
        </div>
      </footer>
    </main>
  );
}
