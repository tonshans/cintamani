"""
Cintamani Core Configuration Manager
Loads, generates, and persists configuration at data/config.json.
Supports customizable host/port, token rotation, and multi-provider LLM settings.
"""

from __future__ import annotations
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
ENV_FILE = BASE_DIR / ".env"


def load_dotenv(path: Path = ENV_FILE) -> None:
    """Loads KEY=VALUE pairs from .env into os.environ (existing env wins)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


load_dotenv()

DEFAULT_CONFIG: Dict[str, Any] = {
    "server_name": "Cintamani Home Brain",
    "host": "0.0.0.0",
    "port": 3000,
    "api_token": "",
    "duckdb_path": "data/cintamani_brain.duckdb",
    "llm_provider": "ollama",  # "ollama" | "openai" | "openai_compatible" | "gemini" | "claude"
    "llm_base_url": os.environ.get("LLM_BASE_URL", ""),
    "llm_api_key": os.environ.get("LLM_API_KEY", ""),
    "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    "llm_model": "qwen2.5:7b",
    "embedding_provider": "ollama",
    "embedding_model": "nomic-embed-text",
    "embedding_dim": 768,
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", "")
}

# Env vars override config.json on every load.
ENV_OVERRIDES = {
    "GEMINI_API_KEY": "gemini_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "LLM_API_KEY": "llm_api_key",
    "LLM_BASE_URL": "llm_base_url",
    "OLLAMA_BASE_URL": "ollama_base_url",
}


def generate_secure_token() -> str:
    """Generate a new secure bearer token prefixed with cm_live_."""
    return f"cm_live_{secrets.token_hex(16)}"


class ConfigManager:
    """Singleton manager for application configuration stored in data/config.json."""

    _instance: ConfigManager | None = None
    _config: Dict[str, Any] = {}

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.load_or_create()
        return cls._instance

    def load_or_create(self) -> Dict[str, Any]:
        """Loads data/config.json or creates it if it doesn't exist."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if not CONFIG_FILE.exists():
            config = dict(DEFAULT_CONFIG)
            config["api_token"] = generate_secure_token()
            self._config = config
            self.save()
            return self._config

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            # Merge with default config to ensure all keys exist
            merged = dict(DEFAULT_CONFIG)
            merged.update(loaded)

            # Ensure API token is present
            if not merged.get("api_token"):
                merged["api_token"] = generate_secure_token()

            # Sync environment variables if present (env wins over file)
            for env_name, cfg_key in ENV_OVERRIDES.items():
                if os.environ.get(env_name):
                    merged[cfg_key] = os.environ[env_name]

            self._config = merged
            self.save()
            return self._config
        except Exception:
            # Keep the unreadable file for recovery instead of silently losing keys.
            try:
                CONFIG_FILE.replace(CONFIG_FILE.with_suffix(".json.corrupt"))
            except OSError:
                pass
            config = dict(DEFAULT_CONFIG)
            config["api_token"] = generate_secure_token()
            self._config = config
            self.save()
            return self._config

    def get_all(self) -> Dict[str, Any]:
        """Returns the complete configuration dictionary."""
        return dict(self._config)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific config value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets a configuration value and persists it."""
        self._config[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]) -> None:
        """Updates multiple configuration values and persists them."""
        self._config.update(updates)
        self.save()

    def rotate_token(self) -> str:
        """Rotates the API token and persists it."""
        new_token = generate_secure_token()
        self.set("api_token", new_token)
        return new_token

    def save(self) -> None:
        """Saves current configuration to data/config.json with indentation."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)
        try:
            os.chmod(CONFIG_FILE, 0o600)  # config may hold API keys
        except OSError:
            pass


def get_config() -> ConfigManager:
    """Helper to access the singleton ConfigManager."""
    return ConfigManager()
