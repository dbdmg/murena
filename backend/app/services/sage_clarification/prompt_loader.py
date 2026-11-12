"""Load named prompt templates from the adjacent Markdown prompt catalog."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_PROMPT_FILE = Path(__file__).with_name("prompts.md")


def _prompt_catalog() -> str:
    # Read on each render so editing the Markdown prompt takes effect without
    # restarting the application process.
    return _PROMPT_FILE.read_text(encoding="utf-8")


def render_prompt(name: str, **values: Any) -> str:
    """Render a prompt section, requiring every template placeholder to be supplied."""
    marker = re.compile(
        rf"<!--\s*prompt:{re.escape(name)}\s*-->(.*?)<!--\s*/prompt:{re.escape(name)}\s*-->",
        re.DOTALL,
    )
    match = marker.search(_prompt_catalog())
    if not match:
        raise KeyError(f"Prompt '{name}' is not defined in {_PROMPT_FILE.name}")

    prompt = match.group(1).strip()
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))
    unresolved = re.findall(r"{{([A-Z_]+)}}", prompt)
    if unresolved:
        raise ValueError(f"Prompt '{name}' has unresolved placeholders: {', '.join(unresolved)}")
    return prompt
