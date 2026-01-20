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
_ape_df: Optional[pd.DataFrame] = None


def get_ape_dataframe() -> pd.DataFrame:
    """Load and cache the APE dataframe."""
    global _ape_df
    if _ape_df is None:
        if not APE_CSV_PATH.exists():
            raise HTTPException(status_code=500, detail="APE data file not found")
        _ape_df = pd.read_parquet(APE_CSV_PATH)
    return _ape_df


class APEDetailResponse(BaseModel):
    """Response model for APE details."""

    file: str
    unita: Optional[str] = None
    indirizzo: Optional[str] = None
    data_emissione: Optional[str] = None
    classe: Optional[str] = None
    epglnren: Optional[float] = None
    epglren: Optional[float] = None
    co2: Optional[float] = None
    superficie: Optional[float] = None
    vettore: Optional[str] = None
    comune: Optional[str] = None
    zona_climatica: Optional[str] = None
    anno_costruzione: Optional[str] = None
    tipologia_edilizia_str: Optional[str] = None
    piano: Optional[str] = None
    # Quality indicators
    qualita_invernale: Optional[str] = None
    qualita_estiva: Optional[str] = None
    fonti_rinnovabili: Optional[str] = None
    # Intervention recommendations
    intervento_desc: Optional[str] = None
    intervento_classe_target: Optional[str] = None
    intervento_payback: Optional[float] = None
    # Heating system
    imp_risc_anno: Optional[str] = None
    imp_risc_desc: Optional[str] = None
    imp_risc_tipo: Optional[str] = None
    # Hot water system
    imp_acs_anno: Optional[str] = None
    imp_acs_desc: Optional[str] = None
    imp_acs_tipo: Optional[str] = None
    # Cooling system
    imp_raf_anno: Optional[str] = None
    imp_raf_desc: Optional[str] = None
    imp_raf_tipo: Optional[str] = None
    # Consumption
    consumo_kwh_tot: Optional[float] = None
    # Cadastral info
    foglio: Optional[str] = None
    particella: Optional[str] = None
    subalterno: Optional[str] = None


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


@router.get("/{filename}", response_model=APEDetailResponse)
async def get_ape_detail(filename: str):
    """
    Get APE details by filename.

    Args:
        filename: The APE file identifier (e.g., "2019_102341_0009.xml")

    Returns:
        APEDetailResponse with all available details
    """
    df = get_ape_dataframe()

    # Find the row with matching filename
    row = df[df["file"] == filename]

    if row.empty:
        raise HTTPException(status_code=404, detail=f"APE file '{filename}' not found")

    # Get first matching row
    r = row.iloc[0]

    return APEDetailResponse(
        file=filename,
        unita=safe_str(r.get("unita")),
        indirizzo=safe_str(r.get("indirizzo")),
        data_emissione=safe_str(r.get("data_emissione")),
        classe=safe_str(r.get("classe")),
        epglnren=safe_value(r.get("epglnren")),
        epglren=safe_value(r.get("epglren")),
        co2=safe_value(r.get("co2")),
        superficie=safe_value(r.get("superficie")),
        vettore=safe_str(r.get("vettore")),
        comune=safe_str(r.get("comune")),
        zona_climatica=safe_str(r.get("zona_climatica")),
        anno_costruzione=safe_str(r.get("anno_costruzione")),
        tipologia_edilizia_str=safe_str(r.get("tipologia_edilizia_str")),
        piano=safe_str(r.get("piano")),
        qualita_invernale=safe_str(r.get("qualita_invernale")),
        qualita_estiva=safe_str(r.get("qualita_estiva")),
        fonti_rinnovabili=safe_str(r.get("fonti_rinnovabili")),
        intervento_desc=safe_str(r.get("intervento_desc")),
        intervento_classe_target=safe_str(r.get("intervento_classe_target")),
        intervento_payback=safe_value(r.get("intervento_payback")),
        imp_risc_anno=safe_str(r.get("imp_risc_anno")),
        imp_risc_desc=safe_str(r.get("imp_risc_desc")),
        imp_risc_tipo=safe_str(r.get("imp_risc_tipo")),
        imp_acs_anno=safe_str(r.get("imp_acs_anno")),
        imp_acs_desc=safe_str(r.get("imp_acs_desc")),
        imp_acs_tipo=safe_str(r.get("imp_acs_tipo")),
        imp_raf_anno=safe_str(r.get("imp_raf_anno")),
        imp_raf_desc=safe_str(r.get("imp_raf_desc")),
        imp_raf_tipo=safe_str(r.get("imp_raf_tipo")),
        consumo_kwh_tot=safe_value(r.get("consumo_kwh_tot")),
        foglio=safe_str(r.get("foglio")),
        particella=safe_str(r.get("particella")),
        subalterno=safe_str(r.get("subalterno")),
    )
