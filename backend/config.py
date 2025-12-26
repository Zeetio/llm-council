"""Configuration helpers (project-aware)."""

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from . import storage

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default council configuration
# モデルID: OpenRouter形式 (https://openrouter.ai/models)
DEFAULT_CONFIG = {
    "council_members": [
        {
            "id": "gpt51",
            "name": "GPT-5.1",
            "model": "openai/gpt-5.1",
            "system_prompt": None
        },
        {
            "id": "gpt5mini",
            "name": "GPT-5 Mini",
            "model": "openai/gpt-5-mini",
            "system_prompt": None
        },
        {
            "id": "gemini",
            "name": "Gemini 3 Flash",
            "model": "google/gemini-3-flash-preview",
            "system_prompt": None
        },
        {
            "id": "grok",
            "name": "Grok 4.1 Fast",
            "model": "x-ai/grok-4.1-fast",
            "system_prompt": None
        },
    ],
    "chairman": {
        "id": "chairman",
        "name": "Chairman",
        "model": "openai/gpt-5.1",
        "system_prompt": None
    }
}


def get_config(project_id: str = "default") -> Dict[str, Any]:
    """Load council configuration for a project, merged with defaults."""
    stored = storage.get_config(project_id, DEFAULT_CONFIG)
    # Merge with defaults to ensure all required fields exist
    result = DEFAULT_CONFIG.copy()
    if stored.get("council_members"):
        result["council_members"] = stored["council_members"]
    if stored.get("chairman"):
        result["chairman"] = stored["chairman"]
    # password_hashはデフォルトにないので明示的にコピー
    if "password_hash" in stored:
        result["password_hash"] = stored["password_hash"]
    # memory_settingsを復元
    if stored.get("memory_settings"):
        result["memory_settings"] = stored["memory_settings"]
    return result


def save_config(config: Dict[str, Any], project_id: str = "default") -> None:
    """Save council configuration for a project."""
    storage.save_config(config, project_id)


def get_council_members(project_id: str = "default") -> List[Dict[str, Any]]:
    config = get_config(project_id)
    return config.get("council_members", DEFAULT_CONFIG["council_members"])


def get_chairman(project_id: str = "default") -> Dict[str, Any]:
    config = get_config(project_id)
    return config.get("chairman", DEFAULT_CONFIG["chairman"])
