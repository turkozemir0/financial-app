"""Live signal generation with batch downloads, multi-timeframe, and Binance fallback."""

from __future__ import annotations

import json
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
import yfinance as yf

from assets import ASSETS
from indicators import compute_full_analysis
from signals import build_signal_record

# Timeframe configs: (yf_interval, yf_period, min_rows)
TIMEFRAMES = {
    "15m": ("15m", "60d", 30),
    "1h": ("1h", "730d", 30),
    "1d": ("1d", "5y", 30),
    "1wk": ("1wk", "max", 20),
    "1mo": ("1mo", "max", 12),
}

BATCH_SIZE = 25


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _normalize_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance output to standard columns."""
    if raw.empty:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]

    df = raw.reset_index()

    rename_map = {}
    for col in df.columns:
        col_lower = str(col).lower()
        if col_lower in ("date", "datetime"):
            rename_map[col] = "date"
        elif col_lower == "open":
            rename_map[col] = "open"
        elif col_lower == "close":
            rename_map[col] = "close"
        elif col_lower == "high":
            rename_map[col] = "high"
        elif col_lower == "low":
            rename_map[col] = "low"
        elif col_lower == "volume":
            rename_map[col] = "volume"

    df = df.rename(columns=rename_map)

    needed = {"date", "open", "close", "high", "low", "volume"}
    if not needed.issubset(df.columns):
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    df = df[["date", "open", "close", "high", "low", "volume"]]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def fetch_history(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    """Download history for a single ticker."""
    try:
        raw = yf.download(symbol, period=period, interval=interval,
                          auto_adjust=False, progress=False)
        df = _normalize_df(raw)
        if not df.empty:
            return df
    except Exception:
        pass

    # Binance fallback for crypto
    if symbol.endswith("-USD"):
        try:
            return _fetch_binance(symbol, interval)
        except Exception:
            pass

    return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])


def _yf_interval_to_binance(interval: str) -> str:
    mapping = {"15m": "15m", "1h": "1h", "1d": "1d", "1wk": "1w", "1mo": "1M"}
    return mapping.get(interval, "1d")


def _fetch_binance(symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
    """Fetch OHLCV from Binance public API (no key needed)."""
    from urllib import request as urllib_request

    # BTC-USD → BTCUSDT
    binance_symbol = symbol.replace("-USD", "USDT")
    binance_interval = _yf_interval_to_binance(interval)

    url = (
        f"https://api.binance.com/api/v3/klines"
        f"?symbol={binance_symbol}&interval={binance_interval}&limit={limit}"
    )
    req = urllib_request.Request(url, headers={"User-Agent": "FinSignal/1.0"})
    with urllib_request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if not data:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    rows = []
    for k in data:
        rows.append({
            "date": pd.to_datetime(k[0], unit="ms"),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    df = pd.DataFrame(rows)
    return df.sort_values("date").reset_index(drop=True)


def fetch_batch(symbols: list[str], period: str = "5y", interval: str = "1d") -> dict[str, pd.DataFrame]:
    """Download multiple tickers in one yfinance call, return dict of DataFrames."""
    result: dict[str, pd.DataFrame] = {}

    if not symbols:
        return result

    try:
        tickers_str = " ".join(symbols)
        raw = yf.download(tickers_str, period=period, interval=interval,
                          auto_adjust=False, progress=False, threads=True)

        if raw.empty:
            return result

        if isinstance(raw.columns, pd.MultiIndex) and len(symbols) > 1:
            for sym in symbols:
                try:
                    sym_data = raw.xs(sym, level=1, axis=1)
                    df = _normalize_df(sym_data)
                    if not df.empty:
                        result[sym] = df
                except (KeyError, Exception):
                    continue
        elif len(symbols) == 1:
            df = _normalize_df(raw)
            if not df.empty:
                result[symbols[0]] = df
        else:
            df = _normalize_df(raw)
            if not df.empty:
                result[symbols[0]] = df
    except Exception:
        pass

    # Fetch missing ones individually (including Binance fallback)
    for sym in symbols:
        if sym not in result:
            df = fetch_history(sym, period=period, interval=interval)
            if not df.empty:
                result[sym] = df

    return result


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------

def _compute_daily_change(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 0.0
    prev = float(df.iloc[-2]["close"])
    curr = float(df.iloc[-1]["close"])
    return ((curr - prev) / prev) * 100 if prev != 0 else 0.0


def generate_live_signals(
    assets: Iterable[Dict[str, str]] = ASSETS,
    interval: str = "1d",
    period: str | None = None,
) -> List[Dict[str, object]]:
    """Generate signals for given assets using batch downloads."""
    asset_list = list(assets)
    if not asset_list:
        return []

    # Determine period from timeframe config
    if period is None:
        tf_config = TIMEFRAMES.get(interval, ("1d", "5y", 30))
        period = tf_config[1]

    # Group symbols into batches
    symbols = [a["symbol"] for a in asset_list]
    symbol_to_asset = {a["symbol"]: a for a in asset_list}

    results: List[Dict[str, object]] = []

    for i in range(0, len(symbols), BATCH_SIZE):
        batch_symbols = symbols[i:i + BATCH_SIZE]
        batch_data = fetch_batch(batch_symbols, period=period, interval=interval)

        for sym in batch_symbols:
            df = batch_data.get(sym)
            if df is None or df.empty:
                continue

            try:
                min_rows = TIMEFRAMES.get(interval, ("1d", "5y", 2))[2]
                if len(df) < min_rows:
                    continue

                analysis = compute_full_analysis(df)
                daily_change = _compute_daily_change(df)
                asset = symbol_to_asset[sym]
                results.append(build_signal_record(asset, df.iloc[-1], analysis, daily_change))
            except Exception:
                continue

    return results


def generate_multi_timeframe(symbol: str) -> dict:
    """Generate signal summary across all timeframes for a single symbol."""
    result = {}

    for tf_key, (interval, period, min_rows) in TIMEFRAMES.items():
        try:
            df = fetch_history(symbol, period=period, interval=interval)
            if df.empty or len(df) < min_rows:
                result[tf_key] = {"signal": "Notr", "buy": 0, "sell": 0, "neutral": 0}
                continue

            analysis = compute_full_analysis(df)
            summary = analysis.get("summary", {})
            result[tf_key] = {
                "signal": summary.get("signal", "Notr"),
                "buy": summary.get("buy_count", 0),
                "sell": summary.get("sell_count", 0),
                "neutral": summary.get("neutral_count", 0),
            }
        except Exception:
            result[tf_key] = {"signal": "Notr", "buy": 0, "sell": 0, "neutral": 0}

    return result
