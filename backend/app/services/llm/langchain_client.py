from functools import lru_cache
import os
from typing import Optional

from dotenv import load_dotenv

from app.core.config import settings

# Usa il modello OpenAI fast come default (configurabile via DEFAULT_LLM_PROVIDER)
if settings.DEFAULT_LLM_PROVIDER == "openai":
    DEFAULT_MODEL = settings.OPENAI_MODEL_FAST
else:
    DEFAULT_MODEL = settings.GEMINI_MODEL_FAST

load_dotenv()

# Global Langfuse client instance
_langfuse_client = None


@lru_cache(maxsize=8)
def get_llm(model_name: Optional[str] = None, temperature: Optional[float] = None):
    """Restituisce un'istanza Chat LLM (Gemini) tramite LangChain.

    Env vars:
    - GEMINI_KEY: API key Google Generative AI
    - GEMINI_MODEL_FAST / LLM_MODEL_DEFAULT: nome modello di default
    - LLM_TEMPERATURE: float opzionale (default: 0.0)

    Args:
        model_name: override esplicito del modello da usare.
        temperature: override della temperatura del modello.
    """
    resolved_model = model_name or os.getenv("LLM_MODEL_DEFAULT", DEFAULT_MODEL)

    try:
        default_temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    except ValueError:
        default_temperature = 0.0

    resolved_temperature = (
        temperature if temperature is not None else default_temperature
    )

    # --- LOGICA DI SWITCHING MODELLO ---
    # 1. Se il modello richiesto è gpt-oss-120b, usiamo l'istanza locale Hugging Face
    if resolved_model == "gpt-oss-120b":
        from app.services.llm.oss_client import ChatOSS
        # Nota: gpt-oss-120b è la versione open-weight di OpenAI caricabile via HF
        return ChatOSS(
            model_id="openai/gpt-oss-120b",
            temperature=resolved_temperature,
            device=settings.OSS_DEVICE,
            max_tokens=settings.OSS_MAX_TOKENS
        )

    # 2. Se il modello inizia con "gpt-" o "o1-", usiamo OpenAI (via API o server compatibile)
    if resolved_model.startswith("gpt-") or resolved_model.startswith("o1-"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key and not settings.OPENAI_API_BASE:
            raise RuntimeError(
                "OPENAI_API_KEY non configurata per utilizzare modelli OpenAI."
            )

        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOpenAI
            except ImportError as e:
                raise RuntimeError(
                    "Manca il pacchetto 'langchain-openai'. Installalo con pip install langchain-openai"
                ) from e

        return ChatOpenAI(
            model=resolved_model, 
            api_key=api_key or "sk-dummy", # Fallback for local servers without auth
            temperature=resolved_temperature,
            base_url=settings.OPENAI_API_BASE
        )

    # --- DEFAULT: GEMINI ---
    api_key = os.getenv("GEMINI_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_KEY non configurata nelle variabili d'ambiente.")

    # Import lazily per evitare hard dependency all'avvio
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except Exception as e:
        raise RuntimeError(
            "Manca il pacchetto 'langchain-google-genai'. Aggiungilo a requirements.txt"
        ) from e

    return ChatGoogleGenerativeAI(
        model=resolved_model,
        api_key=api_key,
        temperature=resolved_temperature,
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
        print(f"✓ Langfuse client initialized successfully (host: {host})")
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
            print("🔄 Flushing Langfuse data...")
            client.flush()
            print("✓ Langfuse data flushed successfully")
        except Exception as e:
            print(f"Error flushing Langfuse data: {e}")
            import traceback
            traceback.print_exc()
