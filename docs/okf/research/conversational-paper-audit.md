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

Il sorgente [EDBT](../../../paper/edbt-paper-template.tex) è una **bozza ricostruita**, distinta dal [manoscritto MURENA originale](../references/paper/guide.md): autori e affiliazioni sono da confermare. Il paper riporta ora il benchmark a tre condizioni v4 seed 13 (246 one-shot, 209/246 refined e 24 oracle completate), con 37 errori refined dichiarati. Il confronto misura accordo con query/ranking oracle, senza attribuire rilevanza indipendentemente verificata agli immobili. I dettagli delle esecuzioni effettive e dei limiti degli scenari sono nel [benchmark conversazionale](edbt-conversational-benchmark.md).

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

## Aggiornamento del paper con le serie del 2026-11-18

- **Tabella 1, Figura 3** (`data/per_k.csv`), abstract, Execution e Results usano il rerun cooperativo `missingness_v3_haiku_r2` (304/304, codice `a5c1b09`). La serie del 17-11 è citata come superata e non combinata.
  - Il testo non dice più "seeded interleaved order": il runner corrente esegue per condizione.
- **Nuovo paragrafo "Imperfect users":** numeri da `imperfect_user_haiku/imperfect_user_summary.json`. La serie è confrontata solo con i propri oracle.
- **Demonstration riscritta** come attività del pubblico: richieste dal vivo con le attività a–d, pannello scenari offline, pagina dei risultati benchmark.
  - Il confronto one-shot passa per run registrate: in UI il chiarimento non si disattiva al volo.
  - Il pannello scenari ripete risposte preparate e top-10 registrati, senza modello.
- **Execution nomina il modello:** Claude Haiku 5.5 via Claude Code CLI, effort medium, campionamento predefinito della CLI. La temperatura 0 non è dichiarata perché non viene applicata.
- **Introduzione, Scope, Conclusion:** il limite "utente cooperativo ed esatto" diventa "utenti simulati".
- **Nuovo paragrafo Availability:**
  - Contiene il repository pubblico `dbdmg/murena`, verificato pubblico il 2026-11-18, e gli APE pubblicati in formato ridotto dalla Regione Piemonte.
  - Mancano ancora l'URL del portale APE e il link al video: da confermare con l'utente.
- **Lavori correlati:** aggiunto Sphinteract (PVLDB 18(4):1145–1158, 2024, DOI 10.14778/3717755.3717772), con metadati verificati sul blocco "PVLDB Reference Format" del PDF.
- **PDF:** rigenerato con Tectonic e controllato visivamente, 4 pagine; overfull verticale di 1,9 pt nella routine di output, dello stesso tipo del precedente. Non è committato: il collega lo aveva rimosso (`b820dc6`).

## Paradigma di generazione v4 nel paper (2026-11-18)

- **Scenari e abstract:** il manoscritto descrive ora il catalogo v4 come framework di generazione: 8 intenti, tutte le 32 maschere di omissione, tre comportamenti per dimensione omessa (specificato, vago, opt-out) e $8 \times \sum_k \binom{5}{k}3^k = 8.192$ scenari. Rimossi il linguaggio del disegno annidato a 48 varianti e la vecchia estensione non eseguita a 256 varianti.
- **Evidenza riportata:** restano le 304 run della serie cooperativa `missingness_v3_haiku_r2`, ora etichettate come tali nell'abstract, nelle Conditions, nella didascalia della Tabella 1 e nello Scope. Nessun parametro di campionamento, seed o risultato v4 è riportato nel paper.
- **Sezione 4:** il pannello demo è descritto come selezione di run v4 completate per caso d'uso e stato delle dimensioni (specificato, omesso, ambiguo), con richiesta iniziale, risposte preparate, query riscritta e top-10.
- **Sezione 5, Imperfect users:** rimossa la meccanica del generatore storico (una sola risposta alterata, frase vaga fissa); restano i risultati osservati su opt-out e risposte vaghe.
- **Verifica:** validatore v4 rieseguito (`8.192` scenari, distribuzione per $k$ e 256 maschere). PDF rigenerato con Tectonic in copia temporanea: 4 pagine, nessuna regressione maggiore. Il PDF è presente in `paper/` come artefatto non tracciato, coerente con la scelta di non versionarlo.

## Registrazione della demo (2026-11-18)

- **File:** `paper/video/murena_demo_nursery.gif`, registrato con il registratore GIF del browser sull'app locale (frontend Vite in modalità normale, backend `uvicorn` con `LLM_PROVIDER=claude_cli`, `LLM_MODEL=claude-haiku-5-5`, effort medium).
- **Richiesta iniziale:** "I am looking for an existing school building in Turin to convert into a nursery, near green spaces."
- **Interazione osservata:**
  1. Domanda sui requisiti edilizi; risposta vaga ("It depends; something suitable for the project, I guess.").
  2. Domanda sull'efficienza energetica; opt-out ("I have no requirement on the energy class.").
  3. Domanda riformulata sui requisiti edilizi; risposta esatta ("At least 600 sqm of gross floor area and capacity for 45 children.").
  4. Revisione della richiesta riscritta, che riporta "Energy performance is not a concern for this search".
  5. Conferma, analisi (circa 50 s) e mappa con 22 immobili e top 10 giustificata.
- **Valore:** è una singola esecuzione dimostrativa, coerente con il comportamento misurato nella serie "utente imperfetto". Non è un risultato e non va citata come tale.
- **Da fare:** il paper non contiene ancora il link al video. La GIF non ha audio: il video finale, con commento, va prodotto e caricato dagli autori.

## Fonte e licenza dei dati APE (2026-11-18)

- **Testo nel paper:** il paragrafo Availability indica gli APE in formato ridotto della Regione Piemonte come open data CC BY 4.0 e rimanda a `https://www.dati.piemonte.it/#/catalogo`.
- **Verifica:** sulla scheda del catalogo, il 2026-11-18. La scheda è "Dettaglio attestato di prestazione/certificazione energetica (APE)", identificativo `regpie_ckan_ckan2_yucca_sdp_smartdatanet.it_Sicee_v_t_export_bo_ape_18895`.
  - Titolare: Regione Piemonte; pubblicato da CSI-Piemonte, fonte Yucca SDP.
  - Licenza: "Creative Commons Attribuzione 4.0 Internazionale".
  - Dimensioni e aggiornamento: 79 colonne e 1.324.334 righe; aggiornamento mensile; dataset aggiornato il 2/11/2026.
- **Limite:** il paper non dichiara quale estrazione mensile sia stata usata per costruire `estates.parquet`. La provenienza della pipeline è in `docs/estates_parquet.md`.
- **Ancora mancante:** il link al video, in preparazione da parte di Marco De Luca.

## Review del paper sullo stato del 2026-11-18 (pomeriggio)

Review del sorgente `paper/edbt-paper-template.tex` al commit `32c1d1b`, con titolo "Ask, Don't Guess". Considera tutte le serie presenti in `backend/experiments/results/` dopo il pull delle 16:10. I numeri sulle serie dei colleghi sono **conteggi di stato** letti da `runs.jsonl` e dagli artefatti, non metriche analizzate.

### Inventario delle serie

| Serie | Modello | Scenari | Record | Stato | Dataset (sha256, prefisso) |
|---|---|---|---|---|---|
| `missingness_v3_haiku_r2` (**nel paper**) | Claude Haiku 5.5 | v3 annidato, 48 | 304 | 304 completate | `bc6732c8ff` |
| `imperfect_user_haiku` (**nel paper**) | Claude Haiku 5.5 | v3 imperfetto, 75 | 265 | 265 completate | `bc6732c8ff` |
| `missingness_v3_haiku`, `imperfect_user_haiku_c7b9f7a` | Claude Haiku 5.5 | v3 | 304; 265 | superate, non combinate | `bc6732c8ff` |
| `all_scenarios_codex` | gpt-6-luna | catalogo combinatorio, 256 | 2.350 | 1.357 completate, 993 errori | `d3956041f1` |
| `imperfect_user_v4_oracle_first_seed13` | gpt-6-luna | v4, campione 1%, seed 13 | 270 | 233 completate, 37 bloccate | `1f32c225db` |
| `imperfect_user_v4_multiseed_seed13` | gpt-6-luna | v4, seed 13 | 107 | 93 completate, 14 bloccate | `1f32c225db` |
| `imperfect_user_v4_multiseed_qwen3-8b_seed13` | Qwen3.8-27B (vLLM) | v4, seed 13 | 10 | in corso | `1f32c225db` |

Dettagli sulle serie dei colleghi:
- **`all_scenarios_codex`:** 989 dei 993 errori sono fallimenti della chiamata Codex CLI. La condizione one-shot ha 899 errori su 1.488 record (60%); refined 768 completate su 814; oracle 48 record, tutti falliti.
- **`imperfect_user_v4_multiseed_seed13`:** 92 dei 107 artefatti per run non sono nel repository.

### Problemi da correggere nel testo (incoerenze con il repository)

1. **Scope.** Il testo dice "An unexecuted catalogue extension …". Il catalogo a 256 varianti è stato eseguito **in parte** con gpt-6-luna (`all_scenarios_codex`), con molti fallimenti, e la serie non è riportata nel paper.
   - Proposta: "executed only partially, with another backend and a high failure rate, and not reported".
2. **Demonstration, pagina risultati.** Il testo promette il confronto affiancato di one-shot, refined e oracle.
   - Il default del frontend (`frontend/vite.config.ts`, `frontend/.env.demo`) punta ora a `imperfect_user_v4_multiseed_seed13`: solo refined, parziale, con un altro modello e un altro dataset.
   - Per la conferenza va fissata una serie coerente con il paper (`missingness_v3_haiku_r2`), oppure il testo deve dire quale serie è mostrata.
3. **Imperfect users.** J5 0,93 è confrontato con il tetto della stessa serie (0,93), più alto di quello della serie principale (0,87).
   - Il lettore può confrontare 0,93 con 0,88 e concludere che le risposte vaghe migliorano il risultato.
   - Proposta: aggiungere che i due tetti differiscono tra le esecuzioni e che i valori non vanno confrontati fra le serie.
4. **Attività (b) della demo.** Invita a rifiutare qualunque dimensione, ma l'opt-out è misurato solo sulle preferenze $C_b$, $C_e$, $C_p$.
   - Con il pubblico un rifiuto su $D$ o $L$ non ha evidenza misurata: vedi i blocchi v4 qui sotto.
   - Proposta: limitare l'esempio alle preferenze, oppure verificare dal vivo $D$ e $L$.

### Punti deboli che un revisore noterà (già dichiarati, da presidiare)

- **Un solo modello:** Claude Haiku 5.5, con il campionamento predefinito della CLI. Le serie gpt-6-luna e Qwen potrebbero rispondere, ma oggi usano tre dataset diversi (hash diversi) e scenari diversi (v4 invece di v3). Non sono confrontabili né combinabili con la serie del paper finché non si allineano dataset, scenari e codice.
- **Otto intenti:** il p-value 0,008 è il minimo ottenibile con 8 intenti; dichiarato.
- **Utente simulato:** rivela esattamente il frammento omesso, quindi il risultato è un limite superiore; dichiarato. Non ci sono studio utenti né baseline a form; dichiarati come lavoro futuro.
- **Oracle:** è un output di riferimento, non un giudizio di rilevanza; dichiarato.

### Punti aperti per il demo track

- Mancano il link al video (lo prepara Marco De Luca), autori e affiliazioni, e i limiti della call EDBT 2027.
- L'input in italiano dichiarato nella Demonstration non è stato verificato in questa sessione.
- La Fig. 2 mostra 144 risultati. Nella registrazione dal vivo del 18-11 (risposte formulate diversamente) i risultati erano 22: è coerente con la variabilità, ma la didascalia descrive una sola esecuzione.

### Segnalazioni per i colleghi (non riguardano il testo del paper)

- **Opt-out su $D$ nella v4.** In `imperfect_user_v4_oracle_first_seed13` le sessioni refined con opt-out su $D$ sono bloccate in 33 casi su 51; con opt-out solo su altre dimensioni, in 4 su 195.
  - Esempio: la risposta simulata "I have no specific spring section or educational program in mind." non rifiuta l'uso. Allude invece all'uso nascosto, cioè la sezione primavera, e non è un opt-out.
  - Il blocco dopo due risposte non risolutive è quindi il comportamento previsto da SAGE. Il difetto è nelle frasi generate da `derive_imperfect_user_v4.py`, che va corretto prima di riportare questa serie.
  - Anche alcune frasi di opt-out su $C_b$ rivelano l'uso ("toddler capacity for the spring section").
- **Dataset diversi:** i tre hash non coincidono con quello delle serie Haiku. Vanno allineati prima di confrontare i modelli.
- **Codex:** il 60% di fallimenti in one-shot rende `all_scenarios_codex` inutilizzabile per il confronto one-shot senza un'esecuzione di ripresa.

## Sostituzione dei risultati con il campione v4 seed 13 (2026-11-18)

- Abstract, Conditions, Execution, Results e tabella ora descrivono la serie `imperfect_user_v4_comparison_seed13` (`gpt-6-luna`, 1%, seed 13). Il confronto include 246 one-shot, 209 refined completate su 246 e 24 oracle; i 37 errori refined sono dichiarati.
- Le tabelle riportano Jaccard@5 e RBO@10 (serviti e tie-aware), F1 aggregato e per k, richiamo per dimensione, atomi inventati, auto-accordo oracle, consistenza SQL, accuratezza della mappatura, tempi, completamento e conteggi operativi, con intervalli cluster-bootstrap e test sign-flip dove calcolati. La figura per k usa `paper/data/per_k.csv`, esportato dagli output aggregati correnti; la curva precedente è conservata in `paper/data/per_k_cooperative_haiku_archived.csv`.
- I precedenti risultati Haiku cooperativi e imperfect-user sono conservati in un blocco LaTeX `\iffalse ... \fi` disattivato; non sono risultati attivi né vengono combinati con v4.
- È stato aggiunto al testo che l'oracle include vincoli anche nei profili opt-out: l'accordo con l'oracle non è un obiettivo appropriato per quei casi e non costituisce una misura indipendente di rilevanza.
- Integrata la review upstream: la serie v4 usa un dataset con hash diverso da Haiku e la formulazione generata per opt-out su $D$ è ambigua. Sono dichiarati i blocchi: 33/51 sessioni $D$-opt-out e 4/195 opt-out di altre dimensioni; le metriche complete-case non includono questi tentativi.
- Su richiesta dell'utente, il PDF non è stato compilato dopo questa modifica; il PDF preesistente è rimasto intatto e non corrisponde ai sorgenti aggiornati. Conteggio pagine e layout dei nuovi sorgenti restano non verificati.

## Regole della call e autori (2026-11-18)

- **Call EDBT 2026, demo track** (`https://edbticdt2026.github.io/?contents=call_for_demos.html`, letta il 2026-11-18):
  - "EDBT uses non-anonymous submissions": i revisori restano anonimi.
  - Al massimo 4 pagine, referenze incluse, nel formato ACM Proceedings senza modifiche.
  - Video facoltativo fino a 5 minuti, che secondo la call aumenta molto le probabilità di accettazione.
  - Criteri di valutazione: esperienza del pubblico e novità del sistema.
  - La call 2027 non è ancora pubblicata; le regole vanno ricontrollate quando uscirà.
- **Autori nel paper:**
  - Marco De Luca, Simone Monaco (DAUIN, Politecnico di Torino);
  - Giovanna De Luca, Alice Gorrino (Edilclima S.r.l., Borgomanero);
  - Daniele Apiletti, Tania Cerquitelli (DAUIN, Politecnico di Torino).
  - Intestazione: "De Luca et al.". Rispetto al paper MURENA manca Claudiu Tcaciuc, per scelta dell'utente.
  - Non sono indicate le email.
- **Ringraziamenti:** il testo WEBFARE è identico a quello del manoscritto MURENA, nell'ambiente `acks` di acmart.
- **Fonte delle affiliazioni:** il manoscritto fornito dall'utente. Su internet non ho trovato una pagina con le affiliazioni.

## Ripristino dei risultati Haiku (2026-11-18)

Su richiesta dell’utente, il manoscritto torna a riportare le serie `missingness_v3_haiku_r2` (304/304) e `imperfect_user_haiku` (265/265), separatamente. Il testo distingue la suite annidata eseguita per le serie Haiku dal catalogo v4 da 8.192 scenari, che resta descritto come generatore. La tabella attiva contiene completion, Jaccard@5, RBO@10 e filter F1 con IC; delta, p-value, detection F1 e tempi non sono riportati. I risultati e le metriche complete v4 restano nel sorgente LaTeX inattivo. `data/per_k.csv` usa la serie Haiku; la curva v4 è in `data/per_k_v4_seed13_archived.csv`. Il PDF non è stato compilato su richiesta.

## Review pre-submission (2026-11-18, sera)

Stato verificato su `37e0732`; il PDF compila in 4 pagine e il layout è corretto. La call EDBT 2027 per le demo (sorgente di `edbticdt2027.github.io`, `contents/call_for_demos.html`) fissa la submission al **18 novembre 2026 alle 17:00 PT** (02:00 del 19 in Italia). Requisiti: massimo 4 pagine incluse le referenze, submission non anonima, **video MP4 obbligatorio** (fino a 5 minuti, H.264/AAC), invio tramite CMT `EDBT2027`. La proposta deve descrivere cosa vede il pubblico, se può interagire, lo script e i requisiti oltre a un tavolo e al Wi-Fi.

Punti emersi:

- **Video.** Esiste solo una GIF muta; serve un MP4.
- **Requisiti logistici.** Il paper non dice cosa serve oltre al tavolo (accesso al provider LLM, rete) né cosa succede se manca la rete. La modalità con scenari offline esiste ed è citata, ma non come piano di riserva esplicito.
- **Riferimenti interni.** Abstract e Scope citano "v4 seed-13" e "not combined with v4": per un revisore sono nomi senza significato, e vanno tolti.
- **Catalogo da 8.192 scenari.** Abstract ed Evaluation lo presentano, ma i risultati usano la suite annidata a 48 varianti: può sembrare un contributo non valutato.
- **Italiano.** La frase "in English or Italian" non è verificata sul sistema.
- **Opzione `review` di acmart.** Mostra i numeri di riga; va lasciata o tolta secondo il template EDBT.
- **Serie `imperfect_user_codex_vlast`.** Non è riportata e non è utilizzabile: 64/225 run refined completate, 0/40 oracle, tutti gli errori sono "Codex CLI LLM call failed".

Interventi applicati nella PR `paper/edbt27-presubmission`:

- **Abstract.** Tolto il riferimento interno a v4 e tolto il catalogo da 8.192 scenari. Aggiunto il confronto con l'auto-accordo dell'oracle (0,87) e la modalità offline.
- **Introduzione.** Anticipa il risultato principale: J5 da 0,16 a 0,88, pari all'auto-accordo dell'oracle, e nessuna domanda quando non manca nulla.
- **Scenari.** La sezione descrive per prima la suite annidata a 48 varianti effettivamente valutata. Il generatore da 8.192 scenari compare in una sola frase, "not evaluated here".
- **Scope.** Tolta la frase su v4.
- **Demo.** Nuovo paragrafo "Setup and fallback": portatile, rete verso il provider LLM, modalità offline come riserva, video allegato.
- **Lingua.** Rimosso "or Italian". Il codice forza le domande e l'output in inglese (`sage_clarification/service.py:855`, `requests.py:31`) e nessuna run reale ha input in italiano.
- **Opzione `review` (numeri di riga).** Mantenuta: il template ufficiale EDBT 2027 usa `\documentclass[sigconf,review]{acmart}` e la call vieta modifiche allo stile. `edbt-macros.tex` coincide con il template.
- **PDF.** Rigenerato: 4 pagine, layout controllato.
