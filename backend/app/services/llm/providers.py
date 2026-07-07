"""LLM provider registry.

Single place where chat-model instances are built. Every agent obtains its
model through ``langchain_client.get_llm``, which delegates here, so switching
provider is a pure configuration change (no code changes anywhere else).

Supported providers (``LLM_PROVIDER`` env var / settings):

===================  ==========================================================
``openai``           Official OpenAI API (ChatGPT / gpt-* models).
``gemini``           Google Gemini via ``langchain-google-genai``.
``anthropic``        Anthropic Claude via ``langchain-anthropic``
                     (alias: ``claude``).
``grok``             xAI Grok via its OpenAI-compatible API (alias: ``xai``).
``ollama``           Local Ollama server (open-weight models on premises).
``openai-compatible``Any OpenAI-compatible endpoint: vLLM, LM Studio,
                     llama.cpp server, TGI, institutional gateways...
                     Used for on-premises open-weight models such as Gemma,
                     gpt-oss or Qwen (alias: ``vllm``, ``local``).
===================  ==========================================================

If ``LLM_PROVIDER`` is not set the provider is inferred from the model name
(``claude-*`` -> anthropic, ``gemini-*`` -> gemini, ``grok-*`` -> grok,
``gpt-*`` -> openai) and finally from the presence of a custom base URL
(-> openai-compatible).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.utils.logger import logger

PROVIDER_ALIASES = {
    "claude": "anthropic",
    "xai": "grok",
    "vllm": "openai-compatible",
    "local": "openai-compatible",
    "lmstudio": "openai-compatible",
    "institutional": "openai-compatible",
    "google": "gemini",
    "chatgpt": "openai",
}

KNOWN_PROVIDERS = (
    "openai",
    "gemini",
    "anthropic",
    "grok",
    "ollama",
    "openai-compatible",
)

# Providers whose chat models reliably support structured output
# (function calling). Open-weight models served locally usually do not.
STRUCTURED_OUTPUT_PROVIDERS = {"openai", "gemini", "anthropic", "grok"}


def _missing_dep(provider: str, package: str, exc: Exception) -> RuntimeError:
    return RuntimeError(
        f"Provider '{provider}' requires the '{package}' package. "
        f"Install it with: uv pip install {package}  (or: pip install {package}). "
        f"Original error: {exc}"
    )


def _missing_key(provider: str, env_var: str) -> RuntimeError:
    return RuntimeError(
        f"Provider '{provider}' is selected but {env_var} is not configured. "
        f"Set it in backend/.env."
    )


def normalize_provider(provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    p = provider.strip().lower()
    p = PROVIDER_ALIASES.get(p, p)
    if p not in KNOWN_PROVIDERS:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Valid values: {', '.join(KNOWN_PROVIDERS)} "
            f"(aliases: {', '.join(sorted(PROVIDER_ALIASES))})."
        )
    return p


def infer_provider(model_name: str, base_url: Optional[str]) -> str:
    """Best-effort provider inference when LLM_PROVIDER is not set."""
    name = (model_name or "").lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gemini"):
        return "gemini"
    if name.startswith("grok"):
        return "grok"
    if base_url:
        if "ollama" in base_url or ":11434" in base_url:
            return "ollama"
        return "openai-compatible"
    if name.startswith("gpt-") or name.startswith("o1") or name.startswith("o3"):
        return "openai"
    # Open-weight names (gemma, qwen, llama, gpt-oss...) without a base URL:
    # assume a local OpenAI-compatible server is intended.
    return "openai-compatible"


def resolve_provider(model_name: str, base_url: Optional[str],
                     explicit: Optional[str] = None) -> str:
    from app.core.config import settings

    provider = normalize_provider(
        explicit
        or getattr(settings, "LLM_PROVIDER", None)
        or os.getenv("LLM_PROVIDER")
    )
    if provider:
        return provider
    return infer_provider(model_name, base_url)


def build_chat_model(
    provider: str,
    model_name: str,
    temperature: float,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Any:
    """Instantiate a LangChain chat model for the given provider."""
    from app.core.config import settings

    provider = normalize_provider(provider) or "openai-compatible"
    logger.info(
        f"[LLM] provider={provider} model={model_name} "
        f"base_url={base_url or 'default'}"
    )

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise _missing_dep(provider, "langchain-openai", e)
        key = api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not key:
            raise _missing_key(provider, "OPENAI_API_KEY")
        return ChatOpenAI(model=model_name, api_key=key, temperature=temperature)

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            raise _missing_dep(provider, "langchain-google-genai", e)
        key = (
            api_key
            or settings.GEMINI_API_KEY
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not key:
            raise _missing_key(provider, "GEMINI_API_KEY")
        return ChatGoogleGenerativeAI(
            model=model_name, google_api_key=key, temperature=temperature
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as e:
            raise _missing_dep(provider, "langchain-anthropic", e)
        key = (
            api_key
            or settings.ANTHROPIC_API_KEY
            or os.getenv("ANTHROPIC_API_KEY")
        )
        if not key:
            raise _missing_key(provider, "ANTHROPIC_API_KEY")
        return ChatAnthropic(model=model_name, api_key=key, temperature=temperature)

    if provider == "grok":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise _missing_dep(provider, "langchain-openai", e)
        key = api_key or settings.XAI_API_KEY or os.getenv("XAI_API_KEY")
        if not key:
            raise _missing_key(provider, "XAI_API_KEY")
        return ChatOpenAI(
            model=model_name,
            api_key=key,
            temperature=temperature,
            base_url=base_url or "https://api.x.ai/v1",
        )

    if provider == "ollama":
        resolved_base = (
            base_url
            or settings.OLLAMA_BASE_URL
            or os.getenv("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model_name, base_url=resolved_base, temperature=temperature
            )
        except ImportError:
            # Graceful fallback: Ollama also exposes an OpenAI-compatible API.
            logger.warning(
                "[LLM] langchain-ollama not installed; using the OpenAI-compatible "
                "endpoint of the Ollama server instead."
            )
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                api_key=api_key or "ollama",
                temperature=temperature,
                base_url=resolved_base.rstrip("/") + "/v1",
            )

    # openai-compatible (vLLM, LM Studio, llama.cpp, institutional gateways...)
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise _missing_dep(provider, "langchain-openai", e)

    if not base_url:
        raise RuntimeError(
            "Provider 'openai-compatible' requires LLM_BASE_URL (or "
            "OPENAI_API_BASE) pointing to the local/remote server, e.g. "
            "http://localhost:8000/v1 for vLLM."
        )

    kwargs: Dict[str, Any] = dict(
        model=model_name,
        api_key=api_key or "sk-local",  # local servers usually ignore the key
        temperature=temperature,
        base_url=base_url,
    )
    # Some local runtimes (vLLM serving Qwen etc.) accept this extra flag to
    # disable "thinking" blocks; official endpoints would reject it.
    lower_base = base_url.lower()
    if any(tok in lower_base for tok in ("localhost", "127.0.0.1", "institutional")):
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    return ChatOpenAI(**kwargs)


def supports_structured_output(provider: str) -> bool:
    return normalize_provider(provider) in STRUCTURED_OUTPUT_PROVIDERS
