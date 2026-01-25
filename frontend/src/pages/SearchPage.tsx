/**
 * SearchPage - AI Command Center Home
 *
 * Main search interface with:
 * - "NEURAL ENGINE READY" badge
 * - "Launch New Intelligence Agent" heading
 * - Auto-expanding Command Bar
 * - Suggested queries
 * - Recent History section
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    ArrowRight,
    Clock,
    CheckCircle2,
    Loader2,
    Building2,
    ToggleLeft,
    ToggleRight,
} from 'lucide-react';
import { useAnalysis } from '../hooks/useAnalysis';
import { useSettings } from '../contexts/SettingsContext';
import { analysisApi } from '../api/endpoints/analysis';
import type { AnalysisHistoryItem } from '../api/types';

const SUGGESTED_QUERIES = [
    'Uffici vicino a Porta Nuova con classe energetica A',
    'Immobili di 200mq vicino al Politecnico',
    'Negozi in centro città adatti a ristorante',
];

export const SearchPage: React.FC = () => {
    const navigate = useNavigate();
    const { demoMode, setDemoMode, llmLimit, markersLimit } = useSettings();
    const [query, setQuery] = useState('');
    const [isFocused, setIsFocused] = useState(false);
    const [recentHistory, setRecentHistory] = useState<AnalysisHistoryItem[]>([]);
    const [isLoadingHistory, setIsLoadingHistory] = useState(true);
    const [availableDemos, setAvailableDemos] = useState<string[]>([]);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const { startAnalysis, loadDemo, status, runId, isLoading } = useAnalysis();

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
                // Limit to 3 most recent completed runs
                setRecentHistory(history.filter(h => h.status === 'completed').slice(0, 3));
                setAvailableDemos(demos);
            } catch (err) {
                console.error('Failed to fetch data:', err);
            } finally {
                setIsLoadingHistory(false);
            }
        };
        fetchData();
    }, []);

    // Navigate to processing when analysis starts (both real and demo runs)
    useEffect(() => {
        if (status === 'processing' && runId) {
            navigate(`/processing/${runId}`);
        }
    }, [status, runId, navigate]);

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!query.trim() || isLoading) return;

        try {
            if (demoMode && availableDemos.length > 0) {
                // In demo mode, load a pre-computed demo
                const id = await loadDemo(availableDemos[0]);
                navigate(`/processing/${id}`);
            } else {
                // Pass settings to the analysis
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
        // Navigate to map with this run's results
        navigate(`/map?run_id=${item.run_id}`);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="min-h-full relative flex flex-col items-center justify-center p-8 overflow-hidden">
            {/* Background Image */}
            <div
                className="absolute inset-0 z-0"
                style={{
                    backgroundImage: 'url(/backgrounds/buildings.jpg)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center bottom',
                    backgroundRepeat: 'no-repeat',
                    opacity: 0.5,
                }}
            />
            {/* Gradient overlay for text readability */}
            <div className="absolute inset-0 z-0 bg-linear-to-b from-[#0a0d12] via-[#0a0d12]/80 to-[#0a0d12]/95" />
            <div className="absolute inset-0 z-0 bg-linear-to-t from-[#0a0d12] via-transparent to-transparent" />

            {/* Main Content */}
            <div className="w-full max-w-3xl mx-auto relative z-10">
                {/* Neural Engine Badge */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="flex justify-center mb-8"
                >
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        <span className="text-xs font-medium text-emerald-400 tracking-wider uppercase">
                            Neural Engine Ready
                        </span>
                    </div>
                </motion.div>

                {/* Main Heading */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-center mb-16"
                >
                    <h1 className="text-4xl md:text-5xl font-bold text-white mb-3">
                        Real Estate Intelligence
                    </h1>
                    <h2 className="text-4xl md:text-5xl font-bold bg-linear-to-r from-blue-400 via-cyan-400 to-blue-500 bg-clip-text text-transparent pb-2">
                        Powered by Agentic AI
                    </h2>
                </motion.div>

                {/* Command Bar */}
                <motion.form
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    onSubmit={handleSubmit}
                    className="relative mb-8"
                >
                    <div className={`
                        relative bg-[#0f1218]/80 backdrop-blur-xl rounded-2xl border transition-all duration-300 overflow-hidden
                        ${isFocused
                            ? 'border-cyan-500/50 shadow-lg shadow-cyan-500/20'
                            : 'border-white/10 hover:border-white/20'
                        }
                    `}>
                        {/* Search Icon */}
                        <div className="absolute left-5 top-1/2 -translate-y-1/2 text-gray-500">
                            <Search className="w-5 h-5" />
                        </div>

                        <div className="flex items-stretch">
                            {/* Textarea */}
                            <textarea
                                ref={textareaRef}
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onFocus={() => setIsFocused(true)}
                                onBlur={() => setIsFocused(false)}
                                onKeyDown={handleKeyDown}
                                placeholder="Describe what you're looking for..."
                                rows={1}
                                className="
                                    flex-1 bg-transparent text-white placeholder-gray-500
                                    pl-14 pr-4 py-4 text-base resize-none outline-none
                                    min-h-[56px] max-h-[200px]
                                    whitespace-pre-wrap break-words [overflow-wrap:anywhere]
                                    overflow-y-auto overflow-x-hidden
                                "
                                disabled={isLoading}
                            />

                            {/* Submit Button (in flow, no overlap) */}
                            <div className="shrink-0 pr-3 pl-2 flex items-center">
                                <motion.button
                                    type="submit"
                                    disabled={!query.trim() || isLoading}
                                    whileHover={{ scale: 1.02 }}
                                    whileTap={{ scale: 0.98 }}
                                    className={`
                                        flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm whitespace-nowrap
                                        transition-all duration-200
                                        ${query.trim() && !isLoading
                                            ? 'bg-linear-to-r from-blue-600 to-cyan-500 text-white shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40'
                                            : 'bg-white/5 text-gray-500 cursor-not-allowed'
                                        }
                                    `}
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            <span>Starting...</span>
                                        </>
                                    ) : (
                                        <>
                                            <span>Initialize</span>
                                            <ArrowRight className="w-4 h-4" />
                                        </>
                                    )}
                                </motion.button>
                            </div>
                        </div>
                    </div>
                </motion.form>

                {/* Demo Warning - Elegant Glass Style below search */}
                {demoMode && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center justify-center gap-2 mb-8"
                    >
                        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-900/20 border border-cyan-500/20 backdrop-blur-md shadow-lg shadow-cyan-900/10">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                            </span>
                            <span className="text-xs font-medium text-cyan-300 tracking-wide">
                                Demo Mode Active <span className="text-cyan-500/70 mx-1">|</span> Using pre-computed results (no token usage)
                            </span>
                        </div>
                    </motion.div>
                )}


                {/* Demo Mode Toggle - Fixed Top Right */}
                <div className="fixed top-8 right-8 z-50">
                    <button
                        onClick={() => setDemoMode(!demoMode)}
                        className={`
                            flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium border backdrop-blur-md transition-all duration-300
                            ${demoMode
                                ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 ring-1 ring-cyan-500/20 shadow-lg shadow-cyan-500/10'
                                : 'bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-white hover:border-white/10'
                            }
                        `}
                    >
                        {demoMode ? (
                            <ToggleRight className="w-4 h-4 text-cyan-400" />
                        ) : (
                            <ToggleLeft className="w-4 h-4" />
                        )}
                        <span>Demo Mode</span>
                    </button>
                </div>

                {/* Suggestions */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="flex flex-wrap items-center justify-center gap-3 mb-16"
                >
                    <span className="text-sm text-gray-500">Suggested:</span>
                    {SUGGESTED_QUERIES.map((suggestion, i) => (
                        <button
                            key={i}
                            onClick={() => handleSuggestionClick(suggestion)}
                            className="text-sm text-blue-400/80 hover:text-blue-300 transition-colors"
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
                >
                    <div className="flex items-center gap-2 mb-4">
                        <Clock className="w-4 h-4 text-gray-500" />
                        <h3 className="text-sm font-medium text-gray-400">Recent Insights</h3>
                        <span className="text-xs text-gray-600">
                            {recentHistory.length > 0 && `${recentHistory.length} completed`}
                        </span>
                    </div>

                    {isLoadingHistory ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="w-5 h-5 text-gray-500 animate-spin" />
                        </div>
                    ) : recentHistory.length === 0 ? (
                        <div className="text-center py-8 text-gray-500 text-sm">
                            No completed analyses yet. Start your first search above!
                        </div>
                    ) : (
                        <div className="grid gap-3">
                            {recentHistory.map((item, i) => (
                                <motion.button
                                    key={item.run_id}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.1 * i }}
                                    onClick={() => handleHistoryClick(item)}
                                    className="
                                        w-full p-4 rounded-xl bg-[#12151a]/60 border border-white/5
                                        hover:bg-[#12151a] hover:border-white/10
                                        transition-all duration-200 text-left group
                                        overflow-hidden
                                    "
                                >
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1.5">
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                                    <CheckCircle2 className="w-3 h-3" />
                                                    COMPLETED
                                                </span>
                                                <span className="text-xs text-gray-500">
                                                    {new Date(item.created_at).toLocaleDateString('it-IT', {
                                                        day: 'numeric',
                                                        month: 'short',
                                                        hour: '2-digit',
                                                        minute: '2-digit',
                                                    })}
                                                </span>
                                            </div>
                                            <p
                                                className="text-sm text-white font-medium group-hover:text-cyan-300 transition-colors break-words [overflow-wrap:anywhere]"
                                                style={{
                                                    display: '-webkit-box',
                                                    WebkitLineClamp: 2,
                                                    WebkitBoxOrient: 'vertical',
                                                    overflow: 'hidden',
                                                }}
                                            >
                                                {item.query}
                                            </p>
                                            {item.buildings_count !== undefined && (
                                                <div className="flex items-center gap-1 mt-1 text-xs text-gray-500">
                                                    <Building2 className="w-3 h-3" />
                                                    <span>{item.buildings_count} properties found</span>
                                                </div>
                                            )}
                                        </div>
                                        <ArrowRight className="w-4 h-4 text-gray-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
                                    </div>
                                </motion.button>
                            ))}
                        </div>
                    )}
                </motion.div>
            </div>
        </div>
    );
};

export default SearchPage;
