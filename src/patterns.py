"""Basic chart pattern detection for AI analysis augmentation.

Detects: Double Top/Bottom, Head-and-Shoulders, Triangles, Support/Resistance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _find_local_extrema(series: pd.Series, window: int = 5) -> tuple[list[int], list[int]]:
    """Find local maxima and minima indices."""
    highs = []
    lows = []
    values = series.values
    n = len(values)

    for i in range(window, n - window):
        segment = values[i - window:i + window + 1]
        if values[i] == np.nanmax(segment):
            highs.append(i)
        if values[i] == np.nanmin(segment):
            lows.append(i)

    return highs, lows


def detect_double_top(close: pd.Series, tolerance: float = 0.02) -> list[dict]:
    """Detect double top patterns."""
    patterns = []
    highs, _ = _find_local_extrema(close, window=10)

    for i in range(len(highs) - 1):
        h1_idx, h2_idx = highs[i], highs[i + 1]
        h1_val, h2_val = close.iloc[h1_idx], close.iloc[h2_idx]

        if abs(h1_val - h2_val) / max(h1_val, h2_val) <= tolerance:
            # Check for valley between peaks
            between = close.iloc[h1_idx:h2_idx + 1]
            valley = between.min()
            if valley < h1_val * (1 - tolerance):
                patterns.append({
                    "pattern": "Cift Tepe (Double Top)",
                    "type": "bearish",
                    "level": round(float((h1_val + h2_val) / 2), 4),
                })
                break

    return patterns


def detect_double_bottom(close: pd.Series, tolerance: float = 0.02) -> list[dict]:
    """Detect double bottom patterns."""
    patterns = []
    _, lows = _find_local_extrema(close, window=10)

    for i in range(len(lows) - 1):
        l1_idx, l2_idx = lows[i], lows[i + 1]
        l1_val, l2_val = close.iloc[l1_idx], close.iloc[l2_idx]

        if abs(l1_val - l2_val) / max(l1_val, l2_val) <= tolerance:
            between = close.iloc[l1_idx:l2_idx + 1]
            peak = between.max()
            if peak > l1_val * (1 + tolerance):
                patterns.append({
                    "pattern": "Cift Dip (Double Bottom)",
                    "type": "bullish",
                    "level": round(float((l1_val + l2_val) / 2), 4),
                })
                break

    return patterns


def detect_head_and_shoulders(close: pd.Series, tolerance: float = 0.02) -> list[dict]:
    """Detect head-and-shoulders pattern (bearish)."""
    patterns = []
    highs, _ = _find_local_extrema(close, window=8)

    for i in range(len(highs) - 2):
        left = close.iloc[highs[i]]
        head = close.iloc[highs[i + 1]]
        right = close.iloc[highs[i + 2]]

        if head > left and head > right:
            if abs(left - right) / max(left, right) <= tolerance:
                patterns.append({
                    "pattern": "Omuz-Bas-Omuz",
                    "type": "bearish",
                    "level": round(float(head), 4),
                })
                break

    return patterns


def detect_support_resistance(close: pd.Series, n_levels: int = 3) -> list[dict]:
    """Detect support and resistance levels via price clustering."""
    if len(close) < 20:
        return []

    recent = close.tail(100).values
    price_range = np.nanmax(recent) - np.nanmin(recent)
    if price_range == 0:
        return []

    n_bins = 50
    counts, edges = np.histogram(recent, bins=n_bins)
    levels = []

    sorted_idx = np.argsort(counts)[::-1]
    current_price = float(close.iloc[-1])

    for idx in sorted_idx[:n_levels * 2]:
        level = (edges[idx] + edges[idx + 1]) / 2
        level_type = "Direnc" if level > current_price else "Destek"
        levels.append({
            "type": level_type,
            "level": round(float(level), 4),
            "strength": int(counts[idx]),
        })

    # Sort and pick top n
    levels.sort(key=lambda x: x["strength"], reverse=True)
    return levels[:n_levels]


def detect_triangle(close: pd.Series) -> list[dict]:
    """Detect contracting/expanding triangle patterns."""
    patterns = []
    if len(close) < 30:
        return patterns

    recent = close.tail(40)
    highs, lows = _find_local_extrema(recent, window=5)

    if len(highs) >= 3 and len(lows) >= 3:
        high_vals = [float(recent.iloc[h]) for h in highs[-3:]]
        low_vals = [float(recent.iloc[l]) for l in lows[-3:]]

        high_decreasing = high_vals[0] > high_vals[1] > high_vals[2]
        low_increasing = low_vals[0] < low_vals[1] < low_vals[2]

        if high_decreasing and low_increasing:
            patterns.append({
                "pattern": "Daralan Ucgen (Symmetrical Triangle)",
                "type": "neutral",
                "level": round((high_vals[-1] + low_vals[-1]) / 2, 4),
            })
        elif high_decreasing and not low_increasing:
            patterns.append({
                "pattern": "Azalan Ucgen (Descending Triangle)",
                "type": "bearish",
                "level": round(low_vals[-1], 4),
            })
        elif not high_decreasing and low_increasing:
            patterns.append({
                "pattern": "Yukselen Ucgen (Ascending Triangle)",
                "type": "bullish",
                "level": round(high_vals[-1], 4),
            })

    return patterns


def detect_all_patterns(df: pd.DataFrame) -> list[dict]:
    """Run all pattern detections and return combined results."""
    if df.empty or "close" not in df.columns or len(df) < 30:
        return []

    close = df["close"]
    patterns = []

    patterns.extend(detect_double_top(close))
    patterns.extend(detect_double_bottom(close))
    patterns.extend(detect_head_and_shoulders(close))
    patterns.extend(detect_triangle(close))

    sr_levels = detect_support_resistance(close)
    for sr in sr_levels:
        patterns.append({
            "pattern": f"{sr['type']} Seviyesi",
            "type": "support" if sr["type"] == "Destek" else "resistance",
            "level": sr["level"],
        })

    return patterns
