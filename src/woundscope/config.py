"""Portable YAML configuration loading and deterministic overrides."""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?}")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a recursive merge without mutating either input."""

    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _expand_environment(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        configured = os.environ.get(name)
        if configured:
            return configured
        if default is not None:
            return default
        raise ValueError(f"Required environment variable is not set: {name}")

    return _ENV_PATTERN.sub(replace, value)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Top-level YAML value must be a mapping: {path}")
    return loaded


def _set_nested(config: dict[str, Any], dotted_key: str, value: Any) -> None:
    keys = dotted_key.split(".")
    if any(not key for key in keys):
        raise ValueError(f"Invalid override key: {dotted_key!r}")
    cursor = config
    for key in keys[:-1]:
        child = cursor.setdefault(key, {})
        if not isinstance(child, dict):
            raise ValueError(f"Cannot set nested override beneath non-mapping key: {dotted_key}")
        cursor = child
    cursor[keys[-1]] = value


def parse_overrides(values: list[str] | None) -> dict[str, Any]:
    """Parse `key=value` overrides using YAML scalar semantics."""

    result: dict[str, Any] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"Override must use key=value syntax: {item!r}")
        key, raw = item.split("=", 1)
        _set_nested(result, key.strip(), yaml.safe_load(raw))
    return result


def load_config(
    base_path: str | Path,
    model_path: str | Path | None = None,
    mode_path: str | Path | None = None,
    overrides: list[str] | None = None,
) -> dict[str, Any]:
    """Load and merge base, model, mode, then CLI overrides."""

    config = _read_yaml(Path(base_path))
    for optional_path in (model_path, mode_path):
        if optional_path is not None:
            config = deep_merge(config, _read_yaml(Path(optional_path)))
    config = deep_merge(config, parse_overrides(overrides))
    return _expand_environment(config)


def config_hash(config: dict[str, Any]) -> str:
    """Return a stable SHA-256 for a resolved configuration mapping."""

    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
