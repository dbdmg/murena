import { useEffect, useMemo, useState } from 'react';
import { dimensions, dimensionLabels, parseDemoScenarios, type Dimension } from '../../utils/demoScenarios';
import type { DemoScenario } from '../../utils/demoScenarios';

type Props = {
    enabled: boolean;
    busy: boolean;
    onSelectScenario: (scenario: DemoScenario) => void;
};

export function DemoPanel({ enabled, busy, onSelectScenario }: Props) {
    const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
    const [selectedBaseId, setSelectedBaseId] = useState('');
    const [selectedDimensions, setSelectedDimensions] = useState<Dimension[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const baseScenarios = useMemo(() => {
        const grouped = new Map<string, DemoScenario[]>();
        scenarios.forEach(item => {
            const baseId = item.base_case_id ?? item.case_id.match(/^S\d+/)?.[0] ?? item.case_id;
            grouped.set(baseId, [...(grouped.get(baseId) ?? []), item]);
        });
        return [...grouped.entries()].map(([id, variants]) => ({ id, variants }));
    }, [scenarios]);
    const selectedBase = baseScenarios.find(item => item.id === selectedBaseId);
    const selected = selectedBase?.variants.find(item =>
        item.missing_dimensions.length === selectedDimensions.length
        && item.missing_dimensions.every(dimension => selectedDimensions.includes(dimension)),
    );

    useEffect(() => {
        let cancelled = false;
        Promise.all([
            import('@demo-scenarios'),
            fetch('/data/benchmark_runs.json').then(response => {
                if (!response.ok) throw new Error('Could not load completed benchmark runs.');
                return response.json() as Promise<Record<string, unknown>>;
            }),
        ])
            .then(([data, completedRuns]) => {
                const parsed = parseDemoScenarios(data.default);
                const completedIds = new Set(Object.keys(completedRuns));
                if (!cancelled) setScenarios(parsed.filter(scenario => completedIds.has(scenario.case_id)));
            })
            .catch(() => { if (!cancelled) setError('Could not load the scenario catalog and completed benchmark results.'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, []);

    return <aside className="mb-4 shrink-0 rounded-2xl border border-(--border-light) bg-(--glass-bg) p-3 text-(--text-primary)">
        <h2 className="text-sm font-semibold">Select scenario</h2>
        {enabled && <div className="mt-3 max-h-[60vh] space-y-3 overflow-y-auto">
            <p className="text-xs text-(--text-secondary)">Choose a case and missing dimensions with a completed refined benchmark result. The stored top 10 and inventory details load locally; no backend or LLM is contacted.</p>
            {loading && <p role="status" className="text-xs">Loading scenarios…</p>}
            {error && <p role="alert" className="text-xs text-amber-200">{error}</p>}
            {!loading && !error && scenarios.length === 0 && <p role="status" className="text-xs">No scenarios are enabled in the configured catalog.</p>}
            {scenarios.length > 0 && <>
                <label className="block text-xs">{baseScenarios.length} completed base cases · {scenarios.length} completed variants
                    <select aria-label="Demo base case" value={selectedBaseId} disabled={busy} onChange={event => {
                        setSelectedBaseId(event.target.value);
                        setSelectedDimensions([]);
                    }} className="mt-1 w-full rounded-lg bg-(--bg-main) p-2 text-sm">
                        <option value="">Choose a base case…</option>
                        {baseScenarios.map(item => <option key={item.id} value={item.id}>{item.id} · {item.variants[0]?.regulatory_use_case}</option>)}
                    </select>
                </label>
                {selectedBase && <fieldset disabled={busy} className="space-y-2">
                    <legend className="mb-2 text-xs">Select missing dimensions</legend>
                    <div className="grid grid-cols-2 gap-2">
                        {dimensions.map(dimension => <label key={dimension} className="flex items-center gap-2 rounded-lg bg-(--bg-main) px-2 py-1.5 text-xs">
                            <input type="checkbox" checked={selectedDimensions.includes(dimension)} onChange={event => setSelectedDimensions(current => event.target.checked
                                ? [...current, dimension]
                                : current.filter(item => item !== dimension))} />
                            {dimensionLabels[dimension]}
                        </label>)}
                    </div>
                    <p role="status" className="text-xs text-(--text-secondary)">{selected ? `Matched variant: ${selected.case_id}` : 'No matching variant exists for this combination.'}</p>
                    <div className="sticky bottom-0 bg-(--glass-bg) py-2">
                        <button type="button" disabled={!selected || busy} onClick={() => selected && onSelectScenario(selected)} className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white enabled:hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50">Load selected scenario</button>
                    </div>
                    <p className="text-xs text-(--text-tertiary)">Loading a scenario replaces the current conversation. Review its final query before confirming.</p>
                </fieldset>}
            </>}
        </div>}
    </aside>;
}
