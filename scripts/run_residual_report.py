"""
Residual report (data-replacement layer, step 1) -- READ-ONLY and OFFLINE. It calibrates nothing and fits nothing.

For every measured tag that maps to a snapshot key it prints model vs measured over the replay window (residual = measured - model, absolute and relative, with the status
of both sides), and for every Assumed parameter it lists which measured tags could constrain it (identifiability list only).

    python scripts/run_residual_report.py                       (SYNTHETIC demonstration: the model's own snapshot plus known offsets; about 1 minute)
    python scripts/run_residual_report.py --replay FILE.csv     (a long-format CSV/JSON, schema docs/measurement_replay_schema.md)

The model side is the in-process engine's final snapshot (tab1_integration.build_live_snapshot), which is quasi-steady: one value per tag for the whole window. Readings that carry a
blocking flag or a quality other than 'good' are listed in the validation summary and EXCLUDED from the residual statistics (never silently: n_used and n_flagged are printed).
Offline: no database, no network; a socket guard refuses Supabase hosts. Writes outputs/data_layer/residual_report.md and .csv (outputs/ is git-ignored).
"""
import csv
import os
import socket
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
if os.environ.get("HYGAS_ALLOW_DB_WRITES") == "1":
    sys.exit("Refusing to run: HYGAS_ALLOW_DB_WRITES=1 is set. This script never writes; unset it.")

from _fakes import FakeSupabase, patched_supabase       # noqa: E402
from python import data_precedence as dp                # noqa: E402
from python import measurement_replay as mr              # noqa: E402
from python import parameter_table as pt                 # noqa: E402
from python import plant_status as ps                    # noqa: E402
from python import tab1_integration as t1                # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "data_layer")
N_CONV = 30
SYNTHETIC_LABEL = "SYNTHETIC: model snapshot + a known offset. Proves the plumbing, not the physics; no plant data exists."
# Demonstration offsets for the synthetic run (units of the tag). They are test inputs, not claims about any plant.
DEMO_OFFSETS = {"HB-012.h2_kg_h": 0.5, "SA-001.H2_vol_pct": -2.0, "GA-001.dry_flow_nm3_h": 4.0, "GA-001.T_gasifier_C": -15.0}

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


socket.getaddrinfo = _guard


# --- model side ---------------------------------------------------------------------------------------------------------------------

def model_value(snapshot, key, field):
    """(value, status, note) of one snapshot number. Missing / absent -> (None, 'Missing', why); never a fallback number."""
    entry = snapshot.get(key)
    if entry is None:
        return None, ps.STATUS_MISSING, f"{key} is not in the snapshot"
    if entry["status"] == ps.STATUS_MISSING:
        return None, ps.STATUS_MISSING, entry.get("missing_reason") or "Missing"
    v = entry["value"] if field is None else entry["value"][field]
    return float(v), entry["status"], ""


# --- residuals ----------------------------------------------------------------------------------------------------------------------

def residual_rows(snapshot, readings, catalog):
    """One row per measured tag that maps to a snapshot key. residual = measured - model (the model is quasi-steady: one value per window)."""
    by_tag = {}
    for r in readings:
        by_tag.setdefault(r["tag"], []).append(r)
    rows, unmapped = [], []
    for tag in sorted(by_tag):
        rs = by_tag[tag]
        info = catalog.get(tag)
        used = mr.usable(rs)
        counts = {q: sum(1 for r in rs if r["quality"] == q) for q in dp.QUALITIES}
        if info is None or info["snapshot_key"] is None:
            unmapped.append({"tag": tag, "n_readings": len(rs), "n_used": len(used),
                             "why": "unknown tag" if info is None else "known quantity, but the model publishes no entry for it"})
            continue
        mv, mstatus, note = model_value(snapshot, info["snapshot_key"], info["field"])
        row = {"tag": tag, "snapshot_key": f"{info['snapshot_key'][0]}/{info['snapshot_key'][1]}" + (f".{info['field']}" if info["field"] else ""),
               "unit": info["unit"], "n_readings": len(rs), "n_used": len(used), "n_flagged": len(rs) - len(used),
               "window_start": None, "window_end": None, "measured_mean": None, "model": mv, "model_status": mstatus,
               "measured_status": f"{ps.STATUS_MEASURED} (good {counts['good']}, suspect {counts['suspect']}, bad {counts['bad']})",
               "residual_abs": None, "residual_rel": None, "residual_max_abs": None, "note": note}
        if used:
            stamps = sorted(r["t"] for r in used)
            row["window_start"], row["window_end"] = stamps[0].isoformat(), stamps[-1].isoformat()
            row["measured_mean"] = sum(r["value"] for r in used) / len(used)
            if mv is not None:
                res = [r["value"] - mv for r in used]
                row["residual_abs"] = sum(res) / len(res)
                row["residual_max_abs"] = max(abs(x) for x in res)
                row["residual_rel"] = row["residual_abs"] / mv if mv else None
        else:
            row["note"] = (row["note"] + " no usable reading (all flagged or not 'good')").strip()
        rows.append(row)
    return rows, unmapped


# --- identifiability (a static, labelled map: engineering judgement, not a fit) -------------------------------------------------------

# parameter tag -> (constrained by [tags], how, what else is needed). "Constrained" means the tag carries information about the parameter in the
# model's structure; it does NOT say the parameter can be separated from the others from those tags alone (see `confounded_with`).
IDENTIFIABILITY = [
    ("GA-001.carbon_conversion", ["GA-008.carbon_black_kg_h", "GA-001.dry_flow_nm3_h", "GA-001.CO_mol_pct_dry", "GA-001.CO2_mol_pct_dry", "GA-001.CH4_mol_pct_dry", "FE-008.feed_rate_kg_h"],
     "carbon balance: carbon in the product gas plus the carbon black against the carbon fed", ["GA-001.ch4_carbon_fraction"],
     "a feed ultimate analysis (lab) and the split of unconverted carbon (carbon black vs bed drain vs fly ash)"),
    ("GA-001.ch4_carbon_fraction", ["GA-001.CH4_mol_pct_dry", "SA-004.CH4_vol_pct", "GA-001.dry_flow_nm3_h"],
     "CH4 carbon over converted carbon", ["GA-001.carbon_conversion"], "the conversion (above) to turn CH4 volume into a fraction"),
    ("GA-001.ER", ["GA-003.air_flow_Nm3_h", "FE-008.feed_rate_kg_h", "GA-001.N2_mol_pct_dry", "SA-005.N2_vol_pct"],
     "directly: measured air against the stoichiometric air of the feed; indirectly: the N2 balance (the gasifying-agent study found the registry's 10 % N2 implies ER about 0.04)",
     ["GA-001.carbon_conversion"], "the gasifying agent (air vs oxygen vs carrier; docs/gasifying_agent_study.md) and the feed ultimate analysis"),
    ("GA-001.steam_to_feed_kg_kg", ["GA-003.steam_flow_kg_h", "FE-008.feed_rate_kg_h"],
     "directly: measured steam mass flow over the dry feed rate", [], "the dry (not as-received) feed rate: FE-005's moisture"),
    ("GA-001.T_gasifier_C", ["GA-001.T_gasifier_C"], "directly: a bed / outlet temperature reading", [], "which thermocouple position the 950 degC refers to"),
    ("GA-001.dry_feed_kg_h", ["FE-008.feed_rate_kg_h"], "directly: ram-feeder / airlock rate", [], "the moisture of the feed to convert wet to dry"),
    ("GA-001.feedstock_daf_CHON", [], "not a time series: a laboratory ultimate analysis of the real feed", [], "sampling plan and lab results (no tag exists)"),
    ("GA-001.ash_fraction", ["GA-008.carbon_black_kg_h"], "ash discharge mass over the dry feed (GA-005 rate); no ash-flow tag is defined in this layer", [], "an ash mass-flow tag and a lab ash analysis"),
    ("GA-001.unconverted_C_to_carbon_black", ["GA-008.carbon_black_kg_h"], "carbon black mass over the unconverted carbon", ["GA-001.carbon_conversion"],
     "masses of the other unconverted-carbon exits (bed drain, cyclone catch, fly ash): no tag exists, Missing"),
    ("GA-001.tail_gas_mode", [], "not identifiable from a measurement: it states where the PSA tail gas goes in the plant", [], "DOK-ING's statement of the real tail-gas routing"),
    ("HB-006.psa_K1", ["HB-012.h2_kg_h", "HB-009.product_flow_nm3_h", "HB-009.tail_flow_nm3_h", "HB-006.psa_recovery"],
     "H2 recovery from the product and tail flows with the PSA feed composition", ["HB-006.psa_void_loss"], "PSA feed composition and flow (no PSA-inlet tag is defined in this layer)"),
    ("HB-006.psa_void_loss", ["HB-006.psa_recovery"], "only with K1 jointly (recovery = 1 - K1*index/(PR-1) - void loss)", ["HB-006.psa_K1"], "recovery at two or more pressure ratios"),
    ("HB-006.psa_target_calibration", ["HB-006.psa_recovery"], "a scale on K1 (Monte-Carlo only): the same data as K1", ["HB-006.psa_K1"], "see K1"),
    ("HB-004.wgs_target_calibration", [], "post-WGS composition: no sensor tag for it is defined in this layer", [], "a post-WGS CO / H2 analyser tag"),
    ("GA-001.tau_conv_s", ["GA-001.dry_flow_nm3_h", "GA-001.H2_mol_pct_dry"], "transient step response of the gas to a feed-rate step", ["GA-001.tau_gas_s"],
     "time-resolved data at sub-minute spacing around a deliberate feed step (the hourly runtime and a 1-hour log cannot show a 20-minute lag)"),
    ("GA-001.tau_gas_s", ["GA-001.dry_flow_nm3_h", "GA-001.H2_mol_pct_dry"], "outlet-gas response to an ER or feed step", ["GA-001.tau_conv_s"], "seconds-resolution gas data"),
    ("GA-001.tau_T_s", ["GA-001.T_gasifier_C"], "temperature response to a setpoint change", [], "seconds-resolution temperature data and the heating actuator"),
    ("HB-009.tau_rec_s", ["HB-009.tail_flow_nm3_h"], "tail-gas flow response at the recycle point", [], "tail-gas flow and buffer-tank data (HB-009)"),
    ("EU-008.tau_cooling_water_s", [], "cooling-water temperature step response: no tag is defined in this layer", [], "a cooling-water temperature tag"),
]


def identifiability(table=None, catalog=None):
    """Validated rows of IDENTIFIABILITY: every parameter must be a table tag and every constraining tag a catalog tag, else LookupError."""
    table = table if table is not None else pt.build_table()
    catalog = catalog if catalog is not None else mr.build_catalog(table)
    by_tag = {}
    for r in table:
        by_tag.setdefault(r["tag"], []).append(r)
    out = []
    for param, tags, how, confounded, needs in IDENTIFIABILITY:
        if param not in by_tag:
            raise LookupError(f"identifiability: {param!r} is not a parameter-table tag")
        for t in list(tags) + list(confounded):
            if t not in catalog and t not in by_tag:
                raise LookupError(f"identifiability: {t!r} (for {param}) is neither a catalog nor a table tag")
        rows = by_tag[param]
        model_row = next((r for r in rows if r["overridable_via"] != pt.VIA_REGISTRY), rows[0])
        out.append({"parameter": param, "status": model_row["status"], "overridable_via": model_row["overridable_via"], "constrained_by": list(tags),
                    "how": how, "confounded_with": list(confounded), "also_needed": needs,
                    "measurable_directly_or_not": "no tag" if not tags else ("direct" if how.startswith("directly") else "indirect")})
    return out


# --- synthetic data -----------------------------------------------------------------------------------------------------------------

def make_synthetic(snapshot, catalog, offsets=None, n=12, start="2026-10-30T00:00:00Z"):
    """Readings = model value + a known offset, hourly. Labelled SYNTHETIC in `source`. Used to prove the plumbing recovers the offset."""
    offsets = DEMO_OFFSETS if offsets is None else offsets
    t0 = dp.parse_timestamp(start)
    out, row = [], 0
    for tag, off in offsets.items():
        info = catalog[tag]
        mv, _st, why = model_value(snapshot, info["snapshot_key"], info["field"])
        if mv is None:
            raise ValueError(f"cannot build synthetic data for {tag}: {why}")
        for i in range(n):
            row += 1
            out.append({"row": row, "timestamp": (t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "tag": tag, "value": mv + off,
                        "unit": info["unit"], "quality": "good", "source": "SYNTHETIC offset " + str(off), "t": None, "flags": []})
    return out


# --- output -------------------------------------------------------------------------------------------------------------------------

def _f(v, digits=6):
    return "Missing" if v is None else (f"{v:.{digits}g}" if isinstance(v, float) else str(v))


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return out


def render(snapshot, report, rows, unmapped, ident, label):
    L = ["# Residual report (data-replacement layer, step 1)", "", f"**Data: {label}**", "",
         "Residual = measured - model. The model is the engine's quasi-steady final snapshot: one value per tag for the whole window. Nothing is fitted or calibrated.", "",
         "## 1. Replay validation", ""]
    if report["counts"]:
        L += md_table(["issue", "count"], sorted(report["counts"].items()))
    else:
        L.append("No issue found.")
    L += ["", f"Readings in: {len(report['readings'])}; readings out: {len(report['readings'])} (validation drops nothing).", "", "## 2. Model vs measured", ""]
    L += md_table(["tag", "model entry", "unit", "n used / flagged", "window", "measured mean", "model", "residual abs (meas - model)", "residual rel", "max |residual|", "model status", "measured status", "note"],
                  [[r["tag"], r["snapshot_key"], r["unit"], f"{r['n_used']} / {r['n_flagged']}", f"{r['window_start']} .. {r['window_end']}" if r["window_start"] else "-",
                    _f(r["measured_mean"]), _f(r["model"]), _f(r["residual_abs"]), _f(r["residual_rel"]), _f(r["residual_max_abs"]), r["model_status"], r["measured_status"], r["note"]]
                   for r in rows])
    L += ["", "## 3. Measured tags with no model counterpart", ""]
    L += md_table(["tag", "readings", "usable", "why"], [[u["tag"], u["n_readings"], u["n_used"], u["why"]] for u in unmapped]) if unmapped else ["None."]
    L += ["", "## 4. Identifiability of the Assumed parameters (a static map, no fitting)", "",
          "`constrained by` = tags that carry information about the parameter in the model's structure. `confounded with` = parameters that move the same tags, so the tags alone do not separate them.", ""]
    L += md_table(["parameter", "status now", "overridable via", "constrained by", "how", "confounded with", "also needed", "direct / indirect"],
                  [[i["parameter"], i["status"], i["overridable_via"], ", ".join(i["constrained_by"]) or "no tag", i["how"], ", ".join(i["confounded_with"]) or "-",
                    i["also_needed"], i["measurable_directly_or_not"]] for i in ident])
    return "\n".join(L) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    replay_path = argv[argv.index("--replay") + 1] if "--replay" in argv else None
    print(f"building the model snapshot ({N_CONV} cycles) ...", flush=True)
    fake = FakeSupabase()
    with patched_supabase(fake):
        snapshot, _state, _engine = t1.build_live_snapshot(N_CONV)
    table = pt.build_table()
    catalog = mr.build_catalog(table)
    if replay_path:
        raw, label = mr.load_file(replay_path), f"replay file {replay_path}"
    else:
        raw, label = make_synthetic(snapshot, catalog), SYNTHETIC_LABEL
    report = mr.replay(mr.InMemorySource(raw), catalog)
    rows, unmapped = residual_rows(snapshot, report["readings"], catalog)
    ident = identifiability(table, catalog)
    text = render(snapshot, report, rows, unmapped, ident, label)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "residual_report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    cols = ["tag", "snapshot_key", "unit", "n_readings", "n_used", "n_flagged", "window_start", "window_end", "measured_mean", "model", "model_status", "measured_status",
            "residual_abs", "residual_rel", "residual_max_abs", "note"]
    with open(os.path.join(OUT_DIR, "residual_report.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})
    print(text)
    print(f"wrote {os.path.join(OUT_DIR, 'residual_report.md')} and .csv; database calls made through the in-memory fake: {len(fake.calls)}")


if __name__ == "__main__":
    main()
