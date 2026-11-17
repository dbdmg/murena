---
type: Assessment
title: Code review per il demo paper EDBT (novembre 2026)
description: Esiti della revisione approfondita di pipeline, chiarimento SAGE, interfaccia e harness sperimentale, con stato delle correzioni.
tags:
- quality
- code-review
- experiments
- edbt
sources:
- resource: ../../../backend/app/services/llm/agents/graph_agent.py
  title: Orchestratore LangGraph, ranking e rilassamento
- resource: ../../../backend/app/services/llm/agents/regulatory_agent.py
  title: RegulatoryAgent
- resource: ../../../backend/app/services/analysis/executor.py
  title: Esecuzione SQL su DuckDB
- resource: ../../../backend/app/data/loaders.py
  title: Loader e geocoding
- resource: ../../../backend/app/services/sage_clarification/service.py
  title: Servizio di chiarimento
- resource: ../../../backend/app/api/v1/endpoints/analysis.py
  title: Endpoint di analisi e chiarimento
- resource: ../../../frontend/src/pages/SearchPage.tsx
  title: UI di chiarimento e revisione
- resource: ../../../backend/experiments/benchmark_cli.py
  title: Runner sperimentale
---

# Code review per il demo paper EDBT (novembre 2026)

## Perimetro e metodo

Revisione del 2026-11-17, svolta da quattro revisori indipendenti in sola lettura (pipeline di analisi, chiarimento SAGE con API e UI, harness sperimentale, bozza del paper). Ogni difetto è stato verificato leggendo il percorso del codice e, dove indicato, con piccoli script locali senza chiamate LLM. Lo scopo era rendere affidabili le metriche del confronto one-shot / refined / oracle e la demo dal vivo. Lo stato delle correzioni è aggiornato in fondo al documento.

## Pipeline di analisi: difetti che alterano i risultati

1. **Score sovrascritto dall'LLM di valutazione**: lo score deterministico del ranking viene arrotondato, passato all'EvaluationAgent e sostituito con il valore che il modello restituisce; il top-10 viene poi riordinato su quel valore. L'ordine dei primi cinque dipende quindi dalla fedeltà con cui il modello ricopia un intero.
2. **Ex aequo risolti in modo arbitrario**: ordinamenti non stabili e senza chiave secondaria. Gli score sono molto discreti (per esempio `ape_score_total` ha 9 valori distinti), e nei run v2 il 5° e il 6° classificato hanno lo stesso score in 84 run su 114. L'ordine finale dipende dall'`ORDER BY` scelto dall'LLM nella SQL, che cambia tra condizioni.
3. **Rilassamento non tracciato**: scatta sotto 10 risultati, può eliminare interi filtri e il flag `relaxation_applied` viene sovrascritto a ogni passaggio; nessuno di questi campi arriva nella risposta API.
4. **Errori degli agenti mascherati**: un'eccezione viene registrata come "agente disattivato per irrilevanza"; un RankingAgent fallito produce pesi uniformi senza segnalazione.
5. **RegulatoryAgent**: il ramo numerico `==` usa variabili non definite (`col_stats`, `diff`) e porta a `regulatory_score = 0` per tutte le righe.
6. **Geocoding**: confronto per sottostringa dei landmark ("Torino" risolto sulle coordinate dell'università, "parco" sul Valentino); errori di Nominatim sotto concorrenza fanno sparire il vincolo di località senza segnalazione.
7. **Percorso di fallback** non segnalato nella risposta, con 500 risultati marcati come corrispondenti.
8. **Sicurezza (media)**: la SQL generata dall'LLM è eseguita senza imporre una singola istruzione `SELECT` e con accesso esterno di DuckDB abilitato.

Determinismo: `AGENT_TEMPERATURE=0.0` per default, ma nessun seed; il provider `codex_exec` ignora la temperatura e applica solo `model_reasoning_effort`. La variabilità tra ripetizioni va quindi misurata, non presunta nulla.

## Chiarimento SAGE, API e interfaccia

- I 10 errori della suite `test_sage_clarification.py` sono dovuti a test non aggiornati (mock privo del prompt `omission_question`, asserzioni in italiano, un placeholder non passato), non a difetti del servizio.
- La definizione di `Cb` nel prompt del parser è troppo larga: "existing building/unit" viene letto come vincolo edilizio (6 run v2). La capienza resta `Cb` per scelta documentata.
- L'endpoint asincrono esegue chiamate LLM bloccanti nel thread dell'event loop.
- Se la prima query è già completa, l'API risponde `REVIEW` ma l'interfaccia non mostra il form di revisione (rischio diretto per la demo).
- Un errore transitorio del modello termina la sessione in `BLOCKED` e la UI perde l'identificativo di sessione.
- Altri: città non ancorata alla risposta dell'utente, domanda geografica ripetuta con opzioni già rifiutate, conferma doppia senza compare-and-set, copia superficiale dello stato JSON della sessione.

## Harness sperimentale

- Un run in cui SAGE non pone domande veniva registrato come errore e non eseguiva l'analisi: tutti i 6 errori v2 (`MS02_k1`, `MS07_k1`) sono di questo tipo.
- `top_ids` includeva immobili non corrispondenti (riempitivi con `is_match=False`).
- Le chiavi di resume ignoravano l'hash dello scenario; il manifest non registrava `use_relaxation`, impostazioni SAGE, commit e hash del dataset.
- F1 del rilevamento pari a 0 quando nulla deve mancare (controlli `k=0`).
- Generatore v2: in 8 scenari su 40 (`MS02_k1`–`k4`, `MS07_k1`–`k3`, `MS08_k3`) l'omissione di `Cb` lascia la capienza nel testo della destinazione; è la causa di 24 delle 30 mancate rilevazioni di `Cb`.

## Stato delle correzioni

**Pipeline di analisi: corrette** (punti 1–8). Score deterministico non più sovrascritto dall'EvaluationAgent; ordinamento stabile con chiavi score, distanza e id; rilassamento, fallback ed errori degli agenti esposti nella risposta; ramo numerico del RegulatoryAgent corretto; landmark per corrispondenza esatta; SQL limitata a una singola istruzione di lettura con accesso esterno di DuckDB disabilitato. Dettagli in [scoring](../data/scoring.md), [SQLAgent](../agents/sql.md), [rilassamento](../agents/relaxation.md) e [geospaziale](../data/geospatial.md). Evidenza: `backend/tests/test_pipeline_fixes.py` (13 test) e suite esistenti senza regressioni. Lasciati invariati: chiavi di stato LangGraph non dichiarate (dichiararle cambierebbe il rilassamento), campionamento casuale come ultima risorsa del fallback.

**Chiarimento, API e UI: corretti.** Test aggiornati, regola `Cb`, errori transitori ritentabili (503), concorrenza (409 e compare-and-set), ancoraggio della città, follow-up sulle ambiguità, timeout client di 180 s per i turni di chiarimento. Dettagli in [chiarimento pre-analisi](../architecture/query-clarification.md). Evidenza: 37 test superati, build TypeScript pulita.

**Harness sperimentale e scenari v3: corretti.** `benchmark_cli.py` esegue le condizioni `refined`, `one_shot` e `oracle` (`--condition`, ripetibile; ordine dei job interleaved con `--seed`; oracle deduplicato per intento base con `--oracle-repeat`; `--dry-run`). Un dialogo senza domande completa il run con `no_clarification=true`; P/R/F1 del rilevamento valgono 1 quando nulla deve mancare; le chiavi di resume includono condizione, modello, unità, ripetizione e hash dell'input; `top` contiene solo immobili corrispondenti con score e distanza; ogni riga di `runs.jsonl` (schema 2) registra SQL pre e post rilassamento, use case, requisiti, estrazioni per agente, flag di rilassamento/fallback, errori degli agenti e tempi separati di chiarimento e analisi. Il manifest registra impostazioni SAGE e LLM, commit, hash del dataset e `use_relaxation`. Nuovo `compare_conditions.py` (metriche di confronto, vedere [benchmark](../research/edbt-conversational-benchmark.md)). Scenari v3 in `backend/experiments/data/scenarios_v3/` con capienza spostata da `D` a `Cb`. Evidenza: 22 test in `backend/tests/test_experiments_metrics.py`, validatore v3 superato, smoke test reale di 4 job (una ripetizione per condizione su `MS02`) completato il 2026-11-17.
