"""Streamlit smoke test (audit follow-up B6): the REAL app.py through Streamlit's
own AppTest harness, offline.

Offline means: the Supabase store is the fake client serving tests/fixtures/
sample_snapshot.json (a TEST FIXTURE, not plant data); the weather feed
(open-meteo) and the GitHub commit-age call are served canned JSON by a patched
urlopen that refuses every other URL. Asserts: no exception, 10 tabs, and that
Tab 2's category counters sum to 91.
"""
import io
import json
import os
import re
import urllib.error
from unittest import mock

from streamlit.testing.v1 import AppTest

from _fakes import FakeSupabase, patched_supabase

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app.py")

WEATHER_JSON = {"current": {"time": "2026-10-27T13:00", "temperature_2m": 13.0, "relative_humidity_2m": 52,
                            "wind_speed_10m": 3.0, "weather_code": 1}}
GITHUB_JSON = {"commit": {"committer": {"date": "2026-10-20T12:00:00Z"}}}


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _offline_urlopen(request, timeout=None, **_kwargs):
    url = request if isinstance(request, str) else request.full_url
    if url.startswith("https://api.open-meteo.com/"):
        return _Response(json.dumps(WEATHER_JSON).encode("utf-8"))
    if url.startswith("https://api.github.com/repos/Shahab-git/hygas-ai-digital-twin/commits/main"):
        return _Response(json.dumps(GITHUB_JSON).encode("utf-8"))
    raise urllib.error.URLError(f"offline smoke test: refusing {url}")


def _store_rows():
    with open(os.path.join(ROOT, "tests", "fixtures", "sample_snapshot.json"), encoding="utf-8") as handle:
        doc = json.load(handle)
    return [{"equipment_id": e["key"][0], "category": e["key"][1], "entry": e["entry"], "cycle": 1,
             "published_at": "2026-09-10T00:04:00Z"} for e in doc["entries"]]


def test_app_runs_offline_with_ten_tabs_and_tab2_counters_summing_to_91():
    fake = FakeSupabase({"plant_state_current": _store_rows()})
    with patched_supabase(fake), mock.patch("urllib.request.urlopen", side_effect=_offline_urlopen):
        at = AppTest.from_file(APP, default_timeout=90).run()

    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert [c for c in fake.calls if c[0] != "select"] == [], "the app wrote to the (fake) database"

    labels = [t.label for t in at.tabs]
    assert len(labels) == 10, labels
    assert labels[1] == "Plant Overview" and labels[-1] == "Design Basis"

    def metric_value(label):
        found = [m for m in at.metric if m.label == label]
        assert len(found) == 1, (label, [m.label for m in at.metric][:40])
        return found[0].value

    parts = {}
    for key, label in (("live", "🟢 Running – live values"), ("assumed", "🟡 Running – assumed inputs only"),
                       ("static", "🔵 Static (no live key)"), ("missing", "⚪ Missing")):
        m = re.fullmatch(r"(\d+) / 91", metric_value(label))
        assert m, (label, metric_value(label))
        parts[key] = int(m.group(1))
    captions = " ".join(str(c.value) for c in at.caption)
    summary = re.search(r"Item categories: (\d+) \+ (\d+) \+ (\d+) \+ (\d+) \+ (\d+) FAULT items = \*\*(\d+)\*\*", captions)
    assert summary, "Tab 2 category-sum caption not found"
    live, assumed, static, missing, fault_items, total = (int(x) for x in summary.groups())
    assert (live, assumed, static, missing) == (parts["live"], parts["assumed"], parts["static"], parts["missing"])
    assert live + assumed + static + missing + fault_items == 91 == total
    assert metric_value("🔴 FAULT events") == "1"
