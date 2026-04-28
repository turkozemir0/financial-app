"""Comprehensive technical indicator calculations.

12 Oscillators + 12 Moving Averages (6 SMA + 6 EMA).
All computed with pandas/numpy only (no ta-lib, no pandas_ta).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helper: validated close / high / low / volume series from DataFrame
# ---------------------------------------------------------------------------

def _require_columns(df: pd.DataFrame, cols: set[str]) -> None:
    missing = cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")


# ---------------------------------------------------------------------------
# Moving Averages
# ---------------------------------------------------------------------------

MA_PERIODS = [5, 10, 20, 50, 100, 200]


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def compute_moving_averages(close: pd.Series, current_price: float) -> list[dict]:
    """Return list of MA dicts with SMA/EMA values and signals."""
    results = []
    for p in MA_PERIODS:
        sma_val = sma(close, p).iloc[-1] if len(close) >= p else np.nan
        ema_val = ema(close, p).iloc[-1] if len(close) >= p else np.nan

        sma_signal = "Al" if (not np.isnan(sma_val) and current_price > sma_val) else (
            "Sat" if (not np.isnan(sma_val) and current_price < sma_val) else "Notr")
        ema_signal = "Al" if (not np.isnan(ema_val) and current_price > ema_val) else (
            "Sat" if (not np.isnan(ema_val) and current_price < ema_val) else "Notr")

        results.append({
            "name": f"MA{p}",
            "sma": round(float(sma_val), 4) if not np.isnan(sma_val) else None,
            "sma_signal": sma_signal,
            "ema": round(float(ema_val), 4) if not np.isnan(ema_val) else None,
            "ema_signal": ema_signal,
        })
    return results


# ---------------------------------------------------------------------------
# Oscillators
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                         k_period: int = 9, d_period: int = 6) -> tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()
    denom = highest_high - lowest_low
    denom = denom.replace(0, np.nan)
    k = 100 * (close - lowest_low) / denom
    k = k.fillna(50)
    d = k.rolling(window=d_period, min_periods=1).mean()
    return k, d


def calculate_stoch_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    rsi = calculate_rsi(close, period)
    lowest_rsi = rsi.rolling(window=period, min_periods=period).min()
    highest_rsi = rsi.rolling(window=period, min_periods=period).max()
    denom = highest_rsi - lowest_rsi
    denom = denom.replace(0, np.nan)
    stoch_rsi = (rsi - lowest_rsi) / denom
    return (stoch_rsi * 100).fillna(50)


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26,
                   signal_period: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series,
                  period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    plus_dm = high - prev_high
    minus_dm = prev_low - low
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr.replace(0, np.nan))

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    return adx.fillna(0), plus_di.fillna(0), minus_di.fillna(0)


def calculate_williams_r(high: pd.Series, low: pd.Series, close: pd.Series,
                         period: int = 14) -> pd.Series:
    highest_high = high.rolling(window=period, min_periods=period).max()
    lowest_low = low.rolling(window=period, min_periods=period).min()
    denom = highest_high - lowest_low
    denom = denom.replace(0, np.nan)
    wr = -100 * (highest_high - close) / denom
    return wr.fillna(-50)


def calculate_cci(high: pd.Series, low: pd.Series, close: pd.Series,
                  period: int = 14) -> pd.Series:
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    mad = tp.rolling(window=period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    mad = mad.replace(0, np.nan)
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci.fillna(0)


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                  period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return atr.fillna(0)


def calculate_highs_lows(close: pd.Series, period: int = 14) -> pd.Series:
    """Count of new highs minus new lows over period."""
    rolling_high = close.rolling(window=period, min_periods=period).max()
    rolling_low = close.rolling(window=period, min_periods=period).min()
    new_highs = (close == rolling_high).astype(int)
    new_lows = (close == rolling_low).astype(int)
    hl = (new_highs - new_lows).rolling(window=period, min_periods=1).sum()
    return hl.fillna(0)


def calculate_ultimate_oscillator(high: pd.Series, low: pd.Series, close: pd.Series,
                                  p1: int = 7, p2: int = 14, p3: int = 28) -> pd.Series:
    prev_close = close.shift(1)
    bp = close - pd.concat([low, prev_close], axis=1).min(axis=1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    avg1 = bp.rolling(p1, min_periods=p1).sum() / tr.rolling(p1, min_periods=p1).sum().replace(0, np.nan)
    avg2 = bp.rolling(p2, min_periods=p2).sum() / tr.rolling(p2, min_periods=p2).sum().replace(0, np.nan)
    avg3 = bp.rolling(p3, min_periods=p3).sum() / tr.rolling(p3, min_periods=p3).sum().replace(0, np.nan)

    uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
    return uo.fillna(50)


def calculate_roc(close: pd.Series, period: int = 12) -> pd.Series:
    prev = close.shift(period)
    roc = ((close - prev) / prev.replace(0, np.nan)) * 100
    return roc.fillna(0)


def calculate_bull_bear_power(high: pd.Series, low: pd.Series, close: pd.Series,
                              period: int = 13) -> tuple[pd.Series, pd.Series]:
    ema_val = ema(close, period)
    bull = high - ema_val
    bear = low - ema_val
    return bull.fillna(0), bear.fillna(0)


# ---------------------------------------------------------------------------
# Oscillator signals
# ---------------------------------------------------------------------------

def compute_oscillator_signals(df: pd.DataFrame) -> list[dict]:
    """Return list of oscillator dicts with name, value, signal."""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    results = []

    # 1. RSI(14)
    rsi_series = calculate_rsi(close, 14)
    rsi_val = float(rsi_series.iloc[-1])
    if rsi_val > 70:
        rsi_sig = "Sat"
    elif rsi_val < 30:
        rsi_sig = "Al"
    elif rsi_val > 50:
        rsi_sig = "Al"
    else:
        rsi_sig = "Sat"
    results.append({"name": "RSI(14)", "value": round(rsi_val, 2), "signal": rsi_sig})

    # 2. STOCH(9,6)
    k, d = calculate_stochastic(high, low, close, 9, 6)
    k_val = float(k.iloc[-1])
    d_val = float(d.iloc[-1])
    if k_val > 80:
        stoch_sig = "Sat"
    elif k_val < 20:
        stoch_sig = "Al"
    elif k_val > d_val:
        stoch_sig = "Al"
    else:
        stoch_sig = "Sat"
    results.append({"name": "STOCH(9,6)", "value": round(k_val, 2), "signal": stoch_sig})

    # 3. StochRSI(14)
    stoch_rsi = calculate_stoch_rsi(close, 14)
    sr_val = float(stoch_rsi.iloc[-1])
    if sr_val > 80:
        sr_sig = "Sat"
    elif sr_val < 20:
        sr_sig = "Al"
    elif sr_val > 50:
        sr_sig = "Al"
    else:
        sr_sig = "Sat"
    results.append({"name": "StochRSI(14)", "value": round(sr_val, 2), "signal": sr_sig})

    # 4. MACD(12,26)
    macd_line, signal_line, _ = calculate_macd(close, 12, 26, 9)
    macd_val = float(macd_line.iloc[-1])
    sig_val = float(signal_line.iloc[-1])
    macd_sig = "Al" if macd_val > sig_val else "Sat"
    results.append({"name": "MACD(12,26)", "value": round(macd_val, 4), "signal": macd_sig})

    # 5. ADX(14)
    adx_series, plus_di, minus_di = calculate_adx(high, low, close, 14)
    adx_val = float(adx_series.iloc[-1])
    pdi_val = float(plus_di.iloc[-1])
    mdi_val = float(minus_di.iloc[-1])
    if adx_val < 20:
        adx_sig = "Notr"
    elif pdi_val > mdi_val:
        adx_sig = "Al"
    else:
        adx_sig = "Sat"
    results.append({"name": "ADX(14)", "value": round(adx_val, 2), "signal": adx_sig})

    # 6. Williams %R(14)
    wr = calculate_williams_r(high, low, close, 14)
    wr_val = float(wr.iloc[-1])
    if wr_val > -20:
        wr_sig = "Sat"
    elif wr_val < -80:
        wr_sig = "Al"
    elif wr_val > -50:
        wr_sig = "Sat"
    else:
        wr_sig = "Al"
    results.append({"name": "Williams %R(14)", "value": round(wr_val, 2), "signal": wr_sig})

    # 7. CCI(14)
    cci = calculate_cci(high, low, close, 14)
    cci_val = float(cci.iloc[-1])
    if cci_val > 100:
        cci_sig = "Al"
    elif cci_val < -100:
        cci_sig = "Sat"
    else:
        cci_sig = "Notr"
    results.append({"name": "CCI(14)", "value": round(cci_val, 2), "signal": cci_sig})

    # 8. ATR(14) - info only
    atr = calculate_atr(high, low, close, 14)
    atr_val = float(atr.iloc[-1])
    results.append({"name": "ATR(14)", "value": round(atr_val, 4), "signal": "Notr"})

    # 9. Highs/Lows(14)
    hl = calculate_highs_lows(close, 14)
    hl_val = float(hl.iloc[-1])
    if hl_val > 0:
        hl_sig = "Al"
    elif hl_val < 0:
        hl_sig = "Sat"
    else:
        hl_sig = "Notr"
    results.append({"name": "Highs/Lows(14)", "value": round(hl_val, 2), "signal": hl_sig})

    # 10. Ultimate Oscillator(7,14,28)
    uo = calculate_ultimate_oscillator(high, low, close, 7, 14, 28)
    uo_val = float(uo.iloc[-1])
    if uo_val > 70:
        uo_sig = "Sat"
    elif uo_val < 30:
        uo_sig = "Al"
    elif uo_val > 50:
        uo_sig = "Al"
    else:
        uo_sig = "Sat"
    results.append({"name": "Ultimate Osc.", "value": round(uo_val, 2), "signal": uo_sig})

    # 11. ROC(12)
    roc = calculate_roc(close, 12)
    roc_val = float(roc.iloc[-1])
    roc_sig = "Al" if roc_val > 0 else ("Sat" if roc_val < 0 else "Notr")
    results.append({"name": "ROC(12)", "value": round(roc_val, 2), "signal": roc_sig})

    # 12. Bull/Bear Power(13)
    bull, bear = calculate_bull_bear_power(high, low, close, 13)
    bull_val = float(bull.iloc[-1])
    bear_val = float(bear.iloc[-1])
    if bull_val > 0 and bear_val > 0:
        bbp_sig = "Al"
    elif bull_val < 0 and bear_val < 0:
        bbp_sig = "Sat"
    elif bull_val > 0:
        bbp_sig = "Al"
    else:
        bbp_sig = "Sat"
    results.append({"name": "Bull/Bear(13)", "value": round(bull_val + bear_val, 4), "signal": bbp_sig})

    return results


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def compute_full_analysis(df: pd.DataFrame) -> dict:
    """Compute all oscillators and MAs; return structured analysis dict."""
    _require_columns(df, {"date", "open", "close", "high", "low", "volume"})

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)

    if out.empty or len(out) < 2:
        return {
            "oscillators": [],
            "moving_averages": [],
            "oscillator_summary": {"signal": "Notr", "buy_count": 0, "sell_count": 0, "neutral_count": 0},
            "ma_summary": {"signal": "Notr", "buy_count": 0, "sell_count": 0},
            "summary": {"signal": "Notr", "buy_count": 0, "sell_count": 0, "neutral_count": 0},
        }

    current_price = float(out["close"].iloc[-1])

    # Oscillators
    oscillators = compute_oscillator_signals(out)
    osc_buy = sum(1 for o in oscillators if o["signal"] == "Al")
    osc_sell = sum(1 for o in oscillators if o["signal"] == "Sat")
    osc_neutral = sum(1 for o in oscillators if o["signal"] == "Notr")

    # Moving averages
    moving_averages = compute_moving_averages(out["close"], current_price)
    ma_buy = sum(1 for m in moving_averages for s in [m["sma_signal"], m["ema_signal"]] if s == "Al")
    ma_sell = sum(1 for m in moving_averages for s in [m["sma_signal"], m["ema_signal"]] if s == "Sat")

    # Summaries
    total_osc = osc_buy + osc_sell + osc_neutral
    osc_ratio = (osc_buy - osc_sell) / total_osc if total_osc > 0 else 0
    osc_summary_signal = _ratio_to_signal(osc_ratio)

    total_ma = ma_buy + ma_sell
    ma_ratio = (ma_buy - ma_sell) / total_ma if total_ma > 0 else 0
    ma_summary_signal = _ratio_to_signal(ma_ratio)

    # Overall summary
    all_buy = osc_buy + ma_buy
    all_sell = osc_sell + ma_sell
    all_neutral = osc_neutral
    total_all = all_buy + all_sell + all_neutral
    overall_ratio = (all_buy - all_sell) / total_all if total_all > 0 else 0
    overall_signal = _ratio_to_signal(overall_ratio)

    return {
        "oscillators": oscillators,
        "moving_averages": moving_averages,
        "oscillator_summary": {
            "signal": osc_summary_signal,
            "buy_count": osc_buy,
            "sell_count": osc_sell,
            "neutral_count": osc_neutral,
        },
        "ma_summary": {
            "signal": ma_summary_signal,
            "buy_count": ma_buy,
            "sell_count": ma_sell,
        },
        "summary": {
            "signal": overall_signal,
            "buy_count": all_buy,
            "sell_count": all_sell,
            "neutral_count": all_neutral,
        },
    }


def _ratio_to_signal(ratio: float) -> str:
    if ratio >= 0.5:
        return "Guclu Al"
    if ratio >= 0.1:
        return "Al"
    if ratio > -0.1:
        return "Notr"
    if ratio > -0.5:
        return "Sat"
    return "Guclu Sat"


# ---------------------------------------------------------------------------
# Legacy compatibility: add_indicators (used by old signals.py / api)
# ---------------------------------------------------------------------------

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Legacy wrapper - adds basic indicators for backward compat."""
    _require_columns(df, {"date", "open", "close", "high", "low", "volume"})
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)

    out["ma50"] = sma(out["close"], 50)
    out["ma200"] = sma(out["close"], 200)
    out["ma_signal"] = "bearish"
    out.loc[out["ma50"] > out["ma200"], "ma_signal"] = "bullish"
    out["rsi"] = calculate_rsi(out["close"], 14)
    avg_5yr = out["close"].mean()
    out["avg_5yr"] = avg_5yr
    out["price_deviation"] = out["close"] / avg_5yr if avg_5yr else np.nan
    return out
