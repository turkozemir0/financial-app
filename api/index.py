"""Vercel serverless API entrypoint - Comprehensive Technical Analysis System."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib import request

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd  # noqa: E402

from assets import ASSETS, get_categories  # noqa: E402
from indicators import compute_full_analysis, add_indicators  # noqa: E402
from live_signals import (  # noqa: E402
    fetch_history,
    generate_live_signals,
    generate_multi_timeframe,
    TIMEFRAMES,
)
from pivot_points import calculate_pivots  # noqa: E402
from patterns import detect_all_patterns  # noqa: E402

app = FastAPI(title="FinSignal API", version="2.0.0")

ANALYSIS_CACHE: Dict[str, Dict[str, object]] = {}
ANALYSIS_TTL_SECONDS = 12 * 60 * 60
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
SECRET_KEY = os.environ.get("APP_SECRET", "change-this-secret-in-production")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@finsignal.app").strip().lower()
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "FinSignal123").strip()


class AuthPayload(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)


def _normalize_email(email: str) -> str:
    value = email.lower().strip()
    if "@" not in value or "." not in value.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Gecerli bir email giriniz")
    return value


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _create_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "iat": int(time.time()),
    }
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_token(token: str) -> Dict[str, object]:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def _get_current_user(request_obj: Request) -> str:
    auth = request_obj.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    email = str(payload.get("sub", ""))
    if not email:
        raise HTTPException(status_code=401, detail="Invalid user")
    return email


def _call_openai_analysis(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return ""

    body = {
        "model": OPENAI_MODEL,
        "input": prompt,
        "max_output_tokens": 700,
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with request.urlopen(req, timeout=30) as res:
        payload = json.loads(res.read().decode("utf-8"))

    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    try:
        chunks = payload.get("output", [])
        texts: List[str] = []
        for item in chunks:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        return "\n".join(t for t in texts if t).strip() or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Frontend HTML
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return _FRONTEND_HTML


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register")
def register(payload: AuthPayload):
    _ = payload
    raise HTTPException(status_code=403, detail="Kayit kapali")


@app.post("/api/auth/login")
def login(payload: AuthPayload):
    email = _normalize_email(payload.email)
    if email != DEMO_EMAIL or not hmac.compare_digest(payload.password, DEMO_PASSWORD):
        raise HTTPException(status_code=401, detail="Email veya sifre hatali")
    token = _create_token(email)
    return {"ok": True, "email": email, "token": token}


@app.get("/api/auth/me")
def me(request_obj: Request):
    email = _get_current_user(request_obj)
    return {"ok": True, "email": email}


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    cats = get_categories()
    return {"ok": True, "assets": len(ASSETS), "categories": cats}


@app.get("/api/signals")
def signals(
    categories: List[str] = Query(default=[]),
    max_assets: int = Query(default=50, ge=1, le=120),
    offset: int = Query(default=0, ge=0),
    timeframe: str = Query(default="1d"),
):
    generated_at = datetime.now(timezone.utc).isoformat()
    selected_assets = ASSETS
    if categories:
        normalized = {c.lower() for c in categories}
        selected_assets = [a for a in ASSETS if a["category"].lower() in normalized]

    total = len(selected_assets)
    selected_assets = selected_assets[offset:offset + max_assets]

    tf_config = TIMEFRAMES.get(timeframe, TIMEFRAMES["1d"])
    interval = tf_config[0]
    period = tf_config[1]

    data = generate_live_signals(selected_assets, interval=interval, period=period)
    signals_data = [{**item, "updated_at": generated_at} for item in data]

    return {
        "count": len(data),
        "total": total,
        "offset": offset,
        "max_assets": max_assets,
        "generated_at": generated_at,
        "signals": signals_data,
    }


@app.get("/api/asset-detail")
def asset_detail(
    symbol: str = Query(...),
    timeframe: str = Query(default="1d"),
):
    ticker = symbol.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="symbol zorunlu")

    asset = next((a for a in ASSETS if a["symbol"].upper() == ticker.upper()), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset bulunamadi")

    tf_config = TIMEFRAMES.get(timeframe, TIMEFRAMES["1d"])
    interval, period, min_rows = tf_config

    df = fetch_history(ticker, period=period, interval=interval)
    if df.empty or len(df) < min_rows:
        raise HTTPException(status_code=404, detail="Yeterli fiyat verisi yok")

    analysis = compute_full_analysis(df)

    current_price = float(df.iloc[-1]["close"])
    daily_change_pct = 0.0
    if len(df) >= 2:
        prev = float(df.iloc[-2]["close"])
        if prev > 0:
            daily_change_pct = ((current_price - prev) / prev) * 100

    # Pivot points from last row
    last = df.iloc[-1]
    pivots = calculate_pivots(
        float(last["high"]), float(last["low"]),
        float(last["close"]), float(last["open"])
    )

    # OHLCV data (last 200 candles for chart)
    chart_df = df.tail(200)
    ohlcv = []
    for _, row in chart_df.iterrows():
        ohlcv.append({
            "date": pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M"),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "volume": int(row["volume"]) if not pd.isna(row["volume"]) else 0,
        })

    return {
        "symbol": asset["symbol"],
        "name": asset["name"],
        "category": asset["category"],
        "price": round(current_price, 4),
        "daily_change_pct": round(daily_change_pct, 2),
        "timeframe": timeframe,
        "oscillators": analysis.get("oscillators", []),
        "moving_averages": analysis.get("moving_averages", []),
        "summary": analysis.get("summary", {}),
        "oscillator_summary": analysis.get("oscillator_summary", {}),
        "ma_summary": analysis.get("ma_summary", {}),
        "pivot_points": pivots,
        "ohlcv": ohlcv,
    }


@app.get("/api/multi-timeframe")
def multi_timeframe(symbol: str = Query(...)):
    ticker = symbol.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="symbol zorunlu")

    asset = next((a for a in ASSETS if a["symbol"].upper() == ticker.upper()), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset bulunamadi")

    tf_data = generate_multi_timeframe(ticker)

    return {
        "symbol": asset["symbol"],
        "name": asset["name"],
        "timeframes": tf_data,
    }


@app.get("/api/ai-analysis")
def ai_analysis(symbol: str, request_obj: Request):
    _ = _get_current_user(request_obj)
    ticker = symbol.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="symbol zorunlu")

    now = int(time.time())
    cached = ANALYSIS_CACHE.get(ticker)
    if cached and int(cached.get("expires_at", 0)) > now:
        return {
            "ok": True,
            "symbol": ticker,
            "generated_at": cached["generated_at"],
            "analysis": cached["analysis"],
            "cached": True,
        }

    asset = next((a for a in ASSETS if a["symbol"].upper() == ticker), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset bulunamadi")

    df = fetch_history(ticker, period="5y", interval="1d")
    if df.empty or len(df) < 30:
        raise HTTPException(status_code=404, detail="Yeterli fiyat verisi yok")

    analysis = compute_full_analysis(df)
    patterns = detect_all_patterns(df)
    last = df.iloc[-1]
    current_price = float(last["close"])
    first_price = float(df.iloc[0]["close"])
    change_5y_pct = ((current_price / first_price) - 1.0) * 100.0 if first_price else 0.0

    # Build comprehensive AI prompt
    osc_lines = []
    for o in analysis.get("oscillators", []):
        osc_lines.append(f"  {o['name']}: {o['value']} → {o['signal']}")

    ma_lines = []
    for m in analysis.get("moving_averages", []):
        ma_lines.append(f"  {m['name']}: SMA={m['sma']} ({m['sma_signal']}), EMA={m['ema']} ({m['ema_signal']})")

    pattern_lines = []
    for p in patterns:
        pattern_lines.append(f"  {p['pattern']} (seviye: {p['level']})")

    summary = analysis.get("summary", {})
    osc_summary = analysis.get("oscillator_summary", {})
    ma_summary = analysis.get("ma_summary", {})

    prompt = (
        "Asagidaki varlik icin kapsamli bir teknik analiz yaz. Cikti turkce olsun.\n"
        "Basliklar:\n"
        "1) Genel Trend Analizi\n"
        "2) Osilator Durumu\n"
        "3) Hareketli Ortalama Analizi\n"
        "4) Destek/Direnc Seviyeleri\n"
        "5) Formasyon Tespiti\n"
        "6) Risk Degerlendirmesi\n"
        "7) Aksiyon Onerisi (Guclu Al / Al / Notr / Sat / Guclu Sat)\n\n"
        "Yatirim tavsiyesi degildir notu ekle.\n\n"
        f"Varlik: {asset['name']} ({ticker})\n"
        f"Guncel Fiyat: {current_price:.4f}\n"
        f"5Y Degisim: %{change_5y_pct:.2f}\n\n"
        f"Genel Ozet: {summary.get('signal', 'Notr')} (Al:{summary.get('buy_count',0)} Sat:{summary.get('sell_count',0)} Notr:{summary.get('neutral_count',0)})\n"
        f"Osilator Ozeti: {osc_summary.get('signal', 'Notr')}\n"
        f"MA Ozeti: {ma_summary.get('signal', 'Notr')}\n\n"
        f"Osilatorler:\n" + "\n".join(osc_lines) + "\n\n"
        f"Hareketli Ortalamalar:\n" + "\n".join(ma_lines) + "\n\n"
    )

    if pattern_lines:
        prompt += f"Tespit Edilen Formasyonlar:\n" + "\n".join(pattern_lines) + "\n\n"

    # Try AI, fallback to local
    analysis_text = _local_ai_fallback(ticker, asset["name"], analysis, change_5y_pct, patterns)
    try:
        if OPENAI_API_KEY:
            ai_text = _call_openai_analysis(prompt)
            if ai_text:
                analysis_text = ai_text
    except Exception:
        pass

    generated_at = datetime.now(timezone.utc).isoformat()
    ANALYSIS_CACHE[ticker] = {
        "analysis": analysis_text,
        "generated_at": generated_at,
        "expires_at": now + ANALYSIS_TTL_SECONDS,
    }

    return {
        "ok": True,
        "symbol": ticker,
        "generated_at": generated_at,
        "analysis": analysis_text,
        "cached": False,
    }


def _local_ai_fallback(symbol: str, name: str, analysis: dict,
                       change_5y_pct: float, patterns: list) -> str:
    summary = analysis.get("summary", {})
    osc_summary = analysis.get("oscillator_summary", {})
    ma_summary = analysis.get("ma_summary", {})

    signal = summary.get("signal", "Notr")
    trend = "yukselis" if change_5y_pct >= 0 else "dusme"

    # Find RSI value from oscillators
    rsi_val = 50.0
    for o in analysis.get("oscillators", []):
        if o["name"] == "RSI(14)":
            rsi_val = o["value"]
            break

    momentum = "asiri alim" if rsi_val > 70 else ("asiri satim" if rsi_val < 30 else "notr")

    pattern_text = ""
    if patterns:
        pattern_names = [p["pattern"] for p in patterns[:3]]
        pattern_text = f" Tespit edilen formasyonlar: {', '.join(pattern_names)}."

    return (
        f"📊 {name} ({symbol}) Teknik Analiz Ozeti\n\n"
        f"1) Genel Trend: 5 yillik degisim %{change_5y_pct:.2f} ({trend} trendi).\n\n"
        f"2) Osilator Durumu: {osc_summary.get('signal', 'Notr')} "
        f"(Al:{osc_summary.get('buy_count',0)} Sat:{osc_summary.get('sell_count',0)} "
        f"Notr:{osc_summary.get('neutral_count',0)}). RSI: {rsi_val:.1f} ({momentum}).\n\n"
        f"3) Hareketli Ortalama: {ma_summary.get('signal', 'Notr')} "
        f"(Al:{ma_summary.get('buy_count',0)} Sat:{ma_summary.get('sell_count',0)}).\n\n"
        f"4) Destek/Direnc: Pivot ve formasyon analizine bakiniz.{pattern_text}\n\n"
        f"5) Genel Sinyal: {signal}\n\n"
        f"⚠️ Bu analiz bilgi amaçlidir, yatirim tavsiyesi degildir."
    )


# ---------------------------------------------------------------------------
# Frontend HTML - Complete rewrite with TradingView charts, gauges, detail view
# ---------------------------------------------------------------------------

_FRONTEND_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>FinSignal Live - Teknik Analiz</title>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{
  --bg:#05070b;--surface:#0f131b;--ink:#e5ecf7;--muted:#8a97ad;
  --line:#273042;--accent:#3bb3ff;--panel:#0b0f16;
  --strong-buy:#00c853;--buy:#37d67a;--neutral:#a6b1c4;--sell:#ff6b6b;--strong-sell:#d50000;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI",Tahoma,sans-serif;color:var(--ink);background:radial-gradient(circle at 10% 10%,rgba(59,179,255,.14),transparent 35%),radial-gradient(circle at 90% 0%,rgba(55,214,122,.12),transparent 30%),var(--bg)}
.wrap{max-width:1400px;margin:0 auto;padding:16px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 8px 30px rgba(0,0,0,.35)}
.topbar{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
h1{font-size:22px}
.sub{color:var(--muted);font-size:13px}
.auth{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.controls{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center}
select,input,button{border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:13px;background:#111722;color:var(--ink)}
input::placeholder{color:#74839b}
button{background:var(--accent);border:0;color:#07101d;font-weight:600;cursor:pointer;white-space:nowrap}
button:hover{opacity:.9}
.btn-s{background:#1f2937;color:#dbe6f7;border:1px solid #334155}
.btn-w{background:#f59e0b;color:#111}
.btn-d{background:#6366f1;color:#fff}
.meta{color:var(--muted);font-size:12px;margin:6px 0}
.user{color:#9cc9ff;font-size:12px}

/* Table */
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;border-bottom:1px solid var(--line);padding:8px 6px}
thead th{color:#9ab0cf;font-weight:600;position:sticky;top:0;background:var(--surface);z-index:1}
tbody tr{cursor:pointer}
tbody tr:hover{background:rgba(59,179,255,.08)}

.sig{font-weight:700;font-size:12px;padding:3px 8px;border-radius:6px;display:inline-block}
.sig-guclu-al{background:rgba(0,200,83,.15);color:var(--strong-buy)}
.sig-al{background:rgba(55,214,122,.15);color:var(--buy)}
.sig-notr{background:rgba(166,177,196,.1);color:var(--neutral)}
.sig-sat{background:rgba(255,107,107,.15);color:var(--sell)}
.sig-guclu-sat{background:rgba(213,0,0,.15);color:var(--strong-sell)}
.chg-pos{color:var(--buy)}.chg-neg{color:var(--sell)}

.pagination{display:flex;gap:8px;align-items:center;justify-content:center;margin-top:10px}

/* Detail view */
#detailView{display:none}
.detail-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.detail-price{font-size:28px;font-weight:700}
.detail-change{font-size:16px}
.tf-tabs{display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap}
.tf-tabs button{font-size:12px;padding:6px 12px;border-radius:6px}
.tf-tabs button.active{background:var(--accent);color:#07101d}
#chartContainer{width:100%;height:400px;margin-bottom:14px;border-radius:10px;overflow:hidden}

/* Gauges */
.gauge-row{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin:14px 0}
.gauge-box{text-align:center;flex:1;min-width:180px;max-width:280px}
.gauge-box h4{margin-bottom:4px;font-size:13px;color:var(--muted)}
.gauge-label{font-weight:700;margin-top:4px;font-size:14px}
.gauge-svg{width:200px;height:120px}

/* Indicator tables */
.ind-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
@media(max-width:768px){.ind-grid{grid-template-columns:1fr}}
.ind-table{font-size:12px}
.ind-table th{font-size:11px}
.ind-table td{padding:5px 6px}

/* Pivot table */
.pivot-wrap{overflow-x:auto;margin:14px 0}
.pivot-table{font-size:12px;min-width:500px}
.pivot-table td,.pivot-table th{padding:5px 8px;text-align:center}

/* Analysis */
.analysis-box{border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:12px;margin-top:14px;display:none}
.analysis-box h3{margin:0 0 8px;font-size:14px}
.analysis-box p{color:#d0dcf1;line-height:1.5;white-space:pre-wrap;font-size:13px}

.footer{margin-top:12px;font-size:11px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}
.footer a{color:var(--accent);text-decoration:none}

/* Scroll container */
.tbl-wrap{overflow:auto;max-height:65vh}
</style>
</head>
<body>
<div class="wrap">
<div class="card">

<!-- LIST VIEW -->
<div id="listView">
  <div class="topbar">
    <div>
      <h1>FinSignal Live</h1>
      <p class="sub">Kapsamli Teknik Analiz Sistemi - BIST, Kripto, US Hisseler</p>
    </div>
    <div>
      <div class="auth">
        <input id="email" type="email" placeholder="mail@ornek.com" style="width:160px"/>
        <input id="password" type="password" placeholder="sifre" style="width:120px"/>
        <button id="loginBtn">Giris</button>
        <button id="logoutBtn" class="btn-w">Cikis</button>
      </div>
      <div class="user" id="userState">Oturum: Yok</div>
    </div>
  </div>

  <div class="controls">
    <select id="category" style="min-width:120px">
      <option value="">Tum kategoriler</option>
      <option value="BIST">BIST</option>
      <option value="Crypto">Crypto</option>
      <option value="Stock">Stock</option>
      <option value="ETF">ETF</option>
      <option value="Index">Index</option>
      <option value="Metals">Metals</option>
      <option value="Energy">Energy</option>
    </select>
    <input id="search" type="text" placeholder="Ara... (THYAO, BTC, Apple)" style="min-width:180px"/>
    <button id="refresh">Yenile</button>
  </div>

  <div class="meta" id="meta">Yukleniyor...</div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>Sembol</th>
          <th>Ad</th>
          <th>Kategori</th>
          <th>Fiyat</th>
          <th>% Fark</th>
          <th>Sinyal</th>
          <th>Al/Sat/Notr</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <div class="pagination" id="pagination"></div>
</div>

<!-- DETAIL VIEW -->
<div id="detailView">
  <div class="detail-header">
    <div>
      <button id="backBtn" class="btn-s">&lt; Geri</button>
      <span id="detailSymbol" style="font-size:18px;font-weight:700;margin-left:10px"></span>
      <span id="detailName" style="color:var(--muted);margin-left:6px"></span>
    </div>
    <div style="text-align:right">
      <div class="detail-price" id="detailPrice"></div>
      <div class="detail-change" id="detailChange"></div>
    </div>
  </div>

  <div class="tf-tabs" id="tfTabs">
    <button data-tf="15m">15 Dk</button>
    <button data-tf="1h">1 Saat</button>
    <button data-tf="1d" class="active">Gunluk</button>
    <button data-tf="1wk">Haftalik</button>
    <button data-tf="1mo">Aylik</button>
  </div>

  <div id="chartContainer"></div>

  <div class="gauge-row" id="gaugeRow"></div>

  <div class="ind-grid">
    <div>
      <h3 style="font-size:14px;margin-bottom:6px">Teknik Indikatorler</h3>
      <div class="tbl-wrap">
        <table class="ind-table">
          <thead><tr><th>Indikator</th><th>Deger</th><th>Sinyal</th></tr></thead>
          <tbody id="oscRows"></tbody>
        </table>
      </div>
    </div>
    <div>
      <h3 style="font-size:14px;margin-bottom:6px">Hareketli Ortalamalar</h3>
      <div class="tbl-wrap">
        <table class="ind-table">
          <thead><tr><th>Periyot</th><th>SMA</th><th>Sinyal</th><th>EMA</th><th>Sinyal</th></tr></thead>
          <tbody id="maRows"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="pivot-wrap">
    <h3 style="font-size:14px;margin-bottom:6px">Pivot Noktalari</h3>
    <table class="pivot-table">
      <thead><tr><th></th><th>Klasik</th><th>Fibonacci</th><th>Camarilla</th><th>Woodie</th><th>DeMark</th></tr></thead>
      <tbody id="pivotRows"></tbody>
    </table>
  </div>

  <div style="margin-top:12px">
    <button id="aiBtn" class="btn-d">AI Teknik Analiz</button>
  </div>
  <div class="analysis-box" id="analysisBox">
    <h3 id="analysisTitle">AI Analiz</h3>
    <p id="analysisText"></p>
  </div>
</div>

<div class="footer">
  <a href="/api/health">/api/health</a>
  <a href="/api/signals?categories=Crypto&max_assets=10">/api/signals</a>
  <a href="/docs">/docs</a>
</div>
</div>
</div>

<script>
// ---- State ----
let cache=[], currentUser=null, currentPage=0, totalAssets=0;
const PAGE_SIZE=50;
let currentDetailSymbol='', currentDetailTf='1d', chart=null;

// ---- DOM ----
const $=id=>document.getElementById(id);
const rowsEl=$('rows'),metaEl=$('meta'),catEl=$('category'),searchEl=$('search');
const refreshEl=$('refresh'),paginationEl=$('pagination');
const listView=$('listView'),detailView=$('detailView');
const emailEl=$('email'),passwordEl=$('password'),loginBtn=$('loginBtn'),logoutBtn=$('logoutBtn'),userState=$('userState');
const backBtn=$('backBtn'),aiBtn=$('aiBtn');
const analysisBox=$('analysisBox'),analysisTitle=$('analysisTitle'),analysisText=$('analysisText');

// ---- Auth ----
function getToken(){return localStorage.getItem('finsignal_token')||''}
function setToken(t){t?localStorage.setItem('finsignal_token',t):localStorage.removeItem('finsignal_token')}

function esc(t){return String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]||c))}

function sigClass(s){
  const m={'Guclu Al':'sig-guclu-al','Al':'sig-al','Notr':'sig-notr','Sat':'sig-sat','Guclu Sat':'sig-guclu-sat'};
  return m[s]||'sig-notr';
}
function sigColor(s){
  const m={'Guclu Al':'#00c853','Al':'#37d67a','Notr':'#a6b1c4','Sat':'#ff6b6b','Guclu Sat':'#d50000'};
  return m[s]||'#a6b1c4';
}

// ---- List View ----
function render(items){
  const term=searchEl.value.trim().toLowerCase();
  const filtered=items.filter(x=>{
    const txt=(x.name+' '+x.symbol).toLowerCase();
    return !term||txt.includes(term);
  });
  if(!filtered.length){
    rowsEl.innerHTML='<tr><td colspan="7">Filtreye uygun veri bulunamadi.</td></tr>';
    metaEl.textContent=`0 / ${totalAssets} varlik`;
    return;
  }
  rowsEl.innerHTML=filtered.map(x=>{
    const chgCls=x.daily_change_pct>=0?'chg-pos':'chg-neg';
    const chgStr=(x.daily_change_pct>=0?'+':'')+x.daily_change_pct.toFixed(2)+'%';
    const sc=sigClass(x.signal);
    const bsn=`${x.buy_count||0}/${x.sell_count||0}/${x.neutral_count||0}`;
    return `<tr data-sym="${esc(x.symbol)}">
      <td><b>${esc(x.symbol)}</b></td>
      <td>${esc(x.name)}</td>
      <td>${esc(x.category)}</td>
      <td>${x.current_price}</td>
      <td class="${chgCls}">${chgStr}</td>
      <td><span class="sig ${sc}">${esc(x.signal)}</span></td>
      <td>${bsn}</td>
    </tr>`;
  }).join('');
  metaEl.textContent=`${filtered.length} gosterilen / ${totalAssets} toplam`;

  document.querySelectorAll('#rows tr[data-sym]').forEach(tr=>{
    tr.onclick=()=>openDetail(tr.dataset.sym);
  });
}

function renderPagination(){
  const pages=Math.ceil(totalAssets/PAGE_SIZE);
  if(pages<=1){paginationEl.innerHTML='';return;}
  let h='';
  if(currentPage>0)h+=`<button class="btn-s" onclick="goPage(${currentPage-1})">&lt; Onceki</button>`;
  h+=`<span class="meta">Sayfa ${currentPage+1}/${pages}</span>`;
  if(currentPage<pages-1)h+=`<button class="btn-s" onclick="goPage(${currentPage+1})">Sonraki &gt;</button>`;
  paginationEl.innerHTML=h;
}

window.goPage=function(p){currentPage=p;loadSignals();}

async function loadSignals(){
  metaEl.textContent='Canli veri aliniyor...';
  rowsEl.innerHTML='';
  const cat=catEl.value;
  const offset=currentPage*PAGE_SIZE;
  let url=`/api/signals?max_assets=${PAGE_SIZE}&offset=${offset}`;
  if(cat)url+=`&categories=${encodeURIComponent(cat)}`;

  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),30000);
  try{
    const res=await fetch(url,{signal:controller.signal});
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||'Hata');
    totalAssets=data.total||data.count;
    cache=data.signals||[];
    render(cache);
    renderPagination();
  }catch(err){
    const msg=err.name==='AbortError'?'Zaman asimi. Kategori secip tekrar deneyin.':err.message;
    metaEl.textContent=`Hata: ${msg}`;
    rowsEl.innerHTML='<tr><td colspan="7">Veri alinamadi.</td></tr>';
  }finally{clearTimeout(timer);}
}

// ---- Detail View ----
async function openDetail(symbol){
  currentDetailSymbol=symbol;
  currentDetailTf='1d';
  listView.style.display='none';
  detailView.style.display='block';
  analysisBox.style.display='none';
  updateTfTabs();
  await loadDetail();
}

function closeDetail(){
  detailView.style.display='none';
  listView.style.display='block';
  if(chart){chart.remove();chart=null;}
}

function updateTfTabs(){
  document.querySelectorAll('#tfTabs button').forEach(b=>{
    b.classList.toggle('active',b.dataset.tf===currentDetailTf);
  });
}

async function loadDetail(){
  $('detailSymbol').textContent=currentDetailSymbol;
  $('detailName').textContent='';
  $('detailPrice').textContent='Yukleniyor...';
  $('detailChange').textContent='';
  $('oscRows').innerHTML='';
  $('maRows').innerHTML='';
  $('pivotRows').innerHTML='';
  $('gaugeRow').innerHTML='';

  try{
    const res=await fetch(`/api/asset-detail?symbol=${encodeURIComponent(currentDetailSymbol)}&timeframe=${currentDetailTf}`);
    const d=await res.json();
    if(!res.ok)throw new Error(d.detail||'Hata');

    $('detailName').textContent=d.name||'';
    $('detailPrice').textContent=d.price;
    const chg=d.daily_change_pct||0;
    const chgEl=$('detailChange');
    chgEl.textContent=(chg>=0?'+':'')+chg.toFixed(2)+'%';
    chgEl.style.color=chg>=0?'var(--buy)':'var(--sell)';

    renderChart(d.ohlcv||[]);
    renderGauges(d.summary,d.oscillator_summary,d.ma_summary);
    renderOscillators(d.oscillators||[]);
    renderMAs(d.moving_averages||[]);
    renderPivots(d.pivot_points||{});
  }catch(err){
    $('detailPrice').textContent='Hata: '+err.message;
  }
}

function renderChart(ohlcv){
  const container=$('chartContainer');
  container.innerHTML='';
  if(chart){chart.remove();chart=null;}
  if(!ohlcv.length)return;

  chart=LightweightCharts.createChart(container,{
    width:container.clientWidth,height:400,
    layout:{background:{color:'#0f131b'},textColor:'#e5ecf7'},
    grid:{vertLines:{color:'#1a2235'},horzLines:{color:'#1a2235'}},
    crosshair:{mode:0},
    timeScale:{borderColor:'#273042',timeVisible:true},
    rightPriceScale:{borderColor:'#273042'},
  });

  const candleSeries=chart.addCandlestickSeries({
    upColor:'#37d67a',downColor:'#ff6b6b',borderDownColor:'#ff6b6b',borderUpColor:'#37d67a',
    wickDownColor:'#ff6b6b',wickUpColor:'#37d67a',
  });

  const candles=ohlcv.map(c=>{
    const t=c.date.length<=10?c.date:c.date.replace(' ','T');
    return{time:t,open:c.open,high:c.high,low:c.low,close:c.close};
  });
  candleSeries.setData(candles);

  const volSeries=chart.addHistogramSeries({
    color:'rgba(59,179,255,0.3)',priceFormat:{type:'volume'},
    priceScaleId:'vol',
  });
  chart.priceScale('vol').applyOptions({scaleMargins:{top:0.8,bottom:0}});

  const vols=ohlcv.map(c=>{
    const t=c.date.length<=10?c.date:c.date.replace(' ','T');
    return{time:t,value:c.volume,color:c.close>=c.open?'rgba(55,214,122,0.4)':'rgba(255,107,107,0.4)'};
  });
  volSeries.setData(vols);

  chart.timeScale().fitContent();

  new ResizeObserver(()=>{
    chart&&chart.applyOptions({width:container.clientWidth});
  }).observe(container);
}

function renderGauges(summary,oscSummary,maSummary){
  const row=$('gaugeRow');
  row.innerHTML='';
  const items=[
    {title:'Genel Ozet',data:summary},
    {title:'Osilatorler',data:oscSummary},
    {title:'Hareketli Ort.',data:maSummary},
  ];
  items.forEach(item=>{
    const sig=item.data?.signal||'Notr';
    const box=document.createElement('div');
    box.className='gauge-box';
    box.innerHTML=`<h4>${item.title}</h4>${buildGaugeSVG(sig)}<div class="gauge-label" style="color:${sigColor(sig)}">${sig}</div>`;
    row.appendChild(box);
  });
}

function buildGaugeSVG(signal){
  const angles={'Guclu Sat':-72,'Sat':-36,'Notr':0,'Al':36,'Guclu Al':72};
  const angle=angles[signal]||0;
  const rad=(angle-90)*Math.PI/180;
  const cx=100,cy=95,r=70;
  const nx=cx+r*0.7*Math.cos(rad);
  const ny=cy+r*0.7*Math.sin(rad);

  return `<svg class="gauge-svg" viewBox="0 0 200 120">
    <path d="M 20 95 A 80 80 0 0 1 56 35" stroke="#d50000" stroke-width="8" fill="none" stroke-linecap="round"/>
    <path d="M 56 35 A 80 80 0 0 1 100 15" stroke="#ff6b6b" stroke-width="8" fill="none" stroke-linecap="round"/>
    <path d="M 100 15 A 80 80 0 0 1 144 35" stroke="#a6b1c4" stroke-width="8" fill="none" stroke-linecap="round"/>
    <path d="M 144 35 A 80 80 0 0 1 180 95" stroke="#37d67a" stroke-width="8" fill="none" stroke-linecap="round"/>
    <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="${sigColor(signal)}" stroke-width="3" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="5" fill="${sigColor(signal)}"/>
  </svg>`;
}

function renderOscillators(oscs){
  const tbody=$('oscRows');
  tbody.innerHTML=oscs.map(o=>{
    const sc=sigClass(o.signal);
    return `<tr><td>${esc(o.name)}</td><td>${o.value}</td><td><span class="sig ${sc}">${o.signal}</span></td></tr>`;
  }).join('');
}

function renderMAs(mas){
  const tbody=$('maRows');
  tbody.innerHTML=mas.map(m=>{
    const ssc=sigClass(m.sma_signal);
    const esc2=sigClass(m.ema_signal);
    return `<tr>
      <td>${esc(m.name)}</td>
      <td>${m.sma??'-'}</td><td><span class="sig ${ssc}">${m.sma_signal}</span></td>
      <td>${m.ema??'-'}</td><td><span class="sig ${esc2}">${m.ema_signal}</span></td>
    </tr>`;
  }).join('');
}

function renderPivots(pivots){
  const tbody=$('pivotRows');
  const levels=['r3','r2','r1','pp','s1','s2','s3'];
  const labels={'r3':'D3','r2':'D2','r1':'D1','pp':'Pivot','s1':'S1','s2':'S2','s3':'S3'};
  const systems=['classic','fibonacci','camarilla','woodie','demark'];
  tbody.innerHTML=levels.map(lv=>{
    const cells=systems.map(sys=>{
      const v=pivots[sys]?.[lv];
      return `<td>${v!=null?v:'-'}</td>`;
    }).join('');
    return `<tr><td><b>${labels[lv]}</b></td>${cells}</tr>`;
  }).join('');
}

// ---- Auth ----
async function loginRequest(){
  const email=emailEl.value.trim(),pw=passwordEl.value;
  if(!email||!pw){alert('Email ve sifre gerekli');return;}
  const res=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pw})});
  const data=await res.json();
  if(!res.ok)throw new Error(data.detail||'Hata');
  setToken(data.token);currentUser=data.email;
  userState.textContent=`Oturum: ${currentUser}`;
  passwordEl.value='';
}

async function refreshMe(){
  const token=getToken();
  if(!token){currentUser=null;userState.textContent='Oturum: Yok';return;}
  try{
    const res=await fetch('/api/auth/me',{headers:{Authorization:`Bearer ${token}`}});
    const data=await res.json();
    if(!res.ok)throw 0;
    currentUser=data.email;userState.textContent=`Oturum: ${currentUser}`;
  }catch{setToken('');currentUser=null;userState.textContent='Oturum: Yok';}
}

async function runAiAnalysis(){
  const token=getToken();
  if(!token){alert('AI analiz icin once giris yapmalisin.');return;}
  analysisBox.style.display='block';
  analysisTitle.textContent=`AI Analiz - ${currentDetailSymbol}`;
  analysisText.textContent='Analiz hazirlaniyor...';
  try{
    const res=await fetch(`/api/ai-analysis?symbol=${encodeURIComponent(currentDetailSymbol)}`,{headers:{Authorization:`Bearer ${token}`}});
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||'Hata');
    const note=data.cached?'(cache)':'(yeni)';
    analysisText.textContent=`${data.analysis}\\n\\nKaynak: ${note} | ${new Date(data.generated_at).toLocaleString('tr-TR')}`;
  }catch(err){analysisText.textContent=`Hata: ${err.message}`;}
}

// ---- Events ----
refreshEl.onclick=()=>{currentPage=0;loadSignals();};
catEl.onchange=()=>{currentPage=0;loadSignals();};
searchEl.oninput=()=>render(cache);
backBtn.onclick=closeDetail;
aiBtn.onclick=runAiAnalysis;

loginBtn.onclick=async()=>{try{await loginRequest();}catch(e){alert(e.message);}};
passwordEl.onkeydown=async e=>{if(e.key==='Enter'){try{await loginRequest();}catch(e2){alert(e2.message);}}};
logoutBtn.onclick=()=>{setToken('');currentUser=null;userState.textContent='Oturum: Yok';};

document.querySelectorAll('#tfTabs button').forEach(b=>{
  b.onclick=()=>{currentDetailTf=b.dataset.tf;updateTfTabs();loadDetail();};
});

// ---- Init ----
refreshMe();
loadSignals();
</script>
</body>
</html>"""
