import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Lock, User as UserIcon, AlertCircle, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import googleIcon from '../assets/icons/icons8-google-48.png';
import microsoftIcon from '../assets/icons/icons8-microsoft-48.png';
import murenaLogo from '../assets/brand/MURENA_56x56px.svg';

export const LoginPage: React.FC = () => {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            await login({ username, password });
            navigate('/');
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } catch (err: any) {
            console.error(err);
            const apiUrl = import.meta.env.VITE_API_URL;
            
            // Handle FastAPI validation errors or standard messages
            const detail = err.response?.data?.detail;
            let msg = 'Login failed';
            
            if (Array.isArray(detail)) {
                // Formatting for validation error list: "field: error message"
                msg = detail.map((d: any) => `${d.loc.at(-1) || 'error'}: ${d.msg}`).join(', ');
            } else if (typeof detail === 'string') {
                msg = detail;
            } else {
                msg = err.message || 'Login failed';
            }
            
            setError(`Error: ${msg} (API: ${apiUrl})`);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-[#0a0d12]">
            {/* Ambient Background Effects - subtle blue glow */}
            <div className="absolute top-[-30%] left-[-15%] w-[700px] h-[700px] bg-blue-900/30 rounded-full blur-[150px] pointer-events-none" />
            <div className="absolute bottom-[-25%] right-[-15%] w-[600px] h-[600px] bg-cyan-900/20 rounded-full blur-[130px] pointer-events-none" />
            <div className="absolute top-[40%] left-[60%] w-[300px] h-[300px] bg-blue-800/15 rounded-full blur-[100px] pointer-events-none" />

            {/* Glassmorphism Card */}
            <div className="w-full max-w-[440px] mx-4 relative z-10">
                {/* Subtle border glow */}
                <div className="absolute -inset-px bg-linear-to-b from-cyan-500/20 via-transparent to-blue-500/10 rounded-2xl"></div>

                <div className="relative bg-[#0f1318]/90 backdrop-blur-2xl border border-cyan-500/10 rounded-2xl p-8 shadow-2xl shadow-black/50">

                    {/* Header */}
                    <div className="text-center mb-10">
                        {/* Logo */}
                        <div className="flex justify-center mb-5">
                            <img src={murenaLogo} alt="Murena" className="w-14 h-14" />
                        </div>
                        <h1 className="text-3xl font-bold text-white tracking-tight">
                            Bentornato
                        </h1>
                        <p className="text-gray-400 mt-2 text-sm">
                            Accedi al Sistema Analitico Immobiliare
                        </p>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-3 text-red-400 text-sm">
                            <AlertCircle className="w-4 h-4 shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    {/* Login Form */}
                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-gray-400 ml-1">Nome utente</label>
                            <div className="relative group">
                                <UserIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-cyan-400 transition-colors" />
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="w-full bg-[#0a0d12]/80 border border-cyan-500/10 rounded-xl py-3.5 pl-11 pr-4 text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/30 transition-all"
                                    placeholder="Inserisci il tuo nome utente"
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-medium text-gray-400 ml-1">Password</label>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-cyan-400 transition-colors" />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-[#0a0d12]/80 border border-cyan-500/10 rounded-xl py-3.5 pl-11 pr-4 text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/30 transition-all"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>
                            <div className="flex justify-end">
                                <a href="#" className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors">Password dimenticata?</a>
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-linear-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold py-3.5 rounded-xl shadow-lg shadow-cyan-900/30 active:scale-[0.98] transition-all flex items-center justify-center gap-2 mt-6"
                        >
                            {isLoading ? (
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                <>
                                    <span>Accedi</span>
                                    <ArrowRight className="w-4 h-4" />
                                </>
                            )}
                        </button>
                    </form>

                    {/* Divider */}
                    <div className="mt-8 relative">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-white/5"></div>
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-[#0f1318] px-3 text-gray-500 tracking-wider">O continua con</span>
                        </div>
                    </div>

                    {/* Social Login Buttons */}
                    <div className="grid grid-cols-2 gap-3 mt-6 mb-8">
                        <button className="flex items-center justify-center gap-2 px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl transition-all group">
                            <img src={googleIcon} alt="Google" className="w-5 h-5 opacity-70 group-hover:opacity-100 transition-opacity" />
                            <span className="text-gray-400 text-sm group-hover:text-white transition-colors">Google</span>
                        </button>
                        <button className="flex items-center justify-center gap-2 px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl transition-all group">
                            <img src={microsoftIcon} alt="Microsoft" className="w-5 h-5 opacity-70 group-hover:opacity-100 transition-opacity" />
                            <span className="text-gray-400 text-sm group-hover:text-white transition-colors">Microsoft</span>
                        </button>
                    </div>

                    {/* Integrated Footer with blurred background */}
                    <div className="absolute bottom-0 left-0 w-full bg-[#0a0d12]/50 backdrop-blur-md border-t border-white/5 p-4 rounded-b-2xl">
                        <p className="text-center text-gray-500 text-sm">
                            Non hai un account? <span className="text-cyan-400 hover:text-cyan-300 cursor-pointer transition-colors">Contatta l'amministratore</span>
                        </p>
                    </div>

                </div>
            </div>
        </div>
    );
};
