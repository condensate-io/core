import { create } from 'zustand';

export const useMemoryStore = create((set, get) => ({
    // State
    auth: localStorage.getItem('admin_auth') || null,
    stats: { total_keys: 0, total_projects: 0, total_memories: 0, total_learnings: 0, total_consolidations: 0 },
    keys: [],
    sources: [],
    learnings: [],
    entities: [],
    memories: [],
    projects: [],
    relations: [],
    consolidations: [],
    jobs: [],
    jobsLoading: false,
    pendingAssertions: [],
    pendingCount: 0,
    reviewFilter: { minInstruction: 0, minSafety: 0 },
    reviewLoading: false,
    graphData: { nodes: [], links: [] },
    searchQuery: '',
    selectedNode: null,
    newApiKey: null,
    showKeyModal: false,
    selectedProjectId: '',
    visualMultiplier: 1.0,
    graphNodeFilter: { episodic: true, semantic: true, entity: true },
    selectedIds: [],
    editItem: null,
    llmConfigs: { configs: [] },
    testLoading: {},
    testResults: {},
    systemConfig: { review_mode: 'manual' },
    synapseConfig: { enabled: true, learning_rate: 0.08, decay_rate: 0.995, prune_threshold: 0.05, consolidation_threshold: 0.75, decay_interval_hours: 24 },
    
    // Loading states
    loadingStates: {
        stats: false,
        keys: false,
        sources: false,
        learnings: false,
        entities: false,
        memories: false,
        projects: false,
        relations: false,
        consolidations: false,
        graph: false,
    },

    // Getters / Helpers
    getHeaders: () => ({
        'Authorization': get().auth,
        'Content-Type': 'application/json'
    }),

    // Auth actions
    handleLogin: (authHeader) => {
        localStorage.setItem('admin_auth', authHeader);
        set({ auth: authHeader });
    },
    handleLogout: () => {
        localStorage.removeItem('admin_auth');
        set({ auth: null });
    },

    // Setters
    setSearchQuery: (query) => set({ searchQuery: query }),
    setSelectedNode: (node) => set({ selectedNode: node }),
    setShowKeyModal: (show) => set({ showKeyModal: show }),
    setSelectedProjectId: (id) => set({ selectedProjectId: id }),
    setVisualMultiplier: (multiplier) => set({ visualMultiplier: multiplier }),
    setGraphNodeFilter: (updater) => {
        const current = get().graphNodeFilter;
        set({ graphNodeFilter: typeof updater === 'function' ? updater(current) : updater });
    },
    setSelectedIds: (ids) => set({ selectedIds: ids }),
    setEditItem: (item) => set({ editItem: item }),
    setReviewFilter: (filter) => set({ reviewFilter: filter }),

    // Fetch actions
    fetchStats: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, stats: true } }));
        try {
            const res = await fetch('/api/admin/stats', { headers: get().getHeaders() });
            if (res.status === 401) {
                get().handleLogout();
                return;
            }
            const data = await res.json();
            set({ stats: data });
        } catch (err) {
            console.error('Failed to fetch stats:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, stats: false } }));
        }
    },

    fetchKeys: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, keys: true } }));
        try {
            const res = await fetch('/api/admin/keys', { headers: get().getHeaders() });
            const data = await res.json();
            set({ keys: data });
        } catch (err) {
            console.error('Failed to fetch keys:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, keys: false } }));
        }
    },

    fetchSources: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, sources: true } }));
        try {
            const res = await fetch('/api/admin/sources', { headers: get().getHeaders() });
            const data = await res.json();
            set({ sources: data });
        } catch (err) {
            console.error('Failed to fetch sources:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, sources: false } }));
        }
    },

    fetchLearnings: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, learnings: true } }));
        try {
            const res = await fetch('/api/admin/learnings', { headers: get().getHeaders() });
            const data = await res.json();
            set({ learnings: data });
        } catch (err) {
            console.error('Failed to fetch learnings:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, learnings: false } }));
        }
    },

    fetchEntities: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, entities: true } }));
        try {
            const res = await fetch('/api/admin/entities', { headers: get().getHeaders() });
            const data = await res.json();
            set({ entities: data });
        } catch (err) {
            console.error('Failed to fetch entities:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, entities: false } }));
        }
    },

    fetchMemories: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, memories: true } }));
        try {
            const res = await fetch('/api/admin/memories?limit=200', { headers: get().getHeaders() });
            const data = await res.json();
            set({ memories: data });
        } catch (err) {
            console.error('Failed to fetch memories:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, memories: false } }));
        }
    },

    fetchProjects: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, projects: true } }));
        try {
            const res = await fetch('/api/admin/projects', { headers: get().getHeaders() });
            const data = await res.json();
            set({ projects: data });
        } catch (err) {
            console.error('Failed to fetch projects:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, projects: false } }));
        }
    },

    fetchRelations: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, relations: true } }));
        try {
            const res = await fetch('/api/admin/relations', { headers: get().getHeaders() });
            const data = await res.json();
            set({ relations: data });
        } catch (err) {
            console.error('Failed to fetch relations:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, relations: false } }));
        }
    },

    fetchConsolidations: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, consolidations: true } }));
        try {
            const res = await fetch('/api/admin/consolidations', { headers: get().getHeaders() });
            const data = await res.json();
            set({ consolidations: data });
        } catch (err) {
            console.error('Failed to fetch consolidations:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, consolidations: false } }));
        }
    },

    fetchJobs: async () => {
        if (!get().auth) return;
        set({ jobsLoading: true });
        try {
            const res = await fetch('/api/admin/jobs?limit=100', { headers: get().getHeaders() });
            const data = await res.json();
            set({ jobs: data.jobs || [] });
        } catch (err) {
            console.error('Failed to fetch jobs:', err);
        } finally {
            set({ jobsLoading: false });
        }
    },

    fetchPendingAssertions: async () => {
        if (!get().auth) return;
        set({ reviewLoading: true });
        try {
            const params = new URLSearchParams();
            const { minInstruction, minSafety } = get().reviewFilter;
            if (minInstruction > 0) params.set('min_instruction_score', minInstruction);
            if (minSafety > 0) params.set('min_safety_score', minSafety);
            const res = await fetch(`/api/admin/review/assertions/pending?${params}`, { headers: get().getHeaders() });
            const data = await res.json();
            set({ pendingAssertions: data.assertions || [], pendingCount: data.total || 0 });
        } catch (err) {
            console.error('Failed to fetch pending assertions:', err);
        } finally {
            set({ reviewLoading: false });
        }
    },

    fetchGraphData: async () => {
        if (!get().auth) return;
        set((state) => ({ loadingStates: { ...state.loadingStates, graph: true } }));
        try {
            const pidQuery = get().selectedProjectId ? `&project_id=${get().selectedProjectId}` : '';
            const res = await fetch(`/api/admin/vectors?visual_multiplier=${get().visualMultiplier}${pidQuery}`, { headers: get().getHeaders() });
            const data = await res.json();
            if (data.nodes && data.links) {
                set({ graphData: data });
            } else {
                set({ graphData: { nodes: [], links: [] } });
            }
        } catch (err) {
            console.error('Failed to fetch graph data:', err);
        } finally {
            set((state) => ({ loadingStates: { ...state.loadingStates, graph: false } }));
        }
    },

    fetchLlmConfig: async () => {
        try {
            const res = await fetch('/api/admin/config/llm', { headers: get().getHeaders() });
            if (res.ok) {
                const data = await res.json();
                set({ llmConfigs: data });
            }
        } catch (err) {
            console.error('Failed to fetch LLM config:', err);
        }
    },

    fetchSystemConfig: async () => {
        try {
            const res = await fetch('/api/admin/config/system', { headers: get().getHeaders() });
            if (res.ok) {
                const data = await res.json();
                set({ systemConfig: data });
            }
        } catch (err) {
            console.error('Failed to fetch system config:', err);
        }
    },

    fetchSynapseConfig: async () => {
        try {
            const res = await fetch('/api/admin/config/synapse', { headers: get().getHeaders() });
            if (res.ok) {
                const data = await res.json();
                set({ synapseConfig: data });
            }
        } catch (err) {
            console.error('Failed to fetch synapse config:', err);
        }
    },

    // Config Actions
    saveSynapseConfig: async (newConfig) => {
        try {
            const res = await fetch('/api/admin/config/synapse', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify(newConfig)
            });
            if (res.ok) {
                set({ synapseConfig: newConfig });
            }
        } catch (err) {
            console.error('Failed to save synapse config:', err);
        }
    },

    saveSystemConfig: async (newConfig) => {
        try {
            const res = await fetch('/api/admin/config/system', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify(newConfig)
            });
            if (res.ok) {
                set({ systemConfig: newConfig });
            }
        } catch (err) {
            console.error('Failed to save system config:', err);
        }
    },

    saveLlmConfigs: async (newConfigs) => {
        const configsToSave = (newConfigs && Array.isArray(newConfigs)) ? newConfigs : get().llmConfigs.configs;
        const payload = { configs: configsToSave };
        try {
            const response = await fetch('/api/admin/config/llm/save', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                get().fetchLlmConfig();
            } else {
                const error = await response.json();
                alert(`Failed to save LLM configuration: ${error.detail || 'Unknown error'}`);
            }
        } catch (err) {
            console.error('Failed to save configuration:', err);
            alert('Error saving configuration.');
        }
    },

    testConfig: async (config) => {
        const id = config.id || 'new';
        set((state) => ({ testLoading: { ...state.testLoading, [id]: true } }));
        try {
            const res = await fetch('/api/admin/config/llm/test', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify(config)
            });
            const result = await res.json();
            set((state) => ({ testResults: { ...state.testResults, [id]: result } }));
        } catch (err) {
            set((state) => ({ testResults: { ...state.testResults, [id]: { status: 'error', error: err.message } } }));
        } finally {
            set((state) => ({ testLoading: { ...state.testLoading, [id]: false } }));
        }
    },

    toggleConfigActive: (id) => {
        const config = get().llmConfigs.configs.find(c => c.id === id);
        const newConfigs = get().llmConfigs.configs.map(c => {
            if (c.id === id) return { ...c, is_active: !c.is_active };
            return c;
        });
        get().saveLlmConfigs(newConfigs);
        if (config && !config.is_active) {
            get().testConfig({ ...config, is_active: true });
        }
    },

    setPrimaryConfig: (id) => {
        const newConfigs = get().llmConfigs.configs.map(c => ({
            ...c,
            is_primary: c.id === id,
            is_active: c.id === id ? true : c.is_active
        }));
        get().saveLlmConfigs(newConfigs);
    },

    addConfig: () => {
        const newConfig = {
            id: 'cfg-' + Math.random().toString(36).substr(2, 9),
            name: 'New Profile',
            baseUrl: 'http://localhost:11434/v1',
            model: 'phi3',
            apiKey: 'ollama',
            is_active: false,
            is_primary: false
        };
        get().saveLlmConfigs([...get().llmConfigs.configs, newConfig]);
    },

    deleteConfig: (id) => {
        if (!confirm('Delete this model profile?')) return;
        get().saveLlmConfigs(get().llmConfigs.configs.filter(c => c.id !== id));
    },

    updateConfigField: (id, field, value) => {
        const newConfigs = get().llmConfigs.configs.map(c => {
            if (c.id === id) return { ...c, [field]: value };
            return c;
        });
        set({ llmConfigs: { configs: newConfigs } });
    },

    // CRUD Actions for Items
    deleteItem: async (type, id) => {
        if (!confirm(`Are you sure you want to delete this ${type}?`)) return;
        try {
            const endpoint = type === 'learning' ? 'learnings' : 
                            type === 'memory' ? 'memories' :
                            type === 'project' ? 'projects' :
                            type === 'entity' ? 'entities' : 
                            type === 'consolidation' ? 'consolidations' : 'relations';
            const res = await fetch(`/api/admin/${endpoint}/${id}`, { method: 'DELETE', headers: get().getHeaders() });
            if (res.ok) get().fetchDataByTab(type);
        } catch (err) {
            console.error(`Failed to delete ${type}:`, err);
        }
    },

    bulkDelete: async (type) => {
        const { selectedIds } = get();
        if (!selectedIds.length) return;
        if (!confirm(`Are you sure you want to delete ${selectedIds.length} items?`)) return;
        try {
            const endpoint = type === 'learning' ? 'learnings' : 
                            type === 'memory' ? 'memories' :
                            type === 'project' ? 'projects' :
                            type === 'entity' ? 'entities' : 'relations';
            const res = await fetch(`/api/admin/${endpoint}/bulk-delete`, {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify(selectedIds)
            });
            if (res.ok) {
                set({ selectedIds: [] });
                get().fetchDataByTab(type);
            }
        } catch (err) {
            console.error(`Failed to bulk delete ${type}:`, err);
        }
    },

    updateItem: async (type, id, data) => {
        try {
            const endpoint = type === 'learning' ? 'learnings' : 
                            type === 'memory' ? 'memories' :
                            type === 'project' ? 'projects' :
                            type === 'entity' ? 'entities' : 'relations';
            const res = await fetch(`/api/admin/${endpoint}/${id}`, {
                method: 'PATCH',
                headers: get().getHeaders(),
                body: JSON.stringify(data)
            });
            if (res.ok) {
                set({ editItem: null });
                get().fetchDataByTab(type);
            }
        } catch (err) {
            console.error(`Failed to update ${type}:`, err);
        }
    },

    createKey: async (name, project) => {
        try {
            const response = await fetch(`/api/admin/keys?name=${name}&project_id=${project}`, {
                method: 'POST',
                headers: get().getHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                set({ newApiKey: data.key, showKeyModal: true });
                get().fetchKeys();
                get().fetchStats();
            }
        } catch (err) {
            console.error('Failed to create key:', err);
        }
    },

    deleteKey: async (key) => {
        if (!confirm('Are you sure you want to delete this key?')) return;
        try {
            await fetch(`/api/admin/keys/${key}`, {
                method: 'DELETE',
                headers: get().getHeaders()
            });
            get().fetchKeys();
            get().fetchStats();
        } catch (err) {
            console.error('Failed to delete key:', err);
        }
    },

    createSource: async (payload) => {
        try {
            const response = await fetch('/api/admin/sources', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                get().fetchSources();
                return true;
            }
        } catch (err) {
            console.error('Failed to create source:', err);
        }
        return false;
    },

    triggerSource: async (id) => {
        try {
            const response = await fetch(`/api/admin/sources/${id}/trigger`, {
                method: 'POST',
                headers: get().getHeaders()
            });
            if (response.ok) {
                alert('Job triggered successfully');
            } else {
                alert('Failed to trigger job');
            }
        } catch (err) {
            console.error('Failed to trigger source:', err);
        }
    },

    deleteMemory: async (id) => {
        if (!confirm('Delete this memory?')) return;
        try {
            await fetch(`/api/admin/memories/${id}`, {
                method: 'DELETE',
                headers: get().getHeaders()
            });
            set({ selectedNode: null });
            get().fetchMemories();
            get().fetchStats();
        } catch (err) {
            console.error('Failed to delete memory:', err);
        }
    },

    pruneMemories: async () => {
        const { searchQuery } = get();
        if (!searchQuery) return;
        if (!confirm(`Delete all memories matching "${searchQuery}"?`)) return;

        try {
            await fetch('/api/admin/memories/prune', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify({ query: searchQuery, threshold: 0.7 })
            });
            get().fetchMemories();
            get().fetchStats();
            get().fetchGraphData();
        } catch (err) {
            console.error('Failed to prune memories:', err);
        }
    },

    approveAssertion: async (id) => {
        try {
            await fetch(`/api/admin/review/assertions/${id}/approve`, {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify({ reviewed_by: 'admin' })
            });
            get().fetchPendingAssertions();
            get().fetchStats();
        } catch (err) {
            console.error('Failed to approve assertion:', err);
        }
    },

    rejectAssertion: async (id, reason) => {
        const r = reason || prompt('Rejection reason:');
        if (!r) return;
        try {
            await fetch(`/api/admin/review/assertions/${id}/reject`, {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify({ reviewed_by: 'admin', rejection_reason: r })
            });
            get().fetchPendingAssertions();
            get().fetchStats();
        } catch (err) {
            console.error('Failed to reject assertion:', err);
        }
    },

    bulkApproveAll: async () => {
        const ids = get().pendingAssertions.map(a => a.id);
        if (!ids.length) return;
        try {
            await fetch('/api/admin/review/assertions/bulk-approve', {
                method: 'POST',
                headers: get().getHeaders(),
                body: JSON.stringify({ assertion_ids: ids, reviewed_by: 'admin' })
            });
            get().fetchPendingAssertions();
            get().fetchStats();
        } catch (err) {
            console.error('Failed to bulk approve assertions:', err);
        }
    },

    manualTrigger: async (projectId, action) => {
        try {
            const res = await fetch(`/api/admin/projects/${projectId}/${action}`, {
                method: 'POST',
                headers: get().getHeaders()
            });
            if (res.ok) {
                alert(`${action.charAt(0).toUpperCase() + action.slice(1)} triggered successfully`);
                get().fetchDataByTab(action === 'condense' ? 'memory' : 'consolidation');
                get().fetchStats();
            } else {
                const err = await res.json();
                alert(`Failed to trigger ${action}: ${err.detail}`);
            }
        } catch (err) {
            console.error(`Failed to trigger ${action}:`, err);
            alert(`Error triggering ${action}`);
        }
    },

    // Helper to fetch data by tab type
    fetchDataByTab: (tab) => {
        const tabLower = tab.toLowerCase();
        if (tabLower === 'learning' || tabLower === 'learnings' || tabLower === 'assertions') get().fetchLearnings();
        else if (tabLower === 'memory' || tabLower === 'memories') get().fetchMemories();
        else if (tabLower === 'project' || tabLower === 'projects') get().fetchProjects();
        else if (tabLower === 'entity' || tabLower === 'entities') get().fetchEntities();
        else if (tabLower === 'relation' || tabLower === 'relations') get().fetchRelations();
        else if (tabLower === 'consolidation' || tabLower === 'consolidations') get().fetchConsolidations();
        else if (tabLower === 'key' || tabLower === 'keys') get().fetchKeys();
        else if (tabLower === 'source' || tabLower === 'sources') get().fetchSources();
    }
}));
