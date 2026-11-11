
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Prospect Edge",
    page_icon="⚾",
    layout="wide",
)

st.title("⚾ Prospect Edge")
st.caption("Baseball Card Investment Intelligence")

inventory_path = Path(__file__).parent / "data" / "inventory.csv"

@st.cache_data
def load_inventory(path):
    return pd.read_csv(path, dtype=str).fillna("")

cards = load_inventory(inventory_path)

# Convert money columns into numbers.
for column in ["purchase_total", "grading_cost", "estimated_value"]:
    if column not in cards.columns:
        cards[column] = ""
    cards[column] = pd.to_numeric(cards[column], errors="coerce")

if "status" not in cards.columns:
    cards["status"] = "Owned"

cards["status"] = cards["status"].str.strip().str.title()

# Temporary support for sales recorded in notes.
# We'll replace this with structured sales data later.
def get_sale_price(row):
    if row["status"] != "Sold":
        return float("nan")
    notes = str(row.get("notes", ""))
    match = re.search(
        r"(?:sold.*?for|sale price[: ]+)\s*\$?([\d,]+(?:\.\d+)?)",
        notes,
        flags=re.IGNORECASE,
    )
    if match:
        return float(match.group(1).replace(",", ""))
    return float("nan")

cards["sale_price"] = cards.apply(get_sale_price, axis=1)

cards["total_cost"] = (
    cards["purchase_total"].fillna(0)
    + cards["grading_cost"].fillna(0)
)

owned = cards[cards["status"] == "Owned"].copy()
sold = cards[cards["status"] == "Sold"].copy()

# A missing valuation is NOT the same as a $0 valuation.
valued_owned = owned[owned["estimated_value"].notna()]
unvalued_owned = owned[owned["estimated_value"].isna()]

known_market_value = valued_owned["estimated_value"].sum()

# Only calculate unrealized gains for cards with
# both a known cost and a known estimated value.
complete_cost = (
    valued_owned["purchase_total"].notna()
    & valued_owned["grading_cost"].notna()
)

# Grading costs are optional for raw cards.
raw_cards = valued_owned["grade"].str.lower().eq("raw")
complete_cost = (
    valued_owned["purchase_total"].notna()
    & (valued_owned["grading_cost"].notna() | raw_cards)
)

eligible = valued_owned[complete_cost]
unrealized_profit = (
    eligible["estimated_value"] - eligible["total_cost"]
).sum()

# Realized profit currently excludes any unrecorded
# selling expenses. Display this as provisional.
sold_with_data = sold[
    sold["sale_price"].notna()
    & sold["purchase_total"].notna()
]

provisional_realized_profit = (
    sold_with_data["sale_price"]
    - sold_with_data["total_cost"]
).sum()

st.subheader("Portfolio Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Cards Owned", len(owned))
c2.metric("Cards Sold", len(sold))
c3.metric(
    "Known Owned-Card Value",
    f"${known_market_value:,.2f}",
)
c4.metric(
    "Provisional Sale Profit",
    f"${provisional_realized_profit:,.2f}",
)

st.info(
    f"{len(unvalued_owned)} owned cards have no market "
    "value entered. Portfolio value is incomplete. "
    "Selling fees, shipping and some grading costs "
    "are not yet included."
)

st.divider()

st.subheader("My Portfolio")

view = st.radio(
    "Show cards",
    ["Owned", "Sold", "All"],
    horizontal=True,
)

if view == "Owned":
    displayed = owned
elif view == "Sold":
    displayed = sold
else:
    displayed = cards

columns = [
    "card_id", "player", "year", "set",
    "card_type", "parallel", "grade",
    "purchase_total", "grading_cost",
    "estimated_value", "status",
]

if view != "Owned":
    columns.append("sale_price")

st.dataframe(
    displayed[columns],
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Financial Performance")

f1, f2, f3 = st.columns(3)

f1.metric(
    "Known Purchase Cost — Owned",
    f"${owned['purchase_total'].sum():,.2f}",
)
f2.metric(
    "Known Market Value — Owned",
    f"${known_market_value:,.2f}",
)
f3.metric(
    "Provisional Realized Profit",
    f"${provisional_realized_profit:,.2f}",
)

st.caption(
    "Market values are manually entered estimates, "
    "not live prices. Realized profit is provisional "
    "until all expenses are recorded."
)

st.subheader("Cards With Market Values")

st.dataframe(
    valued_owned[
        [
            "card_id", "player", "grade",
            "purchase_total", "estimated_value",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Selling Center")

if sold.empty:
    st.write("No sales recorded yet.")
else:
    st.dataframe(
        sold[
            [
                "card_id", "player", "purchase_total",
                "sale_price", "status",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

st.divider()

st.subheader("Player Research")
st.info("Prospect screening and player analysis coming soon.")

st.subheader("Buy Opportunities")
st.info("Market comparisons and buying alerts coming soon.")
