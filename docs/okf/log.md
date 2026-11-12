# MURENA OKF Update Log

## 2026-11-11

* **SAGE clarification wrapper**: documentato il passaggio opzionale pre-analisi, la persistenza delle sessioni e il contratto API; il grafo e gli algoritmi MURENA restano invariati.
* **Conferma delle dimensioni omesse**: quando SAGE è attivo, l'assenza di una dimensione non equivale più a `NOT_REQUESTED`; resta `UNCONFIRMED_ABSENT` e viene chiesta una dimensione per turno. Le risposte aggiornano solo il requisito con evidenza esplicita; un'assenza di evidenza lascia la domanda irrisolta. Il limite predefinito passa a sei turni per coprire le sei dimensioni del modello di query.
* **UI conversazionale SAGE**: `/` conserva query, domande e risposte in un thread visivo durante i turni di chiarimento, con composer dedicato, stato di attesa e gestione di `BLOCKED`. Le domande sulle omissioni sono una dimensione per turno; l'analisi viene avviata solo al completamento del chiarimento.
* **Domande propositive**: i chiarimenti mostrano esempi specifici per tipologia, destinazione, posizione, vincoli edilizi, energia e prossimità. Gli esempi guidano la risposta ma non sono requisiti finché l'utente non li conferma.
* **Tipologia esplicita**: termini come “uffici” vengono riconosciuti come valore della dimensione `I`, con un fallback lessicale conservativo se il parser li omette; non si chiede all'utente di ripetere una tipologia già presente.
* **Prompt SAGE esternalizzati**: istruzioni per parsing, interpretazione delle risposte e controllo delle contraddizioni spostate da `service.py` in `sage_clarification/prompts.md`; loader dedicato per i placeholder runtime.
* **Luoghi nominati**: un riferimento esplicito come “vicino a Porta Nuova” non viene trattato come località omessa; se manca la città, la domanda chiede di disambiguare quel luogo specifico.
* **Coerenza per dimensione**: risposte a dimensioni omesse vengono estratte direttamente; gli altri controlli distinguono tipologia fisica e destinazione futura, evitando di bloccare una conversione come “uffici → studentato”.
* **Provider Codex centralizzato**: `codex_exec` aggiunto alla factory LLM condivisa con supporto a testo e output JSON Schema per tutti gli agenti e SAGE. La configurazione locale seleziona `gpt-6-luna` con reasoning `low`; i prompt restano nel grafo esistente. Il CLI gira in directory temporanea read-only, senza strumenti, e non riceve la API key applicativa. Richiede il login ChatGPT del CLI. Test automatizzati e chiamata live della factory completati; una prova minima ha usato circa 8.5k token d'ingresso, valore variabile.
* **Method caveat**: EVPI usa partizioni finite con pesi uniformi euristici; i valori non sono probabilità calibrate dell'intento dell'utente.

## 2026-11-10

* **Creation**: bundle iniziale OKF v0.2, con concetti per backend, frontend, dati, API, agenti, paper, benchmark e operazioni.
* **Provenance**: allegati i sorgenti LaTeX del manoscritto e i riferimenti relativi ai file del progetto.
* **Validation**: verifica automatica di formato e link locali inclusa nello ZIP; test runtime e riproduzione dei benchmark non eseguiti.
