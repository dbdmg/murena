"""
Energy Performance Certificate (EPC) API endpoints.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import pandas as pd
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

# Energy data path (relative to backend/)
ENERGY_DATA_PATH = Path("data/FOLDER_META/ape_detailed_data.parquet")

# Load APE data
from app.services.energy_score_calculator import get_energy_calculator


def get_energy_dataframe() -> pd.DataFrame:
    """Load and cache the energy dataframe using robust calculator."""
    calculator = get_energy_calculator()
    return calculator.load_and_compute()


class EnergyDetailResponse(BaseModel):
    """Response model for energy details - includes all relevant fields from dataset."""

    # Basic identification
    file: str
    unit: Optional[str] = None
    address: Optional[str] = None
    issue_date: Optional[str] = None

    # Energy class and metrics
    energy_class: Optional[str] = None
    epglnren: Optional[float] = None  # Non-renewable global performance
    epglren: Optional[float] = None  # Renewable global performance
    co2_emissions: Optional[float] = None  # kg CO2/m²/year
    surface_area: Optional[float] = None

    # Energy vector and services
    energy_vector: Optional[str] = None  # Main energy source (Gas, Biomass, etc.)
    heating_service: Optional[bool] = None  # Has heating service
    hot_water_service: Optional[bool] = None  # Has hot water service
    cooling_service: Optional[bool] = None  # Has cooling service
    ventilation_service: Optional[bool] = None  # Has ventilation
    lighting_service: Optional[bool] = None  # Has lighting
    transport_service: Optional[bool] = None  # Has transport (elevators)

    # Location and building
    city: Optional[str] = None
    climate_zone: Optional[str] = None  # A, B, C, D, E, F
    construction_year: Optional[str] = None
    property_type_desc: Optional[str] = None
    property_type_code: Optional[float] = None
    usage_type_code: Optional[float] = None
    floor: Optional[str] = None

    # Quality indicators
    winter_quality: Optional[str] = None  # SMILE, NEUTRAL, SAD equivalents
    summer_quality: Optional[str] = None
    renewables_available: Optional[str] = None  # Yes, No

    # Intervention recommendations
    renovation_desc: Optional[str] = None
    target_energy_class: Optional[str] = None
    payback_period: Optional[float] = None  # years

    # Heating system
    heating_system_year: Optional[str] = None
    heating_system_desc: Optional[str] = None
    heating_system_type: Optional[str] = None
    heating_system_epnren: Optional[float] = None  # Non-renewable EP for heating

    # Hot water system
    hot_water_system_year: Optional[str] = None
    hot_water_system_desc: Optional[str] = None
    hot_water_system_type: Optional[str] = None
    hot_water_system_epnren: Optional[float] = None  # Non-renewable EP for hot water

    # Cooling system
    cooling_system_year: Optional[str] = None
    cooling_system_desc: Optional[str] = None
    cooling_system_type: Optional[str] = None
    cooling_system_epnren: Optional[float] = None  # Non-renewable EP for cooling

    # Total consumption
    total_annual_kwh: Optional[float] = None  # kWh/year

    # Cadastral info
    cadastral_code: Optional[str] = None
    section: Optional[str] = None
    sheet: Optional[str] = None
    parcel: Optional[str] = None
    subaltern: Optional[str] = None

    # Coordinates
    lat: Optional[float] = None
    lon: Optional[float] = None

    # Energy scoring breakdown (internal scoring system)
    energy_score_class: Optional[int] = None
    energy_score_system: Optional[int] = None
    energy_score_envelope: Optional[int] = None
    energy_score_renewables: Optional[int] = None
    energy_total_points: Optional[int] = None
    energy_raw_score: Optional[int] = None

    # Energy cost analysis (calculated)
    energy_score: Optional[int] = None  # Efficiency percentile score (0-100)
    kwh_per_sqm: Optional[float] = None  # kWh/m²/year
    annual_cost_estimate: Optional[float] = None  # Estimated annual cost €
    cost_per_sqm_year: Optional[float] = None  # €/m²/year
    average_kwh_sqm_comparison: Optional[float] = None  # Average for usage type
    usage_type_comparison: Optional[str] = None  # Usage type name
    percentage_difference_comparison: Optional[float] = None  # % difference from average


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


@router.get("/{filename}", response_model=EnergyDetailResponse)
async def get_energy_detail(filename: str):
    """
    Get energy details by filename.

    Args:
        filename: The energy file identifier (e.g., "2019_102341_0009.xml")

    Returns:
        EnergyDetailResponse with all available details
    """
    from app.services.energy_score_calculator import get_energy_score_details

    df = get_energy_dataframe()

    # Find the row with matching filename
    row = df[df["file"] == filename]

    if row.empty:
        raise HTTPException(status_code=404, detail=f"Energy file '{filename}' not found")

    # Get first matching row
    r = row.iloc[0]

    # Get energy score details
    score_details = get_energy_score_details(filename)

    return EnergyDetailResponse(
        # Basic identification
        file=filename,
        unit=safe_str(r.get("unita")),
        address=safe_str(r.get("indirizzo")),
        issue_date=safe_str(r.get("data_emissione")),
        # Energy class and metrics
        energy_class=safe_str(r.get("classe")),
        epglnren=safe_value(r.get("epglnren")),
        epglren=safe_value(r.get("epglren")),
        co2_emissions=safe_value(r.get("co2")),
        surface_area=safe_value(r.get("superficie")),
        # Energy vector and services
        energy_vector=safe_str(r.get("vettore")),
        heating_service=safe_bool(r.get("serv_risc")),
        hot_water_service=safe_bool(r.get("serv_acs")),
        cooling_service=safe_bool(r.get("serv_raf")),
        ventilation_service=safe_bool(r.get("serv_vent")),
        lighting_service=safe_bool(r.get("serv_illu")),
        transport_service=safe_bool(r.get("serv_trasp")),
        # Location and building
        city=safe_str(r.get("comune")),
        climate_zone=safe_str(r.get("zona_climatica")),
        construction_year=safe_str(r.get("anno_costruzione")),
        property_type_desc=safe_str(r.get("tipologia_edilizia_str")),
        property_type_code=safe_value(r.get("tipologia_edilizia_cod")),
        usage_type_code=safe_value(r.get("destinazione_uso_cod")),
        floor=safe_str(r.get("piano")),
        # Quality indicators
        winter_quality=safe_str(r.get("qualita_invernale")),
        summer_quality=safe_str(r.get("qualita_estiva")),
        renewables_available=safe_str(r.get("fonti_rinnovabili")),
        # Intervention recommendations
        renovation_desc=safe_str(r.get("intervento_desc")),
        target_energy_class=safe_str(r.get("intervento_classe_target")),
        payback_period=safe_value(r.get("intervento_payback")),
        # Heating system
        heating_system_year=safe_str(r.get("imp_risc_anno")),
        heating_system_desc=safe_str(r.get("imp_risc_desc")),
        heating_system_type=safe_str(r.get("imp_risc_tipo")),
        heating_system_epnren=safe_value(r.get("imp_risc_epnren")),
        # Hot water system
        hot_water_system_year=safe_str(r.get("imp_acs_anno")),
        hot_water_system_desc=safe_str(r.get("imp_acs_desc")),
        hot_water_system_type=safe_str(r.get("imp_acs_tipo")),
        hot_water_system_epnren=safe_value(r.get("imp_acs_epnren")),
        # Cooling system
        cooling_system_year=safe_str(r.get("imp_raf_anno")),
        cooling_system_desc=safe_str(r.get("imp_raf_desc")),
        cooling_system_type=safe_str(r.get("imp_raf_tipo")),
        cooling_system_epnren=safe_value(r.get("imp_raf_epnren")),
        # Total consumption
        total_annual_kwh=safe_value(r.get("consumo_kwh_tot")),
        # Cadastral info
        cadastral_code=safe_str(r.get("codice_catastale")),
        section=safe_str(r.get("sezione")),
        sheet=safe_str(r.get("foglio")),
        parcel=safe_str(r.get("particella")),
        subaltern=safe_str(r.get("subalterno")),
        # Coordinates
        lat=safe_value(r.get("lat")),
        lon=safe_value(r.get("lon")),
        # Energy scoring breakdown
        energy_score_class=safe_int(r.get("energy_score_class")),
        energy_score_system=safe_int(r.get("energy_score_plant")),
        energy_score_envelope=safe_int(r.get("energy_score_envelope")),
        energy_score_renewables=safe_int(r.get("energy_score_renewables")),
        energy_total_points=safe_int(r.get("energy_total_points")),
        energy_raw_score=safe_int(r.get("energy_score")),
        # Energy cost analysis (calculated)
        energy_score=score_details.get("ape_score") if score_details else None,
        kwh_per_sqm=score_details.get("kwh_per_sqm") if score_details else None,
        annual_cost_estimate=(
            score_details.get("costo_annuo_euro") if score_details else None
        ),
        cost_per_sqm_year=(
            score_details.get("costo_per_mq_anno") if score_details else None
        ),
        average_kwh_sqm_comparison=(
            score_details.get("confronto", {}).get("media_kwh_mq")
            if score_details
            else None
        ),
        usage_type_comparison=(
            score_details.get("confronto", {}).get("tipo_uso")
            if score_details
            else None
        ),
        percentage_difference_comparison=(
            score_details.get("confronto", {}).get("differenza_percentuale")
            if score_details
            else None
        ),
    )
