"""registry_status.load_overlay is cached per file CONTENT, not per timestamp (task: overlay-cache hardening).

Before: the cache key was st_mtime_ns alone, so an overlay rewritten within one timestamp tick (coarse clock, same size or not) kept serving the OLD entries. For status labels that is a
correctness risk (a row could stay 'Confirmed' after its source line was removed), and it made tests/test_apply_provenance.py::test_a_corrupted_overlay_can_never_make_a_row_confirmed flaky.

The tests force the worst case on purpose: the rewrite has the SAME byte size and an IDENTICAL mtime_ns (os.utime), so only the content can tell the two files apart. No database, no network,
no engine; nothing outside tmp_path is written."""
import json
import os
import re

from python import registry_status as rs

RID = rs.row_id("registry", "FE-001", "Total hopper capacity")
GOOD = {"origin": "DOK-ING", "status": "Confirmed", "source": "RFI answer, DOK-ING, 2026-01-01", "note": ""}
NO_SOURCE = {"origin": "DOK-ING", "status": "Confirmed", "source": "", "note": ""}          # breaks its own rule: must be dropped


def _same_size(a, b):
    """Two texts of equal byte length: the shorter is padded with trailing blanks (JSON ignores them)."""
    n = max(len(a.encode("utf-8")), len(b.encode("utf-8")))
    return a + " " * (n - len(a.encode("utf-8"))), b + " " * (n - len(b.encode("utf-8")))


def _write_with_mtime(path, text, mtime_ns):
    path.write_bytes(text.encode("utf-8"))
    os.utime(path, ns=(mtime_ns, mtime_ns))


def _doc(entry):
    return json.dumps({"header": {"format": 1}, "entries": {RID: entry}})


def test_a_rewrite_with_the_same_size_and_the_same_mtime_is_re_read(tmp_path):
    p = tmp_path / "o.json"
    good, bad = _same_size(_doc(GOOD), _doc(NO_SOURCE))
    assert len(good.encode()) == len(bad.encode())
    _write_with_mtime(p, good, 1_700_000_000_000_000_000)
    assert set(rs.load_overlay(str(p))[0]) == {RID}
    _write_with_mtime(p, bad, 1_700_000_000_000_000_000)
    assert os.stat(p).st_mtime_ns == 1_700_000_000_000_000_000 and os.stat(p).st_size == len(good.encode()), "the situation the test needs: nothing but the content differs"
    entries, header = rs.load_overlay(str(p))
    assert entries == {} and header["n_ignored"] == 1, "the stale cached entry (a row still Confirmed) must not be served"


def test_the_content_wins_in_both_directions_and_over_many_rewrites(tmp_path):
    p = tmp_path / "o.json"
    good, bad = _same_size(_doc(GOOD), _doc(NO_SOURCE))
    for i in range(40):
        text, expect = (good, {RID}) if i % 2 == 0 else (bad, set())
        _write_with_mtime(p, text, 1_700_000_000_000_000_000)
        assert set(rs.load_overlay(str(p))[0]) == expect, i


def test_a_file_that_becomes_malformed_with_the_same_size_and_mtime_is_reported(tmp_path):
    p = tmp_path / "o.json"
    good = _doc(GOOD)
    broken = "{" + good[1:-1].replace('"', "'") + "}"                                           # not JSON any more
    good, broken = _same_size(good, broken)
    _write_with_mtime(p, good, 1_700_000_000_000_000_000)
    assert rs.load_overlay(str(p))[0] != {}
    _write_with_mtime(p, broken, 1_700_000_000_000_000_000)
    entries, header = rs.load_overlay(str(p))
    assert entries == {} and "error" in header


def test_an_unchanged_file_is_still_served_from_the_cache(tmp_path):
    p = tmp_path / "o.json"
    p.write_text(_doc(GOOD), encoding="utf-8")
    first = rs.load_overlay(str(p))
    second = rs.load_overlay(str(p))
    assert first[0] is second[0] and first[1] is second[1], "same content -> the cached objects, not a re-parse"
    os.utime(p, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))                      # a touched file with the same content is the same overlay
    assert rs.load_overlay(str(p))[0] is first[0]


def test_a_missing_file_still_means_everything_unverified(tmp_path):
    entries, header = rs.load_overlay(str(tmp_path / "missing.json"))
    assert entries == {} and "not found" in header["error"]


def test_the_cache_key_is_not_a_timestamp():
    src = open(rs.__file__, encoding="utf-8").read()
    body = src[src.index("def load_overlay("):src.index("def resolve_row(")]
    assert not re.search(r"st_mtime|getmtime|st_ctime", body), "a timestamp-only key is the defect this file guards against"
    assert "sha256" in body
