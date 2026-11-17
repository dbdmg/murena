"""LangChain chat-model adapter backed by the authenticated Claude Code CLI.

Each call runs ``claude -p`` (print mode) in an empty temporary directory with
no built-in tools, no MCP servers, no user/project/local settings, and no
session persistence, so the CLI behaves as a plain text/JSON model endpoint.
System messages become the CLI system prompt (replacing Claude Code's default
agentic prompt); the remaining conversation is sent on stdin. Structured
output uses the CLI's ``--json-schema`` validation and reads
``structured_output`` from the JSON result.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.llm.codex_exec import _format_messages, _message_text
from app.utils.json_parser import safe_extract_json

logger = logging.getLogger(__name__)

# Only non-secret variables needed to locate the CLI and its login. API keys
# (e.g. ANTHROPIC_API_KEY) are deliberately excluded so the CLI uses its own
# authenticated session rather than switching billing mode, and variables of
# an enclosing Claude Code session are not inherited.
_CLAUDE_ENV_ALLOWLIST = {
    "HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "CLAUDE_CONFIG_DIR",
}
_CLAUDE_WINDOWS_ENV = {
    "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATHEXT",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "TEMP", "TMP",
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are a component of a data-analysis pipeline. Follow the user's "
    "instructions exactly and reply only with the requested content."
)


def _split_messages(messages: Sequence[BaseMessage]) -> tuple[str, str]:
    """Return (system prompt, conversation text for stdin)."""
    system_parts = [
        _message_text(m.content) for m in messages if isinstance(m, SystemMessage)
    ]
    rest = [m for m in messages if not isinstance(m, SystemMessage)]
    system_prompt = "\n\n".join(p for p in system_parts if p.strip()) or _DEFAULT_SYSTEM_PROMPT
    if len(rest) == 1 and isinstance(rest[0], HumanMessage):
        conversation = _message_text(rest[0].content)
    else:
        conversation = _format_messages(rest)
    return system_prompt, conversation


def _to_messages(value: Any) -> list[BaseMessage]:
    if hasattr(value, "to_messages"):
        return value.to_messages()
    if isinstance(value, BaseMessage):
        return [value]
    if isinstance(value, (list, tuple)) and all(isinstance(i, BaseMessage) for i in value):
        return list(value)
    return [HumanMessage(content=str(value))]


class ClaudeCliChatModel(BaseChatModel):
    """Use ``claude -p`` as a drop-in, centrally configured LangChain model."""

    model_name: str
    temperature: float = 0.0
    effort: str = Field(default_factory=lambda: settings.CLAUDE_CLI_EFFORT)
    executable: str = Field(default_factory=lambda: settings.CLAUDE_CLI_EXECUTABLE)
    timeout_seconds: int = Field(default_factory=lambda: settings.CLAUDE_CLI_TIMEOUT_SECONDS)

    @property
    def _llm_type(self) -> str:
        return "claude_cli"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {"model_name": self.model_name, "effort": self.effort}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        system_prompt, conversation = _split_messages(messages)
        response, _ = self._run_claude(system_prompt, conversation)
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
            json_schema, model_schema = schema, None
        elif isinstance(schema, type) and issubclass(schema, BaseModel):
            json_schema, model_schema = schema.model_json_schema(), schema
        else:
            raise TypeError("Claude CLI structured output requires a JSON Schema or Pydantic model")

        def invoke_structured(value: Any) -> Any:
            system_prompt, conversation = _split_messages(_to_messages(value))
            raw_text, structured = self._run_claude(
                system_prompt, conversation, json_schema=json_schema
            )
            parsed_json = structured
            if parsed_json is None:
                try:
                    parsed_json = json.loads(raw_text)
                except json.JSONDecodeError:
                    parsed_json = safe_extract_json(raw_text)
            if parsed_json is None:
                raise ValueError("Claude CLI returned invalid JSON for structured output")
            parsed = model_schema.model_validate(parsed_json) if model_schema else parsed_json
            if include_raw:
                return {"raw": AIMessage(content=raw_text), "parsed": parsed, "parsing_error": None}
            return parsed

        return RunnableLambda(invoke_structured)

    def _build_command(
        self, executable: str, system_prompt_file: Path, json_schema: dict[str, Any] | None
    ) -> list[str]:
        command = [
            executable,
            "-p",
            "--model", self.model_name,
            "--effort", self.effort,
            "--output-format", "json",
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--system-prompt-file", str(system_prompt_file),
        ]
        if json_schema is not None:
            command.extend(["--json-schema", json.dumps(json_schema, ensure_ascii=False)])
        return command

    def _run_claude(
        self,
        system_prompt: str,
        conversation: str,
        *,
        json_schema: dict[str, Any] | None = None,
    ) -> tuple[str, Any]:
        executable = shutil.which(self.executable)
        if not executable:
            raise RuntimeError("Claude CLI executable was not found")

        allowed = _CLAUDE_ENV_ALLOWLIST | (_CLAUDE_WINDOWS_ENV if os.name == "nt" else set())
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        with tempfile.TemporaryDirectory(prefix="murena-claude-") as workdir:
            system_file = Path(workdir) / "system-prompt.txt"
            system_file.write_text(system_prompt, encoding="utf-8")
            command = self._build_command(executable, system_file, json_schema)
            try:
                result = subprocess.run(
                    command,
                    input=conversation,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=self.timeout_seconds,
                    cwd=workdir,
                    env=env,
                )
            except subprocess.TimeoutExpired as exc:
                logger.warning("Claude CLI LLM call timed out")
                raise RuntimeError("Claude CLI LLM call timed out") from exc

        payload = None
        for line in reversed(result.stdout.strip().splitlines()):
            try:
                candidate = json.loads(line)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(candidate, dict) and candidate.get("type") == "result":
                payload = candidate
                break
        if payload is None:
            logger.error("Claude CLI returned no result (exit=%s)", result.returncode)
            raise RuntimeError("Claude CLI returned no LLM response")
        if payload.get("is_error") or payload.get("subtype") != "success":
            logger.error("Claude CLI LLM call failed (subtype=%s)", payload.get("subtype"))
            raise RuntimeError(f"Claude CLI LLM call failed: {payload.get('subtype')}")
        text = payload.get("result")
        if not isinstance(text, str):
            text = json.dumps(payload.get("structured_output"), ensure_ascii=False)
        return text, payload.get("structured_output")
