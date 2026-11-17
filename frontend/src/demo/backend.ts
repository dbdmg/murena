import { AxiosError, type AxiosAdapter } from 'axios';
import type { AnalysisResults } from '../api/types';
import { dimensionLabels } from '../utils/demoScenarios';
import type { DemoScenario, Dimension } from '../utils/demoScenarios';

export const demoUser = { id: 0, username: 'Demo presenter', created_at: '2026-01-01T00:00:00Z' };
let activeScenario: DemoScenario | null = null;
export function selectDemoScenario(scenario: DemoScenario) {
    activeScenario = scenario;
    sessions.clear();
}
const sessions = new Map<string, { remaining: Dimension[]; text: string; turn: number }>();
const runs = new Map<string, AnalysisResults>();

const questionFor = (dimension: Dimension) =>
    `Please specify your requirements for ${dimensionLabels[dimension].toLowerCase()}.`;

/** Load the complete local script and leave its session ready for review. */
export function loadDemoConversation(scenario: DemoScenario) {
    const messages: { role: 'user' | 'assistant'; content: string }[] = [
        { role: 'user', content: scenario.conversational.initial_query },
    ];
    let text = scenario.conversational.initial_query;
    for (const dimension of scenario.missing_dimensions) {
        const answer = scenario.conversational.simulated_user_answers_by_dimension[dimension];
        if (!answer?.trim()) throw new Error(`Missing prepared answer for ${dimension}.`);
        messages.push({ role: 'assistant', content: questionFor(dimension) }, { role: 'user', content: answer });
        text += ` ${answer}`;
    }
    selectDemoScenario(scenario);
    const sessionId = `demo-session-${crypto.randomUUID()}`;
    sessions.set(sessionId, { remaining: [], text, turn: scenario.missing_dimensions.length });
    return { sessionId, messages, reviewQuery: text };
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
            // Oracle text is already complete. Other inputs follow the selected script.
            sessions.set(id, {
                remaining: body.query === activeScenario.oracle.query ? [] : [...activeScenario.missing_dimensions],
                text: body.query, turn: 0,
            });
            body.clarification_session_id = id;
        }
        const id = body.clarification_session_id as string;
        const session = sessions.get(id);
        if (!session) return fail('Demo session expired. Start a new search.');
        if (body.clarification_confirmed) {
            if (session.remaining.length) return fail('Complete the scripted clarification first.');
            const runId = `demo-${crypto.randomUUID()}`;
            const now = new Date().toISOString();
            const result: AnalysisResults = {
                run_id: runId, status: 'completed', query: body.query,
                created_at: now, completed_at: now, buildings: [], location: [],
                broker_summary: 'Offline demo completed. This scenario contains query and answer scripts only; no property results have been preloaded. No backend or LLM was contacted.',
                agent_trace: [],
            };
            runs.set(runId, result);
            sessions.delete(id);
            return respond({ run_id: runId, status: 'completed', created_at: now, message: 'Offline demo completed.' });
        }
        if (body.clarification_response) {
            session.text += ` ${body.clarification_response}`;
            session.remaining.shift();
            session.turn += 1;
        }
        const dimension = session.remaining[0];
        return respond(dimension
            ? { session_id: id, status: 'ASK', turn: session.turn, question: questionFor(dimension) }
            : { session_id: id, status: 'REVIEW', turn: session.turn, refined_query: session.text });
    }
    const match = path.match(/^\/analysis\/([^/]+)(?:\/(agent_steps|gemini_responses))?$/);
    if (match) {
        if (!runs.has(match[1])) return fail('Unknown local demo run. Demo runs are cleared on reload.');
        if (method === 'delete') { runs.delete(match[1]); return respond(null); }
        if (match[2] === 'agent_steps') return respond({ run_id: match[1], steps: [] });
        if (match[2] === 'gemini_responses') return respond({});
        return respond(runs.get(match[1]));
    }
    if (path === '/map/config') return respond({ center: { lat: 45.07, lng: 7.69 }, zoom: 12, style: '', attribution: 'Offline demo' });
    if (path.startsWith('/map/overlays/')) return respond({ type: 'FeatureCollection', features: [] });
    if (path === '/map/markers' || path === '/map/markers-lite') return respond([]);
    if (path === '/layers/pois') return respond({ count: 0, categories: [], pois: [] });
    if (path === '/buildings') return respond({ buildings: [], total: 0, limit: 0, offset: 0, has_more: false });
    if (path === '/logs/stream') return respond({ events: [], last_id: 0 });
    if (path === '/logs/traces' || (path.startsWith('/feedback/') && method === 'get')) return respond([]);
    return fail(`Unavailable in offline demo: ${method.toUpperCase()} ${path}`);
};
