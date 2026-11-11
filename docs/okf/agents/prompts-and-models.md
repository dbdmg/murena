---
type: Reference
title: Prompt, schemi tipizzati e provider LLM
description: Guida a gestione prompt, scelta provider e validazione degli output degli agenti.
tags:
- agents
- prompts
- models
generated:
  by: process:okf-documentation-generator
  at: '2026-11-10T16:18:43Z'
sources:
- resource: ../../../backend/app/services/llm/prompt_config.md
  title: 'MURENA repository: backend/app/services/llm/prompt_config.md'
- resource: ../../../backend/app/services/llm/prompt_loader.py
  title: 'MURENA repository: backend/app/services/llm/prompt_loader.py'
- resource: ../../../backend/app/services/llm/langchain_client.py
  title: 'MURENA repository: backend/app/services/llm/langchain_client.py'
- resource: ../../../backend/app/services/llm/providers.py
  title: 'MURENA repository: backend/app/services/llm/providers.py'
- resource: ../../../backend/app/services/llm/agents/schema.py
  title: 'MURENA repository: backend/app/services/llm/agents/schema.py'
---

# Prompt, schemi tipizzati e provider LLM

## Fonte unica dei prompt

I template sono memorizzati in `app/services/llm/prompt_config.md`, con sezioni `## nome_agente.system` e `## nome_agente.user`. `prompt_loader.py` risolve i template e le eventuali modifiche da API (`/prompts`).

## Contratti tipizzati

`agents/schema.py` definisce le strutture Pydantic per vincoli, geocoding, categorie, SQL, valutazione, pesi, rank e proposte di rilassamento. È preferibile aggiornare **schema, prompt, consumer e DTO** congiuntamente anziché modificare il solo testo di prompt.

## Provider

`langchain_client.py` e `providers.py` gestiscono adapter tra OpenAI, Gemini, Anthropic, Ollama e server OpenAI-compatible, come vLLM; la scelta dipende dalle variabili di ambiente e dal modello configurato. Non inserire mai chiavi o endpoint privati nei documenti OKF.

## Percorso di modifica

1. Identificare agente e schema Pydantic.
2. Aggiornare prompt e contratto, quando necessario.
3. Verificare uso del risultato nel grafo e nei servizi.
4. Eseguire esperimenti comparabili con modello, seed, query e dataset espliciti.
5. Registrare modifiche in `docs/okf/log.md` e nei test.
