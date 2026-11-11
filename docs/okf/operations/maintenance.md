---
type: Playbook
title: Manutenzione del bundle OKF
description: Come aggiornare la knowledge base quando cambiano agenti, API, dataset o paper.
tags:
- knowledge
- maintenance
- okf
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../AGENTS.md
  title: 'MURENA repository: AGENTS.md'
- resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
  title: Specifica OKF
---

# Manutenzione del bundle OKF

## Regole operative

- `docs/okf/index.md` è l'entry point; aprire solo i concetti necessari al task (**progressive disclosure**).
- Ogni concetto `.md` contiene YAML frontmatter valido con `type` non vuoto e fonti concrete se disponibili.
- Modificare insieme documenti, eventuali indici e `log.md` (date ISO; ultimo aggiornamento in cima).
- Non inserire `verified` senza una prova documentata. `generated.at` descrive quando un concetto è stato scritto, non quando il codice è stato eseguito.
- Conservare link Markdown standard relativi al bundle; evitare riferimenti a repository o ambienti privati non portabili.
- In caso di cambiamento di query, schema o metodo, aggiornare anche metriche e le limitazioni, non soltanto la sezione UI.

## Casi comuni

| Modifica | Documenti da controllare |
|---|---|
| Nuovo endpoint | `api/endpoints.md`, `api/contracts.md`, `frontend/state-and-network.md` |
| Nuovo agente/LLM | `agents/`, `architecture/analysis-flow.md`, `data/scoring.md` |
| Variazione Parquet | `data/estate-schema.md`, `data/datasets-and-lineage.md`, SQL agent |
| Nuovi benchmark | `research/benchmarks.md`, `research/reproduction.md`, `research/limitations.md` |
| Deploy non demo | `operations/quickstart.md`, `operations/security.md`, `operations/environment.md` |

La specifica di riferimento è **Open Knowledge Format v0.2**; le directory scelte sono una convenzione del progetto, non una tassonomia imposta dallo standard.
