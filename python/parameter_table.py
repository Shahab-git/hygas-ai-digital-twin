"""
Parameter table: one read-only view of every tunable input of the twin (data-replacement layer, step 1).

NOTHING here is a second copy of a value. Every row is built at call time by READING the place that owns the value (a module constant, an
engine input function, the uncertainty module, the dynamics TAU_SPECS, a registry row); `file_line` is found by searching the owning file for
the defining statement, so a moved or renamed constant fails loudly (LookupError) instead of silently pointing at a stale line. Whether a
parameter can be overridden through the engine's normal input mechanism is not typed in either: it is checked against the models a fresh
engine really registers.

Not imported by the engine, the runtime or the app. Changes no engine equation, default, Confirmed value or registry row.

Columns: tag, value, unit, status, source, range_low, range_high, overridable_via, file_line, note.
  * `tag` convention `UNIT.quantity` (unit id of the equipment that owns it, then the quantity with its unit suffix), e.g. `GA-001.T_gasifier_C`.
    A parameter that lives in two places (an engine input AND a registry row, e.g. the gasifier temperature) has two rows with the SAME tag
    and different `source`: those are the candidates data_precedence.resolve() chooses between.
  * `status`: the project's vocabulary (plant_status.ALL_STATUSES) plus `Confirmed` (equipment_datasheet.STATUS_CONFIRMED, the default of every
    registry row without a status key). Where the repo carries NO status tag for a constant, the row says so in `note` ("STATUS ASSIGNED BY
    THIS TABLE") rather than pretending the repo had tagged it.
  * `range_low` / `range_high`: from the repo only; None = Missing (no range exists in the repo).
  * `overridable_via`: `engine input` (a registered ("..-INPUT", ..) model: build_live_snapshot(overrides={key: fn})), `registry` (a row of
    data/equipment_registry.json, which the engine does NOT read), `dynamics argument` (dynamics.run_transient(taus=...), not an engine input),
    or `code only` (a module constant: needs a code edit).
"""
import json
import os
import re

from . import (dynamics, equipment_datasheet, equipment_registry, ga001_gasifier_model as ga001, gasifier_mass_balance, plant_status as ps,
               psa, shared_plant_state, simulation_engine, uncertainty)
from . import design_basis

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REGISTRY_FILE = "data/equipment_registry.json"

STATUS_CONFIRMED = equipment_datasheet.STATUS_CONFIRMED
TABLE_STATUSES = (STATUS_CONFIRMED,) + ps.ALL_STATUSES

VIA_ENGINE = "engine input"
VIA_REGISTRY = "registry"
VIA_DYNAMICS = "dynamics argument"
VIA_CODE = "code only"
COLUMNS = ("tag", "value", "unit", "status", "source", "range_low", "range_high", "overridable_via", "file_line", "note")

_ASSIGNED = "STATUS ASSIGNED BY THIS TABLE (the repo carries no status tag for this constant): "


# --- locating the defining line -------------------------------------------------------------------------------------------------

def _lines(rel_path):
    with open(os.path.join(_ROOT, rel_path), encoding="utf-8") as f:
        return f.read().splitlines()


def _find_line(rel_path, pattern, after=0):
    """1-based line of the first line (after line `after`) matching `pattern`. LookupError if none: the table must not point at a guess."""
    rx = re.compile(pattern)
    for i, text in enumerate(_lines(rel_path), start=1):
        if i > after and rx.search(text):
            return i
    raise LookupError(f"{rel_path}: no line matches {pattern!r}; the parameter table's source moved or was renamed")


def _registry_line(item_id, parameter):
    first = _find_line(_REGISTRY_FILE, r'"id": "%s"' % re.escape(item_id))
    return _find_line(_REGISTRY_FILE, r'"parameter": "%s"' % re.escape(parameter), after=first)


def _loc(rel_path, pattern):
    return f"{rel_path}:{_find_line(rel_path, pattern)}"


def _row(tag, value, unit, status, source, lo, hi, via, file_line, note=""):
    if status not in TABLE_STATUSES:
        raise ValueError(f"{tag}: status {status!r} is not in {TABLE_STATUSES}")
    return {"tag": tag, "value": value, "unit": unit, "status": status, "source": source, "range_low": lo, "range_high": hi,
            "overridable_via": via, "file_line": file_line, "note": note}


# --- what a fresh engine registers (the override mechanism, checked, not typed) ----------------------------------------------------

def registered_engine_keys():
    """The keys of every model GA-001's registration puts in a fresh engine. A parameter is an `engine input` only if its key is in here."""
    engine = simulation_engine.SimulationEngine(shared_plant_state.SharedPlantState())
    ga001.register_ga001(engine)
    return set(engine._models)


def _no_engine_get_input(key):
    """A get_input with nothing behind it: makes the input functions return their own fallback / default entry."""
    return {"value": None, "unit": None, "status": ps.STATUS_MISSING, "missing_reason": "parameter_table: no engine is running"}


# --- sources ------------------------------------------------------------------------------------------------------------------------

def _engine_input_rows(keys):
    g = "python/ga001_gasifier_model.py"
    u = "python/uncertainty.py"
    spec = [
        # tag, key, input fn, unit, (file, pattern of the line that DEFINES the value), range (lo, hi) or None, note
        ("GA-001.dry_feed_kg_h", ("GA-001-INPUT", "dry_feed_rate_kg_h"), ga001._input_dry_feed_rate, "kg/h",
         ("python/gasifier_mass_balance.py", r"^DEFAULT_DRY_FEED_KG_H\b"), None,
         "Shown with FE-005 absent (the fallback placeholder). In the running engine this input is Calculated from FE-005's dry-solids balance "
         "(37.5 kg/h dry at the defaults), not this placeholder."),
        ("GA-001.ER", ("GA-001-INPUT", "equivalence_ratio"), ga001._input_equivalence_ratio, "-",
         (u, r'^\s*"air_equivalence_ratio": \{'), uncertainty.bounds("air_equivalence_ratio"),
         "Range is uncertainty.py's default +/-15 % band (UNCERTAINTY_FRACTION, 'our own assumed default'), unless a confirmed range is set."),
        ("GA-001.steam_to_feed_kg_kg", ("GA-001-INPUT", "steam_to_feed_ratio"), ga001._input_steam_to_feed_ratio, "kg/kg",
         (u, r'^\s*"steam_to_feed_ratio": \{'), uncertainty.bounds("steam_to_feed_ratio"),
         "Range is uncertainty.py's default +/-15 % band, unless a confirmed range is set."),
        ("GA-001.carbon_conversion", ("GA-001-INPUT", "carbon_conversion_efficiency"), ga001._input_carbon_conversion_efficiency, "-",
         (g, r"^CARBON_CONVERSION_EFFICIENCY\s*="), ga001.CARBON_CONVERSION_EFFICIENCY_RANGE, ""),
        ("GA-001.ch4_carbon_fraction", ("GA-001-INPUT", "ch4_carbon_fraction"), ga001._input_ch4_carbon_fraction, "-",
         (g, r"^CH4_CARBON_FRACTION\s*="), ga001.CH4_CARBON_FRACTION_RANGE, ""),
        ("GA-001.feedstock_daf_CHON", ("GA-001-INPUT", "feedstock_composition"), ga001._input_feedstock_composition, "mass fraction (dry, ash-free)",
         (g, r"^FEEDSTOCK_C_FRACTION\s*="), None,
         "A dict of the four fractions; no range exists in the repo for the C/H/O/N split (DOK-ING's RFI #2 gives only open C/H floors)."),
        ("GA-001.T_gasifier_C", ("GA-001-INPUT", "operating_temperature_C"), ga001._input_operating_temperature_c, "degC",
         (g, r"^GA001_OPERATING_TEMPERATURE_C\s*="), None,
         "The input's docstring says it is read from the registry; the code holds the 950.0 as a module constant. No range exists in the repo."),
        ("GA-001.tail_gas_mode", ga001.TAIL_GAS_MODE_KEY, ga001._input_tail_gas_mode, "mode",
         (g, r"^TAIL_GAS_MODE_DEFAULT\s*="), None, "A switch, not a measurement: one of %s." % (ga001.TAIL_GAS_MODES,)),
        ("GA-001.unconverted_C_to_carbon_black", ga001.CARBON_BLACK_SPLIT_KEY, ga001._input_carbon_black_split, "fraction",
         (g, r"^CARBON_BLACK_SPLIT_DEFAULT\s*="), ga001.CARBON_BLACK_SPLIT_RANGE, ""),
    ]
    rows = []
    for tag, key, fn, unit, (vfile, vpat), rng, note in spec:
        entry = fn(_no_engine_get_input)
        lo, hi = rng if rng else (None, None)
        via = VIA_ENGINE if key in keys else VIA_CODE
        fn_loc = _loc(g, r"^def %s\(" % re.escape(fn.__name__))
        rows.append(_row(tag, entry["value"], unit, entry["status"],
                         f"engine input {key[0]}/{key[1]} via {fn.__name__} ({fn_loc}); basis {entry.get('validation_basis')}",
                         lo, hi, via, _loc(vfile, vpat), note))
    return rows


def _code_only_rows():
    ash_lo, ash_hi = design_basis.FEEDSTOCK_COMPOSITION_CONFIRMED_RANGES["ash_pct"]
    return [
        _row("GA-001.ash_fraction", gasifier_mass_balance.ASH_FRACTION, "mass fraction of dry feed", STATUS_CONFIRMED,
             "module constant gasifier_mass_balance.ASH_FRACTION (reused by ga001 as ASH_FRACTION)",
             ash_lo / 100.0, ash_hi / 100.0, VIA_CODE, _loc("python/gasifier_mass_balance.py", r"^ASH_FRACTION\s*="),
             "Status as the code states it ('GA-005: 10% ash content (dry basis)', ga001_gasifier_model.py comment on ASH_FRACTION). Range = "
             "DOK-ING's confirmed ash band 5-15 % (design_basis.FEEDSTOCK_COMPOSITION_CONFIRMED_RANGES). NOT an engine input: a feed with another "
             "ash content cannot be represented without a code edit."),
        _row("HB-006.psa_K1", psa.K1, "-", ps.STATUS_ASSUMED, "module constant psa.K1", None, None, VIA_CODE, _loc("python/psa.py", r"^K1\s*="),
             _ASSIGNED + "psa.py calls itself 'a simplified first-pass industrial design heuristic' and K1 'calibrated to the established 75% "
             "design-point recovery'. The HB-006 engine adapter does not pass k1_scale."),
        _row("HB-006.psa_void_loss", psa.VOID_LOSS, "-", ps.STATUS_ASSUMED, "module constant psa.VOID_LOSS", None, None, VIA_CODE,
             _loc("python/psa.py", r"^VOID_LOSS\s*="), _ASSIGNED + "same module docstring as psa.K1."),
        _row("HB-006.psa_selectivity", dict(psa.SELECTIVITY), "-", ps.STATUS_ASSUMED, "module constant psa.SELECTIVITY", None, None, VIA_CODE,
             _loc("python/psa.py", r"^SELECTIVITY\s*="), _ASSIGNED + "same module docstring as psa.K1."),
        _row("HB-006.psa_target_calibration", uncertainty.ASSUMPTIONS["psa_target_calibration"]["point"], "-", ps.STATUS_ASSUMED,
             "uncertainty.ASSUMPTIONS['psa_target_calibration']", *uncertainty.bounds("psa_target_calibration"), VIA_CODE,
             _loc("python/uncertainty.py", r'^\s*"psa_target_calibration": \{'),
             "Scales K1 inside the Monte Carlo only (uncertainty.py, wired_in=%s); the engine's HB-006 does not read it." %
             uncertainty.ASSUMPTIONS["psa_target_calibration"]["wired_in"]),
        _row("HB-004.wgs_target_calibration", uncertainty.ASSUMPTIONS["wgs_target_calibration"]["point"], "-", ps.STATUS_ASSUMED,
             "uncertainty.ASSUMPTIONS['wgs_target_calibration']", *uncertainty.bounds("wgs_target_calibration"), VIA_CODE,
             _loc("python/uncertainty.py", r'^\s*"wgs_target_calibration": \{'),
             "Monte-Carlo scaling only (wired_in=%s); the engine's WGS stages do not read it." % uncertainty.ASSUMPTIONS["wgs_target_calibration"]["wired_in"]),
    ]


_TAU_TAGS = {
    "T_gasifier": ("GA-001.tau_T_s", "lag from the gasifier temperature setpoint to the temperature GA-001 uses"),
    "tau_conv": ("GA-001.tau_conv_s", "fuel conversion / bed inventory lag on the dry feed"),
    "tau_gas": ("GA-001.tau_gas_s", "gas-phase transport and mixing lag of GA-001's outlet"),
    "tau_rec": ("HB-009.tau_rec_s", "transport delay of the PSA tail gas back to GA-001"),
    "EU008_cooling_water": ("EU-008.tau_cooling_water_s", "EU-008 tower-water relaxation"),
}


def _dynamics_rows():
    rows = []
    for name, spec in dynamics.TAU_SPECS.items():
        tag, what = _TAU_TAGS[name]
        lo, hi = spec.range_s
        rows.append(_row(tag, spec.default_s, "s", spec.status, f"dynamics.TAU_SPECS['{name}']", lo, hi, VIA_DYNAMICS,
                         _loc("python/dynamics.py", r'^\s*"%s": TauSpec\(' % re.escape(name)),
                         what + ". Used by the what-if layer only; the hourly engine has no time constants. dynamics.run_transient(taus={name: seconds}) overrides it."))
    return rows


def _registry_value(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return raw


def _registry_rows():
    reg = {item["id"]: item for item in equipment_registry.load_registry()}
    spec = [
        # tag, item id, registry parameter name
        ("GA-001.T_gasifier_C", "GA-001", "Operating temperature (typical)"),
        ("GA-003.air_flow_design_Nm3_h", "GA-003", "Primary air flow rate (design)"),
        ("GA-003.steam_flow_design_kg_h", "GA-003", "Steam flow rate (design)"),
        ("GA-001.ER", "GA-003", "Air-to-fuel equivalence ratio (ER)"),
        ("GA-004.air_preheat_C", "GA-004", "Air preheat temperature"),
        ("GA-004.steam_T_C", "GA-004", "Steam temperature (design)"),
    ]
    rows = []
    for tag, item_id, parameter in spec:
        p = next((q for q in reg[item_id]["parameters"] if q["parameter"] == parameter), None)
        if p is None:
            raise LookupError(f"registry {item_id} has no parameter {parameter!r}")
        status = p.get("status", STATUS_CONFIRMED)
        remark = p.get("remarks", "") or ""
        note = ("Registry rows without a status key count as Confirmed (equipment_datasheet.py:%d). The engine does not read this row." %
                _find_line("python/equipment_datasheet.py", r"^STATUS_CONFIRMED\s*="))
        if "not DOK-ING-confirmed" in remark or "treat as an estimate" in remark:
            note += f" CAVEAT, verbatim from the row's own remark: \"{remark}\" (the row still counts as Confirmed by the default)."
        rows.append(_row(tag, _registry_value(p["value"]), p["unit"], status, f"registry {item_id} '{parameter}'", None, None, VIA_REGISTRY,
                         f"{_REGISTRY_FILE}:{_registry_line(item_id, parameter)}", note))
    return rows


# --- public API ---------------------------------------------------------------------------------------------------------------------

def build_table():
    """The whole table: a list of row dicts with COLUMNS as keys. Built fresh on every call from the owning sources."""
    keys = registered_engine_keys()
    rows = _engine_input_rows(keys) + _code_only_rows() + _dynamics_rows() + _registry_rows()
    return sorted(rows, key=lambda r: (r["tag"], r["source"]))


def code_only_rows(table=None):
    return [r for r in (table if table is not None else build_table()) if r["overridable_via"] == VIA_CODE]


def _cell(v):
    if v is None:
        return "Missing"
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, dict):
        return "; ".join(f"{k} {_cell(x)}" for k, x in v.items())
    return str(v).replace("|", "/")


def _md_table(rows):
    out = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rows:
        out.append("| " + " | ".join(_cell(r[c]) for c in COLUMNS) + " |")
    return out


def to_markdown(table=None):
    table = table if table is not None else build_table()
    overridable = [r for r in table if r["overridable_via"] != VIA_CODE]
    code_only = [r for r in table if r["overridable_via"] == VIA_CODE]
    L = ["## Parameters that can be replaced without editing code", "",
         "`engine input` = overridable through the engine's normal input mechanism; `registry` = a registry row the engine does not read; "
         "`dynamics argument` = a what-if argument, not an engine input.", ""]
    L += _md_table(overridable)
    L += ["", "## Parameters that CANNOT be overridden without a code edit", ""]
    L += _md_table(code_only)
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    print(to_markdown())
