import { useEffect, useState } from 'react';
import { BriefcaseBusiness, BusFront, Circle, CircleCheck, CircleDashed, CircleHelp, Home, MapPin, Ruler, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { dimensionLabels, type DemoScenario, type Dimension } from '../../utils/demoScenarios';

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

type ScenarioFilters = DemoScenario & {
    use_case?: string;
    balance?: string;
    specified_dimensions?: Dimension[];
    vague_dimensions?: Dimension[];
    optout_dimensions?: Dimension[];
};
type ScenarioDimensionState = 'omitted' | 'ambiguous' | 'specified';

const dimensions: Dimension[] = ['I', 'D', 'L', 'Cb', 'Ce', 'Cp'];
const dimensionSet = new Set<Dimension>(dimensions);
const dimensionIcons: Record<Dimension, LucideIcon> = {
    I: Home,
    D: BriefcaseBusiness,
    L: MapPin,
    Cb: Ruler,
    Ce: Zap,
    Cp: BusFront,
};
const stateIcons: Record<ScenarioDimensionState, LucideIcon> = {
    omitted: CircleDashed,
    ambiguous: CircleHelp,
    specified: CircleCheck,
};

function isDemoScenario(value: unknown): value is DemoScenario {
    if (!value || typeof value !== 'object') return false;
    const scenario = value as Partial<DemoScenario>;
    return typeof scenario.case_id === 'string'
        && typeof scenario.name === 'string'
        && typeof scenario.initial_query === 'string'
        && typeof scenario.review_query === 'string'
        && Array.isArray(scenario.missing_dimensions)
        && scenario.missing_dimensions.every(dimension => dimensionSet.has(dimension))
        && Array.isArray(scenario.turns)
        && scenario.turns.every(turn => typeof turn?.question === 'string' && typeof turn?.answer === 'string');
}

export function DemoPanel({ enabled, busy, onSelectScenario }: Props) {
    const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
    const [useCase, setUseCase] = useState('');
    const [dimensionStates, setDimensionStates] = useState<Partial<Record<Dimension, ScenarioDimensionState>>>({});
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

    const scenarioData = scenarios as ScenarioFilters[];
    const useCases = [...new Set(scenarioData.map(scenario => scenario.use_case || scenario.base_case_id || 'Other'))].sort();
    const afterUseCase = scenarioData.filter(scenario => (scenario.use_case || scenario.base_case_id || 'Other') === useCase);
    const getDimensionState = (scenario: ScenarioFilters, dimension: Dimension): ScenarioDimensionState => {
        if (!scenario.missing_dimensions.includes(dimension)) return 'specified';
        if (scenario.vague_dimensions?.includes(dimension)) return 'ambiguous';
        if (scenario.specified_dimensions?.includes(dimension)) return 'specified';
        return 'omitted';
    };
    const matches = afterUseCase.filter(scenario => dimensions.every(dimension =>
        !dimensionStates[dimension] || getDimensionState(scenario, dimension) === dimensionStates[dimension]
    ));
    const statesAvailableFor = (dimension: Dimension): ScenarioDimensionState[] => [...new Set(afterUseCase
        .filter(scenario => dimensions.every(other => other === dimension
            || !dimensionStates[other]
            || getDimensionState(scenario, other) === dimensionStates[other]))
        .map(scenario => getDimensionState(scenario, dimension)))].sort((a, b) =>
            ['omitted', 'ambiguous', 'specified'].indexOf(a) - ['omitted', 'ambiguous', 'specified'].indexOf(b)
        );
    const selected = matches.find(scenario => scenario.case_id === selectedId) ?? (matches.length === 1 ? matches[0] : undefined);

    return <aside className="mb-4 shrink-0 rounded-2xl border border-(--border-light) bg-(--glass-bg) p-4 text-(--text-primary)">
        <h2 className="text-sm font-semibold">Choose a benchmark scenario</h2>
        {enabled && <div className="mt-3 max-h-[60vh] space-y-3 overflow-y-auto">
            <p className="text-xs text-(--text-secondary)">Narrow the available completed runs in order. Only choices with at least one matching run are shown.</p>
            {loading && <p role="status" className="text-xs">Loading benchmark runs…</p>}
            {error && <p role="alert" className="text-xs text-amber-200">{error}</p>}
            {!loading && !error && scenarios.length === 0 && <p role="status" className="text-xs">No completed refined runs are available in the configured results directory.</p>}
            {scenarios.length > 0 && <>
                <div className="flex flex-wrap items-center gap-2">
                <label className="w-56 shrink-0 text-xs font-medium">Use case
                    <select aria-label="Use case" value={useCase} disabled={busy} onChange={event => { setUseCase(event.target.value); setDimensionStates({}); setSelectedId(''); }} className="mt-1 w-full rounded-lg bg-(--bg-main) p-2 text-sm">
                        <option value="">Choose a use case…</option>
                        {useCases.map(option => <option key={option} value={option}>{option}</option>)}
                    </select>
                </label>
                {useCase && dimensions.map(dimension => {
                    const DimensionIcon = dimensionIcons[dimension];
                    const currentState = dimensionStates[dimension];
                    const options = statesAvailableFor(dimension);
                    const stateIndex = currentState ? options.indexOf(currentState) : -1;
                    const nextState = stateIndex >= 0 && stateIndex === options.length - 1
                        ? undefined
                        : options[stateIndex + 1] ?? options[0];
                    const CurrentStateIcon = currentState ? stateIcons[currentState] : Circle;
                    return <button
                        key={dimension}
                        type="button"
                        disabled={busy || options.length === 0}
                        aria-label={`${dimensionLabels[dimension]}: ${currentState ?? 'any state'}. Click to change.`}
                        title={`${dimensionLabels[dimension]} (${dimension}) · ${currentState ?? 'any state'}${options.length ? ` · next: ${nextState ?? 'any state'}` : ''}`}
                        onClick={() => { setDimensionStates(current => {
                            const next = { ...current };
                            if (nextState) next[dimension] = nextState;
                            else delete next[dimension];
                            return next;
                        }); setSelectedId(''); }}
                        className={`inline-flex h-11 min-w-12 items-center justify-center gap-1.5 rounded-xl border px-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${currentState ? 'border-(--accent-cyan)/50 bg-(--accent-cyan)/10 text-(--text-primary)' : 'border-(--border-light) bg-(--bg-main)/60 text-(--text-secondary) hover:bg-white/10'}`}
                    >
                        <DimensionIcon className="h-4 w-4" aria-hidden="true" />
                        <span>{dimension}</span>
                        <CurrentStateIcon className="h-3.5 w-3.5 opacity-80" aria-hidden="true" />
                    </button>;
                })}
                </div>
                {useCase && <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-(--text-tertiary)" aria-label="Dimension state legend">
                    <span className="inline-flex items-center gap-1"><CircleDashed className="h-3.5 w-3.5" />Omitted</span>
                    <span className="inline-flex items-center gap-1"><CircleHelp className="h-3.5 w-3.5" />Ambiguous</span>
                    <span className="inline-flex items-center gap-1"><CircleCheck className="h-3.5 w-3.5" />Specified</span>
                    <span>Click a dimension to cycle available states; click again after the last to clear it.</span>
                </div>}
                {matches.length > 1 && <label className="block text-xs font-medium">Matching run
                    <select aria-label="Matching benchmark run" value={selectedId} disabled={busy} onChange={event => setSelectedId(event.target.value)} className="mt-1 w-full rounded-lg bg-(--bg-main) p-2 text-sm">
                        <option value="">Choose a matching run…</option>
                        {matches.map(scenario => <option key={scenario.case_id} value={scenario.case_id}>
                            {scenario.case_id}
                        </option>)}
                    </select>
                </label>}
                {selected && <>
                    <section aria-label="Selected scenario details" className="space-y-3 rounded-xl border border-(--border-light) bg-(--bg-main)/50 p-3">
                        <p className="text-xs font-semibold text-(--text-primary)">{selected.case_id}</p>
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-(--text-tertiary)">Starting request</p>
                            <p className="mt-1 text-sm leading-relaxed text-(--text-primary)">{selected.initial_query}</p>
                        </div>
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-(--text-tertiary)">Topics clarified</p>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                                {selected.missing_dimensions.map(dimension => <span key={dimension} className="rounded-full border border-(--border-light) px-2 py-1 text-xs text-(--text-secondary)">{dimensionLabels[dimension]}</span>)}
                            </div>
                        </div>
                        <p className="text-xs text-(--text-secondary)">{selected.turns.length} clarification {selected.turns.length === 1 ? 'exchange' : 'exchanges'} recorded{selected.base_case_id ? ` · scenario ${selected.base_case_id}` : ''}</p>
                    </section>
                    <div className="sticky bottom-0 bg-(--glass-bg) py-2">
                        <button type="button" disabled={busy} onClick={() => onSelectScenario(selected)} className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white enabled:hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50">Load recorded conversation</button>
                    </div>
                </>}
            </>}
        </div>}
    </aside>;
}
