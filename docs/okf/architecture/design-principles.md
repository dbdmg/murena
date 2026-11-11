---
type: Decision Record
title: Principi e compromessi architetturali
description: Motivazioni tecniche, controllabilità ed espliciti trade-off del sistema.
tags:
- decision
- architecture
- explainability
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../AGENTS.md
  title: 'MURENA repository: AGENTS.md'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
- resource: ../../../backend/app/services/analysis/ranking.py
  title: 'MURENA repository: backend/app/services/analysis/ranking.py'
---

# Principi e compromessi architetturali

## Scelte documentate

| Scelta | Ragione | Compromesso |
|---|---|---|
| LLM per intent extraction, SQL + codice per esecuzione | Ridurre ambiguità e rendere verificabili criteri e score | L'interpretazione del requisito può ancora essere errata |
| Agenti per dominio | Separare energy, location, building, proximity e regulatory | Maggiori chiamate/modelli e complessità di orchestrazione |
| DuckDB sopra Parquet | Analisi su file colonnari senza server analitico esterno | Dipendenza dallo schema e dalla presenza del dataset locale |
| SQLite per stato applicativo | Demo semplice da eseguire | Il reset del launcher non preserva utenti e sessioni |
| Punteggi espliciti + radar + pro/contro | Audit umano e spiegazione | Non equivale a validazione normativa/tecnica |
| Dataset sintetico di fallback | UI navigabile senza sorgenti EPC reali | Nessun valore probatorio dei risultati demo |

## Vincoli da preservare nel codice

- La *zero-addition policy* del paper stabilisce che SQL utilizzi condizioni estratte dai technical agent, non nuovi requisiti inventati.
- I punteggi dovrebbero rimanere ricostruibili e confrontabili con dati e pesi usati.
- Esecuzione e osservabilità devono distinguere motivazioni da risultati numerici effettivi.

Queste sono intenzioni di progetto e riferimenti metodologici: il bundle non certifica la correttezza di ogni singola query generata.
