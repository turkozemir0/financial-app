"""5-level signal system: Guclu Al / Al / Notr / Sat / Guclu Sat.

Uses comprehensive indicators from indicators.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from assets import ASSETS, sanitize_symbol
from indicators import compute_full_analysis, add_indicators

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def compute_signal_from_analysis(analysis: dict) -> str:
    """Extract overall signal string from full analysis dict."""
    return analysis.get("summary", {}).get("signal", "Notr")


def build_signal_record(asset: Dict[str, str], last_row: pd.Series,
                        analysis: dict | None = None,
                        daily_change_pct: float = 0.0) -> Dict[str, object]:
    """Build signal output dict from asset info, last data row, and analysis."""
    if analysis is None:
        signal = "Notr"
        osc_summary = {"signal": "Notr", "buy_count": 0, "sell_count": 0, "neutral_count": 0}
        ma_summary = {"signal": "Notr", "buy_count": 0, "sell_count": 0}
        summary = {"signal": "Notr", "buy_count": 0, "sell_count": 0, "neutral_count": 0}
    else:
        signal = compute_signal_from_analysis(analysis)
        osc_summary = analysis.get("oscillator_summary", {})
        ma_summary = analysis.get("ma_summary", {})
        summary = analysis.get("summary", {})

    current_price = float(last_row["close"]) if "close" in last_row.index else 0.0

    return {
        "symbol": asset["symbol"],
        "name": asset["name"],
        "category": asset["category"],
        "signal": signal,
        "current_price": round(current_price, 4),
        "daily_change_pct": round(daily_change_pct, 2),
        "last_date": pd.to_datetime(last_row["date"]).date().isoformat() if "date" in last_row.index else "",
        "buy_count": summary.get("buy_count", 0),
        "sell_count": summary.get("sell_count", 0),
        "neutral_count": summary.get("neutral_count", 0),
        "oscillator_summary": osc_summary,
        "ma_summary": ma_summary,
    }


def load_signals() -> List[Dict[str, object]]:
    """Load signals from local CSV files (legacy)."""
    signals: List[Dict[str, object]] = []

    for asset in ASSETS:
        symbol = asset["symbol"]
        csv_path = DATA_DIR / f"{sanitize_symbol(symbol)}.csv"

        if not csv_path.exists():
            continue

        try:
            df = pd.read_csv(csv_path)
            enriched = add_indicators(df)
            if enriched.empty:
                continue

            analysis = compute_full_analysis(df)
            last_row = enriched.iloc[-1]

            # Daily change
            daily_change = 0.0
            if len(enriched) >= 2:
                prev_close = float(enriched.iloc[-2]["close"])
                if prev_close > 0:
                    daily_change = ((float(last_row["close"]) - prev_close) / prev_close) * 100

            signals.append(build_signal_record(asset, last_row, analysis, daily_change))
        except Exception as exc:
            print(f"WARNING: failed processing {symbol}: {exc}")

    return signals


def print_signals_table(signals: List[Dict[str, object]]) -> None:
    if not signals:
        print("No signals available.")
        return

    df = pd.DataFrame(signals)
    cols = ["symbol", "name", "category", "signal", "current_price", "daily_change_pct", "last_date"]
    df = df[[c for c in cols if c in df.columns]]
    print(df.to_string(index=False))


if __name__ == "__main__":
    all_signals = load_signals()
    print_signals_table(all_signals)
