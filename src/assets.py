"""Asset universe for the financial signal system.

Includes ~500+ BIST stocks, 50 crypto, US stocks, ETFs, indices, metals, energy.
"""

from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# BIST stock tickers (Yahoo Finance uses .IS suffix)
# ---------------------------------------------------------------------------

_BIST_TICKERS = [
    "ACSEL", "ADEL", "ADESE", "AEFES", "AFYON", "AGESA", "AGHOL", "AHGAZ",
    "AKBNK", "AKCNS", "AKENR", "AKFGY", "AKFYE", "AKGRT", "AKMGY", "AKSA",
    "AKSEN", "AKSGY", "AKSUE", "AKYHO", "ALARK", "ALBRK", "ALCAM", "ALFAS",
    "ALGYO", "ALKA", "ALKIM", "ALMAD", "ALTNY", "ALVES", "ANELE", "ANGEN",
    "ANHYT", "ANSGR", "ARCLK", "ARDYZ", "ARENA", "ARSAN", "ARTMS", "ARZUM",
    "ASELS", "ASGYO", "ASTOR", "ATAGY", "ATAKP", "ATATP", "ATEKS", "ATLAS",
    "ATSYH", "AVGYO", "AVHOL", "AVOD", "AVPGY", "AVTUR", "AYCES", "AYDEM",
    "AYEN", "AYGAZ", "AZTEK", "BAGFS", "BAKAB", "BALAT", "BANVT", "BARMA",
    "BASCM", "BASGZ", "BASTE", "BAYRK", "BEYAZ", "BFREN", "BIENY", "BIGCH",
    "BIMAS", "BINHO", "BIOEN", "BIZIM", "BJKAS", "BLCYT", "BMSCH", "BMSTL",
    "BNTAS", "BOSSA", "BRISA", "BRKSN", "BRKVY", "BRLSM", "BRMEN", "BRSAN",
    "BRYAT", "BSOKE", "BTCIM", "BUCIM", "BURCE", "BURVA", "BVSAN", "BYDNR",
    "CANTE", "CASA", "CATES", "CCOLA", "CELHA", "CEMAS", "CEMTS", "CEOEM",
    "CIMSA", "CLEBI", "CMBTN", "CONSE", "COSMO", "CRDFA", "CRFSA", "CUSAN",
    "CVKMD", "CWENE", "DAGI", "DAPGM", "DARDL", "DENGE", "DERHL", "DERIM",
    "DESA", "DESPC", "DEVA", "DGNMO", "DIRIT", "DITAS", "DJIST", "DMRGD",
    "DMSAS", "DNISI", "DOAS", "DOBUR", "DOCO", "DOHOL", "DOKTA", "DURDO",
    "DYOBY", "DZGYO", "ECILC", "ECZYT", "EDIP", "EGEEN", "EGEPO", "EGPRO",
    "EGSER", "EKGYO", "EKIZ", "EKOS", "EKSUN", "ELITE", "EMKEL", "EMNIS",
    "ENERY", "ENJSA", "ENKAI", "ENSRI", "EPLAS", "ERBOS", "ERCB", "EREGL",
    "ERSU", "ESCAR", "ESCOM", "ESEN", "ETILR", "ETYAT", "EUHOL", "EUPWR",
    "EUREN", "EUYO", "EYGYO", "FADE", "FENER", "FLAP", "FMIZP", "FONET",
    "FORMT", "FORTE", "FRIGO", "FROTO", "FZLGY", "GARAN", "GARFA", "GEDIK",
    "GEDZA", "GENIL", "GENTS", "GEREL", "GESAN", "GIPTS", "GLBMD", "GLCVY",
    "GLRYH", "GLYHO", "GMTAS", "GOKNR", "GOLTS", "GOODY", "GOZDE", "GRSEL",
    "GRTRK", "GSDDE", "GSDHO", "GSRAY", "GUBRF", "GWIND", "GZNMI", "HATEK",
    "HDFGS", "HEDEF", "HEKTS", "HKTM", "HLGYO", "HTTBT", "HUBVC", "HUNER",
    "HURGZ", "ICBCT", "IDEAS", "IEYHO", "IHEVA", "IHGZT", "IHLAS", "IHLGM",
    "IHYAY", "IMASM", "INDES", "INFO", "INTEM", "INVEO", "INVES", "IPEKE",
    "ISDMR", "ISFIN", "ISGSY", "ISGYO", "ISMEN", "ISSEN", "ITTFH", "IZENR",
    "IZFAS", "IZINV", "IZMDC", "JANTS", "KAPLM", "KARDM", "KARSN", "KARTN",
    "KARYE", "KATMR", "KAYSE", "KBORU", "KCAER", "KCHOL", "KENT", "KERVN",
    "KERVT", "KFEIN", "KGYO", "KIMMR", "KLGYO", "KLKIM", "KLMSN", "KLNMA",
    "KLRHO", "KLSER", "KLSYN", "KMPUR", "KNFRT", "KONKA", "KONTR", "KONYA",
    "KOPOL", "KORDS", "KOSSA", "KOZAA", "KOZAL", "KRDMA", "KRDMB", "KRDMD",
    "KRGYO", "KRONT", "KRPLS", "KRSTL", "KRVGD", "KTLEV", "KTSKR", "KUTPO",
    "KUVVA", "KUYAS", "KZBGY", "KZGYO", "LIDER", "LIDFA", "LILAK", "LINK",
    "LKMNH", "LOGO", "LRSHO", "LUKSK", "MACKO", "MAGEN", "MAKIM", "MAKTK",
    "MANAS", "MARKA", "MARTI", "MAVI", "MEDTR", "MEGAP", "MEKAG", "MERCN",
    "MERIT", "MERKO", "MGROS", "MHRGY", "MIATK", "MIPAZ", "MMCAS", "MNDRS",
    "MNDTR", "MOBTL", "MOGAN", "MPARK", "MRDIN", "MRGYO", "MRSHL", "MSGYO",
    "MTRKS", "MTRYO", "MZHLD", "NATEN", "NETAS", "NIBAS", "NUGYO", "NUHCM",
    "OBAMS", "ODAS", "ODINE", "OFSYM", "ONCSM", "ORCAY", "ORGE", "ORMA",
    "OSMEN", "OSTIM", "OTKAR", "OTTO", "OYAKC", "OYLUM", "OYYAT", "OZGYO",
    "OZKGY", "OZRDN", "OZSUB", "OZTK", "PAGYO", "PAMEL", "PAPIL", "PARSN",
    "PASEU", "PCILT", "PEKGY", "PENGD", "PENTA", "PETKM", "PETUN", "PGSUS",
    "PINSU", "PKART", "PKENT", "PLTUR", "PNLSN", "PNSUT", "POLHO", "POLTK",
    "PRDGS", "PRKAB", "PRKME", "PRTAS", "PRZMA", "PSDTC", "PSGYO", "QUAGR",
    "RALYH", "RAYSG", "REEDR", "RGYAS", "RNPOL", "RODRG", "ROYAL", "RUBNS",
    "RYGYO", "RYSAS", "SAFKR", "SAFIX", "SAHOL", "SAMAT", "SANEL", "SANFM",
    "SANKO", "SARKY", "SASA", "SAYAS", "SDTTR", "SEGYO", "SEKFK", "SEKUR",
    "SELEC", "SELGD", "SELVA", "SEYKM", "SILVR", "SISE", "SKBNK", "SKYLP",
    "SMART", "SMRTG", "SNGYO", "SNICA", "SNKRN", "SNPAM", "SOKM", "SONME",
    "SRVGY", "SUMAS", "SUNTK", "SUWEN", "TABGD", "TARKM", "TATGD", "TAVHL",
    "TCELL", "TDGYO", "TEKTU", "TERA", "TEZOL", "TGSAS", "THYAO", "TKFEN",
    "TKNSA", "TLMAN", "TMPOL", "TMSN", "TNZTP", "TOASO", "TRCAS", "TRGYO",
    "TRILC", "TSGYO", "TSKB", "TSPOR", "TTKOM", "TTRAK", "TUCLK", "TUKAS",
    "TUPRS", "TUREX", "TURSG", "UFUK", "UGUR", "ULUFA", "ULUSE", "ULUUN",
    "UNLU", "USAK", "UZERB", "VAKBN", "VAKFN", "VAKKO", "VANGD", "VBTYZ",
    "VERUS", "VESBE", "VESTEL", "VKFYO", "VKGYO", "VRGYO", "YAPRK", "YATAS",
    "YEOTK", "YESIL", "YGGYO", "YGYO", "YKBNK", "YKSLN", "YUNSA", "ZEDUR",
    "ZOREN", "ZRGYO",
]

# ---------------------------------------------------------------------------
# Crypto tickers (50 - yfinance format)
# ---------------------------------------------------------------------------

_CRYPTO_PAIRS = [
    ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"), ("BNB-USD", "BNB"),
    ("SOL-USD", "Solana"), ("XRP-USD", "XRP"), ("ADA-USD", "Cardano"),
    ("DOGE-USD", "Dogecoin"), ("AVAX-USD", "Avalanche"), ("DOT-USD", "Polkadot"),
    ("MATIC-USD", "Polygon"), ("LINK-USD", "Chainlink"), ("LTC-USD", "Litecoin"),
    ("SHIB-USD", "Shiba Inu"), ("TRX-USD", "TRON"), ("UNI-USD", "Uniswap"),
    ("ATOM-USD", "Cosmos"), ("XLM-USD", "Stellar"), ("NEAR-USD", "NEAR Protocol"),
    ("FIL-USD", "Filecoin"), ("APT-USD", "Aptos"), ("ARB-USD", "Arbitrum"),
    ("OP-USD", "Optimism"), ("IMX-USD", "Immutable X"), ("INJ-USD", "Injective"),
    ("RNDR-USD", "Render"), ("GRT-USD", "The Graph"), ("FTM-USD", "Fantom"),
    ("ALGO-USD", "Algorand"), ("SAND-USD", "The Sandbox"), ("MANA-USD", "Decentraland"),
    ("AXS-USD", "Axie Infinity"), ("AAVE-USD", "Aave"), ("MKR-USD", "Maker"),
    ("SNX-USD", "Synthetix"), ("CRV-USD", "Curve DAO"), ("LDO-USD", "Lido DAO"),
    ("RUNE-USD", "THORChain"), ("EGLD-USD", "MultiversX"), ("KAVA-USD", "Kava"),
    ("ROSE-USD", "Oasis Network"), ("ZIL-USD", "Zilliqa"), ("ENJ-USD", "Enjin Coin"),
    ("ONE-USD", "Harmony"), ("IOTA-USD", "IOTA"), ("EOS-USD", "EOS"),
    ("NEO-USD", "NEO"), ("XTZ-USD", "Tezos"), ("HBAR-USD", "Hedera"),
    ("VET-USD", "VeChain"), ("THETA-USD", "Theta Network"),
]

# ---------------------------------------------------------------------------
# Build ASSETS list
# ---------------------------------------------------------------------------

ASSETS: List[Dict[str, str]] = []

# Metals
ASSETS += [
    {"symbol": "GC=F", "name": "Gold", "category": "Metals"},
    {"symbol": "SI=F", "name": "Silver", "category": "Metals"},
    {"symbol": "PL=F", "name": "Platinum", "category": "Metals"},
    {"symbol": "PA=F", "name": "Palladium", "category": "Metals"},
    {"symbol": "HG=F", "name": "Copper", "category": "Metals"},
]

# Energy
ASSETS += [
    {"symbol": "BZ=F", "name": "Brent Oil", "category": "Energy"},
    {"symbol": "CL=F", "name": "WTI Oil", "category": "Energy"},
    {"symbol": "NG=F", "name": "Natural Gas", "category": "Energy"},
    {"symbol": "RB=F", "name": "RBOB Gasoline", "category": "Energy"},
    {"symbol": "HO=F", "name": "Heating Oil", "category": "Energy"},
]

# Indices (includes BIST 100)
ASSETS += [
    {"symbol": "XU100.IS", "name": "BIST 100", "category": "Index"},
    {"symbol": "^GSPC", "name": "S&P 500", "category": "Index"},
    {"symbol": "^IXIC", "name": "Nasdaq Composite", "category": "Index"},
    {"symbol": "^DJI", "name": "Dow Jones", "category": "Index"},
    {"symbol": "^RUT", "name": "Russell 2000", "category": "Index"},
    {"symbol": "^VIX", "name": "CBOE Volatility Index", "category": "Index"},
    {"symbol": "^GDAXI", "name": "DAX", "category": "Index"},
    {"symbol": "^FTSE", "name": "FTSE 100", "category": "Index"},
    {"symbol": "^N225", "name": "Nikkei 225", "category": "Index"},
    {"symbol": "^BVSP", "name": "Bovespa", "category": "Index"},
    {"symbol": "^HSI", "name": "Hang Seng", "category": "Index"},
    {"symbol": "000001.SS", "name": "Shanghai Composite", "category": "Index"},
    {"symbol": "^STOXX50E", "name": "Euro Stoxx 50", "category": "Index"},
]

# Crypto (50)
ASSETS += [{"symbol": sym, "name": name, "category": "Crypto"} for sym, name in _CRYPTO_PAIRS]

# ETFs
ASSETS += [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "category": "ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ ETF", "category": "ETF"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "category": "ETF"},
    {"symbol": "DIA", "name": "SPDR Dow Jones ETF", "category": "ETF"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "category": "ETF"},
    {"symbol": "SLV", "name": "iShares Silver Trust", "category": "ETF"},
    {"symbol": "USO", "name": "United States Oil Fund", "category": "ETF"},
    {"symbol": "UNG", "name": "United States Natural Gas Fund", "category": "ETF"},
    {"symbol": "TLT", "name": "20+ Year Treasury ETF", "category": "ETF"},
    {"symbol": "XLE", "name": "Energy Select Sector SPDR", "category": "ETF"},
    {"symbol": "XLF", "name": "Financial Select Sector SPDR", "category": "ETF"},
    {"symbol": "XLK", "name": "Technology Select Sector SPDR", "category": "ETF"},
    {"symbol": "XLV", "name": "Health Care Select Sector SPDR", "category": "ETF"},
    {"symbol": "XLI", "name": "Industrial Select Sector SPDR", "category": "ETF"},
    {"symbol": "XLY", "name": "Consumer Discretionary SPDR", "category": "ETF"},
    {"symbol": "XLP", "name": "Consumer Staples SPDR", "category": "ETF"},
    {"symbol": "EEM", "name": "iShares MSCI Emerging Markets", "category": "ETF"},
    {"symbol": "EFA", "name": "iShares MSCI EAFE", "category": "ETF"},
    {"symbol": "ARKK", "name": "ARK Innovation ETF", "category": "ETF"},
    {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "category": "ETF"},
]

# US large-cap stocks
ASSETS += [
    {"symbol": "AAPL", "name": "Apple", "category": "Stock"},
    {"symbol": "MSFT", "name": "Microsoft", "category": "Stock"},
    {"symbol": "GOOGL", "name": "Alphabet", "category": "Stock"},
    {"symbol": "AMZN", "name": "Amazon", "category": "Stock"},
    {"symbol": "NVDA", "name": "NVIDIA", "category": "Stock"},
    {"symbol": "TSLA", "name": "Tesla", "category": "Stock"},
    {"symbol": "META", "name": "Meta Platforms", "category": "Stock"},
    {"symbol": "NFLX", "name": "Netflix", "category": "Stock"},
    {"symbol": "AMD", "name": "AMD", "category": "Stock"},
    {"symbol": "INTC", "name": "Intel", "category": "Stock"},
    {"symbol": "CRM", "name": "Salesforce", "category": "Stock"},
    {"symbol": "ORCL", "name": "Oracle", "category": "Stock"},
    {"symbol": "ADBE", "name": "Adobe", "category": "Stock"},
    {"symbol": "CSCO", "name": "Cisco", "category": "Stock"},
    {"symbol": "QCOM", "name": "Qualcomm", "category": "Stock"},
    {"symbol": "AVGO", "name": "Broadcom", "category": "Stock"},
    {"symbol": "JPM", "name": "JPMorgan Chase", "category": "Stock"},
    {"symbol": "BAC", "name": "Bank of America", "category": "Stock"},
    {"symbol": "WFC", "name": "Wells Fargo", "category": "Stock"},
    {"symbol": "GS", "name": "Goldman Sachs", "category": "Stock"},
    {"symbol": "MS", "name": "Morgan Stanley", "category": "Stock"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway B", "category": "Stock"},
    {"symbol": "V", "name": "Visa", "category": "Stock"},
    {"symbol": "MA", "name": "Mastercard", "category": "Stock"},
    {"symbol": "PYPL", "name": "PayPal", "category": "Stock"},
    {"symbol": "XOM", "name": "Exxon Mobil", "category": "Stock"},
    {"symbol": "CVX", "name": "Chevron", "category": "Stock"},
    {"symbol": "COP", "name": "ConocoPhillips", "category": "Stock"},
    {"symbol": "SHEL", "name": "Shell", "category": "Stock"},
    {"symbol": "BP", "name": "BP", "category": "Stock"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "category": "Stock"},
    {"symbol": "PFE", "name": "Pfizer", "category": "Stock"},
    {"symbol": "MRK", "name": "Merck", "category": "Stock"},
    {"symbol": "ABT", "name": "Abbott", "category": "Stock"},
    {"symbol": "UNH", "name": "UnitedHealth", "category": "Stock"},
    {"symbol": "WMT", "name": "Walmart", "category": "Stock"},
    {"symbol": "COST", "name": "Costco", "category": "Stock"},
    {"symbol": "HD", "name": "Home Depot", "category": "Stock"},
    {"symbol": "MCD", "name": "McDonald's", "category": "Stock"},
    {"symbol": "NKE", "name": "Nike", "category": "Stock"},
    {"symbol": "KO", "name": "Coca-Cola", "category": "Stock"},
    {"symbol": "PEP", "name": "PepsiCo", "category": "Stock"},
    {"symbol": "PG", "name": "Procter & Gamble", "category": "Stock"},
    {"symbol": "DIS", "name": "Walt Disney", "category": "Stock"},
    {"symbol": "BABA", "name": "Alibaba", "category": "Stock"},
    {"symbol": "TSM", "name": "TSMC", "category": "Stock"},
    {"symbol": "ASML", "name": "ASML", "category": "Stock"},
    {"symbol": "SONY", "name": "Sony", "category": "Stock"},
    {"symbol": "TM", "name": "Toyota", "category": "Stock"},
    {"symbol": "RACE", "name": "Ferrari", "category": "Stock"},
    {"symbol": "UBER", "name": "Uber", "category": "Stock"},
    {"symbol": "SHOP", "name": "Shopify", "category": "Stock"},
    {"symbol": "SQ", "name": "Block", "category": "Stock"},
    {"symbol": "COIN", "name": "Coinbase", "category": "Stock"},
]

# BIST stocks (~500+)
ASSETS += [{"symbol": f"{t}.IS", "name": t, "category": "BIST"} for t in _BIST_TICKERS]


def sanitize_symbol(symbol: str) -> str:
    """Make ticker safe for filesystem path."""
    return symbol.replace("=", "_").replace("^", "_").replace("-", "_").replace("/", "_").replace(".", "_")


def get_categories() -> list[str]:
    """Return sorted unique category names."""
    return sorted(set(a["category"] for a in ASSETS))
