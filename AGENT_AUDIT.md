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

## � Mappatura Colonne per Agente

### Dataset Completo (41 colonne)

Il dataset `immobili_with_meta_and_ape_full_cleaned.parquet` contiene:

| Categoria | Colonne | Descrizione |
|-----------|---------|-------------|
| **Identificazione** | id, codice_comune, foglio, particella, subalterno | Identificativi catastali |
| **Localizzazione** | indirizzo, numero_civico, latitudine, longitudine, zona_omi | Dati geografici |
| **Caratteristiche** | superficie_di_riferimento_mq, natura_del_bene, tipologia_bene_immobile, epoca_costruzione | Proprietà fisiche |
| **Stato Giuridico** | vincolo_culturale_paesaggistico, natura_giuridica_del_bene, utilizzo_del_bene, finalita | Status legale/uso |
| **Contratti** | tipo_detenzione_a_terzi, canone_annuale, data_decorrenza | Info locazione |
| **APE Grezzi** | classe_energetica_ape, epglnren_ape, classe_target_ape, lista_file_ape, list_file_ape_filtered | Dati certificazione |
| **APE Scores** | ape_score_classe, ape_score_impianto, ape_score_involucro, ape_score_rinnovabili, ape_score_total | Punteggi 1-5 |
| **POI Scores** | sanita, mobilita, verde, sport, commerciale, educazione | Punteggi 1-5 |
| **Meta** | meta_immobile, numero_immobili_per_catasto, id_list | Flag e aggregazioni |

---

### 📖 Legenda Punteggi (da includere nei prompt)

#### APE Scores (Efficienza Energetica) - Scala 1-5

| Punteggio | Campo | Significato |
|-----------|-------|-------------|
| **ape_score_classe** | Classe Energetica | 5=A1-A4 (ottimo), 3=B-E (medio), 1=F-G (scarso) |
| **ape_score_impianto** | Tipo Impianto | 5=Pompa di calore/Teleriscaldamento, 3=Condensazione/Biomassa, 1=Tradizionale |
| **ape_score_involucro** | Qualità Involucro | 5=Ottimo isolamento, 3=Medio, 1=Scarso/Assente |
| **ape_score_rinnovabili** | Fonti Rinnovabili | 5=Presenti, 1=Assenti |
| **ape_score_total** | Media Complessiva | Media ponderata dei 4 punteggi sopra |

#### POI Scores (Servizi di Prossimità) - Scala 1-5

| Punteggio | Campo | Cosa Misura |
|-----------|-------|-------------|
| **sanita** | Servizi Sanitari | Ospedali, farmacie, ambulatori nel raggio di 1km |
| **mobilita** | Trasporti | Fermate metro/bus, stazioni ferroviarie |
| **verde** | Aree Verdi | Parchi, giardini pubblici, aree naturali |
| **sport** | Impianti Sportivi | Palestre, piscine, campi sportivi |
| **commerciale** | Commercio | Negozi, supermercati, centri commerciali |
| **educazione** | Istruzione | Scuole, università, biblioteche |

> **Interpretazione**: 1=Scarsa copertura, 2=Sufficiente, 3=Buona, 4=Ottima, 5=Eccellente

---

### 🎯 Selezione Colonne per Agente

#### 1. LocationAgent
**Scopo**: Estrae luoghi/POI dalla query utente  
**Input necessario**: Solo la query testuale  
**Colonne nel prompt**: Nessuna (lavora solo sul testo)

```
Input: query (string)
Output: places[] con name, city, lat, lon
```

---

#### 2. TypologyAgent
**Scopo**: Identifica tipologie di immobile richieste  
**Input necessario**: Query + lista tipologie disponibili

**Colonne da passare**:
```python
TYPOLOGY_COLUMNS = []  # Nessuna colonna, solo metadata

# Passare invece i valori possibili dal db_metadata:
available_typologies = db_metadata["tipologia_bene_immobile"]["values"]
```

---

#### 3. NeedsMetricAgent
**Scopo**: Crea piano di analisi con metriche, filtri, strategia  
**Input necessario**: Query + schema DB completo

**Colonne da documentare nel prompt** (per generare filtri corretti):
```python
NEEDS_METRIC_COLUMNS = {
    # Filtrabili via SQL (oggettivi)
    "filterable": [
        "superficie_di_riferimento_mq",
        "tipologia_bene_immobile",
        "natura_del_bene",
        "epoca_costruzione",
        "vincolo_culturale_paesaggistico",
        "natura_giuridica_del_bene",
        "utilizzo_del_bene",
        "finalita",
        "zona_omi",
        "latitudine",
        "longitudine",
    ],
    # NON filtrabili via SQL (da usare per ranking)
    "ranking_only": [
        "ape_score_classe",
        "ape_score_impianto", 
        "ape_score_involucro",
        "ape_score_rinnovabili",
        "ape_score_total",
        "sanita",
        "mobilita",
        "verde",
        "sport",
        "commerciale",
        "educazione",
    ],
}
```

---

#### 4. SQLAgent
**Scopo**: Genera query DuckDB per filtrare il dataset  
**Input necessario**: Query + schema + location + metadata

**Schema da passare** (colonne e tipi):
```python
SQL_AGENT_SCHEMA = {
    "id": "int64 - Identificativo univoco",
    "codice_comune": "string - Codice catastale (L219=Torino)",
    "superficie_di_riferimento_mq": "float - Superficie in mq (1-184556)",
    "latitudine": "float - Coordinata GPS",
    "longitudine": "float - Coordinata GPS",
    "tipologia_bene_immobile": "string - Tipo immobile (vedi valori)",
    "natura_del_bene": "string - FABBRICATO o TERRENO",
    "epoca_costruzione": "string - Periodo costruzione",
    "vincolo_culturale_paesaggistico": "string - Vincoli",
    "natura_giuridica_del_bene": "string - Demanio/Patrimonio",
    "utilizzo_del_bene": "string - Stato utilizzo attuale",
    "finalita": "string - Uso previsto",
    "zona_omi": "string - Zona OMI di riferimento",
    # APE e POI scores NON devono essere usati in WHERE
}
```

**Istruzioni critiche nel prompt**:
```
NON filtrare MAI per:
- ape_score_* (punteggi energetici)
- sanita, mobilita, verde, sport, commerciale, educazione (punteggi POI)
Questi campi saranno usati per il RANKING, non per il filtraggio.
```

---

#### 5. ApeAgent 🔴 (DA ARRICCHIRE)
**Scopo**: Analizza requisiti energetici e suggerisce strategia APE  
**Input necessario**: Query + statistiche APE reali

**Colonne specifiche APE**:
```python
APE_AGENT_COLUMNS = [
    "classe_energetica_ape",      # Classe A1-G
    "epglnren_ape",               # Consumo kWh/m²/anno
    "classe_target_ape",          # Classe target post-riqualificazione
    "ape_score_classe",           # Score 1-5
    "ape_score_impianto",         # Score 1-5
    "ape_score_involucro",        # Score 1-5
    "ape_score_rinnovabili",      # Score 1-5
    "ape_score_total",            # Score 1-5 (media)
]
```

**Statistiche da passare** (NUOVO):
```python
APE_STATISTICS = {
    "total_records": 14915,
    "with_ape_data": 1234,  # Quanti hanno dati APE
    "classe_energetica_ape": {
        "G": 450, "F": 320, "E": 180, "D": 120, 
        "C": 80, "B": 50, "A1": 20, "A2": 10, "A4": 4
    },
    "ape_score_total": {
        "min": 1.0, "max": 5.0, "mean": 2.08, "median": 2.0,
        "percentiles": {"25%": 1.5, "50%": 2.0, "75%": 2.5}
    },
    # ... altre statistiche
}
```

**Prompt arricchito**:
```
Sei un esperto di efficienza energetica.

STATISTICHE DATASET APE:
- Totale immobili: {total_records}
- Con dati APE: {with_ape_data} ({percentage}%)
- Distribuzione classi: {classe_distribution}
- Score medio totale: {mean_score} (mediana: {median_score})

LEGENDA PUNTEGGI (1-5):
- ape_score_classe: 5=A1-A4, 3=B-E, 1=F-G
- ape_score_impianto: 5=Pompa calore, 3=Condensazione, 1=Tradizionale
- ape_score_involucro: 5=Ottimo isolamento, 1=Scarso
- ape_score_rinnovabili: 5=Presenti, 1=Assenti

Analizza la richiesta e suggerisci una strategia energetica.
```

---

#### 6. PoiAgent
**Scopo**: Assegna pesi alle categorie POI in base alla query  
**Input necessario**: Solo query (conosce le 6 categorie)

**Categorie POI** (hardcoded nel prompt):
```python
POI_CATEGORIES = {
    "sanita": "Ospedali, farmacie, ambulatori",
    "mobilita": "Metro, bus, stazioni",
    "verde": "Parchi, giardini",
    "sport": "Palestre, piscine, campi",
    "commerciale": "Negozi, supermercati",
    "educazione": "Scuole, università",
}
```

**Output**: `poi_weights` dict con valori 0.0-1.0 per categoria

---

#### 7. EvaluationAgent ✅ (Già ottimizzato)
**Scopo**: Valuta immobili candidati rispetto alla query  
**Input necessario**: Query + use_case + dati immobili (JSON)

**Colonne selezionate per la valutazione** (già implementate):
```python
EVAL_COLUMNS = [
    # Identificazione e localizzazione
    "id",
    "indirizzo",
    "numero_civico",
    "zona_omi",
    
    # Caratteristiche fisiche
    "superficie_di_riferimento_mq",
    "tipologia_bene_immobile",
    "epoca_costruzione",
    "utilizzo_del_bene",
    "finalita",
    
    # APE Scores (con legenda nel prompt)
    "classe_energetica_ape",
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
    
    # POI Scores (con legenda nel prompt)
    "sanita",
    "mobilita",
    "verde",
    "sport",
    "commerciale",
    "educazione",
    
    # Distanza (se calcolata)
    "tempo_minuti",
    "distanza_km",
]
```

**Legenda da includere nel prompt**:
```
LEGENDA PUNTEGGI (tutti su scala 1-5, dove 5=ottimo):

APE (Efficienza Energetica):
- ape_score_classe: Classe energetica (5=A, 1=G)
- ape_score_impianto: Qualità impianto termico
- ape_score_involucro: Isolamento edificio
- ape_score_rinnovabili: Presenza fonti rinnovabili
- ape_score_total: Media complessiva

POI (Servizi di Prossimità):
- sanita: Vicinanza a servizi sanitari
- mobilita: Accessibilità trasporti pubblici
- verde: Presenza aree verdi
- sport: Vicinanza impianti sportivi
- commerciale: Servizi commerciali
- educazione: Scuole e istruzione
```

---

#### 8. MapAssistantAgent
**Scopo**: Chatbot per interazione sulla mappa  
**Input necessario**: Messaggi + contesto analisi precedente

**Colonne nel contesto** (ereditate da EvaluationAgent):
```python
MAP_ASSISTANT_CONTEXT = {
    "current_results": "DataFrame con EVAL_COLUMNS",
    "filters_applied": "WHERE clause attiva",
    "user_query": "Query originale",
    "evaluation_results": "Valutazioni LLM",
}
```

---

### 🔧 Template Prompt Standardizzato

Struttura consigliata per tutti gli agenti:

```
## {AGENT_NAME}

### RUOLO
[Chi sei e cosa fai - 1-2 righe]

### CONTESTO DATI
[Legenda punteggi se applicabile]
[Statistiche dataset se applicabile]

### REGOLE
✅ Cosa DEVI fare
❌ Cosa NON devi fare

### OUTPUT
[Formato richiesto - JSON schema o testo]

### ESEMPI (opzionale)
[1-2 esempi input/output]
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
1. **APE Agent cieco** - deve vedere statistiche, non solo nomi colonne
2. **Parsing duplicato** - consolidare in utility condivisa
3. **Mancanza legenda nei prompt** - agenti non conoscono significato punteggi
4. **Mancanza caching** - chiamate ripetute costose

### Metriche di Successo
Dopo l'implementazione del piano:
- [ ] APE Agent suggerisce filtri basati su percentili reali
- [ ] Tutti i prompt includono legenda punteggi (APE + POI)
- [ ] Zero `_extract_json()` duplicati nel codice
- [ ] Tutti gli agenti usano `with_structured_output()` o fallback Pydantic
- [ ] Prompt < 1500 caratteri ciascuno
- [ ] Test coverage agenti > 80%

---

## 🚀 Piano di Implementazione Aggiornato

### Sprint 1: Fondamenta (Priorità Critica)

| Task | Descrizione | File | Done |
|------|-------------|------|------|
| 1.1 | Creare costante `SCORE_LEGEND` condivisa | `constants.py` | ⬜ |
| 1.2 | Arricchire ApeAgent con statistiche dataset | `graph_agent.py`, `ape_agent.py` | ⬜ |
| 1.3 | Aggiungere legenda punteggi a EvaluationAgent | `evaluation_agent.py` | ⬜ |
| 1.4 | Aggiungere legenda punteggi a NeedsMetricAgent | `needs_metric_agent.py` | ⬜ |

### Sprint 2: Qualità Codice (Priorità Alta)

| Task | Descrizione | File | Done |
|------|-------------|------|------|
| 2.1 | Creare `utils/json_parser.py` | `utils/json_parser.py` | ⬜ |
| 2.2 | Migrare a `with_structured_output()` | Tutti gli agenti | ⬜ |
| 2.3 | Standardizzare prompt (RUOLO→REGOLE→OUTPUT) | `prompt_config.md` | ⬜ |

### Sprint 3: Ottimizzazione (Priorità Media)

| Task | Descrizione | File | Done |
|------|-------------|------|------|
| 3.1 | Ridurre lunghezza prompt NeedsMetricAgent | `needs_metric_agent.py` | ⬜ |
| 3.2 | Aggiungere few-shot examples a SQLAgent | `sql_agent.py` | ⬜ |
| 3.3 | Documentare architettura in README | `agents/README.md` | ⬜ |

---

## 📊 Appendice: Configurazione Colonne Consigliata

### File: `app/core/constants.py` (da creare/aggiornare)

```python
"""Costanti condivise per la selezione colonne e legende punteggi."""

# =============================================================================
# LEGENDA PUNTEGGI (da includere nei prompt degli agenti)
# =============================================================================

SCORE_LEGEND = """
### LEGENDA PUNTEGGI (Scala 1-5, dove 5 = Ottimo)

**APE (Efficienza Energetica):**
- `ape_score_classe`: Classe energetica certificata (5=A1-A4, 3=B-E, 1=F-G)
- `ape_score_impianto`: Qualità impianto termico (5=Pompa di calore, 3=Condensazione, 1=Caldaia tradizionale)
- `ape_score_involucro`: Isolamento termico edificio (5=Cappotto, 3=Parziale, 1=Assente)
- `ape_score_rinnovabili`: Fonti energia rinnovabile (5=Presenti e certificate, 1=Assenti)
- `ape_score_total`: Media ponderata dei 4 punteggi APE

**POI (Servizi di Prossimità - raggio 1km):**
- `sanita`: Ospedali, farmacie, ambulatori, pronto soccorso
- `mobilita`: Fermate metro/bus, stazioni ferroviarie, parcheggi
- `verde`: Parchi pubblici, giardini, aree naturali protette
- `sport`: Palestre, piscine, campi sportivi, centri fitness
- `commerciale`: Supermercati, negozi, centri commerciali, mercati
- `educazione`: Scuole (ogni ordine), università, biblioteche
"""

# =============================================================================
# SELEZIONE COLONNE PER AGENTE
# =============================================================================

# Colonne per SQL Agent (schema da passare)
SQL_FILTERABLE_COLUMNS = [
    "id",
    "codice_comune",
    "superficie_di_riferimento_mq",
    "latitudine",
    "longitudine",
    "natura_del_bene",
    "tipologia_bene_immobile",
    "epoca_costruzione",
    "vincolo_culturale_paesaggistico",
    "natura_giuridica_del_bene",
    "utilizzo_del_bene",
    "finalita",
    "zona_omi",
]

# Colonne per RANKING (non filtrare via SQL!)
RANKING_ONLY_COLUMNS = [
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
    "sanita",
    "mobilita",
    "verde",
    "sport",
    "commerciale",
    "educazione",
]

# Colonne per Evaluation Agent (invio all'LLM)
EVAL_COLUMNS = [
    "id",
    "indirizzo",
    "numero_civico",
    "zona_omi",
    "superficie_di_riferimento_mq",
    "tipologia_bene_immobile",
    "epoca_costruzione",
    "utilizzo_del_bene",
    "finalita",
    # APE
    "classe_energetica_ape",
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
    # POI
    "sanita",
    "mobilita",
    "verde",
    "sport",
    "commerciale",
    "educazione",
    # Calcolati
    "tempo_minuti",
    "distanza_km",
]

# Colonne APE per APE Agent
APE_AGENT_COLUMNS = [
    "classe_energetica_ape",
    "epglnren_ape",
    "classe_target_ape",
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
]
```

---

## 🗂️ Metadata Distribution per Agente

### File Metadata: `backend/app/data/db_metadata.json`

Il file `db_metadata.json` contiene **tutte le informazioni necessarie** per gli agenti LLM:
- Valori categorici per ogni colonna (es. tipologie, epoche, vincoli)
- Statistiche numeriche (min, max, mean, median)
- **Score Legends** (significato dei punteggi 1-5)
- **SQL Filtering Rules** (quali colonne filtrare vs ranking)

### Matrice di Distribuzione Metadata

| Agente | Riceve Metadata? | Cosa Dovrebbe Ricevere | Stato | Azione |
|--------|------------------|------------------------|-------|--------|
| **SQLAgent** | ✅ Sì | Schema + valori categorici + sql_filtering_rules | ✅ OK | Aggiungere filtering_rules |
| **NeedsMetricAgent** | ✅ Sì | Schema completo + note | ✅ OK | - |
| **TypologyAgent** | ⚠️ Parziale | Solo `available_typologies` (hardcoded) | ⚠️ Parziale | Leggere da metadata |
| **LocationAgent** | ❌ No | Non necessita di metadata dataset | ✅ OK | - |
| **ApeAgent** | ❌ No | `score_legends.ape_scores` + statistiche APE | ❌ CRITICO | **Da implementare** |
| **PoiAgent** | ❌ No | `score_legends.poi_scores` | ⚠️ Nice-to-have | Aggiungere legenda |
| **EvaluationAgent** | ❌ No | `score_legends` (ape + poi) | ❌ CRITICO | **Da implementare** |
| **MapAssistantAgent** | ❌ No | Non necessita di metadata | ✅ OK | - |

### Implementazione Consigliata

#### 1. Caricare Metadata una volta sola (in `graph_agent.py`)

```python
# graph_agent.py - __init__
from app.data import get_db_metadata

class GraphOrchestratorAgent:
    def __init__(self):
        self.db_metadata = get_db_metadata()  # Carica all'init
        self.score_legends = self.db_metadata.get("score_legends", {})
        # ...
```

#### 2. Passare ai singoli agenti

```python
# Per APE Agent
def run_ape():
    return self.ape_agent.run(
        query=query,
        ape_statistics=self.db_metadata.get("ape_score_classe", {}),  # Stats
        score_legend=self.score_legends.get("ape_scores", {})         # Legend
    )

# Per Evaluation Agent
def run_evaluation():
    return self.eval_agent.run(
        use_case=use_case,
        data=estates_data,
        query=query,
        score_legends=self.score_legends  # Sia APE che POI
    )

# Per Typology Agent
def run_typology():
    typologies = self.db_metadata.get("tipologia_bene_immobile", {}).get("values", [])
    return self.typology_agent.run(query, typologies)
```

#### 3. Aggiornare i Prompt degli Agenti

Ogni agente che riceve `score_legends` deve includerle nel prompt:

```python
# In ape_agent.py
prompt = f"""
...
## LEGENDA PUNTEGGI APE
{json.dumps(score_legend, indent=2, ensure_ascii=False)}

## STATISTICHE DATASET
{json.dumps(ape_statistics, indent=2, ensure_ascii=False)}
...
"""
```

### Checklist Implementazione

- [ ] **Task 1:** Aggiungere loader per `score_legends` in `loaders.py`
- [ ] **Task 2:** Modificare `ApeAgent.run()` - accetta `ape_statistics` e `score_legend`
- [ ] **Task 3:** Modificare `EvaluationAgent.run()` - accetta `score_legends`
- [ ] **Task 4:** Modificare `TypologyAgent.run()` - legge tipologie da metadata
- [ ] **Task 5:** Aggiornare `graph_agent.py` - passa metadata ai sotto-agenti
- [ ] **Task 6:** Test end-to-end con query che richiede interpretazione punteggi

---

*Documento generato automaticamente durante la sessione di audit.*  
*Ultimo aggiornamento: Gennaio 2025*

