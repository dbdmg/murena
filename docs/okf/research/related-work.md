---
type: Research Reference
title: Stato dell'arte e posizionamento
description: Lavori correlati a MURENA e al chiarimento conversazionale SAGE, raggruppati per filone, con posizionamento per un demo paper EDBT.
tags:
- research
- related-work
- edbt
- clarification
- text-to-sql
- urban-computing
generated:
  by: process:web-literature-search
  at: '2026-11-17T00:00:00Z'
sources:
- resource: ../references/paper/paper.tex
  title: Manoscritto MURENA (sezione Related Work e bibliografia citata)
- resource: ../architecture/query-clarification.md
  title: Adattamento SAGE implementato in MURENA
- resource: https://arxiv.org/abs/2511.08798
  title: Suri et al., Structured Uncertainty guided Clarification for LLM Agents (SAGE-Agent)
- resource: https://arxiv.org/abs/2508.15276
  title: AmbiSQL, Interactive Ambiguity Detection and Resolution for Text-to-SQL
- resource: https://arxiv.org/abs/2406.19073
  title: AMBROSIA, benchmark per domande ambigue su database
- resource: https://arxiv.org/abs/2310.13659
  title: AmbiQT, Benchmarking and Improving Text-to-SQL Generation under Ambiguity
- resource: https://arxiv.org/abs/2410.11076
  title: PRACTIQ, conversational text-to-SQL con query ambigue e non rispondibili
- resource: https://aclanthology.org/2026.acl-industry.86.pdf
  title: CLARITY, NL2SQL con ambiguità multiple (ACL Industry 2026)
- resource: https://arxiv.org/abs/2405.12063
  title: CLAMBER, identificazione e chiarimento di bisogni informativi ambigui (ACL 2024)
- resource: https://arxiv.org/abs/2503.22674
  title: QuestBench, chiarimento come problema di soddisfacimento di vincoli
- resource: https://arxiv.org/abs/2601.15758
  title: NL4ST, interrogazione in linguaggio naturale di database spazio-temporali
- resource: https://arxiv.org/abs/2509.25264
  title: GeoSQL-Eval, valutazione di LLM su NL2GeoSQL (PostGIS)
- resource: https://www.vldb.org/pvldb/vol19/p4758-li.pdf
  title: ChatQPT, demo VLDB di interazione chat con un query engine
- resource: https://arxiv.org/abs/2511.16131
  title: AskDB, agente LLM per database relazionali
- resource: https://arxiv.org/abs/2509.23988
  title: LLM/Agent-as-Data-Analyst, survey
- resource: https://arxiv.org/abs/2406.08426
  title: Survey su text-to-SQL basato su LLM
- resource: https://arxiv.org/abs/2507.00914
  title: Survey sugli agenti urbani basati su LLM
- resource: https://arxiv.org/abs/2607.14835
  title: LLM-Based Re-Ranking for Real Estate Search
- resource: https://proceedings.iclr.cc/paper_files/paper/2026/hash/5a161a9070cb7b259abe84cb37ed1b6f-Abstract-Conference.html
  title: Eichelbeck, Voigt, Althoff, interactive preference elicitation per decisioni abitative (ICLR 2026)
- resource: https://arxiv.org/abs/2511.08587
  title: SPARA, agente RAG conversazionale per efficienza energetica di cooperative abitative
- resource: https://arxiv.org/abs/2506.20551
  title: Madireddy et al., LLM per code compliance integrato con BIM
- resource: https://arxiv.org/abs/2510.02634
  title: Siddika et al., revisione automatica di codici edilizi con agenti LLM (RAG vs MCP)
- resource: https://www.gensler.com/press-releases/framework-optimize-office-conversion-policies
  title: Brookings/Gensler/HR&A, framework data-driven per conversioni office-to-residential
---

# Stato dell'arte e posizionamento

## Provenienza e livello di verifica

Ricerca bibliografica web svolta il 2026-11-17 per il demo paper EDBT. Per i lavori elencati sono stati consultati **abstract, pagine indice e sintesi dei motori di ricerca, non il testo completo**. I numeri riportati sono quelli dichiarati dagli autori negli abstract e vanno verificati sul full text prima di essere citati. La sede di pubblicazione è indicata solo quando compare nella fonte; altrimenti è segnata come da verificare.

Il manoscritto MURENA già cita: text-to-SQL (TriSQL, Think2sql, Spider), agenti con strumenti (ReAct, Toolformer, survey multi-agente), RAG e normativa (Lewis et al., Reuter et al.), LLM per urbanistica, AVM, recommender immobiliari, GeoGPT, QATCH. Questo documento **non** ripete quelle voci: aggiunge i filoni necessari per il contributo conversazionale e per il confronto con demo recenti.

## Filoni di riferimento

### 1. Chiarimento guidato dall'incertezza per agenti LLM

- **SAGE-Agent** (Suri, Mathur et al., arXiv 2511.08798, Findings of ACL 2026). Modella il chiarimento come POMDP, sceglie le domande con EVPI e penalizza le domande ridondanti per aspetto. Introduce **ClarifyBench**, benchmark multi-turno con utente simulato da LLM. L'abstract dichiara una copertura dei task ambigui più alta del 7–39% e da 1,5 a 2,7 volte meno domande rispetto ai baseline. È la fonte metodologica dell'adattamento MURENA; le differenze sono in [chiarimento pre-analisi](../architecture/query-clarification.md) (niente training né RL, pesi uniformi euristici).
- **CLAMBER** (ACL 2024, arXiv 2405.12063). Tassonomia delle ambiguità e benchmark. Gli autori riportano che gli LLM hanno utilità limitata nell'**identificare** query ambigue, anche con chain-of-thought e few-shot.
- **QuestBench** (arXiv 2503.22674). Chiarimento come problema di soddisfacimento di vincoli: misura se il modello sceglie l'unica domanda minima necessaria.
- **Clarify-Then-Search** (preprint 2026, alphaXiv 2608.20357). Il chiarimento migliora la deep search già con una domanda, ma molti sistemi fanno domande in eccesso.

### 2. Ambiguità in text-to-SQL e interfacce in linguaggio naturale ai dati

- **AmbiQT** (Bhaskar et al., arXiv 2310.13659): oltre 3.000 domande, ciascuna con due SQL plausibili per ambiguità lessicale o strutturale.
- **AMBROSIA** (Saparina e Lapata, NeurIPS 2024): ambiguità di scope, attachment e vaghezza. Gli LLM faticano a riconoscerle.
- **PRACTIQ** (Dong et al., arXiv 2410.11076): 2.800 conversazioni text-to-SQL con domande ambigue e non rispondibili, ognuna con richiesta di chiarimento e risposta dell'utente.
- **CLARITY** (Oracle, ACL Industry 2026): sintesi automatica di istanze NL2SQL con più fonti di ambiguità che interagiscono, a turno singolo e multiplo.
- **AmbiSQL** (Alibaba, arXiv 2508.15276): **sistema demo** che rileva ambiguità, chiede all'utente con domande a scelta multipla su più turni, riscrive la query e la passa a XiYan-SQL. Mantiene un log dei chiarimenti. L'abstract dichiara 87,2% di precisione nel rilevamento e +50% di exact match SQL. Sede della demo da verificare (le fonti indicano SIGMOD o ICDE 2026).
- **ChatQPT** (demo VLDB, PVLDB vol. 19): interazione chat con PostgreSQL, gestione delle allucinazioni e strumenti di analisi della query.
- **AskDB** (arXiv 2511.16131): agente conversazionale unico per query analitiche e amministrazione di database.
- **Agenti text-to-SQL multi-agente**: MAC-SQL (selector, decomposer, refiner), CHESS (schema linking da cataloghi e valori), CHASE-SQL (candidati multipli e selezione a coppie). Survey: arXiv 2406.08426. Survey sugli agenti di analisi dati: arXiv 2509.23988.

### 3. Dati spaziali e linguaggio naturale

- **NL4ST** (arXiv 2601.15758, demo): mappa domande in linguaggio naturale direttamente su piani fisici di query spazio-temporali (range, kNN, join) in SECONDO, con basi di conoscenza estratte dal database per ridurre le allucinazioni sui toponimi.
- **GeoSQL-Eval** (arXiv 2509.25264): 14.178 istanze, 340 funzioni PostGIS, 82 database tematici, 24 modelli valutati.
- **Agenti urbani LLM** (survey, arXiv 2507.00914): ciclo sensing–memoria–ragionamento–esecuzione e applicazioni a pianificazione, trasporti, ambiente. CityGPT e UrbanLLM vi compaiono come esempi; non sono stati consultati direttamente.

### 4. Ricerca immobiliare, preferenze ed energia degli edifici

- **LLM-Based Re-Ranking for Real Estate Search** (QuintoAndar, arXiv 2607.14835): re-ranker LLM su un recommender conversazionale. Dichiarano +5,3% di click-through e +4,8% di visite prenotate in un A/B test di produzione.
- **Interactive preference elicitation for high-stakes housing decisions** (Eichelbeck, Voigt, Althoff, ICLR 2026): Bayesian optimization con preferenze a coppie in uno spazio latente, con un'intervista LLM come prior. Riportano che far specificare i pesi direttamente all'LLM funziona peggio di un prior statico.
- **SPARA** (arXiv 2511.08587): agente RAG conversazionale che consiglia cooperative abitative sull'efficienza energetica, con dati dell'edificio e documenti normativi. È un advisor a singolo agente, non un sistema di ricerca.
- **Conversioni office-to-residential**: il framework Brookings/Gensler/HR&A e il progetto Berkeley CBE usano dati e algoritmi di fattibilità per selezionare edifici da convertire. È letteratura grigia o in corso, utile come motivazione applicativa.

### 5. Normativa edilizia e LLM

- **Madireddy et al.** (arXiv 2506.20551): LLM collegati a Revit che interpretano codici e generano script di verifica.
- **Siddika et al.** (arXiv 2510.02634): confronto RAG vs Model Context Protocol per verificare BIM contro codici. La pipeline RAG è risultata incoerente perché dipende dalla lettura del testo normativo da parte dell'LLM.
- Il punto comune è che l'interpretazione diretta dei testi normativi da parte dell'LLM è poco affidabile e va affiancata a rappresentazioni strutturate o strumenti deterministici. È coerente con la scelta MURENA di non dedurre soglie di superficie lorda non verificate dal catalogo.

## Posizionamento di MURENA

| Sistema | Chiarimento interattivo | Dati spaziali | Vincoli multi-dimensione e ranking | Normativa | Tipo |
|---|---|---|---|---|---|
| SAGE-Agent | sì, EVPI | no | no (tool call) | no | metodo + benchmark |
| AmbiSQL | sì, scelta multipla | no | no (SQL generico) | no | demo |
| NL4ST | no | sì | no | no | demo |
| ChatQPT, AskDB | conversazione, non chiarimento mirato | no | no | no | demo / sistema |
| Re-ranking immobiliare (QuintoAndar) | conversazione | parziale | ranking appreso | no | sistema industriale |
| SPARA | conversazione | no | no | sì (RAG) | sistema |
| **MURENA + SAGE** | sì, per dimensioni della query, EVPI euristico | sì (POI, distanze) | sì (SQL + scoring interpretabile) | sì (catalogo strutturato, nessuna soglia inventata) | demo |

L'elemento distintivo da sostenere nel paper è la **combinazione**: chiarimento strutturato su sei dimensioni di dominio (I, D, L, Cb, Ce, Cp), seguito da una pipeline multi-agente che traduce i vincoli in SQL deterministico e ranking spiegabile, con la normativa usata per riconoscere la destinazione d'uso senza trasformarla in filtri non verificati. Nessuno dei lavori trovati copre insieme chiarimento, dati spaziali-energetici e vincoli normativi.

## Implicazioni per il demo paper

- **Confronto obbligato**: AmbiSQL è il concorrente diretto come demo di chiarimento interattivo prima dell'esecuzione. La differenza da evidenziare è il dominio (vincoli eterogenei, spaziali e normativi invece di ambiguità su schema SQL) e la valutazione per dimensione.
- **Coerenza con la letteratura**: il punto debole osservato nei run (le ambiguità d'uso in UC20 e UC21 non vengono riconosciute come tali, vedi [benchmark EDBT](edbt-conversational-benchmark.md)) è lo stesso fenomeno riportato da CLAMBER e AMBROSIA. Va presentato come limite noto, non nascosto.
- **Metriche confrontabili**: ClarifyBench e AmbiSQL riportano copertura o accuratezza e numero di domande. Le metriche MURENA (F1 del rilevamento iniziale, numero di turni, accuratezza dello stato finale) sono affini; manca ancora il confronto one-shot / oracle.
- **Da verificare sul full text** prima della citazione: tutti i numeri sopra, la sede di AmbiSQL e il rapporto tra ClarifyBench e gli scenari MURENA.

Per le sedi di pubblicazione e le scadenze vedere [venue di pubblicazione](publication-venues.md).
