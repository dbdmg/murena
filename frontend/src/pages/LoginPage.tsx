import React, { useState } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { useSettings } from '../contexts/SettingsContext';
import { translations } from '../utils/translations';
import { Lock, User as UserIcon, AlertCircle, ArrowRight, Languages } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import googleIcon from '../assets/icons/icons8-google-48.png';
import microsoftIcon from '../assets/icons/icons8-microsoft-48.png';
import murenaLogo from '../assets/brand/MURENA_no-casetta_56x56px.svg';

interface FastApiValidationError {
    loc?: Array<string | number>;
    msg?: string;
}

export const LoginPage: React.FC = () => {
    const { login } = useAuth();
    const { language, setLanguage } = useSettings();
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const t = translations[language];

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            await login({ username, password });
            navigate('/');
        } catch (err: unknown) {
            console.error(err);
            const apiUrl = import.meta.env.VITE_API_URL || '/api/v1';
            
            // Handle FastAPI validation errors or standard messages
            const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
            let msg = t.login.failed;
            
            if (Array.isArray(detail)) {
                // Formatting for validation error list: "field: error message"
                msg = detail.map((d: FastApiValidationError) => `${d.loc?.at(-1) || 'error'}: ${d.msg || t.login.failed}`).join(', ');
            } else if (typeof detail === 'string') {
                msg = detail;
            } else if (err instanceof Error) {
                msg = err.message;
            } else {
                msg = t.login.failed;
            }
            
            setError(`Error: ${msg} (API: ${apiUrl})`);
        } finally {
            setIsLoading(false);
        }
    };

    const toggleLanguage = () => {
        setLanguage(language === 'it' ? 'en' : 'it');
    };

    const currentLanguageCode = language === 'it' ? 'IT' : 'EN';
    const languageToggleTitle = language === 'it'
        ? 'Lingua corrente: Italiano. Switch to English'
        : 'Current language: English. Passa all\'Italiano';

    return (
        <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-[#0a0d12]">
            {/* Language Switcher - Floating for Login Page */}
            <div className="absolute top-6 right-6 z-50">
                <button
                    onClick={toggleLanguage}
                    title={languageToggleTitle}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10 backdrop-blur-md transition-all font-medium text-xs"
                >
                    <Languages className="w-4 h-4 text-emerald-500" />
                    <span>{currentLanguageCode}</span>
                </button>
            </div>

            {/* Ambient Background Effects - subtle blue glow */}
            <div className="absolute top-[-30%] left-[-15%] w-[700px] h-[700px] bg-emerald-900/30 rounded-full blur-[150px] pointer-events-none" />
            <div className="absolute bottom-[-25%] right-[-15%] w-[600px] h-[600px] bg-green-900/20 rounded-full blur-[130px] pointer-events-none" />
            <div className="absolute top-[40%] left-[60%] w-[300px] h-[300px] bg-emerald-800/15 rounded-full blur-[100px] pointer-events-none" />

            {/* Glassmorphism Card */}
            <div className="w-full max-w-[440px] mx-4 relative z-10">
                {/* Subtle border glow */}
                <div className="absolute -inset-px bg-linear-to-b from-emerald-500/20 via-transparent to-green-500/10 rounded-2xl"></div>

                <div className="relative bg-[#0f1318]/90 backdrop-blur-2xl border border-emerald-500/10 rounded-2xl p-8 shadow-2xl shadow-black/50">

                    {/* Header */}
                    <div className="text-center mb-10">
                        {/* Logo */}
                        <div className="flex justify-center mb-5">
                            <img src={murenaLogo} alt="Murena" className="w-14 h-14" />
                        </div>
                        <h1 className="text-3xl font-bold text-white tracking-tight">
                            {t.login.welcome}
                        </h1>
                        <p className="text-gray-400 mt-2 text-sm">
                            {t.login.subtitle}
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
                            <label className="text-xs font-medium text-gray-400 ml-1">{t.login.username}</label>
                            <div className="relative group">
                                <UserIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-emerald-400 transition-colors" />
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="w-full bg-[#0a0d12]/80 border border-emerald-500/10 rounded-xl py-3.5 pl-11 pr-4 text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/30 transition-all"
                                    placeholder={t.login.usernamePlaceholder}
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-medium text-gray-400 ml-1">{t.login.password}</label>
                            <div className="relative group">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-emerald-400 transition-colors" />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-[#0a0d12]/80 border border-emerald-500/10 rounded-xl py-3.5 pl-11 pr-4 text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/30 transition-all"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>
                            <div className="flex justify-end">
                                <a href="#" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">{t.login.forgotPassword}</a>
                            </div>
                        </div>

                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full bg-linear-to-r from-emerald-500 to-green-600 hover:from-emerald-400 hover:to-green-500 text-white font-semibold py-3.5 rounded-xl shadow-lg shadow-emerald-900/30 active:scale-[0.98] transition-all flex items-center justify-center gap-2 mt-6"
                            >
                            {isLoading ? (
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                <>
                                    <span>{t.login.submit}</span>
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
                            <span className="bg-[#0f1318] px-3 text-gray-500 tracking-wider font-medium">{t.login.orContinueWith}</span>
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
                            {t.login.noAccount} <span className="text-emerald-400 hover:text-emerald-300 cursor-pointer transition-colors font-medium">{t.login.contactAdmin}</span>
                        </p>
                    </div>

                </div>
            </div>
        </div>
    );
};
