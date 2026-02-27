# Agenti LLM (LangChain)

Questo pacchetto definisce l'architettura degli agenti LLM per l'applicazione, basata su LangChain. 
Gli agenti incapsulano compiti specifici (estrazione location, generazione SQL, valutazione tecnica, ecc.) con input/outputs strutturati.

> ℹ **Nota:** Per la documentazione architettonica completa del sistema multi-agente, inclusi diagrammi di sequenza e retry logic, fare riferimento a [`../../../../../docs/AGENT_ARCHITECTURE.md`](../../../../../docs/AGENT_ARCHITECTURE.md).

## Architettura
- `BaseAgent`: interfaccia astratta con metodo `run(**kwargs)`.
- `schema.py`: modelli Pydantic di I/O per garantire output affidabili e tipizzati.
- `location_agent.py`: agente specializzato nell'estrarre luoghi da una query naturale.
- `langchain_client.get_llm()`: factory per ottenere l'LLM (Gemini) configurato tramite env.

## Convenzioni
- Ogni agente espone:
  - `name`: stringa identificativa.
  - `run(...)`: ritorna un modello Pydantic di risultato.
  - Prompt in italiano, chiaro e vincolato a un output JSON.
- Output: strutturato (JSON) e convertito in Pydantic prima di essere restituito.

## Integrazione (esempio)
```python
from app.llm.agents.location_agent import LocationAgent

agent = LocationAgent()
result = agent.run(query="trova edifici vicino a Piazza Statuto")
print(result.places)  # [Place(name="Piazza Statuto", city="Torino"), ...]
```

## Env vars
- `GEMINI_KEY`: chiave API Google Generative AI.
- `GEMINI_MODEL_FAST`: nome modello (default: `gemini-1.5-flash`).
- `LLM_TEMPERATURE`: temperatura opzionale (default: `0.0`).

## Note
- Il modello `gemini-2.0-*` potrebbe non essere ancora supportato dall'integrazione LangChain. In caso, usare `gemini-1.5-flash`/`pro` o aggiornare il pacchetto `langchain-google-genai`.