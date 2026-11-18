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

Gli scenari sintetici per studiare questo passaggio sono descritti nel [benchmark conversazionale EDBT](../research/edbt-conversational-benchmark.md); il runner documentato lì esegue la sola condizione conversational.

## Confine e attivazione

`ENABLE_SAGE_CLARIFICATION` è `true` per default e può essere disabilitato tramite configurazione. Quando è attivo, `POST /api/v1/analysis` analizza la query prima di creare una run. `ASK` richiede un'altra richiesta con `clarification_session_id` e `clarification_response`; quando tutte le dimensioni sono risolte, l'API restituisce `REVIEW` con la query raffinata e attende che l'utente la confermi o modifichi. La conferma invia `clarification_confirmed=true` e avvia la run usando il testo revisionato. `BLOCKED` non avvia l'analisi. Il grafo LangGraph, gli agenti e le fasi SQL/ranking non ricevono lo stato interno SAGE.

Le sessioni sono salvate in `ClarificationSession` (JSON SQLAlchemy) e associate all'utente autenticato quando presente. In assenza di stato conversazionale esistente, la tabella usa lo stesso database applicativo. Le risposte a sessioni non più attive o appartenenti a un altro utente sono rifiutate; la conferma finale richiede una sessione `ready` e la marca come `submitted` per impedirne il riuso. L'intera UI e tutti i testi generati per l'utente sono in inglese. SAGE formula sempre domande e query revisionate in inglese; anche l'API di analisi vincola `output_language` a `en`.

## Backend del modello

SAGE e gli agenti MURENA passano dalla factory condivisa `get_llm` → `build_chat_model`. `LLM_PROVIDER` seleziona il provider per l'intero flusso: `codex_exec` usa il CLI, mentre `openai-compatible` può usare vLLM e gli altri valori selezionano i provider già supportati. `LLM_MODEL` determina il modello. Per Codex, `CODEX_REASONING_EFFORT` e `CODEX_TIMEOUT_SECONDS` configurano il livello di ragionamento e il timeout. La configurazione locale verificata usa `LLM_PROVIDER=codex_exec`, `LLM_MODEL=gpt-6-luna` e `CODEX_REASONING_EFFORT=low`.

I prompt SAGE — estrazione della query, formulazione delle domande sulle omissioni, interpretazione delle risposte, controllo delle contraddizioni, estrazione della città e riscrittura finale — sono in `backend/app/services/sage_clarification/prompts.md`. `prompt_loader.py` seleziona le sezioni delimitate da commenti HTML e sostituisce i placeholder runtime usando operazioni su stringhe, senza regex; legge il Markdown a ogni invocazione, perciò le modifiche hanno effetto dalla richiesta successiva senza riavvio. Il testo delle domande su omissioni e ambiguità è prodotto dal modello a partire dalla query e dalle dimensioni da chiarire. Il codice mantiene etichette dimensionali, stato, validazione e selezione della prossima domanda, senza template di domanda per le omissioni.

L'adapter invoca `codex exec` senza persistere la sessione, con prompt su stdin, directory temporanea vuota, sandbox read-only e shell, ricerca web, app e sub-agenti disabilitati. Per gli output strutturati passa uno schema JSON al CLI e valida il risultato nel modello Pydantic richiesto dall'agente. Il processo riceve solo le variabili d'ambiente necessarie al CLI; `OPENAI_API_KEY` e i segreti applicativi non vengono inoltrati. Su Windows l'allowlist include anche variabili di sistema non segrete (`SYSTEMROOT`, `USERPROFILE`, `APPDATA`, `TEMP` e simili): senza `SYSTEMROOT` il runtime Node del CLI termina all'avvio con exit 134. Prompt e risposte sono codificati esplicitamente in UTF-8, perché la codifica locale di Windows (cp1252) corrompeva l'input e interrompeva la lettura dell'output. `codex exec` effettua inferenza remota tramite l'autenticazione Codex/ChatGPT. Un test live della factory condivisa ha completato una richiesta con `gpt-6-luna`; una prova minima ha consumato circa 8.5k token d'ingresso, valore variabile per invocazione e versione CLI.

## Stato e readiness

Le dimensioni `I`, `D`, `L`, `Cb`, `Ce`, `Cp` usano `SPECIFIED`, `NOT_REQUESTED`, `UNCONFIRMED_ABSENT`, `AMBIGUOUS` e `MISSING_CRITICAL`. `NOT_REQUESTED` richiede una conferma esplicita dell'utente; un'omissione semplice diventa `UNCONFIRMED_ABSENT`. Quando il wrapper è attivo, il modello formula una domanda per ogni dimensione omessa e il selettore applicativo ne presenta una per turno. Ogni omissione non confermata resta bloccante e selezionabile anche se il parser LLM restituisce `blocking=false`: la readiness non può dipendere da una domanda che il selettore ignora. `Cb` include vincoli edilizi e strutturali, superficie e capienza/occupazione; una capienza esplicita resta distinta dalla superficie e non viene convertita automaticamente in metri quadri o in un filtro SQL. Una risposta `UNCLEAR` a una domanda su omissioni genera un nuovo follow-up LLM e non rende l'aspetto non selezionabile. Per gli esempi sulla destinazione d'uso (`D`), SAGE carica dinamicamente le etichette `use_case` da `backend/docs/knowledge/normativa/normativa.json` e ne usa al massimo due pertinenti per domanda. Le formula come possibili destinazioni senza riferimenti alla fonte normativa e non le presenta come requisiti. `Cp` riguarda le categorie di servizi vicini d'interesse (sanità, mobilità, verde, sport, commercio, istruzione); il chiarimento chiede quali categorie contano, mentre MURENA applica le proprie soglie di distanza predefinite. L'utente può aggiungere un requisito o confermare che la dimensione non gli interessa. Dopo ogni risposta passa al requisito successivo ancora da chiarire. Le omissioni non diventano vincoli e non sono delegate finché non sono state confermate.

L'interpretazione semantica è affidata al parser LLM e guidata dal prompt Markdown. Se il parser lascia irrisolta `L` ma fornisce un luogo esplicito presente nella query e la città è esplicita, SAGE usa `get_coordinates` (landmark locali, cache e Nominatim) per geolocalizzarlo; una città più un luogo nominato è già sufficiente precisione e non genera una domanda sul sotto-quartiere, anche se il geocoder non restituisce coordinate. `turin_areas.json` non è usato da SAGE per riconoscere luoghi; resta una fonte di esempi per le query suggerite. La validazione non usa regex o fallback lessicali per dedurre tipologie o requisiti energetici. Il parser deve riconoscere, per esempio, che “uffici” specifica `I`, “classe energetica alta” specifica `Ce`, che un luogo esplicito senza città può essere ambiguo e che città più quartiere specifica `L`. La tipologia fisica non viene ricavata dalla destinazione futura; i mapping verso sottotipi del dataset restano al Building Agent.

Un luogo nominato dopo un'indicazione di vicinanza (per esempio “vicino a Porta Nuova”) può essere rappresentato dal parser come ambiguo se la città non è specificata. Il modello può proporre fino a tre città plausibili basandosi sulla propria conoscenza geografica; la domanda le presenta come suggerimenti non verificati e include sempre l'opzione di un'altra città. L'utente può indicare una città o selezionare un suggerimento anche per posizione (“la prima”). L'estrazione verifica che la città sia esplicita nella risposta o corrisponda a una delle opzioni offerte. Le alternative non sono esaustive né verificate tramite un geocoder.

Il modello classifica semanticamente le risposte come requisito, rinuncia alla dimensione, impossibilità a rispondere, rifiuto delle alternative o risposta non chiara. Non ci sono elenchi di frasi predefinite che determinano questi esiti. Un'etichetta `UNKNOWN`, `REJECTED` o `UNCLEAR` non rende da sola non selezionabile una località ancora irrisolta: la domanda geografica resta disponibile finché la città non è risolta o l'utente non rinuncia esplicitamente alla località. Una risposta breve con il nome di una città, come “Torino”, è indicata esplicitamente al parser come risposta geografica completa. Le risposte alle dimensioni omesse vengono inoltre estratte per dimensione con evidenza; gli aggiornamenti di stato sono deterministici dopo la classificazione. Per le altre risposte, il controllo confronta requisiti della stessa dimensione: tipologia attuale (`I`) e destinazione futura (`D`) sono indipendenti, quindi “uffici da convertire in studentato” non è una contraddizione.

Le interpretazioni già supportate da MURENA restano intatte: termini qualitativi, soglie di distanza predefinite e requisiti normativi derivabili dalla destinazione non generano chiarimenti solo per la loro forma implicita. Il modello può includere esempi illustrativi nella domanda, ma non li tratta come requisiti senza conferma esplicita. Le ambiguità bloccanti e i dettagli critici continuano a produrre domande mirate. `SAGE_MAX_TURNS` limita il numero di risposte; il default è sei, pari alle dimensioni del modello di query. Se resta un'omissione non confermata al raggiungimento del limite, l'analisi è bloccata.

Il testo originale resta persistito. Quando la sessione è pronta, un prompt dedicato chiede al modello di riscrivere la richiesta come testo naturale, integrando le risposte esplicite e mantenendo intento, qualificatori e preferenze originali. L'output è mostrato all'utente per revisione prima dell'analisi; il modello riceve solo query originale e chiarimenti confermati, non lo stato interno dei candidati. Un “non lo so” conserva l'incertezza e registra la risposta. Su una dimensione omessa, la prima risposta `UNKNOWN` o `REJECTED` riceve una domanda riformulata, che ricorda che la dimensione si può rifiutare. Solo una seconda risposta dello stesso tipo rende l'aspetto non più selezionabile (contatore `unresolved_answer_counts`). Se non resta un percorso utile, la sessione diventa `BLOCKED` e il messaggio elenca le dimensioni irrisolte. Il test di arresto EVPI non scarta mai una domanda che copre un'omissione non confermata o un dettaglio critico, perché la prontezza richiede comunque che quella dimensione sia risolta o rifiutata.

## Robustezza, concorrenza e regole aggiunte (2026-11-17)

Correzioni introdotte dopo la [code review](../operations/code-review-2026-11.md):

- **Definizione di `Cb` nel parser**: `Cb` è `SPECIFIED` solo da un requisito che filtra gli immobili (superficie numerica o qualitativa, capienza come "for 45 children", caratteristiche strutturali esplicite). Le parole che nominano solo l'immobile o il suo stato ("building", "existing building/unit", "premises", "to convert/renovate") non specificano `Cb`; se sono l'unica evidenza, `Cb` resta `UNCONFIRMED_ABSENT`. La capienza resta parte di `Cb`.
- **Errori transitori del modello**: un'eccezione durante un turno non diventa più `BLOCKED`. L'API risponde HTTP 503 con un messaggio esplicito, la sessione resta attiva e l'utente può reinviare la stessa risposta; la UI conserva l'identificativo di sessione. Un'eccezione nella classificazione di una risposta non viene più convertita in un'etichetta d'intento (`UNCLEAR`).
- **Follow-up sulle ambiguità**: una risposta genuinamente `UNCLEAR` a una domanda di ambiguità genera una riformulazione LLM, come già avveniva per le omissioni; il turno di riformulazione non incrementa la penalità di ridondanza, mentre `SAGE_MAX_TURNS` continua a limitare il dialogo.
- **Località**: senza `selected_alternative`, la città estratta deve comparire nella risposta (confronto per parola intera dopo normalizzazione) o coincidere con un'opzione offerta. Dopo una risposta `UNKNOWN`, `REJECTED` o `UNCLEAR` la domanda viene riformulata escludendo le alternative già rifiutate.
- **Concorrenza**: una risposta porta la sessione da `active` a `processing` con un aggiornamento condizionale prima di qualsiasi chiamata LLM; una seconda risposta concorrente riceve HTTP 409. In caso di errore lo stato torna `active` senza modifiche parziali. La conferma finale consuma la sessione con `UPDATE … WHERE status='ready'`: una doppia conferma non avvia due analisi. Se il processo server termina durante un turno, la sessione resta `processing` e occorre avviare una nuova ricerca.
- **Persistenza**: lo stato JSON viene copiato in profondità prima delle modifiche e marcato come modificato al salvataggio, così le modifiche annidate non vanno perse.
- **Event loop**: l'endpoint asincrono esegue il chiarificatore in un thread pool, così le chiamate LLM bloccanti non fermano le altre richieste.
- **UI**: se la prima query è già completa e l'API risponde `REVIEW`, la pagina mostra comunque il form di revisione. Le richieste di chiarimento usano un timeout client di 180 s (invece dei 30 s generali), perché un turno può concatenare più chiamate al modello.

Restano invariati, per scelta: l'evidenza delle dimensioni diverse da `L` non è confrontata con il testo della query (un controllo lessicale respingerebbe parafrasi e traduzioni); una risposta aggiorna solo le dimensioni a cui era rivolta la domanda.

La suite `backend/tests/test_sage_clarification.py` passa interamente (37 test, di cui 8 nuovi per regola `Cb`, ancoraggio della città, alternative rifiutate, follow-up, errori transitori, concorrenza e persistenza).

## Beliefs ed EVPI

Le alternative finite generate dal modello ricevono pesi uniformi iniziali, poi normalizzati. Per i luoghi, l'EVPI include anche un esito aperto per una città diversa da quelle suggerite, poiché i suggerimenti del modello non sono esaustivi. Un riferimento generico come “the university”, senza un luogo nominato o un catalogo geografico di sessione, produce una domanda generica e dominio ignoto. Domini non enumerabili non vengono convertiti in candidati fattuali e non producono una confidenza normalizzata. Per una domanda, le alternative partizionano i candidati per risposta; l'EVPI è la somma del massimo peso per partizione meno il massimo peso corrente. Il punteggio sottrae `SAGE_REDUNDANCY_LAMBDA` per ogni domanda precedente sullo stesso aspetto. Il criterio `SAGE_EVPI_STOP_ALPHA` si applica alle domande con alternative enumerabili; per domini ignoti non viene inventata una distribuzione delle risposte e la domanda resta selezionabile.

Questi pesi e punteggi sono stime euristiche, non posteriori calibrati. L'EVPI è deterministico a stato, alternative e pesi fissati. `SAGE_MAX_TURNS`, `SAGE_REDUNDANCY_LAMBDA` e `SAGE_EVPI_STOP_ALPHA` sono configurabili. Un EVPI basso non autorizza da solo la delega: la readiness esplicita mantiene il blocco se resta un'ambiguità necessaria.

## Differenze metodologiche e verifica

Questa è un'adattamento d'inferenza ispirato alla specifica fornita, non una replica verificata del paper SAGE-Agent. Il modello estrae dimensioni, alternative e testo della domanda; selezione, normalizzazione, aggiornamento deterministico e EVPI sono codice. Per risposte raggruppate, il modello estrae aggiornamenti per dimensione con uno span di evidenza; aggiornamenti senza evidenza testuale verificabile restano irrisolti. Una chiamata LLM addizionale controlla che una risposta esplicita non contraddica requisiti precedenti; in caso di conflitto o classificazione incerta la sessione si blocca. Non sono inclusi training, reward model o RL.

I test unitari sintetici, inclusi quelli dell'adapter CLI, si trovano in `backend/tests/test_sage_clarification.py` e sono eseguibili con `python -m unittest tests/test_sage_clarification.py` dalla directory `backend/`. La build TypeScript verifica il client/UI; non costituisce una misura di latenza, token o qualità end-to-end.
