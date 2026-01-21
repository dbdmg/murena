/**
 * ProcessingPage - Agent Processing View
 *
 * Shows real-time progress of analysis:
 * - Horizontal stepper timeline (Ingestion → Market Scan → Evaluation → Synthesis)
 * - Parameters Locked card with dataset stats
 * - Terminal/Log stream with agent steps from backend
 * - Broker summary card when analysis completes
 * - "View Results on Map" button when complete
 */

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useParams, useNavigate } from 'react-router-dom';
import {
    CheckCircle2,
    Loader2,
    ArrowRight,
    Terminal,
    Zap,
    Search,
    TrendingUp,
    Database,
    BrainCircuit,
    Cpu,
    Network,
    Activity,
    Lock,
    Sparkles,
    MessageSquare,
    StopCircle,
    FileText,
    MapPin,
    Settings2,
    Building2
} from 'lucide-react';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';
import { analysisApi } from '../api/endpoints/analysis';
import type { AnalysisResults, AgentStep } from '../api/types';

// Timeline steps mapping based on backend graph nodes
const TIMELINE_STEPS = [
    { key: 'ingestion', label: 'Data Ingestion', icon: Database, color: 'text-blue-400' },
    { key: 'market_scan', label: 'Market Scan', icon: Search, color: 'text-purple-400' },
    { key: 'evaluation', label: 'Evaluation', icon: BrainCircuit, color: 'text-pink-400' },
    { key: 'synthesis', label: 'Synthesis', icon: Sparkles, color: 'text-amber-400' }
];

const INSIGHTS = [
    "Analisi di 50+ vincoli normativi in corso...",
    "Lo sapevi? La vicinanza al Politecnico aumenta il ROI del 15%.",
    "Cross-referencing con il Piano Regolatore Generale...",
    "Valutazione impatto acustico e ambientale...",
    "Calcolo proiezioni di rendimento a 10 anni...",
    "Ottimizzazione energetica dei candidati individuati...",
    "Verifica accessibilità trasporti pubblici..."
];

// Dataset size (could be fetched from backend config)
const DATASET_TOTAL_BUILDINGS = 14192;

interface LogEntry {
    timestamp: string;
    message: string;
    status: 'done' | 'processing' | 'pending';
    detail?: string;
}

// --- Sub-Components ---

const TypewriterText = ({ text }: { text: string }) => {
    // Simple typewriter effect
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        setDisplayedText('');
        let i = 0;
        const interval = setInterval(() => {
            if (i < text.length) {
                setDisplayedText(prev => prev + text.charAt(i));
                i++;
            } else {
                clearInterval(interval);
            }
        }, 15); // Fast typing speed
        return () => clearInterval(interval);
    }, [text]);

    return <span>{displayedText}</span>;
};

const MicroMetric = ({ label, icon: Icon, valuePrefix = '', suffix = '' }: { label: string, icon: any, valuePrefix?: string, suffix?: string }) => {
    const [value, setValue] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setValue(prev => prev + Math.floor(Math.random() * 5));
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col bg-white/5 border border-white/5 rounded-lg p-2.5">
            <div className="flex items-center gap-1.5 text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                <Icon className="w-3 h-3" />
                <span>{label}</span>
            </div>
            <div className="text-lg font-mono font-bold text-gray-300">
                {valuePrefix}{value.toLocaleString()}{suffix}
            </div>
        </div>
    );
};

const NeuralPulse = ({ active }: { active: boolean }) => {
    return (
        <div className="relative flex items-center justify-center w-16 h-16">
            {active && (
                <>
                    <motion.div
                        animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                        className="absolute inset-0 bg-blue-500/30 rounded-full blur-xl"
                    />
                    <motion.div
                        animate={{ scale: [1, 1.2, 1], opacity: [0.8, 0.4, 0.8] }}
                        transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
                        className="absolute inset-2 bg-cyan-400/20 rounded-full blur-md"
                    />
                </>
            )}
            <div className={`
                relative z-10 w-10 h-10 rounded-full flex items-center justify-center
                ${active ? 'bg-linear-to-br from-blue-500 to-cyan-400 shadow-lg shadow-cyan-500/50' : 'bg-gray-700'}
            `}>
                <BrainCircuit className={`w-5 h-5 ${active ? 'text-white' : 'text-gray-400'}`} />
            </div>
        </div>
    );
};

export const ProcessingPage: React.FC = () => {
    const { runId } = useParams<{ runId: string }>();
    const navigate = useNavigate();

    const [results, setResults] = useState<AnalysisResults | null>(null);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);
    const [isComplete, setIsComplete] = useState(false);
    const [buildingsFound, setBuildingsFound] = useState<number | null>(null);
    const [buildingsEvaluated, setBuildingsEvaluated] = useState<number | null>(null);
    const [brokerSummary, setBrokerSummary] = useState<string | null>(null);
    const [, setAgentSteps] = useState<AgentStep[]>([]);
    const [currentInsightIndex, setCurrentInsightIndex] = useState(0);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const hasFetchedSteps = useRef(false);
    const summaryRef = useRef<HTMLDivElement>(null);

    // Insight Carousel Rotation
    useEffect(() => {
        if (isComplete) return;
        const interval = setInterval(() => {
            setCurrentInsightIndex(prev => (prev + 1) % INSIGHTS.length);
        }, 4000);
        return () => clearInterval(interval);
    }, [isComplete]);

    // Use specific progress hook linked to this runId
    const progress = useAnalysisProgress(runId ?? null, { autoConnect: true });

    // Fetch agent steps when available (polling or on complete)
    const fetchAgentSteps = useCallback(async () => {
        if (!runId) return;
        try {
            const steps = await analysisApi.getAgentSteps(runId, {
                include_prompt: false,
                include_raw: true,
            });
            setAgentSteps(steps);

            // Convert steps to log entries with meaningful details
            const newLogs: LogEntry[] = steps.map(step => ({
                timestamp: new Date().toLocaleTimeString('it-IT', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                }),
                message: step.label || step.key,
                status: 'done' as const,
                detail: extractStepDetail(step),
            }));

            if (newLogs.length > 0) {
                setLogs(newLogs);
            }
        } catch {
            // Steps not ready yet
        }
    }, [runId]);

    // Extract meaningful detail from agent step response
    const extractStepDetail = (step: AgentStep): string | undefined => {
        if (!step.response) return undefined;

        const response = step.response;

        // Handle different step types
        if (step.key === 'location_extraction' && typeof response === 'object') {
            const r = response as Record<string, unknown>;
            if (Array.isArray(r.places)) {
                return `Found ${r.places.length} location(s)`;
            }
        }

        if (step.key === 'typology_extraction' && typeof response === 'object') {
            const r = response as Record<string, unknown>;
            if (Array.isArray(r.typologies)) {
                return `Types: ${(r.typologies as string[]).slice(0, 3).join(', ')}`;
            }
        }

        if (step.key === 'sql_generation' && typeof response === 'string') {
            return response.length > 50 ? `${response.slice(0, 50)}...` : response;
        }

        if (step.key === 'evaluation' && typeof response === 'object') {
            const r = response as Record<string, unknown>;
            if (Array.isArray(r.results)) {
                return `Evaluated ${r.results.length} buildings`;
            }
        }

        if (typeof response === 'string' && response.length > 0) {
            return response.length > 80 ? `${response.slice(0, 80)}...` : response;
        }

        return undefined;
    };

    // START CHANGES: UX Improvements
    const [visualStepIndex, setVisualStepIndex] = useState(0);

    // Smoothly advance visual steps up to the real target (enforce min duration)
    useEffect(() => {
        // Target is either completion or current progress step
        const targetStep = isComplete ? TIMELINE_STEPS.length : currentStepIndex;

        if (visualStepIndex < targetStep) {
            const timeout = setTimeout(() => {
                setVisualStepIndex(prev => prev + 1);
            }, 800); // 800ms minimum per step for better UX
            return () => clearTimeout(timeout);
        }
    }, [visualStepIndex, currentStepIndex, isComplete]);

    // Only show completion state when VISUAL animation finishes
    const isVisuallyComplete = isComplete && visualStepIndex === TIMELINE_STEPS.length;

    // REMOVED: Auto-scroll to summary (User feedback: unwanted behavior)
    /* useEffect(() => {
        if (isComplete && brokerSummary) ...
    }, ...); */

    // END CHANGES

    // Update UI based on WebSocket progress
    useEffect(() => {
        if (progress.percent > 0) {
            // Map progress percentage to timeline step
            const stepIndex = Math.floor((progress.percent / 100) * TIMELINE_STEPS.length);
            setCurrentStepIndex(Math.min(stepIndex, TIMELINE_STEPS.length));
        }

        // Add log entry for current step from WebSocket
        if (progress.message && progress.step) {
            setLogs(prev => {
                const exists = prev.some(l => l.message === progress.step);
                if (exists) return prev;
                return [...prev, {
                    timestamp: new Date().toLocaleTimeString('it-IT', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                    }),
                    message: progress.step,
                    status: 'processing' as const,
                }];
            });
        }

        // Handle WebSocket completion
        if (progress.isComplete) {
            setIsComplete(true);
            setCurrentStepIndex(TIMELINE_STEPS.length);
            // Fetch final agent steps
            if (!hasFetchedSteps.current) {
                hasFetchedSteps.current = true;
                fetchAgentSteps();
            }
            // Fetch results
            if (runId && !results) {
                analysisApi.getResults(runId).then(resultsData => {
                    if (resultsData.status === 'completed') {
                        setResults(resultsData);
                        setBuildingsFound(resultsData.buildings?.length || 0);
                        setBuildingsEvaluated(
                            resultsData.buildings?.filter(b => b.is_evaluated).length || 0
                        );
                        setBrokerSummary(resultsData.broker_summary || null);
                    }
                }).catch(err => console.error('Failed to fetch results:', err));
            }
        }
    }, [progress.percent, progress.message, progress.step, progress.isComplete, fetchAgentSteps, runId, results]);

    // Poll for final results
    useEffect(() => {
        if (!runId || isComplete) return;

        const pollInterval = setInterval(async () => {
            try {
                const resultsData = await analysisApi.getResults(runId);
                if (resultsData.status === 'completed') {
                    setResults(resultsData);
                    setBuildingsFound(resultsData.buildings?.length || 0);
                    setBuildingsEvaluated(
                        resultsData.buildings?.filter(b => b.is_evaluated).length || 0
                    );
                    setBrokerSummary(resultsData.broker_summary || null);
                    setIsComplete(true);
                    setCurrentStepIndex(TIMELINE_STEPS.length);
                    clearInterval(pollInterval);

                    if (!hasFetchedSteps.current) {
                        hasFetchedSteps.current = true;
                        fetchAgentSteps();
                    }
                } else if (resultsData.status === 'failed') {
                    setIsComplete(true);
                    clearInterval(pollInterval);
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 5000);

        return () => clearInterval(pollInterval);
    }, [runId, isComplete, fetchAgentSteps]);

    // Auto-scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const handleViewResults = () => {
        navigate(`/map?run_id=${runId}`);
    };

    if (!runId) {
        return (
            <div className="min-h-full flex items-center justify-center">
                <p className="text-gray-500">No run ID provided</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-linear-to-br from-[#0a0d12] via-[#0d1117] to-[#0a1628]">
            {/* Scrollable Content Container with padding for fixed footer */}
            <div className="p-6 md:p-8 pb-48">
                {/* Centered Container */}
                <div className="max-w-4xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2 text-sm text-gray-400">
                                <Zap className="w-4 h-4 text-blue-400" />
                                <span>Research Session</span>
                            </div>
                            {results?.location?.[0] && (
                                <>
                                    <span className="text-gray-600">/</span>
                                    <div className="flex items-center gap-1.5 text-sm">
                                        <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                                        <span className="text-gray-300">{results.location[0][0]}</span>
                                    </div>
                                </>
                            )}
                        </div>

                        {/* Agent Status Badge - REPLACED WITH NEURAL PULSE SECTION BELOW */}
                    </div>

                    {/* HERO SECTION: Neural Pulse & Status */}
                    <div className="flex flex-col items-center justify-center mb-10 py-4">
                        <NeuralPulse active={!isVisuallyComplete} />

                        <div className="mt-4 text-center">
                            <h2 className="text-2xl md:text-3xl font-bold text-white mb-2">
                                {isVisuallyComplete ? 'Analysis Complete' : 'Neural Engine Active'}
                            </h2>
                            <p className="text-gray-400 flex items-center justify-center gap-2 h-6">
                                {isVisuallyComplete ? (
                                    <span className="text-emerald-400 flex items-center gap-2">
                                        <CheckCircle2 className="w-4 h-4" />
                                        All tasks finished successfully
                                    </span>
                                ) : (
                                    <span className="flex items-center gap-2">
                                        <Loader2 className="w-3 h-3 animate-spin text-cyan-400" />
                                        {INSIGHTS[currentInsightIndex]}
                                    </span>
                                )}
                            </p>
                        </div>
                    </div>

                    {/* Timeline Stepper - Horizontal with connecting lines */}
                    <div className="flex items-center justify-between mb-8 px-2">
                        {TIMELINE_STEPS.map((step, i) => {
                            // Use VISUAL step index
                            const isCompleted = i < visualStepIndex;
                            const isCurrent = i === visualStepIndex && !isVisuallyComplete;
                            const StepIcon = step.icon;

                            return (
                                <React.Fragment key={step.key}>
                                    <div className="flex flex-col items-center">
                                        <motion.div
                                            initial={{ scale: 0.8, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            transition={{ delay: i * 0.1 }}
                                            className={`
                                            w-12 h-12 rounded-full flex items-center justify-center mb-2
                                            transition-all duration-300
                                            ${isCompleted
                                                    ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                                                    : isCurrent
                                                        ? 'bg-blue-500/20 text-blue-400 border-2 border-blue-500 animate-pulse'
                                                        : 'bg-white/5 text-gray-500 border border-white/10'
                                                }
                                        `}
                                        >
                                            {isCompleted ? (
                                                <CheckCircle2 className="w-5 h-5" />
                                            ) : isCurrent ? (
                                                <Loader2 className="w-5 h-5 animate-spin" />
                                            ) : (
                                                <StepIcon className="w-5 h-5" />
                                            )}
                                        </motion.div>
                                        <span className={`
                                        text-xs font-medium
                                        ${isCompleted || isCurrent ? 'text-gray-300' : 'text-gray-500'}
                                    `}>
                                            {step.label}
                                        </span>
                                    </div>

                                    {/* Connecting Line */}
                                    {i < TIMELINE_STEPS.length - 1 && (
                                        <div className={`
                                        flex-1 h-0.5 mx-4 rounded-full transition-all duration-500
                                        ${i < visualStepIndex ? 'bg-blue-500' : 'bg-white/10'}
                                    `} />
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </div>

                    {/* Main Content - Vertical Layout */}
                    <div className="flex flex-col gap-6">
                        {/* Parameters Locked Card & Micro-Metrics */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {/* Main Params Card */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.2 }}
                                className="md:col-span-2 p-5 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 shadow-xl shadow-black/20"
                            >
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                                        <Settings2 className="w-5 h-5 text-emerald-400" />
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <Lock className="w-4 h-4 text-emerald-400" />
                                            <span className="text-emerald-400 font-medium">Session Parameters Locked</span>
                                        </div>
                                        <span className="text-xs text-gray-500">
                                            {progress.percent > 0 ? `${progress.percent.toFixed(0)}% processed` : 'Initializing...'}
                                        </span>
                                    </div>
                                </div>

                                {/* Source Badge */}
                                <div className="mt-4 flex items-center gap-2">
                                    <div className="px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20">
                                        <span className="text-xs font-medium text-blue-400">
                                            <Database className="w-3 h-3 inline mr-1.5" />
                                            MEF Dataset
                                        </span>
                                    </div>
                                    <div className="px-3 py-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20">
                                        <span className="text-xs font-medium text-purple-400">
                                            <Cpu className="w-3 h-3 inline mr-1.5" />
                                            Neural Engine v4.2
                                        </span>
                                    </div>
                                </div>
                            </motion.div>

                            {/* Live Metrics Column */}
                            <div className="space-y-3">
                                <MicroMetric label="Tokens" icon={Activity} valuePrefix="" suffix="/s" />
                                <MicroMetric label="Nodes" icon={Network} valuePrefix="" suffix="" />
                            </div>
                        </div>

                        {/* Stats Grid - Moved below params */}
                        <div className="grid grid-cols-3 gap-3">
                            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                                <div className="flex items-center gap-2 mb-2">
                                    <Building2 className="w-3.5 h-3.5 text-gray-500" />
                                    <span className="text-[10px] text-gray-500 uppercase tracking-wide">Total Dataset</span>
                                </div>
                                <div className="text-2xl font-bold text-white">
                                    {DATASET_TOTAL_BUILDINGS.toLocaleString()}
                                </div>
                            </div>
                            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                                <div className="flex items-center gap-2 mb-2">
                                    <Search className="w-3.5 h-3.5 text-gray-500" />
                                    <span className="text-[10px] text-gray-500 uppercase tracking-wide">Found</span>
                                </div>
                                <div className="text-2xl font-bold text-white">
                                    {isComplete && buildingsFound !== null ? buildingsFound.toLocaleString() : '---'}
                                </div>
                            </div>
                            <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                                <div className="flex items-center gap-2 mb-2">
                                    <TrendingUp className="w-3.5 h-3.5 text-gray-500" />
                                    <span className="text-[10px] text-gray-500 uppercase tracking-wide">Evaluated</span>
                                </div>
                                <div className="text-2xl font-bold text-white">
                                    {isComplete && buildingsEvaluated !== null ? buildingsEvaluated.toLocaleString() : '---'}
                                </div>
                            </div>
                        </div>


                        {/* Agent Log Stream Card with Neon Glow */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="p-5 rounded-2xl bg-[#0a0d12] border border-cyan-500/20 shadow-lg shadow-cyan-900/10 relative overflow-hidden"
                        >
                            <div className="absolute top-0 left-0 w-full h-1 bg-linear-to-r from-transparent via-cyan-500 to-transparent opacity-50" />

                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                    <Terminal className="w-4 h-4 text-cyan-400" />
                                    <span className="text-xs text-cyan-400/80 font-mono tracking-wider">LIVE_AGENT_FEED</span>
                                </div>
                                <div className="flex gap-1">
                                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/30" />
                                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/10" />
                                </div>
                            </div>

                            <div className="h-48 overflow-y-auto font-mono text-xs space-y-2 pr-2 custom-scrollbar">
                                <AnimatePresence mode='popLayout'>
                                    {logs.length === 0 && (
                                        <motion.div
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="text-gray-600 py-8 text-center"
                                        >
                                            <span className="animate-pulse">_initializing_neural_link...</span>
                                        </motion.div>
                                    )}
                                    {logs.map((log, i) => (
                                        <motion.div
                                            key={`${log.message}-${i}`}
                                            initial={{ opacity: 0, x: -10 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            className="flex flex-col gap-0.5 py-1.5 border-b border-white/5 last:border-0"
                                        >
                                            <div className="flex items-start gap-3">
                                                <span className="text-gray-600 shrink-0">[{log.timestamp}]</span>
                                                <span className="text-gray-300 flex-1 font-medium leading-relaxed">
                                                    {i === logs.length - 1 && log.status !== 'done' ? (
                                                        <TypewriterText text={log.message} />
                                                    ) : (
                                                        log.message
                                                    )}
                                                </span>
                                            </div>
                                            {log.detail && (
                                                <div className="pl-[72px] text-gray-500 text-[11px] truncate">
                                                    {log.detail}
                                                </div>
                                            )}
                                        </motion.div>
                                    ))}
                                </AnimatePresence>
                                <div ref={logsEndRef} />
                            </div>
                        </motion.div>

                        {/* Broker Agent Summary Card - Shows when analysis completes */}
                        <AnimatePresence>
                            {isComplete && brokerSummary && (
                                <motion.div
                                    ref={summaryRef}
                                    initial={{ opacity: 0, y: 20, scale: 0.98 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: -20 }}
                                    transition={{ type: 'spring', duration: 0.5 }}
                                    className="p-6 rounded-2xl bg-[#0f1218]/80 backdrop-blur-xl border border-cyan-500/20 shadow-xl shadow-black/20 scroll-mt-24"
                                >
                                    <div className="flex items-start gap-4">
                                        <div className="w-12 h-12 rounded-xl bg-cyan-500/10 flex items-center justify-center shrink-0">
                                            <MessageSquare className="w-6 h-6 text-cyan-400" />
                                        </div>
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-3">
                                                <Sparkles className="w-4 h-4 text-cyan-400" />
                                                <h3 className="text-cyan-400 font-semibold">Broker Agent Summary</h3>
                                            </div>
                                            <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                                                {brokerSummary}
                                            </p>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Analysis Complete Banner */}
                        <AnimatePresence>
                            {isComplete && (
                                <motion.div
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -20 }}
                                    className="p-4 rounded-xl flex items-center justify-between bg-emerald-500/5 backdrop-blur-xl border border-emerald-500/20 shadow-lg shadow-black/10 mb-8"
                                >
                                    <div className="flex items-center gap-3">
                                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                                        <div>
                                            <span className="font-medium text-emerald-400">
                                                Analysis Complete
                                            </span>
                                            <span className="text-gray-400 ml-2">
                                                Found {buildingsFound || 0} properties
                                                {buildingsEvaluated ? ` • ${buildingsEvaluated} evaluated` : ''}
                                            </span>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Spacer to prevent visual overlap with sticky footer */}
                        <div className="h-40" aria-hidden="true" />
                    </div>
                </div>
            </div>

            {/* Sticky Footer Action Buttons */}
            <div className={`
                fixed bottom-0 left-0 w-full p-4 md:px-8 bg-[#0a0d12]/80 backdrop-blur-xl border-t border-white/5 z-50 flex items-center justify-end gap-3
                transition-transform duration-300
                ${isComplete || !isComplete /* Always visible relative to bottom, but we could hide it if needed */ ? 'translate-y-0' : 'translate-y-0'}
            `}>
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white transition-all text-sm font-medium"
                >
                    <FileText className="w-4 h-4" />
                    <span>Modify Criteria</span>
                </button>

                <motion.button
                    onClick={handleViewResults}
                    disabled={!isComplete}
                    whileHover={{ scale: isComplete ? 1.02 : 1 }}
                    whileTap={{ scale: isComplete ? 0.98 : 1 }}
                    className={`
                    flex items-center gap-2 px-6 py-2.5 rounded-xl font-medium text-sm
                    transition-all duration-200
                    ${isComplete
                            ? 'bg-linear-to-r from-blue-600 to-cyan-500 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40'
                            : 'bg-white/5 text-gray-500 cursor-not-allowed'
                        }
                `}
                >
                    <span>View Results on Map</span>
                    <ArrowRight className="w-4 h-4" />
                </motion.button>

                {!isComplete && (
                    <button
                        className="p-2.5 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                        title="Stop Analysis"
                    >
                        <StopCircle className="w-5 h-5" />
                    </button>
                )}
            </div>
        </div>
    );
};

export default ProcessingPage;
