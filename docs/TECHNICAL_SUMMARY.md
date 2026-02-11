# Technical Summary — Real Estate AI: Multi-Agent LLM System for Public Real Estate Valorization

> **Purpose of this document.** This artifact provides a self-contained, highly technical description of the system architecture, algorithms, and design rationale. It is intended as context for an LLM tasked with drafting or refining sections of an academic paper (e.g., IEEE, ACM, or similar venues). Language is formal, terminology is precise, and implementation details are included where they illuminate design decisions.

---

## 1. Core Architecture

### 1.1 System Topology

The system adopts a **three-tier client–server architecture** with a clear separation of concerns:

| Tier | Technology | Role |
|---|---|---|
| **Presentation** | React 18 + TypeScript, Vite, Tailwind CSS, React Leaflet | Interactive SPA with map-based visualization, real-time progress via WebSocket |
| **Application** | Python 3.11, FastAPI, LangChain, LangGraph | RESTful API, multi-agent LLM orchestration, asynchronous task execution |
| **Persistence** | PostgreSQL (via SQLAlchemy + Alembic), Redis, DuckDB (ephemeral) | Relational storage for users/runs, caching layer, in-memory analytical SQL engine |

Communication between Presentation and Application layers occurs over HTTP/REST (JSON payloads) and WebSocket (real-time streaming of analysis progress). The Application tier is stateless with respect to HTTP but maintains in-memory dataset caches and Redis-backed session state.

### 1.2 Backend Module Decomposition

The FastAPI backend (`backend/app/`) is organized into the following principal packages:

```
app/
├── api/v1/endpoints/    # REST controllers: analysis, buildings, auth, map, ape, layers, prompts, feedback, websockets
├── core/                # Configuration (Pydantic Settings), constants, security (JWT + bcrypt)
├── data/                # Data loaders (CSV/Parquet/GeoJSON) and processors (population, POI distances, APE XML parsing)
├── database/            # SQLAlchemy engine, session factory, Alembic migrations
├── models/              # SQLAlchemy ORM models (User, AnalysisRun) and Pydantic request/response schemas
├── repositories/        # Data-access layer (RunRepository, UserRepository)
├── services/
│   ├── analysis/        # SQL execution (DuckDB), ranking score computation
│   ├── llm/
│   │   ├── agents/      # Multi-agent system (10 specialized agents + orchestrator)
│   │   ├── langchain_client.py   # LLM provider abstraction (Gemini / OpenAI)
│   │   ├── prompt_loader.py      # Externalized prompt management from Markdown config
│   │   └── prompt_config.md      # All agent prompts (system + user templates)
│   ├── analysis_service.py       # High-level async orchestration wrapper
│   ├── agent_logger.py           # Structured agent execution logging + HTML report generation
│   ├── energy_score_calculator.py # Percentile-based energy efficiency scoring
│   └── progress_manager.py       # WebSocket progress broadcast
└── utils/               # Decorators (retry, error handling, LLM usage logging), JSON parsing/sanitization, helpers
```

### 1.3 Multi-Agent Orchestration via LangGraph

The intellectual core of the system is the `GraphOrchestratorAgent`, which employs **LangGraph** (a stateful, graph-based workflow engine built atop LangChain) to coordinate a pipeline of specialized LLM agents. The orchestrator is implemented as a **directed acyclic graph (DAG) with conditional edges**, compiled into an executable workflow at initialization time.

**Graph topology (nodes → edges):**

```
analyze_request → generate_sql → execute_sql ─┬─→ enrich_results → calculate_ranking_weights → rank_results → evaluate_results → broker_review → finalize_results → END
                                               │
                       ┌───────────────────────┤
                       │                       │
                  handle_retry ←── (retry)     ├── (retry_relax)
                       │                       │
                       └──→ generate_sql       └── fallback_results → enrich_results
```

The conditional edge from `execute_sql` routes to one of four outcomes:
- **`continue`**: sufficient results obtained; proceed to enrichment.
- **`retry`**: SQL execution error; re-enter the generation loop with error context.
- **`retry_relax`**: valid SQL but insufficient result cardinality; trigger relaxation strategies.
- **`fallback`**: maximum retries exhausted; proceed with best-effort results.

**State management.** The graph operates on a `GraphState` TypedDict that carries all intermediate artifacts (query, agent results, DataFrames, SQL history, progress callbacks) through the pipeline. A recursion limit of 30 prevents infinite retry loops.

### 1.4 Agent Inventory

The system comprises **10 specialized agents**, each inheriting from `BaseAgent` and implementing a `run()` method. Agents operate in one or both of two modes:

| Agent | Filtering Mode | Ranking Mode | LLM-Backed | Description |
|---|:---:|:---:|:---:|---|
| `RankingAgent` | ✓ (priority ordering) | — | ✓ | Determines which agents to activate and their execution priority based on query semantics |
| `LocationAgent` | ✓ (geocoding) | ✓ (distance scoring) | ✓ + Nominatim API | Extracts geographic references; computes Haversine/routing-based distance scores |
| `TypologyAgent` | ✓ (typology matching) | ✓ (rank-based scoring) | ✓ | Identifies and ranks relevant building typologies |
| `ApeAgent` | ✓ (energy filters) | ✓ (deterministic scoring) | ✓ | Extracts energy performance requirements; computes APE-based scores (0–100) |
| `NormativeAgent` | ✓ (regulatory extraction) | ✓ (compliance scoring) | ✓ | Extracts surface/zoning requirements from normative documents |
| `PoiAgent` | ✓ (POI requirements) | ✓ (proximity scoring) | ✓ | Identifies required Points of Interest categories with quality thresholds |
| `SQLAgent` | ✓ (query generation) | — | ✓ | Translates structured requirements into DuckDB-compatible SQL |
| `RelaxationAgent` | ✓ (WHERE relaxation) | — | ✓ | Proposes progressive relaxation strategies for over-constrained queries |
| `EvaluationAgent` | — | ✓ (qualitative assessment) | ✓ | Generates per-property qualitative evaluations (pros, cons, narrative) |
| `BrokerAgent` | — | ✓ (executive summary) | ✓ | Produces comparative executive summary for top candidates |

### 1.5 LLM Provider Abstraction

The `langchain_client.py` module implements a **provider-agnostic LLM factory** (`get_llm()`) that dynamically selects between Google Gemini (`ChatGoogleGenerativeAI`) and OpenAI (`ChatOpenAI`) based on model name prefix:
- Models prefixed with `gpt-` or `o1-` → OpenAI endpoint.
- All other models → Google Gemini endpoint.

Instances are cached via `@lru_cache(maxsize=8)` to avoid redundant initialization. Temperature defaults to `0.0` (deterministic output) but is configurable per-agent via `AGENT_MODELS` settings. Optional **Langfuse** integration provides production observability (tracing, cost tracking).

### 1.6 Prompt Engineering Infrastructure

All agent prompts are externalized in a single **Markdown configuration file** (`prompt_config.md`), parsed at startup by `prompt_loader.py`. This design enables:
- **Runtime prompt editing** without code changes (via API endpoint `/api/v1/prompts`).
- **Cache invalidation** via `reload_prompt_cache()` for hot-reloading.
- **Structured sections**: each agent has `system` and `user` template blocks with placeholder variables (e.g., `{query}`, `{statistics}`, `{format_instructions}`).

Prompts are written in Italian (domain-specific language for the MEF—Ministero dell'Economia e delle Finanze), reflecting the operational deployment context.

---

## 2. Key Functionalities

### 2.1 Natural Language to SQL Pipeline

The system transforms a free-form natural language query into a structured SQL query through a multi-stage pipeline:

1. **Semantic Decomposition**: The `RankingAgent` parses the query to determine which analytical dimensions are relevant (location, typology, energy, normative compliance, POI proximity) and establishes their execution priority.

2. **Parallel Agent Execution**: Activated agents run concurrently via `ThreadPoolExecutor`, each extracting domain-specific requirements:
   - `LocationAgent`: geographic coordinates and search radii.
   - `TypologyAgent`: ordered list of relevant building typologies.
   - `ApeAgent`: energy performance filter conditions (column, operator, value).
   - `NormativeAgent`: surface area and zoning constraints from regulatory documents.
   - `PoiAgent`: POI category thresholds.

3. **Requirement Aggregation**: All extracted requirements are serialized into a structured prompt including the database schema and metadata (column names, value distributions, statistical summaries).

4. **SQL Generation**: The `SQLAgent` synthesizes a single `SELECT * FROM IMMOBILI WHERE ... ORDER BY ...` query. WHERE clause conditions are ordered by relevance (user-explicit constraints first, agent-derived constraints second) to facilitate progressive relaxation.

5. **Execution & Validation**: The query is executed against DuckDB (in-memory analytical engine) with a custom `haversine_km` UDF registered for geospatial filtering. Results are validated against a minimum cardinality threshold.

### 2.2 Adaptive Query Relaxation

When a generated SQL query returns insufficient results, the system employs a **dual-strategy relaxation mechanism**:

#### 2.2.1 AST-Based Deterministic Relaxation
The `_apply_ast_relaxation_workflow` method uses **`sqlglot`** to parse the SQL query into an Abstract Syntax Tree. It then sequentially removes WHERE clause conditions (from least relevant to most relevant, per the ordering established by the SQL agent), re-executing the query after each removal. This approach is:
- **Deterministic**: no LLM calls required.
- **Transparent**: each relaxation step is logged with its result cardinality.
- **Efficient**: terminates as soon as the minimum threshold is met.

#### 2.2.2 LLM-Guided Semantic Relaxation
As a complementary strategy, the `RelaxationAgent` receives the current WHERE conditions along with column statistics (distributions, percentiles, value frequencies) and proposes semantically informed relaxation strategies:
- **Continuous columns**: interval widening proportional to distribution spread.
- **Categorical columns**: inclusion of statistically proximate values.
- Each proposal includes a severity level (`low`, `medium`, `high`) and a ready-to-use SQL fragment.

### 2.3 Multi-Dimensional Ranking

After SQL execution, results are enriched with per-agent scores computed deterministically:

| Dimension | Scoring Algorithm |
|---|---|
| **Location** | Exponential decay: `100 × exp(-(d/2.5)³)` where `d` = Haversine distance in km |
| **Typology** | Inverse rank position: `100 / rank_position` from the ordered typology list |
| **APE (Energy)** | Min-max normalization across APE-relevant columns; composite weighted average |
| **Normative** | Min-max normalization of compliance-relevant columns; weighted aggregate |
| **POI** | Pre-computed amenity scores from aggregated Parquet file; weighted by category relevance |

The `RankingAgent` (in ranking mode) determines per-dimension weights. The final `final_ranking_score` is a weighted linear combination:

```
final_score = Σ (agent_score_i × weight_i)  for i ∈ {location, typology, ape, normative, poi}
```

Transparency columns (e.g., `ape_partial_score_X`, `typology_rank_position`, `ranking_weight_location`) are appended to the result DataFrame for full auditability.

### 2.4 Qualitative Evaluation & Broker Synthesis

Top-ranked properties undergo **per-item qualitative evaluation** by the `EvaluationAgent`, which generates:
- A narrative `evaluation_text` contextualizing the property's potential.
- Exactly 3 `pros` and 3 `cons`.
- The pre-computed `final_ranking_score` is passed through unchanged (the agent provides qualitative interpretation, not re-scoring).

The `BrokerAgent` then produces an **executive summary** comparing the top 3 candidates, offering a strategic recommendation with trade-off analysis.

### 2.5 Energy Performance Certificate (APE) Processing

The system includes a sophisticated APE processing pipeline:

1. **XML Parsing** (`parse_ape_xml`): Parses Italian APE XML certificates (830+ lines of domain logic), extracting:
   - Energy class, consumption metrics (kWh/m²/year).
   - HVAC system details via expert-defined lookup tables.
   - Top 5 energy vectors with PCI (Potere Calorifico Inferiore) conversion.
   - Quality indicators and simulated services detection.

2. **Percentile-Based Scoring** (`EnergyScoreCalculator`): Groups buildings by usage type (`destinazione_uso_cod`), computes consumption percentiles, and assigns 0–100 scores where higher values indicate greater efficiency.

3. **Composite APE Score** (`calculate_ape_score`): Multi-criteria scoring across energy class, system quality, building envelope, and renewable energy adoption, each on a 1–5 scale.

### 2.6 Real-Time Progress Streaming

Analysis progress is streamed to the frontend via **WebSocket** (`/ws/analysis/{run_id}`). The `ProgressManager` implements an async pub-sub pattern:
- The orchestrator emits progress updates at each graph node transition.
- Each update includes: percentage, current step label, and an array of step states (`done`/`current`/`pending`).
- A terminal `complete` message signals the client to fetch full results.

### 2.7 Geospatial Analysis

- **Geocoding**: The `LocationAgent` calls the Nominatim API (with local file-based caching) to resolve place names to coordinates.
- **Distance Computation**: `calculate_travel_times_df` supports both Haversine (great-circle) distance and OSM/Pandana-based real road network routing.
- **Map Visualization**: The frontend uses React Leaflet with marker clustering, GeoJSON overlays (OMI zones), and dynamic population data visualization.

### 2.8 Observability & Logging

- **Agent Trace**: Every agent execution is recorded in a structured `agent_trace` list within the graph state, capturing: agent name, mode, timestamp, execution time, input (prompt or column names), and output (structured results or formulas).
- **AgentLogger**: A 1,200+ line module that serializes traces into JSONL files and generates interactive HTML reports with tabular and tabbed views.
- **Langfuse Integration**: Optional distributed tracing for production monitoring of LLM calls (latency, token usage, cost attribution).
- **LLM Usage Logging**: The `@log_llm_usage` decorator captures per-call metadata (model, duration, context snippet) to daily log files.

---

## 3. Data Flow

### 3.1 End-to-End Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY (Natural Language)                          │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  1. RANKING AGENT (Sequential)                                                      │
│     Input:  User query                                                              │
│     Output: Ordered list of active agents + priority weights                        │
│     Decision: Which analytical dimensions are relevant?                              │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  2. DOMAIN AGENTS (Parallel via ThreadPoolExecutor)                                 │
│     ┌──────────────┐ ┌───────────────┐ ┌────────────┐ ┌──────────────┐ ┌─────────┐ │
│     │ LocationAgent│ │TypologyAgent  │ │  ApeAgent  │ │NormativeAgent│ │PoiAgent │ │
│     │  (geocoding) │ │(type matching)│ │(energy req)│ │ (regulation) │ │(poi req)│ │
│     └──────┬───────┘ └──────┬────────┘ └─────┬──────┘ └──────┬───────┘ └────┬────┘ │
│            │                │                │               │              │       │
│            ▼                ▼                ▼               ▼              ▼       │
│     ┌──────────────────────────────────────────────────────────────────────────────┐ │
│     │               AGGREGATED REQUIREMENTS (structured JSON)                     │ │
│     └──────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  3. SQL AGENT                                                                       │
│     Input:  User query + aggregated requirements + DB schema + metadata              │
│     Output: DuckDB-compatible SQL query (SELECT * FROM IMMOBILI WHERE ...)           │
│     Constraint: WHERE clause ordered by relevance for progressive relaxation         │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  4. SQL EXECUTION (DuckDB in-memory)                                                │
│     - Custom UDF: haversine_km() for geospatial filtering                           │
│     - Native Parquet loading with APE data LEFT JOIN                                 │
│     - Syntax pre-validation via EXPLAIN                                             │
│     ┌──────────────────────────────┐                                                │
│     │ Result cardinality < threshold? ──→ YES ──→ AST Relaxation / LLM Relaxation   │
│     │                              │              (retry loop, max ~10 attempts)     │
│     │                              ──→ NO  ──→ Continue                              │
│     └──────────────────────────────┘                                                │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  5. ENRICHMENT & RANKING (Deterministic)                                            │
│     - Travel time computation (Haversine / road network)                            │
│     - Per-agent scoring in ranking mode (location_score, typology_score, etc.)       │
│     - Weighted linear combination → final_ranking_score                             │
│     - Transparency columns appended for auditability                                │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  6. QUALITATIVE EVALUATION (LLM)                                                    │
│     - EvaluationAgent: per-property narrative (pros, cons, commentary)               │
│     - BrokerAgent: comparative executive summary of top candidates                   │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  7. OUTPUT                                                                          │
│     - Ranked DataFrame with scores + evaluations                                    │
│     - Location payload for map rendering                                            │
│     - Gemini responses dict (full agent trace for frontend inspection)               │
│     - Broker summary string                                                         │
│     - Persisted to PostgreSQL (AnalysisRun model)                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Sources and Preprocessing

| Source | Format | Processing |
|---|---|---|
| Real estate inventory | Parquet (primary) / CSV (fallback) | `load_and_merge_data()`: loads, merges with APE scores, caches in-memory |
| APE certificates | XML (Italian standard) | `parse_ape_xml()`: 360+ line expert parser with namespace-aware XPath |
| APE detailed data | Parquet | LEFT JOIN on building ID; composite scoring via `calculate_ape_score()` |
| GeoJSON zones | GeoJSON | OMI (Osservatorio del Mercato Immobiliare) zone overlays for map |
| Population data | CSV | Merged with GeoJSON zones by zone code for demographic analysis |
| Metro stations | CSV | Static reference file for transit proximity |
| Normative documents | Text files (directory-based) | Loaded by `NormativeAgent` from configurable document directory |
| Amenity scores | Parquet (pre-computed) | Pre-aggregated POI proximity scores per building per category |
| Database metadata | JSON (`db_metadata_lite.json`) | Column descriptions, value distributions, categorical enumerations |

### 3.3 Caching Strategy

The system employs a multi-level caching architecture:

1. **Application-level dataset cache** (`RealEstateService._dataset_cache`): in-memory dict keyed by dataset identifier; populated at startup via the FastAPI lifespan manager.
2. **Redis cache**: session-level caching for authenticated user data and analysis state.
3. **LLM instance cache**: `@lru_cache(maxsize=8)` on `get_llm()` prevents redundant model client instantiation.
4. **Prompt cache**: `@lru_cache(maxsize=1)` on prompt file parsing; invalidated on update.
5. **Geocoding cache**: file-based JSON cache for Nominatim API responses.
6. **Amenity scores cache**: global singleton DataFrame loaded once from Parquet.

---

## 4. Innovation Points

### 4.1 Dynamic Agent Activation via Meta-Reasoning

Unlike static pipelines, the `RankingAgent` performs **meta-reasoning** over the user query to determine which analytical agents are relevant. This selective activation:
- **Reduces latency** by avoiding unnecessary LLM calls (e.g., skipping `ApeAgent` when no energy requirements are mentioned).
- **Improves precision** by preventing irrelevant agents from injecting noise into the SQL WHERE clause.
- **Establishes execution priority**, which propagates to WHERE clause ordering and weight assignment.

### 4.2 Hybrid Relaxation: AST Manipulation + LLM Semantics

The dual relaxation strategy combines:
- **Syntactic (AST-based)**: deterministic, zero-cost, transparent removal of WHERE conditions using `sqlglot` parse trees. Conditions are removed in reverse-relevance order, exploiting the ordering invariant established during SQL generation.
- **Semantic (LLM-based)**: context-aware relaxation proposals that consider column statistics and semantic relationships (e.g., expanding a categorical filter to include adjacent categories).

This hybrid approach balances efficiency (AST relaxation requires no LLM calls) with intelligence (LLM relaxation can propose non-obvious modifications like widening a numeric range based on distribution percentiles).

### 4.3 Separation of Filtering and Ranking Modes

Each domain agent operates in two distinct modes with different computational characteristics:
- **Filtering mode** (LLM-backed): extracts structured requirements from the query, contributing to SQL WHERE clause generation. This is inherently non-deterministic (LLM output).
- **Ranking mode** (deterministic): computes a 0–100 score for each property using mathematical formulas (min-max normalization, inverse ranking, exponential decay). No LLM calls are needed.

This separation ensures that the ranking phase is **reproducible** and **auditable**, while leveraging LLM capabilities only where semantic understanding is required (requirement extraction).

### 4.4 Structured Output Enforcement via Pydantic

All LLM outputs are parsed into **Pydantic models** (`schema.py`), enforcing type safety and structural constraints. This includes:
- `LocationResponse`, `TypologyResponse`, `ApeResponse`, `NormativeResponse`: filtering-mode outputs.
- `EvaluationResult`, `EvaluationList`: qualitative assessment outputs.
- `RelaxationProposal`: relaxation strategy outputs.
- `RankingWeights`, `RankingRanking`: meta-reasoning outputs.

When LLM output fails Pydantic validation, the system falls back to `json_repair` and `ast.literal_eval` for recovery, with structured error logging.

### 4.5 Externalized Prompt Configuration

All agent prompts reside in a single Markdown file (`prompt_config.md`), parsed using a custom section-aware parser. This enables:
- **Non-developer prompt iteration**: domain experts can modify agent behavior without touching Python code.
- **API-driven prompt updates**: the `/api/v1/prompts` endpoint supports runtime modification with cache invalidation.
- **Versioning**: the Markdown file is under version control, enabling diff-based prompt evolution tracking.

### 4.6 Transparent Scoring with Formula Tracing

The `_log_execution` method in the orchestrator generates **per-property formula traces**, exposing the exact mathematical computation behind each score. For example:
```json
{
  "id": "IMM001",
  "score": 78.4,
  "formula": [
    "Sum(",
    "  superficie(2500) [Min 100, Max 5000]: 49.0 * Weight(0.600),",
    "  classe_energetica_ape(B)[Rank 5/10]: 55.6 * Weight(0.400)",
    ")"
  ]
}
```
This level of transparency is critical for regulatory contexts (public administration decision support) and enables human auditing of algorithmic outputs.

### 4.7 DuckDB as Ephemeral Analytical Engine

Rather than executing analytical queries against PostgreSQL, the system uses **DuckDB in-memory instances** for each analysis run. This provides:
- **Native Parquet support**: direct file-to-query without ETL overhead.
- **Custom UDF registration**: `haversine_km()` for inline geospatial computation.
- **SQL dialect compatibility**: generated queries leverage DuckDB's analytical extensions.
- **Isolation**: each analysis operates on a disposable in-memory database, preventing cross-query state contamination.

### 4.8 Synthetic Evaluation Framework

The `tests/synthetic_eval/` directory contains an automated benchmarking harness that:
- Runs parameterized queries against the real dataset.
- Records full agent traces via `AgentLogger`.
- Generates HTML visualization reports for comparative analysis.
- Enables systematic prompt engineering evaluation across query variants.

---

## 5. Dependency Tree

### 5.1 Core Framework

| Package | Version Constraint | Role |
|---|---|---|
| `fastapi` | ≥ 0.100 | ASGI web framework; route definitions, dependency injection, WebSocket support |
| `uvicorn[standard]` | ≥ 0.23 | ASGI server with HTTP/1.1 and WebSocket support |
| `pydantic` / `pydantic-settings` | v2 | Data validation, settings management, structured LLM output parsing |

### 5.2 Database & Persistence

| Package | Role |
|---|---|
| `sqlalchemy` | ORM and database abstraction (declarative models, session management) |
| `asyncpg` | Asynchronous PostgreSQL driver |
| `alembic` | Schema migration management |
| `redis` / `aioredis` | In-memory caching and session storage |
| `duckdb` | Ephemeral in-memory analytical SQL engine for per-analysis query execution |

### 5.3 LLM & AI

| Package | Role |
|---|---|
| `langchain` | Core abstraction for LLM chains, prompts, and output parsing |
| `langchain-core` | Base interfaces (ChatPromptTemplate, BaseMessage, OutputParser) |
| `langchain-community` | Community integrations (fallback chat models) |
| `langchain-google-genai` | Google Gemini model integration via LangChain |
| `langchain-openai` | OpenAI GPT model integration via LangChain |
| `langgraph` | Stateful graph-based workflow orchestration for multi-agent pipelines |
| `openai` | Direct OpenAI API client (used alongside LangChain) |
| `google-genai` / `google-generativeai` | Direct Google Generative AI client |
| `langfuse` | Production observability: distributed tracing, cost tracking, prompt versioning |

### 5.4 Data Processing

| Package | Role |
|---|---|
| `pandas` | Primary DataFrame library for tabular data manipulation |
| `numpy` | Numerical computation (Haversine formula, array operations) |
| `pyarrow` | Parquet file I/O, columnar data format support |
| `geopandas` | Geospatial DataFrame operations |
| `openpyxl` | Excel file I/O (reporting) |

### 5.5 SQL Processing

| Package | Role |
|---|---|
| `sqlglot` | SQL parsing, AST manipulation, transpilation, and pretty-printing; used for deterministic query relaxation |
| `sqlparse` | SQL tokenization and formatting (legacy, used in orchestrator) |

### 5.6 Utilities

| Package | Role |
|---|---|
| `python-dotenv` | Environment variable loading from `.env` files |
| `tenacity` | Advanced retry logic with configurable backoff strategies |
| `loguru` | Structured logging with rich formatting |
| `httpx` | Async HTTP client (external API calls) |
| `json_repair` | Recovery of malformed JSON from LLM outputs |
| `tabulate` | Table formatting for logging and debug output |
| `chardet` | Character encoding detection for XML file parsing |

### 5.7 Security

| Package | Role |
|---|---|
| `python-jose[cryptography]` | JWT token creation and validation |
| `passlib[bcrypt]` | Password hashing with bcrypt |

### 5.8 Frontend

| Package | Role |
|---|---|
| `react` (18.x) + `react-dom` | UI component framework |
| `typescript` | Static type checking |
| `vite` | Build tool and development server |
| `tailwindcss` | Utility-first CSS framework |
| `react-leaflet` + `leaflet` | Interactive map rendering |
| `leaflet.markercluster` | Marker clustering for dense geospatial data |
| `react-router-dom` | Client-side routing |
| `axios` | HTTP client for API communication |
| `lucide-react` | Icon library |
| `recharts` | Data visualization charts |

### 5.9 Development & Testing

| Package | Role |
|---|---|
| `pytest` + `pytest-asyncio` | Test framework with async support |
| `black` | Code formatting |
| `ruff` | Fast Python linter |
| `pre-commit` | Git hook management |

---

## 6. Appendix: Key Design Decisions

### 6.1 Why LangGraph over LangChain Agents?

LangGraph was chosen over LangChain's built-in agent framework (e.g., `AgentExecutor`) for several reasons:
- **Explicit control flow**: the graph topology is defined declaratively, making the pipeline structure visible and debuggable.
- **Typed state**: `GraphState` enforces structural contracts between nodes.
- **Conditional routing**: retry and relaxation logic is expressed as graph edges rather than imperative control flow.
- **Deterministic replay**: given the same initial state, the graph produces identical node traversals (modulo LLM non-determinism).

### 6.2 Why DuckDB rather than PostgreSQL for Analytical Queries?

- **Zero setup**: no need to load analysis data into PostgreSQL; DuckDB reads Parquet files directly.
- **Performance**: DuckDB's columnar vectorized engine is optimized for analytical workloads.
- **Isolation**: each analysis creates an ephemeral database, preventing schema conflicts.
- **UDF support**: custom functions (`haversine_km`) integrate seamlessly.

### 6.3 Why Separate Filtering and Ranking Modes?

- **Reproducibility**: ranking scores are deterministic, enabling consistent comparison across runs.
- **Cost efficiency**: ranking mode avoids LLM calls, reducing API costs and latency.
- **Auditability**: mathematical formulas can be inspected and verified by human reviewers.
- **Modularity**: filtering and ranking logic can evolve independently.

### 6.4 Italian-Language Prompts

All prompts are written in Italian to match the operational context (Italian public administration—MEF). This decision reflects the domain-specific vocabulary (e.g., "Attestato di Prestazione Energetica", "tipologia_bene_immobile", "destinazione d'uso") that would lose precision in translation.

---

*Document generated for academic reference. System version: 1.0.0. Last updated: February 2026.*
