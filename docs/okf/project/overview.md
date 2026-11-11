---
type: Project Overview
title: 'MURENA: panoramica'
description: Scopo, confini, componenti e modalità di utilizzo del progetto full-stack.
tags:
- murena
- project
- overview
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
---

# MURENA: panoramica

MURENA (MUlti-Agent LLM pipeline for large-scale Real Estate maNAgement) è una piattaforma **Human-in-the-Loop** per ricerca, analisi e ranking di immobili a partire da requisiti espressi in linguaggio naturale. Il risultato è una shortlist di edifici con punteggi trasparenti, motivazioni e una visualizzazione cartografica.

## Confini dell'applicazione

- **API e servizi:** FastAPI; autenticazione, esecuzione delle analisi, accesso a edifici e geodati, feedback, log e WebSocket.
- **Motore di analisi:** agenti LLM coordinati da LangGraph, query SQL su DuckDB, ranking numerico, valutazione e sintesi.
- **Interfaccia:** React + TypeScript + Vite; ricerca, elaborazione, mappa, cronologia, tracce e configurazione.
- **Persistenza:** SQLite con SQLAlchemy per utenti, run e feedback; Parquet interrogato con DuckDB per l'inventario immobili.
- **Ricerca:** esperimenti e protocolli valutativi descritti nel manoscritto, **non** automaticamente rappresentativi del dataset demo.

## Principio di separazione

Gli LLM interpretano l'intento e producono rappresentazioni strutturate. L'applicazione esegue filtri su dati tabellari e aggrega i punteggi in codice. L'output rimane un **supporto alla decisione**, non una certificazione legale, immobiliare o energetica.

## Navigazione

- [Architettura](../architecture/system.md) · [Flusso end-to-end](../architecture/analysis-flow.md)
- [Contratti API](../api/contracts.md) · [Interfaccia React](../frontend/ui-routes.md)
- [Dataset: ricerca vs demo](../data/datasets-and-lineage.md) · [Risultati del paper](../research/benchmarks.md)
- [Avvio locale](../operations/quickstart.md)
