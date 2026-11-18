import { AxiosError, type AxiosAdapter } from 'axios';
import type { AnalysisResults } from '../api/types';
import type { DemoScenario, Dimension } from '../utils/demoScenarios';

export const demoUser = { id: 0, username: 'Demo presenter', created_at: '2026-01-01T00:00:00Z' };
let activeScenario: DemoScenario | null = null;
type LocalTopResult = { id: string; score?: number; distance_km?: number };
type LocalEvaluationResult = { id: string | number; evaluation_text: string; pros?: string[]; cons?: string[]; score?: number; final_ranking_score?: number };
type LocalBenchmarkRun = {
    run_id?: string;
    query?: string;
    results_count?: number;
    top?: LocalTopResult[];
    final_sql?: string;
    agent_trace?: AnalysisResults['agent_trace'];
    evaluation_results?: LocalEvaluationResult[];
};
type LocalEstate = Record<string, unknown> & { id: string; latitude: number; longitude: number };
let benchmarkCache: Promise<Record<string, LocalBenchmarkRun>> | null = null;
let estateCache: Promise<LocalEstate[]> | null = null;
let poiCache: Promise<Record<string, Record<string, Array<{ id?: string | number; lat: number; lon: number }>>>> | null = null;

const getBenchmarkRuns = () => benchmarkCache ??= fetch('/data/benchmark_runs.json').then(response => {
    if (!response.ok) throw new Error('Could not load local benchmark output.');
    return response.json() as Promise<Record<string, LocalBenchmarkRun>>;
});
const getEstates = () => estateCache ??= fetch('/data/benchmark_estates.json').then(response => {
    if (!response.ok) throw new Error('Could not load local estate inventory.');
    return response.json() as Promise<LocalEstate[]>;
});
const getPOICatalog = () => poiCache ??= fetch('/data/pois_by_category.json').then(response => {
    if (!response.ok) throw new Error('Could not load local POI catalog.');
    return response.json() as Promise<Record<string, Record<string, Array<{ id?: string | number; lat: number; lon: number }>>>>;
});

const POI_PRESENTATION: Record<string, { icon: string; color: string }> = {
    healthcare: { icon: '🏥', color: '#ef4444' },
    mobility: { icon: '🚇', color: '#3b82f6' },
    green: { icon: '🌳', color: '#22c55e' },
    sport: { icon: '⚽', color: '#f97316' },
    commercial: { icon: '🛒', color: '#eab308' },
    education: { icon: '🎓', color: '#a855f7' },
};

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
            const evaluationResults = benchmarkRun?.evaluation_results ?? [];
            const estatesById = new Map(estates.map(estate => [String(estate.id), estate]));
            const buildings = (benchmarkRun?.top ?? []).flatMap(top => {
                const estate = estatesById.get(String(top.id));
                if (!estate) return [];
                const evaluation = evaluationResults.find(item => String(item.id) === String(top.id));
                const street = typeof estate.address === 'string' ? estate.address.trim() : '';
                const houseNumber = estate.house_number == null ? '' : String(estate.house_number).trim();
                const energy = estate.energy_scores as Record<string, number | null> | undefined;
                const proximity = estate.proximity_scores as Record<string, number | null> | undefined;
                return [{
                    id: String(estate.id),
                    address: [street, houseNumber].filter(Boolean).join(' ') || undefined,
                    coordinates: { lat: estate.latitude, lng: estate.longitude },
                    surface_area: typeof estate.surface_area === 'number' ? estate.surface_area : undefined,
                    construction_year: typeof estate.construction_period === 'string' ? estate.construction_period : undefined,
                    energy_class: typeof estate.energy_class === 'string' ? estate.energy_class : undefined,
                    property_type: typeof estate.property_type === 'string' ? estate.property_type : undefined,
                    omi_zone: typeof estate.omi_zone === 'string' ? estate.omi_zone : undefined,
                    cadastral_sheet: estate.cadastral_sheet != null ? String(estate.cadastral_sheet) : undefined,
                    cadastral_parcel: estate.cadastral_parcel != null ? String(estate.cadastral_parcel) : undefined,
                    cadastral_subaltern: estate.cadastral_subaltern != null ? String(estate.cadastral_subaltern) : undefined,
                    cadastral_units_count: typeof estate.cadastral_units_count === 'number' ? estate.cadastral_units_count : undefined,
                    id_list: typeof estate.id_list === 'string' ? estate.id_list : undefined,
                    effective_date: typeof estate.effective_date === 'string' ? estate.effective_date : undefined,
                    start_date: typeof estate.effective_date === 'string' ? estate.effective_date : undefined,
                    is_evaluated: Boolean(evaluation),
                    is_match: true,
                    is_meta_building: estate.is_meta_estate === true,
                    meta_building: estate.is_meta_estate === true,
                    score: top.score,
                    evaluation_text: evaluation?.evaluation_text,
                    pros: evaluation?.pros,
                    cons: evaluation?.cons,
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
                    ? `Showing the precomputed refined benchmark output for ${scenario.case_id} (${benchmarkRun.run_id}). ${buildings.length} of the top 10 properties were matched to the local inventory. ${evaluationResults.length ? `${evaluationResults.length} saved EvaluationAgent results are available.` : 'This older benchmark artifact does not contain saved EvaluationAgent results.'}`
                    : `No completed refined benchmark run is available for ${scenario.case_id}. The local inventory is shown without scenario-specific results.`,
                agent_trace: benchmarkRun?.agent_trace ?? [],
                gemini_responses: {
                    analysis_mode: 'demo',
                    dataset_key: 'benchmark',
                    sql_generation: benchmarkRun?.final_sql
                        ? { sql_query: benchmarkRun.final_sql, response: benchmarkRun.final_sql }
                        : undefined,
                    evaluation: { results: evaluationResults },
                },
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
        if (match[2] === 'agent_steps') {
            const sqlQuery = runs.get(match[1])?.gemini_responses?.sql_generation?.sql_query;
            return respond({
                run_id: match[1],
                steps: typeof sqlQuery === 'string' ? [{ key: 'sql_generation', response: { sql_query: sqlQuery } }] : [],
            });
        }
        if (match[2] === 'gemini_responses') return respond(runs.get(match[1])?.gemini_responses ?? {});
        return respond(runs.get(match[1]));
    }
    if (path === '/map/config') return respond({ center: { lat: 45.07, lng: 7.69 }, zoom: 12, style: '', attribution: 'Local simulation' });
    if (path.startsWith('/map/overlays/')) return respond({ type: 'FeatureCollection', features: [] });
    if (path === '/map/markers' || path === '/map/markers-lite') return respond([]);
    if (path === '/layers/pois') {
        const catalog = await getPOICatalog();
        const requested = String(config.params?.categories ?? '')
            .split('|').map(category => category.trim().toLowerCase()).filter(Boolean);
        const categories = requested.length ? requested : Object.keys(POI_PRESENTATION);
        const unknown = categories.filter(category => !POI_PRESENTATION[category]);
        if (unknown.length) return fail(`Unsupported POI categories: ${unknown.join(', ')}`);

        const boundsKeys = ['min_lat', 'max_lat', 'min_lon', 'max_lon'] as const;
        const hasAnyBound = boundsKeys.some(key => config.params?.[key] !== undefined);
        const hasAllBounds = boundsKeys.every(key => Number.isFinite(Number(config.params?.[key])));
        if (hasAnyBound && !hasAllBounds) return fail('All four viewport bounds must be provided.');
        const bounds = hasAllBounds ? {
            min_lat: Number(config.params?.min_lat), max_lat: Number(config.params?.max_lat),
            min_lon: Number(config.params?.min_lon), max_lon: Number(config.params?.max_lon),
        } : null;
        const requestedLimit = Number(config.params?.limit) || 1000;
        const limit = Math.max(1, Math.min(1000, requestedLimit));
        const pois = [];
        for (const category of categories) {
            const presentation = POI_PRESENTATION[category];
            for (const [amenityType, entries] of Object.entries(catalog[category] ?? {})) {
                for (const entry of entries) {
                    const { lat, lon } = entry;
                    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
                    if (bounds && (lat < bounds.min_lat || lat > bounds.max_lat || lon < bounds.min_lon || lon > bounds.max_lon)) continue;
                    pois.push({
                        id: entry.id ?? `${category}:${amenityType}:${lat}:${lon}`,
                        lat, lon,
                        name: amenityType.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase()),
                        category,
                        ...presentation,
                    });
                    if (pois.length >= limit) break;
                }
                if (pois.length >= limit) break;
            }
            if (pois.length >= limit) break;
        }
        return respond({ count: pois.length, categories, pois });
    }
    if (path === '/buildings') return respond({ buildings: [], total: 0, limit: 0, offset: 0, has_more: false });
    if (path === '/logs/stream') return respond({ events: [], last_id: 0 });
    if (path === '/logs/traces' || (path.startsWith('/feedback/') && method === 'get')) return respond([]);
    return fail(`Unavailable in local simulation: ${method.toUpperCase()} ${path}`);
};
