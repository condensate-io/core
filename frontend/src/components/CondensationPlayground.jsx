import React, { useState } from 'react';
import { processCondensation } from '../services/condensationEngine';

const CondensationPlayground = () => {
    const [input, setInput] = useState(`USER: Hey, I want to talk about the project roadmap. 
AGENT: Sure, let's look at Q3. 
USER: We need to focus on the migration to v2.0 of our API. Bob said the auth layer is the bottleneck. 
AGENT: Okay, I'll prioritize the auth refactoring.
USER: Also, don't forget we have a meeting with the investors on Friday at 2 PM.`);

    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState(null);

    const handleCondense = async () => {
        if (!input.trim()) return;
        setIsLoading(true);
        try {
            const data = await processCondensation(input);
            setResult(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div id="demo" className="py-12 bg-slate-900/50 relative h-full overflow-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
                    <div>
                        <h2 className="text-3xl md:text-3xl font-bold text-white mb-2">Condensation Playground</h2>
                        <p className="text-slate-400 max-w-xl text-sm">
                            Observe the deterministic <span className="text-blue-400 font-mono">L3-Condenser</span> in action. No LLM magic—just rigorous heuristic extraction.
                        </p>
                    </div>
                    <div className="flex items-center gap-4 bg-slate-900 border border-slate-800 p-2 rounded-lg">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest pl-2">Engine:</span>
                        <span className="text-[10px] font-mono bg-blue-500/20 text-blue-400 px-2 py-1 rounded border border-blue-500/20">ALG-DET-V1</span>
                    </div>
                </div>

                <div className="grid lg:grid-cols-3 gap-8 items-start">
                    {/* Input Section */}
                    <div className="space-y-4 lg:col-span-1">
                        <label className="block text-sm font-medium text-slate-400 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                            Ephemeral Input
                        </label>
                        <textarea
                            className="w-full h-80 bg-slate-800 border border-slate-700 rounded-xl p-4 text-slate-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none font-mono text-sm leading-relaxed"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Paste logs..."
                        />
                        <button
                            onClick={handleCondense}
                            disabled={isLoading}
                            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold py-4 px-6 rounded-xl transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center gap-3 border border-blue-400/20"
                        >
                            {isLoading ? (
                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                            ) : (
                                <>
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                                    </svg>
                                    Run Algorithmic Trace
                                </>
                            )}
                        </button>
                    </div>

                    {/* Result Section */}
                    <div className="lg:col-span-2 space-y-8">
                        <div className="grid md:grid-cols-2 gap-8">
                            {/* Output */}
                            <div className="space-y-4">
                                <label className="block text-sm font-medium text-slate-400 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                    Condensed Memory
                                </label>
                                <div className="min-h-[200px] bg-slate-800 border border-slate-700 rounded-xl p-6 relative overflow-hidden group">
                                    <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity">
                                        <svg className="w-24 h-24" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
                                        </svg>
                                    </div>
                                    {!result && !isLoading && (
                                        <div className="absolute inset-0 flex items-center justify-center text-slate-600 italic text-sm">
                                            Await processing...
                                        </div>
                                    )}
                                    {result && (
                                        <div className="space-y-6 animate-in fade-in duration-500">
                                            <div className="flex justify-between items-center text-xs font-mono">
                                                <span className="text-emerald-400 font-bold">{result.savings}% Efficiency Gain</span>
                                                <span className="text-slate-600">{result.layer}</span>
                                            </div>
                                            <p className="text-slate-300 leading-relaxed font-medium">
                                                {result.condensed}
                                            </p>
                                            <div className="flex flex-wrap gap-2 pt-4 border-t border-slate-700">
                                                {result.entities.map((e, i) => (
                                                    <span key={i} className="text-[10px] bg-slate-900 text-slate-400 px-2 py-1 rounded border border-slate-700 font-mono">
                                                        {e}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Trace Log - Developer Centric */}
                            <div className="space-y-4">
                                <label className="block text-sm font-medium text-slate-400 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                                    Engine Trace Log
                                </label>
                                <div className="h-[300px] bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-[11px] overflow-y-auto custom-scrollbar">
                                    {!result && !isLoading && (
                                        <div className="text-slate-700 flex flex-col items-center justify-center h-full gap-2">
                                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                            </svg>
                                            <span>Idle...</span>
                                        </div>
                                    )}
                                    {isLoading && (
                                        <div className="text-blue-500 animate-pulse">
                                            [SYSTEM] Starting sequence...
                                        </div>
                                    )}
                                    {result && result.trace.map((step, i) => (
                                        <div key={i} className="mb-2 flex items-start gap-2 border-l border-slate-800 pl-3 ml-1 relative">
                                            <div className={`absolute -left-[3.5px] top-1 w-1.5 h-1.5 rounded-full ${step.status === 'success' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-slate-600'}`}></div>
                                            <span className="text-slate-600 shrink-0">[{new Date(step.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>
                                            <span className={`${step.status === 'success' ? 'text-emerald-400' : 'text-slate-400'}`}>{step.label}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default CondensationPlayground;
