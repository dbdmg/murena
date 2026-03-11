"""
Model configuration for test scripts.

Each entry in MODEL_OPTIONS defines a fully-specified model target that can be
selected via --model when running test scripts. The key is the CLI identifier.

Fields:
    backend   : human-readable backend label (informational).
    model     : model name as expected by the API endpoint.
    api_base  : base URL for the API (None = default OpenAI endpoint).
    api_key   : API key to use (None = read from OPENAI_API_KEY env variable).
    provider  : internal routing hint used by set_llm_model logic.
"""

import os
from typing import TypedDict, Optional


class ModelConfig(TypedDict):
    backend: str
    model: str
    api_base: Optional[str]
    api_key: Optional[str]
    provider: str  # "openai" | "llm_polito" | "ollama" | "vllm"
    supports_structured_output: bool  # whether the model reliably handles function_calling / json_mode


MODEL_OPTIONS: dict[str, ModelConfig] = {
    "gpt-5-nano": {
        "backend": "openai API",
        "model": "gpt-5-nano-2025-08-07",
        "api_base": None,
        "api_key": None,  # read from OPENAI_API_KEY env var
        "provider": "openai",
        "supports_structured_output": True,
    },
    "gpt-oss-120b": {
        "backend": "llm polito API",
        "model": "gpt-oss-120b",
        "api_base": "https://llm.polito.it/v1",
        "api_key": None,  # read from LLM_POLITO_API_KEY env var via settings
        "provider": "llm_polito",
        "supports_structured_output": False,
    },
    "ollama-gpt-oss-120b": {
        "backend": "ollama host",
        "model": "gpt-oss:120b",
        "api_base": "http://localhost:11434/v1",
        "api_key": "ollama",  # required placeholder for the OpenAI-compat API
        "provider": "ollama",
        "supports_structured_output": False,
    },
    "ollama-gemma3-27b": {
        "backend": "ollama host",
        "model": "orieg/gemma3-tools:27b-it-qat",
        "api_base": "http://localhost:11434/v1",
        "api_key": "ollama",
        "provider": "ollama",
        "supports_structured_output": False,
    },
    "gpt-5.4": {
        "backend": "openai API",
        "model": "gpt-5.4-2026-03-05",
        "api_base": None,
        "api_key": None,  # read from OPENAI_API_KEY env var
        "provider": "openai",
        "supports_structured_output": True,
    },
    "ollama-deepseek-r1-8b": {
        "backend": "ollama host",
        "model": "MFDoom/deepseek-r1-tool-calling:8b",
        "api_base": "http://localhost:11434/v1",
        "api_key": "ollama",  # required placeholder for the OpenAI-compat API
        "provider": "ollama",
        "supports_structured_output": False,
    },
    "vllm-gemma3-27b": {
        "backend": "vllm host",
        "model": "google/gemma-3-27b-it",
        "api_base": "http://localhost:8000/v1",
        "api_key": "vllm",
        "provider": "vllm",
        "supports_structured_output": False,
    },
    "vllm-deepseek": {
        "backend": "vllm host",
        "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "api_base": "http://localhost:8001/v1",
        "api_key": "vllm",
        "provider": "vllm",
        "supports_structured_output": False,
    },
}

# Flat list of CLI-friendly keys, used for argparse choices.
MODEL_CHOICES: list[str] = list(MODEL_OPTIONS.keys())


def apply_model_config(settings_obj: object, model_key: str) -> None:
    """Apply a model configuration entry to the application settings instance.

    Mutates the provided settings object in-place so that downstream agents
    pick up the correct endpoint, key, and model name.

    Args:
        settings_obj: The application Settings instance (from app.core.config).
        model_key: One of the keys defined in MODEL_OPTIONS.

    Raises:
        ValueError: If model_key is not a recognized option.
    """
    if model_key not in MODEL_OPTIONS:
        raise ValueError(
            f"Unknown model key '{model_key}'. "
            f"Valid options: {MODEL_CHOICES}"
        )

    cfg: ModelConfig = MODEL_OPTIONS[model_key]

    settings_obj.OPENAI_MODEL_FAST = cfg["model"]
    settings_obj.OPENAI_MODEL_SMART = cfg["model"]
    settings_obj.OPENAI_API_BASE = cfg["api_base"]

    if cfg["api_key"] is not None:
        # Override only when the entry carries an explicit key (e.g. ollama placeholder).
        settings_obj.OPENAI_API_KEY = cfg["api_key"]
    elif cfg["provider"] == "llm_polito":
        # Delegate to the value already loaded from LLM_POLITO_API_KEY env var.
        settings_obj.OPENAI_API_KEY = settings_obj.LLM_POLITO_API_KEY
    else:
        # Restore the original OpenAI API key from environment variables.
        settings_obj.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
