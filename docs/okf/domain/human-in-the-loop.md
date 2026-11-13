---
type: Domain Concept
title: Human-in-the-Loop e interpretabilità
description: Ruolo dell’esperto, score explainability, feedback e limiti della decisione automatica.
tags:
- domain
- hitl
- xai
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
- resource: ../../../frontend/src/components/agent/FeedbackPanel.tsx
  title: 'MURENA repository: frontend/src/components/agent/FeedbackPanel.tsx'
- resource: ../../../frontend/src/components/building/AIEvaluationCard.tsx
  title: 'MURENA repository: frontend/src/components/building/AIEvaluationCard.tsx'
- resource: ../../../backend/app/api/v1/endpoints/feedback.py
  title: 'MURENA repository: backend/app/api/v1/endpoints/feedback.py'
---

# Human-in-the-Loop e interpretabilità

MURENA propone una shortlist ordinata e motivata; la decisione finale è affidata a un esperto. Il paper descrive un'interfaccia con breakdown dei pesi, grafici radar, motivazioni, *pros* e *cons* e possibilità di override umano.

## Evidenze nel frontend

`AIEvaluationCard`, i dettagli degli edifici, le viste map e i dettagli delle run rendono ispezionabili diversi aspetti della valutazione. `FeedbackPanel` e gli endpoint `feedback` registrano valutazioni relative all'app, agli agenti o ai singoli edifici. Nella mappa, l'ispezione contestuale è limitata alla query SQL della run; le tracce sono consultabili nelle viste di log e dettaglio run.

## Regole d'uso

- Presentare gli score come indici di prioritizzazione, non come esiti vincolanti di conformità.
- Conservare ID run, criteri di query e motivazioni per ricostruire una decisione.
- Verificare da fonti ufficiali eventuali prescrizioni edilizie o normative prima di usare l'esito per una decisione reale.
- Trattare le spiegazioni qualitative LLM come **ipotesi verificabili** sui dati, soprattutto quando citano un rischio non direttamente rappresentato nello schema.
