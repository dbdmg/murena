# Generalised imperfect-user benchmark v4 — Realistic human-like elicitation

Suite di benchmark conversazionale con **risposte simulate contestualizzate per use case e dimensione**, costruita su **tutte le combinazioni di omissione** e su **tutti i bilanciamenti** tra risposte specificate, vaghe e rifiutate.

## Motivazione

Nella suite v3 (`backend/experiments/data/scenarios_v3/imperfect_user.yaml`):

* la risposta vaga era una frase fissa e generica (*"It depends; something suitable for the project, I guess."*), identica per ogni use case e dimensione;
* ogni scenario alterava **al massimo una** risposta simulata, quindi non venivano mai testate ambiguità multiple o combinazioni di comportamenti;
* l'opt-out era limitato alle sole preferenze ($C_b, C_e, C_p$).

La revisione **v4** rimuove tutte e tre le limitazioni:

1. **Formulazioni realistiche:** 40 risposte vaghe specifiche ($8\ \text{use case} \times 5\ \text{dimensioni}$) e 40 risposte di rinuncia contestualizzate al dominio dell'attività.
2. **Catalogo combinatorio completo:** vengono usate tutte le 32 maschere di omissione dei 5 criteri opzionali $D, L, C_b, C_e, C_p$ per ciascuno degli 8 intenti base (256 maschere), non solo le 6 traiettorie annidate del benchmark storico.
3. **Bilanciamento esaustivo:** per ogni maschera con $k$ omissioni vengono generate tutte le $3^k$ assegnazioni dei tre stati conversazionali.

## Stati conversazionali e turni attesi

Per ogni dimensione omessa nella query iniziale:

| Stato | Risposta simulata | Stato finale | Turni per la dimensione |
| :--- | :--- | :--- | :---: |
| `spec` (cooperativo) | valore esatto subito | `SPECIFIED` | 1 |
| `vague` | frase qualitativa contestualizzata, poi valore esatto al follow-up | `SPECIFIED` | 2 |
| `optout` | dichiarazione esplicita di non avere requisiti | `NOT_REQUESTED` | 1 |

Il numero di turni attesi è $\text{spec} + 2\times\text{vague} + \text{optout}$.

## Dimensioni del catalogo

$$8 \times \sum_{k=0}^{5} \binom{5}{k} 3^k = 8 \times 4^5 = \mathbf{8.192\ scenari}$$

| $k$ | Maschere per intento $\binom{5}{k}$ | Varianti per maschera $3^k$ | Totale ($8$ intenti) |
| :---: | :---: | :---: | :---: |
| 0 | 1 | 1 | 8 |
| 1 | 5 | 3 | 120 |
| 2 | 10 | 9 | 720 |
| 3 | 10 | 27 | 2.160 |
| 4 | 5 | 81 | 3.240 |
| 5 | 1 | 243 | 1.944 |
| **Totale** | **32** | — | **8.192** |

Profili nei metadati `imperfect_user`: 8 controlli `k=0`, 248 `all_specified`, 248 `all_vague`, 248 `all_optout`, 7.440 `mixed`.

Ogni scenario riporta `source_variant_id` (la maschera combinatoria di origine, es. `S02_k2_Cb_Ce`), `balance` (es. `1spec_1vague_1optout`), le dimensioni per stato e `expected_turns`.

## File contenuti

* `imperfect_user_v4.yaml` — 8.192 scenari generati deterministamente (~15,7 MB).
* `derive_imperfect_user_v4.py` — generatore deterministico (nessuna chiamata a modelli LLM) che legge `scenarios_v3/conversational_scenarios.yaml`.
* `validate_scenarios_v4.py` — validatore statico: verifica conteggi, distribuzione per $k$, 256 maschere distinte, formati delle risposte e coerenza degli stati attesi.

## Esecuzione e analisi

```bash
uv run python backend/experiments/benchmark_cli.py \
    --scenarios backend/experiments/data/scenarios_v4/imperfect_user_v4.yaml \
    --condition refined \
    --condition oracle \
    --repeat 3 \
    --sample-fraction 0.01 \
    --sample-seeds 13 29 47 71 101 \
    --output backend/experiments/results/imperfect_user_v4_multiseed
```

Il campionamento è uniforme senza reinserimento e riproducibile: con 8.192
scenari, la frazione 0,01 seleziona `ceil(8192 × 0,01) = 82` casi. Il seed e
gli ID selezionati sono salvati nel manifest; usare gli stessi seed e lo stesso
file riproduce gli stessi campioni. `--sample-seeds` esegue i seed in sequenza e
crea una directory distinta per ciascuno, ad esempio
`imperfect_user_v4_multiseed_seed13`. La CLI usa il modello configurato in
`backend/.env` (`LLM_MODEL`); il nome della directory non imposta il modello.
Con cinque seed si pianificano 1.230 run
`refined` e 120 `oracle`, per 1.350 job complessive. Lo stesso `--repeat 3`
vale per entrambe le condizioni quando `--oracle-repeat` è omesso. L'oracle è condiviso per
intento base; nei profili con opt-out non va interpretato come ranking
obiettivo condizionato alla rinuncia. Per un solo campione usare `--sample-seed 13`.

Per ispezionare il piano senza chiamate LLM, aggiungere `--dry-run`.

`analyze_imperfect_user.py` è ancora l'analizzatore dei profili v3: non usare il
suo output per riassumere v4, perché salta i nuovi profili. L'analisi aggregata
per `balance` richiede un aggiornamento dedicato.

## Cautele

* **Nessuna esecuzione LLM è stata fatta:** la suite è generata e validata staticamente. I risultati del paper restano quelli della serie Haiku su v3, con il protocollo annidato a 48 varianti.
* I profili `all_vague` a $k=5$ prevedono fino a **10 turni**: rientrano nel nuovo default `max_turns = 20`, ma non erano eseguibili con il limite storico di 6 turni usato nelle serie pubblicate.
* Gli scenari con opt-out su $D$ o $L$ non richiedono un trattamento speciale: come per le altre dimensioni, l'omissione diventa `UNCONFIRMED_ABSENT` e il rifiuto esplicito `NOT_REQUESTED`, senza filtri SQL. In particolare, rinunciare a $L$ fa cercare su tutto il dataset, senza perimetro geografico. `MISSING_CRITICAL` per $L$ emerge solo da un valore dichiarato ma non ancorato alla query, non dalla semplice assenza di località.
* `analyze_imperfect_user.py` riconosce solo i profili storici `optout` e `vague` e salta quelli v4; per analisi aggregate per `balance` serve un'estensione dello script.
