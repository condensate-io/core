import React, { useEffect, useState } from 'react';
import { Database, Plus, Trash2, Key, Cpu, RefreshCw, Filter, Brain, X, ShieldAlert, Check, Copy } from 'lucide-react';
import { useMemoryStore } from '../store/useMemoryStore';
import LoadingSpinner from './LoadingSpinner';

export default function DataSourceManager() {
    const [subTab, setSubTab] = useState('projects'); // projects, sources, api-keys, jobs

    const {
        projects, fetchProjects,
        sources, fetchSources,
        keys, fetchKeys,
        jobs, fetchJobs, jobsLoading,
        createKey, deleteKey, newApiKey, showKeyModal, setShowKeyModal,
        createSource, triggerSource, deleteItem,
        manualTrigger, auth, loadingStates
    } = useMemoryStore();

    // Fetch initial data
    useEffect(() => {
        if (subTab === 'projects') fetchProjects();
        if (subTab === 'sources') {
            fetchSources();
            fetchProjects();
        }
        if (subTab === 'api-keys') {
            fetchKeys();
            fetchProjects();
        }
        if (subTab === 'jobs') fetchJobs();
    }, [subTab]);

    // Form fields for Source Creation
    const [sourceType, setSourceType] = useState('url');
    const [sourceName, setSourceName] = useState('');
    const [sourceProject, setSourceProject] = useState('');
    const [sourceUrl, setSourceUrl] = useState('');
    const [sourceCron, setSourceCron] = useState('');
    const [sourceApiConfig, setSourceApiConfig] = useState('{}');
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploading, setUploading] = useState(false);

    // Form fields for Project Creation
    const [newProjectName, setNewProjectName] = useState('');
    const [newProjectId, setNewProjectId] = useState('');
    const [creatingProject, setCreatingProject] = useState(false);

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!newProjectName.trim() || !newProjectId.trim()) return;
        setCreatingProject(true);
        try {
            const res = await fetch('/api/admin/projects', {
                method: 'POST',
                headers: {
                    'Authorization': auth,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    id: newProjectId.trim(),
                    name: newProjectName.trim()
                })
            });
            if (res.ok) {
                setNewProjectName('');
                setNewProjectId('');
                fetchProjects();
            } else {
                const err = await res.json();
                alert(`Failed to create project: ${err.detail || 'Unknown error'}`);
            }
        } catch (err) {
            console.error('Failed to create project:', err);
        } finally {
            setCreatingProject(false);
        }
    };

    const handleCreateSourceSubmit = async (e) => {
        e.preventDefault();
        let config = {};

        if (sourceType === 'url') {
            if (!sourceUrl.trim()) return;
            config = { url: sourceUrl.trim() };
        }

        if (sourceType === 'file') {
            if (!selectedFile) {
                alert("Please select a file to upload.");
                return;
            }
            setUploading(true);
            const uploadData = new FormData();
            uploadData.append('file', selectedFile);

            try {
                const uploadRes = await fetch('/api/admin/upload', {
                    method: 'POST',
                    headers: { 'Authorization': auth },
                    body: uploadData
                });

                if (!uploadRes.ok) throw new Error("File upload failed");
                const uploadJson = await uploadRes.json();
                config = { path: uploadJson.path };
            } catch (err) {
                alert("File upload failed: " + err.message);
                setUploading(false);
                return;
            } finally {
                setUploading(false);
            }
        }

        if (sourceType === 'api') {
            try {
                config = JSON.parse(sourceApiConfig);
            } catch (err) {
                alert('Invalid JSON in API configuration field.');
                return;
            }
        }

        const payload = {
            name: sourceName.trim(),
            project_id: sourceProject,
            source_type: sourceType,
            configuration: config,
            cron_schedule: sourceCron.trim() || null,
            enabled: true
        };

        const success = await createSource(payload);
        if (success) {
            setSourceName('');
            setSourceUrl('');
            setSourceCron('');
            setSourceApiConfig('{}');
            setSelectedFile(null);
        } else {
            alert('Could not configure data source. Please verify payload.');
        }
    };

    const handleCreateApiKey = (e) => {
        e.preventDefault();
        const data = new FormData(e.target);
        createKey(data.get('name'), data.get('project'));
        e.target.reset();
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(newApiKey);
        alert('API key copied to clipboard!');
    };

    const tabs = [
        { id: 'projects', label: 'Projects', icon: Database },
        { id: 'sources', label: 'Ingestion Sources', icon: Filter },
        { id: 'api-keys', label: 'API Credentials', icon: Key },
        { id: 'jobs', label: 'CPU Worker Jobs', icon: Cpu }
    ];

    return (
        <div className="flex flex-col h-full gap-6 animate-in fade-in duration-300 overflow-hidden">
            {/* Sub Tabs Navigation */}
            <div className="flex bg-slate-800/60 p-1.5 rounded-xl border border-slate-700/60 flex-shrink-0 gap-1">
                {tabs.map((tab) => {
                    const Icon = tab.icon;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setSubTab(tab.id)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                                subTab === tab.id 
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/30' 
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/35'
                            }`}
                        >
                            <Icon className="w-4 h-4" />
                            <span>{tab.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Content Drawer */}
            <div className="flex-1 min-h-0 bg-slate-800 rounded-xl border border-slate-700 overflow-hidden flex flex-col shadow-xl">
                {subTab === 'projects' && (
                    <div className="grid lg:grid-cols-3 h-full divide-x lg:divide-slate-700 divide-y lg:divide-y-0 overflow-y-auto">
                        <div className="lg:col-span-2 flex flex-col h-full overflow-hidden">
                            <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                                <h3 className="text-base font-bold text-white flex items-center gap-2">
                                    <Database className="w-5 h-5 text-blue-400" /> Cognitive Simulation Contexts
                                </h3>
                                <button onClick={() => fetchProjects()} className="p-1.5 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors"><RefreshCw className="w-4 h-4" /></button>
                            </div>
                            
                            {loadingStates.projects ? (
                                <LoadingSpinner message="Calibrating directories..." />
                            ) : projects.length === 0 ? (
                                <div className="flex-1 flex items-center justify-center p-12 text-slate-500 italic">
                                    No active projects configured. Get started by provisioning one!
                                </div>
                            ) : (
                                <div className="flex-1 overflow-y-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                            <tr>
                                                <th className="p-4">Name</th>
                                                <th className="p-4">Project ID</th>
                                                <th className="p-4 text-right w-[240px]">Pipeline Triggers</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/40 text-sm">
                                            {projects.map(p => (
                                                <tr key={p.id} className="hover:bg-slate-700/15 transition-colors">
                                                    <td className="p-4 text-white font-semibold">{p.name}</td>
                                                    <td className="p-4 font-mono text-xs text-slate-400">{p.id}</td>
                                                    <td className="p-4 text-right flex justify-end gap-2">
                                                        <button 
                                                            onClick={() => manualTrigger(p.id, 'condense')} 
                                                            className="px-2.5 py-1.5 hover:bg-emerald-500/20 text-emerald-400 rounded-lg flex items-center gap-1 text-xs transition-colors border border-emerald-500/10 font-bold"
                                                            title="Run Condenser (L2 Enrichment)"
                                                        >
                                                            <Filter className="w-3.5 h-3.5" />
                                                            Condense
                                                        </button>
                                                        <button 
                                                            onClick={() => manualTrigger(p.id, 'consolidate')} 
                                                            className="px-2.5 py-1.5 hover:bg-blue-500/20 text-blue-400 rounded-lg flex items-center gap-1 text-xs transition-colors border border-blue-500/10 font-bold"
                                                            title="Run Consolidation (Synapse clustering)"
                                                        >
                                                            <Brain className="w-3.5 h-3.5" />
                                                            Consolidate
                                                        </button>
                                                        <button onClick={() => deleteItem('project', p.id)} className="p-1.5 text-slate-500 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"><Trash2 className="w-4 h-4" /></button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        {/* Provision New Project Pane */}
                        <div className="p-6 bg-slate-900/30 flex flex-col h-full">
                            <h4 className="text-sm font-extrabold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
                                <Plus className="w-4 h-4 text-blue-400" /> Provision New Project
                            </h4>
                            <form onSubmit={handleCreateProject} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Project Name</label>
                                    <input 
                                        type="text" 
                                        placeholder="E.g., Production Agent"
                                        required 
                                        value={newProjectName} 
                                        onChange={e => setNewProjectName(e.target.value)} 
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm" 
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">System ID</label>
                                    <input 
                                        type="text" 
                                        placeholder="E.g., production-agent"
                                        required 
                                        value={newProjectId} 
                                        onChange={e => setNewProjectId(e.target.value)} 
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm font-mono" 
                                    />
                                </div>
                                <button 
                                    type="submit" 
                                    disabled={creatingProject} 
                                    className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all active:scale-95 shadow-lg shadow-blue-900/30 text-sm disabled:opacity-50"
                                >
                                    {creatingProject ? 'Provisioning...' : 'Provision Context'}
                                </button>
                            </form>
                        </div>
                    </div>
                )}

                {subTab === 'sources' && (
                    <div className="grid lg:grid-cols-3 h-full divide-x lg:divide-slate-700 divide-y lg:divide-y-0 overflow-y-auto">
                        <div className="lg:col-span-2 flex flex-col h-full overflow-hidden">
                            <div className="p-5 border-b border-slate-700 bg-slate-800/40">
                                <h3 className="text-base font-bold text-white flex items-center gap-2">
                                    <Filter className="w-5 h-5 text-emerald-400 animate-pulse" /> Ephemeral Data Feed Channels
                                </h3>
                            </div>
                            
                            {loadingStates.sources ? (
                                <LoadingSpinner message="Querying ingestion pipelines..." />
                            ) : sources.length === 0 ? (
                                <div className="flex-1 flex items-center justify-center p-12 text-slate-500 italic">
                                    No data sources mapped. Connect a feed to push text into the context window.
                                </div>
                            ) : (
                                <div className="flex-1 overflow-y-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                            <tr>
                                                <th className="p-4">Name</th>
                                                <th className="p-4">Project ID</th>
                                                <th className="p-4">Source Type</th>
                                                <th className="p-4 text-right w-28">Pipeline</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/40 text-sm">
                                            {sources.map(s => (
                                                <tr key={s.id} className="hover:bg-slate-700/15 transition-colors">
                                                    <td className="p-4 text-white font-semibold">{s.name}</td>
                                                    <td className="p-4 font-mono text-xs text-slate-400">{s.project_id}</td>
                                                    <td className="p-4">
                                                        <span className={`px-2.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border ${
                                                            s.source_type === 'url' ? 'bg-blue-500/10 text-blue-400 border-blue-500/10' :
                                                            s.source_type === 'file' ? 'bg-purple-500/10 text-purple-400 border-purple-500/10' :
                                                            'bg-emerald-500/10 text-emerald-400 border-emerald-500/10'
                                                        }`}>
                                                            {s.source_type}
                                                        </span>
                                                    </td>
                                                    <td className="p-4 text-right">
                                                        <button 
                                                            onClick={() => triggerSource(s.id)} 
                                                            className="bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-slate-200 active:scale-95"
                                                        >
                                                            Trigger
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        {/* Mount Ingestion Channel Pane */}
                        <div className="p-6 bg-slate-900/30 flex flex-col h-full justify-between">
                            <div>
                                <h4 className="text-sm font-extrabold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
                                    <Plus className="w-4 h-4 text-emerald-400" /> Mount Ingestion Channel
                                </h4>
                                <form onSubmit={handleCreateSourceSubmit} className="space-y-4">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Source Name</label>
                                        <input 
                                            type="text" 
                                            placeholder="E.g., Wiki Feed"
                                            required 
                                            value={sourceName} 
                                            onChange={e => setSourceName(e.target.value)} 
                                            className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm" 
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Project Target</label>
                                        <select 
                                            required 
                                            value={sourceProject} 
                                            onChange={e => setSourceProject(e.target.value)} 
                                            className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm"
                                        >
                                            <option value="">Select Project Target...</option>
                                            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Feed Pipeline Type</label>
                                        <div className="grid grid-cols-3 gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800">
                                            {['url', 'file', 'api'].map((t) => (
                                                <button
                                                    key={t}
                                                    type="button"
                                                    onClick={() => setSourceType(t)}
                                                    className={`py-1.5 rounded-lg text-xs font-bold uppercase transition-all ${
                                                        sourceType === t ? 'bg-blue-600 text-white shadow' : 'text-slate-500 hover:text-slate-300'
                                                    }`}
                                                >
                                                    {t}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {sourceType === 'url' && (
                                        <div>
                                            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Source Webpage URL</label>
                                            <input 
                                                type="url" 
                                                placeholder="https://example.com/api/docs"
                                                required 
                                                value={sourceUrl} 
                                                onChange={e => setSourceUrl(e.target.value)} 
                                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm font-mono" 
                                            />
                                        </div>
                                    )}

                                    {sourceType === 'file' && (
                                        <div>
                                            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Local Text File Upload</label>
                                            <input 
                                                type="file" 
                                                required 
                                                onChange={e => setSelectedFile(e.target.files[0])} 
                                                className="w-full text-slate-300 text-xs bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 file:bg-slate-800 file:border-none file:text-blue-400 file:px-3 file:py-1 file:rounded file:mr-3 file:font-semibold" 
                                            />
                                        </div>
                                    )}

                                    {sourceType === 'api' && (
                                        <div>
                                            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Webhook Configuration (JSON)</label>
                                            <textarea 
                                                rows="4" 
                                                value={sourceApiConfig} 
                                                onChange={e => setSourceApiConfig(e.target.value)} 
                                                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 text-xs font-mono" 
                                            />
                                        </div>
                                    )}

                                    <div>
                                        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Polling Schedule (Optional Cron)</label>
                                        <input 
                                            type="text" 
                                            placeholder="*/15 * * * * (Every 15 min)"
                                            value={sourceCron} 
                                            onChange={e => setSourceCron(e.target.value)} 
                                            className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm font-mono" 
                                        />
                                    </div>

                                    <button 
                                        type="submit" 
                                        disabled={uploading} 
                                        className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition-all active:scale-95 shadow-lg shadow-emerald-900/30 text-sm disabled:opacity-50"
                                    >
                                        {uploading ? 'Uploading context...' : 'Provision feed'}
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>
                )}

                {subTab === 'api-keys' && (
                    <div className="grid lg:grid-cols-3 h-full divide-x lg:divide-slate-700 divide-y lg:divide-y-0 overflow-y-auto">
                        <div className="lg:col-span-2 flex flex-col h-full overflow-hidden">
                            <div className="p-5 border-b border-slate-700 bg-slate-800/40">
                                <h3 className="text-base font-bold text-white flex items-center gap-2">
                                    <Key className="w-5 h-5 text-blue-400 animate-pulse" /> Client API Credentials
                                </h3>
                            </div>
                            
                            {loadingStates.keys ? (
                                <LoadingSpinner message="Auditing cryptological records..." />
                            ) : keys.length === 0 ? (
                                <div className="flex-1 flex items-center justify-center p-12 text-slate-500 italic">
                                    No provisioned API keys detected. Secure your endpoints by generating one.
                                </div>
                            ) : (
                                <div className="flex-1 overflow-y-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                            <tr>
                                                <th className="p-4">Key Label</th>
                                                <th className="p-4">Project Context</th>
                                                <th className="p-4">Key Prefix (Redacted)</th>
                                                <th className="p-4 text-right w-24">Revoke</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/40 text-sm">
                                            {keys.map(k => (
                                                <tr key={k.key} className="hover:bg-slate-700/15 transition-colors">
                                                    <td className="p-4 text-white font-semibold">{k.name}</td>
                                                    <td className="p-4 font-mono text-xs text-slate-400">{k.project_id}</td>
                                                    <td className="p-4 font-mono text-xs text-slate-500">{k.key.slice(0, 10)}...</td>
                                                    <td className="p-4 text-right">
                                                        <button 
                                                            onClick={() => deleteKey(k.key)} 
                                                            className="p-2 hover:bg-red-500/15 text-red-400 rounded-lg transition-colors"
                                                            title="Revoke and wipe token"
                                                        >
                                                            <Trash2 className="w-4 h-4" />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        {/* Provision API Keys Pane */}
                        <div className="p-6 bg-slate-900/30 flex flex-col h-full">
                            <h4 className="text-sm font-extrabold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
                                <Plus className="w-4 h-4 text-blue-400" /> Provision API Credentials
                            </h4>
                            <form onSubmit={handleCreateApiKey} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Key Label</label>
                                    <input 
                                        type="text" 
                                        name="name" 
                                        placeholder="E.g., Client Application Portal"
                                        required 
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm" 
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Project Target Context</label>
                                    <select 
                                        name="project" 
                                        required 
                                        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500 text-sm"
                                    >
                                        <option value="">Select Project Scope...</option>
                                        {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                                    </select>
                                </div>
                                <button 
                                    type="submit" 
                                    className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl transition-all active:scale-95 shadow-lg shadow-blue-900/30 text-sm"
                                >
                                    Generate Credentials
                                </button>
                            </form>
                        </div>
                    </div>
                )}

                {subTab === 'jobs' && (
                    <div className="flex flex-col h-full overflow-hidden">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                            <h3 className="text-base font-bold text-white flex items-center gap-2">
                                <Cpu className="w-5 h-5 text-blue-400 animate-pulse" /> Asynchronous CPU Workers
                            </h3>
                            <button onClick={() => fetchJobs()} className="p-2 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors flex items-center gap-1 text-xs font-semibold"><RefreshCw className={`w-3.5 h-3.5 ${jobsLoading ? 'animate-spin' : ''}`} /> Refresh Status</button>
                        </div>

                        {jobsLoading && jobs.length === 0 ? (
                            <LoadingSpinner message="Interrogating worker queue..." />
                        ) : jobs.length === 0 ? (
                            <div className="flex-1 flex items-center justify-center p-12 text-slate-500 italic">
                                No background jobs currently running on the server.
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                        <tr>
                                            <th className="p-4">Thread ID / Status</th>
                                            <th className="p-4">Thread Engine Target</th>
                                            <th className="p-4">Dispatched At</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700/40 text-sm">
                                        {jobs.map((j, i) => (
                                            <tr key={i} className="hover:bg-slate-700/15 transition-colors">
                                                <td className="p-4">
                                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] uppercase font-extrabold tracking-wider border ${
                                                        j.status === 'completed' || j.status === 'success' ? 'bg-green-500/10 text-green-400 border-green-500/10' :
                                                        j.status === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/10' :
                                                        'bg-amber-500/10 text-amber-400 border-amber-500/10 animate-pulse'
                                                    }`}>
                                                        <span className={`w-1.5 h-1.5 rounded-full ${
                                                            j.status === 'completed' || j.status === 'success' ? 'bg-green-400' :
                                                            j.status === 'failed' ? 'bg-red-400' :
                                                            'bg-amber-400 animate-ping'
                                                        }`} />
                                                        {j.status}
                                                    </span>
                                                </td>
                                                <td className="p-4 text-white font-bold">{j.job_name}</td>
                                                <td className="p-4 text-xs font-mono text-slate-400">{new Date(j.started_at).toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* API Key provision modal overlay */}
            {showKeyModal && (
                <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center z-[100] p-4 animate-in fade-in duration-300">
                    <div className="bg-slate-800 p-6 rounded-2xl border border-slate-700 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
                        <div className="flex justify-center mb-5 text-blue-400 bg-blue-500/10 w-12 h-12 rounded-full items-center border border-blue-500/20 mx-auto">
                            <Key className="w-6 h-6" />
                        </div>
                        <h2 className="text-xl font-bold text-center mb-2 text-white">Credentials Provisioned!</h2>
                        <p className="text-xs text-slate-400 text-center mb-4 leading-relaxed">
                            ⚠️ <strong>Crucial Security Notice:</strong> Copy this credential immediately. Under token safety standards, it will not be displayed again.
                        </p>
                        <div className="bg-slate-900 p-4 rounded-xl border border-slate-700 mb-5 font-mono text-xs break-all text-blue-200 font-bold select-all leading-normal flex items-center justify-between gap-3">
                            <span className="flex-1">{newApiKey}</span>
                            <button onClick={copyToClipboard} className="text-slate-400 hover:text-white transition-colors shrink-0 p-1.5 hover:bg-slate-800 rounded-md" title="Copy to clipboard">
                                <Copy className="w-4 h-4" />
                            </button>
                        </div>
                        <button onClick={() => setShowKeyModal(false)} className="w-full bg-slate-700 hover:bg-slate-600 text-white font-bold py-2.5 rounded-xl transition-all active:scale-95 text-xs">
                            Done
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
