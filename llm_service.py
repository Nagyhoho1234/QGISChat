"""Unified multi-provider LLM client."""
import json
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .settings import Settings, LlmProvider, PROVIDER_INFO

SYSTEM_PROMPT = """\
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
Only report failure to the user after you have exhausted reasonable alternatives."""

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
        self.tool_call = None  # dict with id, name, arguments


class LlmService:
    def __init__(self):
        self._history = []

    def clear_history(self):
        self._history.clear()

    def send(self, user_message: str, map_context: str) -> LlmResponse:
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
        provider = Settings.provider()
        dispatch = {
            LlmProvider.Anthropic: self._send_anthropic_tool_result,
            LlmProvider.GoogleGemini: self._send_gemini_tool_result,
        }
        fn = dispatch.get(provider, self._send_openai_tool_result)
        return fn(tool_call_id, result, map_context)

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
            "system": SYSTEM_PROMPT + "\n\nCurrent QGIS state:\n" + map_context,
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
        self._history.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result}],
        })
        body = {
            "model": Settings.model(),
            "max_tokens": Settings.max_tokens(),
            "system": SYSTEM_PROMPT + "\n\nCurrent QGIS state:\n" + map_context,
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
                resp.tool_call = {
                    "id": block["id"],
                    "name": block["name"],
                    "arguments": block["input"],
                }
        return resp

    # ---- OpenAI / Ollama / Compatible ----

    def _send_openai_compatible(self, user_message, map_context):
        self._history.append({"role": "user", "content": user_message})
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nCurrent QGIS state:\n" + map_context},
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
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nCurrent QGIS state:\n" + map_context},
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
            tc = tool_calls[0]
            fn = tc["function"]
            resp.tool_call = {
                "id": tc["id"],
                "name": fn["name"],
                "arguments": json.loads(fn.get("arguments", "{}")),
            }
        return resp

    # ---- Google Gemini ----

    def _send_gemini(self, user_message, map_context):
        self._history.append({"role": "user", "parts": [{"text": user_message}]})
        url = f"{Settings.effective_endpoint()}/models/{Settings.model()}:generateContent?key={Settings.api_key()}"
        contents = [
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\nCurrent QGIS state:\n" + map_context}]},
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
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\nCurrent QGIS state:\n" + map_context}]},
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
                resp.tool_call = {
                    "id": "gemini_" + uuid.uuid4().hex[:8],
                    "name": fc["name"],
                    "arguments": fc["args"],
                }
        return resp
