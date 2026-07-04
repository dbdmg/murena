/**
 * LogsPage - Live activity log of everything MURENA executes.
 *
 * Polls /api/v1/logs/stream for in-process events (agents, SQL, services,
 * errors) and lists persisted per-run agent traces from /api/v1/logs/traces.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import { ScrollText, Pause, Play, Trash2, FileJson, AlertTriangle } from 'lucide-react';

interface LogEvent {
    id: number;
    ts: string;
    level: string;
    source: string;
    message: string;
}

interface TraceFile {
    name: string;
    size_bytes: number;
    modified_at: number;
}

const LEVEL_STYLES: Record<string, string> = {
    ERROR: 'text-red-400 bg-red-500/10 border-red-500/20',
    WARNING: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    INFO: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    DEBUG: 'text-gray-400 bg-white/5 border-white/10',
};

export const LogsPage = () => {
    const [events, setEvents] = useState<LogEvent[]>([]);
    const [traces, setTraces] = useState<TraceFile[]>([]);
    const [paused, setPaused] = useState(false);
    const [filter, setFilter] = useState('');
    const [levelFilter, setLevelFilter] = useState<string>('');
    const [selectedTrace, setSelectedTrace] = useState<string | null>(null);
    const [traceContent, setTraceContent] = useState<unknown>(null);
    const lastIdRef = useRef(0);
    const bottomRef = useRef<HTMLDivElement>(null);

    const poll = useCallback(async () => {
        try {
            const { data } = await apiClient.get('/logs/stream', {
                params: { since_id: lastIdRef.current, limit: 500 },
            });
            if (data.events?.length) {
                lastIdRef.current = data.last_id;
                setEvents((prev) => [...prev, ...data.events].slice(-1500));
            }
        } catch {
            /* backend not reachable: keep silent, retry on next tick */
        }
    }, []);

    useEffect(() => {
        if (paused) return;
        poll();
        const id = setInterval(poll, 3000);
        return () => clearInterval(id);
    }, [paused, poll]);

    useEffect(() => {
        apiClient
            .get<TraceFile[]>('/logs/traces')
            .then(({ data }) => setTraces(data))
            .catch(() => setTraces([]));
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [events.length]);

    const openTrace = async (name: string) => {
        setSelectedTrace(name);
        setTraceContent(null);
        try {
            const { data } = await apiClient.get(`/logs/traces/${name}`);
            setTraceContent(data);
        } catch {
            setTraceContent({ error: 'Unable to load trace' });
        }
    };

    const visible = events.filter((e) => {
        if (levelFilter && e.level !== levelFilter) return false;
        if (filter) {
            const q = filter.toLowerCase();
            return (
                e.message.toLowerCase().includes(q) ||
                e.source.toLowerCase().includes(q)
            );
        }
        return true;
    });

    return (
        <div className="h-full flex flex-col p-6 gap-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                        <ScrollText className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                        <h1 className="text-xl font-semibold text-white">Activity log</h1>
                        <p className="text-xs text-gray-500">
                            Everything MURENA executes, live — plus persisted per-run agent traces
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <input
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        placeholder="Filter by text or source…"
                        className="px-3 py-2 text-sm rounded-lg bg-white/5 border border-white/10 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500/50 w-64"
                    />
                    <select
                        value={levelFilter}
                        onChange={(e) => setLevelFilter(e.target.value)}
                        className="px-3 py-2 text-sm rounded-lg bg-white/5 border border-white/10 text-gray-200 focus:outline-none"
                    >
                        <option value="">All levels</option>
                        <option value="INFO">INFO</option>
                        <option value="WARNING">WARNING</option>
                        <option value="ERROR">ERROR</option>
                    </select>
                    <button
                        onClick={() => setPaused((p) => !p)}
                        className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-white hover:bg-white/10"
                        title={paused ? 'Resume live updates' : 'Pause live updates'}
                    >
                        {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={() => setEvents([])}
                        className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-red-400 hover:bg-red-500/10"
                        title="Clear view"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>

            <div className="flex-1 flex gap-4 min-h-0">
                {/* Live stream */}
                <div className="flex-1 flex flex-col rounded-2xl border border-white/10 bg-black/30 backdrop-blur-xl overflow-hidden">
                    <div className="px-4 py-2 border-b border-white/5 text-[11px] uppercase tracking-wider text-gray-500 flex items-center justify-between">
                        <span>Live stream {paused && '· paused'}</span>
                        <span>{visible.length} events</span>
                    </div>
                    <div className="flex-1 overflow-y-auto font-mono text-xs p-3 space-y-0.5">
                        {visible.length === 0 && (
                            <div className="flex items-center gap-2 text-gray-500 p-4">
                                <AlertTriangle className="w-4 h-4" />
                                No events yet — run an analysis to see the pipeline at work.
                            </div>
                        )}
                        {visible.map((e) => (
                            <div key={e.id} className="flex gap-2 items-start hover:bg-white/5 rounded px-2 py-0.5">
                                <span className="text-gray-600 shrink-0">{e.ts.slice(11, 23)}</span>
                                <span
                                    className={`shrink-0 px-1.5 rounded border text-[10px] leading-4 ${
                                        LEVEL_STYLES[e.level] ?? LEVEL_STYLES.DEBUG
                                    }`}
                                >
                                    {e.level}
                                </span>
                                <span className="text-sky-400/80 shrink-0 max-w-[180px] truncate">{e.source}</span>
                                <span className="text-gray-300 break-all">{e.message}</span>
                            </div>
                        ))}
                        <div ref={bottomRef} />
                    </div>
                </div>

                {/* Persisted traces */}
                <div className="w-[340px] flex flex-col rounded-2xl border border-white/10 bg-black/30 backdrop-blur-xl overflow-hidden">
                    <div className="px-4 py-2 border-b border-white/5 text-[11px] uppercase tracking-wider text-gray-500">
                        Agent traces (per run)
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-1">
                        {traces.length === 0 && (
                            <p className="text-xs text-gray-500 p-3">
                                No persisted traces yet. Each analysis run writes a full JSON
                                trace of every agent execution.
                            </p>
                        )}
                        {traces.map((t) => (
                            <button
                                key={t.name}
                                onClick={() => openTrace(t.name)}
                                className={`w-full text-left px-3 py-2 rounded-lg border text-xs transition-colors ${
                                    selectedTrace === t.name
                                        ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                                        : 'border-white/5 bg-white/5 text-gray-300 hover:bg-white/10'
                                }`}
                            >
                                <span className="flex items-center gap-2">
                                    <FileJson className="w-3.5 h-3.5 shrink-0" />
                                    <span className="truncate">{t.name}</span>
                                </span>
                                <span className="text-[10px] text-gray-500">
                                    {(t.size_bytes / 1024).toFixed(1)} KB ·{' '}
                                    {new Date(t.modified_at * 1000).toLocaleString()}
                                </span>
                            </button>
                        ))}
                    </div>
                    {traceContent !== null && (
                        <div className="h-[45%] border-t border-white/10 overflow-y-auto p-3">
                            <pre className="text-[10px] text-gray-300 whitespace-pre-wrap break-all">
                                {JSON.stringify(traceContent, null, 2)}
                            </pre>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
