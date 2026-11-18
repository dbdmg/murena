import { AxiosError, type AxiosAdapter } from 'axios';
import type { AnalysisResults } from '../api/types';
import type { DemoScenario, Dimension } from '../utils/demoScenarios';

export const demoUser = { id: 0, username: 'Demo presenter', created_at: '2026-01-01T00:00:00Z' };
let activeScenario: DemoScenario | null = null;
type LocalTopResult = { id: string; score?: number; distance_km?: number };
type LocalBenchmarkRun = { run_id?: string; query?: string; results_count?: number; top?: LocalTopResult[]; final_sql?: string; agent_trace?: AnalysisResults['agent_trace'] };
type LocalEstate = Record<string, unknown> & { id: string; latitude: number; longitude: number };
let benchmarkCache: Promise<Record<string, LocalBenchmarkRun>> | null = null;
let estateCache: Promise<LocalEstate[]> | null = null;

const getBenchmarkRuns = () => benchmarkCache ??= fetch('/data/benchmark_runs.json').then(response => {
    if (!response.ok) throw new Error('Could not load local benchmark output.');
    return response.json() as Promise<Record<string, LocalBenchmarkRun>>;
});
const getEstates = () => estateCache ??= fetch('/data/estates.json').then(response => {
    if (!response.ok) throw new Error('Could not load local estate inventory.');
    return response.json() as Promise<LocalEstate[]>;
});

export function selectDemoScenario(scenario: DemoScenario) {
    activeScenario = scenario;
    sessions.clear();
}
const sessions = new Map<string, { remaining: Dimension[]; text: string; turn: number }>();
const runs = new Map<string, AnalysisResults>();

/** Load the complete local script and leave its session ready for review. */
export function loadDemoConversation(scenario: DemoScenario) {
    const messages: { role: 'user' | 'assistant'; content: string }[] = [
        { role: 'user', content: scenario.initial_query },
    ];
    for (const turn of scenario.turns) {
        messages.push(
            { role: 'assistant', content: turn.question },
            { role: 'user', content: turn.answer },
        );
    }
    selectDemoScenario(scenario);
    const sessionId = `demo-session-${crypto.randomUUID()}`;
    sessions.set(sessionId, { remaining: [], text: scenario.review_query, turn: scenario.turns.length });
    return { sessionId, messages, reviewQuery: scenario.review_query };
}


/** Local-only API transport. Unsupported requests fail closed, without a network fallback. */
export const demoAdapter: AxiosAdapter = async config => {
    const path = (config.url || '').split('?')[0].replace(/\/$/, '');
    const method = config.method || 'get';
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : (config.data || {});
    const respond = (data: unknown) => ({ data, status: 200, statusText: 'OK', headers: {}, config });
    const fail = (message: string) => { throw new AxiosError(message, 'ERR_DEMO_REQUEST', config); };
    if (path === '/auth/me') return respond(demoUser);
    if (path === '/analysis/suggested-queries') return respond({ suggestions: [] });
    if (path === '/analysis/demos') return respond([]);
    if (path === '/analysis/history') {
        const history = [...runs.values()].reverse().map(run => ({ ...run, buildings_count: run.buildings.length }));
        const offset = Number(config.params?.offset || 0);
        return respond(history.slice(offset, offset + Number(config.params?.limit || 50)));
    }
    if (path === '/analysis' && method === 'post') {
        if (!body.clarification_session_id) {
            if (!activeScenario) return fail('Select a demo scenario first.');
            const id = `demo-session-${crypto.randomUUID()}`;
            sessions.set(id, {
                remaining: [...activeScenario.missing_dimensions],
                text: body.query, turn: 0,
            });
            body.clarification_session_id = id;
        }
        const id = body.clarification_session_id as string;
        const session = sessions.get(id);
        if (!session) return fail('Demo session expired. Start a new search.');
        if (body.clarification_confirmed) {
            const scenario = activeScenario;
            if (!scenario) return fail('Select a demo scenario first.');
            if (session.remaining.length) return fail('Complete the scripted clarification first.');
            const runId = `demo-${crypto.randomUUID()}`;
            const now = new Date().toISOString();
            const [benchmarkRuns, estates] = await Promise.all([getBenchmarkRuns(), getEstates()]);
            const benchmarkRun = benchmarkRuns[scenario.case_id];
            const estatesById = new Map(estates.map(estate => [String(estate.id), estate]));
            const buildings = (benchmarkRun?.top ?? []).flatMap(top => {
                const estate = estatesById.get(String(top.id));
                if (!estate) return [];
                const energy = estate.energy_scores as Record<string, number | null> | undefined;
                const proximity = estate.proximity_scores as Record<string, number | null> | undefined;
                return [{
                    id: String(estate.id),
                    address: typeof estate.address === 'string' ? estate.address : undefined,
                    coordinates: { lat: estate.latitude, lng: estate.longitude },
                    surface_area: typeof estate.surface_area === 'number' ? estate.surface_area : undefined,
                    construction_year: typeof estate.construction_period === 'string' ? estate.construction_period : undefined,
                    energy_class: typeof estate.energy_class === 'string' ? estate.energy_class : undefined,
                    property_type: typeof estate.property_type === 'string' ? estate.property_type : undefined,
                    is_evaluated: false,
                    is_match: true,
                    is_meta_building: estate.is_meta_estate === true,
                    meta_building: estate.is_meta_estate === true,
                    score: top.score,
                    distance_km: top.distance_km,
                    energy_scores: energy ? { total: energy.total ?? undefined, class_score: energy.class_score ?? undefined, plant_score: energy.plant_score ?? undefined, envelope_score: energy.envelope_score ?? undefined, renewables_score: energy.renewables_score ?? undefined } : undefined,
                    proximity_scores: proximity ? { healthcare: proximity.healthcare ?? undefined, mobility: proximity.mobility ?? undefined, greenery: proximity.greenery ?? undefined, education: proximity.education ?? undefined, commerce: proximity.commerce ?? undefined, sport: proximity.sport ?? undefined } : undefined,
                    energy_files: Array.isArray(estate.ape_file_list_filtered) ? estate.ape_file_list_filtered.filter((value): value is string => typeof value === 'string') : undefined,
                }];
            });
            const result: AnalysisResults = {
                run_id: runId, status: 'completed', query: body.query,
                created_at: now, completed_at: now, buildings, location: [],
                broker_summary: benchmarkRun
                    ? `Showing the precomputed refined benchmark output for ${scenario.case_id} (${benchmarkRun.run_id}). ${buildings.length} of the top 10 properties were matched to the local inventory. EvaluationAgent output was not retained in this compact benchmark artifact.`
                    : `No completed refined benchmark run is available for ${scenario.case_id}. The local inventory is shown without scenario-specific results.`,
                agent_trace: benchmarkRun?.agent_trace ?? [],
            };
            runs.set(runId, result);
            sessions.delete(id);
            return respond({ run_id: runId, status: 'completed', created_at: now, message: 'Simulation completed.' });
        }
        if (body.clarification_response) {
            session.text += ` ${body.clarification_response}`;
            session.remaining.shift();
            session.turn += 1;
        }
        const dimension = session.remaining[0];
        return respond(dimension
            ? { session_id: id, status: 'ASK', turn: session.turn, question: `Please specify your requirements for ${dimension.toLowerCase()}.` }
            : { session_id: id, status: 'REVIEW', turn: session.turn, refined_query: session.text });
    }
    const match = path.match(/^\/analysis\/([^/]+)(?:\/(agent_steps|gemini_responses))?$/);
    if (match) {
        if (!runs.has(match[1])) return fail('Unknown local demo run. Demo runs are cleared on reload.');
        if (method === 'delete') { runs.delete(match[1]); return respond(null); }
        if (match[2] === 'agent_steps') return respond({ run_id: match[1], steps: runs.get(match[1])?.agent_trace ?? [] });
        if (match[2] === 'gemini_responses') return respond({});
        return respond(runs.get(match[1]));
    }
    if (path === '/map/config') return respond({ center: { lat: 45.07, lng: 7.69 }, zoom: 12, style: '', attribution: 'Local simulation' });
    if (path.startsWith('/map/overlays/')) return respond({ type: 'FeatureCollection', features: [] });
    if (path === '/map/markers' || path === '/map/markers-lite') return respond([]);
    if (path === '/layers/pois') return respond({ count: 0, categories: [], pois: [] });
    if (path === '/buildings') return respond({ buildings: [], total: 0, limit: 0, offset: 0, has_more: false });
    if (path === '/logs/stream') return respond({ events: [], last_id: 0 });
    if (path === '/logs/traces' || (path.startsWith('/feedback/') && method === 'get')) return respond([]);
    return fail(`Unavailable in local simulation: ${method.toUpperCase()} ${path}`);
};
