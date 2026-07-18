from __future__ import annotations

from pathlib import Path

import pytest

from woundscope.config import config_hash, deep_merge, load_config, parse_overrides


def test_deep_merge_does_not_mutate_inputs() -> None:
    base = {"training": {"epochs": 2, "amp": True}}
    overlay = {"training": {"epochs": 5}}

    merged = deep_merge(base, overlay)

    assert merged == {"training": {"epochs": 5, "amp": True}}
    assert base["training"]["epochs"] == 2


def test_parse_overrides_uses_yaml_scalars() -> None:
    parsed = parse_overrides(["training.amp=false", "training.epochs=3", "data.limit=null"])

    assert parsed == {"training": {"amp": False, "epochs": 3}, "data": {"limit": None}}


def test_invalid_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="key=value"):
        parse_overrides(["training.epochs"])


def test_load_config_expands_defaults_and_has_stable_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WOUNDSCOPE_DATA_DIR", raising=False)
    config = load_config(
        Path("configs/base.yaml"),
        Path("configs/models/unet_efficientnet_b0.yaml"),
        Path("configs/modes/quick.yaml"),
        ["training.batch_size=4"],
    )

    assert config["data"]["root"] == "data"
    assert config["model"]["name"] == "unet_efficientnet_b0"
    assert config["mode"]["name"] == "quick"
    assert config["training"]["batch_size"] == 4
    assert config_hash(config) == config_hash(config)


def test_environment_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOUNDSCOPE_DATA_DIR", "custom-data")
    config = load_config(Path("configs/base.yaml"))

    assert config["data"]["root"] == "custom-data"
