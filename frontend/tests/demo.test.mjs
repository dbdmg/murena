import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
import axios from 'axios';

// Compile the TS fixtures in memory using the project's existing compiler.
async function moduleUrl(file, replacements = {}) {
    let source = await readFile(new URL(file, import.meta.url), 'utf8');
    for (const [from, to] of Object.entries(replacements)) source = source.replaceAll(from, to);
    const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
    return `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
}
const utilsUrl = await moduleUrl('../src/utils/demoScenarios.ts');
const { parseDemoScenarios } = await import(utilsUrl);
const backendUrl = await moduleUrl('../src/demo/backend.ts', {
    "'axios'": JSON.stringify(import.meta.resolve('axios')),
    "'../utils/demoScenarios'": JSON.stringify(utilsUrl),
});
const { demoAdapter, selectDemoScenario, loadDemoConversation } = await import(backendUrl);
const client = axios.create({ adapter: demoAdapter });
const catalog = JSON.parse(await readFile(new URL('../../backend/experiments/data/scenarios_v3/scenario_triplets.json', import.meta.url)));
const scenarios = catalog.scenarios.flatMap(group => group.variants);

test('scenario contract accepts v3 and rejects malformed or duplicate records', () => {
    assert.equal(scenarios.length, 256);
    assert.equal(parseDemoScenarios(catalog).length, 256);
    const selected = { scenarios: catalog.scenarios.map(g => ({ ...g, enabled: g.id === 'S01' })) };
    assert.equal(parseDemoScenarios(selected).length, 32);
    assert.ok(parseDemoScenarios(selected).every(s => s.case_id.startsWith('S01_')));
    assert.deepEqual(parseDemoScenarios({ scenarios: catalog.scenarios.map(g => ({ ...g, enabled: false })) }), []);
    assert.throws(() => parseDemoScenarios({ scenarios: [{ ...catalog.scenarios[0], enabled: 'false' }] }));
    assert.throws(() => parseDemoScenarios([{ ...scenarios[0], enabled: true }]));
    assert.equal(parseDemoScenarios([scenarios[0]]).length, 1);
    for (const invalid of [null, [], {}, [scenarios[0], scenarios[0]], [{ ...scenarios[0], oracle: {} }], [{ ...scenarios[0], missing_dimensions: ['unknown'] }]]) {
        assert.throws(() => parseDemoScenarios(invalid));
    }
});

test('all 256 scripted conversations reach review and local completion', async () => {
    for (const scenario of scenarios) {
        selectDemoScenario(scenario);
        let { data } = await client.post('/analysis', { query: scenario.conversational.initial_query });
        for (const dimension of scenario.missing_dimensions) {
            assert.equal(data.status, 'ASK', scenario.case_id);
            const answer = scenario.conversational.simulated_user_answers_by_dimension[dimension];
            ({ data } = await client.post('/analysis', { clarification_session_id: data.session_id, clarification_response: answer }));
        }
        assert.equal(data.status, 'REVIEW', scenario.case_id);
        assert.ok(data.refined_query.startsWith(scenario.conversational.initial_query));
        const { data: run } = await client.post('/analysis', { clarification_session_id: data.session_id, clarification_confirmed: true, query: data.refined_query });
        const { data: results } = await client.get(`/analysis/${run.run_id}`);
        assert.equal(results.status, 'completed');
        assert.deepEqual(results.buildings, []);
        assert.match(results.broker_summary, /No backend or LLM was contacted/);
        await client.delete(`/analysis/${run.run_id}`);
        await assert.rejects(client.get(`/analysis/${run.run_id}`));
    }
});

test('oracle skips scripted omissions, unknown endpoints fail without network fallback', async () => {
    selectDemoScenario(scenarios[1]);
    const { data } = await client.post('/analysis', { query: scenarios[1].oracle.query });
    assert.equal(data.status, 'REVIEW');
    await assert.rejects(client.get('https://example.invalid/api/v1/unknown'), /Unavailable in offline demo/);
    await assert.rejects(client.post('/auth/login', { username: 'demo' }), /Unavailable in offline demo/);
});

test('offline demo POI endpoint loads categorized records and filters by viewport and limit', async () => {
    const poiCatalog = JSON.parse(await readFile(new URL('../public/data/pois_by_category.json', import.meta.url), 'utf8'));
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
        assert.equal(url, '/data/pois_by_category.json');
        return { ok: true, json: async () => poiCatalog };
    };
    try {
        const { data } = await client.get('/layers/pois', {
            params: {
                categories: 'healthcare|green',
                min_lat: 45.05, max_lat: 45.10,
                min_lon: 7.60, max_lon: 7.72,
                limit: 75,
            },
        });
        assert.ok(data.count > 0);
        assert.ok(data.count <= 75);
        assert.deepEqual(data.categories, ['healthcare', 'green']);
        assert.ok(data.pois.every(poi =>
            poi.lat >= 45.05 && poi.lat <= 45.10 &&
            poi.lon >= 7.60 && poi.lon <= 7.72 &&
            ['healthcare', 'green'].includes(poi.category) && poi.icon && poi.color
        ));
    } finally {
        globalThis.fetch = originalFetch;
    }
});

test('scenario selection preloads every turn and a confirmable review for all 256 cases', async () => {
    for (const scenario of scenarios) {
        const loaded = loadDemoConversation(scenario);
        assert.equal(loaded.messages.length, 1 + 2 * scenario.missing_dimensions.length);
        assert.equal(loaded.messages[0].content, scenario.conversational.initial_query);
        scenario.missing_dimensions.forEach((dimension, i) => {
            assert.equal(loaded.messages[2 * i + 1].role, 'assistant');
            assert.equal(loaded.messages[2 * i + 2].content, scenario.conversational.simulated_user_answers_by_dimension[dimension]);
        });
        const { data: review } = await client.post('/analysis', { clarification_session_id: loaded.sessionId });
        assert.equal(review.status, 'REVIEW');
        assert.equal(review.refined_query, loaded.reviewQuery);
        const next = loadDemoConversation(scenario);
        await assert.rejects(client.post('/analysis', { clarification_session_id: loaded.sessionId }), /expired/);
        const { data: run } = await client.post('/analysis', { clarification_session_id: next.sessionId, clarification_confirmed: true, query: next.reviewQuery });
        assert.equal(run.status, 'completed');
        await client.delete(`/analysis/${run.run_id}`);
    }
});
