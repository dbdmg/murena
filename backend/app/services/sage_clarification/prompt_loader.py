"""Load named prompt templates from the adjacent Markdown prompt catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any


_PROMPT_FILE = Path(__file__).with_name("prompts.md")


def _prompt_catalog() -> str:
    # Read on each render so editing the Markdown prompt takes effect without
    # restarting the application process.
    return _PROMPT_FILE.read_text(encoding="utf-8")


def render_prompt(name: str, **values: Any) -> str:
    """Render a prompt section, requiring every template placeholder to be supplied."""
    catalog = _prompt_catalog()
    start_marker = f"<!-- prompt:{name} -->"
    end_marker = f"<!-- /prompt:{name} -->"
    start = catalog.find(start_marker)
    if start < 0:
        raise KeyError(f"Prompt '{name}' is not defined in {_PROMPT_FILE.name}")
    start += len(start_marker)
    end = catalog.find(end_marker, start)
    if end < 0:
        raise KeyError(f"Prompt '{name}' has no closing marker in {_PROMPT_FILE.name}")

    prompt = catalog[start:end].strip()
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))
    unresolved = []
    search_from = 0
    while True:
        placeholder_start = prompt.find("{{", search_from)
        if placeholder_start < 0:
            break
        placeholder_end = prompt.find("}}", placeholder_start + 2)
        if placeholder_end < 0:
            unresolved.append(prompt[placeholder_start + 2:].strip())
            break
        unresolved.append(prompt[placeholder_start + 2:placeholder_end].strip())
        search_from = placeholder_end + 2
    if unresolved:
        raise ValueError(f"Prompt '{name}' has unresolved placeholders: {', '.join(unresolved)}")
    return prompt
