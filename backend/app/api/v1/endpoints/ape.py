"""
APE (Attestato Prestazione Energetica) API endpoints.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import pandas as pd
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

# APE data path (relative to backend/)
APE_CSV_PATH = Path("data/FOLDER_META/ape_detailed_data.parquet")

# Load APE data
from app.services.energy_score_calculator import get_calculator


def get_ape_dataframe() -> pd.DataFrame:
    """Load and cache the APE dataframe using robust calculator."""
    calculator = get_calculator()
    return calculator.load_and_compute()


class APEDetailResponse(BaseModel):
    """Response model for APE details - includes ALL useful fields from parquet."""

    # Basic identification
    file: str
    unita: Optional[str] = None
    indirizzo: Optional[str] = None
    data_emissione: Optional[str] = None

    # Energy class and metrics
    classe: Optional[str] = None
    epglnren: Optional[float] = None  # EP globale non rinnovabile
    epglren: Optional[float] = None  # EP globale rinnovabile
    co2: Optional[float] = None  # kg CO2/m²/anno
    superficie: Optional[float] = None

    # Energy vector and services
    vettore: Optional[str] = None  # Main energy source (Gas, Biomasse, etc.)
    serv_risc: Optional[bool] = None  # Has heating service
    serv_acs: Optional[bool] = None  # Has hot water service
    serv_raf: Optional[bool] = None  # Has cooling service
    serv_vent: Optional[bool] = None  # Has ventilation
    serv_illu: Optional[bool] = None  # Has lighting
    serv_trasp: Optional[bool] = None  # Has transport (elevators)

    # Location and building
    comune: Optional[str] = None
    zona_climatica: Optional[str] = None  # A, B, C, D, E, F
    anno_costruzione: Optional[str] = None
    tipologia_edilizia_str: Optional[str] = None
    tipologia_edilizia_cod: Optional[float] = None
    destinazione_uso_cod: Optional[float] = None  # Usage type code
    piano: Optional[str] = None

    # Quality indicators
    qualita_invernale: Optional[str] = None  # Sorridente, Basita, Triste
    qualita_estiva: Optional[str] = None
    fonti_rinnovabili: Optional[str] = None  # Sì, No

    # Intervention recommendations
    intervento_desc: Optional[str] = None
    intervento_classe_target: Optional[str] = None
    intervento_payback: Optional[float] = None  # anni

    # Heating system
    imp_risc_anno: Optional[str] = None
    imp_risc_desc: Optional[str] = None
    imp_risc_tipo: Optional[str] = None
    imp_risc_epnren: Optional[float] = None  # EP non rinnovabile riscaldamento

    # Hot water system
    imp_acs_anno: Optional[str] = None
    imp_acs_desc: Optional[str] = None
    imp_acs_tipo: Optional[str] = None
    imp_acs_epnren: Optional[float] = None  # EP non rinnovabile ACS

    # Cooling system
    imp_raf_anno: Optional[str] = None
    imp_raf_desc: Optional[str] = None
    imp_raf_tipo: Optional[str] = None
    imp_raf_epnren: Optional[float] = None  # EP non rinnovabile raffrescamento

    # Total consumption
    consumo_kwh_tot: Optional[float] = None  # kWh/anno

    # Cadastral info (complete)
    codice_catastale: Optional[str] = None
    sezione: Optional[str] = None
    foglio: Optional[str] = None
    particella: Optional[str] = None
    subalterno: Optional[str] = None
    subA: Optional[float] = None
    subDA: Optional[float] = None

    # Coordinates
    lat: Optional[float] = None
    lon: Optional[float] = None

    # APE scoring breakdown (internal scoring system)
    ape_class_score: Optional[int] = None  # Score based on energy class
    ape_system_score: Optional[int] = None  # Score based on systems
    ape_envelope_score: Optional[int] = None  # Score based on building envelope
    ape_renewables_score: Optional[int] = None  # Score based on renewables
    ape_total_points: Optional[int] = None  # Total points
    ape_score: Optional[int] = None  # Final APE score

    # Energy cost analysis (calculated)
    energy_score: Optional[int] = None  # Efficiency percentile score (0-100)
    kwh_per_sqm: Optional[float] = None  # kWh/m²/anno
    costo_annuo_euro: Optional[float] = None  # Estimated annual cost €
    costo_per_mq_anno: Optional[float] = None  # €/m²/anno
    confronto_media_kwh_mq: Optional[float] = None  # Average for usage type
    confronto_tipo_uso: Optional[str] = None  # Usage type name
    confronto_differenza_pct: Optional[float] = None  # % difference from average


def safe_value(val):
    """Return None for NaN values."""
    if pd.isna(val):
        return None
    return val


def safe_str(val):
    """Return string or None for NaN values."""
    if pd.isna(val):
        return None
    return str(val)


def safe_bool(val):
    """Return boolean or None for NaN values."""
    if pd.isna(val):
        return None
    return bool(val)


def safe_int(val):
    """Return int or None for NaN values."""
    if pd.isna(val):
        return None
    return int(val)


@router.get("/{filename}", response_model=APEDetailResponse)
async def get_ape_detail(filename: str):
    """
    Get APE details by filename.

    Args:
        filename: The APE file identifier (e.g., "2019_102341_0009.xml")

    Returns:
        APEDetailResponse with all available details
    """
    from app.services.energy_score_calculator import get_ape_score_details

    df = get_ape_dataframe()

    # Find the row with matching filename
    row = df[df["file"] == filename]

    if row.empty:
        raise HTTPException(status_code=404, detail=f"APE file '{filename}' not found")

    # Get first matching row
    r = row.iloc[0]

    # Get energy score details
    score_details = get_ape_score_details(filename)

    return APEDetailResponse(
        # Basic identification
        file=filename,
        unita=safe_str(r.get("unita")),
        indirizzo=safe_str(r.get("indirizzo")),
        data_emissione=safe_str(r.get("data_emissione")),
        # Energy class and metrics
        classe=safe_str(r.get("classe")),
        epglnren=safe_value(r.get("epglnren")),
        epglren=safe_value(r.get("epglren")),
        co2=safe_value(r.get("co2")),
        superficie=safe_value(r.get("superficie")),
        # Energy vector and services
        vettore=safe_str(r.get("vettore")),
        serv_risc=safe_bool(r.get("serv_risc")),
        serv_acs=safe_bool(r.get("serv_acs")),
        serv_raf=safe_bool(r.get("serv_raf")),
        serv_vent=safe_bool(r.get("serv_vent")),
        serv_illu=safe_bool(r.get("serv_illu")),
        serv_trasp=safe_bool(r.get("serv_trasp")),
        # Location and building
        comune=safe_str(r.get("comune")),
        zona_climatica=safe_str(r.get("zona_climatica")),
        anno_costruzione=safe_str(r.get("anno_costruzione")),
        tipologia_edilizia_str=safe_str(r.get("tipologia_edilizia_str")),
        tipologia_edilizia_cod=safe_value(r.get("tipologia_edilizia_cod")),
        destinazione_uso_cod=safe_value(r.get("destinazione_uso_cod")),
        piano=safe_str(r.get("piano")),
        # Quality indicators
        qualita_invernale=safe_str(r.get("qualita_invernale")),
        qualita_estiva=safe_str(r.get("qualita_estiva")),
        fonti_rinnovabili=safe_str(r.get("fonti_rinnovabili")),
        # Intervention recommendations
        intervento_desc=safe_str(r.get("intervento_desc")),
        intervento_classe_target=safe_str(r.get("intervento_classe_target")),
        intervento_payback=safe_value(r.get("intervento_payback")),
        # Heating system
        imp_risc_anno=safe_str(r.get("imp_risc_anno")),
        imp_risc_desc=safe_str(r.get("imp_risc_desc")),
        imp_risc_tipo=safe_str(r.get("imp_risc_tipo")),
        imp_risc_epnren=safe_value(r.get("imp_risc_epnren")),
        # Hot water system
        imp_acs_anno=safe_str(r.get("imp_acs_anno")),
        imp_acs_desc=safe_str(r.get("imp_acs_desc")),
        imp_acs_tipo=safe_str(r.get("imp_acs_tipo")),
        imp_acs_epnren=safe_value(r.get("imp_acs_epnren")),
        # Cooling system
        imp_raf_anno=safe_str(r.get("imp_raf_anno")),
        imp_raf_desc=safe_str(r.get("imp_raf_desc")),
        imp_raf_tipo=safe_str(r.get("imp_raf_tipo")),
        imp_raf_epnren=safe_value(r.get("imp_raf_epnren")),
        # Total consumption
        consumo_kwh_tot=safe_value(r.get("consumo_kwh_tot")),
        # Cadastral info (complete)
        codice_catastale=safe_str(r.get("codice_catastale")),
        sezione=safe_str(r.get("sezione")),
        foglio=safe_str(r.get("foglio")),
        particella=safe_str(r.get("particella")),
        subalterno=safe_str(r.get("subalterno")),
        subA=safe_value(r.get("subA")),
        subDA=safe_value(r.get("subDA")),
        # Coordinates
        lat=safe_value(r.get("lat")),
        lon=safe_value(r.get("lon")),
        # APE scoring breakdown
        ape_class_score=safe_int(r.get("ape_class_score")),
        ape_system_score=safe_int(r.get("ape_system_score")),
        ape_envelope_score=safe_int(r.get("ape_envelope_score")),
        ape_renewables_score=safe_int(r.get("ape_renewables_score")),
        ape_total_points=safe_int(r.get("ape_total_points")),
        ape_score=safe_int(r.get("ape_score")),
        # Energy cost analysis (calculated)
        energy_score=score_details.get("energy_score") if score_details else None,
        kwh_per_sqm=score_details.get("kwh_per_sqm") if score_details else None,
        costo_annuo_euro=(
            score_details.get("costo_annuo_euro") if score_details else None
        ),
        costo_per_mq_anno=(
            score_details.get("costo_per_mq_anno") if score_details else None
        ),
        confronto_media_kwh_mq=(
            score_details.get("confronto", {}).get("media_kwh_mq")
            if score_details
            else None
        ),
        confronto_tipo_uso=(
            score_details.get("confronto", {}).get("tipo_uso")
            if score_details
            else None
        ),
        confronto_differenza_pct=(
            score_details.get("confronto", {}).get("differenza_percentuale")
            if score_details
            else None
        ),
    )
