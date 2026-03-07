"""Generate BUY/SELL/HOLD signals from historical CSV files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from assets import ASSETS, sanitize_symbol
from indicators import add_indicators

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


def calculate_score(last_row: pd.Series) -> int:
    score = 0

    ma_signal = str(last_row.get("ma_signal", "")).lower()
    if ma_signal == "bullish":
        score += 1
    elif ma_signal == "bearish":
        score -= 1

    rsi = float(last_row.get("rsi", 50.0))
    if rsi < 30:
        score += 1
    elif rsi > 70:
        score -= 1

    price_deviation = float(last_row.get("price_deviation", 1.0))
    if price_deviation < 0.85:
        score += 1
    elif price_deviation > 1.15:
        score -= 1

    return score


def score_to_signal(score: int) -> str:
    if score >= 2:
        return "BUY"
    if score <= -2:
        return "SELL"
    return "HOLD"


def build_signal_record(asset: Dict[str, str], last_row: pd.Series) -> Dict[str, object]:
    score = calculate_score(last_row)
    return {
        "symbol": asset["symbol"],
        "name": asset["name"],
        "category": asset["category"],
        "signal": score_to_signal(score),
        "score": score,
        "rsi": round(float(last_row["rsi"]), 2),
        "ma_signal": str(last_row["ma_signal"]),
        "price_deviation": round(float(last_row["price_deviation"]), 4),
        "current_price": round(float(last_row["close"]), 4),
        "avg_5yr": round(float(last_row["avg_5yr"]), 4),
        "last_date": pd.to_datetime(last_row["date"]).date().isoformat(),
    }


def load_signals() -> List[Dict[str, object]]:
    signals: List[Dict[str, object]] = []

    for asset in ASSETS:
        symbol = asset["symbol"]
        csv_path = DATA_DIR / f"{sanitize_symbol(symbol)}.csv"

        if not csv_path.exists():
            print(f"WARNING: missing CSV for {symbol}, skipping.")
            continue

        try:
            df = pd.read_csv(csv_path)
            enriched = add_indicators(df)
            if enriched.empty:
                print(f"WARNING: empty data after indicator calculation for {symbol}, skipping.")
                continue
            last_row = enriched.iloc[-1]
            signals.append(build_signal_record(asset, last_row))
        except Exception as exc:
            print(f"WARNING: failed processing {symbol}: {exc}")

    return signals


def print_signals_table(signals: List[Dict[str, object]]) -> None:
    if not signals:
        print("No signals available.")
        return

    df = pd.DataFrame(signals)
    df = df[["symbol", "name", "category", "signal", "score", "rsi", "price_deviation", "current_price", "last_date"]]
    print(df.to_string(index=False))


if __name__ == "__main__":
    all_signals = load_signals()
    print_signals_table(all_signals)
