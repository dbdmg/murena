---
type: Dataset
title: Dataset sintetico demo
description: Generatore demo riproducibile, limiti, variazioni e cautele interpretative.
tags:
- data
- demo
- synthetic
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/data/metadata/create_demo_dataset.py
  title: 'MURENA repository: backend/data/metadata/create_demo_dataset.py'
- resource: ../../../run_app.py
  title: 'MURENA repository: run_app.py'
- resource: ../../../README.md
  title: 'MURENA repository: README.md'
---

# Dataset sintetico demo

## Generazione

```bash
uv run python backend/data/metadata/create_demo_dataset.py
# Opzioni disponibili:
uv run python backend/data/metadata/create_demo_dataset.py --n 1500 --seed 42
```

Lo script non sovrascrive un Parquet esistente senza `--force`. Il launcher lo genera automaticamente se `estates.parquet` è assente e non è richiesto `--real-data-init`.

## Proprietà del campione

Coordinate in un rettangolo geografico di Torino; classe energetica, periodo di costruzione, superficie, rendita e score POI/energia simulati con distribuzioni pseudo-casuali. Una quota dei record è contrassegnata come meta-building, con sottounità sintetiche.

**Non usare** questi record per stime di patrimonio reale, conformità o valutazioni quantitative delle prestazioni scientifiche del sistema. Le correlazioni di energia/centralità sono *costruite dal generatore*, non osservazioni empiriche.

[Lineage](datasets-and-lineage.md) · [Riproduzione paper](../research/reproduction.md).
