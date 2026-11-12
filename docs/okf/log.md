# MURENA OKF Update Log

## 2026-11-12

* **Correzione dei dati per valutazione e distanza**: il payload dell'EvaluationAgent include i nomi canonici del Parquet (indirizzo, tipologia, classe energetica e indicatori di prossimità) oltre agli alias legacy. `calculate_travel_times_df` accetta `latitude`/`longitude` e `latitudine`/`longitudine`, evitando distanze `N/D` causate dal solo disallineamento dei nomi. Algoritmi di ranking e scoring invariati.
* **Fonte normativa collegata**: `backend/docs/knowledge/normativa/normativa.json` viene caricato dal RegulatoryAgent; allineato il placeholder del prompt (`regulatory_documents`) al nome usato dal loader. La fonte elenca cinque casi d'uso, senza una voce per studentati.
* **Layout della chat SAGE**: il pannello di chiarimento è vincolato all'altezza disponibile, con cronologia a scorrimento interno, composer/revisione fissi, controllo comprimi/espandi e ridimensionamento verticale del pannello.
* **Interpretazione senza regex**: rimosse le euristiche lessicali per tipologia, requisiti energetici e luoghi; il parser e gli estrattori LLM applicano le istruzioni strutturate nei prompt. Anche il caricatore dei template Markdown usa solo operazioni su stringhe.
* **Revisione della query prima dell'analisi**: completati i chiarimenti, `POST /analysis` restituisce `REVIEW` con il testo raffinato. Il frontend lo mostra modificabile e avvia la pipeline invariata solo dopo la conferma; il backend valida e consuma una sola volta la sessione pronta.
* **Riscrittura naturale con LLM**: sostituita la concatenazione di metadati alle risposte con un prompt dedicato che integra i chiarimenti confermati nel testo originale e restituisce direttamente la query finale in linguaggio naturale.
* **Suggerimenti geografici**: per luoghi ambigui, il modello può proporre fino a tre città plausibili, presentate come ipotesi non esaustive con l'opzione di indicarne un'altra. La selezione supporta anche risposte indirette come “la prima”; il calcolo EVPI include l'esito aperto.
* **Classificazione semantica delle risposte**: rimossi gli elenchi di frasi per rilevare rinunce, incertezza o rifiuto di alternative. Un prompt LLM classifica l'intento della risposta e fornisce evidenza; il codice applica l'aggiornamento strutturato senza pattern lessicali.

## 2026-11-11

* **SAGE clarification wrapper**: documentato il passaggio opzionale pre-analisi, la persistenza delle sessioni e il contratto API; il grafo e gli algoritmi MURENA restano invariati.
* **Conferma delle dimensioni omesse**: quando SAGE è attivo, l'assenza di una dimensione non equivale più a `NOT_REQUESTED`; resta `UNCONFIRMED_ABSENT` e viene chiesta una dimensione per turno. Le risposte aggiornano solo il requisito con evidenza esplicita; un'assenza di evidenza lascia la domanda irrisolta. Il limite predefinito passa a sei turni per coprire le sei dimensioni del modello di query.
* **UI conversazionale SAGE**: `/` conserva query, domande e risposte in un thread visivo durante i turni di chiarimento, con composer dedicato, stato di attesa e gestione di `BLOCKED`. Le domande sulle omissioni sono una dimensione per turno; l'analisi viene avviata solo al completamento del chiarimento.
* **Domande propositive**: i chiarimenti mostrano esempi specifici per tipologia, destinazione, posizione, vincoli edilizi, energia e prossimità. Gli esempi guidano la risposta ma non sono requisiti finché l'utente non li conferma.
* **Interpretazione guidata dal prompt**: chiariti gli esempi del parser per tipologia fisica, requisiti energetici qualitativi e landmark senza città. La semantica delle dimensioni resta al modello; il servizio non usa regex o fallback lessicali per dedurre requisiti.
* **Prompt SAGE esternalizzati**: istruzioni per parsing, interpretazione delle risposte e controllo delle contraddizioni spostate da `service.py` in `sage_clarification/prompts.md`; loader dedicato per i placeholder runtime.
* **Luoghi nominati**: un riferimento esplicito come “vicino a Porta Nuova” non viene trattato come località omessa; se manca la città, la domanda chiede di disambiguare quel luogo specifico.
* **Coerenza per dimensione**: risposte a dimensioni omesse vengono estratte direttamente; gli altri controlli distinguono tipologia fisica e destinazione futura, evitando di bloccare una conversione come “uffici → studentato”.
* **Provider Codex centralizzato**: `codex_exec` aggiunto alla factory LLM condivisa con supporto a testo e output JSON Schema per tutti gli agenti e SAGE. La configurazione locale seleziona `gpt-6-luna` con reasoning `low`; i prompt restano nel grafo esistente. Il CLI gira in directory temporanea read-only, senza strumenti, e non riceve la API key applicativa. Richiede il login ChatGPT del CLI. Test automatizzati e chiamata live della factory completati; una prova minima ha usato circa 8.5k token d'ingresso, valore variabile.
* **Method caveat**: EVPI usa partizioni finite con pesi uniformi euristici; i valori non sono probabilità calibrate dell'intento dell'utente.

## 2026-11-10

* **Creation**: bundle iniziale OKF v0.2, con concetti per backend, frontend, dati, API, agenti, paper, benchmark e operazioni.
* **Provenance**: allegati i sorgenti LaTeX del manoscritto e i riferimenti relativi ai file del progetto.
* **Validation**: verifica automatica di formato e link locali inclusa nello ZIP; test runtime e riproduzione dei benchmark non eseguiti.
