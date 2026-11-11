---
type: Research Reference
title: Limiti scientifici e validità esterna
description: Limiti del dataset EPC, del modello POI e dell’evidenza di validazione.
tags:
- research
- limitations
- ethics
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../references/paper/paper.tex
  title: Manoscritto LaTeX MURENA fornito dall’utente
---

# Limiti scientifici e validità esterna

Il manoscritto segnala alcuni limiti da mantenere visibili in ogni riuso della piattaforma:

- **Ground truth:** non esiste una verità univoca per richieste urbane multi-criterio; la validazione umana su 10 scenari è utile ma circoscritta.
- **Query ambigue:** richieste poco specifiche possono attivare configurazioni subottimali di agenti; il paper propone raffinamento conversazionale futuro.
- **POI:** categorie aggregate non distinguono sempre la gerarchia dei servizi (ad esempio metro vs fermata di bus).
- **EPC:** dati auto-dichiarati/compilati soggetti a errori e prevalentemente residenziali; rappresentatività limitata per asset specializzati.
- **Normativa:** le regole statiche richiedono verifica di aggiornamento e giurisdizione per applicazioni reali.
- **Spiegazioni LLM:** i *cons* risultano più difficili da verificare delle osservazioni positive negli esperimenti.

La generazione sintetica locale introduce un ulteriore limite, separato dai vincoli di ricerca: nessun risultato della demo deve essere interpretato come evidenza su un immobile reale.
