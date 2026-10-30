"""
Precedence rule for a parameter that has more than one candidate value (data-replacement layer, step 1). A pure function; nothing is wired.

    resolve(candidates) -> {"winner", "status", "value", "override", "blocked_overrides", "replaced", "tie", "trail"}

A candidate is `candidate(value, status, timestamp, source, unit=None, quality=None, flags=())`.

ORDER (best first):  Measured > Confirmed > Calculated > Estimated > Assumed > Missing.
  * Ties inside one status: the newest timestamp wins (a candidate without a timestamp is older than any with one). Equal newest timestamps
    are a TIE: the first listed wins and `tie` is True, never silently.
  * A `Confirmed` value is never replaced by a Calculated / Estimated / Assumed one, whatever the timestamps (status ranks before time).
  * A `Measured` candidate takes part only if its quality passes: `quality == "good"` and none of BLOCKING_FLAGS among its flags. A Measured
    candidate that fails is NOT dropped: it appears in the audit trail as rejected, and if a Confirmed value is thereby kept, `blocked_overrides`
    names it. A flag that is not blocking (e.g. `outside_assumed_range`) does not stop a measurement: a reading outside an Assumed range is
    exactly what a measurement is for.
  * A `Measured` winner over a `Confirmed` candidate is reported as `override`, with BOTH values, never silently.
  * A `Missing` candidate never wins over any other; with only Missing candidates (or none) the result is status Missing, value None.

`dry_run(table, measurements)` lists which parameters WOULD change and by how much if the resolved values were adopted. It reads the table
(parameter_table.build_table()) and a list of readings; it touches no engine, no snapshot, no store.

Not imported by the engine, the runtime or the app. Python 3.11-compatible.
"""
from datetime import datetime, timezone

from . import plant_status as ps

STATUS_CONFIRMED = "Confirmed"
PRECEDENCE = (ps.STATUS_MEASURED, STATUS_CONFIRMED, ps.STATUS_CALCULATED, ps.STATUS_ESTIMATED, ps.STATUS_ASSUMED, ps.STATUS_MISSING)
RANK = {s: i for i, s in enumerate(PRECEDENCE)}

QUALITY_GOOD = "good"
QUALITIES = ("good", "suspect", "bad")
# Flags that make a reading unusable as a replacement. measurement_replay sets them; they are defined here so the rule and the validator agree.
BLOCKING_FLAGS = frozenset({"unit_mismatch", "non_monotonic_time", "duplicate", "bad_timestamp", "bad_value", "bad_quality_label",
                            "physically_impossible"})


_FIELDS = ("value", "status", "timestamp", "source", "unit", "quality", "flags")


def parse_timestamp(ts):
    """UTC ISO-8601 -> aware datetime; None -> None. A naive timestamp is refused: it has no defined zone."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
    else:
        try:
            dt = datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"timestamp {ts!r} is not ISO-8601: {e}") from None
    if dt.tzinfo is None:
        raise ValueError(f"timestamp {ts!r} has no timezone; use UTC (e.g. 2026-10-30T12:00:00Z)")
    return dt.astimezone(timezone.utc)


def candidate(value, status, timestamp=None, source="", unit=None, quality=None, flags=()):
    """A validated candidate dict. Follows plant_status's rule: Missing carries no value, every other status carries one."""
    if status not in RANK:
        raise ValueError(f"status {status!r} is not one of {PRECEDENCE}")
    if status == ps.STATUS_MISSING and value is not None:
        raise ValueError("a Missing candidate must have value None")
    if status != ps.STATUS_MISSING and value is None:
        raise ValueError(f"a {status} candidate must have a value")
    if quality is not None and quality not in QUALITIES:
        raise ValueError(f"quality {quality!r} is not one of {QUALITIES}")
    parse_timestamp(timestamp)
    return {"value": value, "status": status, "timestamp": timestamp, "source": source, "unit": unit, "quality": quality, "flags": list(flags)}


def measured_quality_problem(c):
    """None if a Measured candidate may take part; otherwise the reason it may not."""
    if c["quality"] != QUALITY_GOOD:
        return f"quality is {c['quality']!r}, not 'good'"
    blocking = sorted(set(c["flags"]) & BLOCKING_FLAGS)
    if blocking:
        return f"blocking flag(s) {blocking}"
    return None


def _brief(c):
    return {k: c[k] for k in ("value", "status", "timestamp", "source", "unit")}


def resolve(candidates):
    cands = [candidate(**{k: c[k] for k in _FIELDS if k in c}) for c in candidates]
    trail = []
    eligible = []
    for i, c in enumerate(cands):
        row = {"index": i, "candidate": _brief(c), "rank": RANK[c["status"]], "outcome": None, "reason": None}
        if c["status"] == ps.STATUS_MISSING:
            row["outcome"], row["reason"] = "ignored", "Missing never wins"
        elif c["status"] == ps.STATUS_MEASURED and measured_quality_problem(c):
            row["outcome"], row["reason"] = "rejected", "Measured candidate failed quality: " + measured_quality_problem(c)
        else:
            eligible.append(i)
        trail.append(row)

    if not eligible:
        return {"winner": None, "status": ps.STATUS_MISSING, "value": None, "override": None, "tie": False,
                "blocked_overrides": _blocked(cands, trail, None), "replaced": [], "trail": trail}

    best_rank = min(RANK[cands[i]["status"]] for i in eligible)
    top = [i for i in eligible if RANK[cands[i]["status"]] == best_rank]
    stamps = {i: parse_timestamp(cands[i]["timestamp"]) for i in top}
    newest = max((s for s in stamps.values() if s is not None), default=None)
    top = [i for i in top if stamps[i] == newest]
    winner = top[0]
    tie = len(top) > 1

    replaced = []
    for i in eligible:
        if i == winner:
            trail[i]["outcome"], trail[i]["reason"] = "winner", ("tie on status and timestamp: the first listed wins" if tie else "highest precedence, newest")
        elif RANK[cands[i]["status"]] > best_rank:
            trail[i]["outcome"], trail[i]["reason"] = "superseded", f"lower precedence than {cands[winner]['status']}"
            replaced.append(_brief(cands[i]))
        else:
            trail[i]["outcome"], trail[i]["reason"] = "superseded", ("older than the winner of the same status" if i not in top else "tie: listed after the winner")
            replaced.append(_brief(cands[i]))

    w = cands[winner]
    override = None
    if w["status"] == ps.STATUS_MEASURED:
        confirmed = [_brief(cands[i]) for i in eligible if cands[i]["status"] == STATUS_CONFIRMED]
        if confirmed:
            override = {"kind": "Measured replaces Confirmed", "measured": _brief(w), "confirmed": confirmed}
    return {"winner": winner, "status": w["status"], "value": w["value"], "override": override, "tie": tie,
            "blocked_overrides": _blocked(cands, trail, w), "replaced": replaced, "trail": trail}


def _blocked(cands, trail, winner):
    """Measured candidates rejected for quality while a Confirmed value is (still) there: the override that did NOT happen, named."""
    has_confirmed = any(c["status"] == STATUS_CONFIRMED for c in cands)
    if not has_confirmed:
        return []
    return [{"measured": t["candidate"], "reason": t["reason"]} for t in trail if t["outcome"] == "rejected"]


# --- dry run ---------------------------------------------------------------------------------------------------------------------

_UNIT_ALIASES = {"³": "3", "°c": "degc", "℃": "degc", "—": "-", "–": "-"}


def normalise_unit(u):
    """'Nm³/h' -> 'nm3/h', '°C' -> 'degc'; '', None and the dash placeholders -> '-' (dimensionless)."""
    if u is None:
        return "-"
    s = str(u).strip().lower()
    for a, b in _UNIT_ALIASES.items():
        s = s.replace(a, b)
    s = s.replace(" ", "")
    return s if s else "-"


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def dry_run(table, measurements):
    """Which parameters WOULD change if the resolved values were adopted, and by how much. Touches nothing.

    table: parameter_table.build_table() rows. measurements: dicts with timestamp, tag, value, unit, quality, source and optionally flags.
    For every measured tag that is a table tag: the model value (the row the model really reads: not a `registry` row, which the engine
    ignores), the resolved candidate over {all table rows of that tag} + {all its readings}, the change, the override if any, the readings
    rejected. A reading whose unit differs from the parameter's is rejected as `unit_mismatch`, not converted. Tags that are not table
    parameters are returned separately. Of several good readings the NEWEST wins: that is the rule, not an estimator (no averaging, no fit).
    """
    by_tag = {}
    for r in table:
        by_tag.setdefault(r["tag"], []).append(r)
    readings = {}
    for m in measurements:
        readings.setdefault(m["tag"], []).append(m)

    changes, not_parameters = [], []
    for tag in sorted(readings):
        rows = by_tag.get(tag)
        if not rows:
            not_parameters.append({"tag": tag, "n_readings": len(readings[tag])})
            continue
        model_rows = [r for r in rows if r["overridable_via"] != "registry"]
        model = model_rows[0] if model_rows else None
        ref_unit = normalise_unit((model or rows[0])["unit"])
        cands = [candidate(r["value"], r["status"], None, f"table: {r['source']}", r["unit"]) for r in rows]
        for m in readings[tag]:
            flags = list(m.get("flags", ()))
            if normalise_unit(m.get("unit")) != ref_unit:
                flags.append("unit_mismatch")
            cands.append(candidate(m["value"], ps.STATUS_MEASURED, m["timestamp"], m.get("source", ""), m.get("unit"), m.get("quality"), flags))
        res = resolve(cands)
        model_value = model["value"] if model else None
        new_value = res["value"]
        change = {"tag": tag, "unit": (model or rows[0])["unit"], "model_value": model_value, "model_status": model["status"] if model else None,
                  "resolved_value": new_value, "resolved_status": res["status"], "resolved_source": cands[res["winner"]]["source"] if res["winner"] is not None else None,
                  "changes": new_value != model_value, "abs_change": None, "rel_change": None, "override": res["override"],
                  "blocked_overrides": res["blocked_overrides"], "n_readings": len(readings[tag]),
                  "n_rejected": sum(1 for t in res["trail"] if t["outcome"] == "rejected"), "tie": res["tie"], "trail": res["trail"]}
        if _is_number(model_value) and _is_number(new_value):
            change["abs_change"] = new_value - model_value
            change["rel_change"] = (new_value - model_value) / model_value if model_value else None
        changes.append(change)
    return {"changes": changes, "not_parameters": not_parameters}
