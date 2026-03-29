"""
Application configuration management using Pydantic Settings.
Merged constants from original app/config.py
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==========================================================================
    # App Info
    # ==========================================================================
    APP_NAME: str = "MURENA-API"
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
    DATABASE_PATH: str = "data/database/users.db"  # SQLite fallback
    CACHE_DIR: str = "data/database/cache"

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
    HF_TOKEN: str = ""

    # API key for the institutional LLM endpoint (anonymized for review)
    INSTITUTIONAL_LLM_API_KEY: str = ""  

    # LLM Provider: "openai" or "gemini" - controls which provider to use by default
    DEFAULT_LLM_PROVIDER: str = "openai"

    # LLM Models
    OPENAI_MODEL_FAST: str = "gpt-oss-120b"
    OPENAI_MODEL_SMART: str = "gpt-oss-120b"
    OPENAI_API_BASE: Optional[str] = "https://api.institutional-endpoint.edu/v1"

    LLMODEL_CONCURRENCY_LIMITS = {
        "gpt-5.4": 2,
        "gpt-oss-120b": 48,
        "gemma3-27b": 48,
        "qwen3-8b": 48,
    }

    def set_llm_model(self, model_type: str):
        """Sets the LLM model configuration.
        
        Args:
            model_type: The identifier for the LLM flavor to use.
        """
        if model_type == "gpt-oss-120b":
            self.OPENAI_MODEL_FAST = "gpt-oss-120b"
            self.OPENAI_MODEL_SMART = "gpt-oss-120b"
            self.OPENAI_API_BASE = "https://api.institutional-endpoint.edu/v1"
            self.OPENAI_API_KEY = self.INSTITUTIONAL_LLM_API_KEY
        elif model_type == "gemma3-27b":
            self.OPENAI_MODEL_FAST = "google/gemma-3-27b-it"
            self.OPENAI_MODEL_SMART = "google/gemma-3-27b-it"
            self.OPENAI_API_BASE = "http://localhost:8000/v1"
            self.OPENAI_API_KEY = "vllm"
        elif model_type == "qwen3-8b":
            self.OPENAI_MODEL_FAST = "Qwen/Qwen3-8B"
            self.OPENAI_MODEL_SMART = "Qwen/Qwen3-8B"
            self.OPENAI_API_BASE = "http://localhost:8001/v1"
            self.OPENAI_API_KEY = "vllm"
        elif model_type == "gpt-5.4":
            self.OPENAI_MODEL_FAST = "gpt-5.4"
            self.OPENAI_MODEL_SMART = "gpt-5.4"
            self.OPENAI_API_BASE = None # Base OpenAI


    # Agent Temperature - 0.0 for fully deterministic outputs (consistency)
    # Set to 0.0 to eliminate non-determinism, higher values allow creativity
    AGENT_TEMPERATURE: float = 0.0

    # Enable JSON export of run results for LLM analysis/debugging
    # Set to False in production to avoid unnecessary file writes
    ENABLE_RUN_JSON_EXPORT: bool = False

    # ==========================================================================
    # External APIs
    # ==========================================================================
    NOMINATIM_USER_AGENT: str = "MURENA/1.0"

    # ==========================================================================
    # File Paths (relative to backend/ directory)
    DATA_DIR: str = "data/datasets"
    STATIC_DIR: str = "data/static_data"
    ENERGY_DIR: str = "data/energy_data"
    META_DIR: str = "data/metadata"
    RUNS_DIR: str = "data/runs"
    AGENT_LOGS_DIR: str = "data/agent_logs"

    # Energy specific paths
    ENERGY_MATCH_DIR: str = "data/energy_data/MATCH"
    PLOT_DIR: str = "data/energy_data/metadata/plots_inverted"

    # Dataset paths
    DATASET_FULL: str = (
        "data/metadata/immobili_with_meta_and_ape_full_cleaned.parquet"
    )
    IMMOBILI_MAPPING_PATH: str = os.path.normpath("notebooks/02_quotazione/mapping_immobili.csv")
    QIP_VALORI_PATH: str = "notebooks/02_quotazione/QIP_1303437_1_20251_VALORI.csv"
    QIP_MAPPING_PATH: str = "notebooks/02_quotazione/mapping_qip.csv"
    ZONE_OMI_PROVINCIA_TORINO_GEOJSON: str = "data/static_data/zone_omi_provincia_torino.geojson.zip"
    IMMOBILI_QUOTAZIONE_PATH: str = "notebooks/02_quotazione/quotazione_immobili.csv"
    ZONE_GRUPPO_QUOTAZIONI_PATH: str = "notebooks/02_quotazione/zone_gruppo_quotazioni.csv"
    MISSING_QUOTAZIONI_IDS_PATH: str = "notebooks/02_quotazione/missing_quotazioni_ids.csv"
    ENERGY_DETAILED_DATA_PATH: str = "data/metadata/ape_detailed_data.parquet"

    # Static data
    STATIONS_CSV: str = "data/datasets/station_dataframe.csv"
    ZONE_OMI_GEOJSON: str = "data/static_data/omi_zones.geojson"
    ZONE_URBANISTICHE_GEOJSON: str = (
        "data/static_data/rome_urban_zones.geojson"
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
            "energy": self.ENERGY_DETAILED_DATA_PATH,
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
class DynamicAgentModels(dict):
    """Proxy dictionary that always returns current values from settings.agent_models."""
    def get(self, key, default=None):
        return settings.agent_models.get(key, default)
    def __getitem__(self, key):
        return settings.agent_models[key]
    def __contains__(self, key):
        return key in settings.agent_models
    def __iter__(self):
        return iter(settings.agent_models)
    def __len__(self):
        return len(settings.agent_models)
    def __repr__(self):
        return repr(settings.agent_models)
    def __str__(self):
        return str(settings.agent_models)
    def items(self):
        return settings.agent_models.items()
    def keys(self):
        return settings.agent_models.keys()
    def values(self):
        return settings.agent_models.values()

AGENT_MODELS = DynamicAgentModels()

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
