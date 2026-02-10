from typing import Union
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
    radius_km: float = Field(default=3.0, description="Distanza soglia in km per il filtraggio")



class CategoryResponse(BaseModel):
    categories: List[str] = Field(default_factory=list, description="Lista delle categorie selezionate")
    requisiti: List[Dict[str, Any]] = Field(default_factory=list, description="Lista di requisiti strutturati")


class AmenityResponse(BaseModel):
    amenities: Dict[str, List[str]] = Field(default_factory=dict, description="Amenity selezionate per categoria")


class NormativeResponse(BaseModel):
    requisiti: List[Dict[str, Any]] = Field(default_factory=list, description="Requisiti normativi estratti")
    found: bool = Field(default=False, description="True se sono stati trovati requisiti pertinenti")


class ApeResponse(BaseModel):
    requisiti: List[Dict[str, Any]] = Field(default_factory=list, description="Requisiti energetici estratti")
    found: bool = Field(default=False, description="True se sono stati trovati requisiti pertinenti")



class TypologyResponse(BaseModel):
    typologies: List[str] = Field(default_factory=list, description="Tipologie selezionate")


class LocationResponse(BaseModel):
    places: List[Place] = Field(default_factory=list, description="Luoghi identificati")
    found: bool = Field(default=False, description="True se sono stati trovati riferimenti geografici")





class EvaluationResult(BaseModel):
    id: Union[int, str] = Field(..., description="ID dell'immobile")
    evaluation_text: str = Field(..., description="Testo della valutazione")
    final_ranking_score: int = Field(..., description="Punteggio di rilevanza (0-100) basato sul ranking")
    pros: List[str] = Field(default_factory=list, description="Punti di forza")
    cons: List[str] = Field(default_factory=list, description="Punti di debolezza")


class EvaluationList(BaseModel):
    evaluations: List[EvaluationResult] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Risultato standard di un agente.
    
    - prompt: Metadati sul prompt inviato
    - raw_text: Risposta testuale del modello
    - sources: Fonti opzionali (es. URL, documenti)
    """
    prompt: Optional[PromptRecord] = Field(None)
    raw_text: str = Field(..., description="Risposta grezza del modello")
    sources: Optional[List[str]] = Field(default_factory=list, description="Fonti o riferimenti")




# Alias o classi specifiche che ora seguono lo stesso schema per retrocompatibilità di tipo
class LocationAgentResult(AgentResult): 
    has_locations: bool = False

class TypologyAgentResult(AgentResult): pass
class SQLAgentResult(AgentResult): pass
class EvaluationAgentResponse(AgentResult): pass
class RankingWeights(BaseModel):
    location: float = Field(default=0.2)
    normative: float = Field(default=0.2)
    ape: float = Field(default=0.2)
    typology: float = Field(default=0.2)
    poi: float = Field(default=0.2)

class RankingRanking(BaseModel):
    ranking: List[str] = Field(
        default_factory=lambda: ["location", "typology", "poi", "ape", "normative"],
        description="Lista ordinata degli agenti per importanza"
    )

class RankingAgentResult(AgentResult): 
    weights: RankingWeights = Field(default_factory=RankingWeights)
    ranking: Optional[RankingRanking] = Field(None)

class ApeAgentResult(AgentResult): 
    has_filters: bool = False

class NormativeAgentResult(AgentResult): 
    has_requirements: bool = False

class PoiAgentResult(AgentResult): 
    has_pois: bool = False
    requisiti: List[Dict[str, Any]] = Field(default_factory=list)


class RelaxationProposal(BaseModel):
    condizione_iniziale: str = Field(..., description="Rappresentazione testuale della condizione originale")
    condizione_relaxed: Union[str, List[Dict[str, Any]]] = Field(..., description="Proposta di rilassamento (singola o lista progressiva)")
    strategia: str = Field(..., description="Descrizione della strategia adottata")
    motivazione: str = Field(..., description="Spiegazione del perché il rilassamento è appropriato")
    livello_rilassamento: str = Field(..., description="Livello (low / medium / high)")


class RelaxationAgentResult(AgentResult):
    proposals: List[RelaxationProposal] = Field(default_factory=list)





class AgentContext(BaseModel):
    user_query: str = Field(..., description="Query originale dell'utente")
    locations: List[Place] = Field(
        default_factory=list, description="Luoghi identificati"
    )
    typology_result: Optional[TypologyAgentResult] = Field(
        None, description="Risultato del TypologyAgent"
    )
    # metrics_plan removed
    normative_result: Optional[NormativeAgentResult] = Field(
        None, description="Risultato del NormativeAgent per requisiti normativi"
    )
    poi_result: Optional[PoiAgentResult] = Field(
        None, description="Risultato del PoiAgent per analisi POI"
    )
    ape_result: Optional[ApeAgentResult] = Field(
        None, description="Risultato dell'ApeAgent per analisi energetica"
    )
    ranking_result: Optional[RankingAgentResult] = Field(
        None, description="Risultato del RankingAgent per definire i pesi del ranking"
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

