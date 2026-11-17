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
const scenarios = JSON.parse(await readFile(new URL('../../backend/experiments/data/scenarios_v3/scenario_triplets.json', import.meta.url)));

test('scenario contract accepts v3 and rejects malformed or duplicate records', () => {
    assert.equal(parseDemoScenarios(scenarios).length, 48);
    for (const invalid of [null, [], {}, [scenarios[0], scenarios[0]], [{ ...scenarios[0], oracle: {} }], [{ ...scenarios[0], missing_dimensions: ['unknown'] }]]) {
        assert.throws(() => parseDemoScenarios(invalid));
    }
});

test('all 48 scripted conversations reach review and local completion', async () => {
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

test('scenario selection preloads every turn and a confirmable review for all 48 cases', async () => {
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
