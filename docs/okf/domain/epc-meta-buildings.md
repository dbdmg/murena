---
type: Domain Concept
title: APE/EPC e meta-building
description: Significato dei certificati energetici e aggregazione catastale per valutazioni di edificio.
tags:
- domain
- energy
- cadastral
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/data/metadata/create_estate_dataset.py
  title: 'MURENA repository: backend/data/metadata/create_estate_dataset.py'
- resource: ../../../backend/data/metadata/create_demo_dataset.py
  title: 'MURENA repository: backend/data/metadata/create_demo_dataset.py'
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# APE/EPC e meta-building

L'**Attestato di Prestazione Energetica** (APE/EPC) descrive attributi tecnici ed energetici di un'unità immobiliare: classe energetica, superficie, prestazione primaria non rinnovabile (`EPgl,nren`), sistema di riscaldamento e altri campi.

Un **meta-building** raggruppa unità/attestati che condividono identificativi catastali e rappresentano un fabbricato da valutare nel suo insieme. La pipeline di ricerca conserva i riferimenti alle unità componenti. Il dataset demo contiene campi come `meta_building`, `is_meta`, `cadastral_units_count`, `id_list`.

## Caveat sul dato

- Un attestato è riferito a una **unità**, non necessariamente a un intero edificio.
- APE non costituisce un censimento esaustivo: la disponibilità segue compravendite, locazioni e ristrutturazioni.
- Registrazioni ripetute, aggiornamenti, coordinate/aree errate e la metodologia post-2015 incidono sulla comparabilità.
- Il paper descrive deduplicazione mantenendo il certificato più recente, aggregazione catastale e successivo arricchimento con zone OMI/POI; è una **procedura di ricerca**, non un'operazione effettuata dalla demo sintetica.

Leggere [lineage dei dataset](../data/datasets-and-lineage.md) e [schema](../data/estate-schema.md).
