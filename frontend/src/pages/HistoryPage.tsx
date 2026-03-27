/**
 * HistoryPage - Analysis History Management
 *
 * Features:
 * - Card grid layout of all past analyses
 * - Search by query text
 * - Filter by date range (last 7 days, 30 days, all time)
 * - Favorites system (stored in localStorage)
 * - Multi-select for bulk actions (including all pages)
 * - Delete single or multiple runs
 * - Open run detail modal with agent steps
 * - Load run directly to map
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    Clock,
    Calendar,
    Star,
    Trash2,
    Map as MapIcon,
    ChevronLeft,
    ChevronRight,
    CheckCircle2,
    XCircle,
    Loader2,
    Building2,
    Check,
    AlertTriangle,
    Eye,
    CheckSquare,
} from 'lucide-react';
import { analysisApi } from '../api/endpoints/analysis';
import type { AnalysisHistoryItem } from '../api/types';
import { RunDetailModal } from '../components/history';
import { formatRunDate } from '../utils/dateUtils';

// Date filter options
type DateFilter = 'all' | '7days' | '30days' | '90days';

const DATE_FILTERS: { value: DateFilter; label: string }[] = [
    { value: 'all', label: 'Tutti' },
    { value: '7days', label: 'Ultimi 7 giorni' },
    { value: '30days', label: 'Ultimi 30 giorni' },
    { value: '90days', label: 'Ultimi 90 giorni' },
];

const ITEMS_PER_PAGE = 12; // 4x3 grid
const FAVORITES_KEY = 'realestate_history_favorites';

export const HistoryPage: React.FC = () => {
    const navigate = useNavigate();

    // Data state
    const [allRuns, setAllRuns] = useState<AnalysisHistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filter/search state
    const [searchQuery, setSearchQuery] = useState('');
    const [dateFilter, setDateFilter] = useState<DateFilter>('all');
    const [showOnlyFavorites, setShowOnlyFavorites] = useState(false);

    // Pagination
    const [currentPage, setCurrentPage] = useState(1);

    // Selection state
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [isSelectionMode, setIsSelectionMode] = useState(false);

    // Favorites (persisted to localStorage)
    const [favorites, setFavorites] = useState<Set<string>>(() => {
        const stored = localStorage.getItem(FAVORITES_KEY);
        return stored ? new Set(JSON.parse(stored)) : new Set();
    });

    // Modal state
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

    // Delete confirmation
    const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Save favorites to localStorage
    useEffect(() => {
        localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favorites]));
    }, [favorites]);

    // Clean up favorites when runs are deleted (remove orphaned favorites)
    useEffect(() => {
        if (allRuns.length > 0) {
            const existingRunIds = new Set(allRuns.map(r => r.run_id));
            setFavorites(prev => {
                const validFavorites = new Set([...prev].filter(id => existingRunIds.has(id)));
                if (validFavorites.size !== prev.size) {
                    return validFavorites;
                }
                return prev;
            });
        }
    }, [allRuns]);

    // Fetch all runs
    const fetchRuns = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);
            const history = await analysisApi.getHistory(500, 0);
            setAllRuns(history);
        } catch (err: any) {
            console.error('Failed to fetch history:', err);
            const status = err.response?.status;
            const detail = err.response?.data?.detail;
            setError(`Impossibile caricare la cronologia${status ? ` (${status})` : ''}${detail ? `: ${detail}` : ''}`);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchRuns();
    }, [fetchRuns]);

    // Filter runs based on search, date, and favorites
    const filteredRuns = useMemo(() => {
        let result = allRuns;

        // Search filter
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            result = result.filter(run =>
                run.query.toLowerCase().includes(query) ||
                run.run_id.toLowerCase().includes(query)
            );
        }

        // Date filter
        if (dateFilter !== 'all') {
            const now = new Date();
            const daysAgo = dateFilter === '7days' ? 7 : dateFilter === '30days' ? 30 : 90;
            const cutoff = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000);
            result = result.filter(run => new Date(run.created_at) >= cutoff);
        }

        // Favorites filter
        if (showOnlyFavorites) {
            result = result.filter(run => favorites.has(run.run_id));
        }

        return result;
    }, [allRuns, searchQuery, dateFilter, showOnlyFavorites, favorites]);

    // Paginated runs
    const paginatedRuns = useMemo(() => {
        const start = (currentPage - 1) * ITEMS_PER_PAGE;
        return filteredRuns.slice(start, start + ITEMS_PER_PAGE);
    }, [filteredRuns, currentPage]);

    const totalPages = Math.ceil(filteredRuns.length / ITEMS_PER_PAGE);

    // Reset page when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [searchQuery, dateFilter, showOnlyFavorites]);

    // Toggle favorite
    const toggleFavorite = useCallback((runId: string, e?: React.MouseEvent) => {
        e?.stopPropagation();
        setFavorites(prev => {
            const next = new Set(prev);
            if (next.has(runId)) {
                next.delete(runId);
            } else {
                next.add(runId);
            }
            return next;
        });
    }, []);

    // Toggle selection
    const toggleSelection = useCallback((runId: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(runId)) {
                next.delete(runId);
            } else {
                next.add(runId);
            }
            return next;
        });
    }, []);

    // Select all filtered (across all pages)
    const selectAllFiltered = useCallback(() => {
        const allFilteredIds = new Set(filteredRuns.map(r => r.run_id));
        setSelectedIds(allFilteredIds);
    }, [filteredRuns]);

    // Select only current page
    const selectCurrentPage = useCallback(() => {
        const pageIds = new Set(paginatedRuns.map(r => r.run_id));
        setSelectedIds(prev => new Set([...prev, ...pageIds]));
    }, [paginatedRuns]);

    // Clear selection
    const clearSelection = useCallback(() => {
        setSelectedIds(new Set());
        setIsSelectionMode(false);
    }, []);

    // Delete single run
    const deleteRun = useCallback(async (runId: string) => {
        try {
            setIsDeleting(true);
            await analysisApi.deleteRun(runId);
            setAllRuns(prev => prev.filter(r => r.run_id !== runId));
            setSelectedIds(prev => {
                const next = new Set(prev);
                next.delete(runId);
                return next;
            });
            setDeleteConfirmId(null);
        } catch (err) {
            console.error('Failed to delete run:', err);
        } finally {
            setIsDeleting(false);
        }
    }, []);

    // Delete selected runs
    const deleteSelected = useCallback(async () => {
        if (selectedIds.size === 0) return;

        try {
            setIsDeleting(true);
            await Promise.all([...selectedIds].map(id => analysisApi.deleteRun(id)));
            setAllRuns(prev => prev.filter(r => !selectedIds.has(r.run_id)));
            clearSelection();
        } catch (err) {
            console.error('Failed to delete runs:', err);
        } finally {
            setIsDeleting(false);
        }
    }, [selectedIds, clearSelection]);

    // Navigate to map with run
    const loadToMap = useCallback((runId: string) => {
        navigate(`/map?run_id=${runId}`);
    }, [navigate]);


    // Get status display
    const getStatusDisplay = (status: string) => {
        switch (status) {
            case 'completed':
                return { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', label: 'Completato' };
            case 'processing':
                return { icon: Loader2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', label: 'In corso', animate: true };
            case 'failed':
                return { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20', label: 'Errore' };
            default:
                return { icon: Clock, color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20', label: status };
        }
    };

    // Check if all filtered are selected
    const allSelected = filteredRuns.length > 0 && filteredRuns.every(r => selectedIds.has(r.run_id));

    return (
        <div className="h-full w-full flex flex-col overflow-hidden p-6">
            {/* Header */}
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-xl bg-linear-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                        <Clock className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Cronologia Ricerche</h1>
                        <p className="text-sm text-gray-500">
                            {filteredRuns.length} ricerche trovate
                            {showOnlyFavorites && ' (solo preferiti)'}
                        </p>
                    </div>
                </div>
            </div>

            {/* Filters Bar */}
            <div className="mb-4 flex flex-wrap items-center gap-3">
                {/* Search */}
                <div className="relative flex-1 min-w-[250px] max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        type="text"
                        placeholder="Cerca per query o ID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-[#0f1218]/80 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all"
                    />
                </div>

                {/* Date Filter */}
                <div className="flex items-center gap-1 bg-[#0f1218]/80 border border-white/10 rounded-xl p-1">
                    {DATE_FILTERS.map(({ value, label }) => (
                        <button
                            key={value}
                            onClick={() => setDateFilter(value)}
                            className={`
                                px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                                ${dateFilter === value
                                    ? 'bg-emerald-500/20 text-emerald-400'
                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                                }
                            `}
                        >
                            {label}
                        </button>
                    ))}
                </div>

                {/* Favorites Toggle */}
                <button
                    onClick={() => setShowOnlyFavorites(!showOnlyFavorites)}
                    className={`
                        flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all border
                        ${showOnlyFavorites
                            ? 'bg-amber-500/20 text-amber-400 border-amber-500/50'
                            : 'bg-[#0f1218]/80 text-gray-400 border-white/10 hover:text-white hover:border-white/20'
                        }
                    `}
                >
                    <Star className={`w-4 h-4 ${showOnlyFavorites ? 'fill-amber-400' : ''}`} />
                    Preferiti
                    {favorites.size > 0 && (
                        <span className="bg-amber-500/30 px-1.5 py-0.5 rounded text-[10px]">
                            {favorites.size}
                        </span>
                    )}
                </button>

                {/* Selection Mode Toggle */}
                <button
                    onClick={() => {
                        setIsSelectionMode(!isSelectionMode);
                        if (isSelectionMode) clearSelection();
                    }}
                    className={`
                        flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all border
                        ${isSelectionMode
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                            : 'bg-[#0f1218]/80 text-gray-400 border-white/10 hover:text-white hover:border-white/20'
                        }
                    `}
                >
                    <Check className="w-4 h-4" />
                    Seleziona
                </button>
            </div>

            {/* Selection Actions Bar */}
            <AnimatePresence>
                {isSelectionMode && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="mb-4 flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-4 py-3"
                    >
                        <span className="text-sm text-emerald-300">
                            {selectedIds.size} selezionati
                            {selectedIds.size > 0 && ` su ${filteredRuns.length}`}
                        </span>
                        <div className="flex-1" />

                        {/* Select All Toggle */}
                        <button
                            onClick={allSelected ? clearSelection : selectAllFiltered}
                            className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                        >
                            <CheckSquare className={`w-3.5 h-3.5 ${allSelected ? 'fill-emerald-400' : ''}`} />
                            {allSelected ? 'Deseleziona tutto' : `Seleziona tutto (${filteredRuns.length})`}
                        </button>

                        <div className="w-px h-4 bg-emerald-500/30" />

                        <button
                            onClick={selectCurrentPage}
                            className="text-xs text-gray-400 hover:text-white transition-colors"
                        >
                            Solo questa pagina
                        </button>

                        {selectedIds.size > 0 && (
                            <>
                                <div className="w-px h-4 bg-indigo-500/30" />
                                <button
                                    onClick={deleteSelected}
                                    disabled={isDeleting}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-all disabled:opacity-50"
                                >
                                    {isDeleting ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                        <Trash2 className="w-3.5 h-3.5" />
                                    )}
                                    Elimina ({selectedIds.size})
                                </button>
                            </>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Content */}
            <div className="flex-1 overflow-auto">
                {isLoading ? (
                    <div className="flex items-center justify-center h-64">
                        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center h-64 text-red-400">
                        <AlertTriangle className="w-10 h-10 mb-3" />
                        <p>{error}</p>
                        <button
                            onClick={fetchRuns}
                            className="mt-4 px-4 py-2 bg-white/5 rounded-lg text-sm hover:bg-white/10 transition-colors"
                        >
                            Riprova
                        </button>
                    </div>
                ) : filteredRuns.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                        <Clock className="w-10 h-10 mb-3 opacity-50" />
                        <p>Nessuna ricerca trovata</p>
                        {(searchQuery || dateFilter !== 'all' || showOnlyFavorites) && (
                            <button
                                onClick={() => {
                                    setSearchQuery('');
                                    setDateFilter('all');
                                    setShowOnlyFavorites(false);
                                }}
                                className="mt-3 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
                            >
                                Rimuovi filtri
                            </button>
                        )}
                    </div>
                ) : (
                    /* Card Grid Layout */
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {paginatedRuns.map((run, index) => {
                            const status = getStatusDisplay(run.status);
                            const StatusIcon = status.icon;
                            const isFavorite = favorites.has(run.run_id);
                            const isSelected = selectedIds.has(run.run_id);

                            return (
                                <motion.div
                                    key={run.run_id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.03 }}
                                    className={`
                                        group relative bg-[#0f1218]/80 backdrop-blur-sm border rounded-2xl overflow-hidden
                                        transition-all duration-200 cursor-pointer hover:shadow-lg hover:shadow-emerald-500/5
                                        ${isSelected
                                            ? 'border-emerald-500/50 bg-emerald-500/5 ring-1 ring-emerald-500/20'
                                            : `border-white/5 hover:border-white/10 hover:bg-white/2`
                                        }
                                    `}
                                    onClick={() => {
                                        if (isSelectionMode) {
                                            toggleSelection(run.run_id);
                                        } else {
                                            setSelectedRunId(run.run_id);
                                        }
                                    }}
                                >
                                    {/* Card Header with Status */}
                                    <div className={`px-4 py-3 border-b ${status.border} ${status.bg}`}>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <StatusIcon className={`w-4 h-4 ${status.color} ${status.animate ? 'animate-spin' : ''}`} />
                                                <span className={`text-sm font-medium ${status.color}`}>{status.label}</span>
                                            </div>

                                            {/* Selection Checkbox */}
                                            {isSelectionMode && (
                                                <div
                                                    className={`
                                                        w-5 h-5 rounded-md border flex items-center justify-center transition-all
                                                        ${isSelected
                                                            ? 'bg-emerald-500 border-emerald-500'
                                                            : 'border-white/30 hover:border-white/50'
                                                        }
                                                    `}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        toggleSelection(run.run_id);
                                                    }}
                                                >
                                                    {isSelected && <Check className="w-3 h-3 text-white" />}
                                                </div>
                                            )}

                                            {/* Favorite Star (when not in selection mode) */}
                                            {!isSelectionMode && (
                                                <button
                                                    onClick={(e) => toggleFavorite(run.run_id, e)}
                                                    className={`
                                                        w-6 h-6 rounded-md flex items-center justify-center transition-all
                                                        ${isFavorite
                                                            ? 'text-amber-400'
                                                            : 'text-gray-500 opacity-0 group-hover:opacity-100 hover:text-amber-400'
                                                        }
                                                    `}
                                                >
                                                    <Star className={`w-3.5 h-3.5 ${isFavorite ? 'fill-amber-400' : ''}`} />
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* Card Body */}
                                    <div className="p-4">
                                        {/* Query */}
                                        <h3 className="text-base font-medium text-white line-clamp-2 mb-3 min-h-12">
                                            {run.query}
                                        </h3>

                                        {/* Metadata */}
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-2 text-sm text-gray-500">
                                                <Calendar className="w-4 h-4" />
                                                <span>{formatRunDate(run.created_at)}</span>
                                            </div>
                                            {run.buildings_count !== undefined && run.buildings_count > 0 && (
                                                <div className="flex items-center gap-2 text-sm text-gray-500">
                                                    <Building2 className="w-4 h-4" />
                                                    <span>{run.buildings_count} immobili trovati</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Card Footer - Actions (sempre visibile) */}
                                    <div className="px-4 py-3 border-t border-white/5 flex items-center gap-2">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setSelectedRunId(run.run_id);
                                            }}
                                            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-white/5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/10 transition-all"
                                        >
                                            <Eye className="w-4 h-4" />
                                            Dettagli
                                        </button>

                                        {run.status === 'completed' && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    loadToMap(run.run_id);
                                                }}
                                                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-emerald-500/10 rounded-lg text-sm text-emerald-400 hover:bg-emerald-500/20 transition-all"
                                            >
                                                <MapIcon className="w-4 h-4" />
                                                Mappa
                                            </button>
                                        )}

                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setDeleteConfirmId(run.run_id);
                                            }}
                                            className="w-9 h-9 rounded-lg flex items-center justify-center text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all opacity-0 group-hover:opacity-100"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>

                                    {/* Delete Confirmation Overlay */}
                                    <AnimatePresence>
                                        {deleteConfirmId === run.run_id && (
                                            <motion.div
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                exit={{ opacity: 0 }}
                                                className="absolute inset-0 bg-[#0f1218]/95 backdrop-blur-sm rounded-2xl flex flex-col items-center justify-center gap-3 z-10 p-4"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                <AlertTriangle className="w-8 h-8 text-red-400" />
                                                <span className="text-sm text-gray-300 text-center">Eliminare questa ricerca?</span>
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={() => deleteRun(run.run_id)}
                                                        disabled={isDeleting}
                                                        className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-all disabled:opacity-50 flex items-center gap-1.5"
                                                    >
                                                        {isDeleting ? (
                                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                        ) : (
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        )}
                                                        Elimina
                                                    </button>
                                                    <button
                                                        onClick={() => setDeleteConfirmId(null)}
                                                        className="px-4 py-2 bg-white/5 text-gray-400 rounded-lg text-xs font-medium hover:bg-white/10 transition-all"
                                                    >
                                                        Annulla
                                                    </button>
                                                </div>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </motion.div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-4">
                    <span className="text-sm text-gray-500">
                        Pagina {currentPage} di {totalPages}
                    </span>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage === 1}
                            className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>

                        {/* Page numbers */}
                        <div className="flex items-center gap-1">
                            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                                let page: number;
                                if (totalPages <= 5) {
                                    page = i + 1;
                                } else if (currentPage <= 3) {
                                    page = i + 1;
                                } else if (currentPage >= totalPages - 2) {
                                    page = totalPages - 4 + i;
                                } else {
                                    page = currentPage - 2 + i;
                                }

                                return (
                                    <button
                                        key={page}
                                        onClick={() => setCurrentPage(page)}
                                        className={`
                                            w-9 h-9 rounded-lg text-sm font-medium transition-all
                                            ${page === currentPage
                                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                                                : 'bg-white/5 text-gray-400 border border-white/10 hover:text-white hover:bg-white/10'
                                            }
                                        `}
                                    >
                                        {page}
                                    </button>
                                );
                            })}
                        </div>

                        <button
                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                            disabled={currentPage === totalPages}
                            className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}

            {/* Run Detail Modal */}
            <RunDetailModal
                runId={selectedRunId}
                isOpen={!!selectedRunId}
                onClose={() => setSelectedRunId(null)}
                onLoadToMap={loadToMap}
                isFavorite={selectedRunId ? favorites.has(selectedRunId) : false}
                onToggleFavorite={toggleFavorite}
            />
        </div>
    );
};
