"""Prospect Edge — isolated AI card scanning and listing experiment.

Run: streamlit run prospect_edge_ai_test.py
Dependencies: streamlit, openai
Configure OPENAI_API_KEY as an environment variable or Streamlit secret.
This tool does not write to the production inventory or Supabase.
"""
import base64
import json
import os
import re

import streamlit as st

st.set_page_config(page_title="Prospect Edge | AI Lab", page_icon="⚾", layout="wide")
st.title("⚾ Prospect Edge — AI Lab")
st.caption("Experimental card identification and eBay listing generation. Nothing is saved to your inventory or published to eBay.")

MODEL = "gpt-4.1-mini"
MAX_FILE_BYTES = 8 * 1024 * 1024


def api_key():
    try:
        return str(st.secrets.get("OPENAI_API_KEY", "")).strip() or os.environ.get("OPENAI_API_KEY", "").strip()
    except Exception:
        return os.environ.get("OPENAI_API_KEY", "").strip()


def client():
    from openai import OpenAI
    return OpenAI(api_key=api_key(), timeout=45.0, max_retries=1)


def image_part(upload):
    raw = upload.getvalue()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Each image must be 8 MB or smaller. Please resize the photo and retry.")
    mime = upload.type
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise ValueError("Please upload a JPEG, PNG, or WebP image.")
    encoded = base64.b64encode(raw).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}", "detail": "high"}}


def scan(front, back):
    prompt = """Analyze these baseball trading-card photos. Return ONLY a JSON object with string keys:
player, year, set, card_number, card_type, parallel, serial_number, grade,
autograph_type, autograph_authentication, notes, uncertainties.
Use empty strings for unknowns. autograph_type must be one of: Not autographed,
Pack-issued autograph, In-person autograph, Other / Unsure.
Do not guess a rare parallel, serial numbering, grading label, autograph origin,
or authentication. Do not infer a PSA grade without visible slab evidence.
If photos do not establish a fact, leave it blank or use Other / Unsure.
List ambiguities in uncertainties. This is a visual suggestion, NOT a verified
checklist match. No invented facts or market values."""
    content = [{"type": "text", "text": prompt}, image_part(front)]
    if back is not None:
        content.append(image_part(back))
    result = client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        max_tokens=700,
        temperature=0,
    )
    parsed = json.loads(result.choices[0].message.content)
    return {k: str(parsed.get(k, "") or "") for k in FIELDS}


def write_listing(details, style, shipping, condition):
    prompt = """Write a polished, credible eBay baseball-card listing using ONLY the
seller-reviewed facts supplied in JSON. Do not invent serial numbers, scarcity,
rookie status, signature authenticity, manufacturer certification, condition,
market values, shipping materials, guarantees, or player accomplishments.
If autograph type is Other / Unsure, do not imply it is authenticated or factory-issued.
If a detail is blank, omit it. If grade is blank, don't assert a grade.
The seller's condition wording and shipping preference must be respected.
Avoid excessive hype, emojis, filler and generic marketing slogans.
Return ONLY JSON with keys 'title' and 'description'. Title <=80 characters,
readable and optimized for relevant searchable card details. Description should
be compelling but concise, with a useful identity opening and clear card facts,
condition/photo-review note, and shipping preference. No made-up claims."""
    result = client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps({"card": details, "style": style, "shipping": shipping, "condition": condition})},
        ],
        response_format={"type": "json_object"},
        max_tokens=900,
        temperature=0.4,
    )
    data = json.loads(result.choices[0].message.content)
    title = str(data.get("title", "")).strip()
    if len(title) > 80:
        title = title[:80].rsplit(" ", 1)[0]
    return title, str(data.get("description", "")).strip()


FIELDS = ["player", "year", "set", "card_number", "card_type", "parallel", "serial_number", "grade", "autograph_type", "autograph_authentication", "notes", "uncertainties"]
LABELS = {"player": "Player", "year": "Year", "set": "Set", "card_number": "Card number", "card_type": "Card type", "parallel": "Parallel", "serial_number": "Visible serial number", "grade": "Grade / grading company", "autograph_type": "Autograph type", "autograph_authentication": "Autograph authentication (verified only)", "notes": "Other visible details", "uncertainties": "AI uncertainties / verification needed"}

if not api_key():
    st.info("To use this lab, configure an OPENAI_API_KEY in your test app's Streamlit secrets. Do not paste an API key into this Python file or the chat.")

left, right = st.columns(2)
with left:
    front = st.file_uploader("Front of card (required)", type=["jpg", "jpeg", "png", "webp"], key="front")
    if front:
        st.image(front, caption="Front", use_container_width=True)
with right:
    back = st.file_uploader("Back of card (recommended)", type=["jpg", "jpeg", "png", "webp"], key="back")
    if back:
        st.image(back, caption="Back", use_container_width=True)

if st.button("🔎 Identify Card with AI", disabled=not (front and api_key()), type="primary"):
    try:
        with st.spinner("Reading the card photos..."):
            st.session_state["ai_scan"] = scan(front, back)
            st.session_state.pop("ai_listing", None)
        st.success("Visual scan complete. Review and correct every field before generating a listing.")
    except ImportError:
        st.error("The openai package is not installed. Add 'openai' to requirements.txt for the test app.")
    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"The AI request did not complete ({type(exc).__name__}). Check your API key, billing, model access and usage limits.")

if "ai_scan" in st.session_state:
    st.divider()
    st.subheader("1. Verify the AI's identification")
    st.warning("This is image interpretation, not database verification. Check the exact set, parallel, autograph origin, serial number and grade against the card and a trusted checklist.")
    reviewed = {}
    for field in FIELDS:
        value = st.session_state["ai_scan"].get(field, "")
        if field == "autograph_type":
            choices = ["Not autographed", "Pack-issued autograph", "In-person autograph", "Other / Unsure"]
            reviewed[field] = st.selectbox(LABELS[field], choices, index=choices.index(value) if value in choices else 3, key=f"review_{field}")
        elif field in ("notes", "uncertainties"):
            reviewed[field] = st.text_area(LABELS[field], value=value, key=f"review_{field}")
        else:
            reviewed[field] = st.text_input(LABELS[field], value=value, key=f"review_{field}")
    confirmed = st.checkbox("I reviewed the card details against the photographs and corrected any errors.")
    st.subheader("2. Generate a listing draft")
    style = st.selectbox("Writing style", ["Professional", "Quick & Clean", "Premium Collector"])
    condition = st.selectbox("Condition wording", ["See photos", "Near mint", "Excellent", "Very good"])
    shipping = st.selectbox("Shipping preference", ["Buyer pays shipping", "Free shipping"])
    if st.button("✨ Write AI eBay Listing", disabled=not (confirmed and api_key())):
        if not reviewed["player"].strip() or not reviewed["set"].strip():
            st.error("Please confirm at least the player and set first.")
        else:
            try:
                with st.spinner("Writing your listing..."):
                    st.session_state["ai_listing"] = write_listing(reviewed, style, shipping, condition)
            except Exception as exc:
                st.error(f"Listing generation failed ({type(exc).__name__}). Check your API configuration and retry.")
    if "ai_listing" in st.session_state:
        title, description = st.session_state["ai_listing"]
        st.subheader("3. Your draft eBay listing")
        st.text_input("Title (copy to eBay)", value=title)
        st.caption(f"{len(title)} / 80 characters")
        st.text_area("Description (copy to eBay)", value=description, height=350)
        st.info("Draft only. No sold comps, authentication verification, direct eBay publishing or persistent storage is connected in this lab.")

st.divider()
st.caption("AI requests are sent to OpenAI and may incur API charges. Only upload photos you have permission to use. API keys belong in secrets, never source code.")
