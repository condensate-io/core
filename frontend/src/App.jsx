import React from 'react';
import { HashRouter, Routes, Route, Navigate, Link, useLocation, useNavigate } from 'react-router-dom';
import { useMemoryStore } from './store/useMemoryStore';
import Login from './Login';
import Dashboard from './components/Dashboard';
import MemoryManager from './components/MemoryManager';
import DataSourceManager from './components/DataSourceManager';
import Playground from './components/Playground';
import Settings from './components/Settings';
import ErrorBoundary from './components/ErrorBoundary';
import { Brain, Database, Play, Settings as SettingsIcon, LogOut, LayoutDashboard, Database as DbIcon, Radio, Wrench } from 'lucide-react';

function Layout() {
    const location = useLocation();
    const navigate = useNavigate();
    const handleLogout = useMemoryStore(state => state.handleLogout);
    const stats = useMemoryStore(state => state.stats);
    const systemConfig = useMemoryStore(state => state.systemConfig);

    const menuItems = [
        { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, desc: 'Synaptic graph & overview' },
        { path: '/ledger', label: 'Cognitive Ledger', icon: DbIcon, desc: 'Episodic & semantic data', count: (stats.total_memories || 0) + (stats.total_learnings || 0) },
        { path: '/ingestion', label: 'Ingestion Pipelines', icon: Radio, desc: 'Projects, feeds & credentials' },
        { path: '/playground', label: 'Playground Sandbox', icon: Play, desc: 'Router & Condenser tests' },
        { path: '/settings', label: 'System Settings', icon: Wrench, desc: 'Engines & synaptic learning' }
    ];

    const onLogoutClick = () => {
        handleLogout();
        navigate('/');
    };

    return (
        <div className="flex h-screen bg-slate-900 text-slate-100 font-sans overflow-hidden">
            {/* Sidebar Navigation */}
            <div className="w-72 bg-slate-800/90 border-r border-slate-700/80 p-5 flex flex-col flex-shrink-0 backdrop-blur-md relative z-10">
                <div className="flex items-center gap-3 mb-10 pl-2">
                    <div className="bg-gradient-to-tr from-blue-600 to-indigo-600 p-2.5 rounded-xl border border-blue-400/20 shadow-lg shadow-blue-900/35">
                        <Brain className="w-6 h-6 text-white animate-pulse" />
                    </div>
                    <div>
                        <h1 className="text-lg font-black tracking-wider bg-gradient-to-r from-blue-400 to-indigo-300 bg-clip-text text-transparent uppercase">Memory Server</h1>
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Cognitive Core v0.8.0</span>
                    </div>
                </div>

                <nav className="space-y-1.5 flex-1 overflow-y-auto pr-1">
                    {menuItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
                        return (
                            <Link 
                                key={item.path} 
                                to={item.path} 
                                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 group ${
                                    isActive 
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/30' 
                                        : 'hover:bg-slate-700/40 text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <Icon className={`w-5 h-5 shrink-0 transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-105 text-slate-500'}`} />
                                <div className="flex-1 text-left">
                                    <div className="text-sm font-bold leading-none mb-1">{item.label}</div>
                                    <div className={`text-[10px] transition-colors leading-none ${isActive ? 'text-blue-100/70' : 'text-slate-500'}`}>{item.desc}</div>
                                </div>
                                {item.count !== undefined && item.count > 0 && (
                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold font-mono ${
                                        isActive ? 'bg-blue-800 text-white' : 'bg-slate-700 text-slate-400'
                                    }`}>
                                        {item.count}
                                    </span>
                                )}
                            </Link>
                        );
                    })}

                    {systemConfig.condensation_paused && (
                        <div className="mx-2 px-4 py-2.5 mt-6 bg-red-950/20 border border-red-500/10 rounded-xl flex items-center gap-2.5 text-[10px] font-bold text-red-400 uppercase tracking-wider animate-pulse">
                            <Activity className="w-3.5 h-3.5" />
                            <span>Condensation Paused</span>
                        </div>
                    )}
                </nav>

                <div className="border-t border-slate-700/60 pt-4 mt-auto">
                    <button 
                        onClick={onLogoutClick} 
                        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-700/30 rounded-xl text-slate-400 hover:text-white transition-all text-xs font-bold"
                    >
                        <span>Sign Out Session</span>
                        <LogOut className="w-4 h-4 text-slate-500 hover:text-white transition-colors" />
                    </button>
                </div>
            </div>

            {/* Main Application Container */}
            <main className="flex-1 p-6 md:p-8 overflow-hidden flex flex-col relative z-0">
                <ErrorBoundary>
                    <Routes>
                        <Route path="/" element={<Navigate to="/dashboard" replace />} />
                        <Route path="/dashboard" element={<Dashboard />} />
                        <Route path="/ledger" element={<MemoryManager />} />
                        <Route path="/ingestion" element={<DataSourceManager />} />
                        <Route path="/playground" element={<Playground />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route path="*" element={<Navigate to="/dashboard" replace />} />
                    </Routes>
                </ErrorBoundary>
            </main>
        </div>
    );
}

export default function App() {
    const auth = useMemoryStore(state => state.auth);
    const handleLogin = useMemoryStore(state => state.handleLogin);

    if (!auth) {
        return <Login onLogin={handleLogin} />;
    }

    return (
        <HashRouter>
            <Layout />
        </HashRouter>
    );
}
