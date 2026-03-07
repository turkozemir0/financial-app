# FinSignal — Financial Analysis System
## Codex Project Instructions

---

## Project Goal

Build a financial signal analysis system that:
- Downloads 5-year historical OHLCV data for 100+ financial assets
- Calculates technical indicators: MA50, MA200, RSI(14), price deviation
- Generates BUY / SELL / HOLD signals using a multi-indicator scoring system
- Displays results in a Streamlit dashboard with charts and filters

---

## Project Structure

Create the following folder and file structure:

```
financial-app/
├── data/
│   └── (CSV files will be saved here automatically)
├── src/
│   ├── assets.py          → asset list with symbols and categories
│   ├── fetch_data.py      → download and save historical data
│   ├── indicators.py      → calculate MA, RSI, price deviation
│   ├── signals.py         → scoring logic → BUY/SELL/HOLD
│   └── dashboard.py       → Streamlit UI
├── requirements.txt
└── README.md
```

---

## Step 1 — assets.py

Create a file `src/assets.py` that defines a list of assets to analyze.

Each asset should have:
- `symbol`: the ticker used by yfinance
- `name`: human readable name
- `category`: one of Metals / Energy / Index / Crypto / ETF

Include at least the following assets:

```python
ASSETS = [
    # Metals
    {"symbol": "GC=F",   "name": "Gold",       "category": "Metals"},
    {"symbol": "SI=F",   "name": "Silver",      "category": "Metals"},
    {"symbol": "PL=F",   "name": "Platinum",    "category": "Metals"},
    {"symbol": "HG=F",   "name": "Copper",      "category": "Metals"},

    # Energy
    {"symbol": "BZ=F",   "name": "Brent Oil",   "category": "Energy"},
    {"symbol": "CL=F",   "name": "WTI Oil",     "category": "Energy"},
    {"symbol": "NG=F",   "name": "Natural Gas",  "category": "Energy"},

    # Indices
    {"symbol": "^GSPC",  "name": "S&P 500",     "category": "Index"},
    {"symbol": "^IXIC",  "name": "Nasdaq",       "category": "Index"},
    {"symbol": "^DJI",   "name": "Dow Jones",    "category": "Index"},
    {"symbol": "^GDAXI", "name": "DAX",          "category": "Index"},
    {"symbol": "^FTSE",  "name": "FTSE 100",     "category": "Index"},
    {"symbol": "^N225",  "name": "Nikkei 225",   "category": "Index"},
    {"symbol": "^BVSP",  "name": "Bovespa",      "category": "Index"},
    {"symbol": "^HSI",   "name": "Hang Seng",    "category": "Index"},

    # Crypto
    {"symbol": "BTC-USD", "name": "Bitcoin",    "category": "Crypto"},
    {"symbol": "ETH-USD", "name": "Ethereum",   "category": "Crypto"},
    {"symbol": "BNB-USD", "name": "BNB",        "category": "Crypto"},
    {"symbol": "SOL-USD", "name": "Solana",     "category": "Crypto"},
    {"symbol": "XRP-USD", "name": "XRP",        "category": "Crypto"},
    {"symbol": "ADA-USD", "name": "Cardano",    "category": "Crypto"},
    {"symbol": "AVAX-USD","name": "Avalanche",  "category": "Crypto"},
    {"symbol": "DOGE-USD","name": "Dogecoin",   "category": "Crypto"},

    # ETFs
    {"symbol": "SPY",    "name": "SPDR S&P 500 ETF",     "category": "ETF"},
    {"symbol": "QQQ",    "name": "Invesco Nasdaq ETF",    "category": "ETF"},
    {"symbol": "GLD",    "name": "Gold ETF",              "category": "ETF"},
    {"symbol": "SLV",    "name": "Silver ETF",            "category": "ETF"},
    {"symbol": "USO",    "name": "Oil ETF",               "category": "ETF"},
    {"symbol": "TLT",    "name": "20Y Treasury ETF",      "category": "ETF"},
    {"symbol": "XLE",    "name": "Energy Sector ETF",     "category": "ETF"},
    {"symbol": "XLF",    "name": "Financials ETF",        "category": "ETF"},
    {"symbol": "XLK",    "name": "Technology ETF",        "category": "ETF"},
    {"symbol": "XLV",    "name": "Healthcare ETF",        "category": "ETF"},
    {"symbol": "ARKK",   "name": "ARK Innovation ETF",    "category": "ETF"},
    {"symbol": "EEM",    "name": "Emerging Markets ETF",  "category": "ETF"},
    {"symbol": "VNQ",    "name": "Real Estate ETF",       "category": "ETF"},

    # Stocks
    {"symbol": "AAPL",   "name": "Apple",        "category": "Stock"},
    {"symbol": "MSFT",   "name": "Microsoft",    "category": "Stock"},
    {"symbol": "GOOGL",  "name": "Alphabet",     "category": "Stock"},
    {"symbol": "AMZN",   "name": "Amazon",       "category": "Stock"},
    {"symbol": "NVDA",   "name": "NVIDIA",       "category": "Stock"},
    {"symbol": "TSLA",   "name": "Tesla",        "category": "Stock"},
    {"symbol": "META",   "name": "Meta",         "category": "Stock"},
    {"symbol": "JPM",    "name": "JPMorgan",     "category": "Stock"},
    {"symbol": "BAC",    "name": "Bank of America", "category": "Stock"},
    {"symbol": "XOM",    "name": "ExxonMobil",   "category": "Stock"},
    {"symbol": "JNJ",    "name": "Johnson & Johnson", "category": "Stock"},
    {"symbol": "WMT",    "name": "Walmart",      "category": "Stock"},
    {"symbol": "BABA",   "name": "Alibaba",      "category": "Stock"},
    {"symbol": "TSM",    "name": "TSMC",         "category": "Stock"},
    {"symbol": "NFLX",   "name": "Netflix",      "category": "Stock"},
]
```

---

## Step 2 — fetch_data.py

Create `src/fetch_data.py`.

Requirements:
- Use `yfinance` to download data
- Download 5 years of daily OHLCV data for every asset in `ASSETS`
- For each asset, save a CSV file to `data/{symbol}.csv` (replace special characters like `=`, `^`, `-` with `_` in filename)
- Columns must be: `date, open, close, high, low, volume`
- Drop rows where close is NaN
- Print progress as each asset is downloaded
- If download fails for an asset, print a warning and continue

```python
# Example output CSV format:
# date,open,close,high,low,volume
# 2019-01-02,1282.3,1290.5,1291.0,1280.0,182340
```

Add a `if __name__ == "__main__"` block that downloads all assets when the script is run directly.

---

## Step 3 — indicators.py

Create `src/indicators.py`.

Requirements:
- Accept a pandas DataFrame with columns: `date, open, close, high, low, volume`
- Calculate and return a new DataFrame with these additional columns:

**Moving Averages:**
- `ma50`: 50-day simple moving average of close
- `ma200`: 200-day simple moving average of close
- `ma_signal`: `"bullish"` if ma50 > ma200, else `"bearish"`

**RSI:**
- `rsi`: 14-period RSI
- Do not use any external library, implement RSI from scratch using pandas

**Price Deviation:**
- `avg_5yr`: mean of close over the entire loaded history
- `price_deviation`: `close / avg_5yr` (ratio, not percentage)

Do not use `ta`, `ta-lib`, or `pandas_ta`. Implement all calculations manually with pandas.

---

## Step 4 — signals.py

Create `src/signals.py`.

Requirements:
- Load each asset's CSV from the `data/` folder
- Run `indicators.py` calculations on it
- Take the **last row** (most recent data point)
- Apply this scoring system to the last row:

```
score = 0

MA score:
  if ma_signal == "bullish"  → score += 1
  if ma_signal == "bearish"  → score -= 1

RSI score:
  if rsi < 30                → score += 1  (oversold → likely to go up)
  if rsi > 70                → score -= 1  (overbought → likely to go down)

Price deviation score:
  if price_deviation < 0.85  → score += 1  (undervalued)
  if price_deviation > 1.15  → score -= 1  (overvalued)

Final signal:
  score >= 2   → "BUY"
  score <= -2  → "SELL"
  else         → "HOLD"
```

- Return a list of dicts, one per asset:

```python
{
  "symbol": "GC=F",
  "name": "Gold",
  "category": "Metals",
  "signal": "BUY",
  "score": 2,
  "rsi": 28.4,
  "ma_signal": "bullish",
  "price_deviation": 0.82,
  "current_price": 1923.5,
  "last_date": "2024-03-15"
}
```

- If CSV file for an asset does not exist, skip it with a warning.

Add a `if __name__ == "__main__"` block that prints all signals as a formatted table.

---

## Step 5 — dashboard.py

Create `src/dashboard.py` as a Streamlit app.

Requirements:

**Sidebar filters:**
- Category multiselect (All, Metals, Energy, Index, Crypto, ETF, Stock)
- Signal filter (All, BUY, SELL, HOLD)
- Search box by asset name

**Main table:**
- Show all filtered assets with columns: Name, Category, Signal, Score, RSI, Price Deviation, Current Price, Last Date
- Color code the Signal column: BUY = green, SELL = red, HOLD = gray

**Detail view:**
- When user clicks on (or selects) an asset from the table, show:
  - Line chart of closing price with MA50 and MA200 overlaid
  - RSI chart with horizontal lines at 30 and 70
  - Summary stats: current price, 5yr avg, price deviation, RSI, signal score

**Data loading:**
- Call `signals.py` to get all signals on app start
- Add a "Refresh Data" button that re-runs the signal calculation

Use `st.set_page_config(layout="wide")` for full width layout.
Use `plotly.express` or `plotly.graph_objects` for charts.

---

## Step 6 — requirements.txt

Create `requirements.txt` with:

```
yfinance
pandas
numpy
streamlit
plotly
```

---

## Step 7 — README.md

Create `README.md` with:

```markdown
# FinSignal

Financial signal analysis system for 100+ assets.

## Setup

pip install -r requirements.txt

## Download Data

python src/fetch_data.py

## View Signals (terminal)

python src/signals.py

## Launch Dashboard

streamlit run src/dashboard.py
```

---

## Implementation Order

Build in this exact order:
1. `src/assets.py`
2. `src/fetch_data.py` → test by downloading 3 assets
3. `src/indicators.py` → test on one CSV file
4. `src/signals.py` → test on all downloaded CSVs
5. `src/dashboard.py`
6. `requirements.txt` and `README.md`

After completing each file, confirm it runs without errors before moving to the next.

---

## Important Notes

- Do NOT use `ta`, `ta-lib`, or `pandas_ta` — implement indicators manually with pandas
- All file paths should be relative to the project root (`financial-app/`)
- Handle download errors gracefully — if an asset fails, skip and continue
- All DataFrames must have `date` as a proper datetime column (use `pd.to_datetime`)
- CSV filenames: replace `=`, `^`, `-` with `_` (e.g. `GC=F` → `GC_F.csv`, `^GSPC` → `_GSPC.csv`)
