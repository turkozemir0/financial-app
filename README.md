# FinSignal

Finansal varliklar (altin, gumus, enerji, endeks, kripto, ETF, hisse) icin teknik indikator tabanli sinyal sistemi.

## Kurulum

```bash
pip install -r requirements.txt
```

## Lokal calistirma (CSV tabanli)

1. Veri indir:

```bash
python src/fetch_data.py
```

2. Terminalde sinyalleri gor:

```bash
python src/signals.py
```

3. Dashboard ac:

```bash
streamlit run src/dashboard.py
```

## Vercel deploy (canli veri API)

Bu repoda Vercel icin `api/index.py` (FastAPI) ve `vercel.json` hazirdir.

1. Vercel CLI ile baglan:

```bash
vercel login
vercel
```

2. Uretim deploy:

```bash
vercel --prod
```

Deploy sonrasi:
- Ana sayfa: `/`
- Saglik kontrolu: `/api/health`
- Canli sinyaller: `/api/signals?max_assets=30`

Not: Serverless sure limiti nedeniyle default `max_assets` dusuk tutuldu. Daha cok varlik icin sorguyu parcali cagir.

## Dosya yapisi

- `src/assets.py`: varlik listesi (100+)
- `src/fetch_data.py`: 5 yillik OHLCV indirip CSV kaydeder
- `src/indicators.py`: MA50, MA200, RSI(14), price deviation
- `src/signals.py`: skorlayip BUY/SELL/HOLD uretir
- `src/dashboard.py`: Streamlit arayuzu
- `src/live_signals.py`: CSV olmadan canli sinyal hesaplama
- `api/index.py`: Vercel API girisi
- `index.html`: Vercel uzerinde hizli tablo arayuzu
