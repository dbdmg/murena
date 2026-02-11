import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, SearchCode, Terminal, AlertCircle, Loader2, FileText, Code2 } from 'lucide-react';
import { analysisApi } from '../../api/endpoints/analysis';
import { parseSqlWhereConditions } from '../../utils/sqlUtils';
import { AgentTraceViewer } from './AgentTraceViewer';
import type { SqlCondition } from '../../utils/sqlUtils';
import type { AgentTraceItem } from '../../api/types';

// ============================================================================
// Types
// ============================================================================

interface SQLFiltersHUDProps {
    activeRunId: string | null;
    isOpen: boolean;
    onToggle: () => void;
    className?: string;
}

interface SQLStepInfo {
    key: string;
    label: string;
    sql: string;
    conditions: SqlCondition[];
    isRelaxed: boolean;
    attempt: number;
}

// ============================================================================
// Recursive Condition Component
// ============================================================================

interface ConditionItemProps {
    condition: SqlCondition;
    depth?: number;
}

// Helper for cleaner display of long lists (like IN clauses)
const itemPrettify = (content: string) => {
    const cleanContent = content.trim();
    if (!cleanContent) return null;

    // 1. Case: IN clause
    const inMatch = cleanContent.match(/^(.+?)\s+IN\s*\((.+)\)$/i);
    if (inMatch) {
        const field = inMatch[1].trim();
        const values = inMatch[2].split(',').map(v => v.trim().replace(/^'|'$/g, ''));

        return (
            <div className="flex flex-col gap-2.5">
                <div className="flex items-center gap-2">
                    <span className="text-amber-400 font-bold bg-amber-400/10 px-2 py-0.5 rounded-md text-[13px] border border-amber-400/20 shadow-sm">{field}</span>
                    <span className="text-gray-500 text-[10px] font-bold uppercase tracking-tight opacity-70">in lista</span>
                </div>
                <div className="flex flex-wrap gap-1.5 pl-1">
                    {values.map((v, i) => (
                        <span key={i} className="px-2.5 py-1 bg-white/3 rounded-lg text-[11px] border border-white/5 text-gray-400 font-mono italic">
                            "{v}"
                        </span>
                    ))}
                </div>
            </div>
        );
    }

    // 2. Case: BETWEEN (special handling for range)
    const betweenMatch = cleanContent.match(/^(.*?)\s+BETWEEN\s+(.*?)\s+AND\s+(.*)$/i);
    if (betweenMatch) {
        const field = betweenMatch[1].trim();
        const val1 = betweenMatch[2].trim();
        const val2 = betweenMatch[3].trim();

        return (
            <div className="flex items-center gap-3 flex-wrap min-w-0">
                <span className="text-amber-400 font-bold bg-amber-400/10 px-2 py-0.5 rounded-md text-[13px] border border-amber-400/20 shadow-sm shrink-0">
                    {field}
                </span>

                <div className="flex items-center gap-2">
                    <span className="text-gray-500 text-[10px] font-bold uppercase shrink-0 opacity-70">between</span>
                    <span className="text-gray-200 font-mono text-sm bg-white/2 px-2 py-0.5 rounded border border-white/5">
                        {val1}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <span className="text-gray-500 text-[10px] font-bold uppercase shrink-0 opacity-70">and</span>
                    <span className="text-gray-200 font-mono text-sm bg-white/2 px-2 py-0.5 rounded border border-white/5">
                        {val2}
                    </span>
                </div>
            </div>
        );
    }

    // 3. Case: Binary operators
    // Using regex to be more robust against missing spaces (e.g. field>=100)
    const opRegex = /^(.*?)\s*(>=|<=|!=|<>|=|>|<|IS NOT NULL|IS NULL|LIKE|ILIKE)\s*(.*)$/i;
    const match = cleanContent.match(opRegex);

    if (match) {
        const field = match[1].trim();
        const op = match[2].trim().toUpperCase();
        const value = match[3].trim();

        return (
            <div className="flex items-center gap-3 flex-wrap min-w-0">
                <span className="text-amber-400 font-bold bg-amber-400/10 px-2 py-0.5 rounded-md text-[13px] border border-amber-400/20 shadow-sm shrink-0">
                    {field}
                </span>
                <span className="text-gray-500 text-[10px] font-bold uppercase shrink-0 opacity-70">
                    {op.toLowerCase()}
                </span>
                {value && (
                    <span className="text-gray-200 font-mono text-sm truncate max-w-[500px] bg-white/2 px-2 py-0.5 rounded border border-white/5">
                        {value}
                    </span>
                )}
            </div>
        );
    }

    return <span className="text-gray-300 font-mono text-sm">{cleanContent}</span>;
};

const ConditionItem: React.FC<ConditionItemProps> = ({ condition, depth = 0 }) => {
    const isGroup = !!condition.children;

    return (
        <div className="flex flex-col gap-3 relative">
            {/* Vertical connector */}
            {condition.operator && (
                <div className="absolute left-[23.5px] -top-6 w-px h-7 bg-white/10 z-0" />
            )}

            <div className="flex items-start gap-4 group relative z-10">
                {/* Operator Label */}
                <div className="w-12 flex justify-end pt-3">
                    {condition.operator ? (
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold uppercase tracking-widest shadow-lg ${condition.operator === 'OR'
                            ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-400'
                            : 'bg-amber-500/20 border-amber-500/40 text-amber-400'
                            }`}>
                            {condition.operator}
                        </span>
                    ) : (
                        depth === 0 && (
                            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-2 opacity-60">
                                WHERE
                            </span>
                        )
                    )}
                </div>

                {/* Content or Children */}
                <div className="flex-1 min-w-0">
                    {isGroup ? (
                        <div className="space-y-5 pt-3 pb-3 relative">
                            {/* Visual background for group */}
                            <div className="absolute inset-0 -left-3 -right-2 bg-white/1.5 rounded-2xl border border-white/5 pointer-events-none shadow-inner" />

                            <div className="pl-2">
                                {condition.children?.map((child, idx) => (
                                    <ConditionItem key={idx} condition={child} depth={depth + 1} />
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="px-5 py-4 rounded-xl bg-[#0a0d12]/40 border border-white/10 text-gray-300 group-hover:border-amber-500/40 group-hover:bg-[#0a0d12]/60 transition-all cursor-default shadow-md overflow-hidden">
                            {itemPrettify(condition.content || '')}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

// ============================================================================
// Trigger Button
// ============================================================================

const TriggerButton: React.FC<{ isOpen: boolean; onClick: () => void }> = ({ isOpen, onClick }) => {
    const [isHovered, setIsHovered] = useState(false);

    return (
        <div
            className="relative"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <div className="bg-[#0a0d12]/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-xl shadow-black/30 p-2 flex items-center gap-2">
                <div className={`px-2 ${isHovered || isOpen ? 'text-amber-400' : 'text-gray-500'}`}>
                    <SearchCode className="w-4 h-4" />
                </div>

                <button
                    onClick={onClick}
                    className={`
                        flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                        transition-all duration-200 border whitespace-nowrap
                        ${isOpen || isHovered
                            ? 'bg-amber-500/20 text-amber-400 border-amber-500/50'
                            : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }
                    `}
                >
                    <span className="font-medium">Inspector</span>
                </button>
            </div>
        </div>
    );
};

// ============================================================================
// Main Component
// ============================================================================

export const SQLFiltersHUD: React.FC<SQLFiltersHUDProps> = ({
    activeRunId,
    isOpen,
    onToggle,
    className = '',
}) => {
    const [isLoading, setIsLoading] = useState(false);
    const [sqlSteps, setSqlSteps] = useState<SQLStepInfo[]>([]);
    const [activeTab, setActiveTab] = useState<number>(0);
    const [error, setError] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<'sql' | 'trace'>('sql');
    const [agentTrace, setAgentTrace] = useState<AgentTraceItem[] | null>(null);
    const [isLoadingTrace, setIsLoadingTrace] = useState(false);

    // Load SQL steps
    useEffect(() => {
        if (!activeRunId || !isOpen) return;

        const loadSQL = async () => {
            setIsLoading(true);
            setError(null);
            try {
                // Fetch all steps to find sql_generation ones
                const steps = await analysisApi.getAgentSteps(activeRunId, {
                    include_raw: true,
                });

                // Filter and process SQL steps
                const sqlStepsProcessed: SQLStepInfo[] = steps
                    .filter(s => s.key.startsWith('sql_generation'))
                    .map((s) => {
                        // Extract SQL from response structure (matches backend)
                        let sql = '';
                        if (s.response && typeof s.response === 'string') {
                            sql = s.response;
                        } else if (s.data && typeof s.data.sql_query === 'string') {
                            sql = s.data.sql_query;
                        } else if (s.response && typeof s.response === 'object') {
                            // @ts-expect-error: dynamic response type structure logic
                            sql = s.response.sql_query || s.response.response || '';
                        }

                        // Determine if it's a relaxation attempt
                        const isRetry = s.key !== 'sql_generation';
                        const attempt = isRetry ? parseInt(s.key.split('_').pop() || '0') + 1 : 1;

                        return {
                            key: s.key,
                            label: isRetry ? `Tentativo ${attempt} (Relaxed)` : 'Tentativo Originale',
                            sql: sql,
                            conditions: parseSqlWhereConditions(sql),
                            isRelaxed: isRetry,
                            attempt
                        };
                    })
                    .sort((a, b) => a.attempt - b.attempt);

                if (sqlStepsProcessed.length === 0) {
                    setError("Nessuna query SQL trovata per questa analisi.");
                }

                setSqlSteps(sqlStepsProcessed);
                // Default to last step (final one)
                setActiveTab(Math.max(0, sqlStepsProcessed.length - 1));

            } catch (err) {
                console.error("Failed to load SQL steps:", err);
                setError("Impossibile caricare i filtri SQL.");
            } finally {
                setIsLoading(false);
            }
        };

        loadSQL();

        // Reset state on open
        if (isOpen) {
            setViewMode('sql');
            setAgentTrace(null);
            setIsLoadingTrace(false);
            setError(null);
        }
    }, [activeRunId, isOpen]);

    // Track viewMode changes to load trace
    useEffect(() => {
        if (!activeRunId || !isOpen || viewMode !== 'trace' || agentTrace) return;

        const loadTrace = async () => {
            setIsLoadingTrace(true);
            try {
                const results = await analysisApi.getResults(activeRunId);
                if (results.agent_trace) {
                    setAgentTrace(results.agent_trace);
                }
            } catch (err) {
                console.error("Failed to load trace:", err);
            } finally {
                setIsLoadingTrace(false);
            }
        };

        loadTrace();
    }, [activeRunId, isOpen, viewMode, agentTrace]);

    const activeStep = sqlSteps[activeTab];

    return (
        <>
            <div className={className}>
                <TriggerButton isOpen={isOpen} onClick={onToggle} />
            </div>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-1000 flex items-center justify-center p-8"
                    >
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                            onClick={onToggle}
                        />

                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                            className={`relative w-full transition-all duration-500 bg-[#0f1218] rounded-3xl border border-white/10 shadow-2xl shadow-black/50 flex flex-col overflow-hidden ${viewMode === 'trace' ? 'max-w-5/6 h-[90vh]' : 'max-w-5xl h-[85vh]'
                                }`}
                        >
                            {/* Ambient Glow */}
                            <div className="absolute -top-40 -left-40 w-80 h-80 bg-amber-500/10 rounded-full blur-[100px] pointer-events-none" />

                            {/* Header */}
                            <div className="relative flex items-center justify-between px-8 py-6 border-b border-white/10 bg-white/2">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-2xl bg-linear-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-amber-500/30">
                                        <SearchCode className="w-6 h-6 text-white" />
                                    </div>
                                    <div>
                                        <h2 className="text-xl font-bold text-white">Logic Inspector</h2>
                                        <p className="text-sm text-gray-500 italic">Analisi granulare dei parametri di ricerca applicati</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setViewMode(viewMode === 'sql' ? 'trace' : 'sql')}
                                    className={`mr-2 p-2 rounded-lg transition-colors flex items-center gap-2 text-xs font-medium border ${viewMode === 'trace'
                                        ? 'bg-amber-500/20 text-amber-400 border-amber-500/50'
                                        : 'bg-white/5 text-gray-400 border-white/10 hover:bg-white/10'
                                        }`}
                                    title={viewMode === 'sql' ? "Visualizza Trace Completo" : "Visualizza SQL"}
                                >
                                    {viewMode === 'sql' ? (
                                        <>
                                            <FileText className="w-4 h-4" />
                                            <span className="hidden sm:inline">Visualizza Trace</span>
                                        </>
                                    ) : (
                                        <>
                                            <Code2 className="w-4 h-4" />
                                            <span className="hidden sm:inline">Torna a SQL</span>
                                        </>
                                    )}
                                </button>
                                <button
                                    onClick={onToggle}
                                    className="p-3 rounded-xl hover:bg-white/5 text-gray-500 hover:text-white transition-colors"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            {/* Content */}
                            {viewMode === 'trace' ? (
                                <div className="flex-1 w-full relative bg-[#0f1218] overflow-auto custom-scrollbar p-8">
                                    {isLoadingTrace ? (
                                        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500">
                                            <Loader2 className="w-10 h-10 animate-spin mb-4 text-amber-500" />
                                            <span>Caricamento trace...</span>
                                        </div>
                                    ) : agentTrace ? (
                                        <AgentTraceViewer trace={agentTrace} />
                                    ) : (
                                        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500">
                                            <AlertCircle className="w-10 h-10 mb-4 text-red-400" />
                                            <span>Trace non disponibile</span>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="relative flex-1 flex flex-col min-h-0 p-8 overflow-y-auto custom-scrollbar">
                                    {isLoading ? (
                                        <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                                            <Loader2 className="w-10 h-10 animate-spin mb-4 text-amber-500" />
                                            <span>Analisi della query...</span>
                                        </div>
                                    ) : error ? (
                                        <div className="flex-1 flex flex-col items-center justify-center text-red-400">
                                            <AlertCircle className="w-12 h-12 mb-4" />
                                            <span>{error}</span>
                                        </div>
                                    ) : (
                                        <div className="space-y-10">

                                            {/* Multi-Execution Tabs */}
                                            {sqlSteps.length > 1 && (
                                                <div className="flex items-center gap-2 overflow-x-auto pb-4 scrollbar-hide border-b border-white/5">
                                                    {sqlSteps.map((step, idx) => (
                                                        <button
                                                            key={step.key}
                                                            onClick={() => setActiveTab(idx)}
                                                            className={`
                                                                flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all
                                                                ${activeTab === idx
                                                                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                                                                    : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
                                                                }
                                                            `}
                                                        >
                                                            {step.isRelaxed && <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />}
                                                            {step.label}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}

                                            {/* Filters Chips */}
                                            {activeStep && (
                                                <div className="space-y-6">
                                                    <div className="flex items-center gap-2 text-[11px] text-gray-400 uppercase tracking-widest font-bold opacity-50">
                                                        <SearchCode className="w-3.5 h-3.5" />
                                                        PARAMETRI SEMANTICI E LOGICI
                                                    </div>

                                                    <div className="flex flex-col gap-5">
                                                        {activeStep.conditions.map((item, i) => (
                                                            <ConditionItem key={i} condition={item} />
                                                        ))}
                                                        {activeStep.conditions.length === 0 && (
                                                            <span className="text-gray-500 italic ml-16 bg-white/5 px-4 py-2 rounded-lg">
                                                                Nessun filtro semantico rilevato (Ricerca globale).
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Raw SQL View */}
                                            {activeStep && (
                                                <div className="space-y-4 pt-10 border-t border-white/5">
                                                    <div className="flex items-center gap-2 text-[11px] text-gray-500 uppercase tracking-widest font-bold opacity-50">
                                                        <Terminal className="w-3.5 h-3.5" />
                                                        CODICE SQL ORIGINALE
                                                    </div>
                                                    <div className="relative rounded-2xl overflow-hidden bg-[#080a0e] border border-white/10 group">
                                                        <pre className="p-6 overflow-x-auto font-mono text-sm text-gray-500 leading-relaxed whitespace-pre-wrap">
                                                            {activeStep.sql}
                                                        </pre>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};
