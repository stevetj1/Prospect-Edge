"""Prospect Edge — Streamlit inventory dashboard.

Reads data/inventory.csv, and optionally connects to the Supabase cards table.
Secrets must be configured in Streamlit Cloud, never in this file.
"""

from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Prospect Edge", page_icon="⚾", layout="wide")
st.title("⚾ Prospect Edge")
st.caption("Baseball Card Investment Intelligence")

DATA_FILE = Path(__file__).resolve().parent / "data" / "inventory.csv"
MONEY_COLUMNS = [
    "purchase_total", "grading_cost", "estimated_value", "sale_price",
    "selling_fees", "shipping_cost",
]


def normalize_inventory(df):
    """Standardize both CSV and Supabase card records for display."""
    df = df.copy()
    for name in ["card_id", "player", "year", "set", "card_type", "parallel",
                 "grade", "purchase_date", "status", "notes"]:
        if name not in df.columns:
            df[name] = pd.NA
    for name in MONEY_COLUMNS:
        if name not in df.columns:
            df[name] = pd.NA
        df[name] = pd.to_numeric(df[name], errors="coerce")
    return df


@st.cache_data(ttl=60)
def load_csv():
    if not DATA_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(DATA_FILE, dtype={"card_id": "string"})


def load_supabase():
    """Return (cards dataframe, status message) without breaking the dashboard."""
    if "supabase" not in st.secrets:
        return None, "Supabase secrets have not been configured."
    config = st.secrets["supabase"]
    url = str(config.get("url", "")).strip()
    key = str(config.get("key", "")).strip()
    if not url or not key:
        return None, "Supabase URL or key is missing."
    if not url.startswith("https://"):
        return None, "Supabase URL must start with https://."
    # The Supabase Python client expects the project URL, not /rest/v1/.
    url = url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-8]
    try:
        from supabase import create_client
        client = create_client(url, key)
        response = client.table("cards").select("*").limit(1000).execute()
        return pd.DataFrame(response.data or []), "Connected to Supabase."
    except ImportError:
        return None, "The supabase package is missing from requirements.txt."
    except Exception as exc:
        # Never display credentials or raw exception strings in the app.
        return None, f"Supabase connection failed ({type(exc).__name__}). Check the project URL, key, table and permissions."


csv_cards = load_csv()
supabase_cards, db_message = load_supabase()

with st.sidebar:
    st.header("Data source")
    source_options = []
    if not csv_cards.empty:
        source_options.append("Inventory CSV")
    if supabase_cards is not None and not supabase_cards.empty:
        source_options.append("Supabase")
    if source_options:
        source = st.radio("Display cards from", source_options)
    else:
        source = None
    st.divider()
    if supabase_cards is not None:
        st.success(db_message)
    else:
        st.info(db_message)
    st.caption("CSV and Supabase are separate data sources. This app does not automatically sync them.")

if source == "Supabase":
    cards = normalize_inventory(supabase_cards)
elif source == "Inventory CSV":
    cards = normalize_inventory(csv_cards)
else:
    cards = pd.DataFrame()

if cards.empty:
    st.warning("No cards to display yet. Add cards to data/inventory.csv or import them into your Supabase cards table.")
    st.stop()

cost = cards["purchase_total"].fillna(0) + cards["grading_cost"].fillna(0)
values = cards["estimated_value"].fillna(0)
known_cost = cards["purchase_total"].notna()
known_values = cards["estimated_value"].notna()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cards", f"{len(cards):,}")
c2.metric("Known purchase costs", f"${cards['purchase_total'].sum():,.2f}")
c3.metric("Estimated card values", f"${cards['estimated_value'].sum():,.2f}")
c4.metric("Missing purchase costs", f"{(~known_cost).sum():,}")

st.caption("Totals exclude blank amounts; estimated values are not verified sale prices. Grading costs are added only where entered.")

st.subheader("Card inventory")
search = st.text_input("Search player, set, card ID, or notes", "")
filtered = cards.copy()
if search.strip():
    searchable = filtered.fillna("").astype(str).agg(" ".join, axis=1)
    filtered = filtered[searchable.str.contains(search.strip(), case=False, regex=False)]

preferred = ["card_id", "player", "year", "set", "card_type", "parallel", "grade",
             "purchase_date", "purchase_total", "grading_cost", "estimated_value",
             "status", "notes", "sale_price", "selling_fees", "shipping_cost", "sale_channel"]
ordered = [c for c in preferred if c in filtered.columns]
ordered += [c for c in filtered.columns if c not in ordered and c not in ("id", "created_at")]
st.dataframe(filtered[ordered], use_container_width=True, hide_index=True)

st.download_button(
    "Download displayed inventory (CSV)",
    data=filtered[ordered].to_csv(index=False).encode("utf-8"),
    file_name="prospect_edge_inventory_export.csv",
    mime="text/csv",
)

st.subheader("Portfolio analysis")
analysis = cards.copy()
analysis["total_known_cost"] = cost
analysis["estimated_profit_before_selling_costs"] = analysis["estimated_value"] - analysis["total_known_cost"]
complete = analysis[known_cost & known_values]
if complete.empty:
    st.info("Add purchase costs and estimated values to see projected gains and losses.")
else:
    st.dataframe(
        complete[["card_id", "player", "total_known_cost", "estimated_value",
                  "estimated_profit_before_selling_costs"]],
        use_container_width=True, hide_index=True,
    )
    st.caption("Projected profit excludes future selling fees, shipping, taxes, and any unentered grading costs.")

sold = cards[cards["sale_price"].notna() & cards["purchase_total"].notna()].copy()
if not sold.empty:
    sold["net_profit"] = (
        sold["sale_price"]
        - sold["purchase_total"]
        - sold["grading_cost"].fillna(0)
        - sold["selling_fees"].fillna(0)
        - sold["shipping_cost"].fillna(0)
    )
    st.subheader("Recorded sales")
    st.metric("Recorded net profit", f"${sold['net_profit'].sum():,.2f}")
    st.caption("Uses entered sale prices and expenses. Blank expenses are treated as zero, so profit may be overstated.")
