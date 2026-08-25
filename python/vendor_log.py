"""
Vendor-sourcing agent v1 — manual quote log. "Walking, not running":

This does NOT search the web, call any vendor API, or auto-fill anything.
It is a genuine tracker: you find a quote yourself (phone, email, a vendor's
website), and log it here against the real equipment item it belongs to.
A real web-search/auto-sourcing agent (v2) would replace the manual lookup
step — it has not been built yet, and this module makes no claim otherwise.

Storage: a plain local JSON file (data/vendor_quotes.json), not a database,
per the v1 scope. IMPORTANT caveat, stated here and in the UI: on Streamlit
Community Cloud the container filesystem is not guaranteed to persist across
redeploys/restarts, so quotes logged live on the deployed app may not survive
a redeploy. They *do* persist locally and in git history if this file is
committed after logging — which is how the two test entries below were
captured.
"""
import json
import os
from datetime import datetime, timezone

_QUOTES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "vendor_quotes.json")


def load_quotes():
    """Returns all logged quotes, newest first. Empty list if none logged yet."""
    if not os.path.exists(_QUOTES_PATH):
        return []
    with open(_QUOTES_PATH, "r", encoding="utf-8") as f:
        quotes = json.load(f)
    return sorted(quotes, key=lambda q: q["logged_at"], reverse=True)


def log_quote(equipment_id, vendor, price, quote_date, notes=""):
    """Appends a manually-found quote and persists it to disk. Returns the new record."""
    if not equipment_id or not vendor or price is None:
        raise ValueError("equipment_id, vendor, and price are required")

    record = {
        "equipment_id": equipment_id,
        "vendor": vendor.strip(),
        "price": float(price),
        "date": str(quote_date),
        "notes": notes.strip() if notes else "",
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }

    quotes = load_quotes()
    quotes.append(record)
    os.makedirs(os.path.dirname(_QUOTES_PATH), exist_ok=True)
    with open(_QUOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(quotes, f, indent=2, ensure_ascii=False)
    return record


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
