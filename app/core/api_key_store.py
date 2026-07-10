from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings


@lru_cache
def load_api_key_config() -> dict[str, Any]:
    settings = get_settings()
    config_path = Path(settings.api_keys_config_path)

    if not config_path.exists():
        return {"api_keys": {}}

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        return {"api_keys": {}}

    api_keys = data.get("api_keys", {})

    if not isinstance(api_keys, dict):
        return {"api_keys": {}}

    return {
        "api_keys": api_keys,
    }


def get_api_key_identity(api_key: str | None) -> dict[str, Any] | None:
    if not api_key:
        return None

    config = load_api_key_config()
    identity = config["api_keys"].get(api_key)

    if not isinstance(identity, dict):
        return None
    
    if identity.get("enabled") is False:
        return None

    return identity