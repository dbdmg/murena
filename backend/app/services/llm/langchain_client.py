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

    resolved_temperature = temperature if temperature is not None else default_temperature

    # --- LOGICA DI SWITCHING MODELLO ---
    # Se il modello inizia con "gpt-" o "o1-", usiamo OpenAI
    if resolved_model.startswith("gpt-") or resolved_model.startswith("o1-"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY non configurata per utilizzare modelli OpenAI.")

        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOpenAI
            except ImportError as e:
                raise RuntimeError(
                    "Manca il pacchetto 'langchain-openai'. Installalo con pip install langchain-openai"
                ) from e

        return ChatOpenAI(model=resolved_model, api_key=api_key, temperature=resolved_temperature)

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
