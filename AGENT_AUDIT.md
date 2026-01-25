# 🔍 Agent Architecture Audit - Real Estate AI

**Data Audit:** Gennaio 2025  
**Obiettivo:** Valutazione completa dell'implementazione degli agenti LangChain/LangGraph  
**Scope:** Tutti gli agenti in `backend/app/services/llm/agents/`

---

## 📋 Executive Summary

### Stato Attuale
L'architettura multi-agente è solida ma presenta **diverse aree di miglioramento**:

| Area | Stato | Priorità |
|------|-------|----------|
| Struttura LangChain | ✅ Buona | - |
| Output Parsing | ⚠️ Inconsistente | Alta |
| Dati agli Agenti | ❌ Insufficiente (APE) | Critica |
| Prompt Engineering | ⚠️ Da ottimizzare | Media |
| Error Handling | ✅ Decoratori presenti | - |
| LangGraph Flow | ✅ Solido | - |

### Issues Critiche Identificate
1. **APE Agent riceve solo nomi colonne** - non può vedere dati reali
2. **Parsing JSON manuale** duplicato in più agenti
3. **Prompt troppo lunghi** in alcuni agenti (NeedsMetricAgent)
4. **Mancanza di retry logic** consistente

---

## 🏗️ Architettura Agenti

### Gerarchia e Flusso

```
┌─────────────────────────────────────────────────────────────────┐
│                    GraphOrchestratorAgent                        │
│                    (LangGraph StateGraph)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐         ┌───────────┐         ┌──────────┐
   │ PHASE 1 │         │  PHASE 2  │         │ PHASE 3  │
   │ Analyze │         │  Execute  │         │ Evaluate │
   └─────────┘         └───────────┘         └──────────┘
        │                     │                     │
   ┌────┴────┐                │              ┌──────┴──────┐
   │ Parallel│                │              │   Serial    │
   │ 5 agents│                │              │   2 steps   │
   └────┬────┘                │              └──────┬──────┘
        │                     │                     │
   TypologyAgent              │              EvaluationAgent
   LocationAgent         SQLAgent            BrokerReview
   NeedsMetricAgent           │
   ApeAgent                   │
   PoiAgent                   │
```

### Dettaglio Agenti

| Agente | Input | Output | Parsing | Modello |
|--------|-------|--------|---------|---------|
| LocationAgent | query | places[] | Manual JSON | configurable |
| TypologyAgent | query, available_typologies | typologies[] | Manual JSON | configurable |
| NeedsMetricAgent | query, db_schema, dataset_sample, db_metadata | NeedsMetricPlan | Manual JSON | configurable |
| SQLAgent | query, scheme, location, db_metadata | SQLAgentResult | String cleanup | configurable |
| ApeAgent | query, columns[] | ApeAgentResult | String + FILTRO: parsing | configurable |
| PoiAgent | query | PoiAgentResult | Manual JSON | configurable |
| EvaluationAgent | use_case, estates_data, query | EvaluationResult[] | `with_structured_output` | configurable |
| MapAssistantAgent | messages, context | MapAssistantResponse | `with_structured_output` | configurable |

---

## 🔴 Issue #1: APE Agent - Dati Mancanti (CRITICA)

### Problema Attuale
L'APE Agent riceve **solo i nomi delle colonne**, non i dati statistici:

```python
# graph_agent.py - riga 396
def run_ape():
    return self.ape_agent.run(query, dataset_metadata.get("columns", []))
```

```python
# ape_agent.py - riga 63
def run(self, query: str, columns: list[str] = None) -> ApeAgentResult:
    columns_desc = ", ".join(columns)  # Solo nomi!
```

### Impatto
- L'agente **non può suggerire filtri efficaci** perché non conosce la distribuzione dei dati
- Le raccomandazioni sono generiche e teoriche
- Non può identificare outlier o pattern nei dati APE

### Soluzione Proposta

```python
# NUOVO: Passare statistiche aggregate invece di solo colonne
def _get_ape_statistics(df: pd.DataFrame) -> dict:
    """Estrae statistiche APE rilevanti per l'agente."""
    ape_cols = [c for c in df.columns if c.startswith('ape_') or c == 'classe_energetica_ape']
    
    stats = {}
    for col in ape_cols:
        if df[col].dtype in ['int64', 'float64']:
            stats[col] = {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": float(df[col].mean()),
                "median": float(df[col].median()),
            }
        else:
            # Categorie
            stats[col] = df[col].value_counts().head(10).to_dict()
    
    return stats
```

### Piano d'Azione APE
1. ⬜ Creare `_get_ape_statistics()` in `graph_agent.py`
2. ⬜ Modificare `ApeAgent.run()` per accettare `statistics: dict`
3. ⬜ Aggiornare il prompt per includere le statistiche
4. ⬜ Testare con query reali

---

## 🟠 Issue #2: Output Parsing Inconsistente (ALTA)

### Stato Attuale

| Agente | Metodo Parsing | Problemi |
|--------|---------------|----------|
| LocationAgent | `_extract_json()` manuale | Duplicato |
| TypologyAgent | `_extract_json()` manuale | Duplicato |
| NeedsMetricAgent | `_extract_json()` manuale | Duplicato |
| ApeAgent | String parsing con "FILTRO:" | Fragile |
| PoiAgent | `_extract_json()` manuale | Duplicato |
| EvaluationAgent | `with_structured_output()` | ✅ Best practice |
| SQLAgent | String cleanup | OK per SQL |

### Problema
- **Codice duplicato** per l'estrazione JSON in 5 agenti
- **Mancanza di validazione** strutturale
- **Nessun fallback consistente** per parsing falliti

### Soluzione Proposta

**Opzione A: Structured Output Nativo (Preferita)**
```python
# Usare with_structured_output() per tutti gli agenti
from pydantic import BaseModel

class LocationResponse(BaseModel):
    places: List[Place]

# Nel costruttore dell'agente
if hasattr(self.llm, "with_structured_output"):
    self.chain = self.prompt | self.llm.with_structured_output(LocationResponse)
```

**Opzione B: Utility Centralizzata**
```python
# utils/json_parser.py
def safe_extract_json(text: str, schema: Type[BaseModel]) -> Optional[BaseModel]:
    """Parser JSON robusto con validazione Pydantic."""
    ...
```

### Piano d'Azione Parsing
1. ⬜ Creare `utils/json_parser.py` con utility condivise
2. ⬜ Migrare LocationAgent a `with_structured_output()`
3. ⬜ Migrare TypologyAgent a `with_structured_output()`
4. ⬜ Migrare NeedsMetricAgent a `with_structured_output()`
5. ⬜ Migrare PoiAgent a `with_structured_output()`
6. ⬜ Convertire ApeAgent da "FILTRO:" a JSON strutturato

---

## 🟠 Issue #3: Prompt Engineering (MEDIA)

### Analisi dei Prompt

#### NeedsMetricAgent (Troppo Lungo)
```
Lunghezza system prompt: ~1800 caratteri
Complessità: Alta (BLACKLIST, metriche, strategia)
```

**Problemi:**
- BLACKLIST hardcoded nel prompt (difficile da mantenere)
- Molte istruzioni negative ("NON fare X")
- Formato JSON complesso da generare

**Miglioramenti:**
```python
# Separare le istruzioni in blocchi logici
BLACKLIST_COLUMNS = ["sanita", "mobilita", "verde", ...]

# Prompt più conciso
DEFAULT_SYSTEM = """Sei il Needs & Metric Agent.
Obiettivo: Interpretare la query e creare un piano di analisi.

REGOLE FILTRI SQL:
- ✅ Usa: superficie, tipologia, distanza geografica
- ❌ Non usare: {blacklist_cols}

Output JSON richiesto:
{format_instructions}"""
```

#### SQLAgent (OK ma migliorabile)
```
Lunghezza: ~1200 caratteri
```

**Miglioramenti:**
- Aggiungere esempi concreti di query corrette
- Specificare meglio quando usare/non usare LIMIT

#### EvaluationAgent (Buono)
```
Lunghezza: ~1400 caratteri
Usa format_instructions: Sì ✅
```

### Piano d'Azione Prompt
1. ⬜ Refactoring NeedsMetricAgent con BLACKLIST dinamica
2. ⬜ Aggiungere few-shot examples a SQLAgent
3. ⬜ Standardizzare struttura prompt (RUOLO → REGOLE → OUTPUT → ESEMPI)
4. ⬜ Documentare formato prompt nel README

---

## 🟢 Issue #4: LangGraph Flow (MINORE)

### Stato Attuale - graph_agent.py

```python
# Nodi definiti
workflow.add_node("analyze_request", self._analyze_request)
workflow.add_node("generate_sql", self._generate_sql)
workflow.add_node("execute_sql", self._execute_sql)
workflow.add_node("handle_retry", self._handle_retry)
workflow.add_node("fallback_results", self._fallback_results)
workflow.add_node("enrich_results", self._enrich_results)
workflow.add_node("rank_results", self._rank_results)
workflow.add_node("evaluate_results", self._evaluate_results)
workflow.add_node("broker_review", self._broker_review)
workflow.add_node("finalize_results", self._finalize_results)

# Edge condizionale per retry
workflow.add_conditional_edges(
    "execute_sql",
    self._check_sql_execution,
    {
        "retry": "handle_retry",
        "retry_relax": "handle_retry",
        "fallback": "fallback_results",
        "continue": "enrich_results",
    },
)
```

### Valutazione
- ✅ Retry logic implementata (max 5 tentativi)
- ✅ Fallback robusto quando tutto fallisce
- ✅ Parallel execution per agenti indipendenti
- ⚠️ `recursion_limit=50` potrebbe essere eccessivo

### Miglioramenti Suggeriti
1. ⬜ Aggiungere logging strutturato per ogni nodo
2. ⬜ Considerare checkpoint/persistence per debug
3. ⬜ Ridurre `recursion_limit` a 30 (più sicuro)

---

## 🟢 Issue #5: Error Handling (MINORE)

### Stato Attuale
```python
# Decoratore handle_agent_error presente
@handle_agent_error(
    fallback_value=LocationAgentResult(raw_text="Error", places=[], prompt=None)
)
def run(self, *, query: str) -> LocationAgentResult:
```

### Valutazione
- ✅ Decoratore `@handle_agent_error` usato consistentemente
- ✅ Fallback values definiti per ogni agente
- ⚠️ Log degli errori potrebbe essere più dettagliato

### Miglioramenti
1. ⬜ Aggiungere traceback completo nei log errori
2. ⬜ Implementare circuit breaker per fallimenti ripetuti
3. ⬜ Metriche di failure rate per agente

---

## 📊 Confronto Best Practices LangChain

| Best Practice | Stato | Note |
|--------------|-------|------|
| Usare ChatPromptTemplate | ✅ | Tutti gli agenti |
| Separare system/user prompt | ✅ | Implementato |
| Usare with_structured_output | ⚠️ | Solo EvaluationAgent |
| Prompt esterni configurabili | ✅ | prompt_loader.py |
| Streaming responses | ❌ | Non implementato |
| Token counting | ⚠️ | @log_llm_usage presente ma basic |
| Retry con backoff | ⚠️ | Solo in SQLAgent |
| Caching responses | ❌ | Non implementato |

---

## 📋 Piano d'Azione Completo

### Priorità 1 - Critica (Impatto Funzionale)

| # | Task | File | Stima |
|---|------|------|-------|
| 1.1 | Arricchire APE Agent con statistiche dataset | `graph_agent.py`, `ape_agent.py` | 2h |
| 1.2 | Testare APE Agent con query energetiche reali | `tests/` | 1h |

### Priorità 2 - Alta (Qualità Codice)

| # | Task | File | Stima |
|---|------|------|-------|
| 2.1 | Creare `utils/json_parser.py` centralizzato | `utils/` | 1h |
| 2.2 | Migrare LocationAgent a structured output | `location_agent.py` | 30m |
| 2.3 | Migrare TypologyAgent a structured output | `typology_agent.py` | 30m |
| 2.4 | Migrare NeedsMetricAgent a structured output | `needs_metric_agent.py` | 1h |
| 2.5 | Migrare PoiAgent a structured output | `poi_agent.py` | 30m |
| 2.6 | Convertire ApeAgent da FILTRO: a JSON | `ape_agent.py` | 1h |

### Priorità 3 - Media (Ottimizzazione)

| # | Task | File | Stima |
|---|------|------|-------|
| 3.1 | Refactoring prompt NeedsMetricAgent | `needs_metric_agent.py`, `prompt_config.md` | 1h |
| 3.2 | Aggiungere few-shot examples a SQLAgent | `sql_agent.py`, `prompt_config.md` | 1h |
| 3.3 | Standardizzare struttura prompt | Tutti i prompt | 2h |
| 3.4 | Documentare formato prompt nel README | `agents/README.md` | 30m |

### Priorità 4 - Bassa (Nice to Have)

| # | Task | File | Stima |
|---|------|------|-------|
| 4.1 | Implementare response caching | `langchain_client.py` | 2h |
| 4.2 | Aggiungere streaming per EvaluationAgent | `evaluation_agent.py`, `graph_agent.py` | 3h |
| 4.3 | Ridurre recursion_limit a 30 | `graph_agent.py` | 5m |
| 4.4 | Aggiungere metriche failure rate | `utils/metrics.py` | 2h |

---

## 🔧 Codice di Riferimento

### Esempio: Migrazione a Structured Output

```python
# PRIMA (location_agent.py)
class LocationAgent(BaseAgent):
    def __init__(self):
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser

    def run(self, *, query: str) -> LocationAgentResult:
        raw = self.chain.invoke({"query": query})
        data = _extract_json(raw) or {"places": []}  # Parsing manuale
        ...

# DOPO
from pydantic import BaseModel

class LocationResponse(BaseModel):
    places: List[Place]

class LocationAgent(BaseAgent):
    def __init__(self):
        if hasattr(self.llm, "with_structured_output"):
            self.chain = self.prompt | self.llm.with_structured_output(LocationResponse)
        else:
            # Fallback per modelli senza supporto nativo
            self.parser = PydanticOutputParser(pydantic_object=LocationResponse)
            self.chain = self.prompt | self.llm | self.parser

    def run(self, *, query: str) -> LocationAgentResult:
        result = self.chain.invoke({"query": query})
        # result è già un LocationResponse validato!
        return LocationAgentResult(
            raw_text=str(result),
            places=result.places,
            prompt=...
        )
```

### Esempio: APE Agent con Statistiche

```python
# graph_agent.py - Nuova funzione
def _get_ape_statistics(self, dataset_path: str) -> dict:
    """Estrae statistiche APE per l'agente."""
    try:
        df = pd.read_parquet(dataset_path)
        ape_cols = [c for c in df.columns if 'ape' in c.lower() or c == 'classe_energetica_ape']
        
        stats = {"total_records": len(df)}
        for col in ape_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                stats[col] = {
                    "min": round(df[col].min(), 2),
                    "max": round(df[col].max(), 2),
                    "mean": round(df[col].mean(), 2),
                    "percentiles": {
                        "25%": round(df[col].quantile(0.25), 2),
                        "50%": round(df[col].quantile(0.50), 2),
                        "75%": round(df[col].quantile(0.75), 2),
                    }
                }
            else:
                stats[col] = df[col].value_counts().head(8).to_dict()
        
        return stats
    except Exception as e:
        return {"error": str(e)}

# Uso in _analyze_request
def run_ape():
    if self.is_agent_mode or any(k in query.lower() for k in keywords):
        ape_stats = self._get_ape_statistics(state.get("dataset_path"))
        return self.ape_agent.run(
            query=query,
            columns=dataset_metadata.get("columns", []),
            statistics=ape_stats  # NUOVO
        )
    return None
```

---

## 📝 Note Finali

### Cosa Funziona Bene
1. **Architettura modulare** - ogni agente è indipendente e testabile
2. **Configurabilità modelli** - `AGENT_MODELS` permette override per agente
3. **Prompt esterni** - `prompt_config.md` permette tuning senza deploy
4. **LangGraph flow** - gestione robusta di retry e fallback
5. **Tracciamento prompt** - `PromptRecord` per debug

### Cosa Richiede Attenzione
1. **APE Agent cieco** - deve vedere i dati, non solo i nomi
2. **Parsing duplicato** - consolidare in utility condivisa
3. **Prompt lunghi** - rischio di confusione per il modello
4. **Mancanza caching** - chiamate ripetute costose

### Metriche di Successo
Dopo l'implementazione del piano:
- [ ] APE Agent suggerisce filtri basati su percentili reali
- [ ] Zero `_extract_json()` duplicati nel codice
- [ ] Tutti gli agenti usano `with_structured_output()` o fallback Pydantic
- [ ] Prompt < 1500 caratteri ciascuno
- [ ] Test coverage agenti > 80%

---

*Documento generato automaticamente durante la sessione di audit.*  
*Ultimo aggiornamento: Gennaio 2025*
