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

Il sorgente [EDBT](../../../paper/edbt-paper-template.tex) è una **bozza ricostruita**, distinta dal [manoscritto MURENA originale](../references/paper/guide.md): autori e affiliazioni sono da confermare e il testo riporta ora risultati preliminari del benchmark a tre condizioni (115 run completati su 123 eseguiti e 304 pianificati). Il suo contributo proposto è il chiarimento conversazionale prima dell'analisi; la valutazione comparativa distingue il protocollo pianificato dai risultati osservati, senza attribuire rilevanza indipendentemente verificata al ranking oracle. I dettagli delle esecuzioni effettive e dei limiti degli scenari sono nel [benchmark conversazionale](edbt-conversational-benchmark.md).

## Confronto statico, 2026-11-17

| Affermazione della bozza | Riscontro e limite |
|---|---|
| Chiarimento pre-analisi, sei dimensioni, omissioni e non-preferenze esplicite | Coerente con il servizio di chiarimento; è abilitato per default e configurabile (`ENABLE_SAGE_CLARIFICATION`). Le risposte sono interpretate da un LLM: la conservazione di vincoli e negazioni descrive il comportamento desiderato, non una garanzia dimostrata per ogni input. |
| Priorità ispirata a EVPI con penalità di ripetizione | Il codice calcola un punteggio euristico con penalità di ridondanza; non dimostra probabilità calibrate o una riduzione dei turni. Il limite predefinito è sei turni: una sessione può bloccarsi senza completamento. |
| Revisione e approvazione della query prima dell'analisi | L'interfaccia permette modifica e conferma della query consolidata. La formulazione del paper presuppone il percorso con chiarimento abilitato. |
| Catalogo con otto esempi di destinazione | Gli otto casi sono la base degli scenari controllati e coincidono con il catalogo runtime attuale (`normativa.json` contiene 8 casi, verificato il 2026-11-17; una versione precedente ne conteneva 46). Il matching non certifica l'applicabilità normativa. |
| 40 omissioni, otto controlli e suite separata di 24 casi | La struttura è documentata negli scenari. Il checksum sorgente v2 è stato riallineato e il validatore statico è passato; vedere il benchmark per il contesto e i limiti della verifica. |
| Confronto one-shot, query raffinata e oracle; F1 atomico, Jaccard top-5 e RBO | **Protocollo proposto**, non capacità completa del runner attuale: la CLI esegue solo la condizione conversazionale e non realizza tale confronto o tutte le metriche dichiarate. Non interpretare la sezione come esperimento già eseguito. |

La revisione è basata sulla lettura statica dei componenti pertinenti, non su una verifica esaustiva di ogni affermazione né su nuove esecuzioni. Il comportamento dipende da modello, configurazione e dati; prima della sottomissione occorre verificare i percorsi dimostrativi effettivi e distinguere chiaramente implementazione e valutazione pianificata.

## Perimetro della presentazione, 2026-11-17

Il manoscritto descrive un unico scenario dimostrativo preparato: conversione in nursery (`MS02_k2`), con richiesta e risposte prestabilite presentate dal dimostratore. Rimossa la distinzione tra percorso guidato e percorso aperto, inclusa la promessa di interazioni libere del pubblico, da abstract, contributi e sezione dimostrativa; aggiornate le didascalie. È una decisione sulla presentazione, non una modifica del chiarimento implementato o del protocollo sperimentale. Le schermate e i risultati della sessione backend già registrata restano evidenze storiche distinte dalla modalità frontend offline, che simula il dialogo senza immobili. Nessun nuovo esperimento o risultato scientifico aggiunto.

PDF rigenerato dai sorgenti finali con Tectonic in una copia temporanea di `paper/`: 3 pagine comprese figure e bibliografia. Controllati testo estratto e tutte le pagine rasterizzate, senza regressioni maggiori; avviso minore di overfull verticale (1,69 pt).

## Presentazione del benchmark senza etichette di versione, 2026-11-17

Nel paper il benchmark è descritto direttamente tramite scenari, condizioni e metriche, senza etichette v3/v2/v1 o confronti con definizioni precedenti. Rimossa la suite storica di 24 scenari dall'abstract e dalla valutazione; i suoi risultati e limiti restano nel registro di ricerca e negli artefatti originari. Il testo non attribuisce quei risultati al protocollo corrente: il blocco dei risultati comparativi resta non compilato. La conclusione indica la dipendenza del rilevamento delle ambiguità dall'interpretazione LLM, senza riproporre il confronto empirico con il rilevamento delle omissioni proveniente dalla suite rimossa. Note editoriali e README del paper allineate; definizioni sperimentali, dati e risultati originali non modificati.

PDF rigenerato dopo queste modifiche con Tectonic e verificato su tutte le pagine: 3 pagine; nessun errore di compilazione o overfull segnalato.

## Integrazione dei risultati remoti, 2026-11-17

Integrato il commit `bb02883` con gli artefatti e i risultati preliminari del benchmark (113/304 run), mantenendo le scelte editoriali locali: unico scenario preparato e nessuna etichetta di versione o suite precedente nel manoscritto. I risultati sostituiscono il blocco non compilato descritto nelle note precedenti; tabella, figura e abstract ora riflettono gli output importati, con copertura incompleta dichiarata. Nessuna nuova esecuzione sperimentale in questa integrazione. La cronologia e le distinzioni tra benchmark restano nel registro di ricerca.

PDF rigenerato dopo l'integrazione e controllato visivamente: 4 pagine incluse figure, tabella e bibliografia; nessun errore di compilazione, avviso minore di overfull verticale (1,17 pt). Verificati nell'indice importato 113 record completati, con ripartizione 54 refined / 43 one-shot / 16 oracle.

## Risultati della serie completa Haiku, 2026-11-17

I risultati della serie parziale (115/123 run) sono stati sostituiti nel paper da quelli della serie completa con Claude Haiku 5.5. Riguarda abstract, paragrafi Execution e Results, Tabella 1, Figura 3 ed esempio delle tre condizioni. La serie completa ha 304/304 run e tutti gli 8 intenti in ogni cella.

- Il testo non nomina il modello, per scelta editoriale.
- Il paragrafo Execution segnala che un'esecuzione parziale precedente, con un altro backend LLM, è stata fermata per latenza e non è combinata.
- Rimosse le cautele sulla copertura parziale, non più pertinenti.
- La legenda della Figura 3 è stata spostata sopra il grafico: nella posizione precedente copriva il punto one-shot a k=1.

PDF rigenerato con Tectonic e controllato visivamente: 4 pagine. Resta un overfull verticale di 1,34 pt nella routine di output, preesistente: la versione precedente ne segnalava 24,7 pt.
