"""Settings persistence using QSettings."""
from enum import Enum
from qgis.core import QgsSettings


class LlmProvider(Enum):
    Anthropic = "Anthropic"
    OpenAI = "OpenAI"
    GoogleGemini = "GoogleGemini"
    Ollama = "Ollama"
    OpenAICompatible = "OpenAICompatible"


PROVIDER_INFO = {
    LlmProvider.Anthropic: {
        "display": "Anthropic (Claude)",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
        "endpoint": "https://api.anthropic.com/v1/messages",
        "needs_key": True,
        "key_help": "Get your key at console.anthropic.com/settings/keys",
    },
    LlmProvider.OpenAI: {
        "display": "OpenAI (GPT)",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"],
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "needs_key": True,
        "key_help": "Get your key at platform.openai.com/api-keys",
    },
    LlmProvider.GoogleGemini: {
        "display": "Google Gemini (free tier available)",
        "models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-flash"],
        "endpoint": "https://generativelanguage.googleapis.com/v1beta",
        "needs_key": True,
        "key_help": "Get your FREE key at aistudio.google.com/apikey",
    },
    LlmProvider.Ollama: {
        "display": "Ollama (local, completely free)",
        "models": ["llama3.1", "mistral", "codellama", "deepseek-coder-v2"],
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "needs_key": False,
        "key_help": "No API key needed! Install Ollama from ollama.com",
    },
    LlmProvider.OpenAICompatible: {
        "display": "OpenAI-compatible (LM Studio, vLLM...)",
        "models": ["default"],
        "endpoint": "http://localhost:8080/v1/chat/completions",
        "needs_key": True,
        "key_help": "Enter the API key for your endpoint (if required)",
    },
}


class Settings:
    PREFIX = "GISChat/"

    @staticmethod
    def _s():
        return QgsSettings()

    @classmethod
    def provider(cls) -> LlmProvider:
        val = cls._s().value(cls.PREFIX + "provider", "Anthropic")
        try:
            return LlmProvider(val)
        except ValueError:
            return LlmProvider.Anthropic

    @classmethod
    def set_provider(cls, p: LlmProvider):
        cls._s().setValue(cls.PREFIX + "provider", p.value)

    @classmethod
    def api_key(cls) -> str:
        return cls._s().value(cls.PREFIX + "api_key", "")

    @classmethod
    def set_api_key(cls, key: str):
        cls._s().setValue(cls.PREFIX + "api_key", key)

    @classmethod
    def model(cls) -> str:
        return cls._s().value(cls.PREFIX + "model", "claude-sonnet-4-6")

    @classmethod
    def set_model(cls, m: str):
        cls._s().setValue(cls.PREFIX + "model", m)

    @classmethod
    def endpoint(cls) -> str:
        return cls._s().value(cls.PREFIX + "endpoint", "")

    @classmethod
    def set_endpoint(cls, url: str):
        cls._s().setValue(cls.PREFIX + "endpoint", url)

    @classmethod
    def effective_endpoint(cls) -> str:
        ep = cls.endpoint()
        if ep:
            return ep
        return PROVIDER_INFO[cls.provider()]["endpoint"]

    @classmethod
    def max_tokens(cls) -> int:
        return int(cls._s().value(cls.PREFIX + "max_tokens", 4096))

    @classmethod
    def set_max_tokens(cls, v: int):
        cls._s().setValue(cls.PREFIX + "max_tokens", v)

    @classmethod
    def confirm_before_execute(cls) -> bool:
        return cls._s().value(cls.PREFIX + "confirm_before_execute", "true") == "true"

    @classmethod
    def set_confirm_before_execute(cls, v: bool):
        cls._s().setValue(cls.PREFIX + "confirm_before_execute", "true" if v else "false")

    @classmethod
    def show_generated_code(cls) -> bool:
        return cls._s().value(cls.PREFIX + "show_generated_code", "true") == "true"

    @classmethod
    def set_show_generated_code(cls, v: bool):
        cls._s().setValue(cls.PREFIX + "show_generated_code", "true" if v else "false")

    @classmethod
    def gee_project(cls) -> str:
        return cls._s().value(cls.PREFIX + "gee_project", "")

    @classmethod
    def set_gee_project(cls, project: str):
        cls._s().setValue(cls.PREFIX + "gee_project", project)
