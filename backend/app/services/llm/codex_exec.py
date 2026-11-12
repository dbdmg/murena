"""LangChain chat-model adapter backed by the authenticated Codex CLI."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field

from app.core.config import settings
from app.utils.json_parser import safe_extract_json

logger = logging.getLogger(__name__)


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content)


def _format_messages(messages: Sequence[BaseMessage]) -> str:
    formatted = []
    for message in messages:
        if isinstance(message, SystemMessage):
            role = "SYSTEM"
        elif isinstance(message, HumanMessage):
            role = "USER"
        elif isinstance(message, AIMessage):
            role = "ASSISTANT"
        else:
            role = getattr(message, "type", "MESSAGE").upper()
        formatted.append(f"[{role}]\n{_message_text(message.content)}")
    return "\n\n".join(formatted)


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize Pydantic's JSON Schema to the strict schema Codex accepts."""
    normalized = deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["additionalProperties"] = False
                # Strict structured output requires every declared property.
                # Optional Pydantic values remain nullable in their own schema.
                node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(normalized)
    return normalized


def _has_open_object_map(node: Any) -> bool:
    """Strict JSON Schema cannot represent Pydantic's arbitrary-key dicts."""
    if isinstance(node, dict):
        additional = node.get("additionalProperties")
        if additional is True or isinstance(additional, dict):
            return True
        return any(_has_open_object_map(value) for value in node.values())
    if isinstance(node, list):
        return any(_has_open_object_map(value) for value in node)
    return False


class CodexExecChatModel(BaseChatModel):
    """Use ``codex exec`` as a drop-in, centrally configured LangChain model.

    Codex is launched with no shell, web, app, or multi-agent tools. Structured
    outputs use the CLI's JSON Schema constrained final response.
    """

    model_name: str
    temperature: float = 0.0
    reasoning_effort: str = Field(default_factory=lambda: settings.CODEX_REASONING_EFFORT)
    executable: str = Field(default_factory=lambda: settings.CODEX_EXECUTABLE)
    timeout_seconds: int = Field(default_factory=lambda: settings.CODEX_TIMEOUT_SECONDS)

    @property
    def _llm_type(self) -> str:
        return "codex_exec"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {
            "model_name": self.model_name,
            "reasoning_effort": self.reasoning_effort,
        }

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self._run_codex(_format_messages(messages))
        if stop:
            for stop_token in stop:
                if stop_token and stop_token in response:
                    response = response.split(stop_token, 1)[0]
                    break
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=response))])

    def with_structured_output(
        self,
        schema: type | dict[str, Any],
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable:
        """Return a runnable that validates a schema-constrained JSON reply."""
        if isinstance(schema, dict):
            source_schema = schema
            model_schema = None
        elif isinstance(schema, type) and issubclass(schema, BaseModel):
            source_schema = schema.model_json_schema()
            model_schema = schema
        else:
            raise TypeError("Codex structured output requires a JSON Schema or Pydantic model")
        use_strict_schema = not _has_open_object_map(source_schema)
        json_schema = _strict_schema(source_schema)

        def invoke_structured(value: Any) -> Any:
            if hasattr(value, "to_messages"):
                messages = value.to_messages()
            elif isinstance(value, BaseMessage):
                messages = [value]
            elif isinstance(value, (list, tuple)) and all(
                isinstance(item, BaseMessage) for item in value
            ):
                messages = list(value)
            else:
                messages = [HumanMessage(content=str(value))]

            prompt = _format_messages(messages)
            if not use_strict_schema:
                prompt += (
                    "\n\nReturn only a JSON value that validates against this JSON Schema. "
                    "Preserve arbitrary object keys wherever the schema allows them.\n"
                    + json.dumps(source_schema, ensure_ascii=False)
                )
            raw_text = self._run_codex(
                prompt,
                output_schema=json_schema if use_strict_schema else None,
            )
            try:
                parsed_json = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed_json = safe_extract_json(raw_text)
            if parsed_json is None:
                raise ValueError("Codex returned invalid JSON for structured output")
            parsed = model_schema.model_validate(parsed_json) if model_schema else parsed_json
            if include_raw:
                return {
                    "raw": AIMessage(content=raw_text),
                    "parsed": parsed,
                    "parsing_error": None,
                }
            return parsed

        return RunnableLambda(invoke_structured)

    def _run_codex(
        self, prompt: str, *, output_schema: dict[str, Any] | None = None
    ) -> str:
        executable = shutil.which(self.executable)
        if not executable:
            raise RuntimeError("Codex CLI executable was not found")

        # Keep the process in an empty temporary workspace and omit API keys and
        # application secrets from its environment. Codex auth is read from HOME.
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {
                "HOME", "PATH", "CODEX_HOME", "LANG", "LC_ALL", "TMPDIR",
                "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
            }
        }
        with tempfile.TemporaryDirectory(prefix="murena-codex-") as workdir:
            command = [
                executable,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--cd", workdir,
                "--sandbox", "read-only",
                "--disable", "shell_tool",
                "--disable", "multi_agent",
                "--disable", "apps",
                "--config", 'web_search="disabled"',
                "--config", "agents.enabled=false",
                "--config", 'approval_policy="never"',
                "--model", self.model_name,
                "--config", f'model_reasoning_effort="{self.reasoning_effort}"',
                "--json",
            ]
            if output_schema is not None:
                schema_path = Path(workdir) / "output-schema.json"
                schema_path.write_text(
                    json.dumps(output_schema, ensure_ascii=False), encoding="utf-8"
                )
                command.extend(["--output-schema", str(schema_path)])
            command.append("-")

            try:
                result = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=self.timeout_seconds,
                    cwd=workdir,
                    env=env,
                )
            except subprocess.TimeoutExpired as exc:
                logger.warning("Codex CLI LLM call timed out")
                raise RuntimeError("Codex CLI LLM call timed out") from exc

        if result.returncode != 0:
            logger.error("Codex CLI LLM call failed (exit=%s)", result.returncode)
            raise RuntimeError("Codex CLI LLM call failed")

        final_text = None
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except (TypeError, json.JSONDecodeError):
                continue
            item = event.get("item")
            if (
                event.get("type") == "item.completed"
                and isinstance(item, dict)
                and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)
            ):
                final_text = item["text"]
        if final_text is None:
            logger.error("Codex CLI returned no final agent message")
            raise RuntimeError("Codex CLI returned no LLM response")
        return final_text
