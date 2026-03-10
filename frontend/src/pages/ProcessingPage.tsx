/**
 * ProcessingPage - Agent Processing View
 *
 * Shows real-time progress of analysis with a clean, user-friendly
 * sequence of activated agents.
 */

import React, { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useParams, useNavigate } from 'react-router-dom';
import {
    CheckCircle2,
    Loader2,
    ArrowRight,
    Circle,
    FileText,
    MapPin,
    Zap,
    StopCircle,
    Sparkles
} from 'lucide-react';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';
import { analysisApi } from '../api/endpoints/analysis';
import type { AnalysisResults, ProgressStep } from '../api/types';

interface LogEntry {
    timestamp: string;
    message: string;
    step?: string;
    status: 'done' | 'processing' | 'pending';
    detail?: string;
}

export const ProcessingPage: React.FC = () => {
    const { runId } = useParams<{ runId: string }>();
    const navigate = useNavigate();

    const [results, setResults] = useState<AnalysisResults | null>(null);
    const [isComplete, setIsComplete] = useState(false);
    const [brokerSummary, setBrokerSummary] = useState<string | null>(null);
    const [buildingsFound, setBuildingsFound] = useState<number | null>(null);

    // Use specific progress hook linked to this runId
    const progress = useAnalysisProgress(runId ?? null, { autoConnect: true });

    // Logs for fallback if structured steps aren't provided
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const hasFetchedSteps = useRef(false);
    const summaryRef = useRef<HTMLDivElement>(null);
    const logsEndRef = useRef<HTMLDivElement>(null);

    // Update logs based on progress message (Fallback mechanism)
    useEffect(() => {
        if (progress.message && progress.step) {
            setLogs(prev => {
                // Avoid duplicates for same step if message is identical
                const last = prev[prev.length - 1];
                if (last && last.message === progress.message && last.step === progress.step) {
                    return prev;
                }

                // Mark previous as done if new step comes
                const updated = prev.map(l =>
                    l.status === 'processing' ? { ...l, status: 'done' as const } : l
                );

                return [...updated, {
                    timestamp: new Date().toLocaleTimeString(),
                    message: progress.message,
                    step: progress.step,
                    status: 'processing',
                    // progress object does not have detail property directly exposed by hook, 
                    // message usually contains the detail. 
                    detail: undefined
                }];
            });
        }

        if (progress.isComplete) {
            setIsComplete(true);
            setLogs(prev => prev.map(l => ({ ...l, status: 'done' })));
        }
    }, [progress.message, progress.step, progress.isComplete]);

    // Fetch results on completion
    useEffect(() => {
        if (progress.isComplete || isComplete) {
            if (!hasFetchedSteps.current && runId) {
                hasFetchedSteps.current = true;
                // Fetch final results
                analysisApi.getResults(runId).then(resultsData => {
                    if (resultsData.status === 'completed') {
                        setResults(resultsData);
                        setBuildingsFound(resultsData.buildings?.length || 0);
                        setBrokerSummary(resultsData.broker_summary || null);
                    }
                }).catch(err => console.error('Failed to fetch results:', err));
            }
        }
    }, [progress.isComplete, isComplete, runId]);

    // Poll for results if not yet complete
    useEffect(() => {
        if (!runId || isComplete) return;

        let isCancelled = false;

        const pollInterval = setInterval(async () => {
            if (isCancelled) return;
            try {
                const resultsData = await analysisApi.getResults(runId);
                if (isCancelled) return;
                if (resultsData.status === 'completed') {
                    clearInterval(pollInterval);
                    setResults(resultsData);
                    setBuildingsFound(resultsData.buildings?.length || 0);
                    setBrokerSummary(resultsData.broker_summary || null);
                    setIsComplete(true);
                } else if (resultsData.status === 'failed') {
                    clearInterval(pollInterval);
                    setIsComplete(true);
                }
            } catch (err) {
                if (!isCancelled) {
                    console.error('Polling error:', err);
                }
            }
        }, 3000);

        return () => {
            isCancelled = true;
            clearInterval(pollInterval);
        };
    }, [runId, isComplete]);

    // Auto-scroll to bottom of step list
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs, progress.steps]);


    // Determine which steps to show: Structured from backend OR Fallback from logs
    const displaySteps: ProgressStep[] = (progress.steps && progress.steps.length > 0
        ? progress.steps
        : logs.map(l => ({
            label: l.message,
            state: l.status === 'processing' ? 'current' : l.status,
            detail: l.detail
        } as ProgressStep)))
        .filter(s => s.state !== 'pending')
        .map(s => isComplete ? { ...s, state: 'done' as const } : s)
        .sort((a, b) => {
            if (a.state === 'current' && b.state !== 'current') return 1;
            if (a.state !== 'current' && b.state === 'current') return -1;
            return 0;
        });

    const handleViewResults = () => {
        navigate(`/map?run_id=${runId}`);
    };

    if (!runId) return null;

    return (
        <div className="min-h-screen bg-[#0a0d12] text-gray-200 font-sans selection:bg-blue-500/30">
            <div className="max-w-3xl mx-auto p-6 md:p-12 pb-32">

                {/* Header */}
                <header className="mb-12 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 text-sm text-blue-400 font-medium mb-2">
                            <Zap className="w-4 h-4" />
                            <span>Sessione di ricerca AI</span>
                        </div>
                        <h1 className="text-3xl font-semibold text-white tracking-tight flex items-center gap-3">
                            {isComplete ? (
                                'Analisi completata'
                            ) : (
                                <>
                                    <span>Elaborazione richiesta...</span>
                                    <Loader2 className="w-6 h-6 animate-spin text-blue-500/80" />
                                </>
                            )}
                        </h1>
                    </div>
                    {results?.location?.[0] && (
                        <div className="bg-white/5 border border-white/10 px-4 py-2 rounded-lg flex items-center gap-2 self-start md:self-auto">
                            <MapPin className="w-4 h-4 text-emerald-400" />
                            <span className="text-gray-300 font-medium">{results.location[0][0]}</span>
                        </div>
                    )}
                </header>

                {/* Main Process Flow */}
                <div className="relative pl-4 md:pl-0">
                    {/* Vertical Line */}
                    <div className="absolute left-[19px] md:left-[23px] top-4 bottom-4 w-px bg-gradient-to-b from-blue-500/50 via-gray-700/30 to-transparent" />

                    <div className="space-y-8">
                        <AnimatePresence mode="popLayout">


                            {displaySteps.map((step, index) => {
                                const isCurrent = step.state === 'current';
                                const isDone = step.state === 'done';
                                const isPending = step.state === 'pending';

                                return (
                                    <motion.div
                                        key={`${index}-${step.label}`}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        className={`flex items-start gap-6 ${isPending ? 'opacity-40' : 'opacity-100'}`}
                                    >
                                        {/* Icon Bubble */}
                                        <div className={`
                                            relative z-10 shrink-0 w-12 h-12 rounded-full flex items-center justify-center border transition-all duration-500
                                            ${isDone
                                                ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.2)]'
                                                : isCurrent
                                                    ? 'bg-blue-500/10 border-blue-500 text-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.2)]'
                                                    : 'bg-[#12141a] border-gray-800 text-gray-700'
                                            }
                                        `}>
                                            {isDone ? (
                                                <CheckCircle2 className="w-6 h-6" />
                                            ) : isCurrent ? (
                                                <Loader2 className="w-6 h-6 animate-spin" />
                                            ) : (
                                                <Circle className="w-4 h-4" />
                                            )}

                                            {/* Glow effect for current step */}
                                            {isCurrent && (
                                                <div className="absolute inset-0 rounded-full bg-blue-400/20 animate-ping" />
                                            )}
                                        </div>

                                        {/* Text Content */}
                                        <div className="pt-2 flex flex-col gap-2 w-full">
                                            <div className="flex items-center justify-between">
                                                <span className={`font-semibold text-xl tracking-tight ${isCurrent ? 'text-blue-400' : isDone ? 'text-gray-200' : 'text-gray-500'}`}>
                                                    {step.label}
                                                </span>
                                            </div>

                                            {step.detail && (
                                                <motion.div
                                                    initial={{ opacity: 0, height: 0 }}
                                                    animate={{ opacity: 1, height: 'auto' }}
                                                    className="text-gray-400 leading-relaxed max-w-2xl bg-white/5 p-4 rounded-xl border border-white/5 text-sm"
                                                >
                                                    {step.detail}
                                                </motion.div>
                                            )}
                                        </div>
                                    </motion.div>
                                );
                            })}
                            <div ref={logsEndRef} />
                        </AnimatePresence>
                    </div>
                </div>

                {/* Broker Summary (if available) - Clean Card */}
                <AnimatePresence>
                    {isComplete && brokerSummary && (
                        <motion.div
                            ref={summaryRef}
                            initial={{ opacity: 0, y: 30 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3, type: "spring" }}
                            className="mt-16 p-8 rounded-3xl bg-linear-to-br from-[#12141a] to-[#0a0d12] border border-white/10 shadow-2xl relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />

                            <div className="flex items-center gap-4 mb-6 relative z-10">
                                <div className="p-3 bg-emerald-500/10 rounded-2xl border border-emerald-500/20">
                                    <Sparkles className="w-6 h-6 text-emerald-400" />
                                </div>
                                <h3 className="text-xl font-semibold text-white">Executive summary</h3>
                            </div>

                            <div className="prose prose-invert prose-lg max-w-none text-gray-300 relative z-10">
                                <p className="leading-relaxed whitespace-pre-wrap">{brokerSummary}</p>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Final Stats (Minimal) */}
                {isComplete && buildingsFound !== null && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                        className="mt-8 text-center text-gray-500 text-sm"
                    >
                        Trovati {buildingsFound} immobili corrispondenti ai criteri
                    </motion.div>
                )}
            </div>

            {/* Bottom Floating Action Bar */}
            <div className="fixed bottom-0 left-0 w-full p-6 md:p-8 bg-gradient-to-t from-[#0a0d12] via-[#0a0d12]/95 to-transparent flex items-center justify-center gap-4 z-50 pointer-events-none">
                <div className="pointer-events-auto flex items-center gap-3 bg-[#12141a]/80 backdrop-blur-xl p-2 rounded-2xl border border-white/10 shadow-2xl">
                    {isComplete ? (
                        <>
                            <button
                                onClick={() => navigate('/')}
                                className="px-6 py-3 rounded-xl hover:bg-white/5 text-gray-400 hover:text-white transition-all font-medium flex items-center gap-2"
                            >
                                <FileText className="w-4 h-4" />
                                <span>Nuova ricerca</span>
                            </button>
                            <button
                                onClick={handleViewResults}
                                className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all font-medium flex items-center gap-2"
                            >
                                <span>Visualizza mappa interattiva</span>
                                <ArrowRight className="w-4 h-4" />
                            </button>
                        </>
                    ) : (
                        <button
                            onClick={() => navigate('/')}
                            className="px-6 py-3 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 transition-colors font-medium flex items-center gap-2"
                        >
                            <StopCircle className="w-4 h-4" />
                            <span>Interrompi analisi</span>
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ProcessingPage;
