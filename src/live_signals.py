"""Live signal generation from yfinance without local CSV dependency."""

from __future__ import annotations

from typing import Iterable, List, Dict

import pandas as pd
import yfinance as yf

from assets import ASSETS
from indicators import add_indicators
from signals import build_signal_record


def fetch_history(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    raw = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    if raw.empty:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]

    df = raw.reset_index().rename(
        columns={
            "Date": "date",
            "Open": "open",
            "Close": "close",
            "High": "high",
            "Low": "low",
            "Volume": "volume",
        }
    )
    df = df[["date", "open", "close", "high", "low", "volume"]]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def generate_live_signals(assets: Iterable[Dict[str, str]] = ASSETS) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []

    for asset in assets:
        try:
            df = fetch_history(asset["symbol"])
            if df.empty:
                continue
            enriched = add_indicators(df)
            if enriched.empty:
                continue
            results.append(build_signal_record(asset, enriched.iloc[-1]))
        except Exception:
            continue

    return results
