import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, Code2, Copy, Loader2, X } from 'lucide-react';
import { analysisApi } from '../../api/endpoints/analysis';

interface SQLQueryPanelProps {
    activeRunId: string | null;
    isOpen: boolean;
    onToggle: () => void;
}

interface SQLQueryStep {
    key: string;
    label: string;
    sql: string;
    attempt: number;
}

const extractSql = (step: { response?: unknown; data?: unknown }): string => {
    if (typeof step.response === 'string') return step.response;
    if (step.data && typeof step.data === 'object' && 'sql_query' in step.data) {
        const query = step.data.sql_query;
        if (typeof query === 'string') return query;
    }
    if (step.response && typeof step.response === 'object') {
        const response = step.response as Record<string, unknown>;
        if (typeof response.sql_query === 'string') return response.sql_query;
        if (typeof response.response === 'string') return response.response;
    }
    return '';
};

export const SQLQueryPanel: React.FC<SQLQueryPanelProps> = ({ activeRunId, isOpen, onToggle }) => {
    const [queries, setQueries] = useState<SQLQueryStep[]>([]);
    const [activeQueryIndex, setActiveQueryIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (!activeRunId || !isOpen) return;

        let cancelled = false;
        const loadQueries = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const steps = await analysisApi.getAgentSteps(activeRunId, { include_raw: true });
                const foundQueries = steps
                    .filter(step => step.key.startsWith('sql_generation'))
                    .map(step => {
                        const isRetry = step.key !== 'sql_generation';
                        const attempt = isRetry ? Number.parseInt(step.key.split('_').at(-1) || '0', 10) + 1 : 1;
                        return {
                            key: step.key,
                            label: isRetry ? `Query ${attempt} · relaxed` : 'Initial query',
                            sql: extractSql(step),
                            attempt,
                        };
                    })
                    .filter(step => step.sql.trim().length > 0)
                    .sort((a, b) => a.attempt - b.attempt);

                if (cancelled) return;
                setQueries(foundQueries);
                setActiveQueryIndex(Math.max(0, foundQueries.length - 1));
                if (foundQueries.length === 0) setError('No SQL query was found for this analysis.');
            } catch (loadError) {
                console.error('Failed to load SQL query:', loadError);
                if (!cancelled) setError('Unable to load the SQL query.');
            } finally {
                if (!cancelled) setIsLoading(false);
            }
        };

        loadQueries();
        return () => { cancelled = true; };
    }, [activeRunId, isOpen]);

    const activeQuery = queries[activeQueryIndex];

    const copyQuery = async () => {
        if (!activeQuery) return;
        try {
            await navigator.clipboard.writeText(activeQuery.sql);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
        } catch {
            setError('Unable to copy the query to the clipboard.');
        }
    };

    return (
        <>
            <button
                onClick={onToggle}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs font-medium border backdrop-blur-xl transition-colors shadow-xl shadow-black/30 ${isOpen
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/50'
                    : 'bg-[#0a0d12]/90 text-gray-300 border-white/10 hover:border-amber-500/40 hover:text-white'
                }`}
                aria-label="Open SQL query"
            >
                <Code2 className="w-4 h-4" />
                <span>SQL Query</span>
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-1000 flex items-center justify-center p-4 sm:p-8"
                    >
                        <button
                            className="absolute inset-0 bg-black/75 backdrop-blur-sm"
                            onClick={onToggle}
                            aria-label="Close SQL query"
                        />
                        <motion.section
                            initial={{ opacity: 0, y: 16, scale: 0.98 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: 16, scale: 0.98 }}
                            className="relative flex max-h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0f1218] shadow-2xl"
                            aria-labelledby="sql-query-title"
                        >
                            <header className="flex items-center justify-between border-b border-white/10 px-5 py-4 sm:px-7">
                                <div className="flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 text-amber-400">
                                        <Code2 className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <h2 id="sql-query-title" className="font-semibold text-white">SQL Query</h2>
                                        <p className="text-xs text-gray-500">Query used for this analysis</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    {activeQuery && (
                                        <button
                                            onClick={copyQuery}
                                            className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-gray-300 transition-colors hover:bg-white/5 hover:text-white"
                                        >
                                            {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                                            <span>{copied ? 'Copied' : 'Copy'}</span>
                                        </button>
                                    )}
                                    <button onClick={onToggle} className="rounded-lg p-2 text-gray-500 hover:bg-white/5 hover:text-white" aria-label="Close">
                                        <X className="h-5 w-5" />
                                    </button>
                                </div>
                            </header>

                            {queries.length > 1 && (
                                <div className="flex gap-2 overflow-x-auto border-b border-white/5 px-5 py-3 sm:px-7">
                                    {queries.map((query, index) => (
                                        <button
                                            key={query.key}
                                            onClick={() => setActiveQueryIndex(index)}
                                            className={`whitespace-nowrap rounded-lg border px-3 py-2 text-xs transition-colors ${activeQueryIndex === index
                                                ? 'border-amber-500/40 bg-amber-500/15 text-amber-300'
                                                : 'border-white/10 bg-white/[0.03] text-gray-400 hover:bg-white/[0.06]'
                                            }`}
                                        >
                                            {query.label}
                                        </button>
                                    ))}
                                </div>
                            )}

                            <div className="min-h-48 flex-1 overflow-auto p-5 sm:p-7">
                                {isLoading ? (
                                    <div className="flex h-48 items-center justify-center gap-3 text-gray-400">
                                        <Loader2 className="h-5 w-5 animate-spin text-amber-400" />
                                        Loading query…
                                    </div>
                                ) : error ? (
                                    <div className="flex h-48 items-center justify-center text-sm text-amber-300">{error}</div>
                                ) : activeQuery ? (
                                    <pre className="min-h-full overflow-x-auto rounded-xl border border-white/10 bg-[#080a0e] p-5 font-mono text-sm leading-relaxed text-gray-200 whitespace-pre-wrap">{activeQuery.sql}</pre>
                                ) : null}
                            </div>
                        </motion.section>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};
