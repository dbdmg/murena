import { useEffect, useState } from 'react';
import { ArrowRight, LoaderCircle, MessageSquareText } from 'lucide-react';
import { dimensionLabels, type DemoScenario, type Dimension } from '../../utils/demoScenarios';

type Props = {
    enabled: boolean;
    busy: boolean;
    onSelectScenario: (scenario: DemoScenario) => void;
};

type ExportedBenchmarkRun = { scenario?: DemoScenario };
type ScenarioFilters = DemoScenario & { use_case?: string };
const dimensions: Dimension[] = ['I', 'D', 'L', 'Cb', 'Ce', 'Cp'];

function isDemoScenario(value: unknown): value is DemoScenario {
    if (!value || typeof value !== 'object') return false;
    const scenario = value as Partial<DemoScenario>;
    return typeof scenario.case_id === 'string'
        && typeof scenario.name === 'string'
        && typeof scenario.initial_query === 'string'
        && typeof scenario.review_query === 'string'
        && Array.isArray(scenario.missing_dimensions)
        && scenario.missing_dimensions.every(dimension => dimensions.includes(dimension))
        && Array.isArray(scenario.turns)
        && scenario.turns.every(turn => typeof turn?.question === 'string' && typeof turn?.answer === 'string');
}

function useCaseLabel(scenario: ScenarioFilters): string {
    const label = scenario.use_case?.split(';')[0]?.trim();
    return label || scenario.name || scenario.base_case_id || 'Other';
}

function scenarioK(scenario: DemoScenario): number | null {
    const match = scenario.case_id.match(/_k(\d+)(?:_|$)/i);
    return match ? Number(match[1]) : null;
}

export function DemoPanel({ enabled, busy, onSelectScenario }: Props) {
    const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
    const [useCase, setUseCase] = useState('');
    const [k, setK] = useState('');
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

    const scenarioData = scenarios as ScenarioFilters[];
    const useCases = [...new Set(scenarioData.map(useCaseLabel))].sort((a, b) => a.localeCompare(b));
    const selectedUseCaseScenarios = scenarioData.filter(scenario => useCaseLabel(scenario) === useCase);
    const availableK = [...new Set(selectedUseCaseScenarios.map(scenarioK).filter((value): value is number => value !== null))]
        .sort((a, b) => a - b);
    const matches = k === '' ? [] : selectedUseCaseScenarios.filter(scenario => scenarioK(scenario) === Number(k));
    // Several recorded profiles can share a use case and k. Use the first stable case_id as the demo preview.
    const selected = matches[0];

    return <aside className="mb-4 shrink-0 rounded-2xl border border-(--border-light) bg-(--glass-bg) p-5 text-(--text-primary) shadow-xl backdrop-blur-xl">
        <div className="mb-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-(--accent-cyan)">Demo mode</p>
            <h2 className="mt-1 text-lg font-semibold">Choose a use case</h2>
            <p className="mt-1 text-sm text-(--text-secondary)">Choose a scenario and the number of dimensions to clarify, then review the preview.</p>
        </div>
        {enabled && <div className="space-y-4">
            {loading && <p role="status" className="text-sm text-(--text-secondary)">Loading use cases…</p>}
            {error && <p role="alert" className="text-sm text-amber-200">{error}</p>}
            {!loading && !error && scenarios.length === 0 && <p role="status" className="text-sm text-(--text-secondary)">No completed refined runs are available in the configured results directory.</p>}
            {!loading && !error && scenarios.length > 0 && <>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_8rem]">
                    <label className="text-xs font-medium text-(--text-secondary)">Use case
                        <select aria-label="Use case" value={useCase} disabled={busy} onChange={event => { setUseCase(event.target.value); setK(''); }} className="mt-1.5 w-full rounded-xl border border-(--border-light) bg-(--bg-main) p-3 text-sm text-(--text-primary) outline-none focus:border-(--accent-cyan)/70">
                            <option value="">Choose a use case…</option>
                            {useCases.map(option => <option key={option} value={option}>{option}</option>)}
                        </select>
                    </label>
                    <label className="text-xs font-medium text-(--text-secondary)">k
                        <select aria-label="k" value={k} disabled={busy || !useCase} onChange={event => setK(event.target.value)} className="mt-1.5 w-full rounded-xl border border-(--border-light) bg-(--bg-main) p-3 text-sm text-(--text-primary) outline-none focus:border-(--accent-cyan)/70">
                            <option value="">Choose k…</option>
                            {availableK.map(value => <option key={value} value={value}>{value}</option>)}
                        </select>
                    </label>
                </div>

                {selected && <section aria-label="Scenario preview" className="rounded-xl border border-(--border-light) bg-(--bg-main)/55 p-4">
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-(--text-tertiary)">Preview</p>
                            <p className="mt-1 text-sm font-medium">{useCase} <span className="text-(--text-tertiary)">· k = {k}</span></p>
                        </div>
                        <span className="rounded-full border border-(--border-light) px-2.5 py-1 text-xs text-(--text-secondary)">{selected.turns.length} {selected.turns.length === 1 ? 'clarification' : 'clarifications'}</span>
                    </div>
                    <div className="mt-3 rounded-lg bg-black/10 p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-(--text-tertiary)">Initial request</p>
                        <p className="mt-1 text-sm leading-relaxed">{selected.initial_query}</p>
                    </div>
                    <div className="mt-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-(--text-tertiary)">Omitted dimensions</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                            {selected.missing_dimensions.map(dimension => <span key={dimension} className="rounded-full border border-(--accent-cyan)/30 bg-(--accent-cyan)/10 px-2.5 py-1 text-xs text-(--text-primary)">{dimensionLabels[dimension]}</span>)}
                            {selected.missing_dimensions.length === 0 && <span className="text-xs text-(--text-secondary)">None</span>}
                        </div>
                    </div>
                    {matches.length > 1 && <p className="mt-2 text-[11px] text-(--text-tertiary)">Previewing recorded conversation {selected.case_id}.</p>}
                    <button type="button" disabled={busy} onClick={() => onSelectScenario(selected)} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50">
                        {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <MessageSquareText className="h-4 w-4" />}
                        Start demo
                        {!busy && <ArrowRight className="h-4 w-4" />}
                    </button>
                </section>}
            </>}
        </div>}
    </aside>;
}
