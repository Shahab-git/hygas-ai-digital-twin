"""
Confirmation-loop agent v1 — closes the loop on the six unconfirmed
design assumptions from uncertainty.py, tying together uncertainty.py,
compliance.py, and regulatory_drafting.py rather than starting fresh.

SCOPE, stated honestly, same spirit as regulatory_drafting.py's "drafting,
not legal writing": this does NOT send real emails or messages to
DOK-ING. It has no real correspondence capability and no authority to
represent the user externally. It drafts confirmation-request content and
tracks status (not_yet_asked / awaiting_response / confirmed) in
Supabase, for the user to actually send and follow up on themselves.

Storage: Supabase table `assumption_confirmations` — see
data/confirmation_schema.sql for the DDL (same project as vendor_quotes,
same credential-loading pattern as vendor_log.py). One row per
assumption, upserted on assumption_key (unlike vendor_quotes, which only
ever inserts, this table's status changes over time, so it needs
UPDATE — see the schema file for the grants that requires).

The real payoff — the reason this module exists rather than being just a
status tracker: record_confirmation() calls uncertainty.set_confirmed()
as part of recording a confirmation, so uncertainty.py's own ASSUMPTIONS
dict is updated in place. From that point on:
  - run_monte_carlo() samples the CONFIRMED range for that one assumption
    instead of the default +/-15% band — no separate "confirmed mode"
    flag to thread through, the same function just reads live state.
  - compliance.py's checklist status for that item flips from
    "Assumption — pending confirmation" to "Confirmed" on its own, since
    compliance.py already reads uncertainty.ASSUMPTIONS/bounds()/
    is_confirmed() live (see compliance.py's own docstring) — nothing
    in this module writes to compliance.py at all.
No separate copy of "is this confirmed" exists anywhere in this repo.

Draft generation reuses regulatory_drafting.py's pattern rather than
writing new Markdown formatting from scratch: same header/disclaimer
style, and the literal DRAFT_DISCLAIMER constant. A full reuse of
generate_draft_summary() itself wasn't applicable — that function is
shaped around the compliance checklist's grouped-by-category structure,
while a confirmation request is a one-assumption request letter — so the
shared part is the disclaimer and formatting conventions, not the whole
function.
"""
import os
import tomllib
from datetime import datetime, timezone

from supabase import create_client

from . import compliance, regulatory_drafting, uncertainty

_TABLE = "assumption_confirmations"
_SECRETS_PATH = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")

STATUS_NOT_ASKED = "not_yet_asked"
STATUS_AWAITING = "awaiting_response"
STATUS_CONFIRMED = "confirmed"

_client = None


def _get_secret(name):
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    if os.path.exists(_SECRETS_PATH):
        with open(_SECRETS_PATH, "rb") as f:
            data = tomllib.load(f)
        if name in data:
            return data[name]
    raise RuntimeError(
        f"Missing secret '{name}'. Set it in .streamlit/secrets.toml locally, "
        f"or in Streamlit Cloud's secrets manager when deployed."
    )


def _get_client():
    global _client
    if _client is None:
        url = _get_secret("SUPABASE_URL")
        key = _get_secret("SUPABASE_KEY")
        _client = create_client(url, key)
    return _client


def load_status():
    """Returns dict: assumption_key -> row. Keys missing from the table
    (never asked yet) get a default not_yet_asked row, not a KeyError."""
    resp = _get_client().table(_TABLE).select("*").execute()
    by_key = {row["assumption_key"]: row for row in resp.data}
    result = {}
    for key in uncertainty.ASSUMPTIONS:
        result[key] = by_key.get(key) or {
            "assumption_key": key, "status": STATUS_NOT_ASKED,
            "confirmed_value": None, "confirmed_range_low": None, "confirmed_range_high": None,
            "notes": "", "updated_at": None,
        }
    return result


def mark_asked(key, notes=""):
    """Marks one assumption as asked (awaiting_response). Upserts on
    assumption_key — safe to call again to re-send/update notes."""
    if key not in uncertainty.ASSUMPTIONS:
        raise KeyError(key)
    payload = {
        "assumption_key": key, "status": STATUS_AWAITING,
        "notes": notes, "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _get_client().table(_TABLE).upsert(payload, on_conflict="assumption_key").execute()


def record_confirmation(key, value, range_low, range_high, notes=""):
    """Records a confirmed value/range for one assumption: upserts the
    Supabase row AND calls uncertainty.set_confirmed(), so
    run_monte_carlo() and compliance.py both reflect it immediately —
    see module docstring for why no other write is needed."""
    if key not in uncertainty.ASSUMPTIONS:
        raise KeyError(key)
    if range_low >= range_high:
        raise ValueError("range_low must be < range_high")
    payload = {
        "assumption_key": key, "status": STATUS_CONFIRMED,
        "confirmed_value": float(value), "confirmed_range_low": float(range_low),
        "confirmed_range_high": float(range_high), "notes": notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _get_client().table(_TABLE).upsert(payload, on_conflict="assumption_key").execute()
    uncertainty.set_confirmed(key, range_low, range_high)


def sync_confirmed_from_db():
    """Applies every already-confirmed Supabase row to uncertainty.py's
    live ASSUMPTIONS. Needed once per fresh process (e.g. app startup, or
    after a Streamlit Cloud redeploy) since set_confirmed()'s effect
    lives only in that process's memory, not in uncertainty.py's source —
    Supabase is the durable record; this replays it into memory. Also
    clears confirmed status for any key the DB no longer marks confirmed,
    so this function is idempotent and safe to call repeatedly."""
    status = load_status()
    for key, row in status.items():
        if row["status"] == STATUS_CONFIRMED and row["confirmed_range_low"] is not None:
            uncertainty.set_confirmed(key, row["confirmed_range_low"], row["confirmed_range_high"])
        else:
            uncertainty.clear_confirmed(key)
    return status


def generate_request_draft(key):
    """Drafts a confirmation-request paragraph for ONE assumption. NOT
    real correspondence — see module docstring. Reuses
    regulatory_drafting.py's disclaimer constant and header/section
    formatting conventions rather than writing new ones."""
    if key not in uncertainty.ASSUMPTIONS:
        raise KeyError(key)
    cfg = uncertainty.ASSUMPTIONS[key]
    lo, hi = uncertainty.bounds(key)

    return "\n".join([
        f"### Confirmation request — {cfg['label']}",
        "",
        f"**What we're asking:** Please confirm the real design-basis value (or a tighter, "
        f"confirmed range) for *{cfg['label']}*.",
        "",
        f"**Why:** This parameter is currently an unconfirmed design assumption in the HYGAS-AI "
        f"digital twin, propagated into the Monte Carlo uncertainty analysis on WGS conversion and "
        f"PSA recovery. A confirmed value narrows those confidence intervals directly and "
        f"strengthens the compliance documentation checklist (moves this item from \"Assumption — "
        f"pending confirmation\" to \"Confirmed\").",
        "",
        f"**Current assumed value:** {cfg['point']:g} (our own assumed ±{cfg['fraction']*100:.0f}% "
        f"band, range [{lo:.3g}, {hi:.3g}] — not sourced from any DOK-ING document).",
        "",
        regulatory_drafting.DRAFT_DISCLAIMER,
    ])


def generate_all_requests_draft():
    """One combined Markdown document with all six confirmation-request
    paragraphs — same generate-from-live-data approach as
    regulatory_drafting.generate_draft_summary()."""
    lines = [
        "# HYGAS-AI — Design-Basis Assumption Confirmation Requests",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}._",
        "",
    ]
    for key in uncertainty.ASSUMPTIONS:
        lines.append(generate_request_draft(key))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=== Draft request for steam_to_feed_ratio ===")
    print(generate_request_draft("steam_to_feed_ratio"))

    print("\n=== Current status (from Supabase) ===")
    for key, row in load_status().items():
        print(f"  {key}: {row['status']}")
