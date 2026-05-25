import React, { useEffect, useRef, useMemo } from "react";
import ForceGraph3D from "react-force-graph-3d";
import { Search, X, Trash2, Database } from "lucide-react";
import { useMemoryStore } from "../store/useMemoryStore";
import LoadingSpinner from "./LoadingSpinner";

export default function GraphViewer() {
  const fgRef = useRef();

  const {
    graphData,
    searchQuery,
    setSearchQuery,
    selectedNode,
    setSelectedNode,
    selectedProjectId,
    setSelectedProjectId,
    visualMultiplier,
    setVisualMultiplier,
    graphNodeFilter,
    setGraphNodeFilter,
    projects,
    fetchProjects,
    fetchGraphData,
    deleteMemory,
    pruneMemories,
    loadingStates,
  } = useMemoryStore();

  // Fetch initial data for projects and graph
  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData, selectedProjectId, visualMultiplier]);

  const filteredGraphData = useMemo(() => {
    let nodes = graphData.nodes.filter((n) => graphNodeFilter[n.type] !== false);
    if (searchQuery) {
      const lowerQuery = searchQuery.toLowerCase();
      nodes = nodes.filter(
        (n) =>
          n.content.toLowerCase().includes(lowerQuery) || n.type.toLowerCase().includes(lowerQuery)
      );
    }
    const nodeIds = new Set(nodes.map((n) => n.id));
    const links = graphData.links.filter(
      (l) => nodeIds.has(l.source.id || l.source) && nodeIds.has(l.target.id || l.target)
    );
    return { nodes, links };
  }, [graphData, searchQuery, graphNodeFilter]);

  const nodeColors = {
    episodic: "#475569",
    semantic: "#34d399",
    entity: "#f472b6",
  };

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden relative flex min-h-[500px]">
      {/* Overlay Panels */}
      <div className="absolute top-4 left-4 z-10 space-y-4 max-w-sm w-full pointer-events-none">
        <div className="bg-slate-900/95 p-4 rounded-xl backdrop-blur-md pointer-events-auto border border-slate-700 shadow-2xl space-y-4">
          <h2 className="text-lg font-bold flex items-center gap-2 text-blue-400">
            <Database className="w-5 h-5" /> Memory Explorer
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1.5">
                Simulation Context
              </label>
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="">Global Overview (All)</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1.5">
                Search Nodes
              </label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search names/topics..."
                  className="w-full bg-slate-800 border border-slate-600 rounded pl-9 pr-2 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>
        </div>
        {searchQuery && (
          <div className="bg-slate-900/90 p-3 rounded-xl backdrop-blur-sm pointer-events-auto border border-slate-700 flex justify-between items-center text-xs text-slate-400 shadow-lg">
            <span>Found {filteredGraphData.nodes.length} nodes</span>
            <button
              onClick={pruneMemories}
              className="text-red-400 hover:text-red-300 flex items-center gap-1 font-semibold transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Prune Matches
            </button>
          </div>
        )}
      </div>

      {selectedNode && (
        <div className="absolute top-4 right-4 z-10 w-80 bg-slate-900/95 p-5 rounded-xl backdrop-blur-md pointer-events-auto border border-slate-700 shadow-2xl max-h-[400px] overflow-y-auto animate-in slide-in-from-right duration-300">
          <div className="flex justify-between items-start mb-3">
            <h3 className="font-bold text-blue-400 text-sm">Memory Details</h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="text-sm text-slate-300 mb-4 whitespace-pre-wrap leading-relaxed">
            {selectedNode.full_content || selectedNode.content}
          </div>
          <div className="flex justify-between items-center text-xs text-slate-500 pt-3 border-t border-slate-800">
            <span className="capitalize px-2.5 py-1 bg-slate-800 rounded font-semibold text-slate-300">
              {selectedNode.type}
            </span>
            <button
              onClick={() => deleteMemory(selectedNode.id)}
              className="text-red-400 hover:text-red-300 flex items-center gap-1 px-2.5 py-1 hover:bg-red-500/10 rounded transition-colors font-semibold"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </div>
        </div>
      )}

      <div className="absolute bottom-4 right-4 z-10 pointer-events-none">
        <div className="bg-slate-900/95 p-4 rounded-xl backdrop-blur-md pointer-events-auto border border-slate-700 min-w-[220px] space-y-3 shadow-2xl">
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-semibold text-slate-300">Visual Zoom</label>
            <span className="text-xs text-blue-400 font-mono font-bold">
              {visualMultiplier.toFixed(1)}x
            </span>
          </div>
          <input
            type="range"
            min="1"
            max="10"
            step="0.5"
            value={visualMultiplier}
            onChange={(e) => setVisualMultiplier(parseFloat(e.target.value))}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
          <div className="border-t border-slate-800 pt-3">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
              Node Types
            </div>
            {[
              ["episodic", nodeColors.episodic, "Episodic"],
              ["semantic", nodeColors.semantic, "Assertion"],
              ["entity", nodeColors.entity, "Entity"],
            ].map(([type, color, label]) => (
              <label
                key={type}
                className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer mb-2 hover:text-white transition-colors"
              >
                <input
                  type="checkbox"
                  checked={graphNodeFilter[type] !== false}
                  onChange={(e) => setGraphNodeFilter((f) => ({ ...f, [type]: e.target.checked }))}
                  className="rounded border-slate-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-slate-900 bg-slate-800"
                />
                <span
                  className="w-3 h-3 rounded-full inline-block"
                  style={{ backgroundColor: color }}
                />
                <span className="font-medium">{label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="flex-1 w-full h-full relative">
        {loadingStates.graph && (
          <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm z-20 flex items-center justify-center">
            <LoadingSpinner message="Rendering 3D Cognitive Synapses..." />
          </div>
        )}
        <ForceGraph3D
          ref={fgRef}
          graphData={filteredGraphData}
          nodeLabel="full_content"
          nodeColor={(node) => node.color || nodeColors[node.type] || "#475569"}
          nodeVal={(node) => node.val || 1.5}
          linkOpacity={0.6}
          backgroundColor="#0f172a"
          linkDirectionalArrowLength={2.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.15}
          onNodeClick={(node) => setSelectedNode(node)}
        />
      </div>
    </div>
  );
}
