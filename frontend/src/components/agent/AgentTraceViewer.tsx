
import React, { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ChevronRight,
    ChevronDown,
    Copy,
    Table as TableIcon,
    List,
    FileJson,
    Check,
    Terminal,
    Hash,
    Type,
    Box
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility for tailwind classes
 */
function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

import type { AgentTraceItem } from '../../api/types';

interface AgentTraceViewerProps {
    trace: AgentTraceItem[];
    className?: string;
}

// ----------------------------------------------------------------------------
// Types & Helpers
// ----------------------------------------------------------------------------

type ViewMode = 'tree' | 'table';

const getDataType = (val: any): string => {
    if (val === null) return 'null';
    if (Array.isArray(val)) return 'array';
    return typeof val;
};

const formatPath = (path: string[]) => {
    if (path.length === 0) return 'root';
    return path.map(p => (isNaN(Number(p)) ? p : `[${p}]`)).join('.');
};

const getAgentModeClasses = (mode: string): string => {
    const m = mode.toLowerCase();
    if (m.includes('sql')) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    if (m.includes('filter') || m.includes('discovery')) return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
    if (m.includes('ranking') || m.includes('score')) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (m.includes('extract') || m.includes('parse')) return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    if (m.includes('analys')) return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    if (m.includes('search')) return 'bg-sky-500/20 text-sky-400 border-sky-500/30';
    if (m.includes('refine')) return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
    return 'bg-white/5 text-slate-400 border-white/10';
};

// ----------------------------------------------------------------------------
// Components
// ----------------------------------------------------------------------------

const JsonValue: React.FC<{ value: any; type: string }> = ({ value, type }) => {
    switch (type) {
        case 'string':
            return <span className="text-amber-200/90 break-all">"{value}"</span>;
        case 'number':
            return <span className="text-cyan-400 font-mono">{value}</span>;
        case 'boolean':
            return <span className="text-orange-400 font-bold italic">{String(value)}</span>;
        case 'null':
            return <span className="text-slate-600 italic">null</span>;
        case 'array':
            return (
                <span className="text-slate-500 text-[10px] font-mono">
                    Array({value.length})
                    <span className="ml-2 opacity-30">[...]</span>
                </span>
            );
        case 'object':
            const keys = Object.keys(value);
            return (
                <span className="text-slate-500 text-[10px] font-mono">
                    Object({keys.length})
                    <span className="ml-2 opacity-40 italic">
                        {'{'}{keys.slice(0, 3).join(', ')}{keys.length > 3 ? '...' : ''}{'}'}
                    </span>
                </span>
            );
        default:
            return <span className="text-slate-300">{String(value)}</span>;
    }
};

const JsonNode: React.FC<{
    name: string | number;
    value: any;
    depth: number;
    path: string[];
    expandedPaths: Set<string>;
    togglePath: (path: string) => void;
    onSelect: (path: string[]) => void;
    selectedPath: string;
}> = ({ name, value, depth, path, expandedPaths, togglePath, onSelect, selectedPath }) => {
    // RECURSIVE PARSING: If the value is a string that looks like JSON, try to parse it
    const parsedValue = useMemo(() => {
        if (typeof value === 'string' && (value.startsWith('{') || value.startsWith('['))) {
            try {
                return JSON.parse(value);
            } catch (e) {
                return value;
            }
        }
        return value;
    }, [value]);

    const label = useMemo(() => {
        if (typeof name === 'number' && parsedValue && typeof parsedValue === 'object') {
            return (
                <span className="flex items-center gap-2">
                    <span className="text-slate-600">[{name}]</span>
                    <span className="text-amber-400/90 font-bold px-1.5 py-0.25 rounded bg-amber-400/5 border border-amber-400/10 text-[10px] uppercase tracking-tighter shadow-sm">
                        {parsedValue.agent_name || parsedValue.key || 'Item'}
                    </span>
                </span>
            );
        }
        return name;
    }, [name, parsedValue]);

    const type = getDataType(parsedValue);
    const isExpandable = type === 'object' || type === 'array';
    const pathStr = path.join('.');
    const isExpanded = expandedPaths.has(pathStr);
    const isSelected = selectedPath === pathStr;

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isExpandable) togglePath(pathStr);
        onSelect(path);
    };

    return (
        <div className="flex flex-col">
            <div
                className={cn(
                    "group flex items-center gap-1.5 py-0.5 px-2 rounded-lg cursor-pointer transition-colors border border-transparent",
                    isExpanded ? "bg-white/[0.02]" : "hover:bg-white/[0.04]",
                    isSelected && "bg-cyan-500/10 border-cyan-500/20"
                )}
                onClick={handleClick}
                style={{ paddingLeft: `${depth * 16 + 8}px` }}
            >
                {isExpandable ? (
                    <span className="text-slate-600 group-hover:text-slate-400 transition-colors">
                        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </span>
                ) : (
                    <span className="w-3.5" />
                )}

                <span className="text-sky-400/80 font-mono text-sm group-hover:text-sky-400 transition-colors">
                    {label}:
                </span>

                <div className="flex-1 truncate text-sm">
                    <JsonValue value={parsedValue} type={type} />
                    {typeof value === 'string' && typeof parsedValue === 'object' && (
                        <span className="ml-2 text-[10px] text-cyan-600 font-black uppercase tracking-tighter bg-cyan-500/5 px-1 rounded border border-cyan-500/10 active:scale-95 transition-transform" title="Serialized JSON string auto-parsed">
                            Parsed
                        </span>
                    )}
                </div>

                {isSelected && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(JSON.stringify(parsedValue, null, 2));
                            }}
                            className="p-1 hover:bg-white/10 rounded text-slate-500 hover:text-white transition-colors"
                        >
                            <Copy size={12} />
                        </button>
                    </motion.div>
                )}
            </div>

            {isExpandable && isExpanded && (
                <div className="flex flex-col">
                    {type === 'array' ? (
                        (parsedValue as any[]).map((item, i) => (
                            <JsonNode
                                key={i}
                                name={i}
                                value={item}
                                depth={depth + 1}
                                path={[...path, String(i)]}
                                expandedPaths={expandedPaths}
                                togglePath={togglePath}
                                onSelect={onSelect}
                                selectedPath={selectedPath}
                            />
                        ))
                    ) : (
                        Object.entries(parsedValue).map(([key, val]) => (
                            <JsonNode
                                key={key}
                                name={key}
                                value={val}
                                depth={depth + 1}
                                path={[...path, key]}
                                expandedPaths={expandedPaths}
                                togglePath={togglePath}
                                onSelect={onSelect}
                                selectedPath={selectedPath}
                            />
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

// ----------------------------------------------------------------------------
// Tabular Viewer for Intelligence Traces
// ----------------------------------------------------------------------------

const JsonTable: React.FC<{
    data: AgentTraceItem[];
    onInspect: (path: string[]) => void;
}> = ({ data, onInspect }) => {
    const columns = ['agent_name', 'agent_mode', 'execution_time_ms', 'timestamp'];

    return (
        <div className="w-full overflow-hidden rounded-2xl border border-white/5 bg-[#0a0d12]/40 backdrop-blur-xl shadow-2xl">
            <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-white/[0.02] border-b border-white/5">
                            <th className="px-6 py-4 text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">#</th>
                            {columns.map(col => (
                                <th key={col} className="px-6 py-4 text-[11px] font-black uppercase tracking-[0.2em] text-slate-500 whitespace-nowrap">
                                    {col.replace('_', ' ')}
                                </th>
                            ))}
                            <th className="px-6 py-4 text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">Payload</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 font-mono text-xs">
                        {data.map((item, idx) => (
                            <tr key={idx} className="hover:bg-white/[0.03] transition-colors group">
                                <td className="px-6 py-4 text-slate-700 font-bold">{idx + 1}</td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 group-hover:animate-pulse" />
                                        <span className="text-white/90 font-bold">{item.agent_name}</span>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={cn(
                                        "px-2 py-0.5 rounded-md border text-[10px] font-black uppercase tracking-tighter transition-colors",
                                        getAgentModeClasses(item.agent_mode)
                                    )}>
                                        {item.agent_mode}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={cn(
                                        "font-bold",
                                        item.execution_time_ms > 1000 ? "text-amber-400" : "text-emerald-400"
                                    )}>
                                        {Math.round(item.execution_time_ms)}ms
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-slate-500">
                                    {new Date(item.timestamp).toLocaleTimeString()}
                                </td>
                                <td className="px-6 py-4 max-w-md">
                                    <div className="flex gap-2 items-center">
                                        <button
                                            onClick={() => onInspect([String(idx), 'input'])}
                                            className="bg-blue-500/10 text-blue-400 px-3 py-1 rounded-md text-[10px] uppercase font-black border border-blue-500/20 hover:bg-blue-500/20 active:scale-95 transition-all"
                                        >
                                            Input
                                        </button>
                                        <button
                                            onClick={() => onInspect([String(idx), 'output'])}
                                            className="bg-emerald-500/10 text-emerald-400 px-3 py-1 rounded-md text-[10px] uppercase font-black border border-emerald-500/20 hover:bg-emerald-500/20 active:scale-95 transition-all"
                                        >
                                            Output
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

// ----------------------------------------------------------------------------
// Main Explorer Component
// ----------------------------------------------------------------------------

export const AgentTraceViewer: React.FC<AgentTraceViewerProps> = ({ trace, className = '' }) => {
    const [viewMode, setViewMode] = useState<ViewMode>('tree');
    const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['root']));
    const [selectedPathArr, setSelectedPathArr] = useState<string[]>([]);
    const [isCopied, setIsCopied] = useState(false);

    if (!trace || trace.length === 0) {
        return (
            <div className={`flex flex-col items-center justify-center p-20 text-slate-600 ${className}`}>
                <div className="w-16 h-16 rounded-3xl bg-white/5 flex items-center justify-center mb-6">
                    <Terminal className="w-8 h-8 opacity-20" />
                </div>
                <p className="text-lg font-medium opacity-40">Nessuna traccia disponibile</p>
            </div>
        );
    }

    const togglePath = useCallback((path: string) => {
        setExpandedPaths(prev => {
            const next = new Set(prev);
            if (next.has(path)) next.delete(path);
            else next.add(path);
            return next;
        });
    }, []);

    const handleInspectFromTable = useCallback((path: string[]) => {
        setViewMode('tree');
        setSelectedPathArr(path);
        setExpandedPaths(prev => {
            const next = new Set(prev);
            // In the tree, root is at "", child 0 is at "0", child input is at "0.input"
            let currentPath = '';
            for (const part of path) {
                currentPath = currentPath ? `${currentPath}.${part}` : part;
                next.add(currentPath);
            }
            return next;
        });
    }, []);

    const selectedPath = selectedPathArr.join('.');

    const copyPathToClipboard = () => {
        navigator.clipboard.writeText(formatPath(selectedPathArr));
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    return (
        <div className={cn("flex flex-col gap-4 min-h-[600px]", className)}>
            {/* Toolbar inspired by Discovery */}
            <div className="flex flex-col gap-4 p-4 rounded-2xl bg-[#0f1218] border border-white/10 shadow-2xl relative overflow-hidden group/toolbar">
                <div className="absolute top-0 left-0 w-1 h-full bg-cyan-500/40" />

                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center border border-white/10">
                            <FileJson className="w-5 h-5 text-cyan-400" />
                        </div>
                        <div>
                            <h2 className="text-white font-black text-sm uppercase tracking-widest flex items-center gap-2">
                                Intelligence Discovery
                                <span className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-slate-500 font-mono">v1.2</span>
                            </h2>
                            <p className="text-[10px] text-slate-500 font-mono flex items-center gap-4 mt-0.5">
                                <span className="flex items-center gap-1.5"><Hash size={10} className="text-cyan-600" /> {trace.length} Opérations</span>
                                <span className="flex items-center gap-1.5"><Type size={10} className="text-emerald-600" /> {JSON.stringify(trace).length.toLocaleString()} byte JSON</span>
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 bg-white/5 p-1 rounded-xl border border-white/5">
                        <button
                            onClick={() => setViewMode('tree')}
                            className={cn(
                                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                                viewMode === 'tree' ? "bg-cyan-500 text-black shadow-lg shadow-cyan-500/20" : "text-slate-500 hover:text-white"
                            )}
                        >
                            <List size={14} /> Tree
                        </button>
                        <button
                            onClick={() => setViewMode('table')}
                            className={cn(
                                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                                viewMode === 'table' ? "bg-cyan-500 text-black shadow-lg shadow-cyan-500/20" : "text-slate-500 hover:text-white"
                            )}
                        >
                            <TableIcon size={14} /> Table
                        </button>
                    </div>
                </div>

                {/* Breadcrumbs Path */}
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 px-2 group/path cursor-pointer" onClick={copyPathToClipboard}>
                    <div className="flex items-center gap-2 truncate">
                        <span className="text-slate-700 uppercase tracking-tighter">Path:</span>
                        <span className="text-cyan-500/80 truncate font-bold">
                            {formatPath(selectedPathArr)}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] opacity-0 group-hover/path:opacity-100 transition-opacity">
                        {isCopied ? (
                            <span className="text-emerald-500 flex items-center gap-1 font-bold"><Check size={10} /> Copied!</span>
                        ) : (
                            <span className="text-slate-600 uppercase">Click to copy path</span>
                        )}
                    </div>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 min-h-[500px] relative">
                <AnimatePresence mode="wait">
                    {viewMode === 'tree' ? (
                        <motion.div
                            key="tree"
                            initial={{ opacity: 0, scale: 0.98 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.98 }}
                            className="bg-[#0f1218]/50 border border-white/5 rounded-2xl p-4 overflow-auto custom-scrollbar max-h-[70vh] font-mono"
                        >
                            <JsonNode
                                name="root"
                                value={trace}
                                depth={0}
                                path={[]}
                                expandedPaths={expandedPaths}
                                togglePath={togglePath}
                                onSelect={setSelectedPathArr}
                                selectedPath={selectedPath}
                            />
                        </motion.div>
                    ) : (
                        <motion.div
                            key="table"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                        >
                            <JsonTable data={trace} onInspect={handleInspectFromTable} />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Details Overlay (Optional detail pane like discovery) */}
            {selectedPathArr.length > 0 && (
                <div className="mt-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                        <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center border border-orange-500/20">
                            <Box className="w-4 h-4 text-orange-400" />
                        </div>
                        <div>
                            <div className="text-[10px] text-slate-600 uppercase font-black tracking-widest leading-none">Selected Inspection</div>
                            <div className="text-xs text-white/80 font-mono mt-1 font-bold">
                                {selectedPathArr[selectedPathArr.length - 1]}
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={() => {
                            // Helper function to resolve path deeply considering recursive parsing
                            const resolveDeep = (obj: any, pathArr: string[]): any => {
                                let current = obj;
                                for (const key of pathArr) {
                                    if (typeof current === 'string') {
                                        try { current = JSON.parse(current); } catch { return undefined; }
                                    }
                                    current = current[key];
                                }
                                return current;
                            };
                            const val = resolveDeep(trace, selectedPathArr);
                            navigator.clipboard.writeText(JSON.stringify(val, null, 2));
                            setIsCopied(true);
                            setTimeout(() => setIsCopied(false), 2000);
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-slate-300 hover:text-white hover:bg-white/10 transition-all"
                    >
                        <Copy size={14} /> Copy Value
                    </button>
                </div>
            )}
        </div>
    );
};
