---
type: Reference
title: Fonti e livelli di evidenza
description: Come leggere le affermazioni derivate da codice, README e paper senza confondere demo e risultati.
tags:
- sources
- provenance
- research
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../README.md
  title: 'MURENA repository: README.md'
- resource: ../../../AGENTS.md
  title: 'MURENA repository: AGENTS.md'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
- resource: ../../../backend/docs/knowledge/normativa/normativa.json
  title: Metriche di conversione immobiliare fornite dall'utente
---

# Fonti e livelli di evidenza

## Origine delle informazioni

1. **Codice fornito** (`backend/`, `frontend/`, launcher e configurazioni): supporta la descrizione della struttura e dei percorsi implementativi. È stata svolta **lettura statica**, non esecuzione dell'applicazione.
2. **Documentazione nel repository** (`README.md`, `AGENTS.md`): descrive uso previsto e comandi; può essere meno aggiornata del codice.
3. **Manoscritto LaTeX caricato** (`references/paper/paper.tex`, più `metadata.tex` e supplemento): supporta metodo, dataset di ricerca e risultati sperimentali. Le prestazioni sono **rivendicazioni del paper**, non benchmark replicati per questo bundle.
4. **Metriche di conversione fornite dall'utente** (ora in `backend/docs/knowledge/normativa/normativa.json`): il file è stato spostato nella posizione runtime della normativa precedente; il codice tratta i campi e i relativi status come contenuto di input. Il nome originario e gli status non equivalgono a una verifica legale indipendente da parte di MURENA.
5. **Scenari EDBT**: `backend/experiments/data/scenarios/` contiene 24 casi sintetici di robustezza; `backend/experiments/data/scenarios_v2/` contiene 40 casi a omissione controllata e 8 controlli completi. I file definiscono risposte simulate e query di riferimento, non osservazioni empiriche. La CLI corrente esegue solo la condizione conversational. Per i 24 scenari originari sono documentati 72 run validi del 2026-11-16, con modello, dataset, parametri e limiti descritti nel [benchmark EDBT](../research/edbt-conversational-benchmark.md); non costituiscono un confronto one-shot/oracle. Sulla famiglia v2 è stata completata il 2026-11-17 una singola run end-to-end `MS01_k1`, smoke test non comparativo. Il 2026-11-17 la famiglia v2 è stata rigenerata nel repository (cambia solo il checksum sorgente nel manifest) e il validatore statico è passato; è una verifica strutturale, non un'esecuzione del benchmark. I risultati osservati vanno riferiti all'artefatto, al modello e al dataset specifici e restano distinti dai risultati del manoscritto. Aggiornamento del 2026-11-17: la CLI ora esegue le condizioni `refined`, `one_shot` e `oracle`. Sulla famiglia `scenarios_v3/` (48 scenari) il benchmark a tre condizioni è stato **eseguito parzialmente**: 123 dei 304 run pianificati, di cui 115 completati e 8 falliti per timeout di Codex, poi sospeso per il rallentamento del servizio. I risultati sono **verificati ma preliminari**: copertura di 5–7 intenti su 8 per cella e nessun run oracle per `UC08`. Sono riportati come tali nel paper EDBT e descritti nel [benchmark EDBT](../research/edbt-conversational-benchmark.md). Il confronto con l'oracle misura l'accordo con una query di riferimento, non la rilevanza degli immobili.

## Casi che non vanno confusi

| Aspetto | Demo inclusa / avvio predefinito | Setup di ricerca del paper |
|---|---|---|
| Dati | Generazione sintetica di 1.500 edifici a Torino | Registro EPC/APE reale vicino a 90.000 unità/edifici analizzati |
| Scopo | Eseguire UI e API senza i dati APE grezzi | Valutazione scientifica e scenari istituzionali |
| Riproducibilità | Script demo nel repository | Dataset e risorse APE/OSM originali potrebbero non essere distribuiti |
| Metriche | Nessuna garanzia di conservare i numeri del paper | Valori riportati in [benchmark](../research/benchmarks.md) |

## Stato della verifica

I concetti OKF hanno `sources` tracciabili e un timestamp di generazione; non hanno un campo `verified` e non attestano un audit di un esperto di dominio. Per la CLI benchmark conversazionale è stato eseguito un solo smoke test v2, descritto in [riproduzione](../research/reproduction.md); non equivale a una verifica completa di tutte le funzioni o dei 40 scenari. Nessuna credenziale o dato riservato è incluso nel bundle.

Quando codice e paper divergono, per una **modifica software** privilegiare il codice; per una **citazione scientifica** privilegiare il paper, esplicitando il contesto.

Per il benchmark EDBT distinguere quindi: **scenario sintetico** (input progettato); **ground truth** (query oracle e aspettative curate); **risultato osservato** (output di una specifica esecuzione registrata); **risultato pubblicato** (affermazione attribuita a una pubblicazione). Nessuna di queste categorie sostituisce le altre.
