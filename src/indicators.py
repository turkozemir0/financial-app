"""Technical indicator calculations (MA, RSI, price deviation)."""

from __future__ import annotations

import pandas as pd


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"date", "open", "close", "high", "low", "volume"}
    missing = required_columns.difference(df.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"Missing required columns: {missing_str}")

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)

    out["ma50"] = out["close"].rolling(50, min_periods=50).mean()
    out["ma200"] = out["close"].rolling(200, min_periods=200).mean()
    out["ma_signal"] = "bearish"
    out.loc[out["ma50"] > out["ma200"], "ma_signal"] = "bullish"

    out["rsi"] = calculate_rsi(out["close"], period=14)

    avg_5yr = out["close"].mean()
    out["avg_5yr"] = avg_5yr
    out["price_deviation"] = out["close"] / avg_5yr if avg_5yr else pd.NA

    return out
