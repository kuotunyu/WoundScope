"""Small top-level CLI; task-specific scripts live under scripts/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from woundscope import __version__
from woundscope.config import config_hash, load_config

app = typer.Typer(no_args_is_help=True, help="WoundScope reproducible segmentation toolkit.")


@app.command()
def version() -> None:
    """Print the package version."""

    typer.echo(__version__)


@app.command("show-config")
def show_config(
    base: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path("configs/base.yaml"),
    model: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    mode: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    set_value: Annotated[
        list[str] | None,
        typer.Option("--set", help="Repeatable dotted key=value override."),
    ] = None,
) -> None:
    """Print a resolved configuration and its stable hash."""

    config = load_config(base, model, mode, set_value)
    typer.echo(json.dumps({"config": config, "config_hash": config_hash(config)}, indent=2))
