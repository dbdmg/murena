---
type: Playbook
title: Test e quality gate
description: Controlli statici, frontend lint/build e valutazioni sperimentali.
tags:
- testing
- quality
- playbook
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../AGENTS.md
  title: 'MURENA repository: AGENTS.md'
- resource: ../../../frontend/package.json
  title: 'MURENA repository: frontend/package.json'
- resource: ../../../backend/tests/test_suite.py
  title: 'MURENA repository: backend/tests/test_suite.py'
- resource: ../../../backend/experiments/reproduce_results.py
  title: 'MURENA repository: backend/experiments/reproduce_results.py'
---

# Test e quality gate

## Controlli frontend

```bash
cd frontend
npm ci
npm run lint
npm run build
```

## Backend e flusso

Verificare serializzazione Pydantic, filtri SQL consentiti, limiti `AnalysisRequest`, retry/relaxation e score con fixture sintetiche. Il repository contiene un harness in `backend/tests/test_suite.py` ma non dichiara una suite pytest di unit test completa.

## Ripetibilità dei risultati

Per il comportamento del sistema LLM confrontare prompt e modello fissati e dataset versionato; leggere il [playbook ricerca](../research/reproduction.md). Evitare di inferire qualità del modello da una singola run manuale.

## Controllo OKF

Per ogni modifica software aggiornare il concept interessato, il suo `sources`, eventuali link, `docs/okf/index.md` e `docs/okf/log.md`; eseguire lo script `verify_okf.py` incluso nello ZIP.
