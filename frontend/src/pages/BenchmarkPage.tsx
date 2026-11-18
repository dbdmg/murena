import { useMemo, useState, type ReactNode } from 'react';

type JsonObject = Record<string, unknown>;
type BenchmarkRun = JsonObject & {
    run_id?: string;
    condition?: string;
    model?: string;
    unit_id?: string;
    scenario_id?: string;
    base_case_id?: string;
    status?: string;
    started_at?: string;
    repeat?: number;
    attempt?: number;
    duration_seconds?: number | null;
    clarification_seconds?: number | null;
    analysis_seconds?: number | null;
    results_count?: number | null;
    submitted_query?: string | null;
    refined_query?: string | null;
    final_sql?: string | null;
    sql_agent_sql?: string | null;
    error?: string | null;
    clarification_status?: string | null;
    initial_missing?: unknown;
    expected_initial_missing?: unknown;
    detection?: unknown;
    mapping_accuracy?: number | null;
    turns?: number;
    turn_targets?: unknown;
    top?: unknown;
};

function readObject(source: string): JsonObject {
    const parsed: unknown = JSON.parse(source);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as JsonObject : {};
}

function readRuns(source: string): BenchmarkRun[] {
    return source.split(/\r?\n/).flatMap((line) => {
        if (!line.trim()) return [];
        try {
            return [readObject(line) as BenchmarkRun];
        } catch {
            // The runner may be appending a line while Vite reads the JSONL.
            return [];
        }
    });
}

const manifest = readObject(__BENCHMARK_MANIFEST__);
const runs = readRuns(__BENCHMARK_RUNS__);
const scenarioFile = typeof manifest.scenario_file === 'string'
    ? manifest.scenario_file.replaceAll('\\', '/').split('/').pop()?.replace(/\.(json|ya?ml)$/i, '')
    : undefined;
const benchmarkLabel = [scenarioFile || 'Benchmark',
    typeof manifest.sample_seed === 'number' ? `seed ${manifest.sample_seed}` : undefined,
].filter(Boolean).join(' · ');
const formatDuration = (seconds: unknown) => typeof seconds === 'number' ? `${seconds.toFixed(1)} s` : '—';
const display = (value: unknown) => value === null || value === undefined || value === '' ? '—' : String(value);

function plannedRuns(): number | null {
    const variants = manifest.enabled_variant_ids;
    const scenarios = manifest.enabled_scenario_ids;
    const conditions = manifest.conditions;
    if (!Array.isArray(variants) || !Array.isArray(scenarios) || !Array.isArray(conditions)) return null;

    const ordinaryVariants = variants.filter((variant: unknown) => typeof variant === 'string' && !variant.endsWith('_k0')).length;
    const repeat = Number(manifest.repeat_default) || 1;
    const oracleRepeat = Number(manifest.oracle_repeat) || repeat;
    let planned = 0;
    if (conditions.includes('refined')) planned += variants.length * repeat;
    if (conditions.includes('one_shot')) planned += ordinaryVariants * repeat;
    if (conditions.includes('oracle')) planned += scenarios.length * oracleRepeat;
    return planned || null;
}

function StatusBadge({ status }: { status: unknown }) {
    const normalized = String(status ?? 'unknown').toLowerCase();
    const style = normalized === 'completed'
        ? 'bg-emerald-500/15 text-emerald-300'
        : normalized === 'error'
            ? 'bg-red-500/15 text-red-300'
            : 'bg-amber-500/15 text-amber-200';
    return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>{normalized}</span>;
}

function Detail({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section className="rounded-xl border border-white/10 bg-black/15 p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">{title}</h3>
            <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-200">{children || '—'}</div>
        </section>
    );
}

export function BenchmarkPage() {
    const [condition, setCondition] = useState('all');
    const [scenario, setScenario] = useState('all');
    const [status, setStatus] = useState('all');
    const [search, setSearch] = useState('');
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const conditions: string[] = Array.isArray(manifest.conditions) ? manifest.conditions as string[] : [...new Set(runs.map(run => String(run.condition ?? 'unknown')))];
    const scenarios: string[] = Array.isArray(manifest.enabled_scenario_ids)
        ? manifest.enabled_scenario_ids as string[]
        : [...new Set(runs.map(run => String(run.base_case_id ?? 'unknown')))].sort();

    const filteredRuns = useMemo(() => {
        const needle = search.trim().toLowerCase();
        return runs.filter((run) => {
            if (condition !== 'all' && run.condition !== condition) return false;
            if (scenario !== 'all' && run.base_case_id !== scenario) return false;
            if (status !== 'all' && run.status !== status) return false;
            if (needle && ![run.run_id, run.unit_id, run.scenario_id, run.error, run.submitted_query, run.final_sql]
                .some(value => String(value ?? '').toLowerCase().includes(needle))) return false;
            return true;
        }).sort((a, b) => String(b.started_at ?? '').localeCompare(String(a.started_at ?? '')));
    }, [condition, scenario, status, search]);

    const counts = useMemo(() => ({
        completed: runs.filter(run => run.status === 'completed').length,
        errors: runs.filter(run => run.status === 'error').length,
        total: runs.length,
    }), []);
    const selected = filteredRuns.find(run => run.run_id === selectedId) ?? filteredRuns[0] ?? null;
    const llm = manifest.llm && typeof manifest.llm === 'object' ? manifest.llm as JsonObject : {};
    const plan = plannedRuns();
    const progress = plan ? Math.min(100, Math.round(counts.total / plan * 100)) : 0;

    return (
        <div className="min-h-full px-6 py-8 text-(--text-primary) md:px-10">
            <div className="mx-auto max-w-[1500px] space-y-6">
                <header className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">Experiments</p>
                        <h1 className="text-3xl font-semibold text-white">Benchmark · {benchmarkLabel}</h1>
                        <p className="mt-2 text-sm text-gray-400">
                            {display(llm.provider)} / {display(llm.model)} · {display(manifest.clarification_mode)} · {display(manifest.concurrency)} parallel workers
                        </p>
                    </div>
                    <div className="text-right text-xs text-gray-500">
                        <div>Avviato: {display(typeof manifest.started_at === 'string' ? new Date(manifest.started_at).toLocaleString() : null)}</div>
                        <div>Manifest schema v{display(manifest.run_artifact_schema_version)}</div>
                    </div>
                </header>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Metric label="Run registrate" value={counts.total} hint={plan ? `${progress}% del totale previsto (${plan})` : 'Totale dal JSONL'} />
                    <Metric label="Completate" value={counts.completed} hint={counts.total ? `${Math.round(counts.completed / counts.total * 100)}% delle run registrate` : 'Nessuna run'} />
                    <Metric label="Errori" value={counts.errors} hint="Tentativi terminati con errore" />
                    <Metric label="Scenari abilitati" value={scenarios.length} hint={`${Array.isArray(manifest.enabled_variant_ids) ? manifest.enabled_variant_ids.length : '—'} varianti`} />
                </div>

                <div className="flex flex-wrap gap-3 rounded-2xl border border-white/10 bg-(--glass-bg) p-4">
                    <Filter label="Condizione" value={condition} onChange={setCondition} values={conditions} />
                    <Filter label="Scenario" value={scenario} onChange={setScenario} values={scenarios} />
                    <Filter label="Esito" value={status} onChange={setStatus} values={['completed', 'error']} />
                    <label className="min-w-56 flex-1 text-xs text-gray-400">
                        Cerca
                        <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Run, query, SQL o errore…" className="mt-1.5 w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/50" />
                    </label>
                    <div className="self-end pb-2 text-xs text-gray-500">{filteredRuns.length} risultati</div>
                </div>

                <div className="grid min-h-[560px] gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
                    <section className="overflow-hidden rounded-2xl border border-white/10 bg-(--glass-bg)">
                        <div className="max-h-[720px] overflow-auto">
                            <table className="w-full min-w-[760px] text-left text-sm">
                                <thead className="sticky top-0 z-10 bg-[#111b1a] text-xs uppercase tracking-wider text-gray-500">
                                    <tr>
                                        <th className="px-4 py-3">Scenario / unità</th><th className="px-4 py-3">Condizione</th><th className="px-4 py-3">Rep.</th><th className="px-4 py-3">Esito</th><th className="px-4 py-3">Durata</th><th className="px-4 py-3">Risultati</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {filteredRuns.map((run, index) => (
                                        <tr key={`${run.run_id}-${index}`} onClick={() => setSelectedId(run.run_id ?? null)} className={`cursor-pointer transition-colors hover:bg-white/5 ${selected?.run_id === run.run_id ? 'bg-emerald-500/10' : ''}`}>
                                            <td className="px-4 py-3"><div className="font-medium text-white">{display(run.unit_id ?? run.scenario_id)}</div><div className="mt-1 font-mono text-[11px] text-gray-500">{display(run.run_id)}</div></td>
                                            <td className="px-4 py-3 text-gray-300">{display(run.condition)}</td>
                                            <td className="px-4 py-3 text-gray-300">{display(run.repeat)}</td>
                                            <td className="px-4 py-3"><StatusBadge status={run.status} /></td>
                                            <td className="px-4 py-3 text-gray-300">{formatDuration(run.duration_seconds)}</td>
                                            <td className="px-4 py-3 text-gray-300">{display(run.results_count)}</td>
                                        </tr>
                                    ))}
                                    {filteredRuns.length === 0 && <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-500">Nessuna run corrisponde ai filtri.</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <aside className="space-y-3 xl:max-h-[720px] xl:overflow-auto">
                        {selected ? <>
                            <div className="rounded-2xl border border-white/10 bg-(--glass-bg) p-5">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div><p className="font-mono text-xs text-gray-500">{display(selected.run_id)}</p><h2 className="mt-1 text-xl font-semibold text-white">{display(selected.unit_id ?? selected.scenario_id)}</h2></div>
                                    <StatusBadge status={selected.status} />
                                </div>
                                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                                    <Info label="Condizione" value={selected.condition} /><Info label="Modello" value={selected.model} /><Info label="Repeat / attempt" value={`${display(selected.repeat)} / ${display(selected.attempt)}`} /><Info label="Durata" value={formatDuration(selected.duration_seconds)} /><Info label="Chiarimento" value={formatDuration(selected.clarification_seconds)} /><Info label="Analisi" value={formatDuration(selected.analysis_seconds)} /><Info label="Stato chiarimento" value={selected.clarification_status} /><Info label="Risultati" value={selected.results_count} />
                                </div>
                            </div>
                            {selected.error && <Detail title="Errore">{selected.error}</Detail>}
                            <Detail title="Query inviata">{selected.submitted_query ?? '—'}</Detail>
                            {selected.refined_query && <Detail title="Query revisionata">{selected.refined_query}</Detail>}
                            <Detail title="SQL finale"><code className="font-mono text-xs">{selected.final_sql ?? '—'}</code></Detail>
                            <Detail title="SQL agent"><code className="font-mono text-xs">{selected.sql_agent_sql ?? '—'}</code></Detail>
                            <Detail title="Rilevamento omissioni / mapping">
                                {JSON.stringify({ initial_missing: selected.initial_missing, expected_initial_missing: selected.expected_initial_missing, detection: selected.detection, mapping_accuracy: selected.mapping_accuracy, turns: selected.turns, turn_targets: selected.turn_targets }, null, 2)}
                            </Detail>
                            <Detail title="Top risultati">{JSON.stringify(selected.top ?? [], null, 2)}</Detail>
                        </> : <div className="rounded-2xl border border-white/10 bg-(--glass-bg) p-8 text-center text-gray-500">Seleziona una run per vedere i dettagli.</div>}
                    </aside>
                </div>
                <p className="text-xs text-gray-600">I dati sono caricati dai file configurati all’avvio/build di Vite. Per aggiornare una build statica, ricostruire il frontend dopo l’aggiornamento del benchmark.</p>
            </div>
        </div>
    );
}

function Metric({ label, value, hint }: { label: string; value: string | number; hint: string }) {
    return <div className="rounded-2xl border border-white/10 bg-(--glass-bg) p-4"><div className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</div><div className="mt-2 text-2xl font-semibold text-white">{value}</div><div className="mt-1 text-xs text-gray-500">{hint}</div></div>;
}

function Filter({ label, value, onChange, values }: { label: string; value: string; onChange: (value: string) => void; values: string[] }) {
    return <label className="min-w-36 text-xs text-gray-400">{label}<select value={value} onChange={event => onChange(event.target.value)} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#101817] px-3 py-2 text-sm text-white outline-none focus:border-emerald-500/50"><option value="all">Tutte</option>{values.map(option => <option key={option} value={option}>{option}</option>)}</select></label>;
}

function Info({ label, value }: { label: string; value: unknown }) {
    return <div className="rounded-lg bg-black/15 px-3 py-2"><div className="text-[11px] text-gray-500">{label}</div><div className="mt-1 text-gray-200">{display(value)}</div></div>;
}
