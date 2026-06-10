/**
 * RunDetailModal - Sidebar-style detailed view of an analysis run
 *
 * Features:
 * - Slide-in panel from right (doesn't overlap sidebar)
 * - Run metadata (query, date, status, building count)
 * - Agent steps with prompts and responses
 * - Beautiful JSON syntax highlighting
 * - Expanded code blocks for long content
 * - Actions: Load to map, toggle favorite, close
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    X,
    Clock,
    Calendar,
    Building2,
    Map as MapIcon,
    Star,
    ChevronRight,
    Bot,
    MessageSquare,
    Sparkles,

    Database,
    MapPin,
    Target,
    CheckCircle2,
    Loader2,
    Copy,
    Check,
    AlertTriangle,
    Maximize2,
    Minimize2,
    Code2,
} from 'lucide-react';
import { analysisApi } from '../../api/endpoints/analysis';
import type { AnalysisResults, AgentStep } from '../../api/types';
import { QueryTooltip } from '../common/QueryTooltip';
import { formatFullDate } from '../../utils/dateUtils';
import { MarkdownText } from '../common/MarkdownText';

interface RunDetailModalProps {
    runId: string | null;
    isOpen: boolean;
    onClose: () => void;
    onLoadToMap: (runId: string) => void;
    isFavorite: boolean;
    onToggleFavorite: (runId: string) => void;
}

// Agent step icons and labels
const AGENT_STEP_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string; bgColor: string }> = {
    intent_analysis: { icon: Target, label: 'Analisi Intent', color: 'text-purple-400', bgColor: 'bg-purple-500/10' },
    location_extraction: { icon: MapPin, label: 'Estrazione Location', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },
    property_technical_extraction: { icon: Building2, label: 'Caratteristiche Tecniche', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },

    sql_generation: { icon: Database, label: 'Generazione SQL', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },
    evaluation: { icon: Sparkles, label: 'Valutazione AI', color: 'text-yellow-400', bgColor: 'bg-yellow-500/10' },
    broker_review: { icon: MessageSquare, label: 'Recensione Broker', color: 'text-pink-400', bgColor: 'bg-pink-500/10' },
};

// JSON Syntax Highlighter Component
const JsonViewer: React.FC<{ data: unknown; maxHeight?: string; expanded?: boolean }> = ({
    data,
    maxHeight = '300px',
    expanded = false
}) => {
    const [isExpanded, setIsExpanded] = useState(expanded);

    const syntaxHighlight = (json: string): string => {
        return json.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
            (match) => {
                let cls = 'text-amber-300'; // number
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'text-emerald-400'; // key
                        match = match.slice(0, -1) + '<span class="text-gray-500">:</span>';
                    } else {
                        cls = 'text-emerald-300'; // string
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'text-purple-400'; // boolean
                } else if (/null/.test(match)) {
                    cls = 'text-red-400'; // null
                }
                return `<span class="${cls}">${match}</span>`;
            }
        );
    };

    const formatAndHighlight = (obj: unknown): string => {
        try {
            const json = JSON.stringify(obj, null, 2);
            return syntaxHighlight(json);
        } catch {
            return String(obj);
        }
    };

    const formattedContent = formatAndHighlight(data);
    const lineCount = formattedContent.split('\n').length;
    const needsExpand = lineCount > 15;

    return (
        <div className="relative group">
            <div
                className={`
                    bg-[#0d1117] rounded-xl border border-white/5 overflow-hidden
                    ${!isExpanded && needsExpand ? 'max-h-[200px]' : ''}
                    transition-all duration-300
                `}
                style={{ maxHeight: isExpanded ? 'none' : maxHeight }}
            >
                <pre
                    className="p-4 text-xs font-mono leading-relaxed overflow-auto"
                    style={{ maxHeight: isExpanded ? '600px' : maxHeight }}
                    dangerouslySetInnerHTML={{ __html: formattedContent }}
                />

                {/* Fade overlay when collapsed */}
                {!isExpanded && needsExpand && (
                    <div className="absolute bottom-0 left-0 right-0 h-16 bg-linear-to-t from-[#0d1117] to-transparent pointer-events-none" />
                )}
            </div>

            {/* Expand/Collapse button */}
            {needsExpand && (
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="absolute bottom-2 right-2 flex items-center gap-1.5 px-2.5 py-1.5 bg-white/10 backdrop-blur-sm rounded-lg text-xs text-gray-400 hover:text-white hover:bg-white/20 transition-all"
                >
                    {isExpanded ? (
                        <>
                            <Minimize2 className="w-3 h-3" />
                            Comprimi
                        </>
                    ) : (
                        <>
                            <Maximize2 className="w-3 h-3" />
                            Espandi ({lineCount} righe)
                        </>
                    )}
                </button>
            )}
        </div>
    );
};

export const RunDetailModal: React.FC<RunDetailModalProps> = ({
    runId,
    isOpen,
    onClose,
    onLoadToMap,
    isFavorite,
    onToggleFavorite,
}) => {
    const [results, setResults] = useState<AnalysisResults | null>(null);
    const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
    const [copiedKey, setCopiedKey] = useState<string | null>(null);

    // Fetch run data
    const fetchRunData = useCallback(async () => {
        if (!runId) return;

        try {
            setIsLoading(true);
            setError(null);

            const [resultsData, stepsData] = await Promise.all([
                analysisApi.getResults(runId),
                analysisApi.getAgentSteps(runId, { include_prompt: true, include_raw: true }).catch(() => []),
            ]);

            setResults(resultsData);
            setAgentSteps(stepsData);
        } catch (err) {
            console.error('Failed to fetch run data:', err);
            setError('Impossibile caricare i dettagli della ricerca');
        } finally {
            setIsLoading(false);
        }
    }, [runId]);

    useEffect(() => {
        if (isOpen && runId) {
            fetchRunData();
            setExpandedSteps(new Set());
        }
    }, [isOpen, runId, fetchRunData]);

    // Toggle step expansion
    const toggleStep = useCallback((key: string) => {
        setExpandedSteps(prev => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    }, []);

    // Copy to clipboard
    const copyToClipboard = useCallback(async (text: string, key: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedKey(key);
            setTimeout(() => setCopiedKey(null), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    }, []);


    // Format JSON for clipboard
    const formatJson = (obj: unknown): string => {
        try {
            return JSON.stringify(obj, null, 2);
        } catch {
            return String(obj);
        }
    };

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
                        onClick={onClose}
                    />

                    {/* Slide-in Panel from Right */}
                    <motion.div
                        initial={{ x: '100%', opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: '100%', opacity: 0 }}
                        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
                        className="fixed top-0 right-0 bottom-0 w-full max-w-3xl bg-[#0a0d12] border-l border-white/10 shadow-2xl z-50 flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-start justify-between p-6 border-b border-white/5 bg-[#0a0d12]/95 backdrop-blur-xl">
                            <div className="flex-1 min-w-0 pr-4">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-10 h-10 rounded-xl bg-linear-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                                        <Bot className="w-5 h-5 text-white" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-bold text-white">Dettagli Ricerca</h2>
                                        {results && (
                                            <p className="text-xs text-gray-500 font-mono truncate max-w-[250px]">{results.run_id}</p>
                                        )}
                                    </div>
                                </div>
                                {results && (
                                    <QueryTooltip text={results.query}>
                                        <p className="text-base text-gray-300 line-clamp-2 hover:text-white transition-colors cursor-help">
                                            "{results.query}"
                                        </p>
                                    </QueryTooltip>
                                )}
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2 shrink-0">
                                {runId && (
                                    <button
                                        onClick={() => onToggleFavorite(runId)}
                                        className={`
                                            w-10 h-10 rounded-xl flex items-center justify-center transition-all
                                            ${isFavorite
                                                ? 'bg-amber-500/20 text-amber-400'
                                                : 'bg-white/5 text-gray-400 hover:text-amber-400 hover:bg-white/10'
                                            }
                                        `}
                                        title={isFavorite ? 'Rimuovi dai preferiti' : 'Aggiungi ai preferiti'}
                                    >
                                        <Star className={`w-5 h-5 ${isFavorite ? 'fill-amber-400' : ''}`} />
                                    </button>
                                )}
                                {results?.status === 'completed' && runId && (
                                    <button
                                        onClick={() => onLoadToMap(runId)}
                                        className="flex items-center gap-2 px-4 py-2.5 bg-linear-to-r from-emerald-600 to-green-600 rounded-xl text-sm font-medium text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-all"
                                    >
                                        <MapIcon className="w-4 h-4" />
                                        Carica sulla Mappa
                                    </button>
                                )}
                                <button
                                    onClick={onClose}
                                    className="w-10 h-10 rounded-xl bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-all"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>
                        </div>

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
                                </div>
                            ) : results ? (
                                <div className="p-6 space-y-6">
                                    {/* Metadata Cards - Compact Grid */}
                                    <div className="grid grid-cols-4 gap-4">
                                        <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                                            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1.5">
                                                <Clock className="w-3.5 h-3.5" />
                                                Stato
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <CheckCircle2 className={`w-4 h-4 ${results.status === 'completed' ? 'text-emerald-400' :
                                                    results.status === 'failed' ? 'text-red-400' : 'text-emerald-400'
                                                    }`} />
                                                <span className="text-sm text-white">
                                                    {results.status === 'completed' ? 'Completato' :
                                                        results.status === 'failed' ? 'Fallito' :
                                                            results.status === 'processing' ? 'In corso' : results.status}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                                            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1.5">
                                                <Calendar className="w-3.5 h-3.5" />
                                                Creato
                                            </div>
                                            <span className="text-sm text-white">{formatFullDate(results.created_at)}</span>
                                        </div>
                                        <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                                            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1.5">
                                                <Building2 className="w-3.5 h-3.5" />
                                                Immobili
                                            </div>
                                            <span className="text-sm text-white font-semibold">{results.buildings?.length || 0}</span>
                                        </div>
                                        <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                                            <div className="flex items-center gap-2 text-gray-500 text-xs mb-1.5">
                                                <MapPin className="w-3.5 h-3.5" />
                                                Location
                                            </div>
                                            <span className="text-sm text-white truncate block">
                                                {results.location?.[0]?.[0] || 'N/A'}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Broker Summary */}
                                    {results.broker_summary && (
                                        <div className="bg-linear-to-br from-pink-500/10 to-purple-500/10 rounded-xl p-5 border border-pink-500/20">
                                            <div className="flex items-center gap-2 mb-3">
                                                <MessageSquare className="w-5 h-5 text-pink-400" />
                                                <h3 className="text-sm font-semibold text-white">Riepilogo AI Broker</h3>
                                            </div>
                                             <div className="text-sm text-gray-300 leading-relaxed">
                                                 <MarkdownText text={results.broker_summary} />
                                             </div>
                                        </div>
                                    )}

                                    {/* Agent Steps */}
                                    <div>
                                        <div className="flex items-center justify-between mb-4">
                                            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                                                <Bot className="w-5 h-5 text-emerald-400" />
                                                Passaggi Agenti AI
                                                <span className="text-xs text-gray-500 font-normal px-2 py-1 bg-white/5 rounded-lg">
                                                    {agentSteps.length} steps
                                                </span>
                                            </h3>
                                        </div>

                                        {agentSteps.length === 0 ? (
                                            <div className="text-center text-gray-500 py-8 text-base">
                                                Nessun dettaglio disponibile per questa ricerca
                                            </div>
                                        ) : (
                                            <div className="space-y-3">
                                                {agentSteps.map((step, stepIndex) => {
                                                    const config = AGENT_STEP_CONFIG[step.key] || {
                                                        icon: Bot,
                                                        label: step.label || step.key,
                                                        color: 'text-gray-400',
                                                        bgColor: 'bg-gray-500/10',
                                                    };
                                                    const StepIcon = config.icon;
                                                    const isExpanded = expandedSteps.has(step.key);

                                                    return (
                                                        <div
                                                            key={step.key}
                                                            className="bg-white/2 rounded-xl border border-white/5 overflow-hidden"
                                                        >
                                                            {/* Step Header */}
                                                            <button
                                                                onClick={() => toggleStep(step.key)}
                                                                className="w-full flex items-center gap-3 px-4 py-3.5 text-left hover:bg-white/2 transition-colors"
                                                            >
                                                                <div className="flex items-center gap-2 text-gray-500 text-xs">
                                                                    <span className="w-6 h-6 rounded-full bg-white/5 flex items-center justify-center text-xs font-medium">
                                                                        {stepIndex + 1}
                                                                    </span>
                                                                </div>
                                                                <div className={`w-8 h-8 rounded-lg ${config.bgColor} flex items-center justify-center ${config.color}`}>
                                                                    <StepIcon className="w-4 h-4" />
                                                                </div>
                                                                <div className="flex-1 min-w-0">
                                                                    <span className="text-sm font-medium text-white">
                                                                        {config.label}
                                                                    </span>
                                                                    <span className="text-xs text-gray-600 ml-2 font-mono">
                                                                        {step.key}
                                                                    </span>
                                                                </div>
                                                                <motion.div
                                                                    animate={{ rotate: isExpanded ? 90 : 0 }}
                                                                    transition={{ duration: 0.2 }}
                                                                >
                                                                    <ChevronRight className="w-4 h-4 text-gray-500" />
                                                                </motion.div>
                                                            </button>

                                                            {/* Step Content */}
                                                            <AnimatePresence>
                                                                {isExpanded && (
                                                                    <motion.div
                                                                        initial={{ height: 0, opacity: 0 }}
                                                                        animate={{ height: 'auto', opacity: 1 }}
                                                                        exit={{ height: 0, opacity: 0 }}
                                                                        transition={{ duration: 0.2 }}
                                                                        className="overflow-hidden"
                                                                    >
                                                                        <div className="px-4 pb-4 space-y-5">
                                                                            {/* Prompt - System and User separated */}
                                                                            {step.prompt != null && (
                                                                                <div className="space-y-4">
                                                                                    {/* System Prompt */}
                                                                                    {step.prompt.system && step.prompt.system !== 'N/D' && (
                                                                                        <div>
                                                                                            <div className="flex items-center justify-between mb-2">
                                                                                                <span className="text-xs text-violet-400/70 uppercase tracking-wider font-medium flex items-center gap-1.5">
                                                                                                    <Code2 className="w-3 h-3" />
                                                                                                    System Prompt
                                                                                                </span>
                                                                                                <button
                                                                                                    onClick={() => copyToClipboard(step.prompt?.system || '', `system-${step.key}`)}
                                                                                                    className="text-xs text-gray-500 hover:text-white flex items-center gap-1.5 transition-colors px-2.5 py-1 rounded-md hover:bg-white/5"
                                                                                                >
                                                                                                    {copiedKey === `system-${step.key}` ? (
                                                                                                        <>
                                                                                                            <Check className="w-3 h-3 text-emerald-400" />
                                                                                                            Copiato
                                                                                                        </>
                                                                                                    ) : (
                                                                                                        <>
                                                                                                            <Copy className="w-3 h-3" />
                                                                                                            Copia
                                                                                                        </>
                                                                                                    )}
                                                                                                </button>
                                                                                            </div>
                                                                                            <div className="bg-violet-500/5 border border-violet-500/10 rounded-xl p-4">
                                                                                                <pre className="text-sm text-violet-200/80 whitespace-pre-wrap leading-relaxed font-mono">
                                                                                                    {step.prompt.system}
                                                                                                </pre>
                                                                                            </div>
                                                                                        </div>
                                                                                    )}

                                                                                    {/* User Prompt */}
                                                                                    {step.prompt.user && step.prompt.user !== 'N/D' && (
                                                                                        <div>
                                                                                            <div className="flex items-center justify-between mb-2">
                                                                                                <span className="text-xs text-emerald-400/70 uppercase tracking-wider font-medium flex items-center gap-1.5">
                                                                                                    <MessageSquare className="w-3 h-3" />
                                                                                                    User Prompt
                                                                                                </span>
                                                                                                <button
                                                                                                    onClick={() => copyToClipboard(step.prompt?.user || '', `user-${step.key}`)}
                                                                                                    className="text-xs text-gray-500 hover:text-white flex items-center gap-1.5 transition-colors px-2.5 py-1 rounded-md hover:bg-white/5"
                                                                                                >
                                                                                                    {copiedKey === `user-${step.key}` ? (
                                                                                                        <>
                                                                                                            <Check className="w-3 h-3 text-emerald-400" />
                                                                                                            Copiato
                                                                                                        </>
                                                                                                    ) : (
                                                                                                        <>
                                                                                                            <Copy className="w-3 h-3" />
                                                                                                            Copia
                                                                                                        </>
                                                                                                    )}
                                                                                                </button>
                                                                                            </div>
                                                                                            <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-4">
                                                                                                <pre className="text-sm text-emerald-200/80 whitespace-pre-wrap leading-relaxed font-mono">
                                                                                                    {step.prompt.user}
                                                                                                </pre>
                                                                                            </div>
                                                                                        </div>
                                                                                    )}
                                                                                </div>
                                                                            )}

                                                                            {/* Response */}
                                                                            {step.response != null && (
                                                                                <div>
                                                                                    <div className="flex items-center justify-between mb-2">
                                                                                        <span className="text-xs text-emerald-400/70 uppercase tracking-wider font-medium">Risposta</span>
                                                                                        <button
                                                                                            onClick={() => copyToClipboard(
                                                                                                typeof step.response === 'string'
                                                                                                    ? step.response
                                                                                                    : formatJson(step.response),
                                                                                                `response-${step.key}`
                                                                                            )}
                                                                                            className="text-xs text-gray-500 hover:text-white flex items-center gap-1.5 transition-colors px-2.5 py-1 rounded-md hover:bg-white/5"
                                                                                        >
                                                                                            {copiedKey === `response-${step.key}` ? (
                                                                                                <>
                                                                                                    <Check className="w-3 h-3 text-emerald-400" />
                                                                                                    Copiato
                                                                                                </>
                                                                                            ) : (
                                                                                                <>
                                                                                                    <Copy className="w-3 h-3" />
                                                                                                    Copia
                                                                                                </>
                                                                                            )}
                                                                                        </button>
                                                                                    </div>
                                                                                    {typeof step.response === 'string' ? (
                                                                                        <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-4">
                                                                                            <p className="text-sm text-emerald-200/80 whitespace-pre-wrap leading-relaxed">
                                                                                                {step.response}
                                                                                            </p>
                                                                                        </div>
                                                                                    ) : (
                                                                                        <JsonViewer data={step.response} maxHeight="350px" />
                                                                                    )}
                                                                                </div>
                                                                            )}

                                                                            {/* Data */}
                                                                            {step.data != null && Object.keys(step.data).length > 0 && (
                                                                                <div>
                                                                                    <div className="flex items-center justify-between mb-2">
                                                                                        <span className="text-xs text-emerald-400/70 uppercase tracking-wider font-medium">Dati Estratti</span>
                                                                                        <button
                                                                                            onClick={() => copyToClipboard(formatJson(step.data as Record<string, unknown>), `data-${step.key}`)}
                                                                                            className="text-xs text-gray-500 hover:text-white flex items-center gap-1.5 transition-colors px-2.5 py-1 rounded-md hover:bg-white/5"
                                                                                        >
                                                                                            {copiedKey === `data-${step.key}` ? (
                                                                                                <>
                                                                                                    <Check className="w-3 h-3 text-emerald-400" />
                                                                                                    Copiato
                                                                                                </>
                                                                                            ) : (
                                                                                                <>
                                                                                                    <Copy className="w-3 h-3" />
                                                                                                    Copia
                                                                                                </>
                                                                                            )}
                                                                                        </button>
                                                                                    </div>
                                                                                    <JsonViewer data={step.data} maxHeight="250px" />
                                                                                </div>
                                                                            )}
                                                                        </div>
                                                                    </motion.div>
                                                                )}
                                                            </AnimatePresence>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};
