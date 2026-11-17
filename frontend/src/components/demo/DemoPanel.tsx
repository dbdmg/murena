import { useEffect, useState } from 'react';
import { dimensionLabels, parseDemoScenarios } from '../../utils/demoScenarios';
import type { DemoScenario } from '../../utils/demoScenarios';

type Props = {
    enabled: boolean;
    busy: boolean;
    onSelectScenario: (scenario: DemoScenario) => void;
};

export function DemoPanel({ enabled, busy, onSelectScenario }: Props) {
    const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
    const [selectedId, setSelectedId] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const selected = scenarios.find(item => item.case_id === selectedId);

    useEffect(() => {
        let cancelled = false;
        import('@demo-scenarios')
            .then(data => {
                const parsed = parseDemoScenarios(data.default);
                if (!cancelled) setScenarios(parsed);
            })
            .catch(() => { if (!cancelled) setError('Could not load the configured scenario catalog.'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, []);

    return <aside className="mb-4 shrink-0 rounded-2xl border border-(--border-light) bg-(--glass-bg) p-3 text-(--text-primary)">
        <h2 className="text-sm font-semibold">Offline demo · Backend disconnected</h2>
        {enabled && <div className="mt-3 max-h-[30vh] space-y-3 overflow-y-auto">
            <p className="text-xs text-(--text-secondary)">Scripted local conversation. No backend or LLM connection. Choose a scenario to load the complete conversation and its final query for review. Property results are not included in the scenario triplets.</p>
            {loading && <p role="status" className="text-xs">Loading scenarios…</p>}
            {error && <p role="alert" className="text-xs text-amber-200">{error}</p>}
            {!loading && !error && scenarios.length === 0 && <p role="status" className="text-xs">No scenarios are enabled in the configured catalog.</p>}
            {scenarios.length > 0 && <>
                <label className="block text-xs">{scenarios.length} scenarios
                    <select aria-label="Demo scenario" value={selectedId} disabled={busy} onChange={event => {
                        setSelectedId(event.target.value);
                        const scenario = scenarios.find(item => item.case_id === event.target.value);
                        if (scenario) onSelectScenario(scenario);
                    }} className="mt-1 w-full rounded-lg bg-(--bg-main) p-2 text-sm">
                        <option value="" disabled>Choose a scenario…</option>
                        {scenarios.map(item => <option key={item.case_id} value={item.case_id}>{item.case_id} · {item.regulatory_use_case} · {item.missing_dimensions.length} missing</option>)}
                    </select>
                </label>
                {selected && <>
                    <p className="text-xs">Missing dimensions: {selected.missing_dimensions.map(d => dimensionLabels[d]).join(', ') || 'None'}</p>
                    <p className="text-xs text-(--text-tertiary)">Selecting another scenario replaces this conversation. Review the final query below before confirming.</p>
                </>}
            </>}
        </div>}
    </aside>;
}
