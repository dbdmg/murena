
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Clock,
    AlertCircle,
    Database,
    BrainCircuit,
    MapPin,
    Zap,
    Layers,
    ListFilter,
    ChevronDown,
    ChevronRight,
    Terminal,
    Copy,
    Check,
    Cpu,
    ArrowDownRight,
    Command,
    SearchCode
} from 'lucide-react';
import type { AgentTraceItem } from '../../api/types';
import { QueryTooltip } from '../common/QueryTooltip';
import { FeedbackPanel } from './FeedbackPanel';
import { feedbackApi } from '../../api/endpoints/feedback';
import type { AgentFeedbackResponse } from '../../api/types';
import { useEffect } from 'react';

interface AgentTraceViewerProps {
    trace: AgentTraceItem[];
    runId?: string;
    initialQuery?: string;
    className?: string;
}

// ----------------------------------------------------------------------------
// Syntax Highlighting Utilities
// ----------------------------------------------------------------------------

const SemanticTextRenderer = ({ text, isNested = false }: { text: string; isNested?: boolean }) => {
    // Try to find JSON blocks within the text and format them
    const renderContent = (content: string) => {
        const lines = content.split('\n');
        const results: React.ReactNode[] = [];
        let currentJsonBlock: string[] = [];
        let isInsideJson = false;
        let braceBalance = 0;

        lines.forEach((line, i) => {
            const trimmed = line.trim();

            // Heuristic for starting a JSON block
            if (!isInsideJson && (trimmed.startsWith('{') || trimmed.startsWith('['))) {
                isInsideJson = true;
                braceBalance = 0;
            }

            if (isInsideJson) {
                currentJsonBlock.push(line);

                // Basic brace counting to find end of JSON block
                const opens = (line.match(/\{|\[/g) || []).length;
                const closes = (line.match(/\}|\]/g) || []).length;
                braceBalance += opens - closes;

                if (braceBalance <= 0 && currentJsonBlock.length > 0) {
                    const jsonStr = currentJsonBlock.join('\n').trim();
                    try {
                        // Validate and render
                        const parsed = JSON.parse(jsonStr.replace(/,$/, ''));
                        results.push(
                            <div key={`json-${i}`} className="my-8 bg-[#0a0d12]/80 border border-white/10 rounded-2xl p-6 font-mono text-[14px] overflow-x-auto shadow-2xl relative group/json-block">
                                <div className="absolute top-3 right-4 text-[14px] font-black text-white/5 group-hover/json-block:text-white/20 transition-colors uppercase tracking-[0.2em] pointer-events-none">
                                    Structured Data
                                </div>
                                <SyntaxHighlightedJSON data={parsed} />
                            </div>
                        );
                    } catch {
                        // Not valid JSON, revert to text rendering
                        results.push(<div key={`text-block-${i}`} className="whitespace-pre-wrap text-cyan-400/80 mb-1 pl-1">{jsonStr}</div>);
                    }
                    currentJsonBlock = [];
                    isInsideJson = false;
                    braceBalance = 0;
                }
                return;
            }

            // Standard semantic rendering
            if (trimmed === ',' || trimmed === '""') return;

            if (trimmed.startsWith('#')) {
                const level = (trimmed.match(/^#+/) || ['#'])[0].length;
                results.push(
                    <div key={i} className={`
                        text-amber-500 font-bold mt-8 mb-3 border-b border-amber-500/10 pb-1.5
                        ${level === 1 ? 'text-[14px] tracking-wider uppercase' : 'text-[14px]'}
                    `}>
                        {trimmed}
                    </div>
                );
                return;
            }

            if (trimmed.startsWith('[') && trimmed.includes(']')) {
                results.push(
                    <div key={i} className="text-indigo-400 font-black mt-10 mb-6 opacity-90 select-none tracking-[0.3em] uppercase text-[14px] flex items-center gap-4">
                        <span className="h-px w-12 bg-indigo-500/40" />
                        {trimmed}
                        <span className="h-px flex-1 bg-indigo-500/10" />
                    </div>
                );
                return;
            }

            if (trimmed.startsWith('- ') || trimmed.match(/^\d+\./)) {
                results.push(
                    <div key={i} className="flex gap-4 pl-3 py-1.5 group/line">
                        <span className="text-slate-600 group-hover/line:text-amber-500/60 transition-colors shrink-0 font-mono text-[14px] mt-0.5">
                            {trimmed.startsWith('-') ? '•' : trimmed.split('.')[0] + '.'}
                        </span>
                        <span className="text-cyan-400/90 italic leading-relaxed text-[14px]">
                            {trimmed.replace(/^- |\d+\. /, '')}
                        </span>
                    </div>
                );
                return;
            }

            if (line.includes('**')) {
                const parts = line.split(/(\*\*.*?\*\*)/);
                results.push(
                    <div key={i} className="text-cyan-400/80 mb-1.5 leading-relaxed text-[14px]">
                        {parts.map((part, pi) =>
                            part.startsWith('**') && part.endsWith('**')
                                ? <strong key={pi} className="text-amber-400/90 font-bold decoration-amber-500/20 underline underline-offset-4">{part.slice(2, -2)}</strong>
                                : part
                        )}
                    </div>
                );
                return;
            }

            if (!trimmed) {
                results.push(<div key={i} className="h-3" />);
                return;
            }

            results.push(<div key={i} className="text-cyan-400/70 mb-1.5 pl-1 leading-relaxed text-[14px]">{line}</div>);
        });

        return results;
    };

    return (
        <div className={`leading-relaxed ${isNested ? 'pl-6 border-l border-white/5 my-4' : ''}`}>
            {renderContent(text)}
        </div>
    );
};

const SyntaxHighlightedJSON = ({ data }: { data: any }) => {
    const renderValue = (val: any, isSemanticCandidate = true): React.ReactNode => {
        if (val === null) return <span className="text-slate-500 italic">null</span>;
        if (typeof val === 'number') return <span className="text-emerald-400 font-medium">{val}</span>;
        if (typeof val === 'boolean') return <span className="text-rose-400 font-bold lowercase">{String(val)}</span>;

        if (typeof val === 'string') {
            if (val.match(/^\d{4}-\d{2}-\d{2}T/)) {
                return <span className="text-purple-300">"{val}"</span>;
            }

            if (isSemanticCandidate && (val.includes('\n') || val.length > 100 || val.includes('#'))) {
                return <SemanticTextRenderer text={val} isNested />;
            }

            return <span className="text-amber-200/80 font-medium transition-colors hover:text-amber-200 text-[14px]">"{val}"</span>;
        }

        if (Array.isArray(val)) {
            if (val.length === 0) return <span className="text-slate-500">[]</span>;

            // Handle semantic candidate: Join string arrays into a single doc
            const stringsOnly = val.every(i => typeof i === 'string');
            if (isSemanticCandidate && stringsOnly && val.length > 2) {
                return <SemanticTextRenderer text={val.join('\n')} isNested />;
            }

            return (
                <div className="pl-6 border-l border-white/5 my-1.5 space-y-1">
                    <span className="text-slate-600 font-mono text-[14px] opacity-50">[</span>
                    {val.map((item, i) => (
                        <div key={i} className="flex group/array-item">
                            <div className="flex-1">{renderValue(item, false)}</div>
                            {i < val.length - 1 && <span className="text-slate-700 font-mono ml-1 opacity-40 text-[14px]">,</span>}
                        </div>
                    ))}
                    <span className="text-slate-600 font-mono text-[14px] opacity-50">]</span>
                </div>
            );
        }

        if (typeof val === 'object') {
            const keys = Object.keys(val);
            if (keys.length === 0) return <span className="text-slate-500">{ }</span>;

            if (keys.includes('system') && keys.includes('user')) {
                return (
                    <div className="space-y-8 my-4">
                        <div className="border border-white/5 rounded-3xl overflow-hidden bg-white/5 shadow-2xl">
                            <div className="px-5 py-2.5 bg-indigo-500/10 text-[14px] font-black text-indigo-400 uppercase tracking-widest border-b border-indigo-500/10 flex items-center justify-between">
                                <span>System Instruction</span>
                                <div className="flex gap-1">
                                    <div className="w-1 h-1 rounded-full bg-indigo-500/40" />
                                    <div className="w-1 h-1 rounded-full bg-indigo-500/20" />
                                </div>
                            </div>
                            <div className="p-8"><SemanticTextRenderer text={String(val.system)} /></div>
                        </div>
                        <div className="border border-white/5 rounded-3xl overflow-hidden shadow-2xl">
                            <div className="px-5 py-2.5 bg-cyan-500/5 text-[14px] font-black text-cyan-400 uppercase tracking-widest border-b border-white/5 flex items-center justify-between">
                                <span>User Message</span>
                                <div className="flex gap-1">
                                    <div className="w-1 h-1 rounded-full bg-cyan-500/40" />
                                    <div className="w-1 h-1 rounded-full bg-cyan-500/20" />
                                </div>
                            </div>
                            <div className="p-8"><SemanticTextRenderer text={String(val.user)} /></div>
                        </div>
                    </div>
                );
            }

            return (
                <div className="pl-6 border-l border-white/5 my-1.5 space-y-1">
                    {keys.map((key) => {
                        const isPrimitive = val[key] === null || (typeof val[key] !== 'object');
                        return (
                            <div key={key} className={`group/json-item flex ${isPrimitive ? 'items-baseline gap-2.5' : 'flex-col'}`}>
                                <span className="text-sky-300/60 font-mono text-[14px] select-none group-hover/json-item:text-sky-300 transition-colors shrink-0">
                                    "{key}":
                                </span>
                                <div className={isPrimitive ? '' : 'pl-4'}>
                                    {renderValue(val[key], false)}
                                </div>
                            </div>
                        );
                    })}
                </div>
            );
        }

        return <span>{String(val)}</span>;
    };

    return <div className="space-y-1">{renderValue(data)}</div>;
};

// ----------------------------------------------------------------------------
// Sub-Components
// ----------------------------------------------------------------------------

const JSONViewer = ({ data, label, defaultExpanded = false }: { data: unknown; label?: string; defaultExpanded?: boolean }) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const [copied, setCopied] = useState(false);

    if (data === null || data === undefined) return null;

    // Parse strings if they look like JSON
    let parsedData = data;
    if (typeof data === 'string') {
        const trimmed = data.trim();
        if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
            try {
                parsedData = JSON.parse(trimmed);
            } catch { /* stay as string */ }
        }
    }

    const handleCopy = (e: React.MouseEvent) => {
        e.stopPropagation();
        navigator.clipboard.writeText(JSON.stringify(parsedData, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const isComplex = typeof parsedData === 'object' && parsedData !== null;

    return (
        <div className="group/viewer flex flex-col h-full">
            {label && (
                <div
                    className="flex items-center justify-between mb-2 group cursor-pointer select-none"
                    onClick={() => setIsExpanded(!isExpanded)}
                >
                    <div className="flex items-center gap-2">
                        <div className={`w-1 h-3 rounded-full transition-colors ${isExpanded ? 'bg-amber-500' : 'bg-white/10'}`} />
                        <span className={`text-[14px] font-bold uppercase tracking-widest transition-colors ${isExpanded ? 'text-amber-400' : 'text-slate-500'}`}>
                            {label}
                        </span>
                    </div>

                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                            onClick={handleCopy}
                            className="p-1 hover:bg-white/10 rounded transition-colors text-slate-500 hover:text-white"
                            title="Copia dati"
                        >
                            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        </button>
                        {isComplex && (
                            <div className="text-slate-500">
                                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                            </div>
                        )}
                    </div>
                </div>
            )}

            <div className={`
                flex-1 font-mono text-[14px] rounded-xl transition-all duration-300 overflow-hidden border
                ${isExpanded
                    ? 'bg-[#0a0d12] border-white/10 shadow-inner'
                    : 'bg-[#0a0d12]/40 border-white/5 cursor-pointer hover:bg-[#0a0d12]/80 hover:border-white/10'}
            `}
                onClick={() => !isExpanded && setIsExpanded(true)}
            >
                {isExpanded ? (
                    <div className="p-5 overflow-x-auto custom-scrollbar-thin max-h-[600px]">
                        <SyntaxHighlightedJSON data={parsedData} />
                    </div>
                ) : (
                    <div className="p-4 flex items-center justify-between gap-4 text-slate-500 italic truncate">
                        <div className="flex-1 truncate">
                            {isComplex
                                ? Array.isArray(parsedData)
                                    ? `Array(${parsedData.length}) [ ${JSON.stringify(parsedData).substring(0, 40)}... ]`
                                    : `Object { ${Object.keys(parsedData).join(', ')} }`
                                : String(parsedData).substring(0, 80) + '...'}
                        </div>
                        <span className="text-[14px] font-bold uppercase tracking-tighter shrink-0 opacity-50 group-hover/viewer:opacity-100 transition-opacity">
                            ESPANDI
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};

// ----------------------------------------------------------------------------
// Main Components
// ----------------------------------------------------------------------------

export const AgentTraceViewer: React.FC<AgentTraceViewerProps> = ({ trace, runId, initialQuery, className = '' }) => {
    const [feedbacks, setFeedbacks] = useState<AgentFeedbackResponse[]>([]);

    useEffect(() => {
        if (!runId) return;

        const loadFeedback = async () => {
            try {
                const data = await feedbackApi.getAgentFeedback(runId);
                setFeedbacks(data);
            } catch (err) {
                console.error("Failed to load feedback:", err);
            }
        };

        loadFeedback();
    }, [runId]);

    if (!trace || trace.length === 0) {
        return (
            <div className={`flex flex-col items-center justify-center p-20 text-slate-600 ${className}`}>
                <div className="w-16 h-16 rounded-3xl bg-white/5 flex items-center justify-center mb-6">
                    <Terminal className="w-8 h-8 opacity-20" />
                </div>
                <p className="text-lg font-medium opacity-40">Nessuna traccia disponibile</p>
                <p className="text-sm opacity-25 mt-2 transition-all">Le analisi precedenti all'aggiornamento potrebbero non includere i dati del trace.</p>
            </div>
        );
    }

    // Grouping Logic
    const groups = [
        {
            id: 'ranking',
            title: 'Ranking & Extraction Agent',
            icon: <Zap className="w-4 h-4" />,
            agents: [
                'sql-agent',
                'typology-extractor',
                'location-extraction-agent',
                'ape-agent',
                'poi-agent',
                'ranking-agent'
            ]
        },
        {
            id: 'evaluation',
            title: 'Evaluation Agent',
            icon: <Cpu className="w-4 h-4" />,
            agents: ['evaluation-agent']
        }
    ];

    const sortedTrace = [...trace].sort((a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const groupedTrace = groups.map(group => ({
        ...group,
        items: sortedTrace.filter(item => group.agents.includes(item.agent_name.toLowerCase()))
    })).filter(group => group.items.length > 0);

    // Any items not in defined groups
    const otherItems = sortedTrace.filter(item =>
        !groups.some(g => g.agents.includes(item.agent_name.toLowerCase()))
    );

    if (otherItems.length > 0) {
        groupedTrace.push({
            id: 'others',
            title: 'Other Operations',
            icon: <Terminal className="w-4 h-4" />,
            agents: [],
            items: otherItems
        });
    }

    return (
        <div className={`relative flex flex-col gap-8 ${className}`}>
            {/* Sticky Query Header */}
            {initialQuery && (
                <div className="sticky top-0 z-100 -mx-8 pl-[39px] pr-8 py-4 bg-[#0f1218] border-b border-white/10 shadow-xl shadow-black/40 flex items-center gap-6 group/sticky-header">
                    <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center border border-amber-500/20 shrink-0">
                        <SearchCode className="w-4 h-4 text-amber-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="text-[10px] font-black text-amber-500/40 uppercase tracking-widest mb-0.5">Contesto Ricerca</div>
                        <QueryTooltip text={initialQuery}>
                            <div className="text-white/80 text-[14px] font-medium truncate italic group-hover/sticky-header:text-white transition-colors cursor-help">
                                "{initialQuery.length > 200 ? initialQuery.substring(0, 200) + '...' : initialQuery}"
                            </div>
                        </QueryTooltip>
                    </div>
                    <div className="flex items-center gap-2 opacity-30 group-hover/sticky-header:opacity-100 transition-opacity">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Active Context</span>
                    </div>
                    {/* Global Feedback */}
                    {runId && (
                        <FeedbackPanel
                            runId={runId}
                            variant="compact"
                            existingFeedback={feedbacks.find(f => !f.agent_name)}
                        />
                    )}
                </div>
            )}

            {/* Context Header */}
            <div className="flex items-center justify-between pb-6 border-b border-white/5">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                        <Command className="w-5 h-5 text-amber-500" />
                    </div>
                    <div>
                        <div className="text-xs font-bold text-amber-500/50 uppercase tracking-[0.2em]">Live Execution Flow</div>
                        <div className="text-white/60 text-[10px] font-mono mt-0.5">Pipeline: Multi-Agent Real Estate Analysis</div>
                    </div>
                </div>

                <div className="flex items-center gap-8 text-[14px] font-mono text-slate-500 uppercase tracking-widest">
                    <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                        Status: Optimal
                    </div>
                    <div className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg">
                        {trace.length} Operazioni
                    </div>
                </div>
            </div>

            <div className="relative">
                {/* Vertical Timeline Track */}
                <div className="absolute top-0 bottom-0 left-[23px] w-px bg-linear-to-b from-amber-500/20 via-white/5 to-transparent" />

                <div className="space-y-6">
                    {groupedTrace.map((group) => (
                        <TraceGroup
                            key={group.id}
                            title={group.title}
                            icon={group.icon}
                            items={group.items}
                            runId={runId}
                            feedbacks={feedbacks}
                        />
                    ))}
                </div>
            </div>

            <div className="pl-14 py-8 flex flex-col gap-2">
                <div className="h-px w-12 bg-white/5" />
                <span className="text-[10px] text-slate-700 font-mono uppercase tracking-[0.3em]">End of Execution Chain</span>
            </div>
        </div>
    );
};

const TraceGroup = ({ title, icon, items, runId, feedbacks }: { title: string; icon: React.ReactNode; items: AgentTraceItem[]; runId?: string; feedbacks: AgentFeedbackResponse[] }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <div className="space-y-4">
            <div
                className="flex items-center gap-4 cursor-pointer select-none group/group-header"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="z-10 w-12 flex justify-center">
                    <div className={`
                       w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300
                       ${isExpanded ? 'bg-amber-500/10 text-amber-500' : 'bg-white/5 text-slate-500 group-hover/group-header:text-white'}
                   `}>
                        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </div>
                </div>

                <div className="flex-1 flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/5 group-hover/group-header:border-white/10 transition-colors">
                    <span className="text-amber-500 opacity-70">{icon}</span>
                    <span className="text-[14px] font-bold uppercase tracking-widest text-slate-400 group-hover/group-header:text-slate-200">
                        {title}
                    </span>
                    <span className="text-[14px] px-1.5 py-0.5 rounded-md bg-white/5 text-slate-500 font-mono">
                        {items.length}
                    </span>
                </div>
            </div>

            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden space-y-4"
                    >
                        {items.map((item, idx) => (
                            <TraceItemCard
                                key={`${item.agent_name}-${item.timestamp}-${idx}`}
                                item={item}
                                runId={runId}
                                existingFeedback={feedbacks.find(f => f.agent_name === item.agent_name)}
                            />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const TraceItemCard = ({ item, runId, existingFeedback }: { item: AgentTraceItem; runId?: string; existingFeedback?: AgentFeedbackResponse }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    const duration = item.execution_time_ms < 1
        ? '< 1ms'
        : `${Math.round(item.execution_time_ms)}ms`;

    const time = new Date(item.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    const getAgentIcon = (name: string) => {
        const ln = name.toLowerCase();
        if (ln.includes('sql')) return <Database />;
        if (ln.includes('typology')) return <Layers />;
        if (ln.includes('location')) return <MapPin />;
        if (ln.includes('ape')) return <Zap />;
        if (ln.includes('poi')) return <ListFilter />;
        if (ln.includes('evaluation')) return <Cpu />;
        return <BrainCircuit />;
    };

    return (
        <div className="relative pl-14">
            {/* Timeline Icon */}
            <div
                className={`
                    absolute left-0 top-2 w-12 h-12 rounded-2xl border flex items-center justify-center transition-all duration-500 cursor-pointer z-10
                    ${isExpanded
                        ? 'bg-amber-500 border-amber-400 shadow-[0_0_20px_rgba(251,191,36,0.2)] text-black scale-110'
                        : 'bg-[#0f1218] border-white/10 text-slate-500 hover:border-white/30 hover:text-white'}
                `}
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="w-5 h-5">
                    {getAgentIcon(item.agent_name)}
                </div>
            </div>

            {/* Card Body */}
            <motion.div
                layout
                className={`
                    group relative transition-all duration-500 rounded-3xl border
                    ${isExpanded
                        ? 'bg-white/3 border-white/10 p-8 shadow-2xl'
                        : 'bg-white/1 border-transparent p-4 hover:bg-white/3 active:scale-[0.99] cursor-pointer'}
                `}
                onClick={() => !isExpanded && setIsExpanded(true)}
            >
                {/* Visual Accent */}
                {isExpanded && (
                    <div className="absolute -top-10 -right-10 w-40 h-40 bg-amber-500/5 blur-[80px] pointer-events-none rounded-full" />
                )}

                <div className="flex flex-wrap items-center justify-between gap-6 pb-2">
                    <div className="flex items-center gap-4">
                        <div className="flex flex-col">
                            <span className={`font-bold transition-colors ${isExpanded ? 'text-white text-lg' : 'text-slate-200 text-sm'}`}>
                                {item.agent_name}
                            </span>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-[14px] px-2 py-0.5 rounded-full border border-white/5 bg-white/5 text-slate-500 uppercase tracking-widest font-black">
                                    {item.agent_mode}
                                </span>
                                {item.batch_id && (
                                    <span className="text-[14px] text-amber-500/80 font-mono flex items-center gap-1">
                                        <ArrowDownRight className="w-3 h-3" /> BATCH {item.batch_id}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-6">
                        <div className="flex flex-col items-end gap-1">
                            <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
                                <Clock className="w-3 h-3 opacity-50" />
                                {duration}
                            </div>
                            <span className="text-[10px] text-slate-600 font-mono uppercase tracking-tighter opacity-50">{time}</span>
                        </div>

                        {/* Per-Agent Feedback */}
                        {runId && (
                            <div onClick={(e) => e.stopPropagation()} className="ml-2">
                                <FeedbackPanel
                                    runId={runId}
                                    agentName={item.agent_name}
                                    variant="compact"
                                    existingFeedback={existingFeedback}
                                />
                            </div>
                        )}

                        {!isExpanded && (
                            <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors">
                                <ChevronRight className="w-4 h-4 text-slate-600" />
                            </div>
                        )}
                        {isExpanded && (
                            <button
                                onClick={(e) => { e.stopPropagation(); setIsExpanded(false); }}
                                className="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
                            >
                                <X className="w-4 h-4 text-slate-400" />
                            </button>
                        )}
                    </div>
                </div>

                <AnimatePresence>
                    {isExpanded && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 10 }}
                            className="mt-8 space-y-6"
                        >
                            {/* Detailed Grid */}
                            <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-8">
                                <div className="space-y-6">
                                    <JSONViewer data={item.input} label="Query & Context (Input)" defaultExpanded />

                                    {item.notes && (
                                        <div className="p-4 bg-amber-500/5 border border-amber-500/20 rounded-2xl text-amber-200/70 text-[14px] leading-relaxed relative overflow-hidden">
                                            <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 blur-3xl rounded-full" />
                                            <div className="relative flex gap-3">
                                                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                                                <div>
                                                    <span className="font-bold text-amber-400 tracking-wider uppercase text-[14px] block mb-1">Agent Notes</span>
                                                    {item.notes}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <div className="space-y-6">
                                    <JSONViewer data={item.output} label="Reasoning Results (Output)" defaultExpanded />
                                    {Boolean(item.output_structure) && (
                                        <JSONViewer data={item.output_structure} label="Structured Data / Internal Stats" />
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
};

const X = ({ className }: { className?: string }) => (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
);
