"""Vercel serverless API entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from assets import ASSETS  # noqa: E402
from live_signals import generate_live_signals  # noqa: E402

app = FastAPI(title="FinSignal API", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!doctype html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>FinSignal Live</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --surface: #ffffff;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #e2e8f0;
      --accent: #0ea5e9;
      --buy: #16a34a;
      --sell: #dc2626;
      --hold: #64748b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, #dbeafe 0%, var(--bg) 45%);
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }
    h1 { margin: 0 0 6px; font-size: 28px; }
    .sub { margin: 0 0 14px; color: var(--muted); }
    .controls {
      display: grid;
      grid-template-columns: 1fr 1fr 120px auto;
      gap: 10px;
      margin-bottom: 14px;
    }
    @media (max-width: 800px) {
      .controls { grid-template-columns: 1fr 1fr; }
    }
    select, input, button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
      background: #fff;
    }
    button {
      background: var(--accent);
      border: 0;
      color: #fff;
      font-weight: 600;
      cursor: pointer;
    }
    .meta { color: var(--muted); font-size: 13px; margin: 8px 0 6px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 10px 8px; }
    .sig-buy { color: var(--buy); font-weight: 700; }
    .sig-sell { color: var(--sell); font-weight: 700; }
    .sig-hold { color: var(--hold); font-weight: 700; }
    .footer {
      margin-top: 14px;
      font-size: 12px;
      color: var(--muted);
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .footer a { color: var(--accent); text-decoration: none; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>FinSignal Live | Hoşgeldin, Ahmet Uğur</h1>
      <p class="sub">Altin, gumus ve diger varliklar icin canli teknik sinyal ekrani</p>
      <div class="controls">
        <select id="category">
          <option value="">Tum kategoriler</option>
          <option value="Metals">Metals</option>
          <option value="Energy">Energy</option>
          <option value="Index">Index</option>
          <option value="Crypto">Crypto</option>
          <option value="ETF">ETF</option>
          <option value="Stock">Stock</option>
        </select>
        <input id="search" type="text" placeholder="Varlik ara (gold, btc, apple...)" />
        <input id="limit" type="number" min="1" max="120" value="30" />
        <button id="refresh">Yenile</button>
      </div>
      <div class="meta" id="meta">Yukleniyor...</div>
      <div style="overflow:auto;">
        <table>
          <thead>
            <tr>
              <th>Varlik</th>
              <th>Kategori</th>
              <th>Sinyal</th>
              <th>Skor</th>
              <th>RSI</th>
              <th>Price Dev</th>
              <th>Fiyat</th>
              <th>Tarih</th>
              <th>Son Guncelleme</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <div class="footer">
        <a href="/api/health">/api/health</a>
        <a href="/api/signals?max_assets=10">/api/signals</a>
        <a href="/docs">/docs</a>
      </div>
    </div>
  </div>
  <script>
    const rowsEl = document.getElementById("rows");
    const metaEl = document.getElementById("meta");
    const categoryEl = document.getElementById("category");
    const searchEl = document.getElementById("search");
    const limitEl = document.getElementById("limit");
    const refreshEl = document.getElementById("refresh");
    let cache = [];

    function signalClass(signal) {
      const s = String(signal || "").toUpperCase();
      if (s === "BUY") return "sig-buy";
      if (s === "SELL") return "sig-sell";
      return "sig-hold";
    }

    function render(items) {
      const term = searchEl.value.trim().toLowerCase();
      const cat = categoryEl.value;
      const filtered = items.filter((x) => {
        const catOk = !cat || x.category === cat;
        const txt = (x.name + " " + x.symbol).toLowerCase();
        const searchOk = !term || txt.includes(term);
        return catOk && searchOk;
      });

      rowsEl.innerHTML = filtered.map((x) => `
        <tr>
          <td>${x.name} (${x.symbol})</td>
          <td>${x.category}</td>
          <td class="${signalClass(x.signal)}">${x.signal}</td>
          <td>${x.score}</td>
          <td>${x.rsi}</td>
          <td>${x.price_deviation}</td>
          <td>${x.current_price}</td>
          <td>${x.last_date}</td>
          <td>${x.updated_at || "-"}</td>
        </tr>
      `).join("");

      if (!filtered.length) {
        rowsEl.innerHTML = `<tr><td colspan="9">Filtreye uygun veri bulunamadi.</td></tr>`;
      }

      metaEl.textContent = `${filtered.length} gosterilen / ${items.length} alinan sinyal`;
    }

    async function load() {
      metaEl.textContent = "Canli veri aliniyor...";
      rowsEl.innerHTML = "";
      const maxAssets = Math.min(120, Math.max(1, Number(limitEl.value) || 30));
      const url = `/api/signals?max_assets=${maxAssets}`;
      try {
        const res = await fetch(url);
        const data = await res.json();
        const updatedAt = data.generated_at
          ? new Date(data.generated_at).toLocaleString("tr-TR")
          : new Date().toLocaleString("tr-TR");
        cache = (data.signals || []).map((x) => ({ ...x, updated_at: updatedAt }));
        render(cache);
      } catch (err) {
        metaEl.textContent = `Hata: ${err.message}`;
        rowsEl.innerHTML = `<tr><td colspan="9">Veri alinamadi.</td></tr>`;
      }
    }

    refreshEl.addEventListener("click", load);
    categoryEl.addEventListener("change", () => render(cache));
    searchEl.addEventListener("input", () => render(cache));
    load();
  </script>
</body>
</html>
    """


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "assets": len(ASSETS)}


@app.get("/api/signals")
def signals(
    categories: List[str] = Query(default=[]),
    max_assets: int = Query(default=25, ge=1, le=120),
):
    generated_at = datetime.now(timezone.utc).isoformat()
    selected_assets = ASSETS
    if categories:
        normalized = {c.lower() for c in categories}
        selected_assets = [a for a in ASSETS if a["category"].lower() in normalized]

    selected_assets = selected_assets[:max_assets]
    data = generate_live_signals(selected_assets)

    signals_data = [{**item, "updated_at": generated_at} for item in data]

    return {
        "count": len(data),
        "requested_assets": len(selected_assets),
        "generated_at": generated_at,
        "signals": signals_data,
    }
