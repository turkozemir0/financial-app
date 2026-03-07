"""Streamlit dashboard for FinSignal."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from assets import sanitize_symbol
from indicators import add_indicators
from signals import DATA_DIR, load_signals

st.set_page_config(layout="wide", page_title="FinSignal Dashboard")


@st.cache_data(ttl=600)
def get_signals() -> pd.DataFrame:
    return pd.DataFrame(load_signals())


@st.cache_data(ttl=600)
def get_asset_history(symbol: str) -> pd.DataFrame:
    csv_path = DATA_DIR / f"{sanitize_symbol(symbol)}.csv"
    df = pd.read_csv(csv_path)
    return add_indicators(df)


def format_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename_map = {
        "name": "Name",
        "category": "Category",
        "signal": "Signal",
        "score": "Score",
        "rsi": "RSI",
        "price_deviation": "Price Deviation",
        "current_price": "Current Price",
        "last_date": "Last Date",
    }
    out = out.rename(columns=rename_map)
    return out[["Name", "Category", "Signal", "Score", "RSI", "Price Deviation", "Current Price", "Last Date"]]


def signal_color(signal: str) -> str:
    if signal == "BUY":
        return "#0f9d58"
    if signal == "SELL":
        return "#db4437"
    return "#7d7d7d"


def main() -> None:
    st.title("FinSignal")
    st.caption("Live market-derived technical signals for metals, energy, indices, crypto, ETFs and stocks.")

    if st.button("Refresh Data"):
        get_signals.clear()
        get_asset_history.clear()

    signals_df = get_signals()
    if signals_df.empty:
        st.warning("No signals available. Run data download first: python src/fetch_data.py")
        return

    all_categories = sorted(signals_df["category"].dropna().unique().tolist())
    with st.sidebar:
        st.header("Filters")
        selected_categories = st.multiselect("Category", all_categories, default=all_categories)
        selected_signal = st.selectbox("Signal", ["All", "BUY", "SELL", "HOLD"], index=0)
        search = st.text_input("Search by Name", value="").strip().lower()

    filtered = signals_df[signals_df["category"].isin(selected_categories)]
    if selected_signal != "All":
        filtered = filtered[filtered["signal"] == selected_signal]
    if search:
        filtered = filtered[filtered["name"].str.lower().str.contains(search)]

    st.subheader("Signal Table")
    display_df = format_signals(filtered)
    styled = display_df.style.apply(
        lambda row: [f"color: {signal_color(row['Signal'])}; font-weight: 700;" if col == "Signal" else "" for col in row.index],
        axis=1,
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    if filtered.empty:
        st.info("No asset matches selected filters.")
        return

    asset_label_map = {f"{row['name']} ({row['symbol']})": row["symbol"] for _, row in filtered.sort_values("name").iterrows()}
    selected_label = st.selectbox("Asset Detail", list(asset_label_map.keys()), index=0)
    selected_symbol = asset_label_map[selected_label]

    detail = filtered[filtered["symbol"] == selected_symbol].iloc[0]
    history = get_asset_history(selected_symbol)

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Price + MA50/MA200")
        fig_price = go.Figure()
        fig_price.add_trace(go.Scatter(x=history["date"], y=history["close"], mode="lines", name="Close"))
        fig_price.add_trace(go.Scatter(x=history["date"], y=history["ma50"], mode="lines", name="MA50"))
        fig_price.add_trace(go.Scatter(x=history["date"], y=history["ma200"], mode="lines", name="MA200"))
        fig_price.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_price, use_container_width=True)

        st.subheader("RSI (14)")
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=history["date"], y=history["rsi"], mode="lines", name="RSI"))
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="#0f9d58")
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="#db4437")
        fig_rsi.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]))
        st.plotly_chart(fig_rsi, use_container_width=True)

    with right:
        st.subheader("Summary")
        st.metric("Current Price", f"{detail['current_price']:.4f}")
        st.metric("5Y Average", f"{detail['avg_5yr']:.4f}")
        st.metric("Price Deviation", f"{detail['price_deviation']:.4f}")
        st.metric("RSI", f"{detail['rsi']:.2f}")
        st.metric("Signal", detail["signal"])
        st.metric("Score", f"{detail['score']:+d}")
        st.caption(f"Last Date: {detail['last_date']}")


if __name__ == "__main__":
    main()
