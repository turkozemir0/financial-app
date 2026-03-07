"""Vercel serverless API entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from fastapi import FastAPI, Query

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from assets import ASSETS  # noqa: E402
from live_signals import generate_live_signals  # noqa: E402

app = FastAPI(title="FinSignal API", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "assets": len(ASSETS)}


@app.get("/api/signals")
def signals(
    categories: List[str] = Query(default=[]),
    max_assets: int = Query(default=25, ge=1, le=120),
):
    selected_assets = ASSETS
    if categories:
        normalized = {c.lower() for c in categories}
        selected_assets = [a for a in ASSETS if a["category"].lower() in normalized]

    selected_assets = selected_assets[:max_assets]
    data = generate_live_signals(selected_assets)

    return {
        "count": len(data),
        "requested_assets": len(selected_assets),
        "signals": data,
    }
