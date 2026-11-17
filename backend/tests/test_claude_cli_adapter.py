"""Unit tests for the Claude Code CLI LangChain adapter (no real CLI calls)."""

import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.services.llm.claude_cli import ClaudeCliChatModel  # noqa: E402
from app.services.llm.providers import build_chat_model, normalize_provider  # noqa: E402


def _result(payload):
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")


class Extract(BaseModel):
    use: str
    city: str


class ClaudeCliAdapterTest(unittest.TestCase):
    def _model(self):
        return ClaudeCliChatModel(
            model_name="claude-haiku-5-5", effort="medium", executable="claude",
            timeout_seconds=30, retry_backoff_seconds=0.0,
        )

    def test_transient_failure_is_retried(self):
        replies = iter([
            SimpleNamespace(returncode=1, stdout="", stderr="transient"),
            _result({"type": "result", "subtype": "success", "is_error": False, "result": "OK"}),
        ])
        with patch("app.services.llm.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
             patch("app.services.llm.claude_cli.subprocess.run", side_effect=lambda *a, **k: next(replies)) as run:
            self.assertEqual(self._model().invoke("x").content, "OK")
        self.assertEqual(run.call_count, 2)

    def test_command_isolated_and_system_prompt_separated(self):
        seen = {}

        def fake_run(command, **kwargs):
            seen["command"] = command
            seen["input"] = kwargs["input"]
            seen["env"] = kwargs["env"]
            idx = command.index("--system-prompt-file")
            seen["system"] = Path(command[idx + 1]).read_text(encoding="utf-8")
            return _result({"type": "result", "subtype": "success", "is_error": False, "result": "PONG"})

        env = {"PATH": os.environ.get("PATH", ""), "ANTHROPIC_API_KEY": "secret", "CLAUDECODE": "1"}
        with patch("app.services.llm.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
             patch("app.services.llm.claude_cli.subprocess.run", side_effect=fake_run), \
             patch.dict(os.environ, env, clear=True):
            reply = self._model().invoke([SystemMessage(content="Be terse."), HumanMessage(content="ping")])

        self.assertEqual(reply.content, "PONG")
        cmd = seen["command"]
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-haiku-5-5")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
        for flag in ("--strict-mcp-config", "--no-session-persistence", "-p"):
            self.assertIn(flag, cmd)
        self.assertEqual(seen["system"], "Be terse.")
        self.assertEqual(seen["input"], "ping")
        self.assertNotIn("ANTHROPIC_API_KEY", seen["env"])
        self.assertNotIn("CLAUDECODE", seen["env"])

    def test_structured_output_uses_schema_and_structured_field(self):
        seen = {}

        def fake_run(command, **kwargs):
            seen["schema"] = json.loads(command[command.index("--json-schema") + 1])
            return _result({
                "type": "result", "subtype": "success", "is_error": False,
                "result": "```json\n{\"use\": \"x\"}\n```",
                "structured_output": {"use": "nursery", "city": "Turin"},
            })

        with patch("app.services.llm.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
             patch("app.services.llm.claude_cli.subprocess.run", side_effect=fake_run):
            parsed = self._model().with_structured_output(Extract).invoke("extract")

        self.assertEqual(parsed, Extract(use="nursery", city="Turin"))
        self.assertIn("use", seen["schema"]["properties"])

    def test_structured_output_falls_back_to_fenced_json(self):
        with patch("app.services.llm.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
             patch("app.services.llm.claude_cli.subprocess.run", return_value=_result({
                 "type": "result", "subtype": "success", "is_error": False,
                 "result": "```json\n{\"use\": \"nursery\", \"city\": \"Turin\"}\n```",
             })):
            parsed = self._model().with_structured_output(Extract).invoke("extract")
        self.assertEqual(parsed.city, "Turin")

    def test_fails_closed_on_error_result_and_missing_payload(self):
        with patch("app.services.llm.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
             patch("app.services.llm.claude_cli.subprocess.run", return_value=_result({
                 "type": "result", "subtype": "error_max_turns", "is_error": True,
             })):
            with self.assertRaises(RuntimeError):
                self._model().invoke("x")
        with patch("app.services.llm.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
             patch("app.services.llm.claude_cli.subprocess.run",
                   return_value=SimpleNamespace(returncode=1, stdout="not json", stderr="boom")):
            with self.assertRaises(RuntimeError):
                self._model().invoke("x")

    def test_provider_registry(self):
        self.assertEqual(normalize_provider("claude-cli"), "claude_cli")
        model = build_chat_model(provider="claude_cli", model_name="claude-haiku-5-5", temperature=0.0)
        self.assertIsInstance(model, ClaudeCliChatModel)
        self.assertEqual(model.model_name, "claude-haiku-5-5")


if __name__ == "__main__":
    unittest.main()
