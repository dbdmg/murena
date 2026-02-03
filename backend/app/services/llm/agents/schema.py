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


class CategoryResponse(BaseModel):
    categories: List[str] = Field(default_factory=list, description="Lista delle categorie selezionate")


class AmenityResponse(BaseModel):
    amenities: Dict[str, List[str]] = Field(default_factory=dict, description="Amenity selezionate per categoria")


class NormativeResponse(BaseModel):
    requisiti: List[Dict[str, Any]] = Field(default_factory=list, description="Requisiti normativi estratti")


class TypologyResponse(BaseModel):
    typologies: List[str] = Field(default_factory=list, description="Tipologie selezionate")


class LocationResponse(BaseModel):
    places: List[Place] = Field(default_factory=list, description="Luoghi identificati")


class ConsistencyResponse(BaseModel):
    requirements: List[str] = Field(default_factory=list, description="Requisiti consolidati")


class EvaluationResult(BaseModel):
    id: int = Field(..., description="ID dell'immobile")
    evaluation_text: str = Field(..., description="Testo della valutazione")
    score: int = Field(..., description="Punteggio di rilevanza (0-100)")
    pros: List[str] = Field(default_factory=list, description="Punti di forza")
    cons: List[str] = Field(default_factory=list, description="Punti di debolezza")


class EvaluationList(BaseModel):
    evaluations: List[EvaluationResult] = Field(default_factory=list)


class MetricDefinition(BaseModel):
    name: str
    goal: str = ""
    weight: float = 0.5
    data_points: List[str] = Field(default_factory=list)


class DatasetStrategy(BaseModel):
    filters: List[str] = Field(default_factory=list)
    sort_by: Optional[str] = None
    notes: Optional[str] = None
    top_k: Optional[int] = None


class ApeUsagePlan(BaseModel):
    use_ape: bool = False
    strategy: str = ""


class AgentResult(BaseModel):
    """Risultato standard di un agente.
    
    - prompt: Metadati sul prompt inviato
    - raw_text: Risposta testuale del modello
    - sources: Fonti opzionali (es. URL, documenti)
    """
    prompt: Optional[PromptRecord] = Field(None)
    raw_text: str = Field(..., description="Risposta grezza del modello")
    sources: Optional[List[str]] = Field(default_factory=list, description="Fonti o riferimenti")


class NeedsMetricPlan(AgentResult):
    summary: str = ""
    metrics: List[MetricDefinition] = Field(default_factory=list)
    dataset_strategy: DatasetStrategy = Field(default_factory=DatasetStrategy)
    ape_strategy: ApeUsagePlan = Field(default_factory=ApeUsagePlan)

# Alias o classi specifiche che ora seguono lo stesso schema per retrocompatibilità di tipo
class LocationAgentResult(AgentResult): pass
class TypologyAgentResult(AgentResult): pass
class SQLAgentResult(AgentResult): pass
class EvaluationAgentResponse(AgentResult): pass
class ApeAgentResult(AgentResult): pass
class NormativeAgentResult(AgentResult): pass
class ConsistencyAgentResult(AgentResult): pass
class PoiCategoryAgentResult(AgentResult): pass
class PoiAmenityAgentResult(AgentResult): pass


class AgentContext(BaseModel):
    user_query: str = Field(..., description="Query originale dell'utente")
    locations: List[Place] = Field(
        default_factory=list, description="Luoghi identificati"
    )
    typology_result: Optional[TypologyAgentResult] = Field(
        None, description="Risultato del TypologyAgent"
    )
    metrics_plan: Optional[Any] = Field(
        None, description="Piano generato dal NeedsMetricAgent (deprecato/legacy)"
    )
    normative_result: Optional[NormativeAgentResult] = Field(
        None, description="Risultato del NormativeAgent per requisiti normativi"
    )
    poi_category_result: Optional[PoiCategoryAgentResult] = Field(
        None, description="Risultato del PoiCategoryAgent per categorie POI"
    )
    poi_amenity_result: Optional[PoiAmenityAgentResult] = Field(
        None, description="Risultato del PoiAmenityAgent per amenities POI"
    )
    filtered_dataset_preview: List[dict] = Field(
        default_factory=list, description="Anteprima del dataset filtrato"
    )
    evaluation_results: List[Any] = Field(
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


class MapAssistantResponse(AgentResult):
    action: Optional[ChatAction] = Field(
        None, description="Azione da eseguire sulla UI"
    )

