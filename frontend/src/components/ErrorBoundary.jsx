import React from 'react';
import { ShieldAlert, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center min-h-[400px] p-8 bg-slate-900/80 border border-red-500/30 rounded-2xl backdrop-blur-md text-slate-100 max-w-lg mx-auto my-12 shadow-2xl animate-in fade-in duration-300">
                    <div className="bg-red-500/10 p-4 rounded-full border border-red-500/20 mb-6">
                        <ShieldAlert className="w-12 h-12 text-red-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-2 text-center">Something went wrong</h2>
                    <p className="text-sm text-slate-400 text-center mb-6 max-w-sm">
                        An error occurred while loading this section of the memory system. This has been logged for our engineers.
                    </p>
                    <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 w-full mb-6 font-mono text-xs text-red-300 overflow-x-auto max-h-[150px] leading-relaxed">
                        {this.state.error?.toString() || 'Unknown Error'}
                    </div>
                    <button
                        onClick={this.handleReset}
                        className="flex items-center gap-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 px-6 py-3 rounded-xl font-bold transition-all active:scale-95 shadow-lg shadow-red-950/30 border border-red-500/20"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Reload Interface
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
