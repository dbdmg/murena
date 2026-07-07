from functools import lru_cache
import os
from typing import Optional

from dotenv import load_dotenv

from app.core.config import settings

load_dotenv()

# Global Langfuse client instance
_langfuse_client = None


@lru_cache(maxsize=16)
def _get_llm_internal(
    provider: str,
    model_name: str,
    temperature: float,
    base_url: Optional[str],
    api_key: Optional[str] = None,
):
    """Internal cached model factory to ensure unified instances."""
    from app.services.llm.providers import build_chat_model

    # Institutional gateway keeps its dedicated key (backward compatibility).
    if not api_key and base_url and "institutional-endpoint.edu" in base_url:
        api_key = (
            settings.INSTITUTIONAL_LLM_API_KEY
            or os.getenv("INSTITUTIONAL_LLM_API_KEY")
            or settings.OPENAI_API_KEY
        )

    return build_chat_model(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        base_url=base_url,
        api_key=api_key,
    )


def get_llm(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
):
    """Return a LangChain chat-model instance (cached).

    Provider selection is configuration-driven: set ``LLM_PROVIDER`` in
    backend/.env (openai | gemini | anthropic | grok | ollama |
    openai-compatible) or let it be inferred from the model name.

    Args:
        model_name: explicit model override (e.g. 'gpt-4o', 'claude-sonnet-5',
            'gemini-2.5-pro', 'grok-4', 'gemma3:27b').
        temperature: model temperature (default: settings.AGENT_TEMPERATURE).
        api_base: base-URL override (e.g. a vLLM/LM Studio/Ollama server).
        api_key: API-key override.
        provider: explicit provider override (see LLM_PROVIDER).
    """
    from app.services.llm.providers import resolve_provider

    resolved_model = model_name or settings.LLM_MODEL or os.getenv("LLM_MODEL_DEFAULT")

    # Temperature resolution: explicit arg > env > settings default.
    if temperature is not None:
        resolved_temperature = float(temperature)
    else:
        try:
            env_temp = os.getenv("LLM_TEMPERATURE")
            resolved_temperature = (
                float(env_temp) if env_temp is not None
                else float(settings.AGENT_TEMPERATURE)
            )
        except ValueError:
            resolved_temperature = 0.0

    resolved_base = api_base or settings.LLM_BASE_URL or settings.OPENAI_API_BASE
    resolved_provider = resolve_provider(resolved_model, resolved_base, explicit=provider)

    return _get_llm_internal(
        provider=resolved_provider,
        model_name=resolved_model,
        temperature=resolved_temperature,
        base_url=resolved_base,
        api_key=api_key,
    )


def is_oss_model(model_name: Optional[str] = None) -> bool:
    """Return True when the active model does not reliably support structured output.

    Resolution order:
    1. Look up the model by name in MODEL_OPTIONS (authoritative, explicit).
    2. Fall back to heuristic substring matching for models not registered there.

    Args:
        model_name: Override the model name to check. If None, the current
            settings.LLM_MODEL is used.

    Returns:
        True if the model should use plain text output instead of
        function_calling / json_mode structured output.
    """
    try:
        from tests.model_config import MODEL_OPTIONS
        resolved = model_name or settings.LLM_MODEL
        for cfg in MODEL_OPTIONS.values():
            if cfg["model"] == resolved:
                return not cfg["supports_structured_output"]
    except ImportError:
        pass

    # Provider-based check: managed APIs support structured output reliably.
    from app.services.llm.providers import resolve_provider, supports_structured_output
    resolved = (model_name or settings.LLM_MODEL or "").lower()
    api_base = (settings.LLM_BASE_URL or settings.OPENAI_API_BASE or "").lower()
    try:
        provider = resolve_provider(resolved, api_base or None)
        if supports_structured_output(provider):
            return False
    except RuntimeError:
        pass

    # Fallback: heuristic based on model name and endpoint URL.
    return (
        "oss" in resolved
        or "llama" in resolved
        or "qwen" in resolved
        or "gemma" in resolved
        or "deepseek" in resolved
        or "mistral" in resolved
        or "ollama" in api_base
        or "institutional" in api_base
        or "localhost" in api_base
    )

def get_langfuse_callback(session_id: Optional[str] = None, user_id: Optional[str] = None, tags: Optional[list] = None, trace_name: Optional[str] = None):
    """Restituisce il callback handler per Langfuse se configurato.
    
    Args:
        session_id: ID sessione per raggruppare le trace (default: da LANGFUSE_SESSION_ID env var)
        user_id: ID utente (default: da LANGFUSE_USER_ID env var)
        tags: Tag per categorizzare le trace (default: da LANGFUSE_TAGS env var, comma-separated)
        trace_name: Nome della trace
    """
    try:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        
        if not public_key or not secret_key:
            return None
        
        try:
            from langfuse.langchain import CallbackHandler
            from langfuse.types import TraceContext
        except ImportError:
            return None
        
        # Leggi da env vars se non specificato
        if not session_id:
            session_id = os.getenv("LANGFUSE_SESSION_ID", "").strip() or None
        if not user_id:
            user_id = os.getenv("LANGFUSE_USER_ID", "").strip() or None
        if not tags:
            tags_str = os.getenv("LANGFUSE_TAGS", "").strip()
            if tags_str:
                tags = [t.strip() for t in tags_str.split(",")]
        if not trace_name:
            trace_name = os.getenv("LANGFUSE_TRACE_NAME", "").strip() or None
        
        # Crea TraceContext se ci sono parametri da passare
        trace_context = None
        if session_id or user_id or tags or trace_name:
            trace_context_dict = {}
            if session_id:
                trace_context_dict['session_id'] = session_id
            if user_id:
                trace_context_dict['user_id'] = user_id
            if tags:
                trace_context_dict['tags'] = tags
            if trace_name:
                trace_context_dict['name'] = trace_name
            
            trace_context = TraceContext(**trace_context_dict)
        
        # Le credenziali vengono lette automaticamente dalle variabili d'ambiente
        # LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
        return CallbackHandler(trace_context=trace_context)
    except Exception as e:
        print(f"Langfuse callback error (tracing disabled): {e}")
        import traceback
        traceback.print_exc()
    return None


def invoke_with_langfuse(chain, inputs, session_id=None, user_id=None, tags=None, trace_name=None, **kwargs):
    """Invoca una chain LangChain con callback Langfuse se configurato.
    
    Args:
        chain: LangChain chain da invocare
        inputs: Input per la chain
        session_id: ID sessione per raggruppare le trace
        user_id: ID utente
        tags: Tag per categorizzare le trace
        trace_name: Nome della trace
        **kwargs: Altri argomenti per chain.invoke()
    """
    callback = get_langfuse_callback(session_id=session_id, user_id=user_id, tags=tags, trace_name=trace_name)
    if callback:
        callbacks = kwargs.get('callbacks', [])
        if isinstance(callbacks, list):
            callbacks.append(callback)
        else:
            callbacks = [callback]
        kwargs['callbacks'] = callbacks
    
    return chain.invoke(inputs, **kwargs)

def get_langfuse_client():
    """Restituisce il client Langfuse singleton se configurato."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
        
    try:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
        
        if not public_key or not secret_key:
            missing = []
            if not public_key:
                missing.append("LANGFUSE_PUBLIC_KEY")
            if not secret_key:
                missing.append("LANGFUSE_SECRET_KEY")
            print(f"Langfuse tracing disabled: missing environment variables: {', '.join(missing)}")
            return None
        
        try:
            from langfuse import Langfuse
        except ImportError:
            print("Langfuse tracing disabled: 'langfuse' package not installed. Install with: pip install langfuse")
            return None
            
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            flush_at=0,  # Invia immediatamente ogni evento singolo
            flush_interval=0.1  # Verifica ogni 0.1 secondi
        )
        print(f" Langfuse client initialized successfully (host: {host})")
        return _langfuse_client
        
    except Exception as e:
        print(f"Langfuse client initialization error: {e}")
        import traceback
        traceback.print_exc()
    return None

def flush_langfuse():
    """Forza il flush di tutti i dati pendenti su Langfuse."""
    client = get_langfuse_client()
    if client:
        try:
            print(" Flushing Langfuse data...")
            client.flush()
            print(" Langfuse data flushed successfully")
        except Exception as e:
            print(f"Error flushing Langfuse data: {e}")
            import traceback
            traceback.print_exc()
