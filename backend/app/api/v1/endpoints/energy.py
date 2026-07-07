"""
Energy Performance Certificate (EPC) API endpoints.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import re
import pandas as pd
from typing import Any, Optional
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter()

# Energy data path (relative to backend/)
ENERGY_DATA_PATH = Path("data/FOLDER_META/ape_detailed_data.parquet")

# Load APE data
from app.services.energy_score_calculator import DEFAULT_KWH_COST

_energy_dataframe_cache: Optional[pd.DataFrame] = None


def get_energy_dataframe() -> pd.DataFrame:
    """Load and cache the current energy/building dataframe."""
    global _energy_dataframe_cache
    if _energy_dataframe_cache is not None:
        return _energy_dataframe_cache

    dataset_path = Path(settings.DATASET_FULL)
    if not dataset_path.exists() and not dataset_path.is_absolute():
        dataset_path = Path(__file__).resolve().parents[4] / dataset_path

    if not dataset_path.exists():
        _energy_dataframe_cache = pd.DataFrame()
        return _energy_dataframe_cache

    _energy_dataframe_cache = pd.read_parquet(dataset_path)
    return _energy_dataframe_cache


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


def normalize_filename(filename: str) -> str:
    """Normalize an APE file identifier to a basename."""
    normalized = str(filename).strip().replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def first_available(row: pd.Series, *columns: str) -> Any:
    """Return the first non-null value for the provided column names."""
    for column in columns:
        if column not in row.index:
            continue
        value = row.get(column)
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        return value
    return None


def safe_float(val) -> Optional[float]:
    """Return float or None for missing/unparseable values."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def city_from_row(row: pd.Series) -> Optional[str]:
    """Map cadastral city codes to readable names when possible."""
    city = first_available(row, "comune", "city")
    if city:
        return str(city)

    code = first_available(row, "codice_comune", "cadastral_code")
    target_code = getattr(settings, "TARGET_COMUNE_CODE", "L219")
    if code == "L219" or code == target_code:
        return getattr(settings, "TARGET_CITY", "Torino")
    return safe_str(code)


def find_aggregate_energy_row(df: pd.DataFrame, filename: str) -> Optional[pd.Series]:
    """Find a row in the aggregate Turin dataset whose APE file list contains filename."""
    file_name = normalize_filename(filename)
    file_stem = re.sub(r"\.xml$", "", file_name, flags=re.IGNORECASE)
    candidate_columns = [
        "lista_file_ape",
        "list_file_ape_filtered",
        "list_file_ape_filtered_parsed",
        "energy_files",
        "ape_file_list",
    ]

    for term in dict.fromkeys([file_name, file_stem]):
        if not term:
            continue
        escaped = re.escape(term)
        for column in candidate_columns:
            if column not in df.columns:
                continue
            matches = df[column].astype(str).str.contains(escaped, na=False, regex=True)
            if matches.any():
                return df.loc[matches].iloc[0]

    return None


def aggregate_score_details(df: pd.DataFrame, row: pd.Series) -> dict[str, Any]:
    """Compute comparable cost/efficiency details from the aggregate Turin parquet."""
    kwh_per_sqm = safe_float(first_available(row, "epglnren_ape", "epglnren"))
    surface = safe_float(
        first_available(row, "superficie_di_riferimento_mq", "surface_area", "superficie")
    )

    total_kwh = kwh_per_sqm * surface if kwh_per_sqm is not None and surface else None
    annual_cost = total_kwh * DEFAULT_KWH_COST if total_kwh is not None else None
    cost_per_sqm_year = kwh_per_sqm * DEFAULT_KWH_COST if kwh_per_sqm is not None else None

    comparison_col = next(
        (col for col in ["epglnren_ape", "epglnren"] if col in df.columns),
        None,
    )
    average_kwh = None
    percentage_difference = None
    percentile_score = None
    if comparison_col and kwh_per_sqm is not None:
        values = pd.to_numeric(df[comparison_col], errors="coerce")
        values = values[(values > 0) & (values < 1000)].dropna()
        if not values.empty:
            average_kwh = float(values.mean())
            if average_kwh > 0:
                percentage_difference = ((kwh_per_sqm - average_kwh) / average_kwh) * 100
            percentile_score = int(round((values > kwh_per_sqm).mean() * 100))

    return {
        "energy_score": percentile_score,
        "kwh_per_sqm": round(kwh_per_sqm, 1) if kwh_per_sqm is not None else None,
        "annual_kwh_consumption": round(total_kwh, 0) if total_kwh is not None else None,
        "annual_cost_estimate": round(annual_cost, 2) if annual_cost is not None else None,
        "cost_per_sqm_year": (
            round(cost_per_sqm_year, 2) if cost_per_sqm_year is not None else None
        ),
        "comparison": {
            "usage_type": "Turin EPC dataset",
            "average_kwh_sqm": round(average_kwh, 1) if average_kwh is not None else None,
            "percentage_difference": (
                round(percentage_difference, 1)
                if percentage_difference is not None
                else None
            ),
        },
    }


def aggregate_energy_response(
    filename: str, row: pd.Series, df: pd.DataFrame
) -> EnergyDetailResponse:
    """Build an EnergyDetailResponse from the aggregate Turin estates dataset."""
    score_details = aggregate_score_details(df, row)
    address = first_available(row, "indirizzo", "address")
    civic = first_available(row, "numero_civico", "house_number")
    address_str = f"{address}, {civic}" if address and civic else safe_str(address)

    return EnergyDetailResponse(
        file=normalize_filename(filename),
        address=address_str,
        energy_class=safe_str(first_available(row, "classe_energetica_ape", "energy_class")),
        epglnren=safe_value(first_available(row, "epglnren_ape", "epglnren")),
        epglren=safe_value(first_available(row, "epglren_ape", "epglren")),
        co2_emissions=safe_value(first_available(row, "emissioni_co2", "co2")),
        surface_area=safe_value(
            first_available(row, "superficie_di_riferimento_mq", "surface_area", "superficie")
        ),
        city=city_from_row(row),
        construction_year=safe_str(first_available(row, "epoca_costruzione", "construction_year")),
        property_type_desc=safe_str(first_available(row, "tipologia_bene_immobile", "property_type")),
        target_energy_class=safe_str(first_available(row, "classe_target_ape", "target_energy_class")),
        cadastral_code=safe_str(first_available(row, "codice_comune", "cadastral_code")),
        sheet=safe_str(first_available(row, "foglio", "cadastral_sheet")),
        parcel=safe_str(first_available(row, "particella", "cadastral_parcel")),
        subaltern=safe_str(first_available(row, "subalterno", "cadastral_subaltern")),
        lat=safe_value(first_available(row, "latitudine", "lat", "latitude")),
        lon=safe_value(first_available(row, "longitudine", "lon", "longitude")),
        energy_score_class=safe_int(first_available(row, "ape_score_classe", "energy_score_class")),
        energy_score_system=safe_int(first_available(row, "ape_score_impianto", "energy_score_plant")),
        energy_score_envelope=safe_int(first_available(row, "ape_score_involucro", "energy_score_envelope")),
        energy_score_renewables=safe_int(first_available(row, "ape_score_rinnovabili", "energy_score_renewables")),
        energy_total_points=safe_int(first_available(row, "ape_score_total", "energy_score_total")),
        energy_raw_score=safe_int(first_available(row, "ape_score_total", "energy_score")),
        total_annual_kwh=score_details.get("annual_kwh_consumption"),
        energy_score=score_details.get("energy_score"),
        kwh_per_sqm=score_details.get("kwh_per_sqm"),
        annual_cost_estimate=score_details.get("annual_cost_estimate"),
        cost_per_sqm_year=score_details.get("cost_per_sqm_year"),
        average_kwh_sqm_comparison=score_details.get("comparison", {}).get("average_kwh_sqm"),
        usage_type_comparison=score_details.get("comparison", {}).get("usage_type"),
        percentage_difference_comparison=score_details.get("comparison", {}).get("percentage_difference"),
    )


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
    file_name = normalize_filename(filename)

    if df.empty:
        raise HTTPException(status_code=404, detail="Energy dataset is empty")

    # New Turin real-data exports only contain aggregate estate rows with
    # lista_file_ape; older detailed exports contain one APE row per "file".
    if "file" not in df.columns:
        aggregate_row = find_aggregate_energy_row(df, file_name)
        if aggregate_row is None:
            raise HTTPException(status_code=404, detail=f"Energy file '{file_name}' not found")
        return aggregate_energy_response(file_name, aggregate_row, df)

    file_series = df["file"].astype(str)
    row = df[
        (file_series == file_name)
        | (file_series.map(normalize_filename) == file_name)
    ]

    if row.empty:
        aggregate_row = find_aggregate_energy_row(df, file_name)
        if aggregate_row is not None:
            return aggregate_energy_response(file_name, aggregate_row, df)
        raise HTTPException(status_code=404, detail=f"Energy file '{file_name}' not found")

    # Get first matching row
    r = row.iloc[0]

    # Get energy score details
    score_details = get_energy_score_details(file_name)

    return EnergyDetailResponse(
        # Basic identification
        file=file_name,
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
        energy_score=score_details.get("energy_score") if score_details else None,
        kwh_per_sqm=score_details.get("kwh_per_sqm") if score_details else None,
        annual_cost_estimate=(
            score_details.get("annual_cost_estimate") if score_details else None
        ),
        cost_per_sqm_year=(
            score_details.get("cost_per_sqm_year") if score_details else None
        ),
        average_kwh_sqm_comparison=(
            score_details.get("comparison", {}).get("average_kwh_sqm")
            if score_details
            else None
        ),
        usage_type_comparison=(
            score_details.get("comparison", {}).get("usage_type")
            if score_details
            else None
        ),
        percentage_difference_comparison=(
            score_details.get("comparison", {}).get("percentage_difference")
            if score_details
            else None
        ),
    )
