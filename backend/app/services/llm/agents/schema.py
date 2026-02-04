from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptRecord(BaseModel):
    """Record dei prompt inviati al modello LLM.

    - system: Istruzioni di sistema che definiscono il ruolo e comportamento dell'agente
    - user: Template/messaggio dell'utente con le variabili sostituite
    - full_text: Concatenazione completa di system + user (per debug)
    """

    system: str = Field(
        default="N/D",
        description="System prompt: istruzioni di ruolo e comportamento per l'agente",
    )
    user: str = Field(
        default="N/D",
        description="User prompt: richiesta specifica con i dati interpolati",
    )
    full_text: Optional[str] = Field(
        None, description="Prompt completo inviato al modello (system + user)"
    )


class Place(BaseModel):
    name: str = Field(..., description="Nome del luogo o POI")
    city: Optional[str] = Field(None, description="Città se disponibile")
    lat: Optional[float] = Field(None, description="Latitudine")
    lon: Optional[float] = Field(None, description="Longitudine")


class LocationAgentResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello (stringa)")
    places: List[Place] = Field(default_factory=list, description="Luoghi estratti")
    prompt: Optional[PromptRecord] = Field(
        None, description="Metadati sul prompt inviato al modello"
    )


class CategoryResponse(BaseModel):
    categories: List[str] = Field(default_factory=list, description="Lista delle categorie selezionate")


class AmenityResponse(BaseModel):
    amenities: Dict[str, List[str]] = Field(default_factory=dict, description="Amenity selezionate per categoria")


class NormativeResponse(BaseModel):
    requisiti: List[Dict[str, Any]] = Field(default_factory=list, description="Requisiti normativi estratti")


class UseCaseResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello")
    description: str = Field(..., description="Descrizione dettagliata dello use case")
    target_audience: str = Field(..., description="Target audience identificata")
    key_metrics: List[str] = Field(
        default_factory=list, description="Metriche chiave da analizzare"
    )
    prompt: Optional[PromptRecord] = Field(
        None, description="Prompt utilizzato per la generazione"
    )


class SQLAgentResult(BaseModel):
    sql_query: str = Field(..., description="Query SQL generata")
    explanation: Optional[str] = Field(None, description="Spiegazione della query")
    raw_text: str = Field(..., description="Risposta grezza ottenuta dal modello")
    prompt: Optional[PromptRecord] = Field(
        None, description="Prompt utilizzato per la generazione"
    )


class EvaluationResult(BaseModel):
    id: int = Field(..., description="ID dell'immobile")
    evaluation_text: str = Field(..., description="Testo della valutazione")
    score: int = Field(..., description="Punteggio di rilevanza (0-100)")
    pros: List[str] = Field(default_factory=list, description="Punti di forza")
    cons: List[str] = Field(default_factory=list, description="Punti di debolezza")


class EvaluationAgentResponse(BaseModel):
    prompt: Optional[PromptRecord] = Field(
        None, description="Prompt utilizzato per la valutazione"
    )
    raw_text: str = Field(..., description="Risposta grezza del modello")
    results: List[EvaluationResult] = Field(
        default_factory=list, description="Valutazioni strutturate"
    )


class MetricDefinition(BaseModel):
    name: str = Field(..., description="Nome della metrica")
    goal: Optional[str] = Field(None, description="Obiettivo della metrica")
    weight: float = Field(default=1.0, description="Peso relativo della metrica")
    data_points: List[str] = Field(
        default_factory=list, description="Colonne o fonti dati rilevanti"
    )


class DatasetStrategy(BaseModel):
    filters: List[str] = Field(
        default_factory=list, description="Filtri o clausole suggerite"
    )
    sort_by: Optional[str] = Field(
        None, description="Campo e direzione di ordinamento consigliati"
    )
    top_k: Optional[int] = Field(
        None, description="Numero ideale di candidati da analizzare"
    )
    notes: Optional[str] = Field(
        None, description="Indicazioni aggiuntive sulla strategia dataset"
    )


class ApeUsagePlan(BaseModel):
    use_ape: bool = Field(default=False, description="Se i dati APE sono necessari")
    strategy: Optional[str] = Field(None, description="Come utilizzare i dati APE")


class TypologyAgentResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello")
    typologies: List[str] = Field(
        default_factory=list, description="Tipologie di immobile identificate"
    )
    prompt: Optional[PromptRecord] = Field(None, description="Prompt utilizzato")


class ApeAgentResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello")
    answer: str = Field(..., description="Risposta elaborata basata sui dati APE")
    relevant_ape_ids: List[str] = Field(
        default_factory=list, description="ID degli APE rilevanti identificati"
    )
    suggested_filters: List[str] = Field(
        default_factory=list, description="Filtri suggeriti basati sui dati APE"
    )
    prompt: Optional[PromptRecord] = Field(None, description="Prompt utilizzato")


class NeedsMetricPlan(BaseModel):
    summary: str = Field(default="", description="Sintesi del bisogno dell'utente")
    raw_text: Optional[str] = Field(
        None, description="Risposta grezza generata dal modello"
    )
    prompt: Optional[PromptRecord] = Field(
        None, description="Prompt utilizzato per la generazione del piano"
    )
    metrics: List[MetricDefinition] = Field(
        default_factory=list, description="Metriche/criteri da applicare"
    )
    dataset_strategy: DatasetStrategy = Field(
        default_factory=DatasetStrategy,
        description="Strategia di filtraggio/ordinamento",
    )
    ape_strategy: ApeUsagePlan = Field(
        default_factory=ApeUsagePlan, description="Piano di utilizzo dei dati APE"
    )


class AgentContext(BaseModel):
    user_query: str = Field(..., description="Query originale dell'utente")
    locations: List[Place] = Field(
        default_factory=list, description="Luoghi identificati"
    )
    typology_result: Optional[TypologyAgentResult] = Field(
        None, description="Risultato del TypologyAgent"
    )
    metrics_plan: Optional[NeedsMetricPlan] = Field(
        None, description="Piano generato dal NeedsMetricAgent"
    )
    normative_result: Optional['NormativeAgentResult'] = Field(
        None, description="Risultato del NormativeAgent per requisiti normativi"
    )
    poi_category_result: Optional['PoiCategoryAgentResult'] = Field(
        None, description="Risultato del PoiCategoryAgent per categorie POI"
    )
    poi_amenity_result: Optional['PoiAmenityAgentResult'] = Field(
        None, description="Risultato del PoiAmenityAgent per amenities POI"
    )
    filtered_dataset_preview: List[dict] = Field(
        default_factory=list, description="Anteprima del dataset filtrato"
    )
    evaluation_results: List[EvaluationResult] = Field(
        default_factory=list, description="Valutazioni prodotte dall'LLM"
    )


class ChatAction(BaseModel):
    action_type: str = Field(
        ..., description="Tipo di azione: 'filter', 'reset', 'rerun', 'none'"
    )
    filter_field: Optional[str] = Field(
        None, description="Campo su cui filtrare (es. 'tipologia', 'classe')"
    )
    filter_value: Optional[str] = Field(
        None, description="Valore del filtro (es. 'Ufficio', 'A4')"
    )
    reasoning: str = Field(
        ..., description="Spiegazione dell'azione o risposta all'utente"
    )


class MapAssistantResponse(BaseModel):
    response_text: str = Field(
        ..., description="Risposta testuale da mostrare all'utente"
    )
    action: Optional[ChatAction] = Field(
        None, description="Azione da eseguire sulla UI"
    )
    prompt: Optional[PromptRecord] = Field(None, description="Prompt utilizzato")

class PoiCategoryAgentResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello")
    category_weights: Dict[str, float] = Field(default_factory=dict, description="Pesi delle categorie POI")
    prompt: Optional[PromptRecord] = Field(None, description="Prompt utilizzato")

class PoiAmenityAgentResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello")
    selected_categories: List[str] = Field(default_factory=list, description="Categorie selezionate come rilevanti")
    selected_amenities: Dict[str, List[str]] = Field(default_factory=dict, description="Amenity selezionate per categoria")
    category_weights: Dict[str, float] = Field(default_factory=dict, description="Pesi delle categorie")
    amenity_weights: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Pesi delle amenity per categoria basati sull'ordine")
    prompt: Optional[PromptRecord] = Field(None, description="Prompt utilizzato")

class NormativeAgentResult(BaseModel):
    raw_text: str = Field(..., description="Risposta grezza del modello")
    normative_info: str = Field(..., description="Informazioni normative estratte sui requisiti strutturali ed energetici")
    constraints: List[str] = Field(default_factory=list, description="Vincoli normativi identificati")
    recommendations: List[str] = Field(default_factory=list, description="Raccomandazioni basate su normative")
    sources: List[str] = Field(default_factory=list, description="URL o fonti consultate")
    prompt: Optional[PromptRecord] = Field(None, description="Prompt utilizzato")
