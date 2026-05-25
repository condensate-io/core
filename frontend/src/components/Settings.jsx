import React, { useEffect } from "react";
import {
  Brain,
  Plus,
  Trash2,
  Activity,
  ShieldAlert,
  CheckCircle,
  XCircle,
  Settings as SettingsIcon,
} from "lucide-react";
import { useMemoryStore } from "../store/useMemoryStore";
import LoadingSpinner from "./LoadingSpinner";

export default function Settings() {
  const {
    llmConfigs,
    fetchLlmConfig,
    systemConfig,
    fetchSystemConfig,
    saveSystemConfig,
    synapseConfig,
    fetchSynapseConfig,
    saveSynapseConfig,
    testLoading,
    testResults,
    testConfig,
    saveLlmConfigs,
    toggleConfigActive,
    setPrimaryConfig,
    addConfig,
    deleteConfig,
    updateConfigField,
  } = useMemoryStore();

  // Fetch config on mount
  useEffect(() => {
    fetchLlmConfig();
    fetchSystemConfig();
    fetchSynapseConfig();
  }, [fetchLlmConfig, fetchSystemConfig, fetchSynapseConfig]);

  if (!llmConfigs.configs.length && !systemConfig.review_mode) {
    return <LoadingSpinner message="Calibrating cognitive profiles..." />;
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto w-full pb-20 animate-in fade-in duration-300 overflow-y-auto pr-1 h-full">
      {/* Header Control Panel */}
      <div className="flex flex-col md:flex-row md:justify-between md:items-end gap-4 border-b border-slate-800 pb-6">
        <div>
          <h2 className="text-2xl font-bold text-blue-400 mb-1 flex items-center gap-2">
            <SettingsIcon className="w-6 h-6 animate-spin-slow" /> Cognitive Engines
          </h2>
          <p className="text-slate-400 text-sm">
            Provision default (Primary) and fallback model configurations for retrieval and
            synthesis logic.
          </p>
        </div>
        <div className="flex gap-3 items-center flex-wrap">
          <div className="bg-slate-800/60 p-1 rounded-xl border border-slate-700/60 flex items-center gap-1.5 shadow">
            <button
              type="button"
              onClick={() =>
                saveSystemConfig({
                  ...systemConfig,
                  condensation_paused: !systemConfig.condensation_paused,
                })
              }
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                systemConfig.condensation_paused
                  ? "bg-red-600/90 text-white shadow shadow-red-950/20"
                  : "text-slate-400 hover:text-slate-300"
              }`}
            >
              <Activity
                className={`w-3.5 h-3.5 ${systemConfig.condensation_paused ? "" : "animate-pulse"}`}
              />
              {systemConfig.condensation_paused ? "Condensation Paused" : "Condensation Active"}
            </button>
            <div className="w-px h-4 bg-slate-700/60" />
            <button
              type="button"
              onClick={() => saveSystemConfig({ ...systemConfig, review_mode: "manual" })}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                systemConfig.review_mode === "manual"
                  ? "bg-amber-600/90 text-white shadow"
                  : "text-slate-400 hover:text-slate-300"
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" /> Manual Review
            </button>
            <button
              type="button"
              onClick={() => saveSystemConfig({ ...systemConfig, review_mode: "auto" })}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                systemConfig.review_mode === "auto"
                  ? "bg-emerald-600/90 text-white shadow"
                  : "text-slate-400 hover:text-slate-300"
              }`}
            >
              <CheckCircle className="w-3.5 h-3.5" /> Auto-Approve
            </button>
          </div>
        </div>
      </div>

      {/* Model Profiles List */}
      <div className="grid gap-6">
        {llmConfigs.configs.map((config) => {
          const id = config.id;
          const tr = testResults[id];
          const loading = testLoading[id];
          return (
            <div
              key={id}
              className={`bg-slate-800 rounded-2xl border p-6 transition-all duration-300 shadow-xl ${
                config.is_primary ? "border-blue-500/80 shadow-blue-950/20" : "border-slate-700/80"
              }`}
            >
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2.5 rounded-xl ${config.is_primary ? "bg-blue-600 text-white shadow-lg" : "bg-slate-700 text-slate-400"}`}
                  >
                    <Brain className="w-5 h-5 animate-pulse" />
                  </div>
                  <div>
                    <input
                      className="bg-transparent border-none text-lg font-bold text-white focus:outline-none focus:ring-0 p-0 hover:bg-slate-700/20 px-2 py-0.5 rounded cursor-edit"
                      value={config.name}
                      onChange={(e) => updateConfigField(id, "name", e.target.value)}
                      onBlur={() => saveLlmConfigs()}
                      title="Click to rename"
                    />
                    <div className="flex gap-2 items-center mt-1 px-2">
                      {config.is_primary && (
                        <span className="text-[9px] bg-blue-900/60 text-blue-200 px-2 py-0.5 rounded border border-blue-800/40 font-extrabold uppercase tracking-wider">
                          Primary
                        </span>
                      )}
                      {config.is_active ? (
                        <span className="text-[9px] bg-green-900/60 text-green-300 px-2 py-0.5 rounded border border-green-800/40 font-extrabold uppercase tracking-wider">
                          Active
                        </span>
                      ) : (
                        <span className="text-[9px] bg-slate-700 text-slate-400 px-2 py-0.5 rounded font-extrabold uppercase tracking-wider">
                          Disabled
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap shrink-0">
                  <button
                    onClick={() => testConfig(config)}
                    disabled={loading}
                    className="px-3 py-1.5 bg-slate-700/80 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors border border-slate-600"
                  >
                    <Activity className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                    {loading ? "Testing..." : "Test Connection"}
                  </button>
                  {!config.is_primary && (
                    <button
                      onClick={() => setPrimaryConfig(id)}
                      className="px-3 py-1.5 bg-blue-950/60 hover:bg-blue-600 text-blue-300 hover:text-white rounded-lg text-xs font-bold transition-all border border-blue-900"
                    >
                      Set Primary
                    </button>
                  )}
                  <button
                    onClick={() => toggleConfigActive(id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${
                      config.is_active
                        ? "bg-amber-950/40 border-amber-900 text-amber-400 hover:bg-amber-900/40"
                        : "bg-green-950/40 border-green-900 text-green-400 hover:bg-green-900/40"
                    }`}
                  >
                    {config.is_active ? "Deactivate" : "Activate"}
                  </button>
                  <button
                    onClick={() => deleteConfig(id)}
                    className="p-2 text-slate-500 hover:text-red-400 transition-colors hover:bg-red-500/10 rounded-lg"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5">
                    Base Endpoint URL
                  </label>
                  <input
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none font-mono"
                    value={config.baseUrl}
                    onChange={(e) => updateConfigField(id, "baseUrl", e.target.value)}
                    onBlur={() => saveLlmConfigs()}
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5">
                    Model Identifier
                  </label>
                  <input
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none font-mono"
                    value={config.model}
                    onChange={(e) => updateConfigField(id, "model", e.target.value)}
                    onBlur={() => saveLlmConfigs()}
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5">
                    Auth / API Key
                  </label>
                  <input
                    type="password"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none font-mono"
                    value={config.apiKey}
                    onChange={(e) => updateConfigField(id, "apiKey", e.target.value)}
                    onBlur={() => saveLlmConfigs()}
                  />
                </div>
              </div>

              {tr && (
                <div
                  className={`mt-5 p-3.5 rounded-xl flex items-center justify-between text-xs border ${
                    tr.status === "success"
                      ? "bg-green-500/10 border-green-500/15 text-green-400"
                      : "bg-red-500/10 border-red-500/15 text-red-400"
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    {tr.status === "success" ? (
                      <CheckCircle className="w-4 h-4" />
                    ) : (
                      <XCircle className="w-4 h-4" />
                    )}
                    {tr.status === "success"
                      ? "Model reachable and validated!"
                      : `Connection failed: ${tr.error}`}
                  </div>
                  {tr.status === "success" && (
                    <div className="font-mono bg-slate-950/40 px-3 py-1 rounded-lg border border-slate-900 font-bold">
                      Latency: {tr.latency}ms
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={addConfig}
        className="w-full py-4 border-2 border-dashed border-slate-700 rounded-2xl text-slate-500 hover:text-blue-400 hover:border-blue-500/50 hover:bg-blue-500/5 transition-all font-bold flex items-center justify-center gap-2"
      >
        <Plus className="w-5 h-5" /> Add Cognitive Profile
      </button>

      {/* Synapse Engine Settings */}
      <div className="mt-12">
        <h3 className="text-xl font-bold text-blue-400 mb-4 flex items-center gap-2.5 border-b border-slate-800 pb-3">
          <Brain className="w-6 h-6" /> Synapse Engine Settings
        </h3>
        <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6 space-y-6 shadow-xl">
          <div className="flex items-center justify-between p-4 bg-slate-900/40 rounded-xl border border-slate-700/50">
            <div>
              <div className="font-bold text-white mb-0.5">Engine Dispatched Status</div>
              <div className="text-xs text-slate-400">
                Trigger continuous self-organizing learning maps (Hebbian Long Term Potentiation).
              </div>
            </div>
            <button
              type="button"
              onClick={() =>
                saveSynapseConfig({ ...synapseConfig, enabled: !synapseConfig.enabled })
              }
              className={`px-5 py-2.5 rounded-xl font-bold transition-all ${
                synapseConfig.enabled
                  ? "bg-green-600 text-white shadow-lg shadow-green-950/20"
                  : "bg-slate-700 text-slate-400"
              }`}
            >
              {synapseConfig.enabled ? "Enabled" : "Disabled"}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
            <div className="space-y-6">
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Learning Rate (LTP)
                  </label>
                  <span className="text-blue-400 font-mono text-xs font-bold">
                    {synapseConfig.learning_rate}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.01"
                  max="0.5"
                  step="0.01"
                  value={synapseConfig.learning_rate}
                  onChange={(e) =>
                    saveSynapseConfig({
                      ...synapseConfig,
                      learning_rate: parseFloat(e.target.value),
                    })
                  }
                  className="w-full h-2 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="text-[10px] text-slate-500 mt-2">
                  Determines how quickly links strengthen when co-retrieved (Hebbian rate).
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Consolidation Threshold
                  </label>
                  <span className="text-blue-400 font-mono text-xs font-bold">
                    {synapseConfig.consolidation_threshold}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="0.95"
                  step="0.01"
                  value={synapseConfig.consolidation_threshold}
                  onChange={(e) =>
                    saveSynapseConfig({
                      ...synapseConfig,
                      consolidation_threshold: parseFloat(e.target.value),
                    })
                  }
                  className="w-full h-2 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="text-[10px] text-slate-500 mt-2">
                  Minimum weight required for a cluster to trigger higher-order consolidation.
                </div>
              </div>
            </div>
            <div className="space-y-6">
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Decay Rate
                  </label>
                  <span className="text-blue-400 font-mono text-xs font-bold">
                    {synapseConfig.decay_rate}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.9"
                  max="0.999"
                  step="0.001"
                  value={synapseConfig.decay_rate}
                  onChange={(e) =>
                    saveSynapseConfig({ ...synapseConfig, decay_rate: parseFloat(e.target.value) })
                  }
                  className="w-full h-2 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="text-[10px] text-slate-500 mt-2">
                  Rate at which inactive connections decay without co-retrieval (LTD).
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Prune Threshold
                  </label>
                  <span className="text-blue-400 font-mono text-xs font-bold">
                    {synapseConfig.prune_threshold}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.01"
                  max="0.2"
                  step="0.01"
                  value={synapseConfig.prune_threshold}
                  onChange={(e) =>
                    saveSynapseConfig({
                      ...synapseConfig,
                      prune_threshold: parseFloat(e.target.value),
                    })
                  }
                  className="w-full h-2 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="text-[10px] text-slate-500 mt-2">
                  Synaptic edge weight below which connections are pruned permanently.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
