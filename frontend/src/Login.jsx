import React, { useState } from 'react';
import { Lock } from 'lucide-react';

export default function Login({ onLogin }) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        const credentials = btoa(`${username}:${password}`);
        const authHeader = `Basic ${credentials}`;

        try {
            const res = await fetch('/api/admin/check-auth', {
                headers: { 'Authorization': authHeader }
            });

            if (res.ok) {
                onLogin(authHeader);
            } else {
                setError('Invalid credentials');
            }
        } catch (err) {
            setError('Login failed');
        }
    };

    return (
        <div className="flex items-center justify-center h-screen bg-slate-900 text-slate-100">
            <div className="bg-slate-800 p-8 rounded-lg border border-slate-700 w-96 shadow-xl">
                <div className="flex justify-center mb-6">
                    <div className="bg-blue-600 p-3 rounded-full">
                        <Lock className="w-6 h-6 text-white" />
                    </div>
                </div>
                <h1 className="text-2xl font-bold text-center mb-6">Admin Login</h1>

                {error && (
                    <div className="bg-red-900/50 border border-red-500 text-red-200 p-3 rounded mb-4 text-sm text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm text-slate-400 mb-1">Username</label>
                        <input
                            type="text"
                            value={username}
                            onChange={e => setUsername(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                            placeholder="admin"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-slate-400 mb-1">Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                            placeholder="••••••••"
                        />
                    </div>
                    <button
                        type="submit"
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded transition-colors"
                    >
                        Sign In
                    </button>
                </form>
            </div>
        </div>
    );
}
