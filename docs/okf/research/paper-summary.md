---
type: Research Reference
title: Sintesi del paper MURENA
description: Domanda di ricerca, metodo scientifico e contributo della piattaforma.
tags:
- research
- paper
- murena
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
- resource: ../references/paper/metadata.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Sintesi del paper MURENA

## Metadati

**Titolo:** *MURENA, a MUlti-Agent LLM pipeline for large-scale Real Estate maNAgement*. Manoscritto fornito come sorgente LaTeX con template ECML/PKDD.

## Problema

L'analisi di grandi patrimoni immobiliari implica incrociare vincoli tecnici, energetici, territoriali e normativi da fonti eterogenee. Il paper propone che i modelli linguistici agiscano come **controllori semantici**, delegando a SQL e calcolo numerico la selezione e il punteggio e lasciando all'esperto l'ultima decisione.

## Contributi dichiarati

- Architettura multi-agente specializzata in cinque dimensioni immobiliari.
- Integrazione di EPC/APE, aggregazione catastale, indicatori di accessibilità OSM e contesto OMI.
- Zero-addition policy per la composizione SQL.
- Pesi armonici e scoring multi-criterio interpretabile con supporto visuale Human-in-the-Loop.
- Valutazione su query combinatorie e scenari reali tramite esperti.

Le affermazioni sperimentali sono riportate separatamente in [risultati](benchmarks.md), mentre le condizioni per riprodurre la valutazione sono in [reproduction](reproduction.md).
