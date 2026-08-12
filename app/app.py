"""FastAPI entry point for the WoundScope review workbench."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from woundscope.review_api import create_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
app = create_app(frontend_dir=REPOSITORY_ROOT / "frontend" / "dist")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "7860")),
        log_level="info",
    )
