import React, { useState } from "react";
import { Play, Filter, Activity } from "lucide-react";
import { useMemoryStore } from "../store/useMemoryStore";
import CondensationPlayground from "./CondensationPlayground";

export default function Playground() {
  const [subTab, setSubTab] = useState("traffic"); // traffic, condenser

  const { keys, llmConfigs, auth } = useMemoryStore();

  // Traffic Control state
  const [playgroundQuery, setPlaygroundQuery] = useState("");
  const [playgroundResult, setPlaygroundResult] = useState(null);
  const [playgroundLoading, setPlaygroundLoading] = useState(false);

  const handlePlaygroundSubmit = async (e) => {
    e.preventDefault();
    if (!playgroundQuery.trim()) return;
    setPlaygroundLoading(true);
    setPlaygroundResult(null);
    try {
      const pid = keys.length > 0 ? keys[0].project_id : "default-project";
      const currentLlmConfig =
        llmConfigs.configs.find((c) => c.is_primary) ||
        llmConfigs.configs.find((c) => c.is_active) ||
        null;

      const res = await fetch("/api/admin/playground/retrieve", {
        method: "POST",
        headers: {
          Authorization: auth,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          project_id: pid,
          query: playgroundQuery.trim(),
          skip_llm: false,
          llm_config: currentLlmConfig,
        }),
      });
      const data = await res.json();
      setPlaygroundResult(data);
    } catch (err) {
      console.error(err);
      alert("Playground error: " + err.message);
    } finally {
      setPlaygroundLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full gap-6 animate-in fade-in duration-300 overflow-hidden">
      {/* Sub Tabs Selection */}
      <div className="flex bg-slate-800/60 p-1.5 rounded-xl border border-slate-700/60 flex-shrink-0 gap-1">
        <button
          onClick={() => setSubTab("traffic")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            subTab === "traffic"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/35"
          }`}
        >
          <Play className="w-4 h-4" />
          <span>Traffic Control Router</span>
        </button>
        <button
          onClick={() => setSubTab("condenser")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            subTab === "condenser"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/35"
          }`}
        >
          <Filter className="w-4 h-4" />
          <span>L3-Condenser Heuristics</span>
        </button>
      </div>

      {/* Content Display */}
      <div className="flex-1 min-h-0 bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex flex-col shadow-xl">
        {subTab === "traffic" && (
          <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6">
            <div className="text-center max-w-xl mx-auto mb-8 space-y-2">
              <h2 className="text-2xl font-bold text-blue-400">Traffic Control Sandbox</h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                Inspect how the semantic router splits traffic. Verify deterministic heuristics, LTP
                activation, and when LLM generation cycles are fully bypassed.
              </p>
            </div>

            <div className="max-w-3xl mx-auto space-y-6">
              <form onSubmit={handlePlaygroundSubmit} className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={playgroundQuery}
                  onChange={(e) => setPlaygroundQuery(e.target.value)}
                  placeholder="Enter your memory context search or chat prompt..."
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm font-semibold shadow"
                />
                <button
                  type="submit"
                  disabled={playgroundLoading}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold px-6 py-3 rounded-xl transition-all shadow-lg shadow-blue-900/30 text-sm shrink-0 flex items-center justify-center gap-2"
                >
                  {playgroundLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                      <span>Routing...</span>
                    </>
                  ) : (
                    <>
                      <Activity className="w-4 h-4" />
                      <span>Test Route</span>
                    </>
                  )}
                </button>
              </form>

              {playgroundResult && (
                <div className="space-y-6 animate-in fade-in duration-300">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-slate-900 p-4 rounded-xl border border-slate-750">
                      <div className="text-[10px] text-slate-500 uppercase font-extrabold tracking-wider mb-1">
                        Route Strategy Decided
                      </div>
                      <div className="text-lg font-mono font-bold text-purple-400 uppercase">
                        {playgroundResult.strategy}
                      </div>
                    </div>
                    <div className="bg-slate-900 p-4 rounded-xl border border-slate-750">
                      <div className="text-[10px] text-slate-500 uppercase font-extrabold tracking-wider mb-1">
                        Synaptic Relevance Score
                      </div>
                      <div className="text-lg font-mono font-bold text-blue-400 uppercase">
                        {playgroundResult.score !== undefined
                          ? `${(playgroundResult.score * 100).toFixed(0)}%`
                          : "N/A"}
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-900 p-5 rounded-xl border border-slate-750">
                    <div className="text-[10px] text-slate-500 uppercase font-extrabold tracking-wider mb-2.5">
                      Contextual Answer
                    </div>
                    <pre className="text-slate-300 font-mono text-xs whitespace-pre-wrap leading-relaxed bg-slate-950 p-4 rounded-lg border border-slate-900/40">
                      {playgroundResult.answer || "Bypassed generation. No relevant context found."}
                    </pre>
                  </div>

                  {playgroundResult.sources && playgroundResult.sources.length > 0 && (
                    <div className="bg-slate-900 p-5 rounded-xl border border-slate-750">
                      <div className="text-[10px] text-slate-500 uppercase font-extrabold tracking-wider mb-3">
                        Supporting Synaptic Nodes
                      </div>
                      <div className="space-y-2">
                        {playgroundResult.sources.map((src, idx) => (
                          <div
                            key={idx}
                            className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 text-xs text-slate-300 leading-relaxed font-mono"
                          >
                            {src}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {subTab === "condenser" && (
          <div className="flex-1 overflow-hidden h-full">
            <CondensationPlayground />
          </div>
        )}
      </div>
    </div>
  );
}
