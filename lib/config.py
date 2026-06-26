"""配置加载"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

CONFIG_FILE = Path("config.toml")


def load_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return {}


def get_email_config() -> dict[str, Any]:
    return load_config().get("email", {})


def get_turnstile_config() -> dict[str, Any]:
    return load_config().get("turnstile", {})


def get_platform_config(name: str) -> dict[str, Any]:
    return load_config().get("platforms", {}).get(name, {})
