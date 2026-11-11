
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Prospect Edge",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Prospect Edge")
st.caption("Baseball Card Investment Intelligence")

st.subheader("My Portfolio")

inventory_path = Path(__file__).parent / "data" / "inventory.csv"

cards = pd.read_csv(inventory_path)
cards["purchase_total"] = pd.to_numeric(
    cards["purchase_total"], errors="coerce"
)

total_invested = cards["purchase_total"].sum()
total_cards = len(cards)
missing_costs = cards["purchase_total"].isna().sum()

col1, col2, col3 = st.columns(3)

col1.metric("Known Purchase Costs", f"${total_invested:,.2f}")
col2.metric("Cards in Portfolio", total_cards)
col3.metric("Missing Purchase Costs", missing_costs)

st.divider()

st.subheader("Your Baseball Cards")

st.dataframe(
    cards,
    use_container_width=True,
    hide_index=True
)

st.info(
    "Market valuations, selling profits, and automated "
    "purchase importing are coming in future versions."
)
