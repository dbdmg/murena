/**
 * SearchPage - AI Command Center Home
 *
 * Main search interface with:
 * - Refined glassmorphism Command Bar
 * - Design-token based styling
 * - Decoupled HistoryItem component
 * - Suggestion system
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    ArrowRight,
    Clock,
    Loader2,
} from 'lucide-react';
import { useAnalysis } from '../hooks/useAnalysis';
import { useSettings } from '../contexts/SettingsContext';
import { translations } from '../utils/translations';
import { analysisApi } from '../api/endpoints/analysis';
import type { AnalysisHistoryItem } from '../api/types';
import { HistoryItem } from '../components/search/HistoryItem';

const SUGGESTED_QUERIES = [
    'Uffici vicino a Porta Nuova con classe energetica alta',
    'Edifici di almeno 1000 mq vicino al Politecnico',
    'Spazi commerciali in centro comodi ai trasporti',
];

import murenaLogo217 from '../assets/brand/MURENA_217x34px.svg';

export const SearchPage: React.FC = () => {
    const navigate = useNavigate();
    const { dataSource, language, llmLimit, markersLimit } = useSettings();
    const [query, setQuery] = useState('');
    const [isFocused, setIsFocused] = useState(false);
    const [recentHistory, setRecentHistory] = useState<AnalysisHistoryItem[]>([]);
    const [isLoadingHistory, setIsLoadingHistory] = useState(true);
    const [availableDemos, setAvailableDemos] = useState<string[]>([]);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const { startAnalysis, loadDemo, status, runId, isLoading } = useAnalysis();

    const t = translations[language];
    const suggestions = SUGGESTED_QUERIES;

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [query]);

    // Fetch recent history and demos on mount
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [history, demos] = await Promise.all([
                    analysisApi.getHistory(10),
                    analysisApi.getDemos().catch(() => []),
                ]);
                setRecentHistory(history.slice(0, 3));
                setAvailableDemos(demos);
            } catch (err) {
                console.error('Failed to fetch data:', err);
            } finally {
                setIsLoadingHistory(false);
            }
        };
        fetchData();
    }, []);

    // Navigate to processing when analysis starts
    useEffect(() => {
        if (status === 'processing' && runId) {
            navigate(`/processing/${runId}`);
        }
    }, [status, runId, navigate]);

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!query.trim() || isLoading) return;

        try {
            if (dataSource === 'sandbox' && availableDemos.length > 0) {
                const id = await loadDemo(availableDemos[0]);
                navigate(`/processing/${id}`);
            } else {
                const id = await startAnalysis({
                    query: query.trim(),
                    llm_limit: llmLimit,
                    map_limit: markersLimit,
                });
                navigate(`/processing/${id}`);
            }
        } catch (err) {
            console.error('Failed to start analysis:', err);
        }
    };

    const handleSuggestionClick = (suggestion: string) => {
        setQuery(suggestion);
        textareaRef.current?.focus();
    };

    const handleHistoryClick = (item: AnalysisHistoryItem) => {
        navigate(`/map?run_id=${item.run_id}`);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="min-h-full relative flex flex-col items-center justify-center p-8 overflow-hidden bg-(--bg-main)">
            {/* Background Image with refined layer */}
            <div
                className="absolute inset-0 z-0 opacity-40 scale-105 pointer-events-none"
                style={{
                    backgroundImage: 'url(/backgrounds/buildings.jpg)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center bottom',
                    backgroundRepeat: 'no-repeat',
                }}
            />
            {/* Gradient overlays with design tokens */}
            <div className="absolute inset-0 z-0 bg-linear-to-b from-(--bg-main) via-(--bg-main)/90 to-(--bg-main)/95 pointer-events-none" />
            <div className="absolute inset-0 z-0 bg-linear-to-t from-(--bg-main) via-transparent to-transparent opacity-80 pointer-events-none" />

            {/* Main Content */}
            <div className="w-full max-w-3xl mx-auto relative z-10">

                {/* Logo Murena */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-center mb-10"
                >
                    <img src={murenaLogo217} alt="Murena" className="w-[300px] h-auto" />
                </motion.div>

                {/* Command Bar */}
                <motion.form
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    onSubmit={handleSubmit}
                    className="relative mb-10"
                >
                    <div className={`
                        relative bg-(--glass-bg) backdrop-blur-2xl rounded-2xl border transition-all duration-500 overflow-hidden
                        ${isFocused
                            ? 'border-(--accent-cyan)/50 ring-4 ring-(--accent-cyan)/10 shadow-2xl scale-[1.01]'
                            : 'border-(--border-light) hover:border-(--border-light)/30'
                        }
                    `}>
                        <div className="absolute left-6 top-1/2 -translate-y-1/2 text-(--text-tertiary)">
                            <Search className="w-5 h-5" />
                        </div>

                        <div className="flex items-stretch">
                            <textarea
                                ref={textareaRef}
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onFocus={() => setIsFocused(true)}
                                onBlur={() => setIsFocused(false)}
                                onKeyDown={handleKeyDown}
                                placeholder={t.search.placeholder}
                                rows={1}
                                className="
                                    flex-1 bg-transparent text-(--text-primary) placeholder-(--text-tertiary)
                                    pl-16 pr-6 py-6 text-lg font-medium resize-none outline-none
                                    min-h-[72px] max-h-[200px]
                                "
                                disabled={isLoading}
                            />

                            <div className="shrink-0 pr-4 pl-2 flex items-center">
                                <motion.button
                                    type="submit"
                                    disabled={!query.trim() || isLoading}
                                    whileHover={{ scale: 1.05 }}
                                    whileTap={{ scale: 0.95 }}
                                    className={`
                                        flex items-center gap-3 px-6 py-3 rounded-xl font-bold text-sm tracking-wide uppercase
                                        transition-all duration-300
                                        ${query.trim() && !isLoading
                                            ? 'bg-linear-to-r from-emerald-600 to-cyan-600 text-white shadow-lg shadow-emerald-500/30'
                                            : 'bg-white/5 text-(--text-tertiary) cursor-not-allowed'
                                        }
                                    `}
                                >
                                    {isLoading ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            <span>{t.search.submit}</span>
                                            <ArrowRight className="w-5 h-5" />
                                        </>
                                    )}
                                </motion.button>
                            </div>
                        </div>
                    </div>
                </motion.form>

                {/* Suggestions */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="flex flex-wrap items-center justify-center gap-4 mb-20"
                >
                    <span className="text-sm text-(--text-tertiary) font-medium uppercase tracking-widest">{t.search.suggested}</span>
                    {suggestions.map((suggestion, i) => (
                        <button
                            key={i}
                            onClick={() => handleSuggestionClick(suggestion)}
                            className="text-sm font-semibold text-emerald-400/80 hover:text-emerald-300 hover:underline decoration-emerald-500/30 underline-offset-4 transition-all"
                        >
                            {suggestion}
                        </button>
                    ))}
                </motion.div>

                {/* Recent History */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="space-y-6"
                >
                    <div className="flex items-center justify-between px-2">
                        <div className="flex items-center gap-3">
                            <Clock className="w-4 h-4 text-emerald-500/60" />
                            <h3 className="text-xs font-bold uppercase tracking-widest text-(--text-tertiary)">{t.search.recentHistory}</h3>
                        </div>
                        <span className="text-[10px] font-bold text-gray-700 uppercase tracking-tighter">
                            {recentHistory.length > 0 && `${recentHistory.length} ${t.search.found}`}
                        </span>
                    </div>

                    {isLoadingHistory ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
                        </div>
                    ) : recentHistory.length === 0 ? (
                        <div className="text-center py-16 text-(--text-tertiary) text-sm bg-white/5 rounded-2xl border border-dashed border-(--border-light)">
                            {t.search.noHistory}
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {recentHistory.map((item, i) => (
                                <HistoryItem
                                    key={item.run_id}
                                    item={item}
                                    index={i}
                                    language={language}
                                    translations={translations}
                                    onClick={handleHistoryClick}
                                />
                            ))}
                        </div>
                    )}
                </motion.div>
            </div>
        </div>
    );
};

export default SearchPage;
