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
            timeout_seconds=30, retry_backoff_seconds=0.0, launch_spacing_seconds=0.0,
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
            seen["input"] = kwargs["stdin"].read().decode("utf-8")
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


class SageJsonParsingTest(unittest.TestCase):
    def test_single_fence_is_unwrapped_other_text_rejected(self):
        from app.services.sage_clarification.service import _parse_llm_json

        self.assertEqual(_parse_llm_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(_parse_llm_json('{"a": 1}'), {"a": 1})
        with self.assertRaises(ValueError):
            _parse_llm_json('Here it is: {"a": 1}')

    def test_leading_think_block_is_dropped(self):
        from app.services.sage_clarification.service import _parse_llm_json

        self.assertEqual(_parse_llm_json('<think>reasoning {x}</think>\n{"a": 1}'), {"a": 1})
        self.assertEqual(_parse_llm_json('<think>r</think>\n```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ValueError):
            _parse_llm_json('{"a": 1} <think>late</think>')


class OpenWeightConfigTest(unittest.TestCase):
    def test_thinking_flag_override_and_heuristic(self):
        from app.core.config import settings
        from app.services.llm.providers import disable_thinking

        with patch.object(settings, "LLM_DISABLE_THINKING", None):
            self.assertTrue(disable_thinking("http://localhost:8000/v1"))
            self.assertFalse(disable_thinking("http://130.192.0.1:8000/v1"))
        with patch.object(settings, "LLM_DISABLE_THINKING", True):
            self.assertTrue(disable_thinking("http://130.192.0.1:8000/v1"))
        with patch.object(settings, "LLM_DISABLE_THINKING", False):
            self.assertFalse(disable_thinking("http://localhost:8000/v1"))

    def test_provenance_records_endpoint_without_credentials(self):
        import sys
        from pathlib import Path
        from types import SimpleNamespace

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
        from benchmark_cli import llm_provenance

        fake = SimpleNamespace(
            LLM_MODEL="qwen-test", LLM_PROVIDER="openai-compatible",
            LLM_BASE_URL="http://user:secret@10.0.0.5:8000/v1?key=abc", OPENAI_API_BASE=None,
            CODEX_REASONING_EFFORT="low", CLAUDE_CLI_EFFORT="medium", AGENT_TEMPERATURE=0.0,
        )
        with patch("app.services.llm.providers.resolve_provider", return_value="openai-compatible"):
            prov = llm_provenance(fake)
        self.assertEqual(prov["endpoint"], "http://10.0.0.5:8000")
        self.assertNotIn("secret", json.dumps(prov))
        self.assertTrue(prov["temperature_applied"])
        self.assertIn(prov["thinking_disabled"], (True, False))


if __name__ == "__main__":
    unittest.main()
