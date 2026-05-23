import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingSpinner({ message = 'Loading memory system...' }) {
    return (
        <div className="flex flex-col items-center justify-center py-20 w-full h-full text-slate-400 gap-4 animate-in fade-in duration-300">
            <div className="relative">
                <div className="w-12 h-12 rounded-full border-4 border-slate-800 border-t-blue-500 animate-spin"></div>
                <div className="absolute inset-0 w-12 h-12 rounded-full border-4 border-transparent border-b-purple-500/30 animate-pulse"></div>
            </div>
            <span className="text-sm font-semibold tracking-wide text-slate-400 font-sans">{message}</span>
        </div>
    );
}
