from typing import Dict, List

# Legenda Punteggi (1-5) per APE e POI
SCORE_LEGEND = """LEGENDA PUNTEGGI (tutti su scala 1-5, dove 5=ottimo):

APE (Efficienza Energetica):
- ape_score_classe: Classe energetica (5=A1-A4, 3=B-E, 1=F-G)
- ape_score_impianto: Qualità impianto termico (5=Pompa calore/Teleriscaldamento, 3=Condensazione/Biomassa, 1=Tradizionale)
- ape_score_involucro: Isolamento edificio (5=Ottimo, 3=Medio, 1=Scarso/Assente)
- ape_score_rinnovabili: Presenza fonti rinnovabili (5=Sì, 1=No)
- ape_score_total: Media complessiva dei punteggi energetici

POI (Servizi di Prossimità):
- sanita: Vicinanza a servizi sanitari (Ospedali, farmacie)
- mobilita: Accessibilità trasporti pubblici (Metro, bus, stazioni)
- verde: Presenza aree verdi (Parchi, giardini)
- sport: Vicinanza impianti sportivi (Palestre, piscine)
- commerciale: Servizi commerciali (Negozi, supermercati)
- educazione: Scuole e istruzione (Scuole, università)
"""

# Legenda specifica per APE Agent (solo APE)
APE_SCORE_LEGEND = """LEGENDA PUNTEGGI APE (scala 1-5, dove 5=ottimo):

- ape_score_classe: Classe energetica (5=A1-A4, 3=B-E, 1=F-G)
- ape_score_impianto: Qualità impianto termico (5=Pompa calore/Teleriscaldamento, 3=Condensazione/Biomassa, 1=Tradizionale)
- ape_score_involucro: Isolamento edificio (5=Ottimo, 3=Medio, 1=Scarso/Assente)
- ape_score_rinnovabili: Presenza fonti rinnovabili (5=Sì, 1=No)
- ape_score_total: Media complessiva dei punteggi energetici
"""

# Colonne specifiche per Location Agent
LOCATION_AGENT_COLUMNS: List[str] = [
    "indirizzo",
    "numero_civico",
    "latitudine",
    "longitudine",
    "zona_omi",
]

# Colonne specifiche per APE Agent
APE_AGENT_COLUMNS: List[str] = [
    "classe_energetica_ape",
    "epglnren_ape",
    "classe_target_ape",
    "ape_score_classe",
    "ape_score_impianto",
    "ape_score_involucro",
    "ape_score_rinnovabili",
    "ape_score_total",
]

# Colonne specifiche per Property Technical Agent
PROPERTY_TECHNICAL_AGENT_COLUMNS: List[str] = [
    "tipologia_bene_immobile",
    "epoca_costruzione",
    "id",
    "codice_comune",
    "foglio",
    "particella",
    "subalterno",
    "numero_immobili_per_catasto",
    "superficie_di_riferimento_mq",
]

# Colonne specifiche per Normative Agent
NORMATIVE_AGENT_COLUMNS: List[str] = [
    "superficie_di_riferimento_mq",
    "tipologia_bene_immobile",
]

# Colonne specifiche per POI Agent
POI_AGENT_COLUMNS: List[str] = [
    "sanita",
    "mobilita",
    "verde",
    "sport",
    "commerciale",
    "educazione",
]


# Unione di tutte le colonne visibili agli agenti e quindi filtrabili via SQL
ALL_AGENT_COLUMNS_SET = set(
    LOCATION_AGENT_COLUMNS +
    APE_AGENT_COLUMNS +
    PROPERTY_TECHNICAL_AGENT_COLUMNS +
    NORMATIVE_AGENT_COLUMNS +
    POI_AGENT_COLUMNS
)

SQL_FILTERABLE_COLUMNS: List[str] = sorted(list(ALL_AGENT_COLUMNS_SET))
ALL_AGENT_COLUMNS: List[str] = SQL_FILTERABLE_COLUMNS

# Categorie POI per la documentazione
POI_CATEGORIES: Dict[str, str] = {
    "sanita": "Ospedali, farmacie, ambulatori",
    "mobilita": "Metro, bus, stazioni",
    "verde": "Parchi, giardini",
    "sport": "Palestre, piscine, campi",
    "commerciale": "Negozi, supermercati",
    "educazione": "Scuole, università",
}

