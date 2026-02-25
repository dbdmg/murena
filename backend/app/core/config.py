"""
Application configuration management using Pydantic Settings.
Merged constants from original app/config.py
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==========================================================================
    # App Info
    # ==========================================================================
    APP_NAME: str = "MEF-Immobili-API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ==========================================================================
    # Server
    # ==========================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_PATH: str = "data/FOLDER_DATABASE/users.db"  # SQLite fallback
    CACHE_DIR: str = "data/FOLDER_DATABASE/cache"

    # ==========================================================================
    # Redis
    # ==========================================================================
    REDIS_URL: str = "redis://localhost:6379/0"

    # ==========================================================================
    # Security
    # ==========================================================================
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ==========================================================================
    # CORS
    # ==========================================================================
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost",
        "http://localhost:80",
        "http://127.0.0.1",
        "http://127.0.0.1:80",
    ]

    # ==========================================================================
    # LLM APIs
    # ==========================================================================
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: Optional[str] = None  # Use custom base URL for OSS models

    # LLM Provider: "openai" o "gemini" - controlla quale provider usare di default
    DEFAULT_LLM_PROVIDER: str = "openai"

    # LLM Models
    OPENAI_MODEL_FAST: str = "gpt-oss-120b"
    OPENAI_MODEL_SMART: str = "gpt-oss-120b"
    USE_MOCK_RESPONSES: bool = False
    USE_MOCK_NORMATIVE_AGENT: bool = False

    # Agent Temperature - 0.0 for fully deterministic outputs (consistency)
    # Set to 0.0 to eliminate non-determinism, higher values allow creativity
    AGENT_TEMPERATURE: float = 0.0

    # OSS Local Model Config
    OSS_DEVICE: str = "auto"  # "auto", "cpu", "mps", "cuda"
    OSS_MAX_TOKENS: int = 2048

    # Enable JSON export of run results for LLM analysis/debugging
    # Set to False in production to avoid unnecessary file writes
    ENABLE_RUN_JSON_EXPORT: bool = False

    # ==========================================================================
    # External APIs
    # ==========================================================================
    NOMINATIM_USER_AGENT: str = "MEF-Immobili/1.0"

    # ==========================================================================
    # File Paths (relative to backend/ directory)
    # ==========================================================================
    DATA_DIR: str = "data/FOLDER_DATASET"
    STATIC_DIR: str = "data/FOLDER_STATIC_ROME"
    APE_DIR: str = "data/FOLDER_APE"
    META_DIR: str = "data/FOLDER_META"
    RUNS_DIR: str = "data/runs"
    AGENT_LOGS_DIR: str = "data/agent_logs"

    # APE specific paths
    APE_MATCH_DIR: str = "data/FOLDER_APE/MATCH"
    PLOT_DIR: str = "data/FOLDER_APE/META/plots_inverted"

    # Dataset paths
    DATASET_FULL: str = (
        "data/FOLDER_META/immobili_with_meta_and_ape_full_cleaned.parquet"
    )
    IMMOBILI_MAPPING_PATH: str = os.path.normpath("notebooks/02_quotazione/mapping_immobili.csv")
    QIP_VALORI_PATH: str = "notebooks/02_quotazione/QIP_1303437_1_20251_VALORI.csv"
    QIP_MAPPING_PATH: str = "notebooks/02_quotazione/mapping_qip.csv"
    ZONE_OMI_PROVINCIA_TORINO_GEOJSON: str = "/Users/marcodeluca/Downloads/real-estate-ai/backend/data/FOLDER_STATIC_ROME/zone_omi_provincia_torino.geojson.zip"
    IMMOBILI_QUOTAZIONE_PATH: str = "notebooks/02_quotazione/quotazione_immobili.csv"
    ZONE_GRUPPO_QUOTAZIONI_PATH: str = "notebooks/02_quotazione/zone_gruppo_quotazioni.csv"
    MISSING_QUOTAZIONI_IDS_PATH: str = "notebooks/02_quotazione/missing_quotazioni_ids.csv"
    # NOTE: DATASET_META and DATASET_APE removed - they were legacy files never used
    # The application uses DATASET_FULL as the single source of truth
    APE_DETAILED_DATA_PATH: str = "data/FOLDER_META/ape_detailed_data.parquet"

    # Static data
    STATIONS_CSV: str = "data/FOLDER_DATASET/station_dataframe.csv"
    POPULATION_CSV: str = (
        "data/FOLDER_STATIC_ROME/dati_popolazione_roma_normalizzati.csv"
    )
    MUNICIPI_GEOJSON: str = "data/FOLDER_STATIC_ROME/municipi_roma.geojson"
    ZONE_OMI_GEOJSON: str = "data/FOLDER_STATIC_ROME/Zone_omi_torino.geojson"
    ZONE_URBANISTICHE_GEOJSON: str = (
        "data/FOLDER_STATIC_ROME/roma_zone_urbanistiche.geojson"
    )

    TORINO_LAT: float = 45.116177
    TORINO_LON: float = 7.742615

    # ==========================================================================
    # Map Configuration
    # ==========================================================================
    DEFAULT_MAP_CENTER_LAT: float = 45.070860
    DEFAULT_MAP_CENTER_LON: float = 7.685588
    DEFAULT_MAP_ZOOM: int = 13
    SELECTED_ITEM_ZOOM: int = 15

    # ==========================================================================
    # Limits and Caps
    # ==========================================================================
    MAX_ITEMS_FOR_MAP: int = 1000
    MAX_ITEMS_FOR_LLM: int = 25
    MAX_LLM_CAP: int = 10  # Hard cap for LLM evaluation

    # ==========================================================================
    # Calculation Constants
    # ==========================================================================
    MINUTES_PER_KM_WALKING: int = 12  # 5 km/h
    MINUTES_PER_METRO_STATION_SEGMENT: int = 2

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "../../.env"), case_sensitive=True, extra="ignore"
    )

    # ==========================================================================
    # Computed Properties
    # ==========================================================================
    @property
    def dataset_options(self) -> Dict[str, str]:
        """Return dataset options mapping.

        Note: Only 'full' is actively used. The 'ape' option points to
        detailed APE data used by the /ape endpoint.
        """
        return {
            "full": self.DATASET_FULL,
            "ape": self.APE_DETAILED_DATA_PATH,
        }

    @property
    def agent_models(self) -> Dict[str, str]:
        """Return agent-specific model configuration."""
        return {
            "default": self.OPENAI_MODEL_FAST,
        }


# Global settings instance
settings = Settings()

# Export agent-specific settings
AGENT_MODELS = settings.agent_models
USE_MOCK_NORMATIVE_AGENT = settings.USE_MOCK_NORMATIVE_AGENT

# Legacy constants for backward compatibility
QIP_VALORI_PATH = settings.QIP_VALORI_PATH
QIP_MAPPING_PATH = settings.QIP_MAPPING_PATH
ZONE_OMI_PROVINCIA_TORINO_GEOJSON = settings.ZONE_OMI_PROVINCIA_TORINO_GEOJSON
IMMOBILI_QUOTAZIONE_PATH = settings.IMMOBILI_QUOTAZIONE_PATH
ZONE_GRUPPO_QUOTAZIONI_PATH = settings.ZONE_GRUPPO_QUOTAZIONI_PATH
MISSING_QUOTAZIONI_IDS_PATH = settings.MISSING_QUOTAZIONI_IDS_PATH
DATASET_FULL = settings.DATASET_FULL
ZONE_OMI_GEOJSON = settings.ZONE_OMI_GEOJSON
TORINO_LAT = settings.TORINO_LAT
TORINO_LON = settings.TORINO_LON
