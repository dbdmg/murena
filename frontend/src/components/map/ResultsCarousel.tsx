import React, { useRef, useEffect, useCallback, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, Star, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import type { MapMarker } from '../../api/types';

interface ResultsCarouselProps {
    topPicks: MapMarker[];
    selectedId: string | null;
    hoveredId: string | null;
    onCardClick: (marker: MapMarker) => void;
    onCardHover: (markerId: string | null) => void;
    sidebarOpen?: boolean;
}

const CARD_WIDTH = 200; // Width of each card
const CARD_GAP = 20; // Gap between cards
const VISIBLE_CARDS = 4; // Max visible cards

// Helper function for energy class colors (consistent with ResultsSidebar)
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

export const ResultsCarousel: React.FC<ResultsCarouselProps> = ({
    topPicks,
    selectedId,
    hoveredId,
    onCardClick,
    onCardHover,
    sidebarOpen = false,
}) => {
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const cardRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
    const [scrollProgress, setScrollProgress] = useState(0);
    const [isDragging, setIsDragging] = useState(false);
    const progressBarRef = useRef<HTMLDivElement>(null);

    // Calculate total scrollable width
    const totalCards = topPicks.length;
    const hasMoreCards = totalCards > VISIBLE_CARDS;

    // Scroll to selected card when selectedId changes
    useEffect(() => {
        if (selectedId && scrollContainerRef.current) {
            const card = cardRefs.current.get(selectedId);
            if (card) {
                card.scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest',
                    inline: 'center',
                });
            }
        }
    }, [selectedId]);

    // Update scroll progress
    const updateScrollProgress = useCallback(() => {
        if (scrollContainerRef.current) {
            const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
            const maxScroll = scrollWidth - clientWidth;
            const progress = maxScroll > 0 ? scrollLeft / maxScroll : 0;
            setScrollProgress(progress);
        }
    }, []);

    useEffect(() => {
        const container = scrollContainerRef.current;
        if (container) {
            container.addEventListener('scroll', updateScrollProgress);
            requestAnimationFrame(updateScrollProgress);
            return () => container.removeEventListener('scroll', updateScrollProgress);
        }
    }, [updateScrollProgress, topPicks]);

    const scroll = useCallback((direction: 'left' | 'right') => {
        if (scrollContainerRef.current) {
            const scrollAmount = CARD_WIDTH + CARD_GAP;
            scrollContainerRef.current.scrollBy({
                left: direction === 'left' ? -scrollAmount : scrollAmount,
                behavior: 'smooth',
            });
        }
    }, []);

    // Handle progress bar drag
    const handleProgressBarClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (progressBarRef.current && scrollContainerRef.current) {
            const rect = progressBarRef.current.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const percentage = clickX / rect.width;
            const { scrollWidth, clientWidth } = scrollContainerRef.current;
            const maxScroll = scrollWidth - clientWidth;
            scrollContainerRef.current.scrollTo({
                left: percentage * maxScroll,
                behavior: 'smooth',
            });
        }
    }, []);

    const handleProgressBarDrag = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        if (isDragging && progressBarRef.current && scrollContainerRef.current) {
            const rect = progressBarRef.current.getBoundingClientRect();
            const clickX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
            const percentage = clickX / rect.width;
            const { scrollWidth, clientWidth } = scrollContainerRef.current;
            const maxScroll = scrollWidth - clientWidth;
            scrollContainerRef.current.scrollLeft = percentage * maxScroll;
        }
    }, [isDragging]);

    useEffect(() => {
        const handleMouseUp = () => setIsDragging(false);
        const handleMouseMove = (e: MouseEvent) => {
            if (isDragging && progressBarRef.current && scrollContainerRef.current) {
                const rect = progressBarRef.current.getBoundingClientRect();
                const clickX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
                const percentage = clickX / rect.width;
                const { scrollWidth, clientWidth } = scrollContainerRef.current;
                const maxScroll = scrollWidth - clientWidth;
                scrollContainerRef.current.scrollLeft = percentage * maxScroll;
            }
        };

        if (isDragging) {
            document.addEventListener('mouseup', handleMouseUp);
            document.addEventListener('mousemove', handleMouseMove);
        }

        return () => {
            document.removeEventListener('mouseup', handleMouseUp);
            document.removeEventListener('mousemove', handleMouseMove);
        };
    }, [isDragging]);

    if (topPicks.length === 0) {
        return null;
    }

    return (
        <div className="relative" style={{ marginRight: sidebarOpen ? '340px' : '0', transition: 'margin-right 0.3s ease' }}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 mb-3">
                <div className="flex items-center gap-3 bg-slate-900/80 backdrop-blur-xl px-4 py-2 rounded-2xl border border-amber-400/20 shadow-xl shadow-black/40">
                    <div className="w-7 h-7 rounded-xl bg-linear-to-br from-amber-300 via-yellow-400 to-orange-400 flex items-center justify-center shadow-lg shadow-amber-500/40">
                        <Sparkles className="w-4 h-4 text-slate-900" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-bold bg-linear-to-r from-amber-300 to-yellow-400 bg-clip-text text-transparent">
                            Top Picks AI
                        </span>
                        <span className="text-[10px] text-amber-200/50">
                            {topPicks.length} immobili selezionati
                        </span>
                    </div>
                </div>

                {/* Navigation Arrows & Progress */}
                <div className="flex items-center gap-3">
                    {/* Progress Bar - only show if more than visible cards */}
                    {hasMoreCards && (
                        <div
                            ref={progressBarRef}
                            className="w-32 h-1.5 bg-slate-700/50 rounded-full cursor-pointer relative group"
                            onClick={handleProgressBarClick}
                            onMouseDown={() => setIsDragging(true)}
                            onMouseMove={handleProgressBarDrag}
                        >
                            {/* Track */}
                            <div className="absolute inset-0 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-linear-to-r from-amber-400 via-yellow-400 to-orange-400 rounded-full transition-all duration-100"
                                    style={{ width: `${Math.max(20, (VISIBLE_CARDS / totalCards) * 100)}%`, marginLeft: `${scrollProgress * (100 - (VISIBLE_CARDS / totalCards) * 100)}%` }}
                                />
                            </div>
                            {/* Hover hint */}
                            <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                                Trascina per scorrere
                            </div>
                        </div>
                    )}

                    {/* Arrow buttons */}
                    <button
                        onClick={() => scroll('left')}
                        disabled={scrollProgress <= 0}
                        className="w-8 h-8 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed backdrop-blur-sm"
                    >
                        <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => scroll('right')}
                        disabled={scrollProgress >= 1}
                        className="w-8 h-8 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed backdrop-blur-sm"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Carousel Container */}
            <div className="relative">
                <div
                    ref={scrollContainerRef}
                    className="flex gap-5 overflow-x-auto pb-3 pt-3 px-4 snap-x snap-mandatory carousel-scroll"
                    style={{
                        scrollbarWidth: 'thin',
                        scrollbarColor: 'rgba(251, 191, 36, 0.4) rgba(255, 255, 255, 0.05)',
                    }}
                >
                    <AnimatePresence mode="popLayout">
                        {topPicks.map((marker, index) => {
                            const isSelected = marker.id === selectedId;
                            const isHovered = marker.id === hoveredId;

                            return (
                                <motion.button
                                    key={marker.id}
                                    ref={(el) => {
                                        if (el) cardRefs.current.set(marker.id, el);
                                    }}
                                    initial={{ opacity: 0, scale: 0.9, x: 20 }}
                                    animate={{ opacity: 1, scale: 1, x: 0 }}
                                    exit={{ opacity: 0, scale: 0.9, x: -20 }}
                                    transition={{ delay: index * 0.05 }}
                                    onClick={() => onCardClick(marker)}
                                    onMouseEnter={() => onCardHover(marker.id)}
                                    onMouseLeave={() => onCardHover(null)}
                                    style={{ width: CARD_WIDTH, minWidth: CARD_WIDTH }}
                                    className={`
                                        shrink-0 snap-center
                                        bg-slate-900/95 backdrop-blur-xl rounded-2xl overflow-hidden
                                        border-2 transition-all duration-300 text-left
                                        ${isSelected
                                            ? 'border-amber-400/60 shadow-xl shadow-amber-500/25 ring-2 ring-amber-400/30 scale-[1.03] -translate-y-1'
                                            : isHovered
                                                ? 'border-white/25 shadow-xl shadow-black/40 scale-[1.01] -translate-y-0.5'
                                                : 'border-white/10 hover:border-white/20'
                                        }
                                    `}
                                >
                                    {/* Card Header with Rank & Score */}
                                    <div className="relative h-16 bg-linear-to-br from-slate-800/90 to-slate-900/90 flex items-center justify-between px-3 border-b border-white/5">
                                        {/* Rank Badge */}
                                        <div className="flex items-center gap-2">
                                            <div className={`
                                            w-7 h-7 rounded-lg flex items-center justify-center font-bold text-sm
                                            ${index < 3
                                                    ? 'bg-linear-to-br from-amber-400 to-yellow-500 text-black'
                                                    : 'bg-white/10 text-gray-300'
                                                }
                                        `}>
                                                #{index + 1}
                                            </div>
                                            <div className="flex flex-col">
                                                <span className="text-[10px] text-gray-500 uppercase">Rank</span>
                                                {index < 3 && (
                                                    <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
                                                )}
                                            </div>
                                        </div>

                                        {/* Score Badge - Squared, Amber themed */}
                                        <div className={`
                                            px-3 py-1.5 rounded-lg font-bold text-base
                                            ${(marker.ranking_score ?? 0) >= 80
                                                ? 'bg-linear-to-br from-amber-400 to-yellow-500 text-black shadow-lg shadow-amber-500/30'
                                                : (marker.ranking_score ?? 0) >= 60
                                                    ? 'bg-linear-to-br from-amber-500/80 to-orange-500/80 text-white shadow-lg shadow-amber-500/20'
                                                    : (marker.ranking_score ?? 0) >= 40
                                                        ? 'bg-linear-to-br from-slate-500 to-slate-600 text-white'
                                                        : 'bg-slate-700 text-gray-300'
                                            }
                                        `}>
                                            {marker.ranking_score ?? '—'}
                                        </div>
                                    </div>

                                    {/* Card Body */}
                                    <div className="p-3 space-y-2">
                                        {/* Address */}
                                        <div className="flex items-start gap-2">
                                            <MapPin className="w-3.5 h-3.5 text-gray-500 mt-0.5 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm text-white font-medium truncate">
                                                    {marker.address || `Immobile ${marker.id}`}
                                                </p>
                                                {marker.city && (
                                                    <p className="text-[11px] text-gray-500 truncate">
                                                        {marker.city}
                                                    </p>
                                                )}
                                            </div>
                                        </div>

                                        {/* Quick Stats - Simplified (consistent with ResultsSidebar) */}
                                        <div className="flex items-center gap-2 text-[10px]">
                                            {marker.surface_area && (
                                                <span className="px-1.5 py-0.5 rounded bg-slate-700/50 text-gray-300">
                                                    {marker.surface_area.toLocaleString()} m²
                                                </span>
                                            )}
                                            {marker.energy_class && (
                                                <span className={`px-1.5 py-0.5 rounded font-medium ${getEnergyClassColor(marker.energy_class)}`}>
                                                    Classe {marker.energy_class}
                                                </span>
                                            )}
                                            {marker.omi_zone && (
                                                <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400">
                                                    {marker.omi_zone}
                                                </span>
                                            )}
                                        </div>

                                        {/* AI Evaluation Preview */}
                                        {marker.evaluation_text && (
                                            <p className="text-[11px] text-gray-400 line-clamp-2 leading-relaxed">
                                                {marker.evaluation_text}
                                            </p>
                                        )}

                                        {/* Pros/Cons Preview */}
                                        {(marker.pros?.length || marker.cons?.length) && (
                                            <div className="flex items-center gap-2 text-[10px]">
                                                {marker.pros && marker.pros.length > 0 && (
                                                    <span className="text-emerald-400">
                                                        ✓ {marker.pros.length} pro
                                                    </span>
                                                )}
                                                {marker.cons && marker.cons.length > 0 && (
                                                    <span className="text-amber-400">
                                                        ⚠ {marker.cons.length} contro
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </motion.button>
                            );
                        })}
                    </AnimatePresence>

                    {/* Spacer for right padding */}
                    <div className="shrink-0 w-4" aria-hidden="true" />
                </div>

                {/* Fade edge on left */}
                <div className="absolute left-0 top-0 bottom-0 w-6 bg-linear-to-r from-[#0a0d12] to-transparent pointer-events-none z-10" />

                {/* Stronger fade on right to indicate more content */}
                {hasMoreCards && (
                    <div className="absolute right-0 top-0 bottom-0 w-20 bg-linear-to-l from-[#0a0d12] via-[#0a0d12]/80 to-transparent pointer-events-none z-10" />
                )}
            </div>
        </div>
    );
};
