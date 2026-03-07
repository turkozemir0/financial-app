"""Vercel serverless API entrypoint."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib import request

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from assets import ASSETS  # noqa: E402
from indicators import add_indicators  # noqa: E402
from live_signals import fetch_history, generate_live_signals  # noqa: E402

app = FastAPI(title="FinSignal API", version="1.2.0")

USERS_FILE = Path("/tmp/finsignal_users.json")
USERS_LOCK = threading.Lock()
ANALYSIS_CACHE: Dict[str, Dict[str, object]] = {}
ANALYSIS_TTL_SECONDS = 12 * 60 * 60
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
SECRET_KEY = os.environ.get("APP_SECRET", "change-this-secret-in-production")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class AuthPayload(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)


def _normalize_email(email: str) -> str:
    value = email.lower().strip()
    if "@" not in value or "." not in value.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Gecerli bir email giriniz")
    return value


def _load_users() -> Dict[str, Dict[str, str]]:
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_users(users: Dict[str, Dict[str, str]]) -> None:
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False), encoding="utf-8")


def _hash_password(password: str, salt_hex: Optional[str] = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${hashed.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    expected = _hash_password(password, salt_hex=salt_hex).split("$", 1)[1]
    return hmac.compare_digest(expected, digest_hex)


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
        return "AI API key ayarli degil. Bu nedenle lokal analiz ozeti donuldu."

    body = {
        "model": OPENAI_MODEL,
        "input": prompt,
        "max_output_tokens": 350,
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

    with request.urlopen(req, timeout=25) as res:
        payload = json.loads(res.read().decode("utf-8"))

    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    # Fallback parse for nested output structure.
    try:
        chunks = payload.get("output", [])
        texts: List[str] = []
        for item in chunks:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
        return "\n".join(t for t in texts if t).strip() or "AI cevabi bos dondu."
    except Exception:
        return "AI cevabi parse edilemedi."


def _local_ai_fallback(symbol: str, name: str, summary: Dict[str, float]) -> str:
    trend = "yukselis" if summary["change_5y_pct"] >= 0 else "dusme"
    valuation = "pahali" if summary["price_deviation"] > 1.15 else ("ucuz" if summary["price_deviation"] < 0.85 else "denge")
    momentum = "asiri alim" if summary["rsi"] > 70 else ("asiri satim" if summary["rsi"] < 30 else "nötr")

    return (
        f"{name} ({symbol}) icin 5 yillik fiyat degisimi %{summary['change_5y_pct']:.2f} ve genel trend {trend}. "
        f"RSI {summary['rsi']:.2f} ile momentum {momentum} bolgesinde. "
        f"MA50/MA200 durumu {summary['ma_signal']}. Fiyatin 5 yillik ortalamaya gore konumu {valuation} seviyede "
        f"(sapma: {summary['price_deviation']:.3f}). "
        "Bu sinyal karar destek amaclidir; tek basina alim-satim tavsiyesi degildir."
    )


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
      --bg: #05070b;
      --surface: #0f131b;
      --ink: #e5ecf7;
      --muted: #8a97ad;
      --line: #273042;
      --accent: #3bb3ff;
      --buy: #37d67a;
      --sell: #ff6b6b;
      --hold: #a6b1c4;
      --panel: #0b0f16;
      --warn: #f59e0b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 10%, rgba(59, 179, 255, 0.14), transparent 35%),
        radial-gradient(circle at 90% 0%, rgba(55, 214, 122, 0.12), transparent 30%),
        var(--bg);
    }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 24px; }
    .card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 12px 35px rgba(0, 0, 0, 0.35);
      backdrop-filter: blur(6px);
    }
    .topbar { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
    h1 { margin: 0 0 6px; font-size: 28px; }
    .sub { margin: 0 0 14px; color: var(--muted); }
    .auth {
      display: grid;
      grid-template-columns: 220px 160px auto auto auto;
      gap: 8px;
      align-items: center;
      min-width: 340px;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr 1fr 120px auto;
      gap: 10px;
      margin-bottom: 14px;
    }
    @media (max-width: 980px) {
      .auth { grid-template-columns: 1fr 1fr 1fr; }
      .controls { grid-template-columns: 1fr 1fr; }
    }
    select, input, button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
      background: #111722;
      color: var(--ink);
    }
    input::placeholder { color: #74839b; }
    button { background: var(--accent); border: 0; color: #07101d; font-weight: 600; cursor: pointer; }
    .btn-secondary { background: #1f2937; color: #dbe6f7; border: 1px solid #334155; }
    .btn-warn { background: var(--warn); color: #111; }
    .meta { color: var(--muted); font-size: 13px; margin: 8px 0 6px; }
    .user { color: #9cc9ff; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }
    thead th { color: #9ab0cf; font-weight: 600; }
    tbody tr:hover { background: rgba(59, 179, 255, 0.08); }
    .sig-buy { color: var(--buy); font-weight: 700; }
    .sig-sell { color: var(--sell); font-weight: 700; }
    .sig-hold { color: var(--hold); font-weight: 700; }
    .tiny-btn { padding: 6px 10px; font-size: 12px; border-radius: 8px; }
    .analysis {
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
      padding: 12px;
      display: none;
    }
    .analysis h3 { margin: 0 0 8px; font-size: 15px; }
    .analysis p { margin: 0; color: #d0dcf1; line-height: 1.55; white-space: pre-wrap; }
    .footer { margin-top: 14px; font-size: 12px; color: var(--muted); display: flex; gap: 10px; flex-wrap: wrap; }
    .footer a { color: var(--accent); text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="topbar">
        <div>
          <h1>FinSignal Live | Hoşgeldin, Ahmet Uğur</h1>
          <p class="sub">Altin, gumus ve diger varliklar icin canli teknik sinyal ekrani</p>
        </div>
        <div>
          <div class="auth">
            <input id="email" type="email" placeholder="mail@ornek.com" />
            <input id="password" type="password" placeholder="sifre" />
            <button id="registerBtn" class="btn-secondary">Kayit Ol</button>
            <button id="loginBtn">Giris Yap</button>
            <button id="logoutBtn" class="btn-warn">Cikis</button>
          </div>
          <div class="user" id="userState">Oturum: Yok</div>
        </div>
      </div>

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
              <th>AI</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>

      <div class="analysis" id="analysisBox">
        <h3 id="analysisTitle">AI Analiz</h3>
        <p id="analysisText"></p>
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
    const analysisBox = document.getElementById("analysisBox");
    const analysisTitle = document.getElementById("analysisTitle");
    const analysisText = document.getElementById("analysisText");
    const emailEl = document.getElementById("email");
    const passwordEl = document.getElementById("password");
    const registerBtn = document.getElementById("registerBtn");
    const loginBtn = document.getElementById("loginBtn");
    const logoutBtn = document.getElementById("logoutBtn");
    const userState = document.getElementById("userState");

    let cache = [];
    let currentUser = null;

    function getToken() {
      return localStorage.getItem("finsignal_token") || "";
    }

    function setToken(token) {
      if (token) localStorage.setItem("finsignal_token", token);
      else localStorage.removeItem("finsignal_token");
    }

    function signalClass(signal) {
      const s = String(signal || "").toUpperCase();
      if (s === "BUY") return "sig-buy";
      if (s === "SELL") return "sig-sell";
      return "sig-hold";
    }

    function esc(text) {
      return String(text ?? "").replace(/[&<>\"]/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[ch]);
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

      if (!filtered.length) {
        rowsEl.innerHTML = `<tr><td colspan="10">Filtreye uygun veri bulunamadi.</td></tr>`;
        metaEl.textContent = `0 gosterilen / ${items.length} alinan sinyal`;
        return;
      }

      rowsEl.innerHTML = filtered.map((x) => `
        <tr>
          <td>${esc(x.name)} (${esc(x.symbol)})</td>
          <td>${esc(x.category)}</td>
          <td class="${signalClass(x.signal)}">${esc(x.signal)}</td>
          <td>${x.score}</td>
          <td>${x.rsi}</td>
          <td>${x.price_deviation}</td>
          <td>${x.current_price}</td>
          <td>${esc(x.last_date)}</td>
          <td>${esc(x.updated_at || "-")}</td>
          <td><button class="tiny-btn btn-secondary" data-symbol="${esc(x.symbol)}" data-name="${esc(x.name)}">AI Analiz</button></td>
        </tr>
      `).join("");

      metaEl.textContent = `${filtered.length} gosterilen / ${items.length} alinan sinyal`;

      document.querySelectorAll("button[data-symbol]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const symbol = btn.getAttribute("data-symbol");
          const name = btn.getAttribute("data-name");
          await runAiAnalysis(symbol, name);
        });
      });
    }

    async function loadSignals() {
      metaEl.textContent = "Canli veri aliniyor...";
      rowsEl.innerHTML = "";
      const maxAssets = Math.min(120, Math.max(1, Number(limitEl.value) || 30));
      try {
        const res = await fetch(`/api/signals?max_assets=${maxAssets}`);
        const data = await res.json();
        const updatedAt = data.generated_at ? new Date(data.generated_at).toLocaleString("tr-TR") : new Date().toLocaleString("tr-TR");
        cache = (data.signals || []).map((x) => ({ ...x, updated_at: updatedAt }));
        render(cache);
      } catch (err) {
        metaEl.textContent = `Hata: ${err.message}`;
        rowsEl.innerHTML = `<tr><td colspan="10">Veri alinamadi.</td></tr>`;
      }
    }

    async function authRequest(path) {
      const email = emailEl.value.trim();
      const password = passwordEl.value;
      if (!email || !password) {
        alert("Email ve sifre gerekli");
        return;
      }
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Auth hatasi");
      }
      setToken(data.token);
      currentUser = data.email;
      userState.textContent = `Oturum: ${currentUser}`;
      passwordEl.value = "";
    }

    async function refreshMe() {
      const token = getToken();
      if (!token) {
        currentUser = null;
        userState.textContent = "Oturum: Yok";
        return;
      }
      try {
        const res = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${token}` } });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Oturum gecersiz");
        currentUser = data.email;
        userState.textContent = `Oturum: ${currentUser}`;
      } catch {
        setToken("");
        currentUser = null;
        userState.textContent = "Oturum: Yok";
      }
    }

    async function runAiAnalysis(symbol, name) {
      const token = getToken();
      if (!token) {
        alert("AI analiz icin once giris yapmalisin.");
        return;
      }
      analysisBox.style.display = "block";
      analysisTitle.textContent = `AI Analiz - ${name} (${symbol})`;
      analysisText.textContent = "Analiz hazirlaniyor...";

      try {
        const res = await fetch(`/api/ai-analysis?symbol=${encodeURIComponent(symbol)}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Analiz hatasi");
        const cacheNote = data.cached ? "(cache)" : "(new)";
        analysisText.textContent = `${data.analysis}\n\nKaynak: ${cacheNote} | Guncelleme: ${new Date(data.generated_at).toLocaleString("tr-TR")}`;
      } catch (err) {
        analysisText.textContent = `Hata: ${err.message}`;
      }
    }

    refreshEl.addEventListener("click", loadSignals);
    categoryEl.addEventListener("change", () => render(cache));
    searchEl.addEventListener("input", () => render(cache));

    registerBtn.addEventListener("click", async () => {
      try { await authRequest("/api/auth/register"); }
      catch (err) { alert(err.message); }
    });

    loginBtn.addEventListener("click", async () => {
      try { await authRequest("/api/auth/login"); }
      catch (err) { alert(err.message); }
    });

    logoutBtn.addEventListener("click", () => {
      setToken("");
      currentUser = null;
      userState.textContent = "Oturum: Yok";
    });

    refreshMe();
    loadSignals();
  </script>
</body>
</html>
    """


@app.post("/api/auth/register")
def register(payload: AuthPayload):
    email = _normalize_email(payload.email)

    with USERS_LOCK:
        users = _load_users()
        if email in users:
            raise HTTPException(status_code=409, detail="Bu email zaten kayitli")
        users[email] = {
            "password_hash": _hash_password(payload.password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_users(users)

    token = _create_token(email)
    return {"ok": True, "email": email, "token": token}


@app.post("/api/auth/login")
def login(payload: AuthPayload):
    email = _normalize_email(payload.email)
    users = _load_users()
    user = users.get(email)
    if not user or not _verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email veya sifre hatali")

    token = _create_token(email)
    return {"ok": True, "email": email, "token": token}


@app.get("/api/auth/me")
def me(request_obj: Request):
    email = _get_current_user(request_obj)
    return {"ok": True, "email": email}


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
    if df.empty or len(df) < 220:
        raise HTTPException(status_code=404, detail="Yeterli fiyat verisi yok")

    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    first_price = float(enriched.iloc[0]["close"])
    current_price = float(last["close"])
    change_5y_pct = ((current_price / first_price) - 1.0) * 100.0 if first_price else 0.0

    summary = {
        "current_price": current_price,
        "rsi": float(last["rsi"]),
        "ma_signal": str(last["ma_signal"]),
        "price_deviation": float(last["price_deviation"]),
        "change_5y_pct": change_5y_pct,
    }

    prompt = (
        "Asagidaki varlik icin kisa ve net bir analiz yaz. Cikti turkce olsun. "
        "Basliklar: 1) 5 Yillik Karsilastirma 2) Teknik Durum 3) Riskler 4) Aksiyon Ozeti. "
        "Yatirim tavsiyesi degildir notu ekle.\n\n"
        f"Varlik: {asset['name']} ({ticker})\n"
        f"5Y Degisim (%): {summary['change_5y_pct']:.2f}\n"
        f"Guncel Fiyat: {summary['current_price']:.4f}\n"
        f"RSI(14): {summary['rsi']:.2f}\n"
        f"MA Sinyali: {summary['ma_signal']}\n"
        f"Price Deviation: {summary['price_deviation']:.4f}\n"
    )

    analysis_text = _local_ai_fallback(ticker, asset["name"], summary)
    try:
        if OPENAI_API_KEY:
            analysis_text = _call_openai_analysis(prompt)
    except Exception:
        # Keep local fallback response if model call fails.
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
