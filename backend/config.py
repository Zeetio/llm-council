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
DEFAULT_CONFIG = {
    "council_members": [
        {
            "id": "gpt",
            "name": "GPT-5.1",
            "model": "openai/gpt-5.1",
            "system_prompt": None
        },
        {
            "id": "gemini",
            "name": "Gemini 3 Pro",
            "model": "google/gemini-3-pro-preview",
            "system_prompt": None
        },
        {
            "id": "claude",
            "name": "Claude Opus 4.5",
            "model": "anthropic/claude-opus-4.5",
            "system_prompt": None
        },
        {
            "id": "grok",
            "name": "Grok 4.1",
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
    """Load council configuration for a project, or return defaults."""
    return storage.get_config(project_id, DEFAULT_CONFIG)


def save_config(config: Dict[str, Any], project_id: str = "default") -> None:
    """Save council configuration for a project."""
    storage.save_config(config, project_id)


def get_council_members(project_id: str = "default") -> List[Dict[str, Any]]:
    config = get_config(project_id)
    return config.get("council_members", DEFAULT_CONFIG["council_members"])


def get_chairman(project_id: str = "default") -> Dict[str, Any]:
    config = get_config(project_id)
    return config.get("chairman", DEFAULT_CONFIG["chairman"])
