import React, { useState } from 'react';
import { Map } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface MapLegendProps {
    className?: string;
    hasSearchLocation?: boolean;
}

export const MapLegend: React.FC<MapLegendProps> = ({ className = '', hasSearchLocation = false }) => {
    const [isHovered, setIsHovered] = useState(false);

    return (
        <div
            className={`relative ${className}`}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* Trigger Button - matching other panels style */}
            <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/40 p-2 flex items-center gap-2">
                <div className={`px-2 transition-colors ${isHovered ? 'text-teal-400' : 'text-slate-500'}`}>
                    <Map className="w-4 h-4" />
                </div>

                <button
                    className={`
                        flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium
                        transition-all duration-200 border whitespace-nowrap
                        ${isHovered
                            ? 'bg-teal-500/20 text-teal-400 border-teal-500/40'
                            : 'bg-white/5 text-slate-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }
                    `}
                >
                    <span className="font-medium">Legenda</span>
                </button>
            </div>

            {/* Legend Popup on Hover */}
            <AnimatePresence>
                {isHovered && (
                    <motion.div
                        initial={{ opacity: 0, y: -8, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -8, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute top-full left-0 mt-2 z-50"
                    >
                        <div className="bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl shadow-black/50 p-4 min-w-[220px]">
                            <div className="text-[10px] text-slate-500 uppercase mb-3 font-semibold tracking-wider">
                                Tipologie Markers
                            </div>
                            <div className="space-y-3">
                                {hasSearchLocation && (
                                    <>
                                        <div className="flex items-center gap-3">
                                            <div className="w-5 h-5 rounded-full bg-linear-to-br from-rose-400 via-red-500 to-rose-600 ring-2 ring-rose-400/30 shrink-0 flex items-center justify-center shadow-md shadow-rose-500/30">
                                                <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                                                    <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                                                </svg>
                                            </div>
                                            <span className="text-xs text-slate-300">Location Cercata</span>
                                        </div>
                                        <div className="w-full h-px bg-white/5 my-2" />
                                    </>
                                )}
                                <div className="flex items-center gap-3">
                                    <div className="w-3.5 h-3.5 rounded-full bg-linear-to-br from-slate-400/80 to-slate-600/80 border border-white/20 shrink-0" />
                                    <span className="text-xs text-slate-400">Background</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="w-4 h-4 rounded-full bg-linear-to-br from-teal-400 to-cyan-600 border border-white/40 shadow-sm shadow-cyan-500/40 shrink-0" />
                                    <span className="text-xs text-slate-300">Risultati ricerca</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="w-5 h-5 rounded-full bg-linear-to-br from-amber-300 via-yellow-400 to-orange-400 border border-white/50 shadow-md shadow-amber-500/40 shrink-0 flex items-center justify-center">
                                        <span className="text-[8px] font-bold text-slate-900">★</span>
                                    </div>
                                    <span className="text-xs text-slate-300">Top Picks AI</span>
                                </div>
                                <div className="w-full h-px bg-white/5 my-2" />
                                <div className="flex items-center gap-3">
                                    <div className="w-4 h-4 rounded-full bg-linear-to-br from-emerald-400 via-teal-400 to-emerald-500 ring-2 ring-emerald-400/40 animate-pulse shrink-0 border border-white/40" />
                                    <span className="text-xs text-slate-300">Selezionato</span>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};
