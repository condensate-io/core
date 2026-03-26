import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import { Key, Database, Brain, Activity, Plus, Trash2, Search, X, Filter, Play, Clock, FileText, ShieldAlert, CheckCircle, XCircle, List, Tag, Cpu, RefreshCw, AlertCircle, Settings, Save } from 'lucide-react';
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
    const [selectedProjectId, setSelectedProjectId] = useState('');
    const [visualMultiplier, setVisualMultiplier] = useState(1.0);
    const [graphNodeFilter, setGraphNodeFilter] = useState({ episodic: true, semantic: true, entity: true });
    const [memories, setMemories] = useState([]);
    const [entities, setEntities] = useState([]);
    const [jobs, setJobs] = useState([]);
    const [jobsLoading, setJobsLoading] = useState(false);
    const [ontologySubTab, setOntologySubTab] = useState('assertions');
    const [projects, setProjects] = useState([]);
    const [relations, setRelations] = useState([]);
    const [selectedIds, setSelectedIds] = useState([]);
    const [editItem, setEditItem] = useState(null);
    const [llmConfigs, setLlmConfigs] = useState({ configs: [] });
    const [testLoading, setTestLoading] = useState({});
    const [testResults, setTestResults] = useState({});
    const fgRef = useRef();

    // Clear selections when switching tabs
    useEffect(() => {
        setSelectedIds([]);
    }, [activeTab]);

    const headers = useMemo(() => ({
        'Authorization': auth,
        'Content-Type': 'application/json'
    }), [auth]);

    useEffect(() => {
        if (!auth) return;
        fetchData();
        if (activeTab === 'settings') {
            fetchLlmConfig();
        }
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

        if (activeTab === 'assertions') {
            fetch('/api/admin/learnings', { headers }).then(res => res.json()).then(setLearnings).catch(console.error);
        }

        if (activeTab === 'entities') {
            fetch('/api/admin/entities', { headers }).then(res => res.json()).then(setEntities).catch(console.error);
        }

        if (activeTab === 'memories') {
            fetch('/api/admin/memories?limit=200', { headers }).then(res => res.json()).then(setMemories).catch(console.error);
        }

        if (activeTab === 'projects') {
            fetch('/api/admin/projects', { headers }).then(res => res.json()).then(setProjects).catch(console.error);
        }

        if (activeTab === 'relations') {
            fetch('/api/admin/relations', { headers }).then(res => res.json()).then(setRelations).catch(console.error);
        }

        if (activeTab === 'review') {
            fetchPendingAssertions();
        }

        if (activeTab === 'jobs' || true) { // Always fetch jobs to keep sidebar count fresh
            fetchJobs();
        }

        if (activeTab === 'review') {
            fetchPendingAssertions();
        }

        if (activeTab === 'dashboard') {
            const pidQuery = selectedProjectId ? `&project_id=${selectedProjectId}` : '';
            fetch(`/api/admin/vectors?visual_multiplier=${visualMultiplier}${pidQuery}`, { headers }).then(res => res.json()).then(data => {
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

    const fetchLlmConfig = async () => {
        try {
            const res = await fetch('/api/admin/config/llm', { headers });
            if (res.ok) {
                const data = await res.json();
                setLlmConfigs(data);
            }
        } catch (err) {
            console.error('Failed to fetch LLM config', err);
        }
    };

    const saveLlmConfigs = async (newConfigs) => {
        const payload = { configs: newConfigs || llmConfigs.configs };
        try {
            const response = await fetch('/api/admin/config/llm/save', {
                method: 'POST',
                headers,
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                fetchLlmConfig();
            } else {
                const error = await response.json();
                alert(`Failed to save: ${error.detail || 'Unknown error'}`);
            }
        } catch (err) {
            console.error('Failed to save configuration', err);
            alert('Error saving configuration.');
        }
    };

    const testConfig = async (config) => {
        const id = config.id || 'new';
        setTestLoading(prev => ({ ...prev, [id]: true }));
        try {
            const res = await fetch('/api/admin/config/llm/test', {
                method: 'POST',
                headers,
                body: JSON.stringify(config)
            });
            const result = await res.json();
            setTestResults(prev => ({ ...prev, [id]: result }));
        } catch (err) {
            setTestResults(prev => ({ ...prev, [id]: { status: 'error', error: err.message } }));
        } finally {
            setTestLoading(prev => ({ ...prev, [id]: false }));
        }
    };

    const toggleConfigActive = (id) => {
        const config = llmConfigs.configs.find(c => c.id === id);
        const newConfigs = llmConfigs.configs.map(c => {
            if (c.id === id) return { ...c, is_active: !c.is_active };
            return c;
        });
        saveLlmConfigs(newConfigs);
        // Auto-test if activating
        if (config && !config.is_active) {
            testConfig({ ...config, is_active: true });
        }
    };

    const setPrimaryConfig = (id) => {
        const newConfigs = llmConfigs.configs.map(c => ({
            ...c,
            is_primary: c.id === id,
            is_active: c.id === id ? true : c.is_active // Auto-activate if setting as primary
        }));
        saveLlmConfigs(newConfigs);
    };

    const addConfig = () => {
        const newConfig = {
            id: 'cfg-' + Math.random().toString(36).substr(2, 9),
            name: 'New Profile',
            baseUrl: 'http://localhost:11434/v1',
            model: 'phi3',
            apiKey: 'ollama',
            is_active: false,
            is_primary: false
        };
        saveLlmConfigs([...llmConfigs.configs, newConfig]);
    };

    const deleteConfig = (id) => {
        if (!confirm('Delete this model profile?')) return;
        saveLlmConfigs(llmConfigs.configs.filter(c => c.id !== id));
    };

    const updateConfigField = (id, field, value) => {
        const newConfigs = llmConfigs.configs.map(c => {
            if (c.id === id) return { ...c, [field]: value };
            return c;
        });
        setLlmConfigs({ configs: newConfigs });
    };

    const deleteItem = async (type, id) => {
        if (!confirm(`Are you sure you want to delete this ${type}?`)) return;
        try {
            const endpoint = type === 'learning' ? 'learnings' : 
                            type === 'memory' ? 'memories' :
                            type === 'project' ? 'projects' :
                            type === 'entity' ? 'entities' : 'relations';
            const res = await fetch(`/api/admin/${endpoint}/${id}`, { method: 'DELETE', headers });
            if (res.ok) fetchData();
        } catch (err) { console.error(err); }
    };

    const bulkDelete = async (type) => {
        if (!selectedIds.length) return;
        if (!confirm(`Are you sure you want to delete ${selectedIds.length} items?`)) return;
        try {
            const endpoint = type === 'learning' ? 'learnings' : 
                            type === 'memory' ? 'memories' :
                            type === 'project' ? 'projects' :
                            type === 'entity' ? 'entities' : 'relations';
            const res = await fetch(`/api/admin/${endpoint}/bulk-delete`, {
                method: 'POST',
                headers,
                body: JSON.stringify(selectedIds)
            });
            if (res.ok) {
                setSelectedIds([]);
                fetchData();
            }
        } catch (err) { console.error(err); }
    };

    const updateItem = async (type, id, data) => {
        try {
            const endpoint = type === 'learning' ? 'learnings' : 
                            type === 'memory' ? 'memories' :
                            type === 'project' ? 'projects' :
                            type === 'entity' ? 'entities' : 'relations';
            const res = await fetch(`/api/admin/${endpoint}/${id}`, {
                method: 'PATCH',
                headers,
                body: JSON.stringify(data)
            });
            if (res.ok) {
                setEditItem(null);
                fetchData();
            }
        } catch (err) { console.error(err); }
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
                    headers: { 'Authorization': auth },
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

    const [sourceType, setSourceType] = useState('url');
    const [playgroundQuery, setPlaygroundQuery] = useState('');
    const [playgroundResult, setPlaygroundResult] = useState(null);
    const [playgroundLoading, setPlaygroundLoading] = useState(false);

    const handlePlaygroundSubmit = async (e) => {
        e.preventDefault();
        setPlaygroundLoading(true);
        setPlaygroundResult(null);
        try {
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
                            <button onClick={copyToClipboard} className="flex-1 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-white font-semibold transition-colors">
                                📋 Copy to Clipboard
                            </button>
                            <button onClick={closeKeyModal} className="flex-1 bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded text-white font-semibold transition-colors">
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="w-64 bg-slate-800 border-r border-slate-700 p-4 flex flex-col">
                <h1 className="text-xl font-bold mb-8 text-blue-400 flex items-center gap-2">
                    <Brain className="w-6 h-6" /> Memory Server
                </h1>
                <nav className="space-y-1 flex-1 overflow-y-auto pr-1">
                    <button onClick={() => setActiveTab('dashboard')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'dashboard' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Activity className="w-4 h-4" /> Dashboard
                    </button>
                    <button onClick={() => setActiveTab('playground')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'playground' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Play className="w-4 h-4" /> Router (Traffic)
                    </button>
                    <button onClick={() => setActiveTab('condenser')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'condenser' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Filter className="w-4 h-4" /> Condenser (Algo)
                    </button>
                    <div className="my-2 border-t border-slate-700/50 pt-2 text-[10px] uppercase tracking-wider text-slate-500 font-bold px-4">Data Management</div>
                    <button onClick={() => setActiveTab('projects')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'projects' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Database className="w-4 h-4" /> Projects
                        <span className="ml-auto text-slate-500 text-xs">{stats.total_projects}</span>
                    </button>
                    <button onClick={() => setActiveTab('memories')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'memories' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <List className="w-4 h-4" /> Episodic Items
                        <span className="ml-auto text-slate-500 text-xs">{stats.total_memories}</span>
                    </button>
                    <button onClick={() => setActiveTab('assertions')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'assertions' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <FileText className="w-4 h-4" /> Assertions
                        <span className="ml-auto text-slate-500 text-xs">{stats.total_learnings}</span>
                    </button>
                    <button onClick={() => setActiveTab('entities')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'entities' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Tag className="w-4 h-4" /> Entities
                        <span className="ml-auto text-slate-500 text-xs">{stats.total_entities}</span>
                    </button>
                    <button onClick={() => setActiveTab('relations')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'relations' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <RefreshCw className="w-4 h-4" /> Relations
                        <span className="ml-auto text-slate-500 text-xs">{stats.total_relations}</span>
                    </button>
                    <button onClick={() => setActiveTab('review')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'review' ? 'bg-amber-600' : 'hover:bg-slate-700'}`}>
                        <ShieldAlert className="w-4 h-4" /> Review Queue
                        {pendingCount > 0 ? (
                            <span className="ml-auto bg-amber-500 text-black text-xs font-bold px-1.5 py-0.5 rounded-full">{pendingCount}</span>
                        ) : (
                             <span className="ml-auto text-slate-500 text-xs">{stats.pending_review}</span>
                        )}
                    </button>
                    <button onClick={() => setActiveTab('jobs')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'jobs' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Cpu className="w-4 h-4" /> Jobs
                    </button>
                    <button onClick={() => setActiveTab('settings')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'settings' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Settings className="w-4 h-4" /> Model Config
                    </button>
                    <button onClick={() => setActiveTab('keys')} className={`w-full text-left px-4 py-2 rounded flex items-center gap-2 ${activeTab === 'keys' ? 'bg-blue-600' : 'hover:bg-slate-700'}`}>
                        <Key className="w-4 h-4" /> API Keys
                    </button>
                </nav>
                <button onClick={handleLogout} className="text-slate-400 hover:text-white text-sm mt-auto">Logout</button>
            </div>

            <div className="flex-1 p-8 overflow-hidden flex flex-col">
                {activeTab === 'dashboard' && (
                    <div className="flex flex-col h-full gap-8">
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

                        <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden relative flex">
                            <div className="absolute top-4 left-4 z-10 space-y-4 max-w-sm w-full pointer-events-none">
                                <div className="bg-slate-900/90 p-4 rounded backdrop-blur-sm pointer-events-auto border border-slate-700 shadow-2xl">
                                    <h2 className="text-lg font-bold mb-3 flex items-center gap-2 text-blue-400">
                                        <Database className="w-5 h-5" /> OmniSim Explorer
                                    </h2>
                                    <div className="space-y-4">
                                        <div>
                                            <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1.5">Simulation Context</label>
                                            <select 
                                                value={selectedProjectId}
                                                onChange={e => setSelectedProjectId(e.target.value)}
                                                className="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                                            >
                                                <option value="">Global Overview (All)</option>
                                                {projects.map(p => (
                                                    <option key={p.id} value={p.id}>{p.name}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div>
                                            <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1.5">Search Nodes</label>
                                            <div className="relative">
                                                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                                                <input
                                                    type="text"
                                                    value={searchQuery}
                                                    onChange={e => setSearchQuery(e.target.value)}
                                                    placeholder="Search names/topics..."
                                                    className="w-full bg-slate-800 border border-slate-600 rounded pl-9 pr-2 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                    {searchQuery && (
                                        <div className="flex justify-between items-center text-xs text-slate-400">
                                            <span>Found {filteredGraphData.nodes.length} nodes</span>
                                            <button onClick={pruneMemories} className="text-red-400 hover:text-red-300 flex items-center gap-1">
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
                                        <div className="flex justify-between items-center text-xs text-slate-500">
                                            <span className="capitalize px-2 py-1 bg-slate-800 rounded">{selectedNode.type}</span>
                                            <button onClick={() => deleteMemory(selectedNode.id)} className="text-red-400 hover:text-red-300 flex items-center gap-1 px-2 py-1 hover:bg-slate-800 rounded transition-colors">
                                                <Trash2 className="w-3 h-3" /> Delete
                                            </button>
                                        </div>
                                    </div>
                                )}

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
                                </div>
                            </div>

                            <div className="flex-1">
                                <ForceGraph3D
                                    ref={fgRef}
                                    graphData={filteredGraphData}
                                    nodeLabel="full_content"
                                    nodeColor={node => node.color || '#475569'}
                                    nodeVal="val"
                                    linkOpacity={0.6}
                                    backgroundColor="#0f172a"
                                    linkDirectionalArrowLength={2.5}
                                    linkDirectionalArrowRelPos={1}
                                    linkCurvature={0.15}
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
                                    className="flex-1 bg-slate-900 border border-slate-600 rounded px-4 py-3 text-lg text-white focus:outline-none"
                                />
                                <button type="submit" disabled={playgroundLoading} className="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded text-white font-bold transition-all disabled:opacity-50">
                                    {playgroundLoading ? 'Routing...' : 'Test Route'}
                                </button>
                            </form>
                            {playgroundResult && (
                                <div className="space-y-6">
                                    <div className="bg-slate-900 p-4 rounded border border-slate-700">
                                        <div className="text-xs text-slate-500 uppercase font-bold mb-1">Strategy</div>
                                        <div className="text-xl font-mono text-purple-400">{playgroundResult.strategy}</div>
                                    </div>
                                    <div className="bg-slate-900 p-6 rounded border border-slate-700">
                                        <div className="text-xs text-slate-500 uppercase font-bold mb-2">Answer</div>
                                        <pre className="text-slate-300 font-mono text-sm whitespace-pre-wrap">{playgroundResult.answer}</pre>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'assertions' && (
                    <div className="flex flex-col h-full">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-2xl font-bold text-emerald-400 flex items-center gap-2"><FileText className="w-6 h-6" /> Assertions</h2>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('learning')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded flex items-center gap-2"><Trash2 className="w-4 h-4" /> Delete ({selectedIds.length})</button>
                            )}
                        </div>
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex-1 overflow-y-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400">
                                    <tr>
                                        <th className="p-4 w-10"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? learnings.map(l => l.id) : [])} checked={selectedIds.length === learnings.length && learnings.length > 0} /></th>
                                        <th className="p-4 text-xs font-bold uppercase">Triple</th>
                                        <th className="p-4 text-xs font-bold uppercase">Conf</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {learnings.map(l => (
                                        <tr key={l.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                            <td className="p-4"><input type="checkbox" checked={selectedIds.includes(l.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, l.id] : selectedIds.filter(id => id !== l.id))} /></td>
                                            <td className="p-4 text-white font-medium">{l.subject_text} {l.predicate} {l.object_text}</td>
                                            <td className="p-4 font-mono text-xs">{(l.confidence * 100).toFixed(0)}%</td>
                                            <td className="p-4 text-right">
                                                <button onClick={() => setEditItem({ type: 'learning', data: l })} className="p-1.5 hover:bg-blue-500/20 text-blue-400 rounded"><FileText className="w-4 h-4" /></button>
                                                <button onClick={() => deleteItem('learning', l.id)} className="p-1.5 hover:bg-red-500/20 text-red-400 rounded"><Trash2 className="w-4 h-4" /></button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'entities' && (
                    <div className="flex flex-col h-full">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-2xl font-bold text-purple-400 flex items-center gap-2"><Tag className="w-6 h-6" /> Entities</h2>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('entity')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded flex items-center gap-2"><Trash2 className="w-4 h-4" /> Delete ({selectedIds.length})</button>
                            )}
                        </div>
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex-1 overflow-y-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400">
                                    <tr>
                                        <th className="p-4 w-10"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? entities.map(e => e.id) : [])} checked={selectedIds.length === entities.length && entities.length > 0} /></th>
                                        <th className="p-4 text-xs font-bold uppercase">Name</th>
                                        <th className="p-4 text-xs font-bold uppercase">Type</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {entities.map(e => (
                                        <tr key={e.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                            <td className="p-4"><input type="checkbox" checked={selectedIds.includes(e.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, e.id] : selectedIds.filter(id => id !== e.id))} /></td>
                                            <td className="p-4 text-white font-medium">{e.canonical_name}</td>
                                            <td className="p-4"><span className="px-2 py-0.5 bg-slate-700 rounded text-[10px] uppercase font-bold text-slate-400">{e.type}</span></td>
                                            <td className="p-4 text-right">
                                                <button onClick={() => setEditItem({ type: 'entity', data: e })} className="p-1.5 hover:bg-blue-500/20 text-blue-400 rounded"><FileText className="w-4 h-4" /></button>
                                                <button onClick={() => deleteItem('entity', e.id)} className="p-1.5 hover:bg-red-500/20 text-red-400 rounded"><Trash2 className="w-4 h-4" /></button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'condenser' && <CondensationPlayground />}

                {activeTab === 'projects' && (
                    <div className="flex flex-col h-full">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-2xl font-bold text-white flex items-center gap-2"><Database className="w-6 h-6 text-blue-400" /> Projects</h2>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('project')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded flex items-center gap-2"><Trash2 className="w-4 h-4" /> Delete ({selectedIds.length})</button>
                            )}
                        </div>
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex-1 overflow-y-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10">
                                    <tr>
                                        <th className="p-4 w-10"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? projects.map(p => p.id) : [])} checked={selectedIds.length === projects.length && projects.length > 0} /></th>
                                        <th className="p-4 text-xs font-bold text-slate-400 uppercase">Name</th>
                                        <th className="p-4 text-xs font-bold text-slate-400 uppercase">ID</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {projects.map(p => (
                                        <tr key={p.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                            <td className="p-4"><input type="checkbox" checked={selectedIds.includes(p.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, p.id] : selectedIds.filter(id => id !== p.id))} /></td>
                                            <td className="p-4 text-white font-medium">{p.name}</td>
                                            <td className="p-4 text-slate-500 font-mono text-xs">{p.id}</td>
                                            <td className="p-4 text-right">
                                                <button onClick={() => setEditItem({ type: 'project', data: p })} className="p-1.5 hover:bg-blue-500/20 text-blue-400 rounded"><FileText className="w-4 h-4" /></button>
                                                <button onClick={() => deleteItem('project', p.id)} className="p-1.5 hover:bg-red-500/20 text-red-400 rounded"><Trash2 className="w-4 h-4" /></button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'relations' && (
                    <div className="flex flex-col h-full">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-2xl font-bold text-white flex items-center gap-2"><RefreshCw className="w-6 h-6 text-purple-400" /> Relations</h2>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('relation')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded flex items-center gap-2"><Trash2 className="w-4 h-4" /> Delete ({selectedIds.length})</button>
                            )}
                        </div>
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex-1 overflow-y-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10">
                                    <tr>
                                        <th className="p-4 w-10"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? relations.map(r => r.id) : [])} checked={selectedIds.length === relations.length && relations.length > 0} /></th>
                                        <th className="p-4 text-xs font-bold text-slate-400 uppercase">From</th>
                                        <th className="p-4 text-xs font-bold text-slate-400 uppercase">Type</th>
                                        <th className="p-4 text-xs font-bold text-slate-400 uppercase">To</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {relations.map(r => (
                                        <tr key={r.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                            <td className="p-4"><input type="checkbox" checked={selectedIds.includes(r.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, r.id] : selectedIds.filter(id => id !== r.id))} /></td>
                                            <td className="p-4 text-xs font-mono">{r.from_id.slice(0,8)}...</td>
                                            <td className="p-4"><span className="px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded text-xs uppercase">{r.relation_type}</span></td>
                                            <td className="p-4 text-xs font-mono">{r.to_id.slice(0,8)}...</td>
                                            <td className="p-4 text-right">
                                                <button onClick={() => setEditItem({ type: 'relation', data: r })} className="p-1.5 hover:bg-blue-500/20 text-blue-400 rounded"><FileText className="w-4 h-4" /></button>
                                                <button onClick={() => deleteItem('relation', r.id)} className="p-1.5 hover:bg-red-500/20 text-red-400 rounded"><Trash2 className="w-4 h-4" /></button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'memories' && (
                    <div className="flex flex-col h-full">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-2xl font-bold text-blue-400 flex items-center gap-2"><List className="w-6 h-6" /> Episodic Items</h2>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('memory')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded flex items-center gap-2"><Trash2 className="w-4 h-4" /> Delete ({selectedIds.length})</button>
                            )}
                        </div>
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex-1 overflow-y-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10">
                                    <tr>
                                        <th className="p-4 w-10"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? memories.map(m => m.id) : [])} checked={selectedIds.length === memories.length && memories.length > 0} /></th>
                                        <th className="p-4 text-xs font-bold text-slate-400 uppercase">Content</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {memories.map(m => (
                                        <tr key={m.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                            <td className="p-4"><input type="checkbox" checked={selectedIds.includes(m.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, m.id] : selectedIds.filter(id => id !== m.id))} /></td>
                                            <td className="p-4 text-sm text-slate-300 truncate max-w-lg">{m.content}</td>
                                            <td className="p-4 text-right">
                                                <button onClick={() => setEditItem({ type: 'memory', data: m })} className="p-1.5 hover:bg-blue-500/20 text-blue-400 rounded"><FileText className="w-4 h-4" /></button>
                                                <button onClick={() => deleteItem('memory', m.id)} className="p-1.5 hover:bg-red-500/20 text-red-400 rounded"><Trash2 className="w-4 h-4" /></button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'jobs' && (
                    <div className="space-y-4 overflow-auto h-full">
                        <div className="flex justify-between items-center">
                            <h2 className="text-2xl font-bold text-blue-400">Background Jobs</h2>
                            <button onClick={fetchJobs} className="flex items-center gap-2 px-4 py-2 bg-slate-700 rounded text-sm"><RefreshCw className="w-4 h-4" /> Refresh</button>
                        </div>
                        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-slate-900 text-slate-400 uppercase text-xs">
                                    <tr><th className="p-3">Status</th><th className="p-3">Job Name</th><th className="p-3">Started</th></tr>
                                </thead>
                                <tbody>
                                    {jobs.map((j, i) => (
                                        <tr key={i} className="border-b border-slate-700">
                                            <td className="p-3 capitalize">{j.status}</td>
                                            <td className="p-3">{j.job_name}</td>
                                            <td className="p-3">{new Date(j.started_at).toLocaleString()}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'settings' && (
                    <div className="space-y-8 max-w-4xl mx-auto w-full pb-20">
                        <div className="flex justify-between items-end mb-8">
                            <div className="text-left">
                                <h2 className="text-3xl font-bold text-blue-400 mb-2">Cognitive Engines</h2>
                                <p className="text-slate-400">Configure Primary (default) and Secondary model profiles for retrieval and synthesis.</p>
                            </div>
                            <button 
                                onClick={saveLlmConfigs} 
                                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-blue-900/40 transition-all active:scale-95"
                            >
                                <Save className="w-4 h-4" /> Save All Configurations
                            </button>
                        </div>

                        <div className="grid gap-6">
                            {llmConfigs.configs.map(config => {
                                const id = config.id;
                                const tr = testResults[id];
                                const loading = testLoading[id];
                                return (
                                    <div key={id} className={`bg-slate-800 rounded-xl border p-6 transition-all ${config.is_primary ? 'border-blue-500 shadow-blue-900/20 shadow-xl' : 'border-slate-700'}`}>
                                        <div className="flex justify-between items-start mb-6">
                                            <div className="flex items-center gap-3">
                                                <div className={`p-2 rounded-lg ${config.is_primary ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400'}`}>
                                                    <Brain className="w-5 h-5" />
                                                </div>
                                                <div>
                                                    <input 
                                                        className="bg-transparent border-none text-xl font-bold text-white focus:outline-none focus:ring-0 p-0"
                                                        value={config.name}
                                                        onChange={e => updateConfigField(id, 'name', e.target.value)}
                                                        onBlur={() => saveLlmConfigs()}
                                                    />
                                                    <div className="flex gap-2 items-center mt-1">
                                                        {config.is_primary && <span className="text-[10px] bg-blue-900 text-blue-200 px-1.5 py-0.5 rounded font-bold uppercase">Primary</span>}
                                                        {config.is_active ? 
                                                            <span className="text-[10px] bg-green-900 text-green-300 px-1.5 py-0.5 rounded font-bold uppercase">Active</span> :
                                                            <span className="text-[10px] bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded font-bold uppercase">Disabled</span>
                                                        }
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex gap-2">
                                                <button 
                                                    onClick={() => testConfig(config)}
                                                    disabled={loading}
                                                    className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-xs font-semibold flex items-center gap-2 transition-colors"
                                                >
                                                    <Activity className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                                                    {loading ? 'Testing...' : 'Test Connection'}
                                                </button>
                                                {!config.is_primary && (
                                                    <button 
                                                        onClick={() => setPrimaryConfig(id)}
                                                        className="px-3 py-1.5 bg-blue-900/50 hover:bg-blue-600 text-blue-200 hover:text-white rounded text-xs font-semibold"
                                                    >
                                                        Set Primary
                                                    </button>
                                                )}
                                                <button 
                                                    onClick={() => toggleConfigActive(id)}
                                                    className={`px-3 py-1.5 rounded text-xs font-semibold ${config.is_active ? 'bg-amber-900/50 text-amber-300 hover:bg-amber-800' : 'bg-green-900/50 text-green-300 hover:bg-green-800'}`}
                                                >
                                                    {config.is_active ? 'Deactivate' : 'Activate'}
                                                </button>
                                                <button onClick={() => deleteConfig(id)} className="p-1.5 text-slate-500 hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-3 gap-6">
                                            <div>
                                                <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1">Base URL</label>
                                                <input 
                                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-300 focus:border-blue-500 focus:outline-none font-mono"
                                                    value={config.baseUrl}
                                                    onChange={e => updateConfigField(id, 'baseUrl', e.target.value)}
                                                    onBlur={() => saveLlmConfigs()}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1">Model ID</label>
                                                <input 
                                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-300 focus:border-blue-500 focus:outline-none font-mono"
                                                    value={config.model}
                                                    onChange={e => updateConfigField(id, 'model', e.target.value)}
                                                    onBlur={() => saveLlmConfigs()}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1">Auth / API Key</label>
                                                <input 
                                                    type="password"
                                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-300 focus:border-blue-500 focus:outline-none font-mono"
                                                    value={config.apiKey}
                                                    onChange={e => updateConfigField(id, 'apiKey', e.target.value)}
                                                    onBlur={() => saveLlmConfigs()}
                                                />
                                            </div>
                                        </div>

                                        {tr && (
                                            <div className={`mt-4 p-3 rounded flex items-center justify-between text-xs ${tr.status === 'success' ? 'bg-green-900/20 border border-green-800/50 text-green-400' : 'bg-red-900/20 border border-red-800/50 text-red-400'}`}>
                                                <div className="flex items-center gap-2">
                                                    {tr.status === 'success' ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                                                    {tr.status === 'success' ? 'Model reachable' : `Error: ${tr.error}`}
                                                </div>
                                                <div className="font-mono bg-black/30 px-2 py-0.5 rounded">
                                                    Latency: {tr.latency}ms
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                        
                        <button 
                            onClick={addConfig}
                            className="w-full py-4 border-2 border-dashed border-slate-700 rounded-xl text-slate-500 hover:text-blue-400 hover:border-blue-500/50 hover:bg-blue-500/5 transition-all font-bold flex items-center justify-center gap-2"
                        >
                            <Plus className="w-5 h-5" /> Add New Model Profile
                        </button>
                    </div>
                )}

                {activeTab === 'review' && (
                    <div className="flex flex-col h-full gap-6">
                        <div className="flex items-center justify-between">
                            <h2 className="text-2xl font-bold flex items-center gap-3 text-amber-400"><ShieldAlert className="w-7 h-7" /> Review Queue</h2>
                            <button onClick={bulkApproveAll} className="px-4 py-2 bg-green-700 rounded text-sm font-semibold">Approve All ({pendingAssertions.length})</button>
                        </div>
                        <div className="flex-1 overflow-y-auto space-y-3">
                            {pendingAssertions.map(a => (
                                <div key={a.id} className="bg-slate-800 rounded-lg border border-slate-700 p-4 flex justify-between items-center">
                                    <div>
                                        <div className="flex gap-2 text-sm"><span className="text-blue-300">{a.subject_text}</span> <span className="text-slate-500">{a.predicate}</span> <span className="text-purple-300">{a.object_text}</span></div>
                                        <div className="text-xs text-slate-500 mt-1">Confidence: {(a.confidence * 100).toFixed(0)}% | Safety: {a.safety_score?.toFixed(2)}</div>
                                    </div>
                                    <div className="flex gap-2">
                                        <button onClick={() => approveAssertion(a.id)} className="bg-green-700 hover:bg-green-600 px-3 py-1 rounded text-sm font-semibold">Approve</button>
                                        <button onClick={() => rejectAssertion(a.id)} className="bg-red-800 hover:bg-red-700 px-3 py-1 rounded text-sm font-semibold">Reject</button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {activeTab === 'keys' && (
                    <div className="space-y-6 overflow-auto h-full">
                        <div className="flex justify-between items-center">
                            <h2 className="text-2xl font-bold flex items-center gap-2 text-blue-400"><Key className="w-6 h-6" /> API Keys</h2>
                        </div>
                        <div className="grid grid-cols-3 gap-6">
                            <div className="col-span-2 bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                                <table className="w-full text-left">
                                    <thead className="bg-slate-900 text-slate-400">
                                        <tr><th className="p-4">Name</th><th className="p-4">Project ID</th><th className="p-4">Key (Redacted)</th><th className="p-4">Actions</th></tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700">
                                        {keys.map(k => (
                                            <tr key={k.key} className="hover:bg-slate-700/50">
                                                <td className="p-4 font-medium">{k.name}</td>
                                                <td className="p-4 text-xs font-mono text-slate-400">{k.project_id}</td>
                                                <td className="p-4 text-xs font-mono text-slate-500">{k.key.slice(0, 8)}...</td>
                                                <td className="p-4">
                                                    <button onClick={() => deleteKey(k.key)} className="p-1 hover:bg-red-500/20 text-red-400 rounded transition-colors"><Trash2 className="w-4 h-4" /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 h-fit">
                                <h3 className="text-lg font-bold mb-4">Generate New Key</h3>
                                <form onSubmit={createKey} className="space-y-4">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Key Name (e.g. My Website)</label>
                                        <input type="text" name="name" required className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Project Name/ID</label>
                                        <input type="text" name="project" required className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" list="project-list" />
                                        <datalist id="project-list">
                                            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                                        </datalist>
                                    </div>
                                    <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 rounded transition-colors">Generate Key</button>
                                </form>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Global Edit Modal */}
            {editItem && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
                    <div className="bg-slate-800 w-full max-w-lg rounded-xl border border-slate-700 shadow-2xl overflow-hidden">
                        <div className="p-6 border-b border-slate-700 flex justify-between items-center">
                            <h3 className="text-xl font-bold text-white capitalize">Edit {editItem.type}</h3>
                            <button onClick={() => setEditItem(null)} className="p-1 hover:bg-slate-700 rounded transition-colors"><X className="w-5 h-5" /></button>
                        </div>
                        <div className="p-6 space-y-4">
                            {editItem.type === 'project' && (
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Project Name</label>
                                    <input type="text" defaultValue={editItem.data.name} className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" onBlur={(e) => updateItem('project', editItem.data.id, { name: e.target.value })} />
                                </div>
                            )}
                            {editItem.type === 'memory' && (
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Content</label>
                                    <textarea defaultValue={editItem.data.content} rows="4" className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" onBlur={(e) => updateItem('memory', editItem.data.id, { content: e.target.value })} />
                                </div>
                            )}
                            {editItem.type === 'entity' && (
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Name</label>
                                    <input type="text" defaultValue={editItem.data.canonical_name} className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" onBlur={(e) => updateItem('entity', editItem.data.id, { canonical_name: e.target.value })} />
                                </div>
                            )}
                            {editItem.type === 'relation' && (
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Relation Type</label>
                                    <input type="text" defaultValue={editItem.data.relation_type} className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white" onBlur={(e) => updateItem('relation', editItem.data.id, { relation_type: e.target.value })} />
                                </div>
                            )}
                        </div>
                        <div className="p-6 border-t border-slate-700 flex justify-end">
                            <button onClick={() => setEditItem(null)} className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded transition-colors shadow-lg">Done</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;
