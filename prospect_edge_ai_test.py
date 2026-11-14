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
    prompt = """You are a conservative baseball-card photo transcription assistant.
Inspect the FRONT and BACK independently before combining findings. Return ONLY
one JSON object with these STRING keys: player, year, set, card_number,
card_type, parallel, serial_number, grade, autograph_type,
autograph_authentication, notes, uncertainties.

ACCURACY RULES (more important than filling fields):
1. TRANSCRIBE card_number from printed text, preferably the back. Preserve the
   EXACT letters, digits and hyphens. Do not infer a number from a checklist.
   Distinguish BCP from BOP, 0 from O, and 1 from I. If any character is unclear,
   leave card_number empty and explicitly say which characters need inspection.
2. Distinguish a 1st Bowman designation from an MLB Rookie Card (RC) logo.
   A 1st Bowman is NOT automatically an MLB rookie card. Use 'Rookie Card'
   only when clearly supported by visible evidence; do not infer from year.
3. Never invent a parallel, print run, serial stamp, or grade. A parallel's
   apparent color alone is insufficient for a definitive identification.
   Transcribe serial numbering exactly as visible, e.g. '01/10'.
4. For grade, include company and grade together (e.g. 'PSA 9') ONLY when
   both are legible on the slab. A protective holder is not a grading slab.
5. Autograph type MUST be exactly one of: Not autographed,
   Pack-issued autograph, In-person autograph, Other / Unsure.
   'Pack-issued autograph' requires visible manufacturer certification or
   unmistakable factory autograph-card evidence; a blue signature alone is
   NOT enough. A non-autograph checklist card with an added signature and
   third-party autograph authentication may be in-person/aftermarket, but
   don't claim certainty from third-party certification alone. If origin is
   not proven, choose Other / Unsure and explain the ambiguity.
6. Separate AUTHENTICATION from ORIGIN. JSA, PSA/DNA and Beckett/BAS
   certify signatures (subject to actual verification); they do NOT by
   themselves establish a pack-issued autograph. If a certificate or sticker
   is pictured, transcribe its agency and number in notes, and state
   'visible, not independently verified' in autograph_authentication.
   Do NOT claim a certificate number has been checked in an external database.
7. Before returning JSON, check for contradictions: third-party signature
   certificate vs claimed pack-issued origin; 'Rookie Card' without an RC
   logo; grade without grading slab; conflicting front/back numbers.
   When conflicting or uncertain, prefer blank / Other / Unsure and describe
   the precise question in uncertainties.
8. No web lookup or checklist validation has occurred. Do not invent
   market prices, rarity, provenance, or authentication results.
Use empty strings for genuinely unknown fields. In uncertainties, provide
specific checks the seller should perform. Keep notes factual and concise."""
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
    if not isinstance(parsed, dict):
        raise ValueError("AI returned an unexpected response. Please try again.")
    details = {k: str(parsed.get(k, "") or "").strip() for k in FIELDS}
    return validate_scan(details)



def validate_scan(details):
    """Conservative post-scan checks; these flag ambiguity, not authenticate cards."""
    flags = []
    origin = details["autograph_type"]
    valid_origins = {"Not autographed", "Pack-issued autograph", "In-person autograph", "Other / Unsure"}
    if origin not in valid_origins:
        details["autograph_type"] = "Other / Unsure"
        flags.append("Autograph origin could not be classified reliably.")

    number = details["card_number"]
    # Never silently 'fix' a potentially misread printed card number.
    if number and not re.fullmatch(r"[A-Za-z0-9]+(?:[-./][A-Za-z0-9]+)*", number):
        flags.append("Card number has unusual characters; compare it carefully with the back.")
    if number and re.search(r"\bB[CO]P[-]?[0-9]+\b", number, re.I):
        flags.append("Confirm each letter of this Bowman-style card number against the printed back (for example, BCP versus BOP).")

    auth = details["autograph_authentication"]
    third_party = bool(re.search(r"\b(?:JSA|PSA\s*/\s*DNA|BAS|Beckett\s+Authentication)\b", auth, re.I))
    if third_party and not re.search(r"not independently verified|unverified", auth, re.I):
        details["autograph_authentication"] = auth + " (visible; not independently verified)"
    if third_party and details["autograph_type"] == "Pack-issued autograph":
        details["autograph_type"] = "Other / Unsure"
        flags.append("Third-party autograph authentication does not prove a pack-issued signature. Verify the card's factory autograph status against a trusted checklist.")
    if details["grade"] and not re.search(r"\b(?:PSA|BGS|SGC|CGC|CSG)\b", details["grade"], re.I):
        flags.append("Grading company is missing or unclear; verify the slab label before listing a grade.")
    if flags:
        details["uncertainties"] = "\n".join(filter(None, [details["uncertainties"], *flags]))
    return details


def write_listing(details, style, shipping, condition):
    prompt = """Write a polished, credible eBay baseball-card listing using ONLY the
seller-reviewed facts supplied in JSON. Do not invent serial numbers, scarcity,
rookie status, signature authenticity, manufacturer certification, condition,
market values, shipping materials, guarantees, or player accomplishments.
If autograph type is Other / Unsure, do not imply it is factory-issued or in-person.
A pictured JSA/PSA-DNA/BAS certificate is NOT independent database verification;
never say 'verified' or 'guaranteed authentic' based solely on a photo.
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
LABELS = {"player": "Player", "year": "Year", "set": "Set", "card_number": "Card number", "card_type": "Card type", "parallel": "Parallel", "serial_number": "Visible serial number", "grade": "Grade / grading company", "autograph_type": "Autograph type", "autograph_authentication": "Autograph authentication (visible evidence; check independently)", "notes": "Other visible details", "uncertainties": "AI uncertainties / verification needed"}

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
            new_scan = scan(front, back)
            # Streamlit widget state persists across scans unless explicitly reset.
            for field in FIELDS:
                st.session_state.pop(f"review_{field}", None)
            st.session_state.pop("scan_confirmed", None)
            st.session_state["ai_scan"] = new_scan
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
    if st.session_state["ai_scan"].get("uncertainties"):
        st.info("AI verification flags: " + st.session_state["ai_scan"]["uncertainties"])
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
    confirmed = st.checkbox("I reviewed the card details against the photographs and corrected any errors.", key="scan_confirmed")
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
