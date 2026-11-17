---
type: Research Assessment
title: Bozza Conversational MURENA e confronto con il codice
description: Provenienza, perimetro e verifica statica della bozza EDBT rispetto all'implementazione.
tags:
- research
- edbt
- provenance
sources:
- resource: ../../../paper/edbt-paper-template.tex
  title: Bozza EDBT Conversational MURENA
- resource: ../../../paper/README.md
  title: Provenienza della bozza ricostruita
- resource: ../../../paper/README-EDITORIAL.md
  title: Note editoriali della bozza
- resource: ../../../backend/app/services/sage_clarification/service.py
  title: Servizio di chiarimento
- resource: ../../../backend/app/services/sage_clarification/uncertainty.py
  title: Calcolo euristico della priorità
- resource: ../../../backend/experiments/benchmark_cli.py
  title: Runner sperimentale
- resource: ../../../frontend/src/pages/SearchPage.tsx
  title: Interfaccia di chiarimento e revisione
---

# Bozza Conversational MURENA e confronto con il codice

Il sorgente [EDBT](../../../paper/edbt-paper-template.tex) è una **bozza ricostruita**, distinta dal [manoscritto MURENA originale](../references/paper/guide.md): autori e affiliazioni sono da confermare e il testo non riporta risultati misurati. Il suo contributo proposto è il chiarimento conversazionale prima dell'analisi; la valutazione comparativa descritta è un disegno sperimentale, non un risultato pubblicato o verificato. I dettagli delle esecuzioni effettive e dei limiti degli scenari sono nel [benchmark conversazionale](edbt-conversational-benchmark.md).

## Confronto statico, 2026-11-17

| Affermazione della bozza | Riscontro e limite |
|---|---|
| Chiarimento pre-analisi, sei dimensioni, omissioni e non-preferenze esplicite | Coerente con il servizio di chiarimento; è abilitato per default e configurabile (`ENABLE_SAGE_CLARIFICATION`). Le risposte sono interpretate da un LLM: la conservazione di vincoli e negazioni descrive il comportamento desiderato, non una garanzia dimostrata per ogni input. |
| Priorità ispirata a EVPI con penalità di ripetizione | Il codice calcola un punteggio euristico con penalità di ridondanza; non dimostra probabilità calibrate o una riduzione dei turni. Il limite predefinito è sei turni: una sessione può bloccarsi senza completamento. |
| Revisione e approvazione della query prima dell'analisi | L'interfaccia permette modifica e conferma della query consolidata. La formulazione del paper presuppone il percorso con chiarimento abilitato. |
| Catalogo con otto esempi di destinazione | Gli otto casi sono la base degli scenari controllati, non l'intero catalogo runtime, che contiene 46 casi. Il matching non certifica l'applicabilità normativa. |
| 40 omissioni, otto controlli e suite separata di 24 casi | La struttura è documentata negli scenari. Il validatore sulla copia v2 presente segnala un checksum sorgente non allineato; vedere il benchmark per il contesto. |
| Confronto one-shot, query raffinata e oracle; F1 atomico, Jaccard top-5 e RBO | **Protocollo proposto**, non capacità completa del runner attuale: la CLI esegue solo la condizione conversazionale e non realizza tale confronto o tutte le metriche dichiarate. Non interpretare la sezione come esperimento già eseguito. |

La revisione è basata sulla lettura statica dei componenti pertinenti, non su una verifica esaustiva di ogni affermazione né su nuove esecuzioni. Il comportamento dipende da modello, configurazione e dati; prima della sottomissione occorre verificare i percorsi dimostrativi effettivi e distinguere chiaramente implementazione e valutazione pianificata.
