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
---

# Fonti e livelli di evidenza

## Origine delle informazioni

1. **Codice fornito** (`backend/`, `frontend/`, launcher e configurazioni): supporta la descrizione della struttura e dei percorsi implementativi. È stata svolta **lettura statica**, non esecuzione dell'applicazione.
2. **Documentazione nel repository** (`README.md`, `AGENTS.md`): descrive uso previsto e comandi; può essere meno aggiornata del codice.
3. **Manoscritto LaTeX caricato** (`references/paper/paper.tex`, più `metadata.tex` e supplemento): supporta metodo, dataset di ricerca e risultati sperimentali. Le prestazioni sono **rivendicazioni del paper**, non benchmark replicati per questo bundle.

## Casi che non vanno confusi

| Aspetto | Demo inclusa / avvio predefinito | Setup di ricerca del paper |
|---|---|---|
| Dati | Generazione sintetica di 1.500 edifici a Torino | Registro EPC/APE reale vicino a 90.000 unità/edifici analizzati |
| Scopo | Eseguire UI e API senza i dati APE grezzi | Valutazione scientifica e scenari istituzionali |
| Riproducibilità | Script demo nel repository | Dataset e risorse APE/OSM originali potrebbero non essere distribuiti |
| Metriche | Nessuna garanzia di conservare i numeri del paper | Valori riportati in [benchmark](../research/benchmarks.md) |

## Stato della verifica

I concetti OKF hanno `sources` tracciabili e un timestamp di generazione; non hanno un campo `verified`, perché non è stato eseguito un controllo funzionale end-to-end né un audit di un esperto di dominio. Nessuna credenziale o dato riservato è incluso nel bundle.

Quando codice e paper divergono, per una **modifica software** privilegiare il codice; per una **citazione scientifica** privilegiare il paper, esplicitando il contesto.
