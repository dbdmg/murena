---
type: Architecture
title: Chiarimento pre-analisi
description: Wrapper SAGE-inspired facoltativo per rappresentare e risolvere ambiguità prima della run MURENA.
tags:
- sage
- clarification
- api
sources:
- resource: ../../../backend/app/services/sage_clarification/service.py
  title: Implementazione del servizio di chiarimento
- resource: ../../../backend/app/services/sage_clarification/prompts.md
  title: Prompt LLM del chiarificatore SAGE
- resource: ../../../backend/app/services/sage_clarification/prompt_loader.py
  title: Caricamento e rendering dei template Markdown
- resource: ../../../backend/app/services/sage_clarification/uncertainty.py
  title: Calcolo euristico di beliefs ed EVPI
- resource: ../../../backend/app/api/v1/endpoints/analysis.py
  title: Integrazione al confine API
---

# Chiarimento pre-analisi

## Confine e attivazione

`ENABLE_SAGE_CLARIFICATION` è `false` per default. Quando è attivo, `POST /api/v1/analysis` analizza la query prima di creare una run. `ASK` richiede un'altra richiesta con `clarification_session_id` e `clarification_response`; `BLOCKED` non avvia l'analisi; `READY` passa la query raffinata al percorso esistente `AnalysisService.run_analysis`. Il grafo LangGraph, gli agenti e le fasi SQL/ranking non ricevono lo stato interno SAGE.

Le sessioni sono salvate in `ClarificationSession` (JSON SQLAlchemy) e associate all'utente autenticato quando presente. In assenza di stato conversazionale esistente, la tabella usa lo stesso database applicativo. Le risposte a sessioni non più attive o appartenenti a un altro utente sono rifiutate. Le domande seguono la lingua di output della richiesta (`en` o `it`).

## Backend del modello

SAGE e gli agenti MURENA passano dalla factory condivisa `get_llm` → `build_chat_model`. `LLM_PROVIDER` seleziona il provider per l'intero flusso: `codex_exec` usa il CLI, mentre `openai-compatible` può usare vLLM e gli altri valori selezionano i provider già supportati. `LLM_MODEL` determina il modello. Per Codex, `CODEX_REASONING_EFFORT` e `CODEX_TIMEOUT_SECONDS` configurano il livello di ragionamento e il timeout. La configurazione locale verificata usa `LLM_PROVIDER=codex_exec`, `LLM_MODEL=gpt-6-luna` e `CODEX_REASONING_EFFORT=low`.

I tre prompt SAGE — estrazione della query, interpretazione della risposta alle omissioni e controllo delle contraddizioni — sono in `backend/app/services/sage_clarification/prompts.md`. `prompt_loader.py` seleziona le sezioni HTML-comment e sostituisce i placeholder runtime; legge il Markdown a ogni invocazione, perciò le modifiche hanno effetto dalla richiesta successiva senza riavvio. I template conversazionali e gli esempi di risposta restano costanti applicative in `service.py`, separati dalle istruzioni inviate al modello.

L'adapter invoca `codex exec` senza persistere la sessione, con prompt su stdin, directory temporanea vuota, sandbox read-only e shell, ricerca web, app e sub-agenti disabilitati. Per gli output strutturati passa uno schema JSON al CLI e valida il risultato nel modello Pydantic richiesto dall'agente. Il processo riceve solo le variabili d'ambiente necessarie al CLI; `OPENAI_API_KEY` e i segreti applicativi non vengono inoltrati. `codex exec` effettua inferenza remota tramite l'autenticazione Codex/ChatGPT. Un test live della factory condivisa ha completato una richiesta con `gpt-6-luna`; una prova minima ha consumato circa 8.5k token d'ingresso, valore variabile per invocazione e versione CLI.

## Stato e readiness

Le dimensioni `I`, `D`, `L`, `Cb`, `Ce`, `Cp` usano `SPECIFIED`, `NOT_REQUESTED`, `UNCONFIRMED_ABSENT`, `AMBIGUOUS` e `MISSING_CRITICAL`. `NOT_REQUESTED` richiede una conferma esplicita dell'utente; un'omissione semplice diventa `UNCONFIRMED_ABSENT`. Quando il wrapper è attivo, chiede conferma delle dimensioni omesse **una per turno**: per ciascuna l'utente può aggiungere un requisito o confermare che non gli interessa. Dopo ogni risposta passa al requisito successivo ancora da chiarire. Le omissioni non diventano vincoli e non sono delegate finché non sono state confermate.

I termini espliciti di tipologia fisica, come “uffici”, “residenziale” o “commerciale”, valorizzano `I`; un controllo lessicale conservativo corregge eventuali omissioni del parser. Non ricava la tipologia dalla destinazione futura e lascia al Building Agent i mapping verso sottotipi del dataset.

Un luogo nominato dopo un'indicazione di vicinanza (per esempio “vicino a Porta Nuova”) non viene classificato come località assente. Se la città non è specificata, SAGE conserva il riferimento e chiede quale città intenda l'utente; se la città è presente nella stessa frase, conserva il riferimento completo.

Le risposte alle domande su dimensioni assenti aggiornano direttamente la dimensione richiesta, con evidenza testuale, senza passare dal classificatore generico di contraddizioni. Per le altre risposte, il controllo confronta requisiti della stessa dimensione: tipologia attuale (`I`) e destinazione futura (`D`) sono indipendenti, quindi “uffici da convertire in studentato” non è una contraddizione.

Le interpretazioni già supportate da MURENA restano intatte: termini qualitativi, soglie di distanza predefinite e requisiti normativi derivabili dalla destinazione non generano chiarimenti solo per la loro forma implicita. Le domande includono esempi di risposta per guidare l'utente; sono suggerimenti illustrativi e non diventano requisiti senza conferma esplicita. Le ambiguità bloccanti e i dettagli critici continuano a produrre domande mirate. `SAGE_MAX_TURNS` limita il numero di risposte; il default è sei, pari alle dimensioni del modello di query. Se resta un'omissione non confermata al raggiungimento del limite, l'analisi è bloccata.

Il testo originale resta persistito. La query raffinata lo conserva e aggiunge soltanto le risposte esplicite ricevute. Un “non lo so” conserva l'incertezza, registra la risposta e impedisce di ripetere lo stesso aspetto; se non resta un percorso utile, la sessione diventa `BLOCKED`.

## Beliefs ed EVPI

Le alternative finite generate dal modello ricevono pesi uniformi iniziali, poi normalizzati. I candidati geografici sono mantenuti solo se nominati nella query; al confine API non è disponibile un catalogo geografico di sessione, quindi un riferimento come “the university” produce una domanda generica e dominio ignoto. Domini non enumerabili non vengono convertiti in candidati fattuali e non producono una confidenza normalizzata. Per una domanda, le alternative partizionano i candidati per risposta; l'EVPI è la somma del massimo peso per partizione meno il massimo peso corrente. Il punteggio sottrae `SAGE_REDUNDANCY_LAMBDA` per ogni domanda precedente sullo stesso aspetto. Il criterio `SAGE_EVPI_STOP_ALPHA` si applica alle domande con alternative enumerabili; per domini ignoti non viene inventata una distribuzione delle risposte e la domanda resta selezionabile.

Questi pesi e punteggi sono stime euristiche, non posteriori calibrati. L'EVPI è deterministico a stato, alternative e pesi fissati. `SAGE_MAX_TURNS`, `SAGE_REDUNDANCY_LAMBDA` e `SAGE_EVPI_STOP_ALPHA` sono configurabili. Un EVPI basso non autorizza da solo la delega: la readiness esplicita mantiene il blocco se resta un'ambiguità necessaria.

## Differenze metodologiche e verifica

Questa è un'adattamento d'inferenza ispirato alla specifica fornita, non una replica verificata del paper SAGE-Agent. Il modello estrae dimensioni, alternative e testo della domanda; selezione, normalizzazione, aggiornamento deterministico e EVPI sono codice. Per risposte raggruppate, il modello estrae aggiornamenti per dimensione con uno span di evidenza; aggiornamenti senza evidenza testuale verificabile restano irrisolti. Una chiamata LLM addizionale controlla che una risposta esplicita non contraddica requisiti precedenti; in caso di conflitto o classificazione incerta la sessione si blocca. Non sono inclusi training, reward model o RL.

I test unitari sintetici, inclusi quelli dell'adapter CLI, si trovano in `backend/tests/test_sage_clarification.py` e sono eseguibili con `python -m unittest tests/test_sage_clarification.py` dalla directory `backend/`. La build TypeScript verifica il client/UI; non costituisce una misura di latenza, token o qualità end-to-end.
