import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, CheckCircle2, AlertTriangle } from 'lucide-react';

interface AIEvaluationCardProps {
    score?: number;
    evaluationText?: string;
    pros?: string[];
    cons?: string[];
    compact?: boolean; // For smaller display in sidebar
}

export const AIEvaluationCard: React.FC<AIEvaluationCardProps> = ({
    score,
    evaluationText,
    pros = [],
    cons = [],
    compact = false,
}) => {
    const getScoreColor = (s?: number) => {
        if (!s) return { bg: 'from-gray-600 to-gray-700', text: 'text-gray-400', glow: 'shadow-gray-500/20' };
        if (s >= 80) return { bg: 'from-emerald-500 to-green-600', text: 'text-emerald-400', glow: 'shadow-emerald-500/30' };
        if (s >= 60) return { bg: 'from-cyan-500 to-blue-600', text: 'text-cyan-400', glow: 'shadow-cyan-500/30' };
        if (s >= 40) return { bg: 'from-amber-500 to-orange-600', text: 'text-amber-400', glow: 'shadow-amber-500/30' };
        return { bg: 'from-red-500 to-rose-600', text: 'text-red-400', glow: 'shadow-red-500/30' };
    };

    const scoreColors = getScoreColor(score);
    const hasEvaluation = score != null || evaluationText || pros.length > 0 || cons.length > 0;

    if (!hasEvaluation) {
        return null;
    }

    if (compact) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gradient-to-br from-amber-500/10 to-yellow-500/5 border border-amber-400/20 rounded-lg p-3"
            >
                <div className="flex items-center gap-3">
                    {/* Score Circle */}
                    {score != null && (
                        <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${scoreColors.bg} flex items-center justify-center shadow-lg ${scoreColors.glow} shrink-0`}>
                            <span className="text-white font-bold text-base">{score}</span>
                        </div>
                    )}
                    
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Sparkles className="w-3 h-3 text-amber-400" />
                            <span className="text-[10px] uppercase font-semibold text-amber-400 tracking-wide">
                                Valutazione AI
                            </span>
                        </div>
                        {evaluationText && (
                            <p className="text-xs text-gray-300 line-clamp-2 leading-relaxed">
                                {evaluationText}
                            </p>
                        )}
                    </div>
                </div>

                {/* Compact Pros/Cons */}
                {(pros.length > 0 || cons.length > 0) && (
                    <div className="flex items-center gap-3 mt-2 pt-2 border-t border-white/5 text-[10px]">
                        {pros.length > 0 && (
                            <span className="text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" />
                                {pros.length} punti di forza
                            </span>
                        )}
                        {cons.length > 0 && (
                            <span className="text-amber-400 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                {cons.length} criticità
                            </span>
                        )}
                    </div>
                )}
            </motion.div>
        );
    }

    // Full display
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-amber-500/10 via-yellow-500/5 to-transparent border border-amber-400/20 rounded-xl overflow-hidden"
        >
            {/* Header */}
            <div className="px-4 py-3 bg-gradient-to-r from-amber-500/10 to-transparent border-b border-amber-400/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center">
                        <Sparkles className="w-3.5 h-3.5 text-white" />
                    </div>
                    <span className="text-sm font-semibold text-amber-400">
                        Valutazione AI
                    </span>
                </div>
                
                {/* Score Circle */}
                {score != null && (
                    <div className={`w-14 h-14 rounded-full bg-gradient-to-br ${scoreColors.bg} flex items-center justify-center shadow-lg ${scoreColors.glow}`}>
                        <div className="text-center">
                            <span className="text-white font-bold text-lg">{score}</span>
                            <span className="text-white/60 text-[8px] block -mt-1">/100</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Content */}
            <div className="p-4 space-y-4">
                {/* Evaluation Text */}
                {evaluationText && (
                    <p className="text-sm text-gray-300 leading-relaxed">
                        {evaluationText}
                    </p>
                )}

                {/* Pros */}
                {pros.length > 0 && (
                    <div>
                        <div className="flex items-center gap-1.5 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wide">
                                Punti di forza
                            </span>
                        </div>
                        <ul className="space-y-1.5">
                            {pros.map((pro, index) => (
                                <motion.li
                                    key={index}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="flex items-start gap-2 text-sm text-gray-300"
                                >
                                    <span className="text-emerald-400 mt-0.5">✓</span>
                                    <span>{pro}</span>
                                </motion.li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Cons */}
                {cons.length > 0 && (
                    <div>
                        <div className="flex items-center gap-1.5 mb-2">
                            <AlertTriangle className="w-4 h-4 text-amber-400" />
                            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
                                Criticità
                            </span>
                        </div>
                        <ul className="space-y-1.5">
                            {cons.map((con, index) => (
                                <motion.li
                                    key={index}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="flex items-start gap-2 text-sm text-gray-300"
                                >
                                    <span className="text-amber-400 mt-0.5">⚠</span>
                                    <span>{con}</span>
                                </motion.li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </motion.div>
    );
};
