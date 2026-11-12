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

# -----------------------------------------
# Prospect Edge — Sell Assistant V1
# -----------------------------------------

with st.sidebar:
    st.divider()
    page = st.radio(
        "Prospect Edge tools",
        ["Collection Dashboard", "Sell Assistant"],
    )

if page == "Sell Assistant":
    st.header("✨ Sell Assistant")
    st.write(
        "Turn a card from your collection into an eBay-ready "
        "listing in just a few clicks."
    )

    available = cards.reset_index(drop=True).copy()

    def card_label(index):
        card = available.iloc[index]

        def show(field):
            value = card.get(field)
            return str(value).strip() if pd.notna(value) else ""

        parts = [
            show("player"),
            show("year"),
            show("set"),
            show("card_type"),
            show("parallel"),
            show("grade"),
        ]
        return " | ".join(part for part in parts if part)

    selected_index = st.selectbox(
        "Choose a card from your collection",
        options=list(range(len(available))),
        format_func=card_label,
    )

    card = available.iloc[selected_index]

    def card_field(name):
        value = card.get(name)
        return str(value).strip() if pd.notna(value) else ""

    st.subheader("Verify your card details")

    player = st.text_input("Player", value=card_field("player"))
    year = st.text_input("Year", value=card_field("year"))
    card_set = st.text_input("Set", value=card_field("set"))
    card_type = st.text_input(
        "Card type", value=card_field("card_type")
    )
    parallel = st.text_input(
        "Parallel", value=card_field("parallel")
    )
    grade = st.text_input("Grade", value=card_field("grade"))
    autograph_type = st.selectbox(
    "Autograph type",
    ["Not autographed", "Pack-issued autograph", "In-person autograph", "Other / Unsure"]
    key=f"autograph_type_{selected_index}",
    )
    condition = st.selectbox(
        "Condition",
        ["See photos", "Near mint", "Excellent", "Very good"],
    )

    strategy = st.radio(
        "What's your selling goal?",
        ["Quick Sale", "Balanced", "Maximum Return"],
        horizontal=True,
    )

    asking_price = st.number_input(
        "Your asking price ($)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

    shipping = st.selectbox(
        "Shipping preference",
        ["Buyer pays shipping", "Free shipping"],
    )
    description_style = st.selectbox(
        "Listing description style",
        [
            "Professional",
            "Quick & Clean",
            "Premium Collector",
        ],
        help="Choose how detailed your eBay listing will be.",
    )
    if st.button("✨ Generate My Listing", type="primary"):
        details = [
            year, card_set, player, card_type, parallel, grade
        ]
        title = " ".join(
            str(item).strip()
            for item in details
            if str(item).strip()
        )

        # eBay titles are limited to 80 characters.
        title = title[:80].rstrip()

        
        autograph_note = {
            "Not autographed": "No autograph.",
            "Pack-issued autograph": "Features an original pack-issued autograph.",
            "In-person autograph": "Features an in-person autograph. Authentication details should be verified.",
            "Other / Unsure": "Autograph details should be verified."
        }.get(autograph_type, "")
        if description_style == "Quick & Clean":
            description = (
                f"{year} {card_set} {player} {card_type}\n"
                f"Parallel: {parallel or 'Base'}\n"
                f"Grade: {grade or 'Ungraded'}\n\n"
                f"Autograph: {autograph_note}\n\n"
                f"Condition: {condition}\n"
                f"Please review photos for condition.\n\n"
                f"Shipping: {shipping}. Packaged securely."
            )

        elif description_style == "Premium Collector":
            description = (
                f"FEATURED COLLECTOR CARD\n\n"
                f"Offered for sale: {year} {card_set} "
                f"{player} {card_type}.\n\n"
                f"CARD INFORMATION\n"
                f"Player: {player}\n"
                f"Year: {year}\n"
                f"Set: {card_set}\n"
                f"Card Type: {card_type}\n"
                f"Parallel: {parallel or 'Base'}\n"
                f"Grade: {grade or 'Ungraded'}\n\n"
                f"Autograph: {autograph_note}\n\n"
                f"COLLECTOR APPEAL\n"
                f"An opportunity to add this {player} card "
                f"to your personal collection.\n\n"
                f"CONDITION\n"
                f"{condition}. Please examine the photos "
                f"for details of the card's appearance.\n\n"
                f"SHIPPING\n"
                f"{shipping}. Carefully packaged for transit.\n\n"
                f"Thank you for considering this card!"
            )

        else:
            description = (
                f"Available for purchase: {year} {card_set} "
                f"{player} {card_type} baseball card.\n\n"
                f"CARD DETAILS\n"
                f"Player: {player}\n"
                f"Year: {year}\n"
                f"Set: {card_set}\n"
                f"Card Type: {card_type}\n"
                f"Parallel: {parallel or 'Base'}\n"
                f"Grade: {grade or 'Ungraded'}\n\n"
                f"Autograph: {autograph_note}\n\n"
                f"CONDITION\n"
                f"{condition}. Please review all photographs "
                f"carefully before purchasing.\n\n"
                f"SHIPPING\n"
                f"{shipping}. The card will be packaged "
                f"securely to help protect it in transit.\n\n"
                f"Questions are welcome. Thank you for looking!"
            )


        st.subheader("Your Listing Is Ready")
        st.text_input("eBay title — copy this", value=title)
        st.text_area(
            "eBay description — copy this",
            value=description,
            height=280,
        )
        st.metric("Your asking price", f"${asking_price:,.2f}")
        st.caption(f"Selling strategy: {strategy}")

        st.info(
            "Review all details and card photos before publishing. "
            "Market-based price recommendations and AI-enhanced "
            "writing are coming in a future version."
        )

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
