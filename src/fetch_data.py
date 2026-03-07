"""Download historical OHLCV data for all configured assets."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

from assets import ASSETS, sanitize_symbol

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def _normalize_ohlcv(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()

    # yfinance can return a multi-index; flatten when needed.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "Close": "close",
            "High": "high",
            "Low": "low",
            "Volume": "volume",
        }
    )

    if "date" not in df.columns:
        df = df.reset_index().rename(columns={"index": "date"})

    keep_columns = ["date", "open", "close", "high", "low", "volume"]
    df = df[keep_columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def download_asset(symbol: str) -> pd.DataFrame:
    raw = yf.download(symbol, period="5y", interval="1d", auto_adjust=False, progress=False)
    if raw.empty:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])
    return _normalize_ohlcv(raw)


def download_all_assets(assets: Iterable[dict] = ASSETS) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for idx, asset in enumerate(assets, start=1):
        symbol = asset["symbol"]
        safe_name = sanitize_symbol(symbol)
        out_path = DATA_DIR / f"{safe_name}.csv"

        print(f"[{idx:03d}/{len(ASSETS):03d}] Downloading {symbol} -> {out_path.name}")
        try:
            df = download_asset(symbol)
            if df.empty:
                print(f"  WARNING: no data for {symbol}, skipping.")
                continue
            df.to_csv(out_path, index=False)
            print(f"  Saved {len(df)} rows")
        except Exception as exc:
            print(f"  WARNING: failed {symbol}: {exc}")


if __name__ == "__main__":
    download_all_assets()
