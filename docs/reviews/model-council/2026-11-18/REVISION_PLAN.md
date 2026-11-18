# Piano di revisione del paper dopo il model council (2026-11-18, 18:45)

Fonte: [SYNTHESIS.md](SYNTHESIS.md). Scadenza EDBT 2027 demo: 18-11-2026, 17:00 PT (02:00 in Italia). Ogni modifica va in una PR separata, senza push diretti su `demo`.

## 1. Paper (PR dedicata, circa 45 minuti inclusa la compilazione)

- **Controlled scenarios.** Descrivere il pannello reale: si scelgono use case e k, si vede una run alla volta, i dati sono della serie Haiku. *(sintesi #4)*
- **Fig. 2.** Didascalia "sessione live su una build precedente", senza il numero 144. Se c'è tempo, nuovi screenshot durante la registrazione del video. *(#5)*
- **Opt-out.** Limitare l'attività (b) alle preferenze $C_b, C_e, C_p$. Nel paragrafo sugli utenti imperfetti: frase fissa e copertura reale. *(#6)*
- **Validità.** I tetti dell'oracle variano tra esecuzioni (0,87 e 0,93), quindi niente confronti tra serie. Le condizioni sono state eseguite in finestre temporali diverse. *(#7)*
- **Abstract.** L'utente simulato fornisce esattamente il requisito omesso; il valore 0,87 si riferisce solo a J5. *(#11)*
- **Correzioni fattuali:**
  - il controllo delle contraddizioni avviene solo sulle domande di ambiguità *(#8)*;
  - EVPI vale $1-1/n$ e le omissioni aperte hanno EVPI 0 *(#9)*;
  - latenza di 11 s a k=0 *(#10)*;
  - relaxation one-shot solo su UC07 *(#12)*;
  - due esecuzioni preliminari *(#13)*;
  - blocco dopo una seconda risposta non risolta *(#16)*.
- **Minori:**
  - citare Fig. 3 nel testo;
  - "six dimensions" elencate per intero;
  - "result relaxation" senza "MURENA's" *(#15)*.
- **Spazio:**
  - togliere tie-aware e invented atoms;
  - riportare detection 360/360 e sign-flip $p=0{,}008$;
  - accorciare l'esempio nursery *(#14)*.
- **Pulizia:**
  - `showcomments` a false;
  - togliere `%% test`;
  - aggiornare il README *(#19)*.
- **Chiusura:**
  - ricompilare e verificare le 4 pagine;
  - committare anche il PDF *(#1)*;
  - aggiornare l'OKF.

## 2. Configurazione della demo (codice, da concordare con Marco De Luca)

- Puntare `.env.demo` su `missingness_v3_haiku_r2`, rigenerare gli export e provare la modalità offline prima del video. *(#3)*

## 3. Video MP4 (bloccante)

- Al massimo 5 minuti, H.264/AAC. Sequenza: richiesta nursery, risposta vaga e follow-up, opt-out su una preferenza, revisione, mappa, modalità offline. *(#2)*
- Mantenere nel paper la frase sul video solo se l'MP4 viene caricato.

## 4. Rimandato alla camera-ready

- Citazioni verificate su slot filling e clarifying questions. *(#18)*
- Nota di riproducibilità: commit equivalente `a5c1b09`; tabella degli immobili ricostruita dagli open data. *(#17)*
