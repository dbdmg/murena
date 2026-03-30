/**
 * ResultsSidebar - Collapsible left sidebar with building list
 * 
 * Features:
 * - Sortable list (Score, Surface, Energy Class, Address)
 * - Pagination (20 per page)
 * - Compact building cards
 * - Bidirectional selection with map
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    X,
    ChevronLeft,
    ChevronRight,
    ArrowUpDown,
    Building2,
    MapPin,
    Zap,
    Layers,
    Check,
    Search,
    Star
} from 'lucide-react';
import type { MapMarker } from '../../api/types';

interface ResultsSidebarProps {
    isOpen: boolean;
    onClose: () => void;
    markers: MapMarker[];
    selectedId: string | null;
    onSelect: (marker: MapMarker) => void;
    hasActiveRun?: boolean;
    buildingRatings?: Record<string, number>;
}

type SortOption = 'score' | 'surface' | 'energy' | 'address';

const ITEMS_PER_PAGE = 20;

const SORT_OPTIONS: { value: SortOption; label: string; icon: React.ReactNode }[] = [
    { value: 'score', label: 'AI Score', icon: <Zap className="w-3.5 h-3.5" /> },
    { value: 'surface', label: 'Surface', icon: <Building2 className="w-3.5 h-3.5" /> },
    { value: 'energy', label: 'Energy Class', icon: <Zap className="w-3.5 h-3.5" /> },
    { value: 'address', label: 'Address', icon: <MapPin className="w-3.5 h-3.5" /> },
];

const ENERGY_CLASS_ORDER = ['A4', 'A3', 'A2', 'A1', 'B', 'C', 'D', 'E', 'F', 'G'];

export const ResultsSidebar: React.FC<ResultsSidebarProps> = ({
    isOpen,
    onClose,
    markers,
    selectedId,
    onSelect,
    hasActiveRun = false,
    buildingRatings = {},
}) => {
    const [sortBy, setSortBy] = useState<SortOption>(hasActiveRun ? 'score' : 'address');
    const [currentPage, setCurrentPage] = useState(1);
    const [showSortDropdown, setShowSortDropdown] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    // Refs for card elements to enable autoscroll
    const cardRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

    // Track previous props for render-time updates
    const [prevMarkersLen, setPrevMarkersLen] = useState(markers.length);
    const [prevHasActiveRun, setPrevHasActiveRun] = useState(hasActiveRun);

    // Reset page when markers change
    if (markers.length !== prevMarkersLen) {
        setPrevMarkersLen(markers.length);
        setCurrentPage(1);
    }

    // Reset sort to score when run becomes active
    if (hasActiveRun !== prevHasActiveRun) {
        setPrevHasActiveRun(hasActiveRun);
        if (hasActiveRun) {
            setSortBy('score');
        }
    }

    // Sort and Filter markers
    const sortedMarkers = useMemo(() => {
        let sorted = [...markers];

        // Filter by search query
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase().trim();
            sorted = sorted.filter(m =>
                String(m.id).includes(q) ||
                (m.address && m.address.toLowerCase().includes(q))
            );
        }

        switch (sortBy) {
            case 'score':
                return sorted.sort((a, b) => (b.ranking_score ?? 0) - (a.ranking_score ?? 0));
            case 'surface':
                return sorted.sort((a, b) => (b.surface_area ?? 0) - (a.surface_area ?? 0));
            case 'energy':
                return sorted.sort((a, b) => {
                    const aIdx = ENERGY_CLASS_ORDER.indexOf(a.energy_class || 'G');
                    const bIdx = ENERGY_CLASS_ORDER.indexOf(b.energy_class || 'G');
                    return aIdx - bIdx;
                });
            case 'address':
                return sorted.sort((a, b) =>
                    (a.address || '').localeCompare(b.address || '')
                );
            default:
                return sorted;
        }
    }, [markers, sortBy, searchQuery]);

    // Paginate
    const totalPages = Math.ceil(sortedMarkers.length / ITEMS_PER_PAGE);
    const paginatedMarkers = useMemo(() => {
        const start = (currentPage - 1) * ITEMS_PER_PAGE;
        return sortedMarkers.slice(start, start + ITEMS_PER_PAGE);
    }, [sortedMarkers, currentPage]);

    // Navigate to the page containing selected marker AND scroll to it
    useEffect(() => {
        if (selectedId && isOpen) {
            const idx = sortedMarkers.findIndex(m => m.id === selectedId);
            if (idx >= 0) {
                const targetPage = Math.floor(idx / ITEMS_PER_PAGE) + 1;
                if (targetPage !== currentPage) {
                    setTimeout(() => setCurrentPage(targetPage), 0);
                }
                // Scroll to card after a short delay (for page change to render)
                setTimeout(() => {
                    const cardEl = cardRefs.current.get(selectedId);
                    if (cardEl) {
                        cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }, 100);
            }
        }
    }, [selectedId, isOpen, sortedMarkers, currentPage]);

    const getEnergyClassColor = (cls?: string) => {
        if (!cls) return 'bg-gray-500/20 text-gray-400';
        const base = cls.charAt(0);
        switch (base) {
            case 'A': return 'bg-emerald-500/20 text-emerald-400';
            case 'B': return 'bg-lime-500/20 text-lime-400';
            case 'C': return 'bg-yellow-500/20 text-yellow-400';
            case 'D': return 'bg-orange-500/20 text-orange-400';
            case 'E': return 'bg-orange-600/20 text-orange-500';
            case 'F': return 'bg-red-500/20 text-red-400';
            case 'G': return 'bg-red-600/20 text-red-500';
            default: return 'bg-gray-500/20 text-gray-400';
        }
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ x: -320, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    exit={{ x: -320, opacity: 0 }}
                    transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                    className="absolute left-0 top-0 bottom-0 w-80 bg-[#0a0d12]/95 backdrop-blur-xl border-r border-white/10 z-40 flex flex-col shadow-2xl"
                >
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b border-white/10">
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                                <Layers className="w-4 h-4 text-emerald-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-white">Results</h3>
                                <span className="text-xs text-gray-500">{sortedMarkers.length} properties</span>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                        >
                            <X className="w-4 h-4 text-gray-400" />
                        </button>
                    </div>

                    {/* Search and Sort Controls */}
                    <div className="p-3 border-b border-white/5 space-y-2">
                        {/* Search Input */}
                        <div className="relative">
                            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                            <input
                                type="text"
                                placeholder="Search address or ID..."
                                value={searchQuery}
                                onChange={(e) => {
                                    setSearchQuery(e.target.value);
                                    setCurrentPage(1);
                                }}
                                className="w-full pl-9 pr-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => setSearchQuery('')}
                                    className="absolute right-3 top-2.5 hover:text-white text-gray-500"
                                >
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </div>

                        {/* Sort Dropdown */}
                        <div className="relative">
                            <button
                                onClick={() => setShowSortDropdown(!showSortDropdown)}
                                className="flex items-center gap-2 w-full px-3 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm text-gray-300 transition-colors"
                            >
                                <ArrowUpDown className="w-4 h-4 text-gray-500" />
                                <span>Sort by: <span className="text-white font-medium">
                                    {SORT_OPTIONS.find(o => o.value === sortBy)?.label}
                                </span></span>
                            </button>

                            {showSortDropdown && (
                                <div className="absolute top-full left-0 right-0 mt-1 bg-[#12151a] border border-white/10 rounded-lg overflow-hidden z-50 shadow-xl">
                                    {SORT_OPTIONS.map((option) => (
                                        <button
                                            key={option.value}
                                            onClick={() => {
                                                setSortBy(option.value);
                                                setShowSortDropdown(false);
                                                setCurrentPage(1);
                                            }}
                                            disabled={option.value === 'score' && !hasActiveRun}
                                            className={`
                                                flex items-center gap-2 w-full px-3 py-2 text-sm text-left transition-colors
                                                ${sortBy === option.value
                                                    ? 'bg-emerald-500/20 text-emerald-400'
                                                    : 'text-gray-300 hover:bg-white/5'
                                                }
                                                ${option.value === 'score' && !hasActiveRun ? 'opacity-40 cursor-not-allowed' : ''}
                                            `}
                                        >
                                            {option.icon}
                                            <span>{option.label}</span>
                                            {option.value === 'score' && !hasActiveRun && (
                                                <span className="text-xs text-gray-500 ml-auto">(requires run)</span>
                                            )}
                                            {sortBy === option.value && <Check className="w-3 h-3 ml-auto" />}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Building List */}
                    <div className="flex-1 overflow-y-auto">
                        {paginatedMarkers.length === 0 ? (
                            <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
                                No results
                            </div>
                        ) : (
                            <div className="p-2 space-y-2">
                                {paginatedMarkers.map((marker) => {
                                    const isSelected = marker.id === selectedId;

                                    return (
                                        <button
                                            key={marker.id}
                                            ref={(el) => {
                                                if (el) cardRefs.current.set(marker.id, el);
                                            }}
                                            onClick={() => onSelect(marker)}
                                            className={`
                                                w-full p-3 rounded-xl text-left transition-all duration-200
                                                ${isSelected
                                                    ? 'bg-emerald-500/20 border border-emerald-500/40 ring-1 ring-emerald-500/20'
                                                    : 'bg-white/5 border border-transparent hover:bg-white/10 hover:border-white/10'
                                                }
                                            `}
                                        >
                                            {/* Header row */}
                                            <div className="flex items-start justify-between gap-2 mb-2">
                                                <div className="flex-1 min-w-0">
                                                    <p className={`text-sm font-medium truncate ${isSelected ? 'text-emerald-300' : 'text-white'}`}>
                                                        {marker.address || `ID: ${marker.id}`}
                                                    </p>
                                                    {marker.meta_immobile && (
                                                        <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30">
                                                            META
                                                        </span>
                                                    )}
                                                </div>

                                                {/* Score badge & stars */}
                                                <div className="flex flex-col items-end gap-1 shrink-0">
                                                    {marker.ranking_score != null && (
                                                        <div className={`
                                                            px-2 py-1 rounded-lg font-bold text-xs
                                                            ${marker.ranking_score >= 80
                                                                ? 'bg-linear-to-br from-amber-400 to-yellow-500 text-black'
                                                                : marker.ranking_score >= 60
                                                                    ? 'bg-amber-500/30 text-amber-400'
                                                                    : 'bg-slate-600/50 text-gray-300'
                                                            }
                                                        `}>
                                                            {marker.ranking_score}
                                                        </div>
                                                    )}

                                                    {buildingRatings[marker.id] > 0 && (
                                                        <div className="flex items-center gap-0.5">
                                                            {[1, 2, 3, 4, 5].map(s => (
                                                                <Star
                                                                    key={s}
                                                                    size={11}
                                                                    fill={s <= (buildingRatings[marker.id] || 0) ? "currentColor" : "none"}
                                                                    className={s <= (buildingRatings[marker.id] || 0) ? 'text-amber-400' : 'text-slate-700'}
                                                                />
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Info badges - Simplified: only surface, energy class, OMI zone */}
                                            <div className="flex flex-wrap items-center gap-1.5">
                                                {marker.surface_area && (
                                                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-700/50 text-gray-300">
                                                        {marker.surface_area.toLocaleString()} m²
                                                    </span>
                                                )}

                                                {marker.energy_class && (
                                                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${getEnergyClassColor(marker.energy_class)}`}>
                                                        Class {marker.energy_class}
                                                    </span>
                                                )}

                                                {marker.omi_zone && (
                                                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400">
                                                        {marker.omi_zone}
                                                    </span>
                                                )}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="p-3 border-t border-white/10 flex items-center justify-between">
                            <button
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="p-2 hover:bg-white/10 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                                <ChevronLeft className="w-4 h-4 text-gray-400" />
                            </button>

                            <span className="text-xs text-gray-400">
                                Page <span className="text-white font-medium">{currentPage}</span> of {totalPages}
                            </span>

                            <button
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="p-2 hover:bg-white/10 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                                <ChevronRight className="w-4 h-4 text-gray-400" />
                            </button>
                        </div>
                    )}
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default ResultsSidebar;
