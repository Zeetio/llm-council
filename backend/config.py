"""Configuration for the LLM Council."""

import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Config file path
CONFIG_FILE = "data/council_config.json"

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


def get_config() -> Dict[str, Any]:
    """Load council configuration from JSON file, or return defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save council configuration to JSON file."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_council_members() -> List[Dict[str, Any]]:
    """Get list of council members from config."""
    config = get_config()
    return config.get("council_members", DEFAULT_CONFIG["council_members"])


def get_chairman() -> Dict[str, Any]:
    """Get chairman configuration."""
    config = get_config()
    return config.get("chairman", DEFAULT_CONFIG["chairman"])


# Legacy compatibility - will be removed later
COUNCIL_MODELS = [m["model"] for m in DEFAULT_CONFIG["council_members"]]
CHAIRMAN_MODEL = DEFAULT_CONFIG["chairman"]["model"]
