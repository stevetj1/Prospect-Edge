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
# Prospect Edge — Sell Assistant V2
# -----------------------------------------

with st.sidebar:
    st.divider()
    page = st.radio("Prospect Edge tools", ["Collection Dashboard", "Sell Assistant"])


def clean_value(value):
    """Avoid showing pandas missing-value placeholders in listing text."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def known_autograph_type(card):
    """Only preselect a specific autograph type when inventory explicitly says so."""
    explicit = clean_value(card.get("autograph_type")).lower()
    if explicit in ("pack-issued autograph", "pack issued", "factory auto", "certified auto"):
        return "Pack-issued autograph"
    if explicit in ("in-person autograph", "in person", "ip auto", "in-person auto"):
        return "In-person autograph"
    if explicit in ("not autographed", "none", "no"):
        return "Not autographed"
    if explicit:
        return "Other / Unsure"
    # Card type alone cannot establish whether a signature was pack-issued.
    type_text = clean_value(card.get("card_type")).lower()
    notes_text = clean_value(card.get("notes")).lower()
    if any(word in type_text for word in ("auto", "autograph", "signed")) or any(
        word in notes_text for word in ("autograph", "signed", "auto")
    ):
        return "Other / Unsure"
    return "Not autographed"


def listing_title(year, card_set, player, card_type, parallel, grade, autograph_type):
    parts = [year, card_set, player, card_type, parallel, grade]
    # Do not duplicate autograph terms already present in the card type.
    if autograph_type == "In-person autograph":
        parts.append("In-Person Auto")
    elif autograph_type == "Pack-issued autograph":
        parts.append("Auto")
    elif autograph_type == "Other / Unsure":
        parts.append("Auto Unverified")
    title = " ".join(clean_value(part) for part in parts if clean_value(part))
    # eBay title maximum is 80 characters; trim at a word boundary when possible.
    if len(title) > 80:
        title = title[:80].rsplit(" ", 1)[0]
    return title


if page == "Sell Assistant":
    st.header("✨ Sell Assistant")
    st.write("Create a draft eBay listing from your collection. Verify the card before publishing.")
    available = cards.reset_index(drop=True)

    def card_label(index):
        row = available.iloc[index]
        fields = ("player", "year", "set", "card_type", "parallel", "grade")
        return " | ".join(clean_value(row.get(field)) for field in fields if clean_value(row.get(field)))

    selected_index = st.selectbox(
        "Choose a card from your collection",
        options=list(range(len(available))),
        format_func=card_label,
    )
    card = available.iloc[selected_index]

    def card_field(name):
        return clean_value(card.get(name))

    st.subheader("Verify your card details")
    st.caption("Values come from your inventory, not from an automated card identification service.")
    player = st.text_input("Player", value=card_field("player"), key=f"player_{selected_index}")
    year = st.text_input("Year", value=card_field("year"), key=f"year_{selected_index}")
    card_set = st.text_input("Set", value=card_field("set"), key=f"set_{selected_index}")
    card_type = st.text_input("Card type", value=card_field("card_type"), key=f"card_type_{selected_index}")
    parallel = st.text_input("Parallel", value=card_field("parallel"), key=f"parallel_{selected_index}")
    grade = st.text_input("Grade", value=card_field("grade"), key=f"grade_{selected_index}")

    autograph_options = [
        "Not autographed", "Pack-issued autograph", "In-person autograph", "Other / Unsure"
    ]
    default_autograph = known_autograph_type(card)
    autograph_type = st.selectbox(
        "Autograph type",
        autograph_options,
        index=autograph_options.index(default_autograph),
        key=f"autograph_type_{selected_index}",
        help="Pack-issued means the card was originally issued with the signature. In-person means it was signed separately.",
    )
    authentication = st.text_input(
        "Autograph authentication (optional)",
        value=card_field("autograph_authentication"),
        key=f"authentication_{selected_index}",
        placeholder="e.g., PSA/DNA authenticated — only if verified",
    )
    condition = st.selectbox(
        "Condition", ["See photos", "Near mint", "Excellent", "Very good"],
        key=f"condition_{selected_index}",
    )
    strategy = st.radio(
        "What's your selling goal?", ["Quick Sale", "Balanced", "Maximum Return"],
        horizontal=True, key=f"strategy_{selected_index}",
    )
    asking_price = st.number_input(
        "Your asking price ($)", min_value=0.0, value=0.0, step=1.0,
        key=f"asking_price_{selected_index}",
    )
    shipping = st.selectbox(
        "Shipping preference", ["Buyer pays shipping", "Free shipping"],
        key=f"shipping_{selected_index}",
    )
    description_style = st.selectbox(
        "Listing description style",
        ["Professional", "Quick & Clean", "Premium Collector"],
        key=f"description_style_{selected_index}",
    )

    if st.button("✨ Generate My Listing", type="primary"):
        missing = [label for label, value in (
            ("Player", player), ("Year", year), ("Set", card_set),
            ("Card type", card_type), ("Grade/raw status", grade)
        ) if not value.strip()]
        if missing:
            st.error("Please verify these fields before generating: " + ", ".join(missing))
        else:
            if autograph_type == "Other / Unsure":
                st.warning("Autograph type is uncertain. Confirm whether this is a pack-issued or in-person signature before publishing.")
            if not parallel.strip():
                st.warning("Parallel is blank. Confirm whether this is a base card or a specific parallel.")
            if authentication.strip() and autograph_type == "Not autographed":
                st.warning("Authentication details were entered, but autograph type is set to Not autographed.")

            title = listing_title(year, card_set, player, card_type, parallel, grade, autograph_type)
            autograph_note = {
                "Not autographed": "No autograph indicated.",
                "Pack-issued autograph": "Pack-issued autograph (verify against the manufacturer's checklist).",
                "In-person autograph": "In-person autograph (signed separately from the original card issue).",
                "Other / Unsure": "Autograph origin not confirmed; verify before listing.",
            }[autograph_type]
            if authentication.strip() and autograph_type != "Not autographed":
                autograph_note += f" Authentication: {authentication.strip()} (seller to verify)."

            identity = " ".join(x for x in [year, card_set, player, card_type] if x.strip())
            detail_lines = [
                f"Player: {player}", f"Year: {year}", f"Set: {card_set}",
                f"Card type: {card_type}",
                f"Parallel: {parallel if parallel.strip() else 'Not verified'}",
                f"Grade: {grade}", f"Autograph: {autograph_note}",
            ]
            if description_style == "Quick & Clean":
                description = (
                    identity + "\n" + "\n".join(detail_lines[4:])
                    + f"\n\nCondition: {condition}. Please review photos."
                    + f"\nShipping: {shipping}. Packaged securely."
                )
            elif description_style == "Premium Collector":
                description = (
                    "FEATURED COLLECTOR CARD\n\n" + identity + "\n\n"
                    + "CARD DETAILS\n" + "\n".join(detail_lines)
                    + f"\n\nCONDITION\n{condition}. Please examine all photos carefully."
                    + f"\n\nSHIPPING\n{shipping}. Carefully packaged for transit."
                    + "\n\nThank you for considering this card."
                )
            else:
                description = (
                    "Available for purchase: " + identity + " baseball card.\n\n"
                    + "CARD DETAILS\n" + "\n".join(detail_lines)
                    + f"\n\nCONDITION\n{condition}. Please review all photographs carefully before purchasing."
                    + f"\n\nSHIPPING\n{shipping}. The card will be packaged securely for transit."
                    + "\n\nQuestions are welcome. Thank you for looking!"
                )
            st.subheader("Your Listing Is Ready — Draft")
            st.text_input("eBay title — copy this", value=title)
            st.caption(f"{len(title)}/80 characters")
            st.text_area("eBay description — copy this", value=description, height=320)
            st.metric("Your asking price", f"${asking_price:,.2f}")
            st.caption(f"Selling strategy: {strategy}. Asking price is user-entered, not market-verified.")
            st.info("Draft only. Check exact card identity, autograph origin, grading, parallel, photos and price before publishing. No live sold comps are connected yet.")
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
