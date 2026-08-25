"""
One-off migration: data/vendor_quotes.json -> Supabase `vendor_quotes` table.

Run once, after:
  1. data/supabase_schema.sql has been run in the Supabase SQL Editor, and
  2. .streamlit/secrets.toml has SUPABASE_URL and SUPABASE_KEY set.

Preserves each entry's original logged_at timestamp as created_at, rather
than letting the table default to "now" for historical records.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python.vendor_log import _get_client, _TABLE  # noqa: E402

JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "vendor_quotes.json")


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        old_quotes = json.load(f)

    client = _get_client()
    existing = {row["equipment_tag"] for row in client.table(_TABLE).select("equipment_tag").execute().data}

    inserted, skipped = 0, 0
    for q in old_quotes:
        if q["equipment_id"] in existing:
            print(f"skip (already present): {q['equipment_id']} — {q['vendor']}")
            skipped += 1
            continue
        payload = {
            "equipment_tag": q["equipment_id"],
            "vendor_name": q["vendor"],
            "price": float(q["price"]),
            "date": q["date"],
            "notes": q.get("notes") or "",
            "created_at": q["logged_at"],
        }
        client.table(_TABLE).insert(payload).execute()
        print(f"migrated: {q['equipment_id']} — {q['vendor']} (€{q['price']:,.0f})")
        inserted += 1

    print(f"\nDone. Inserted {inserted}, skipped {skipped} (already present).")


if __name__ == "__main__":
    main()
