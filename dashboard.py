
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

st.subheader("Card Values & Potential Profits")

# Work with a copy of the inventory
valuation = cards.copy()

# Convert costs and estimated values to numbers
valuation["purchase_total"] = pd.to_numeric(
    valuation["purchase_total"], errors="coerce"
)
valuation["estimated_value"] = pd.to_numeric(
    valuation["estimated_value"], errors="coerce"
)
valuation["grading_cost"] = pd.to_numeric(
    valuation["grading_cost"], errors="coerce"
) if "grading_cost" in valuation.columns else 0

# Estimated selling fees: 13.25% plus $0.40 per sale
fee_rate = 0.1325
fixed_fee = 0.40

valuation["potential_profit"] = (
    valuation["estimated_value"] * (1 - fee_rate)
    - fixed_fee
    - valuation["purchase_total"]
    - valuation["grading_cost"].fillna(0)
)

# Unknown values or purchase costs mean unknown profit
valuation.loc[
    valuation["estimated_value"].isna()
    | valuation["purchase_total"].isna(),
    "potential_profit"
] = float("nan")

st.dataframe(
    valuation[
        ["player", "grade", "purchase_total",
         "estimated_value", "potential_profit"]
    ].rename(columns={
        "player": "Player",
        "grade": "Grade",
        "purchase_total": "Purchase Cost ($)",
        "estimated_value": "Estimated Value ($)",
        "potential_profit": "Potential Profit ($)"
    }),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Potential profit is an estimate using assumed selling fees. "
    "Shipping, taxes, and other expenses may not be fully included."
)
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
