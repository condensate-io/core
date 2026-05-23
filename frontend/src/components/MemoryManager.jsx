import React, { useEffect, useState, useMemo } from 'react';
import { List, FileText, Brain, Tag, RefreshCw, ShieldAlert, Trash2, Filter, X, Check, AlertCircle } from 'lucide-react';
import { useMemoryStore } from '../store/useMemoryStore';
import LoadingSpinner from './LoadingSpinner';

export default function MemoryManager() {
    const [subTab, setSubTab] = useState('episodic'); // episodic, assertions, consolidations, entities, relations, review
    
    const {
        memories, fetchMemories,
        learnings, fetchLearnings,
        entities, fetchEntities,
        relations, fetchRelations,
        consolidations, fetchConsolidations,
        pendingAssertions, fetchPendingAssertions,
        pendingCount,
        selectedIds, setSelectedIds,
        editItem, setEditItem,
        deleteItem, bulkDelete, updateItem,
        approveAssertion, rejectAssertion, bulkApproveAll,
        manualTrigger, selectedProjectId,
        loadingStates, reviewLoading
    } = useMemoryStore();

    // Fetch tab data when active tab changes
    useEffect(() => {
        setSelectedIds([]);
        if (subTab === 'episodic') fetchMemories();
        if (subTab === 'assertions') fetchLearnings();
        if (subTab === 'entities') fetchEntities();
        if (subTab === 'relations') fetchRelations();
        if (subTab === 'consolidations') fetchConsolidations();
        if (subTab === 'review') fetchPendingAssertions();
    }, [subTab]);

    const tabs = [
        { id: 'episodic', label: 'Episodic Items', icon: List, count: memories.length },
        { id: 'assertions', label: 'Assertions', icon: FileText, count: learnings.length },
        { id: 'consolidations', label: 'Consolidations', icon: Brain, count: consolidations.length },
        { id: 'entities', label: 'Entities', icon: Tag, count: entities.length },
        { id: 'relations', label: 'Relations', icon: RefreshCw, count: relations.length },
        { id: 'review', label: 'Review Queue', icon: ShieldAlert, count: pendingCount, highlight: pendingCount > 0 }
    ];

    // Local state for editing form
    const [editContent, setEditContent] = useState('');

    const openEdit = (item) => {
        setEditItem(item);
        if (item.type === 'memory') setEditContent(item.data.content);
        if (item.type === 'project') setEditContent(item.data.name);
        if (item.type === 'entity') setEditContent(item.data.canonical_name);
        if (item.type === 'relation') setEditContent(item.data.relation_type);
        if (item.type === 'learning') setEditContent(item.data.subject_text); // Or serialize triple
    };

    const handleSaveEdit = () => {
        if (!editItem) return;
        const id = editItem.data.id;
        let payload = {};
        if (editItem.type === 'memory') payload = { content: editContent };
        if (editItem.type === 'entity') payload = { canonical_name: editContent };
        if (editItem.type === 'relation') payload = { relation_type: editContent };
        if (editItem.type === 'project') payload = { name: editContent };
        
        updateItem(editItem.type, id, payload);
    };

    return (
        <div className="flex flex-col h-full gap-6 animate-in fade-in duration-300 overflow-hidden">
            {/* Sub navigation bar */}
            <div className="flex bg-slate-800/60 p-1.5 rounded-xl border border-slate-700/60 flex-shrink-0 overflow-x-auto gap-1">
                {tabs.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = subTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setSubTab(tab.id)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shrink-0 ${
                                isActive 
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/30' 
                                    : tab.highlight
                                        ? 'bg-amber-600/10 text-amber-400 hover:bg-amber-600/20'
                                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/35'
                            }`}
                        >
                            <Icon className="w-4 h-4" />
                            <span>{tab.label}</span>
                            {tab.count > 0 && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold font-mono ${
                                    isActive 
                                        ? 'bg-blue-800 text-blue-100' 
                                        : tab.highlight 
                                            ? 'bg-amber-500 text-slate-950' 
                                            : 'bg-slate-700 text-slate-400'
                                }`}>
                                    {tab.count}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Content pane */}
            <div className="flex-1 min-h-0 bg-slate-800 rounded-xl border border-slate-700 flex flex-col overflow-hidden shadow-xl">
                {subTab === 'episodic' && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <List className="w-5 h-5 text-blue-400" /> Episodic Memories
                            </h3>
                            <div className="flex gap-3">
                                <button 
                                    onClick={() => selectedProjectId ? manualTrigger(selectedProjectId, 'condense') : alert('Please select a project in the Dashboard first to condense its memories.')} 
                                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all active:scale-95 border border-emerald-500/20"
                                >
                                    <Filter className="w-3.5 h-3.5" /> Run Condensation
                                </button>
                                {selectedIds.length > 0 && (
                                    <button onClick={() => bulkDelete('memory')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition-all active:scale-95">
                                        <Trash2 className="w-3.5 h-3.5" /> Delete ({selectedIds.length})
                                    </button>
                                )}
                            </div>
                        </div>

                        {loadingStates.memories ? (
                            <LoadingSpinner message="Retrieving episodic memory trace..." />
                        ) : memories.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-sm">
                                <List className="w-12 h-12 text-slate-600 mb-3" />
                                No episodic memories found.
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                        <tr>
                                            <th className="p-4 w-12"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? memories.map(m => m.id) : [])} checked={selectedIds.length === memories.length && memories.length > 0} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></th>
                                            <th className="p-4">Content</th>
                                            <th className="p-4 text-right w-28">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700/40 text-sm">
                                        {memories.map(m => (
                                            <tr key={m.id} className="hover:bg-slate-700/15 transition-colors">
                                                <td className="p-4"><input type="checkbox" checked={selectedIds.includes(m.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, m.id] : selectedIds.filter(id => id !== m.id))} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></td>
                                                <td className="p-4 text-slate-300 truncate max-w-xl font-medium" title={m.content}>{m.content}</td>
                                                <td className="p-4 text-right flex justify-end gap-1">
                                                    <button onClick={() => openEdit({ type: 'memory', data: m })} className="p-2 hover:bg-blue-500/15 text-blue-400 rounded-lg transition-colors"><FileText className="w-4 h-4" /></button>
                                                    <button onClick={() => deleteItem('memory', m.id)} className="p-2 hover:bg-red-500/15 text-red-400 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'assertions' && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <FileText className="w-5 h-5 text-emerald-400" /> Semantic Assertions
                            </h3>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('learning')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition-all active:scale-95">
                                    <Trash2 className="w-3.5 h-3.5" /> Delete ({selectedIds.length})
                                </button>
                            )}
                        </div>

                        {loadingStates.learnings ? (
                            <LoadingSpinner message="Reconstructing assertion graph..." />
                        ) : learnings.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-sm">
                                <FileText className="w-12 h-12 text-slate-600 mb-3" />
                                No semantic assertions registered.
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                        <tr>
                                            <th className="p-4 w-12"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? learnings.map(l => l.id) : [])} checked={selectedIds.length === learnings.length && learnings.length > 0} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></th>
                                            <th className="p-4">Triple (Subject, Predicate, Object)</th>
                                            <th className="p-4 w-28">Confidence</th>
                                            <th className="p-4 text-right w-24">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700/40 text-sm">
                                        {learnings.map(l => (
                                            <tr key={l.id} className="hover:bg-slate-700/15 transition-colors">
                                                <td className="p-4"><input type="checkbox" checked={selectedIds.includes(l.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, l.id] : selectedIds.filter(id => id !== l.id))} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></td>
                                                <td className="p-4">
                                                    <div className="flex items-center gap-2 flex-wrap font-medium">
                                                        <span className="text-blue-300 font-semibold px-2 py-0.5 bg-blue-500/10 rounded">{l.subject_text}</span>
                                                        <span className="text-slate-400 text-xs italic">{l.predicate}</span>
                                                        <span className="text-purple-300 font-semibold px-2 py-0.5 bg-purple-500/10 rounded">{l.object_text}</span>
                                                    </div>
                                                </td>
                                                <td className="p-4">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-16 bg-slate-700 h-1.5 rounded-full overflow-hidden">
                                                            <div className="bg-emerald-500 h-full" style={{ width: `${l.confidence * 100}%` }}></div>
                                                        </div>
                                                        <span className="font-mono text-xs font-bold text-slate-300">{(l.confidence * 100).toFixed(0)}%</span>
                                                    </div>
                                                </td>
                                                <td className="p-4 text-right flex justify-end gap-1">
                                                    <button onClick={() => deleteItem('learning', l.id)} className="p-2 hover:bg-red-500/15 text-red-400 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'entities' && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <Tag className="w-5 h-5 text-purple-400" /> Conceptual Entities
                            </h3>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('entity')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition-all active:scale-95">
                                    <Trash2 className="w-3.5 h-3.5" /> Delete ({selectedIds.length})
                                </button>
                            )}
                        </div>

                        {loadingStates.entities ? (
                            <LoadingSpinner message="Indexing entity ledger..." />
                        ) : entities.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-sm">
                                <Tag className="w-12 h-12 text-slate-600 mb-3" />
                                No conceptual entities discovered yet.
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                        <tr>
                                            <th className="p-4 w-12"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? entities.map(ent => ent.id) : [])} checked={selectedIds.length === entities.length && entities.length > 0} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></th>
                                            <th className="p-4">Canonical Name</th>
                                            <th className="p-4 w-40">Classification</th>
                                            <th className="p-4 text-right w-24">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700/40 text-sm">
                                        {entities.map(e => (
                                            <tr key={e.id} className="hover:bg-slate-700/15 transition-colors">
                                                <td className="p-4"><input type="checkbox" checked={selectedIds.includes(e.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, e.id] : selectedIds.filter(id => id !== e.id))} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></td>
                                                <td className="p-4 text-white font-bold">{e.canonical_name}</td>
                                                <td className="p-4"><span className="px-2.5 py-0.5 bg-slate-700 rounded-md text-[10px] uppercase font-bold tracking-wider text-slate-400 border border-slate-600">{e.type}</span></td>
                                                <td className="p-4 text-right flex justify-end gap-1">
                                                    <button onClick={() => openEdit({ type: 'entity', data: e })} className="p-2 hover:bg-blue-500/15 text-blue-400 rounded-lg transition-colors"><FileText className="w-4 h-4" /></button>
                                                    <button onClick={() => deleteItem('entity', e.id)} className="p-2 hover:bg-red-500/15 text-red-400 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'relations' && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <RefreshCw className="w-5 h-5 text-purple-400 animate-spin-slow" /> Graph Relations
                            </h3>
                            {selectedIds.length > 0 && (
                                <button onClick={() => bulkDelete('relation')} className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 transition-all active:scale-95">
                                    <Trash2 className="w-3.5 h-3.5" /> Delete ({selectedIds.length})
                                </button>
                            )}
                        </div>

                        {loadingStates.relations ? (
                            <LoadingSpinner message="Calculating edge indices..." />
                        ) : relations.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-sm">
                                <RefreshCw className="w-12 h-12 text-slate-600 mb-3" />
                                No connections or relations documented.
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead className="sticky top-0 bg-slate-800 border-b border-slate-700 z-10 text-slate-400 text-xs uppercase font-bold">
                                        <tr>
                                            <th className="p-4 w-12"><input type="checkbox" onChange={(e) => setSelectedIds(e.target.checked ? relations.map(r => r.id) : [])} checked={selectedIds.length === relations.length && relations.length > 0} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></th>
                                            <th className="p-4">Origin ID</th>
                                            <th className="p-4 w-40">Relation</th>
                                            <th className="p-4">Target ID</th>
                                            <th className="p-4 text-right w-24">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-700/40 text-sm">
                                        {relations.map(r => (
                                            <tr key={r.id} className="hover:bg-slate-700/15 transition-colors">
                                                <td className="p-4"><input type="checkbox" checked={selectedIds.includes(r.id)} onChange={(e) => setSelectedIds(e.target.checked ? [...selectedIds, r.id] : selectedIds.filter(id => id !== r.id))} className="rounded text-blue-600 bg-slate-900 border-slate-700" /></td>
                                                <td className="p-4 font-mono text-xs text-slate-400">{r.from_id.slice(0, 12)}...</td>
                                                <td className="p-4"><span className="px-2.5 py-0.5 bg-purple-500/10 text-purple-300 rounded text-xs uppercase tracking-wide border border-purple-500/10 font-bold">{r.relation_type}</span></td>
                                                <td className="p-4 font-mono text-xs text-slate-400">{r.to_id.slice(0, 12)}...</td>
                                                <td className="p-4 text-right flex justify-end gap-1">
                                                    <button onClick={() => openEdit({ type: 'relation', data: r })} className="p-2 hover:bg-blue-500/15 text-blue-400 rounded-lg transition-colors"><FileText className="w-4 h-4" /></button>
                                                    <button onClick={() => deleteItem('relation', r.id)} className="p-2 hover:bg-red-500/15 text-red-400 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'consolidations' && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40 flex-shrink-0">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <Brain className="w-5 h-5 text-blue-400 animate-pulse" /> Higher-Order Meta-Learnings
                            </h3>
                            <button 
                                onClick={() => selectedProjectId ? manualTrigger(selectedProjectId, 'consolidate') : alert('Please select a project in the Dashboard first to run a consolidation cycle.')} 
                                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg shadow-blue-950/40 transition-all active:scale-95 border border-blue-500/20"
                            >
                                <Brain className="w-3.5 h-3.5" /> Run Consolidation Cycle
                            </button>
                        </div>

                        {loadingStates.consolidations ? (
                            <LoadingSpinner message="Synthesizing consolidation nodes..." />
                        ) : consolidations.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-sm">
                                <Brain className="w-12 h-12 text-slate-600 mb-3" />
                                No consolidated learnings found yet. Run a cycle to synthesize clusters.
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                                {consolidations.map(c => (
                                    <div key={c.id} className="bg-slate-900/60 rounded-xl border border-slate-700/80 p-5 hover:border-blue-500/50 transition-all duration-300 group shadow-lg">
                                        <div className="flex justify-between items-start mb-3">
                                            <span className="text-[9px] font-extrabold text-slate-500 uppercase tracking-widest px-2 py-0.5 bg-slate-800 rounded border border-slate-700">Meta-Learning Insight</span>
                                            <span className="text-xs font-mono text-slate-500">{new Date(c.created_at).toLocaleString()}</span>
                                        </div>
                                        <div className="text-base text-slate-200 mb-5 leading-relaxed font-semibold">
                                            {c.content}
                                        </div>
                                        <div className="flex items-center justify-between pt-4 border-t border-slate-800/60">
                                            <div className="flex gap-3">
                                                <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 flex items-center gap-2">
                                                    <Brain className="w-3.5 h-3.5 text-blue-400" />
                                                    <span className="text-xs font-bold text-blue-400">{(c.confidence * 100).toFixed(0)}% Confidence</span>
                                                </div>
                                                <div className="bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 flex items-center gap-2">
                                                    <List className="w-3.5 h-3.5 text-slate-400" />
                                                    <span className="text-xs font-bold text-slate-400">{c.evidence_count} Source Memories</span>
                                                </div>
                                            </div>
                                            <button onClick={() => deleteItem('consolidation', c.id)} className="opacity-0 group-hover:opacity-100 p-2 text-slate-500 hover:text-red-400 transition-all rounded-lg hover:bg-red-500/10">
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'review' && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-700 flex justify-between items-center bg-slate-800/40">
                            <h3 className="text-lg font-bold text-amber-400 flex items-center gap-2">
                                <ShieldAlert className="w-5 h-5" /> Human In The Loop Review
                            </h3>
                            {pendingAssertions.length > 0 && (
                                <button onClick={bulkApproveAll} className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all active:scale-95 border border-emerald-500/20 text-white">
                                    <Check className="w-3.5 h-3.5" /> Approve All ({pendingAssertions.length})
                                </button>
                            )}
                        </div>

                        {reviewLoading ? (
                            <LoadingSpinner message="Auditing manual review queue..." />
                        ) : pendingAssertions.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-sm">
                                <ShieldAlert className="w-12 h-12 text-slate-600 mb-3" />
                                No assertions in the review queue. All clear!
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                                {pendingAssertions.map(a => (
                                    <div key={a.id} className="bg-slate-900/60 rounded-xl border border-slate-700/80 p-5 flex justify-between items-center hover:border-amber-500/40 transition-all duration-300 shadow-md">
                                        <div className="space-y-3">
                                            <div className="flex items-center gap-2 flex-wrap font-medium">
                                                <span className="text-blue-300 font-bold px-2.5 py-0.5 bg-blue-500/10 rounded-lg text-sm">{a.subject_text}</span>
                                                <span className="text-slate-400 text-xs italic font-bold">{a.predicate}</span>
                                                <span className="text-purple-300 font-bold px-2.5 py-0.5 bg-purple-500/10 rounded-lg text-sm">{a.object_text}</span>
                                            </div>
                                            <div className="flex items-center gap-3 text-xs text-slate-500">
                                                <div className="flex items-center gap-1.5">
                                                    <AlertCircle className="w-3.5 h-3.5 text-blue-400" />
                                                    <span>Confidence: <span className="font-mono font-bold text-slate-300">{(a.confidence * 100).toFixed(0)}%</span></span>
                                                </div>
                                                <span className="text-slate-700">|</span>
                                                <div className="flex items-center gap-1.5">
                                                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                                                    <span>Safety Score: <span className="font-mono font-bold text-slate-300">{a.safety_score?.toFixed(2)}</span></span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <button onClick={() => approveAssertion(a.id)} className="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-lg text-xs font-bold text-white transition-all active:scale-95">Approve</button>
                                            <button onClick={() => rejectAssertion(a.id)} className="bg-red-800 hover:bg-red-700 px-4 py-2 rounded-lg text-xs font-bold text-white transition-all active:scale-95">Reject</button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Global Inline Edit Modal */}
            {editItem && (
                <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center z-[100] p-4 animate-in fade-in duration-300">
                    <div className="bg-slate-800 w-full max-w-lg rounded-2xl border border-slate-700 shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-6 border-b border-slate-700 flex justify-between items-center bg-slate-800/50">
                            <h3 className="text-lg font-bold text-white capitalize">Edit {editItem.type}</h3>
                            <button onClick={() => setEditItem(null)} className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
                        </div>
                        <div className="p-6 space-y-4">
                            {editItem.type === 'memory' ? (
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1.5">Content</label>
                                    <textarea 
                                        value={editContent} 
                                        onChange={e => setEditContent(e.target.value)}
                                        rows="5" 
                                        className="w-full bg-slate-900 border border-slate-600 rounded-xl px-4 py-3 text-slate-100 focus:outline-none focus:border-blue-500 font-sans leading-relaxed text-sm" 
                                    />
                                </div>
                            ) : (
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-1.5">Name / Label</label>
                                    <input 
                                        type="text" 
                                        value={editContent} 
                                        onChange={e => setEditContent(e.target.value)}
                                        className="w-full bg-slate-900 border border-slate-600 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:border-blue-500 text-sm font-semibold" 
                                    />
                                </div>
                            )}
                        </div>
                        <div className="p-5 border-t border-slate-700/60 bg-slate-800/40 flex justify-end gap-3">
                            <button onClick={() => setEditItem(null)} className="bg-slate-700 hover:bg-slate-600 text-slate-300 font-bold py-2 px-5 rounded-lg text-xs transition-colors">Cancel</button>
                            <button onClick={handleSaveEdit} className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded-lg text-xs transition-all shadow-lg shadow-blue-900/30">Save Changes</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
