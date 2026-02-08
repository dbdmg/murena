import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Star, Check, MessageSquare, X, Loader2 } from 'lucide-react';
import { feedbackApi } from '../../api/endpoints/feedback';

interface FeedbackPanelProps {
    runId: string;
    agentName?: string; // undefined = global feedback
    existingFeedback?: {
        rating: number;
        comment?: string;
    };
    variant?: 'compact' | 'expanded';
    onSubmitSuccess?: () => void;
}

export const FeedbackPanel: React.FC<FeedbackPanelProps> = ({
    runId,
    agentName,
    existingFeedback,
    variant = 'compact',
    onSubmitSuccess,
}) => {
    const [rating, setRating] = useState(existingFeedback?.rating || 0);
    const [hoveredRating, setHoveredRating] = useState(0);
    const [comment, setComment] = useState(existingFeedback?.comment || '');
    const [isExpanded, setIsExpanded] = useState(variant === 'expanded');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isSubmitted, setIsSubmitted] = useState(!!existingFeedback);
    const [error, setError] = useState<string | null>(null);

    // Sync state when existingFeedback changes (e.g. after fetch in parent)
    useEffect(() => {
        if (existingFeedback) {
            setRating(existingFeedback.rating);
            setComment(existingFeedback.comment || '');
            setIsSubmitted(true);
        }
    }, [existingFeedback]);

    const handleSubmit = async () => {
        if (rating === 0) {
            setError('Seleziona almeno una stella');
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            await feedbackApi.submitAgentFeedback({
                run_id: runId,
                agent_name: agentName || undefined,
                rating: rating as 1 | 2 | 3 | 4 | 5,
                comment: comment.trim() || undefined,
            });

            setIsSubmitted(true);
            if (onSubmitSuccess) onSubmitSuccess();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Errore durante l\'invio del feedback');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleReset = () => {
        setRating(0);
        setComment('');
        setIsSubmitted(false);
        setError(null);
    };

    const displayRating = hoveredRating || rating;

    return (
        <div className="relative">
            {/* Compact Trigger */}
            {!isExpanded && (
                <button
                    onClick={() => setIsExpanded(true)}
                    className={`
                        flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all group shadow-lg shadow-amber-500/20
                        ${isSubmitted
                            ? 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
                            : 'bg-amber-500 border border-amber-600 text-black hover:bg-amber-400'
                        }
                    `}
                    title="Invia feedback"
                >
                    <Star className={`w-3.5 h-3.5 ${isSubmitted ? 'text-emerald-400' : 'text-black opacity-70 group-hover:opacity-100'} transition-colors`} />
                    <span className="text-[11px] font-bold uppercase tracking-widest">
                        {isSubmitted ? 'Feedback Inviato' : 'Valuta'}
                    </span>
                    {isSubmitted && <Check className="w-3 h-3 text-emerald-400" />}
                </button>
            )}

            {/* Expanded Panel */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: -10 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -10 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="absolute right-0 top-0 z-50 w-80 bg-[#0a0f16]/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-white/5">
                            <div className="flex items-center gap-2">
                                <MessageSquare className="w-4 h-4 text-amber-500" />
                                <span className="text-sm font-bold text-white">
                                    {agentName ? `Feedback: ${agentName}` : 'Feedback Globale'}
                                </span>
                            </div>
                            <button
                                onClick={() => setIsExpanded(false)}
                                className="p-1 hover:bg-white/10 rounded transition-colors text-slate-500 hover:text-white"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="p-4 space-y-4">
                            {/* Star Rating */}
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                                    Valutazione
                                </label>
                                <div className="flex items-center gap-1">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                        <button
                                            key={star}
                                            onClick={() => setRating(star)}
                                            onMouseEnter={() => setHoveredRating(star)}
                                            onMouseLeave={() => setHoveredRating(0)}
                                            disabled={isSubmitted || isSubmitting}
                                            className="relative group transition-transform hover:scale-110 active:scale-95 disabled:cursor-not-allowed"
                                        >
                                            <Star
                                                className={`w-8 h-8 transition-all ${star <= displayRating
                                                    ? 'fill-amber-500 text-amber-500 drop-shadow-[0_0_8px_rgba(251,191,36,0.5)]'
                                                    : 'text-slate-700 hover:text-slate-600'
                                                    }`}
                                            />
                                        </button>
                                    ))}
                                </div>
                                {rating > 0 && (
                                    <div className="text-xs text-amber-400 font-medium">
                                        {rating} {rating === 1 ? 'stella' : 'stelle'}
                                    </div>
                                )}
                            </div>

                            {/* Comment Field */}
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                                    Commento (Opzionale)
                                </label>
                                <textarea
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                    disabled={isSubmitted || isSubmitting}
                                    placeholder="Condividi i tuoi pensieri..."
                                    className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-colors resize-none disabled:opacity-50 disabled:cursor-not-allowed"
                                    rows={3}
                                />
                            </div>

                            {/* Error Message */}
                            {error && (
                                <div className="px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">
                                    {error}
                                </div>
                            )}

                            {/* Actions */}
                            <div className="flex items-center gap-2">
                                {!isSubmitted ? (
                                    <>
                                        <button
                                            onClick={handleSubmit}
                                            disabled={isSubmitting || rating === 0}
                                            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 disabled:bg-slate-700 text-white font-medium rounded-lg transition-colors disabled:cursor-not-allowed"
                                        >
                                            {isSubmitting ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                    <span>Invio...</span>
                                                </>
                                            ) : (
                                                <>
                                                    <Check className="w-4 h-4" />
                                                    <span>Invia Feedback</span>
                                                </>
                                            )}
                                        </button>
                                        <button
                                            onClick={() => setIsExpanded(false)}
                                            className="px-4 py-2 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white font-medium rounded-lg transition-colors"
                                        >
                                            Annulla
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <div className="flex-1 flex items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium rounded-lg">
                                            <Check className="w-4 h-4" />
                                            <span>Feedback Inviato!</span>
                                        </div>
                                        <button
                                            onClick={handleReset}
                                            className="px-4 py-2 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white font-medium rounded-lg transition-colors text-sm"
                                        >
                                            Modifica
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};
