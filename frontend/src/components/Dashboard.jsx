import React, { useEffect } from "react";
import { useMemoryStore } from "../store/useMemoryStore";
import GraphViewer from "./GraphViewer";
import LoadingSpinner from "./LoadingSpinner";

export default function Dashboard() {
  const { stats, fetchStats, loadingStates } = useMemoryStore();

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  if (loadingStates.stats && !stats.total_memories) {
    return <LoadingSpinner message="Calibrating metrics..." />;
  }

  const cards = [
    {
      label: "Episodic Items",
      val: stats.total_memories,
      color: "text-slate-200 border-slate-700",
    },
    { label: "Assertions", val: stats.total_learnings, color: "text-emerald-300 border-slate-700" },
    {
      label: "Consolidations",
      val: stats.total_consolidations ?? 0,
      color: "text-blue-300 border-blue-900/50",
    },
    {
      label: "Entities",
      val: stats.total_entities ?? 0,
      color: "text-emerald-300 border-emerald-800/50",
    },
    {
      label: "Relations",
      val: stats.total_relations ?? 0,
      color: "text-purple-300 border-purple-800/50",
    },
    {
      label: "Pending Review",
      val: stats.pending_review ?? 0,
      color: "text-amber-300 border-amber-800/50",
    },
    { label: "Projects", val: stats.total_projects, color: "text-slate-200 border-slate-700" },
    { label: "API Keys", val: stats.total_keys, color: "text-slate-200 border-slate-700" },
  ];

  return (
    <div className="flex flex-col h-full gap-6 animate-in fade-in duration-300 overflow-hidden">
      {/* Stats Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 flex-shrink-0">
        {cards.map((card, i) => (
          <div
            key={i}
            className={`bg-slate-800/90 p-4 rounded-xl border ${card.color} shadow-lg hover:shadow-xl transition-all duration-300 flex flex-col justify-between`}
          >
            <div className="text-slate-400 text-xs font-semibold tracking-wider uppercase mb-1.5">
              {card.label}
            </div>
            <div className="text-3xl font-extrabold tracking-tight font-mono">{card.val}</div>
          </div>
        ))}
      </div>

      {/* 3D Graph Explorer Area */}
      <div className="flex-1 min-h-0 flex flex-col relative">
        <GraphViewer />
      </div>
    </div>
  );
}
