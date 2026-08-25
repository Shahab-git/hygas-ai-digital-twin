"""
Vendor-sourcing agent v1 — manual quote log. "Walking, not running":

This does NOT search the web, call any vendor API, or auto-fill anything.
It is a genuine tracker: you find a quote yourself (phone, email, a vendor's
website), and log it here against the real equipment item it belongs to.
A real web-search/auto-sourcing agent (v2) would replace the manual lookup
step — it has not been built yet, and this module makes no claim otherwise.

Storage: Supabase (Postgres), table `vendor_quotes` — see
data/supabase_schema.sql for the DDL. This replaces the original plain-JSON
storage (data/vendor_quotes.json, kept in the repo only as a record of the
schema that version used — no longer read or written by this module) so
that quotes logged through the *deployed* app actually persist: Streamlit
Community Cloud's container filesystem is not guaranteed to survive a
redeploy/restart, so a local file was never durable there.

Credentials: read from Streamlit secrets (SUPABASE_URL, SUPABASE_KEY) —
.streamlit/secrets.toml locally (gitignored), Streamlit Cloud's secrets
manager when deployed. Falls back to reading that same secrets.toml file
directly for standalone scripts (e.g. the migration script) that run
outside a `streamlit run` context, where st.secrets isn't populated.
"""
import os
import tomllib

from supabase import create_client

_TABLE = "vendor_quotes"
_SECRETS_PATH = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")

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


def _row_to_quote(row):
    return {
        "equipment_id": row["equipment_tag"],
        "vendor": row["vendor_name"],
        "price": float(row["price"]),
        "date": row["date"],
        "notes": row.get("notes") or "",
        "logged_at": row["created_at"],
    }


def load_quotes():
    """Returns all logged quotes, newest first. Empty list if none logged yet."""
    resp = _get_client().table(_TABLE).select("*").order("created_at", desc=True).execute()
    return [_row_to_quote(row) for row in resp.data]


def log_quote(equipment_id, vendor, price, quote_date, notes=""):
    """Inserts a manually-found quote into Supabase. Returns the new record."""
    if not equipment_id or not vendor or price is None:
        raise ValueError("equipment_id, vendor, and price are required")

    payload = {
        "equipment_tag": equipment_id,
        "vendor_name": vendor.strip(),
        "price": float(price),
        "date": str(quote_date),
        "notes": notes.strip() if notes else "",
    }
    resp = _get_client().table(_TABLE).insert(payload).execute()
    return _row_to_quote(resp.data[0])


def quotes_for(equipment_id, quotes=None):
    """All logged quotes for one equipment item, newest first."""
    quotes = load_quotes() if quotes is None else quotes
    return [q for q in quotes if q["equipment_id"] == equipment_id]


def has_quote(equipment_id, quotes=None):
    return len(quotes_for(equipment_id, quotes)) > 0


def status_counts(registry, quotes=None):
    """registry: list of items from equipment_registry.load_registry().
    Returns {total, needs_sourcing, quoted, open, not_applicable}."""
    from . import equipment_registry

    quotes = load_quotes() if quotes is None else quotes
    quoted_ids = {q["equipment_id"] for q in quotes}

    total = len(registry)
    not_applicable = sum(1 for item in registry if not equipment_registry.needs_vendor_sourcing(item))
    needs_sourcing = total - not_applicable
    quoted = sum(
        1 for item in registry
        if equipment_registry.needs_vendor_sourcing(item) and item["id"] in quoted_ids
    )
    open_count = needs_sourcing - quoted

    return {
        "total": total,
        "needs_sourcing": needs_sourcing,
        "quoted": quoted,
        "open": open_count,
        "not_applicable": not_applicable,
    }
