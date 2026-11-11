---
type: Research Metric
title: Metriche e risultati dichiarati nel paper
description: Numeri sperimentali e relative popolazioni, senza presentarli come test effettuati ora.
tags:
- research
- benchmark
- evaluation
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Metriche e risultati dichiarati nel paper

## Setup dichiarato

Paper su dataset reale vicino a **90.000** edifici/record EPC in una grande città italiana, con **486 query combinatorie**, di cui **64** attivano tutte e cinque le dimensioni tecniche. Modelli open-weight eseguiti localmente: `gpt-oss-120b`, `gemma3-27b`, `qwen3-8b`. Modello closed-weight `gpt-5.4` usato come baseline esterna / giudice, non come modello del pipeline valutato.

## Routing agenti (486 query)

| Indicatore | gpt-oss-120b | gemma3-27b | qwen3-8b |
|---|---:|---:|---:|
| Perfect Match Ratio | **90,3%** | 54,5% | 54,9% |
| Mean Jaccard | **0,972** | 0,863 | 0,861 |

## Ranking e qualità (subset di 64 query full)

| Indicatore | gpt-oss-120b | gemma3-27b | qwen3-8b |
|---|---:|---:|---:|
| Self-query IoU su 3 prove | 0,705 | **0,820** | 0,720 |
| Precisione *Pros* stimata da LLM-as-judge | 69,8% | **79,5%** | 63,5% |
| Precisione *Cons* stimata da LLM-as-judge | 52,8% | **68,9%** | 50,4% |

## Valutazione umana

Due esperti senior hanno valutato **10** scenari di cambio d'uso; nel **9/10** il top-5 MURENA includeva almeno un immobile preferito dagli esperti. Questo **non significa** che 90% degli edifici top-5 coincidano con la lista manuale. Fra gli edifici alternativi suggeriti, l'**80%** è stato giudicato rilevante da entrambi. Tempo medio di esecuzione riportato: **55 secondi**.

## Ablation / baseline SQL

Il paper riporta una Domain Coverage F1 di **0,757** per le due baseline monolitiche `gpt-5.4`, contro **1,0** per l'architettura multi-agente nei confronti effettuati. Non considerare 1,0 come accuratezza universale fuori dal protocollo sperimentale.

## Attribuzione

Tutti questi numeri sono **trascritti dal manoscritto**: non sono misurazioni ottenute nel presente ambiente e non valgono per il dataset sintetico. Si raccomanda di usare la versione finale pubblicata del paper per citazioni esterne.
