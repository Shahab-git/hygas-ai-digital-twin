"""
Offline measurement replay: read a long-format file of plant readings, validate it, report every problem, drop nothing (data-replacement layer,
step 1). Schema: docs/measurement_replay_schema.md.

    timestamp (UTC ISO-8601, e.g. 2026-10-30T12:00:00Z), tag (UNIT.quantity), value, unit, quality (good|suspect|bad), source

Validation never removes a row. Every row comes back with `flags` (what is wrong with it) and the report lists every issue:
  blocking flags (data_precedence.BLOCKING_FLAGS; such a reading cannot replace a Confirmed or any other value):
      bad_timestamp, bad_value, bad_quality_label, unit_mismatch, non_monotonic_time, duplicate, physically_impossible
  informational flags (reported, do not block):
      unknown_tag, outside_assumed_range, quality_suspect, quality_bad
A `quality` of suspect / bad is the sender's judgement: it is kept as given and data_precedence refuses a non-'good' Measured value.

Live feeds: this task builds none. `MeasurementSource.read(since)` is the interface a later task implements (Supabase table, SCADA export);
InMemorySource and FileSource are the only implementations here. No database, no network, no PLC / SCADA code. Not imported by the engine,
the runtime or the app. Python 3.11-compatible.
"""
import csv
import io
import json
import math

from . import data_precedence as dp
from . import parameter_table

REQUIRED_COLUMNS = ("timestamp", "tag", "value", "unit", "quality", "source")
BLOCKING = dp.BLOCKING_FLAGS
INFORMATIONAL = frozenset({"unknown_tag", "outside_assumed_range", "quality_suspect", "quality_bad"})

# Physical limits by kind of quantity: identities (a percentage is 0..100), not plant numbers.
_PHYSICAL = {
    "pct": (0.0, 100.0), "fraction": (0.0, 1.0), "nonneg": (0.0, None), "temperature_C": (-273.15, None), "any": (None, None),
}

# Sensor tags: tag -> unit, physical kind, and the snapshot entry the model publishes for it (None = the model has no counterpart).
# `field` is the key inside the entry's value dict, or None when the entry's value is the number itself.
_SENSORS = {
    "GA-001.dry_flow_nm3_h": ("Nm3/h", "nonneg", ("GA-001", "Outputs"), "dry_flow_nm3_h"),
    "GA-001.H2_mol_pct_dry": ("mol%", "pct", ("GA-001", "Outputs"), "H2_mol_pct_dry"),
    "GA-001.CO_mol_pct_dry": ("mol%", "pct", ("GA-001", "Outputs"), "CO_mol_pct_dry"),
    "GA-001.CO2_mol_pct_dry": ("mol%", "pct", ("GA-001", "Outputs"), "CO2_mol_pct_dry"),
    "GA-001.CH4_mol_pct_dry": ("mol%", "pct", ("GA-001", "Outputs"), "CH4_mol_pct_dry"),
    "GA-001.N2_mol_pct_dry": ("mol%", "pct", ("GA-001", "Outputs"), "N2_mol_pct_dry"),
    "SA-001.H2_vol_pct": ("vol%", "pct", ("SA-001", "Reading"), None),
    "SA-002.CO_vol_pct": ("vol%", "pct", ("SA-002", "Reading"), None),
    "SA-003.CO2_vol_pct": ("vol%", "pct", ("SA-003", "Reading"), None),
    "SA-004.CH4_vol_pct": ("vol%", "pct", ("SA-004", "Reading"), None),
    "SA-005.N2_vol_pct": ("vol%", "pct", ("SA-005", "Reading"), None),
    "SA-006.LHV_MJ_Nm3": ("MJ/Nm3", "nonneg", ("SA-006", "Reading"), None),
    "SA-010.flow_Nm3_h": ("Nm3/h", "nonneg", ("SA-010", "Reading"), None),
    "HB-006.psa_recovery": ("-", "fraction", ("HB-006", "PSA"), "recovery"),
    "HB-009.product_flow_nm3_h": ("Nm3/h", "nonneg", ("HB-009", "TailGas"), "product_flow_nm3_h"),
    "HB-009.tail_flow_nm3_h": ("Nm3/h", "nonneg", ("HB-009", "TailGas"), "tail_flow_nm3_h"),
    "HB-012.h2_kg_h": ("kg/h", "nonneg", ("HB-012", "Compressor"), "h2_kg_h"),
    "HB-013.level_kg": ("kg", "nonneg", ("HB-013", "Storage"), "level_kg"),
    "FE-008.feed_rate_kg_h": ("kg/h", "nonneg", ("FE-008", "Airlock"), "feed_rate_kg_h"),
    "GC-001.T_C": ("degC", "temperature_C", ("GC-001", "Temperature"), None),
    # known quantities the model does not publish (no residual is possible, but they identify parameters):
    "GA-003.air_flow_Nm3_h": ("Nm3/h", "nonneg", None, None),
    "GA-003.steam_flow_kg_h": ("kg/h", "nonneg", None, None),
    "GA-008.carbon_black_kg_h": ("kg/h", "nonneg", None, None),
}

# Parameter-table tags whose current model value is a snapshot input (the residual of a measured parameter against the model input).
_PARAMETER_SNAPSHOT = {
    "GA-001.T_gasifier_C": (("GA-001-INPUT", "operating_temperature_C"), None),
    "GA-001.ER": (("GA-001-INPUT", "equivalence_ratio"), None),
    "GA-001.steam_to_feed_kg_kg": (("GA-001-INPUT", "steam_to_feed_ratio"), None),
    "GA-001.carbon_conversion": (("GA-001-INPUT", "carbon_conversion_efficiency"), None),
    "GA-001.ch4_carbon_fraction": (("GA-001-INPUT", "ch4_carbon_fraction"), None),
    "GA-001.dry_feed_kg_h": (("GA-001-INPUT", "dry_feed_rate_kg_h"), None),
}


class ReplayFormatError(ValueError):
    """The file is not in the schema at all (a required column is missing): nothing can be read, so it is refused, not guessed."""


def build_catalog(table=None):
    """tag -> {unit, kind, snapshot_key, field, range_low, range_high, origin}. Parameter tags come from the parameter table (unit and range
    of the row the model reads, else the first row); sensor tags from _SENSORS."""
    table = table if table is not None else parameter_table.build_table()
    cat = {}
    for tag, (unit, kind, key, field) in _SENSORS.items():
        cat[tag] = {"unit": unit, "kind": kind, "snapshot_key": key, "field": field, "range_low": None, "range_high": None, "origin": "sensor catalog"}
    by_tag = {}
    for r in table:
        by_tag.setdefault(r["tag"], []).append(r)
    for tag, rows in by_tag.items():
        row = next((r for r in rows if r["overridable_via"] != parameter_table.VIA_REGISTRY), rows[0])
        if not isinstance(row["value"], (int, float)) or isinstance(row["value"], bool):
            continue                      # dict / string parameters (feed composition, tail_gas_mode) cannot be a numeric reading
        key, field = _PARAMETER_SNAPSHOT.get(tag, (None, None))
        cat[tag] = {"unit": row["unit"], "kind": "any", "snapshot_key": key, "field": field,
                    "range_low": row["range_low"], "range_high": row["range_high"], "origin": "parameter table"}
    return cat


# --- reading files ----------------------------------------------------------------------------------------------------------------

def _raw_reading(i, rec):
    return {"row": i, "timestamp": rec.get("timestamp"), "tag": rec.get("tag"), "value": rec.get("value"), "unit": rec.get("unit"),
            "quality": rec.get("quality"), "source": rec.get("source"), "t": None, "flags": []}


def parse_csv_text(text):
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ReplayFormatError(f"CSV is missing required column(s) {missing}; required: {REQUIRED_COLUMNS}")
    return [_raw_reading(i, {k: (v.strip() if isinstance(v, str) else v) for k, v in rec.items()}) for i, rec in enumerate(reader, start=1)]


def parse_json_text(text):
    data = json.loads(text)
    recs = data["readings"] if isinstance(data, dict) and "readings" in data else data
    if not isinstance(recs, list):
        raise ReplayFormatError("JSON must be a list of readings or {'readings': [...]}")
    for i, rec in enumerate(recs, start=1):
        missing = [c for c in REQUIRED_COLUMNS if c not in rec]
        if missing:
            raise ReplayFormatError(f"JSON reading {i} is missing required field(s) {missing}; required: {REQUIRED_COLUMNS}")
    return [_raw_reading(i, rec) for i, rec in enumerate(recs, start=1)]


def load_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return parse_json_text(text) if str(path).lower().endswith(".json") else parse_csv_text(text)


# --- sources ----------------------------------------------------------------------------------------------------------------------

class MeasurementSource:
    """Interface a later task implements for a live feed (a Supabase measurement table, a SCADA export). `read(since)` returns raw readings
    (dicts as produced by parse_csv_text / parse_json_text) strictly AFTER `since` (a UTC ISO string or datetime; None = all), in arrival order.
    A reading whose timestamp cannot be parsed is always returned (it is flagged, never silently dropped). Must not write anywhere."""

    def read(self, since=None):
        raise NotImplementedError


def _after(reading, since_dt):
    if since_dt is None:
        return True
    try:
        t = dp.parse_timestamp(reading["timestamp"])
    except (ValueError, TypeError):
        return True
    return t is None or t > since_dt


class InMemorySource(MeasurementSource):
    def __init__(self, readings):
        self._readings = [dict(r) for r in readings]

    def read(self, since=None):
        s = dp.parse_timestamp(since) if since is not None else None
        return [dict(r) for r in self._readings if _after(r, s)]


class FileSource(MeasurementSource):
    def __init__(self, path):
        self.path = path

    def read(self, since=None):
        s = dp.parse_timestamp(since) if since is not None else None
        return [r for r in load_file(self.path) if _after(r, s)]


# --- validation -------------------------------------------------------------------------------------------------------------------

def _issue(issues, reading, kind, severity, message):
    issues.append({"row": reading["row"], "tag": reading["tag"], "kind": kind, "severity": severity, "message": message})


def validate(readings, catalog=None):
    """Validates in arrival order. Returns {"readings": every row, annotated; "issues": [...]; "counts": {kind: n}}; len(readings) is preserved."""
    catalog = catalog if catalog is not None else build_catalog()
    out, issues = [], []
    last_t, seen = {}, {}
    for raw in readings:
        r = dict(raw)
        r["flags"] = list(raw.get("flags", ()))
        # timestamp
        try:
            r["t"] = dp.parse_timestamp(r["timestamp"]) if r["timestamp"] not in (None, "") else None
            if r["t"] is None:
                raise ValueError("timestamp is empty")
        except (ValueError, TypeError) as e:
            r["t"] = None
            r["flags"].append("bad_timestamp")
            _issue(issues, r, "bad_timestamp", "error", str(e))
        # value
        try:
            v = float(r["value"])
            if not math.isfinite(v):
                raise ValueError("not finite")
            r["value"] = v
        except (TypeError, ValueError):
            r["flags"].append("bad_value")
            _issue(issues, r, "bad_value", "error", f"value {r['value']!r} is not a finite number")
            r["value"] = None
        # quality
        q = (r["quality"] or "").strip().lower() if isinstance(r["quality"], str) else r["quality"]
        if q not in dp.QUALITIES:
            r["flags"].append("bad_quality_label")
            _issue(issues, r, "bad_quality_label", "error", f"quality {r['quality']!r} is not one of {dp.QUALITIES}")
            r["quality"] = None
        else:
            r["quality"] = q
            if q != dp.QUALITY_GOOD:
                r["flags"].append(f"quality_{q}")
                _issue(issues, r, f"quality_{q}", "info", f"sender marked the reading {q}")
        # tag, unit, ranges
        info = catalog.get(r["tag"])
        if info is None:
            r["flags"].append("unknown_tag")
            _issue(issues, r, "unknown_tag", "warning", f"tag {r['tag']!r} is neither a parameter-table tag nor a known sensor tag")
        else:
            if dp.normalise_unit(r["unit"]) != dp.normalise_unit(info["unit"]):
                r["flags"].append("unit_mismatch")
                _issue(issues, r, "unit_mismatch", "error", f"unit {r['unit']!r} but {r['tag']} is {info['unit']!r}")
            if r["value"] is not None:
                lo, hi = _PHYSICAL[info["kind"]]
                if (lo is not None and r["value"] < lo) or (hi is not None and r["value"] > hi):
                    r["flags"].append("physically_impossible")
                    _issue(issues, r, "physically_impossible", "error", f"value {r['value']} is outside the physical limits ({lo}, {hi}) of kind {info['kind']!r}")
                a, b = info["range_low"], info["range_high"]
                if (a is not None and r["value"] < a) or (b is not None and r["value"] > b):
                    r["flags"].append("outside_assumed_range")
                    _issue(issues, r, "outside_assumed_range", "info", f"value {r['value']} is outside the table's range [{a}, {b}] (informational: a measurement outside an Assumed range is the point of measuring)")
        # time order and duplicates, per tag, in arrival order
        if r["t"] is not None:
            key = (r["tag"], r["t"])
            if key in seen:
                same = seen[key] == r["value"]
                r["flags"].append("duplicate")
                _issue(issues, r, "duplicate", "error", f"second reading of {r['tag']} at {r['timestamp']} ({'identical value' if same else 'CONFLICTING value ' + str(seen[key]) + ' vs ' + str(r['value'])})")
            else:
                seen[key] = r["value"]
                prev = last_t.get(r["tag"])
                if prev is not None and r["t"] < prev:
                    r["flags"].append("non_monotonic_time")
                    _issue(issues, r, "non_monotonic_time", "error", f"{r['timestamp']} is earlier than an already-seen reading of {r['tag']} ({prev.isoformat()})")
                else:
                    last_t[r["tag"]] = r["t"]
        out.append(r)
    counts = {}
    for i in issues:
        counts[i["kind"]] = counts.get(i["kind"], 0) + 1
    return {"readings": out, "issues": issues, "counts": counts}


def replay(source, catalog=None, since=None):
    """Reads a MeasurementSource and validates what it returns."""
    return validate(source.read(since), catalog)


def usable(readings):
    """Readings that carry no blocking flag and have quality 'good' (the ones data_precedence would let take part). Nothing is deleted from the report."""
    return [r for r in readings if r["quality"] == dp.QUALITY_GOOD and not (set(r["flags"]) & BLOCKING) and r["value"] is not None]
