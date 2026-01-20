import React, { useState } from 'react';
import { ChevronDown, History, Loader2, X, Search } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { AnalysisHistoryItem } from '../../api/types';

interface MapRunSelectorProps {
    history: AnalysisHistoryItem[];
    activeRunId: string | null;
    isLoading: boolean;
    onSelectRun: (runId: string) => void;
    onClearResults: () => void;
}

export const MapRunSelector: React.FC<MapRunSelectorProps> = ({
    history,
    activeRunId,
    isLoading,
    onSelectRun,
    onClearResults,
}) => {
    const [isOpen, setIsOpen] = useState(false);

    const activeRun = history.find(h => h.run_id === activeRunId);

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('it-IT', {
            day: '2-digit',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const truncateQuery = (query: string, maxLen = 40) => {
        if (query.length <= maxLen) return query;
        return query.substring(0, maxLen) + '...';
    };

    return (
        <div className="relative">
            {/* Trigger Button */}
            <div className="bg-[#0a0d12]/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-xl shadow-black/30 p-2 flex items-center gap-2">
                <div className={`px-2 ${activeRun ? 'text-cyan-400' : 'text-gray-500'}`}>
                    {isLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                    ) : (
                        <History className="w-4 h-4" />
                    )}
                </div>

                <button
                    onClick={() => setIsOpen(!isOpen)}
                    disabled={isLoading}
                    className={`
                        flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                        transition-all duration-200 border whitespace-nowrap
                        ${isOpen || activeRun
                            ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50'
                            : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }
                        disabled:opacity-50
                    `}
                >
                    {activeRun ? (
                        <span className="max-w-[150px] truncate font-medium">
                            {truncateQuery(activeRun.query, 25)}
                        </span>
                    ) : (
                        <span className="font-medium">Seleziona ricerca...</span>
                    )}

                    <ChevronDown
                        className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    />
                </button>
            </div>

            {/* Dropdown */}
            <AnimatePresence>
                {isOpen && (
                    <>
                        {/* Backdrop */}
                        <div
                            className="fixed inset-0 z-[450]"
                            onClick={() => setIsOpen(false)}
                        />

                        <motion.div
                            initial={{ opacity: 0, y: -10, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: -10, scale: 0.95 }}
                            transition={{ duration: 0.15 }}
                            className="absolute top-full left-0 mt-2 w-[320px] bg-[#0a0d12]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-2xl shadow-black/50 z-[500] overflow-hidden"
                        >
                            {/* Header */}
                            <div className="px-3 py-2 border-b border-white/5 flex items-center justify-between">
                                <span className="text-[10px] uppercase text-gray-500 font-medium tracking-wider">
                                    Ricerche recenti
                                </span>
                                {activeRunId && (
                                    <button
                                        onClick={() => {
                                            onClearResults();
                                            setIsOpen(false);
                                        }}
                                        className="text-[10px] text-red-400 hover:text-red-300 transition-colors flex items-center gap-1"
                                    >
                                        <X className="w-3 h-3" />
                                        Pulisci
                                    </button>
                                )}
                            </div>

                            {/* History List */}
                            <div className="max-h-[300px] overflow-auto custom-scrollbar">
                                {/* Default Map Option - Always visible */}
                                <button
                                    onClick={() => {
                                        onClearResults();
                                        setIsOpen(false);
                                    }}
                                    className={`w-full text-left px-3 py-2.5 hover:bg-white/5 transition-colors border-b border-white/5 ${!activeRunId ? 'bg-cyan-500/10 border-l-2 border-l-cyan-400' : ''
                                        }`}
                                >
                                    <div className="flex items-center gap-2">
                                        <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-gray-600 to-gray-700 flex items-center justify-center">
                                            <span className="text-xs">🗺️</span>
                                        </div>
                                        <div>
                                            <p className={`text-sm ${!activeRunId ? 'text-cyan-400 font-medium' : 'text-gray-300'}`}>
                                                Mappa completa
                                            </p>
                                            <p className="text-[10px] text-gray-500">
                                                Visualizza tutti i marker di background
                                            </p>
                                        </div>
                                    </div>
                                </button>

                                {history.length === 0 ? (
                                    <div className="p-4 text-center">
                                        <Search className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                                        <p className="text-sm text-gray-500">
                                            Nessuna ricerca recente
                                        </p>
                                        <p className="text-xs text-gray-600 mt-1">
                                            Effettua una ricerca per vederla qui
                                        </p>
                                    </div>
                                ) : (
                                    <div className="py-1">
                                        {history.map((item) => {
                                            const isActive = item.run_id === activeRunId;
                                            return (
                                                <button
                                                    key={item.run_id}
                                                    onClick={() => {
                                                        if (isActive) {
                                                            // Clicking active = deselect
                                                            onClearResults();
                                                        } else {
                                                            onSelectRun(item.run_id);
                                                        }
                                                        setIsOpen(false);
                                                    }}
                                                    className={`w-full text-left px-3 py-2.5 hover:bg-white/5 transition-colors ${isActive ? 'bg-cyan-500/10 border-l-2 border-cyan-400' : ''
                                                        }`}
                                                >
                                                    <div className="flex items-start justify-between gap-2">
                                                        <div className="flex-1 min-w-0">
                                                            <p className={`text-sm truncate ${isActive ? 'text-cyan-400 font-medium' : 'text-gray-300'}`}>
                                                                {truncateQuery(item.query)}
                                                            </p>
                                                            <div className="flex items-center gap-2 mt-1">
                                                                <span className="text-[10px] text-gray-500">
                                                                    {formatDate(item.created_at)}
                                                                </span>
                                                                {item.buildings_count && (
                                                                    <span className="text-[10px] bg-white/5 text-gray-400 px-1.5 py-0.5 rounded">
                                                                        {item.buildings_count} immobili
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <span
                                                            className={`text-[9px] px-1.5 py-0.5 rounded uppercase font-medium ${item.status === 'completed'
                                                                    ? 'bg-emerald-500/20 text-emerald-400'
                                                                    : item.status === 'failed'
                                                                        ? 'bg-red-500/20 text-red-400'
                                                                        : 'bg-amber-500/20 text-amber-400'
                                                                }`}
                                                        >
                                                            {item.status === 'completed' ? '✓' : item.status === 'failed' ? '✗' : '...'}
                                                        </span>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
};
