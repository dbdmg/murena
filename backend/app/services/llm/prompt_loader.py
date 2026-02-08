"""Utility per caricare i prompt dagli override esterni."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import shutil
from typing import Dict, List

CONFIG_PATH = Path(__file__).with_name("prompt_config.md")
DEFAULT_CONFIG_PATH = Path(__file__).with_name("prompt_config.default.md")
SECTION_PATTERN = re.compile(r"^##\s+([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*$")


def _clean_block(lines: list[str]) -> str:
    """Rimuove righe vuote iniziali/finali e restituisce il blocco come stringa."""
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _load_overrides() -> Dict[str, Dict[str, str]]:
    if not CONFIG_PATH.exists():
        return {}

    text = CONFIG_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    overrides: Dict[str, Dict[str, str]] = {}
    i = 0
    total = len(lines)

    while i < total:
        match = SECTION_PATTERN.match(lines[i].strip())
        if not match:
            i += 1
            continue

        agent, key = match.groups()
        i += 1

        # salta eventuali righe vuote tra header e blocco
        while i < total and not lines[i].strip():
            i += 1

        if i >= total or not lines[i].strip().startswith("```"):
            continue

        fence = lines[i].strip()
        # Normalize fence - the closing fence can be just ``` even if opening was ```prompt
        fence_close = "```" if fence.startswith("```") else fence
        i += 1
        block: list[str] = []
        while i < total and not lines[i].strip().startswith(fence_close):
            block.append(lines[i])
            i += 1

        if i < total and lines[i].strip().startswith(fence_close):
            i += 1

        overrides.setdefault(agent, {})[key] = _clean_block(block)

    return overrides


def get_prompt_template(agent: str, key: str = "template", default: str = "") -> str:
    """Restituisce il prompt per l'agente, con fallback al default."""
    overrides = _load_overrides()
    agent_prompts = overrides.get(agent)
    if agent_prompts is None:
        return default
    return agent_prompts.get(key, default)


def get_system_prompt(agent: str, default: str = "", *, key: str = "system") -> str:
    """Restituisce il system prompt per l'agente.

    Args:
        agent: Nome dell'agente (es. 'sql_agent')
        default: Valore di fallback se il prompt non esiste
        key: Chiave del prompt (default 'system', può essere 'retry_system' ecc.)
    """
    return get_prompt_template(agent, key, default)


def get_user_template(agent: str, default: str = "", *, key: str = "user") -> str:
    """Restituisce lo user template per l'agente.

    Args:
        agent: Nome dell'agente (es. 'sql_agent')
        default: Valore di fallback se il prompt non esiste
        key: Chiave del prompt (default 'user', può essere 'retry_user' ecc.)
    """
    return get_prompt_template(agent, key, default)


def get_agent_prompts(agent: str) -> dict[str, str]:
    """Restituisce tutti i prompt (system, user, ecc.) per un agente."""
    overrides = _load_overrides()
    return overrides.get(agent, {})


def reload_prompt_cache() -> None:
    """Svuota la cache per ricaricare i prompt dal file."""
    _load_overrides.cache_clear()


def update_prompt_template(agent: str, key: str, new_text: str) -> None:
    """Aggiorna (o crea) il template indicato all'interno del file markdown."""
    agent = (agent or "").strip()
    key = (key or "").strip()
    if not agent or not key:
        raise ValueError("Agent e key devono essere specificati.")

    sanitized = (new_text or "").splitlines()
    config_exists = CONFIG_PATH.exists()
    if not config_exists:
        raise FileNotFoundError(f"Prompt config non trovato: {CONFIG_PATH}")

    lines: List[str] = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    header = f"## {agent}.{key}"
    header_idx = next(
        (i for i, line in enumerate(lines) if line.strip() == header), None
    )
    fence_default = "```prompt"

    if header_idx is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(header)
        lines.append(fence_default)
        lines.extend(sanitized)
        lines.append(fence_default)
        lines.append("")
    else:
        i = header_idx + 1
        while i < len(lines) and not lines[i].strip().startswith("```"):
            i += 1
        if i >= len(lines):
            raise ValueError(f"Blocco codice mancante per {header}.")

        fence_line = lines[i].strip() or fence_default
        start_block = i + 1
        end_block = start_block
        while end_block < len(lines) and lines[end_block].strip() != fence_line:
            end_block += 1
        if end_block >= len(lines):
            raise ValueError(f"Blocco codice non terminato per {header}.")

        lines = lines[:start_block] + sanitized + lines[end_block:]

    CONFIG_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    reload_prompt_cache()


def reset_to_defaults(agent: str | None = None) -> dict[str, str]:
    """Ripristina i prompt ai valori di default.

    Args:
        agent: Se specificato, resetta solo i prompt di quell'agente.
               Se None, resetta tutto il file.

    Returns:
        Dict con info sul reset effettuato.

    Raises:
        FileNotFoundError: Se il file di default non esiste.
    """
    if not DEFAULT_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"File di default non trovato: {DEFAULT_CONFIG_PATH}. "
            "Impossibile ripristinare i prompt."
        )

    if agent is None:
        # Reset completo: copia il file default sul config attivo
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
        reload_prompt_cache()
        return {
            "status": "ok",
            "reset": "all",
            "message": "Tutti i prompt ripristinati ai valori di default.",
        }

    # Reset singolo agente: leggi i default e sovrascrivi solo le sezioni dell'agente
    default_overrides = _load_defaults()
    agent_defaults = default_overrides.get(agent)

    if not agent_defaults:
        raise ValueError(f"Nessun default trovato per l'agente: {agent}")

    # Aggiorna ogni chiave dell'agente
    for key, text in agent_defaults.items():
        update_prompt_template(agent=agent, key=key, new_text=text)

    reload_prompt_cache()
    return {
        "status": "ok",
        "reset": "agent",
        "agent": agent,
        "keys": list(agent_defaults.keys()),
        "message": f"Prompt dell'agente '{agent}' ripristinati ai valori di default.",
    }


def _load_defaults() -> Dict[str, Dict[str, str]]:
    """Carica i prompt di default dal file backup (non usa cache)."""
    if not DEFAULT_CONFIG_PATH.exists():
        return {}

    text = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    overrides: Dict[str, Dict[str, str]] = {}
    i = 0
    total = len(lines)

    while i < total:
        match = SECTION_PATTERN.match(lines[i].strip())
        if not match:
            i += 1
            continue

        agent, key = match.groups()
        i += 1

        while i < total and not lines[i].strip():
            i += 1

        if i >= total or not lines[i].strip().startswith("```"):
            continue

        fence = lines[i].strip()
        fence_close = "```" if fence.startswith("```") else fence
        i += 1
        block: list[str] = []
        while i < total and not lines[i].strip().startswith(fence_close):
            block.append(lines[i])
            i += 1

        if i < total and lines[i].strip().startswith(fence_close):
            i += 1

        overrides.setdefault(agent, {})[key] = _clean_block(block)

    return overrides


def get_available_agents() -> list[str]:
    """Restituisce la lista degli agenti disponibili."""
    overrides = _load_overrides()
    return sorted(overrides.keys())
