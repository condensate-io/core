import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import { Key, Database, Brain, Activity, Plus, Trash2, Search, X, Filter, Play, Clock, FileText, ShieldAlert, CheckCircle, XCircle, List, Tag, Cpu, RefreshCw, AlertCircle } from 'lucide-react';
import Login from './Login';
import CondensationPlayground from './components/CondensationPlayground';

function App() {
    const [auth, setAuth] = useState(localStorage.getItem('admin_auth') || null);
    const [activeTab, setActiveTab] = useState('dashboard');
    const [stats, setStats] = useState({ total_keys: 0, total_projects: 0, total_memories: 0, total_learnings: 0 });
    const [keys, setKeys] = useState([]);
    const [sources, setSources] = useState([]);
    const [learnings, setLearnings] = useState([]);
    const [pendingAssertions, setPendingAssertions] = useState([]);
    const [reviewFilter, setReviewFilter] = useState({ minInstruction: 0, minSafety: 0 });
    const [reviewLoading, setReviewLoading] = useState(false);
    const [pendingCount, setPendingCount] = useState(0);
    const [graphData, setGraphData] = useState({ nodes: [], links: [] });
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedNode, setSelectedNode] = useState(null);
    const [newApiKey, setNewApiKey] = useState(null);
    const [showKeyModal, setShowKeyModal] = useState(false);
    const [visualMultiplier, setVisualMultiplier] = useState(1.0);
    const [graphNodeFilter, setGraphNodeFilter] = useState({ episodic: true, semantic: true, entity: true });
    const [memories, setMemories] = useState([]);
    const [entities, setEntities] = useState([]);
    const [jobs, setJobs] = useState([]);
    const [jobsLoading, setJobsLoading] = useState(false);
    const [ontologySubTab, setOntologySubTab] = useState('assertions');
    const [llmConfig, setLlmConfig] = useState({
        baseUrl: 'http://localhost:11434/v1',
        model: 'phi3',
        apiKey: 'ollama'
    });
    const fgRef = useRef();

    const headers = useMemo(() => ({
        'Authorization': auth,
        'Content-Type': 'application/json'
    }), [auth]);

    useEffect(() => {
        if (!auth) return;
        fetchData();
    }, [auth, activeTab, visualMultiplier]);

    // Auto-poll jobs every 5s
    useEffect(() => {
        if (!auth) return;
        fetchJobs();
        const interval = setInterval(fetchJobs, 5000);
        return () => clearInterval(interval);
    }, [auth]);

    const fetchData = () => {
        fetch('/api/admin/stats', { headers }).then(res => {
            if (res.status === 401) setAuth(null);
            return res.json();
        }).then(setStats).catch(console.error);

        if (activeTab === 'keys') {
            fetch('/api/admin/keys', { headers }).then(res => res.json()).then(setKeys).catch(console.error);
        }

        if (activeTab === 'sources') {
            fetch('/api/admin/sources', { headers }).then(res => res.json()).then(setSources).catch(console.error);
        }

        if (activeTab === 'ontology') {
            fetch('/api/admin/learnings', { headers }).then(res => res.json()).then(setLearnings).catch(console.error);
            fetch('/api/admin/entities', { headers }).then(res => res.json()).then(setEntities).catch(console.error);
        }

        if (activeTab === 'memories') {
            fetch('/api/admin/memories?limit=200', { headers }).then(res => res.json()).then(setMemories).catch(console.error);
        }

        if (activeTab === 'jobs' || true) { // Always fetch jobs to keep sidebar count fresh
            fetchJobs();
        }

        if (activeTab === 'review') {
            fetchPendingAssertions();
        }

        if (activeTab === 'dashboard') {
            fetch(`/api/admin/vectors?visual_multiplier=${visualMultiplier}`, { headers }).then(res => res.json()).then(data => {
                if (data.nodes && data.links) {
                    setGraphData(data);
                } else {
                    setGraphData({ nodes: [], links: [] });
                }
            }).catch(console.error);
        }
    };

    const handleLogin = (authHeader) => {
        localStorage.setItem('admin_auth', authHeader);
        setAuth(authHeader);
    };

    const fetchJobs = async () => {
        setJobsLoading(true);
        try {
            const res = await fetch('/api/admin/jobs?limit=100', { headers });
            const data = await res.json();
            setJobs(data.jobs || []);
        } catch (err) {
            console.error('Failed to fetch jobs', err);
        } finally {
            setJobsLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('admin_auth');
        setAuth(null);
    };

    const createKey = async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const name = formData.get('name');
        const project = formData.get('project');

        const response = await fetch(`/api/admin/keys?name=${name}&project_id=${project}`, {
            method: 'POST',
            headers
        });

        if (response.ok) {
            const data = await response.json();
            setNewApiKey(data.key);
            setShowKeyModal(true);
            fetchData();
        }
        e.target.reset();
    };

    const createSource = async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const type = formData.get('source_type');
        let config = {};

        if (type === 'url') config = { url: formData.get('url') };

        if (type === 'file') {
            const file = formData.get('file_upload');
            if (!file || file.size === 0) {
                alert("Please select a file to upload.");
                return;
            }

            // Upload first
            const uploadData = new FormData();
            uploadData.append('file', file);

            try {
                const uploadRes = await fetch('/api/admin/upload', {
                    method: 'POST',
                    headers: { 'Authorization': auth }, // No Content-Type, let browser set boundary
                    body: uploadData
                });

                if (!uploadRes.ok) throw new Error("Upload failed");
                const uploadJson = await uploadRes.json();
                config = { path: uploadJson.path };
            } catch (err) {
                alert("File upload failed: " + err.message);
                return;
            }
        }

        if (type === 'api') {
            try {
                config = JSON.parse(formData.get('api_config'));
            } catch (err) {
                alert('Invalid JSON for API Config');
                return;
            }
        }

        const payload = {
            name: formData.get('name'),
            project_id: formData.get('project_id'),
            source_type: type,
            configuration: config,
            cron_schedule: formData.get('cron_schedule') || null,
            enabled: true
        };

        const response = await fetch('/api/admin/sources', {
            method: 'POST',
            headers,
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            fetchData();
            e.target.reset();
        } else {
            alert('Failed to create source');
        }
    };

    const triggerSource = async (id) => {
        const response = await fetch(`/api/admin/sources/${id}/trigger`, {
            method: 'POST',
            headers
        });
        if (response.ok) {
            alert('Job triggered successfully');
        } else {
            alert('Failed to trigger job');
        }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(newApiKey);
    };

    const closeKeyModal = () => {
        setShowKeyModal(false);
        setNewApiKey(null);
    };

    const deleteKey = async (key) => {
        if (!confirm('Are you sure you want to delete this key?')) return;
        await fetch(`/api/admin/keys/${key}`, {
            method: 'DELETE',
            headers
        });
        fetchData();
    };

    const deleteMemory = async (id) => {
        if (!confirm('Delete this memory?')) return;
        await fetch(`/api/admin/memories/${id}`, {
            method: 'DELETE',
            headers
        });
        setSelectedNode(null);
        fetchData();
    };

    const pruneMemories = async () => {
        if (!searchQuery) return;
        if (!confirm(`Delete all memories matching "${searchQuery}"?`)) return;

        await fetch('/api/admin/memories/prune', {
            method: 'POST',
            headers,
            body: JSON.stringify({ query: searchQuery, threshold: 0.7 })
        });
        fetchData();
    };

    // Filter graph nodes based on search AND type filter
    const filteredGraphData = useMemo(() => {
        let nodes = graphData.nodes.filter(n => graphNodeFilter[n.type] !== false);
        if (searchQuery) {
            const lowerQuery = searchQuery.toLowerCase();
            nodes = nodes.filter(n =>
                n.content.toLowerCase().includes(lowerQuery) ||
                n.type.toLowerCase().includes(lowerQuery)
            );
        }
        const nodeIds = new Set(nodes.map(n => n.id));
        const links = graphData.links.filter(l =>
            nodeIds.has(l.source.id || l.source) && nodeIds.has(l.target.id || l.target)
        );
        return { nodes, links };
    }, [graphData, searchQuery, graphNodeFilter]);

    // UI Helper for dynamic form fields
    const [sourceType, setSourceType] = useState('url');

    // Playground State
    const [playgroundQuery, setPlaygroundQuery] = useState('');
    const [playgroundResult, setPlaygroundResult] = useState(null);
    const [playgroundLoading, setPlaygroundLoading] = useState(false);

    const handlePlaygroundSubmit = async (e) => {
        e.preventDefault();
        setPlaygroundLoading(true);
        setPlaygroundResult(null);
        try {
            // Use first project found or default
            const pid = keys.length > 0 ? keys[0].project_id : "default-project";

            const res = await fetch('/api/admin/playground/retrieve', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    project_id: pid,
                    query: playgroundQuery,
                    skip_llm: false,
                    llm_config: llmConfig
                })
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

    const fetchPendingAssertions = async () => {
        setReviewLoading(true);
        try {
            const params = new URLSearchParams();
            if (reviewFilter.minInstruction > 0) params.set('min_instruction_score', reviewFilter.minInstruction);
            if (reviewFilter.minSafety > 0) params.set('min_safety_score', reviewFilter.minSafety);
            const res = await fetch(`/api/admin/review/assertions/pending?${params}`, { headers });
            const data = await res.json();
            setPendingAssertions(data.assertions || []);
            setPendingCount(data.total || 0);
        } catch (err) {
            console.error(err);
        } finally {
            setReviewLoading(false);
        }
    };

    const approveAssertion = async (id) => {
        await fetch(`/api/admin/review/assertions/${id}/approve`, {
            method: 'POST', headers,
            body: JSON.stringify({ reviewed_by: 'admin' })
        });
        fetchPendingAssertions();
    };

    const rejectAssertion = async (id, reason) => {
        const r = reason || prompt('Rejection reason:');
        if (!r) return;
        await fetch(`/api/admin/review/assertions/${id}/reject`, {
            method: 'POST', headers,
            body: JSON.stringify({ reviewed_by: 'admin', rejection_reason: r })
        });
        fetchPendingAssertions();
    };

    const bulkApproveAll = async () => {
        const ids = pendingAssertions.map(a => a.id);
        if (!ids.length) return;
        await fetch('/api/admin/review/assertions/bulk-approve', {
            method: 'POST', headers,
            body: JSON.stringify({ assertion_ids: ids, reviewed_by: 'admin' })
        });
        fetchPendingAssertions();
    };

    if (!auth) {
        return <Login onLogin={handleLogin} />;
    }

    return (
        <div className="flex h-screen bg-slate-900 text-slate-100 font-sans">
            {/* API Key Modal */}
            {showKeyModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 max-w-lg w-full mx-4">
                        <h2 className="text-xl font-bold mb-4 text-blue-400">API Key Generated!</h2>
                        <p className="text-sm text-slate-300 mb-4">
                            ⚠️ <strong>Important:</strong> Copy this key now. For security reasons, it won't be shown again.
                        </p>
                        <div className="bg-slate-900 p-4 rounded border border-slate-600 mb-4 font-mono text-sm break-all">
                            {newApiKey}
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={copyToClipboard}
                                className="flex-1 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-white font-semibold transition-colors"
                            >
                                📋 Copy to Clipboard
                            </button>
                            <button
                                onClick={closeKeyModal}
                                className="flex-1 bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded text-white font-semibold transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Sidebar */}
            <div className="w-64 bg-slate-800 border-r border-slate-700 p-4 flex flex-col">
                <h1 className="text-xl font-bold mb-8 text-blue-400 flex items-center gap-2">
                    <Brain className="w-6 h-6" /> Memory Server
                </h1>
                <nav className="space-y-2 flex-1">
                    <button onClick={() => setActiveTab('dashboard')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'dashboard' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Activity className="w-4 h-4" /> Dashboard
                    </button>
                    <button onClick={() => setActiveTab('playground')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'playground' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Play className="w-4 h-4" /> Router (Traffic)
                    </button>
                    <button onClick={() => setActiveTab('condenser')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'condenser' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Filter className="w-4 h-4" /> Condenser (Algo)
                    </button>
                    <button onClick={() => setActiveTab('memories')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'memories' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <List className="w-4 h-4" /> Memories
                    </button>
                    <button onClick={() => setActiveTab('sources')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'sources' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Database className="w-4 h-4" /> Data Sources
                    </button>
                    <button onClick={() => setActiveTab('ontology')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'ontology' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Brain className="w-4 h-4" /> Ontology
                    </button>
                    <button onClick={() => setActiveTab('keys')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'keys' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Key className="w-4 h-4" /> API Keys
                    </button>
                    <button onClick={() => setActiveTab('review')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'review' ? 'bg-amber-600' : 'hover:bg-slate-700'}`}>
                        <ShieldAlert className="w-4 h-4" /> Review Queue
                        {pendingCount > 0 && <span className="ml-auto bg-amber-500 text-black text-xs font-bold px-1.5 py-0.5 rounded-full">{pendingCount}</span>}
                    </button>
                    <button onClick={() => setActiveTab('jobs')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'jobs' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Cpu className="w-4 h-4" /> Jobs
                        {jobs.filter(j => j.status === 'running').length > 0 && (
                            <span className="ml-auto bg-blue-400 text-black text-xs font-bold px-1.5 py-0.5 rounded-full animate-pulse">
                                {jobs.filter(j => j.status === 'running').length}
                            </span>
                        )}
                    </button>
                    <button onClick={() => setActiveTab('settings')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'settings' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Filter className="w-4 h-4" /> LLM Settings
                    </button>
                </nav>
                <button onClick={handleLogout} className="text-slate-400 hover:text-white text-sm mt-auto">
                    Logout
                </button>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-8 overflow-hidden flex flex-col">
                {activeTab === 'dashboard' && (
                    <div className="flex flex-col h-full gap-8">
                        {/* Stats Cards */}
                        <div className="grid grid-cols-7 gap-3 flex-shrink-0">
                            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
                                <div className="text-slate-400 text-xs">Episodic Items</div>
                                <div className="text-2xl font-bold">{stats.total_memories}</div>
                            </div>
                            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
                                <div className="text-slate-400 text-xs">Assertions</div>
                                <div className="text-2xl font-bold">{stats.total_learnings}</div>
                            </div>
                            <div className="bg-slate-800 p-4 rounded-lg border border-emerald-800">
                                <div className="text-emerald-400 text-xs">Entities</div>
                                <div className="text-2xl font-bold text-emerald-300">{stats.total_entities ?? 0}</div>
                            </div>
                            <div className="bg-slate-800 p-4 rounded-lg border border-purple-800">
                                <div className="text-purple-400 text-xs">Relations</div>
                                <div className="text-2xl font-bold text-purple-300">{stats.total_relations ?? 0}</div>
                            </div>
                            <div className="bg-slate-800 p-4 rounded-lg border border-amber-800">
                                <div className="text-amber-400 text-xs">Pending Review</div>
                                <div className="text-2xl font-bold text-amber-300">{stats.pending_review ?? 0}</div>
                            </div>
                            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
                                <div className="text-slate-400 text-xs">Projects</div>
                                <div className="text-2xl font-bold">{stats.total_projects}</div>
                            </div>
                            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
                                <div className="text-slate-400 text-xs">API Keys</div>
                                <div className="text-2xl font-bold">{stats.total_keys}</div>
                            </div>
                        </div>

                        {/* Vector Visualization */}
                        <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden relative flex">
                            <div className="absolute top-4 left-4 z-10 space-y-4 max-w-sm w-full pointer-events-none">
                                <div className="bg-slate-900/90 p-4 rounded backdrop-blur-sm pointer-events-auto border border-slate-700">
                                    <h2 className="text-lg font-semibold mb-2">Memory Explorer</h2>
                                    <div className="flex gap-2 mb-2">
                                        <div className="relative flex-1">
                                            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                                            <input
                                                type="text"
                                                value={searchQuery}
                                                onChange={e => setSearchQuery(e.target.value)}
                                                placeholder="Search topics..."
                                                className="w-full bg-slate-800 border border-slate-600 rounded pl-9 pr-2 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                            />
                                        </div>
                                    </div>
                                    {searchQuery && (
                                        <div className="flex justify-between items-center text-xs text-slate-400">
                                            <span>Found {filteredGraphData.nodes.length} nodes</span>
                                            <button
                                                onClick={pruneMemories}
                                                className="text-red-400 hover:text-red-300 flex items-center gap-1"
                                            >
                                                <Trash2 className="w-3 h-3" /> Prune Matches
                                            </button>
                                        </div>
                                    )}
                                </div>

                                {selectedNode && (
                                    <div className="bg-slate-900/90 p-4 rounded backdrop-blur-sm pointer-events-auto border border-slate-700 max-h-[400px] overflow-y-auto">
                                        <div className="flex justify-between items-start mb-2">
                                            <h3 className="font-semibold text-blue-400">Memory Details</h3>
                                            <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
                                        </div>
                                        <div className="text-sm text-slate-300 mb-4">
                                            {selectedNode.full_content || selectedNode.content}
                                        </div>

                                        {selectedNode.provenance && (
                                            <div className="mb-4">
                                                <h4 className="text-xs font-bold text-slate-500 uppercase mb-1">Proof Envelope</h4>
                                                <pre className="bg-slate-950 p-2 rounded text-[10px] text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                                                    {JSON.stringify(selectedNode.provenance, null, 2)}
                                                </pre>
                                            </div>
                                        )}

                                        <div className="flex justify-between items-center text-xs text-slate-500">
                                            <span className="capitalize px-2 py-1 bg-slate-800 rounded">{selectedNode.type}</span>
                                            <button
                                                onClick={() => deleteMemory(selectedNode.id)}
                                                className="text-red-400 hover:text-red-300 flex items-center gap-1 px-2 py-1 hover:bg-slate-800 rounded transition-colors"
                                            >
                                                <Trash2 className="w-3 h-3" /> Delete
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Graph Legend + Type Filter - Bottom Right */}
                            <div className="absolute bottom-4 right-4 z-10 pointer-events-none">
                                <div className="bg-slate-900/90 p-4 rounded backdrop-blur-sm pointer-events-auto border border-slate-700 min-w-[220px] space-y-3">
                                    <div className="flex items-center justify-between mb-1">
                                        <label className="text-sm font-semibold text-slate-300">Visual Zoom</label>
                                        <span className="text-xs text-blue-400 font-mono">{visualMultiplier.toFixed(1)}x</span>
                                    </div>
                                    <input
                                        type="range" min="1" max="10" step="0.5"
                                        value={visualMultiplier}
                                        onChange={e => setVisualMultiplier(parseFloat(e.target.value))}
                                        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                                        style={{ background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${((visualMultiplier - 1) / 9) * 100}%, #475569 ${((visualMultiplier - 1) / 9) * 100}%, #475569 100%)` }}
                                    />
                                    <div className="border-t border-slate-700 pt-3">
                                        <div className="text-xs font-semibold text-slate-400 uppercase mb-2">Node Types</div>
                                        {[['episodic', '#60a5fa', 'Episodic'], ['semantic', '#34d399', 'Assertion'], ['entity', '#f472b6', 'Entity']].map(([type, color, label]) => (
                                            <label key={type} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer mb-1">
                                                <input
                                                    type="checkbox"
                                                    checked={graphNodeFilter[type] !== false}
                                                    onChange={e => setGraphNodeFilter(f => ({ ...f, [type]: e.target.checked }))}
                                                    className="accent-blue-500"
                                                />
                                                <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
                                                {label}
                                            </label>
                                        ))}
                                    </div>
                                    <div className="border-t border-slate-700 pt-2">
                                        <div className="text-xs font-semibold text-slate-400 uppercase mb-1">Edge Types</div>
                                        {[['co_occurs', '#94a3b8', 'Co-occurrence'], ['refers_to', '#a78bfa', 'Refers To'], ['evidence', '#fbbf24', 'Evidence']].map(([type, color, label]) => (
                                            <div key={type} className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                                                <span className="w-6 h-0.5 inline-block" style={{ backgroundColor: color }} />
                                                {label}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1">
                                <ForceGraph3D
                                    ref={fgRef}
                                    graphData={filteredGraphData}
                                    nodeLabel="content"
                                    nodeColor={node => node.type === 'episodic' ? '#60a5fa' : node.type === 'semantic' ? '#34d399' : '#f472b6'}
                                    nodeVal="val"
                                    linkWidth={link => (link.value || 0.5) * 2}
                                    linkColor={link => link.type === 'refers_to' ? '#a78bfa' : link.type === 'evidence' ? '#fbbf24' : '#94a3b8'}
                                    linkOpacity={0.6}
                                    linkDistance={link => link.distance || 30}
                                    backgroundColor="#1e293b"
                                    controlPointerInteraction={true}
                                    onNodeClick={node => {
                                        setSelectedNode(node);
                                        const distance = 40;
                                        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
                                        fgRef.current.cameraPosition(
                                            { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
                                            node,
                                            3000
                                        );
                                    }}
                                />
                            </div>
                        </div>
                    </div>
                )}


                {activeTab === 'playground' && (
                    <div className="space-y-8 overflow-auto h-full max-w-4xl mx-auto w-full">
                        <div className="text-center mb-8">
                            <h2 className="text-2xl font-bold text-blue-400 mb-2">Traffic Control Playground</h2>
                            <p className="text-slate-400">Test the router logic. Verify that LLMs are skipped when not needed.</p>
                        </div>

                        <div className="bg-slate-800 p-8 rounded-xl border border-slate-700 shadow-2xl">
                            <form onSubmit={handlePlaygroundSubmit} className="flex gap-4 mb-8">
                                <input
                                    type="text"
                                    value={playgroundQuery}
                                    onChange={(e) => setPlaygroundQuery(e.target.value)}
                                    placeholder="Ask your memory system (e.g., 'What is the production deployment policy?')"
                                    className="flex-1 bg-slate-900 border border-slate-600 rounded px-4 py-3 text-lg text-white focus:outline-none focus:border-blue-500"
                                />
                                <button
                                    type="submit"
                                    disabled={playgroundLoading}
                                    className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded text-white font-bold transition-all disabled:opacity-50"
                                >
                                    {playgroundLoading ? 'Routing...' : 'Test Route'}
                                </button>
                            </form>

                            {playgroundResult && (
                                <div className="space-y-6 animate-fade-in-up">
                                    <div className="flex gap-4">
                                        <div className="bg-slate-900 p-4 rounded border border-slate-700 flex-1">
                                            <div className="text-xs text-slate-500 uppercase font-bold mb-1">Strategy Selected</div>
                                            <div className="text-xl font-mono text-purple-400">{playgroundResult.strategy}</div>
                                        </div>
                                        <div className="bg-slate-900 p-4 rounded border border-slate-700 flex-1">
                                            <div className="text-xs text-slate-500 uppercase font-bold mb-1">Traffic Control</div>
                                            <div className="text-xl font-mono text-emerald-400">LLM ACTIVE</div>
                                        </div>
                                    </div>

                                    <div className="bg-slate-900 p-6 rounded border border-slate-700">
                                        <div className="text-xs text-slate-500 uppercase font-bold mb-2">System Response (Deterministic)</div>
                                        <pre className="text-slate-300 font-mono text-sm whitespace-pre-wrap">{playgroundResult.answer}</pre>
                                    </div>

                                    {playgroundResult.sources.length > 0 && (
                                        <div className="bg-slate-900 p-6 rounded border border-slate-700">
                                            <div className="text-xs text-slate-500 uppercase font-bold mb-2">Sources Activated</div>
                                            <div className="flex flex-wrap gap-2">
                                                {playgroundResult.sources.map(s => (
                                                    <span key={s} className="px-2 py-1 bg-slate-800 rounded text-xs text-blue-300 border border-slate-700 font-mono">
                                                        {s}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'ontology' && (
                    <div className="space-y-6 overflow-auto h-full">
                        <div className="flex justify-between items-center">
                            <h2 className="text-2xl font-bold text-emerald-400">Structured Ontology</h2>
                            <div className="flex gap-2">
                                <button onClick={() => setOntologySubTab('assertions')} className={`px-4 py-1.5 rounded text-sm font-semibold transition-colors ${ontologySubTab === 'assertions' ? 'bg-emerald-700 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>
                                    Assertions ({learnings.length})
                                </button>
                                <button onClick={() => setOntologySubTab('entities')} className={`px-4 py-1.5 rounded text-sm font-semibold transition-colors ${ontologySubTab === 'entities' ? 'bg-purple-700 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>
                                    Entities ({entities.length})
                                </button>
                            </div>
                        </div>

                        {ontologySubTab === 'assertions' && (
                            <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                                <table className="w-full text-left">
                                    <thead className="bg-slate-900 text-slate-400">
                                        <tr>
                                            <th className="p-4">Subject</th>
                                            <th className="p-4">Predicate</th>
                                            <th className="p-4">Object</th>
                                            <th className="p-4">Confidence</th>
                                            <th className="p-4">Status</th>
                                            <th className="p-4">Created</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700">
                                        {learnings.map(l => (
                                            <tr key={l.id} className="hover:bg-slate-700/50 transition-colors">
                                                <td className="p-4 font-mono text-blue-300 text-sm">{l.subject_text || l.statement?.split(' ')[0] || '—'}</td>
                                                <td className="p-4 text-slate-400 text-sm uppercase text-xs">{l.predicate || '—'}</td>
                                                <td className="p-4 font-mono text-purple-300 text-sm">{l.object_text || '—'}</td>
                                                <td className="p-4">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                                                            <div className="h-full bg-emerald-500" style={{ width: `${(l.confidence || 0) * 100}%` }} />
                                                        </div>
                                                        <span className="text-xs text-slate-400">{((l.confidence || 0) * 100).toFixed(0)}%</span>
                                                    </div>
                                                </td>
                                                <td className="p-4">
                                                    <span className={`px-2 py-1 rounded text-xs uppercase font-bold ${l.status === 'active' ? 'bg-green-900 text-green-300' :
                                                        l.status === 'refuted' ? 'bg-red-900 text-red-300' :
                                                            l.status === 'pending_review' ? 'bg-amber-900 text-amber-300' :
                                                                'bg-slate-700 text-slate-300'
                                                        }`}>{l.status}</span>
                                                </td>
                                                <td className="p-4 text-slate-500 text-sm">{l.created_at ? new Date(l.created_at).toLocaleDateString() : '—'}</td>
                                            </tr>
                                        ))}
                                        {learnings.length === 0 && (
                                            <tr><td colSpan="6" className="p-8 text-center text-slate-500">No assertions yet. Run condensation on data sources.</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {ontologySubTab === 'entities' && (
                            <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                                <table className="w-full text-left">
                                    <thead className="bg-slate-900 text-slate-400">
                                        <tr>
                                            <th className="p-4">Canonical Name</th>
                                            <th className="p-4">Type</th>
                                            <th className="p-4">Aliases</th>
                                            <th className="p-4">Project</th>
                                            <th className="p-4">Created</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700">
                                        {entities.map(e => (
                                            <tr key={e.id} className="hover:bg-slate-700/50 transition-colors">
                                                <td className="p-4 font-semibold text-purple-300">{e.canonical_name}</td>
                                                <td className="p-4">
                                                    <span className="px-2 py-1 bg-slate-700 rounded text-xs uppercase font-bold text-slate-300">{e.type}</span>
                                                </td>
                                                <td className="p-4 text-slate-400 text-sm">
                                                    {(e.aliases || []).slice(0, 3).join(', ') || '—'}
                                                </td>
                                                <td className="p-4 font-mono text-xs text-blue-400">{e.project_id?.substring(0, 8)}...</td>
                                                <td className="p-4 text-slate-500 text-sm">{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                                            </tr>
                                        ))}
                                        {entities.length === 0 && (
                                            <tr><td colSpan="5" className="p-8 text-center text-slate-500">No entities extracted yet. Condensation pipeline must run first.</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'condenser' && <CondensationPlayground />}

                {activeTab === 'jobs' && (
                    <div className="space-y-4 overflow-auto h-full">
                        <div className="flex justify-between items-center flex-shrink-0">
                            <div>
                                <h2 className="text-2xl font-bold text-blue-400 flex items-center gap-2">
                                    <Cpu className="w-6 h-6" /> Background Jobs
                                </h2>
                                <p className="text-slate-400 text-sm mt-1">Condensation, data source pulls, and maintenance tasks. Auto-refreshes every 5s.</p>
                            </div>
                            <button
                                onClick={fetchJobs}
                                disabled={jobsLoading}
                                className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm text-slate-200 transition-colors disabled:opacity-50"
                            >
                                <RefreshCw className={`w-4 h-4 ${jobsLoading ? 'animate-spin' : ''}`} />
                                Refresh
                            </button>
                        </div>

                        {/* Summary Bar */}
                        <div className="grid grid-cols-4 gap-3 flex-shrink-0">
                            {[
                                { label: 'Running', color: 'blue', filter: j => j.status === 'running' },
                                { label: 'Success', color: 'emerald', filter: j => j.status === 'success' },
                                { label: 'Error', color: 'red', filter: j => j.status === 'error' },
                                { label: 'Total', color: 'slate', filter: j => true },
                            ].map(({ label, color, filter }) => (
                                <div key={label} className={`bg-slate-800 p-3 rounded-lg border border-${color}-800`}>
                                    <div className={`text-${color}-400 text-xs font-semibold uppercase`}>{label}</div>
                                    <div className={`text-2xl font-bold text-${color}-300`}>{jobs.filter(filter).length}</div>
                                </div>
                            ))}
                        </div>

                        {/* Job List */}
                        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-slate-900 text-slate-400 text-xs uppercase">
                                    <tr>
                                        <th className="px-4 py-3 w-32">Status</th>
                                        <th className="px-4 py-3">Job</th>
                                        <th className="px-4 py-3 w-40">Started</th>
                                        <th className="px-4 py-3 w-28">Duration</th>
                                        <th className="px-4 py-3">Error</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700">
                                    {jobs.map((job, idx) => {
                                        const statusConfig = {
                                            running: { bg: 'bg-blue-900/60', text: 'text-blue-300', label: '⟳ Running', dot: 'bg-blue-400 animate-pulse' },
                                            success: { bg: 'bg-emerald-900/30', text: 'text-emerald-300', label: '✓ Success', dot: 'bg-emerald-400' },
                                            error: { bg: 'bg-red-900/30', text: 'text-red-300', label: '✗ Error', dot: 'bg-red-400' },
                                            skipped: { bg: '', text: 'text-slate-400', label: '— Skipped', dot: 'bg-slate-500' },
                                        }[job.status] || { bg: '', text: 'text-slate-400', label: job.status, dot: 'bg-slate-500' };

                                        return (
                                            <tr key={idx} className={`${statusConfig.bg} hover:bg-slate-700/30 transition-colors`}>
                                                <td className="px-4 py-3">
                                                    <span className={`flex items-center gap-1.5 text-xs font-bold ${statusConfig.text}`}>
                                                        <span className={`w-2 h-2 rounded-full ${statusConfig.dot} inline-block`} />
                                                        {statusConfig.label}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="font-medium text-slate-200">{job.job_name}</div>
                                                    <div className="text-xs text-slate-500 font-mono">{job.job_id}</div>
                                                </td>
                                                <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                                                    {job.started_at ? new Date(job.started_at).toLocaleTimeString() : '—'}
                                                    <div className="text-slate-600">{job.started_at ? new Date(job.started_at).toLocaleDateString() : ''}</div>
                                                </td>
                                                <td className="px-4 py-3 text-slate-400 text-xs font-mono">
                                                    {job.duration_ms != null ? `${(job.duration_ms / 1000).toFixed(1)}s` : job.status === 'running' ? <span className="text-blue-400 animate-pulse">…</span> : '—'}
                                                </td>
                                                <td className="px-4 py-3 text-red-400 text-xs max-w-xs">
                                                    {job.error ? (
                                                        <span className="flex items-start gap-1">
                                                            <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                                            <span className="truncate" title={job.error}>{job.error}</span>
                                                        </span>
                                                    ) : '—'}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {jobs.length === 0 && (
                                        <tr>
                                            <td colSpan="5" className="px-4 py-12 text-center text-slate-500">
                                                <Cpu className="w-8 h-8 mx-auto mb-2 opacity-30" />
                                                No jobs have run yet. Trigger a data source or ingest memories to see activity.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'memories' && (
                    <div className="space-y-6 overflow-auto h-full">
                        <div className="flex justify-between items-center">
                            <h2 className="text-2xl font-bold text-blue-400">Episodic Memory Browser</h2>
                            <span className="text-slate-400 text-sm">{memories.length} items (latest 200)</span>
                        </div>
                        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                            <table className="w-full text-left">
                                <thead className="bg-slate-900 text-slate-400">
                                    <tr>
                                        <th className="p-4">Content</th>
                                        <th className="p-4">Source</th>
                                        <th className="p-4">Project</th>
                                        <th className="p-4">Created</th>
                                        <th className="p-4">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700">
                                    {memories.map(m => (
                                        <tr key={m.id} className="hover:bg-slate-700/50 transition-colors">
                                            <td className="p-4 text-slate-200 text-sm max-w-lg">
                                                <div className="truncate" title={m.content}>{m.content}</div>
                                            </td>
                                            <td className="p-4">
                                                <span className="px-2 py-1 bg-slate-700 rounded text-xs uppercase">{m.type}</span>
                                            </td>
                                            <td className="p-4 font-mono text-xs text-blue-400">{m.project_id?.substring(0, 8)}...</td>
                                            <td className="p-4 text-slate-500 text-sm">{new Date(m.created_at).toLocaleDateString()}</td>
                                            <td className="p-4">
                                                <button
                                                    onClick={() => deleteMemory(m.id)}
                                                    className="text-red-400 hover:text-red-300 p-1 hover:bg-slate-700 rounded transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    {memories.length === 0 && (
                                        <tr><td colSpan="5" className="p-8 text-center text-slate-500">No episodic items stored yet.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'sources' && (
                    <div className="space-y-8 overflow-auto h-full">
                        <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
                            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Plus className="w-4 h-4" /> Add Data Source</h2>
                            <form onSubmit={createSource} className="grid grid-cols-2 gap-6">
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Source Name</label>
                                    <input name="name" required className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" placeholder="e.g. Daily Reports" />
                                </div>
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Project ID</label>
                                    <input name="project_id" required className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" placeholder="Project UUID or Name" />
                                </div>
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Source Type</label>
                                    <select
                                        name="source_type"
                                        value={sourceType}
                                        onChange={e => setSourceType(e.target.value)}
                                        className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white"
                                    >
                                        <option value="url">Web URL</option>
                                        <option value="file">Local File</option>
                                        <option value="api">JSON API</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Cron Schedule (Optional)</label>
                                    <input name="cron_schedule" className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" placeholder="*/30 * * * * (Every 30 mins)" />
                                </div>

                                <div className="col-span-2">
                                    <label className="block text-sm text-slate-400 mb-1">Configuration</label>
                                    {sourceType === 'url' && (
                                        <input name="url" required type="url" className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" placeholder="https://example.com/data" />
                                    )}
                                    {sourceType === 'file' && (
                                        <div className="space-y-2">
                                            <input name="file_upload" type="file" className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" />
                                            <p className="text-xs text-slate-500">Upload a file to act as the source.</p>
                                        </div>
                                    )}
                                    {sourceType === 'api' && (
                                        <textarea name="api_config" className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white h-24 font-mono" placeholder='{"url": "https://api.com", "headers": {"X-Api-Key": "..."}}'></textarea>
                                    )}
                                </div>

                                <div className="col-span-2">
                                    <button type="submit" className="bg-blue-600 hover:bg-blue-500 px-6 py-2 rounded text-white font-semibold">Create Source</button>
                                </div>
                            </form>
                        </div>

                        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                            <table className="w-full text-left">
                                <thead className="bg-slate-900 text-slate-400">
                                    <tr>
                                        <th className="p-4">Name</th>
                                        <th className="p-4">Type</th>
                                        <th className="p-4">Schedule</th>
                                        <th className="p-4">Last Run</th>
                                        <th className="p-4">Status</th>
                                        <th className="p-4">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700">
                                    {sources.map(s => (
                                        <tr key={s.id}>
                                            <td className="p-4 font-medium">{s.name}</td>
                                            <td className="p-4"><span className="px-2 py-1 bg-slate-700 rounded text-xs uppercase">{s.type}</span></td>
                                            <td className="p-4 font-mono text-sm">{s.schedule || 'Manual'}</td>
                                            <td className="p-4 text-slate-400 text-sm">{s.last_run ? new Date(s.last_run).toLocaleString() : 'Never'}</td>
                                            <td className="p-4">
                                                {s.enabled ? (
                                                    <span className="flex items-center gap-1 text-green-400 text-xs"><div className="w-2 h-2 bg-green-500 rounded-full"></div> Active</span>
                                                ) : (
                                                    <span className="flex items-center gap-1 text-slate-500 text-xs"><div className="w-2 h-2 bg-slate-500 rounded-full"></div> Disabled</span>
                                                )}
                                            </td>
                                            <td className="p-4 flex gap-2">
                                                <button
                                                    onClick={() => triggerSource(s.id)}
                                                    className="bg-blue-900/50 hover:bg-blue-900 text-blue-200 p-2 rounded transition-colors"
                                                    title="Run Now"
                                                >
                                                    <Play className="w-4 h-4" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    {sources.length === 0 && (
                                        <tr>
                                            <td colSpan="6" className="p-8 text-center text-slate-500">No data sources configured.</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'keys' && (
                    <div className="space-y-8 overflow-auto h-full">
                        <div className="bg-slate-800 p-6 rounded-lg border border-slate-700">
                            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Plus className="w-4 h-4" /> Generate New Key</h2>
                            <form onSubmit={createKey} className="flex gap-4 items-end">
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Key Name</label>
                                    <input name="name" required className="bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" placeholder="e.g. Cursor Client" />
                                </div>
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Project ID</label>
                                    <input name="project" required className="bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" placeholder="e.g. project-alpha" />
                                </div>
                                <button type="submit" className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-white">Generate</button>
                            </form>
                        </div>

                        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                            <table className="w-full text-left">
                                <thead className="bg-slate-900 text-slate-400">
                                    <tr>
                                        <th className="p-4">Name</th>
                                        <th className="p-4">Project ID</th>
                                        <th className="p-4">Key Prefix</th>
                                        <th className="p-4">Status</th>
                                        <th className="p-4">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700">
                                    {keys.map(k => (
                                        <tr key={k.key}>
                                            <td className="p-4">{k.name}</td>
                                            <td className="p-4 font-mono text-sm text-blue-400">{k.project_id}</td>
                                            <td className="p-4 font-mono text-sm text-slate-500">{k.key.substring(0, 8)}...</td>
                                            <td className="p-4"><span className="bg-green-900 text-green-300 px-2 py-1 rounded text-xs">Active</span></td>
                                            <td className="p-4">
                                                <button
                                                    onClick={() => deleteKey(k.key)}
                                                    className="text-red-400 hover:text-red-300 p-1 hover:bg-slate-700 rounded transition-colors"
                                                    title="Delete Key"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'settings' && (
                    <div className="space-y-8 max-w-2xl mx-auto w-full">
                        <div className="text-center mb-8">
                            <h2 className="text-2xl font-bold text-blue-400 mb-2">Internal LLM Configuration</h2>
                            <p className="text-slate-400">Configure the models used for condensation, retrieval routing, and synthesis.</p>
                        </div>

                        <div className="bg-slate-800 p-8 rounded-xl border border-slate-700 shadow-2xl space-y-6">
                            <div className="grid gap-6">
                                <div>
                                    <label className="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">Base URL</label>
                                    <input
                                        type="text"
                                        value={llmConfig.baseUrl}
                                        onChange={e => setLlmConfig({ ...llmConfig, baseUrl: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-600 rounded px-4 py-3 text-white focus:border-blue-500 outline-none font-mono"
                                        placeholder="http://localhost:11434/v1"
                                    />
                                    <p className="text-xs text-slate-500 mt-2">The endpoint for your LLM provider (Ollama, OpenAI, etc.)</p>
                                </div>

                                <div>
                                    <label className="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">Model Name</label>
                                    <input
                                        type="text"
                                        value={llmConfig.model}
                                        onChange={e => setLlmConfig({ ...llmConfig, model: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-600 rounded px-4 py-3 text-white focus:border-blue-500 outline-none font-mono"
                                        placeholder="phi3"
                                    />
                                    <p className="text-xs text-slate-500 mt-2">The specific model identifier (e.g., phi3, gpt-4o)</p>
                                </div>

                                <div>
                                    <label className="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">API Key</label>
                                    <input
                                        type="password"
                                        value={llmConfig.apiKey}
                                        onChange={e => setLlmConfig({ ...llmConfig, apiKey: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-600 rounded px-4 py-3 text-white focus:border-blue-500 outline-none font-mono"
                                        placeholder="ollama"
                                    />
                                    <p className="text-xs text-slate-500 mt-2">Required for remote providers like OpenAI or Anthropic.</p>
                                </div>
                            </div>

                            <div className="pt-4 flex items-center gap-3">
                                <div className="p-3 bg-blue-500/10 rounded-lg text-blue-400">
                                    <Activity className="w-5 h-5" />
                                </div>
                                <div className="text-sm">
                                    <span className="text-slate-300 block font-semibold">Active Engine</span>
                                    <span className="text-slate-500">Routing and Synthesis will use this configuration immediately.</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'review' && (
                    <div className="flex flex-col h-full gap-6">
                        <div className="flex items-center justify-between flex-shrink-0">
                            <div>
                                <h2 className="text-2xl font-bold flex items-center gap-3">
                                    <ShieldAlert className="w-7 h-7 text-amber-400" />
                                    Assertion Review Queue
                                </h2>
                                <p className="text-slate-400 text-sm mt-1">
                                    Review and approve assertions before they enter long-term memory.
                                </p>
                            </div>
                            <div className="flex gap-3">
                                <button
                                    onClick={fetchPendingAssertions}
                                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors"
                                >
                                    ↻ Refresh
                                </button>
                                <button
                                    onClick={bulkApproveAll}
                                    disabled={!pendingAssertions.length}
                                    className="px-4 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed rounded text-sm font-semibold transition-colors flex items-center gap-2"
                                >
                                    <CheckCircle className="w-4 h-4" /> Approve All ({pendingAssertions.length})
                                </button>
                            </div>
                        </div>

                        {/* Filters */}
                        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 flex-shrink-0">
                            <h3 className="text-sm font-semibold text-slate-300 mb-3">Filter by Guardrail Score</h3>
                            <div className="flex gap-6 items-center">
                                <label className="flex items-center gap-3 text-sm text-slate-400">
                                    <span className="w-36">Min Instruction Score</span>
                                    <input
                                        type="range" min="0" max="1" step="0.1"
                                        value={reviewFilter.minInstruction}
                                        onChange={e => setReviewFilter({ ...reviewFilter, minInstruction: parseFloat(e.target.value) })}
                                        className="w-32 accent-amber-500"
                                    />
                                    <span className="text-amber-400 font-mono w-8">{reviewFilter.minInstruction.toFixed(1)}</span>
                                </label>
                                <label className="flex items-center gap-3 text-sm text-slate-400">
                                    <span className="w-36">Min Safety Score</span>
                                    <input
                                        type="range" min="0" max="1" step="0.1"
                                        value={reviewFilter.minSafety}
                                        onChange={e => setReviewFilter({ ...reviewFilter, minSafety: parseFloat(e.target.value) })}
                                        className="w-32 accent-red-500"
                                    />
                                    <span className="text-red-400 font-mono w-8">{reviewFilter.minSafety.toFixed(1)}</span>
                                </label>
                                <button
                                    onClick={fetchPendingAssertions}
                                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm transition-colors"
                                >
                                    Apply
                                </button>
                            </div>
                        </div>

                        {/* Assertion List */}
                        <div className="flex-1 overflow-y-auto space-y-3">
                            {reviewLoading && (
                                <div className="text-center text-slate-400 py-12">Loading pending assertions...</div>
                            )}
                            {!reviewLoading && pendingAssertions.length === 0 && (
                                <div className="text-center py-16 bg-slate-800 rounded-lg border border-slate-700">
                                    <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
                                    <p className="text-slate-300 font-semibold">All caught up!</p>
                                    <p className="text-slate-500 text-sm mt-1">No assertions pending review.</p>
                                </div>
                            )}
                            {pendingAssertions.map(assertion => {
                                const instrScore = assertion.instruction_score || 0;
                                const safetyScore = assertion.safety_score || 0;
                                const isFlagged = instrScore >= 0.3 || safetyScore >= 0.4;
                                return (
                                    <div
                                        key={assertion.id}
                                        className={`bg-slate-800 rounded-lg border p-4 ${isFlagged ? 'border-amber-600/60' : 'border-slate-700'}`}
                                    >
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex-1 min-w-0">
                                                {/* Assertion Triple */}
                                                <div className="flex items-center gap-2 flex-wrap mb-3">
                                                    <span className="bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded text-sm font-mono">{assertion.subject_text || '—'}</span>
                                                    <span className="text-slate-500 text-xs font-semibold uppercase">{assertion.predicate}</span>
                                                    <span className="bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded text-sm font-mono">{assertion.object_text || '—'}</span>
                                                    <span className="text-slate-500 text-xs ml-2">conf: {(assertion.confidence || 0).toFixed(2)}</span>
                                                </div>

                                                {/* Guardrail Scores */}
                                                <div className="flex gap-4 text-xs">
                                                    <div className="flex items-center gap-1.5">
                                                        <span className="text-slate-500">Instruction:</span>
                                                        <div className="w-20 bg-slate-700 rounded-full h-1.5">
                                                            <div
                                                                className="h-1.5 rounded-full transition-all"
                                                                style={{
                                                                    width: `${instrScore * 100}%`,
                                                                    backgroundColor: instrScore > 0.5 ? '#ef4444' : instrScore > 0.3 ? '#f59e0b' : '#22c55e'
                                                                }}
                                                            />
                                                        </div>
                                                        <span className={`font-mono ${instrScore > 0.5 ? 'text-red-400' : instrScore > 0.3 ? 'text-amber-400' : 'text-green-400'}`}>
                                                            {instrScore.toFixed(2)}
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center gap-1.5">
                                                        <span className="text-slate-500">Safety:</span>
                                                        <div className="w-20 bg-slate-700 rounded-full h-1.5">
                                                            <div
                                                                className="h-1.5 rounded-full transition-all"
                                                                style={{
                                                                    width: `${safetyScore * 100}%`,
                                                                    backgroundColor: safetyScore > 0.7 ? '#ef4444' : safetyScore > 0.4 ? '#f59e0b' : '#22c55e'
                                                                }}
                                                            />
                                                        </div>
                                                        <span className={`font-mono ${safetyScore > 0.7 ? 'text-red-400' : safetyScore > 0.4 ? 'text-amber-400' : 'text-green-400'}`}>
                                                            {safetyScore.toFixed(2)}
                                                        </span>
                                                    </div>
                                                    {isFlagged && (
                                                        <span className="flex items-center gap-1 text-amber-400">
                                                            <ShieldAlert className="w-3 h-3" /> Flagged
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Action Buttons */}
                                            <div className="flex gap-2 flex-shrink-0">
                                                <button
                                                    onClick={() => approveAssertion(assertion.id)}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-green-700 hover:bg-green-600 rounded text-sm font-semibold transition-colors"
                                                >
                                                    <CheckCircle className="w-4 h-4" /> Approve
                                                </button>
                                                <button
                                                    onClick={() => rejectAssertion(assertion.id)}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-red-800 hover:bg-red-700 rounded text-sm font-semibold transition-colors"
                                                >
                                                    <XCircle className="w-4 h-4" /> Reject
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );

}

export default App;
