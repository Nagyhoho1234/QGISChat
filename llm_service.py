"""Unified multi-provider LLM client."""
import json
import os
import uuid
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .settings import Settings, LlmProvider, PROVIDER_INFO

_SYSTEM_PROMPT_BASE = """\
You are a GIS assistant embedded in QGIS. You help users perform geospatial tasks
using natural language. You have access to the current map state (layers, extent, CRS).

When the user asks you to perform a GIS operation, call the run_pyqgis function/tool
to generate and execute Python/PyQGIS code.

Guidelines for generated PyQGIS code:
- Access the current project: project = QgsProject.instance()
- Get the active canvas: canvas = iface.mapCanvas()
- Use processing.run() for geoprocessing: processing.run("native:buffer", {...})
- For layer references, use the layer name as shown in the map context
- Store results in a temporary or memory layer, or save to the project folder
- Use descriptive output names
- Print results/counts so the user gets feedback
- Handle errors with try/except and print useful messages
- Always end with a print() statement summarizing what was done
- To add a result layer to the map: QgsProject.instance().addMapLayer(layer)
- For selections: layer.selectByExpression() or processing.run("native:selectbylocation", ...)

If the user asks a question that doesn't require code execution, just answer with text.
If you're unsure which layer the user means, ask for clarification.
If a task seems destructive (deleting data), warn the user and ask for confirmation.

IMPORTANT — Error recovery:
When a tool execution returns an error, DO NOT just report the error to the user.
Instead, automatically try an alternative approach. For example:
- If a processing tool fails, try an alternative algorithm or workaround
- If a layer name is not found, list available layers and pick the closest match
- If a CRS transformation fails, try a different approach
Only report failure to the user after you have exhausted reasonable alternatives.

CRITICAL: In QGIS, sys.executable points to qgis-bin.exe, NOT python.exe.
NEVER use subprocess.run([sys.executable, ...]) — it launches a new QGIS instance.
For pip install, use: from pip._internal.cli.main import main as _pip; _pip(['install', 'package_name'])"""

_GEE_SECTION = """

Google Earth Engine Integration:
The user has GEE configured (project: {project}). You can generate Python code that uses
the earthengine-api (ee) to query, process, and download GEE data.

GEE code guidelines:
- Initialize with: import ee; ee.Initialize(project='{project}')
- Use ee.Image, ee.ImageCollection, ee.FeatureCollection for GEE data
- Use the current map extent or study area from context as default region
- ee.Image.getDownloadURL() has a 50 MB per-request limit
- Server-side operations (mosaic, clip, compositing) have no size limit
- For large areas, estimate size first and split downloads if needed
- After downloading, add the result as a raster layer to QGIS"""


def build_system_prompt():
    """Build system prompt, appending GEE section if configured."""
    prompt = _SYSTEM_PROMPT_BASE
    gee_project = Settings.gee_project()
    if gee_project:
        prompt += _GEE_SECTION.format(project=gee_project)
    return prompt

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "PyQGIS/Python code to execute"},
        "explanation": {"type": "string", "description": "Brief explanation of what this code does"},
    },
    "required": ["code", "explanation"],
}


class LlmResponse:
    def __init__(self):
        self.text = ""
        self.tool_calls = []  # list of dicts with id, name, arguments

    @property
    def tool_call(self):
        """Convenience: first tool call or None."""
        return self.tool_calls[0] if self.tool_calls else None

    @property
    def has_tool_call(self):
        return len(self.tool_calls) > 0


MAX_HISTORY_LENGTH = 40


class LlmService:
    def __init__(self):
        self._history = []

    def clear_history(self):
        self._history.clear()

    def rollback_history(self, count=1):
        """Remove the last N entries from history."""
        for _ in range(min(count, len(self._history))):
            self._history.pop()

    def trim_history(self):
        """Trim history to MAX_HISTORY_LENGTH, preserving tool_use/tool_result pairs."""
        if len(self._history) <= MAX_HISTORY_LENGTH:
            return
        cut = len(self._history) - MAX_HISTORY_LENGTH
        # Ensure we don't cut in the middle of a tool_use/tool_result pair
        # Skip forward past any assistant message that contains tool_use
        while cut < len(self._history) - 2:
            msg = self._history[cut]
            # Anthropic: assistant content may be a list with tool_use blocks
            if isinstance(msg.get("content"), list):
                has_tool = any(
                    isinstance(b, dict) and b.get("type") in ("tool_use", "tool_result")
                    for b in msg["content"]
                )
                if has_tool:
                    cut += 1
                    continue
            # OpenAI: assistant message with tool_calls
            if msg.get("tool_calls"):
                cut += 1
                continue
            # OpenAI: tool role message
            if msg.get("role") == "tool":
                cut += 1
                continue
            break
        self._dump_history_to_debug_log("trim", len(self._history))
        self._history = self._history[cut:]

    def _dump_history_to_debug_log(self, reason: str, msg_count: int):
        """Write conversation snapshot to JSONL for debugging."""
        try:
            if os.name == "nt":
                log_dir = os.path.join(os.environ.get("APPDATA", "."), "QGISChat", "logs")
            else:
                log_dir = os.path.expanduser("~/.local/share/QGISChat/logs")
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, f"conversation_{datetime.now():%Y-%m-%d}.jsonl")
            entry = {
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "messageCount": msg_count,
                "messages": self._history,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Debug logging must never break the main flow

    def send(self, user_message: str, map_context: str) -> LlmResponse:
        self.trim_history()
        provider = Settings.provider()
        if PROVIDER_INFO[provider]["needs_key"] and not Settings.api_key():
            raise ValueError(
                f"API key not configured for {PROVIDER_INFO[provider]['display']}.\n"
                "Go to Plugins > GIS Chat > Settings to configure."
            )
        dispatch = {
            LlmProvider.Anthropic: self._send_anthropic,
            LlmProvider.GoogleGemini: self._send_gemini,
        }
        fn = dispatch.get(provider, self._send_openai_compatible)
        return fn(user_message, map_context)

    def send_tool_result(self, tool_call_id: str, result: str, map_context: str) -> LlmResponse:
        """Send a single tool result (legacy, used by non-Anthropic providers)."""
        self.trim_history()
        provider = Settings.provider()
        dispatch = {
            LlmProvider.Anthropic: self._send_anthropic_tool_result,
            LlmProvider.GoogleGemini: self._send_gemini_tool_result,
        }
        fn = dispatch.get(provider, self._send_openai_tool_result)
        return fn(tool_call_id, result, map_context)

    def send_tool_results(self, results: list, map_context: str) -> LlmResponse:
        """Send multiple tool results in one message (required by Anthropic).

        Args:
            results: list of (tool_call_id, result_text) tuples
            map_context: current map state
        """
        self.trim_history()
        provider = Settings.provider()
        if provider == LlmProvider.Anthropic:
            return self._send_anthropic_tool_results(results, map_context)
        elif provider == LlmProvider.GoogleGemini:
            # Gemini: send results one by one (no batch requirement)
            resp = LlmResponse()
            for tc_id, result in results:
                resp = self._send_gemini_tool_result(tc_id, result, map_context)
            return resp
        else:
            # OpenAI: send results one by one
            resp = LlmResponse()
            for tc_id, result in results:
                resp = self._send_openai_tool_result(tc_id, result, map_context)
            return resp

    # ---- HTTP helper ----

    @staticmethod
    def _post(url: str, headers: dict, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API error ({e.code}): {error_body}") from e
        except URLError as e:
            raise RuntimeError(f"Connection error: {e.reason}") from e

    # ---- Anthropic ----

    def _send_anthropic(self, user_message, map_context):
        self._history.append({"role": "user", "content": user_message})
        body = {
            "model": Settings.model(),
            "max_tokens": Settings.max_tokens(),
            "system": build_system_prompt() + "\n\nCurrent QGIS state:\n" + map_context,
            "messages": self._history,
            "tools": [{
                "name": "run_pyqgis",
                "description": "Execute PyQGIS/Python code in the QGIS Python environment.",
                "input_schema": TOOL_SCHEMA,
            }],
        }
        headers = {
            "x-api-key": Settings.api_key(),
            "anthropic-version": "2023-06-01",
        }
        data = self._post(Settings.effective_endpoint(), headers, body)
        self._history.append({"role": "assistant", "content": data.get("content", [])})
        return self._parse_anthropic(data)

    def _send_anthropic_tool_result(self, tool_call_id, result, map_context):
        """Send a single tool result (kept for compatibility)."""
        return self._send_anthropic_tool_results([(tool_call_id, result)], map_context)

    def _send_anthropic_tool_results(self, results, map_context):
        """Send multiple tool results in one user message (Anthropic requires this)."""
        content = [
            {"type": "tool_result", "tool_use_id": tc_id, "content": result_text}
            for tc_id, result_text in results
        ]
        self._history.append({"role": "user", "content": content})
        body = {
            "model": Settings.model(),
            "max_tokens": Settings.max_tokens(),
            "system": build_system_prompt() + "\n\nCurrent QGIS state:\n" + map_context,
            "messages": self._history,
            "tools": [{
                "name": "run_pyqgis",
                "description": "Execute PyQGIS/Python code in the QGIS Python environment.",
                "input_schema": TOOL_SCHEMA,
            }],
        }
        headers = {
            "x-api-key": Settings.api_key(),
            "anthropic-version": "2023-06-01",
        }
        data = self._post(Settings.effective_endpoint(), headers, body)
        self._history.append({"role": "assistant", "content": data.get("content", [])})
        return self._parse_anthropic(data)

    @staticmethod
    def _parse_anthropic(data):
        resp = LlmResponse()
        for block in data.get("content", []):
            if block.get("type") == "text":
                resp.text += block.get("text", "")
            elif block.get("type") == "tool_use":
                resp.tool_calls.append({
                    "id": block["id"],
                    "name": block["name"],
                    "arguments": block["input"],
                })
        return resp

    # ---- OpenAI / Ollama / Compatible ----

    def _send_openai_compatible(self, user_message, map_context):
        self._history.append({"role": "user", "content": user_message})
        messages = [
            {"role": "system", "content": build_system_prompt() + "\n\nCurrent QGIS state:\n" + map_context},
        ] + self._history
        body = {
            "model": Settings.model(),
            "messages": messages,
            "max_tokens": Settings.max_tokens(),
            "tools": [{
                "type": "function",
                "function": {
                    "name": "run_pyqgis",
                    "description": "Execute PyQGIS/Python code in the QGIS Python environment.",
                    "parameters": TOOL_SCHEMA,
                },
            }],
        }
        headers = {}
        api_key = Settings.api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = self._post(Settings.effective_endpoint(), headers, body)
        choice = data["choices"][0]["message"]
        self._history.append(choice)
        return self._parse_openai(choice)

    def _send_openai_tool_result(self, tool_call_id, result, map_context):
        self._history.append({"role": "tool", "tool_call_id": tool_call_id, "content": result})
        messages = [
            {"role": "system", "content": build_system_prompt() + "\n\nCurrent QGIS state:\n" + map_context},
        ] + self._history
        body = {
            "model": Settings.model(),
            "messages": messages,
            "max_tokens": Settings.max_tokens(),
            "tools": [{
                "type": "function",
                "function": {
                    "name": "run_pyqgis",
                    "description": "Execute PyQGIS/Python code in the QGIS Python environment.",
                    "parameters": TOOL_SCHEMA,
                },
            }],
        }
        headers = {}
        api_key = Settings.api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = self._post(Settings.effective_endpoint(), headers, body)
        choice = data["choices"][0]["message"]
        self._history.append(choice)
        return self._parse_openai(choice)

    @staticmethod
    def _parse_openai(message):
        resp = LlmResponse()
        resp.text = message.get("content") or ""
        tool_calls = message.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = tc["function"]
                resp.tool_calls.append({
                    "id": tc["id"],
                    "name": fn["name"],
                    "arguments": json.loads(fn.get("arguments", "{}")),
                })
        return resp

    # ---- Google Gemini ----

    def _send_gemini(self, user_message, map_context):
        self._history.append({"role": "user", "parts": [{"text": user_message}]})
        url = f"{Settings.effective_endpoint()}/models/{Settings.model()}:generateContent?key={Settings.api_key()}"
        contents = [
            {"role": "user", "parts": [{"text": build_system_prompt() + "\n\nCurrent QGIS state:\n" + map_context}]},
            {"role": "model", "parts": [{"text": "Understood. I'm ready to help with GIS tasks."}]},
        ] + self._history
        body = {
            "contents": contents,
            "tools": [{
                "function_declarations": [{
                    "name": "run_pyqgis",
                    "description": "Execute PyQGIS/Python code in the QGIS Python environment.",
                    "parameters": TOOL_SCHEMA,
                }],
            }],
        }
        data = self._post(url, {}, body)
        parts = data["candidates"][0]["content"]["parts"]
        self._history.append({"role": "model", "parts": parts})
        return self._parse_gemini(parts)

    def _send_gemini_tool_result(self, tool_call_id, result, map_context):
        self._history.append({
            "role": "user",
            "parts": [{"functionResponse": {"name": "run_pyqgis", "response": {"result": result}}}],
        })
        url = f"{Settings.effective_endpoint()}/models/{Settings.model()}:generateContent?key={Settings.api_key()}"
        contents = [
            {"role": "user", "parts": [{"text": build_system_prompt() + "\n\nCurrent QGIS state:\n" + map_context}]},
            {"role": "model", "parts": [{"text": "Understood."}]},
        ] + self._history
        body = {"contents": contents}
        data = self._post(url, {}, body)
        parts = data["candidates"][0]["content"]["parts"]
        self._history.append({"role": "model", "parts": parts})
        return self._parse_gemini(parts)

    @staticmethod
    def _parse_gemini(parts):
        resp = LlmResponse()
        for part in parts:
            if "text" in part:
                resp.text += part["text"]
            if "functionCall" in part:
                fc = part["functionCall"]
                resp.tool_calls.append({
                    "id": "gemini_" + uuid.uuid4().hex[:8],
                    "name": fc["name"],
                    "arguments": fc["args"],
                })
        return resp
