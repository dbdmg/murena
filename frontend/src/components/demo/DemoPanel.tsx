import { useEffect, useRef, useState } from 'react';
import { dimensionLabels, parseDemoScenarios } from '../../utils/demoScenarios';
import type { DemoScenario } from '../../utils/demoScenarios';

type Props = {
    enabled: boolean;
    busy: boolean;
    inConversation: boolean;
    onSelectScenario: (scenario: DemoScenario) => void;
};

export function DemoPanel({ enabled, busy, inConversation, onSelectScenario }: Props) {
    const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
    const [selectedId, setSelectedId] = useState('');
    const [source, setSource] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const uploadVersion = useRef(0);
    const selected = scenarios.find(item => item.case_id === selectedId);

    const replaceScenarios = (value: unknown, name: string) => {
        const parsed = parseDemoScenarios(value);
        setScenarios(parsed);
        setSelectedId('');
        setSource(name);
        setError(null);
    };
    useEffect(() => {
        let cancelled = false;
        const version = uploadVersion.current;
        import('../../../../backend/experiments/data/scenarios_v3/scenario_triplets.json')
            .then(data => {
                if (!cancelled && version === uploadVersion.current) replaceScenarios(data.default, 'Built-in scenarios v3');
            })
            .catch(() => { if (!cancelled) setError('Could not load built-in scenarios. Import a scenario triplets JSON file.'); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, []);

    return <aside className="mb-4 shrink-0 rounded-2xl border border-(--border-light) bg-(--glass-bg) p-3 text-(--text-primary)">
        <h2 className="text-sm font-semibold">Offline demo · Backend disconnected</h2>
        {enabled && <div className="mt-3 max-h-[30vh] space-y-3 overflow-y-auto">
            <p className="text-xs text-(--text-secondary)">Scripted local conversation. No backend or LLM connection. Choose a scenario to load the complete conversation and its final query for review. Property results are not included in the scenario triplets.</p>
            <label className="block text-xs">Import scenario triplets JSON
                <input type="file" accept=".json,application/json" disabled={busy || inConversation} className="mt-1 block w-full text-xs" onChange={async event => {
                    const file = event.target.files?.[0];
                    event.target.value = '';
                    if (!file) return;
                    uploadVersion.current += 1;
                    try { replaceScenarios(JSON.parse(await file.text()), file.name); }
                    catch (err) { setError(err instanceof Error ? err.message : 'Invalid JSON file.'); }
                }} />
            </label>
            {loading && <p role="status" className="text-xs">Loading scenarios…</p>}
            {error && <p role="alert" className="text-xs text-amber-200">{error}</p>}
            {scenarios.length > 0 && <>
                <label className="block text-xs">{source} · {scenarios.length} scenarios
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
