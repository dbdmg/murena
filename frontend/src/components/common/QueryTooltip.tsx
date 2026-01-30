import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Copy, Check } from 'lucide-react';

interface QueryTooltipProps {
    text: string;
    children: React.ReactNode;
    className?: string;
    maxLength?: number;
}

export const QueryTooltip: React.FC<QueryTooltipProps> = ({
    text,
    children,
    className = '',
}) => {
    const [isHovered, setIsHovered] = useState(false);
    const [isCopied, setIsCopied] = useState(false);
    const [coords, setCoords] = useState<{
        top?: number;
        bottom?: number;
        left: number;
        placement: 'top' | 'bottom';
    }>({ left: 0, placement: 'bottom' });
    const triggerRef = useRef<HTMLDivElement>(null);

    const handleCopy = (e: React.MouseEvent) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    // Calculate position on hover
    useEffect(() => {
        if (isHovered && triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            const spaceBelow = viewportHeight - rect.bottom;
            const tooltipHeightEstimate = 300; // Approximate max height

            // Decide placement
            const placement = spaceBelow < tooltipHeightEstimate ? 'top' : 'bottom';

            if (placement === 'top') {
                setCoords({
                    bottom: viewportHeight - rect.top + 8, // Position above trigger
                    left: rect.left + window.scrollX,
                    placement: 'top'
                });
            } else {
                setCoords({
                    top: rect.bottom + window.scrollY + 8, // Position below trigger
                    left: rect.left + window.scrollX,
                    placement: 'bottom'
                });
            }
        }
    }, [isHovered]);

    return (
        <div
            ref={triggerRef}
            className={`relative inline-block ${className}`}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {children}

            {createPortal(
                <AnimatePresence>
                    {isHovered && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9, filter: "blur(10px)" }}
                            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                            exit={{ opacity: 0, scale: 0.9, filter: "blur(10px)" }}
                            transition={{ type: "spring", stiffness: 400, damping: 25 }}
                            className="fixed z-[9999] w-[400px] max-w-[90vw] flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0a0f16]/90 shadow-2xl backdrop-blur-3xl ring-1 ring-white/5"
                            style={{
                                top: coords.placement === 'bottom' ? coords.top : undefined,
                                bottom: coords.placement === 'top' ? coords.bottom : undefined,
                                left: coords.left,
                            }}
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Header Gradient Line */}
                            <div className="h-1 w-full bg-gradient-to-r from-blue-500/50 via-purple-500/50 to-pink-500/50" />

                            <div className="p-4">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <div className="p-1.5 rounded-md bg-blue-500/10 border border-blue-500/20">
                                            <svg className="w-3.5 h-3.5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                <circle cx="11" cy="11" r="8" />
                                                <path d="m21 21-4.3-4.3" />
                                            </svg>
                                        </div>
                                        <span className="text-xs font-medium text-blue-200/80 uppercase tracking-widest">
                                            Analysis Query
                                        </span>
                                    </div>
                                </div>

                                <div className="relative group rounded-xl bg-black/40 border border-white/5 p-3.5 overflow-hidden transition-colors hover:border-white/10">
                                    <p className="text-sm text-gray-300 font-mono leading-relaxed whitespace-pre-wrap max-h-[300px] overflow-y-auto custom-scrollbar selection:bg-blue-500/30 selection:text-blue-200">
                                        {text}
                                    </p>

                                    {/* Copy Button */}
                                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={handleCopy}
                                            className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white shadow-lg backdrop-blur-md transition-all active:scale-95"
                                            title="Copy to clipboard"
                                        >
                                            {isCopied ? (
                                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                                            ) : (
                                                <Copy className="w-3.5 h-3.5" />
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Footer info/decoration */}
                            <div className="px-4 py-2 bg-white/[0.02] border-t border-white/5 flex justify-between items-center text-[10px] text-gray-500">
                                <span>ID: {Math.random().toString(36).substring(7).toUpperCase()}</span>
                                <span className="flex items-center gap-1.5">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/50 animate-pulse" />
                                    Active Context
                                </span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>,
                document.body
            )}
        </div>
    );
};
