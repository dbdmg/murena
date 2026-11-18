import { useEffect, useState } from 'react';
import type { DemoScenario, Dimension } from '../../utils/demoScenarios';

type Props = {
    enabled: boolean;
    busy: boolean;
    onSelectScenario: (scenario: DemoScenario) => void;
};

type ExportedBenchmarkRun = {
    scenario?: DemoScenario;
    status?: string;
    model?: string;
    repeat?: number;
};

const dimensions = new Set<Dimension>(['I', 'D', 'L', 'Cb', 'Ce', 'Cp']);

function isDemoScenario(value: unknown): value is DemoScenario {
    if (!value || typeof value !== 'object') return false;
    const scenario = value as Partial<DemoScenario>;
    return typeof scenario.case_id === 'string'
        && typeof scenario.name === 'string'
        && typeof scenario.initial_query === 'string'
        && typeof scenario.review_query === 'string'
        && Array.isArray(scenario.missing_dimensions)
        && scenario.missing_dimensions.every(dimension => dimensions.has(dimension))
        && Array.isArray(scenario.turns)
        && scenario.turns.every(turn => typeof turn?.question === 'string' && typeof turn?.answer === 'string');
}

export function DemoPanel({ enabled, busy, onSelectScenario }: Props) {
    const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
    const [selectedId, setSelectedId] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        fetch('/data/benchmark_runs.json')
            .then(response => {
                if (!response.ok) throw new Error('Could not load completed benchmark runs.');
                return response.json() as Promise<Record<string, ExportedBenchmarkRun>>;
            })
            .then(exported => {
                const available = Object.values(exported)
                    .map(item => item.scenario)
                    .filter(isDemoScenario)
                    .sort((a, b) => a.case_id.localeCompare(b.case_id));
                if (!cancelled) setScenarios(available);
            })
            .catch(() => { if (!cancelled) setError('Could not load scenarios and results from the configured benchmark run.'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, []);

    const selected = scenarios.find(scenario => scenario.case_id === selectedId);

    return <aside className="mb-4 shrink-0 rounded-2xl border border-(--border-light) bg-(--glass-bg) p-3 text-(--text-primary)">
        <h2 className="text-sm font-semibold">Select benchmark run</h2>
        {enabled && <div className="mt-3 max-h-[60vh] space-y-3 overflow-y-auto">
            <p className="text-xs text-(--text-secondary)">Choose a completed refined v4 run. Its recorded conversation and top results come from the same configured results directory as the Benchmark page.</p>
            {loading && <p role="status" className="text-xs">Loading benchmark runs…</p>}
            {error && <p role="alert" className="text-xs text-amber-200">{error}</p>}
            {!loading && !error && scenarios.length === 0 && <p role="status" className="text-xs">No completed refined runs are available in the configured results directory.</p>}
            {scenarios.length > 0 && <>
                <label className="block text-xs">{scenarios.length} completed scenarios
                    <select aria-label="Demo benchmark scenario" value={selectedId} disabled={busy} onChange={event => setSelectedId(event.target.value)} className="mt-1 w-full rounded-lg bg-(--bg-main) p-2 text-sm">
                        <option value="">Choose a completed run…</option>
                        {scenarios.map(scenario => <option key={scenario.case_id} value={scenario.case_id}>
                            {scenario.case_id} · {scenario.profile ?? scenario.balance ?? scenario.name}
                        </option>)}
                    </select>
                </label>
                {selected && <>
                    <p role="status" className="text-xs text-(--text-secondary)">{selected.name}{selected.base_case_id ? ` · ${selected.base_case_id}` : ''}</p>
                    <div className="sticky bottom-0 bg-(--glass-bg) py-2">
                        <button type="button" disabled={busy} onClick={() => onSelectScenario(selected)} className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white enabled:hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50">Load recorded conversation</button>
                    </div>
                </>}
            </>}
        </div>}
    </aside>;
}
