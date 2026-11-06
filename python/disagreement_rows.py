"""Cross-module disagreement figures (G5-07, read-only): the live engine numbers next to the registry / DOK-ING numbers they disagree with.

CLASS: report only. Pure functions of a published plant snapshot and the registry file; nothing here is read by the engine, the runtime or the app,
nothing is tuned, and no value is chosen from a difference. A difference is a finding, not an error verdict (no tolerance is set).
Registry values are DOK-ING's datasheet extract with status 'Unverified (registry)' unless a DOK-ING line says otherwise; they are not plant measurements.
Rows covered (numbering of the G5-07 list): 1, 3, 4, 7, 8, 10, 11, 12, 13. Rows that come from the balance, heat or agent scripts are not repeated here.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY_PATH = os.path.join(ROOT, "data", "equipment_registry.json")


def _registry_value(registry, item_id, parameter):
    for it in registry:
        if it["id"] == item_id:
            for p in it["parameters"]:
                if p["parameter"] == parameter:
                    return p["value"]
    raise KeyError((item_id, parameter))


def _num(text):
    """'32-33' -> 32.5, '28' -> 28.0 (midpoint of a stated range)."""
    parts = [float(x) for x in str(text).replace("–", "-").split("-") if x.strip()]
    return sum(parts) / len(parts)


def load_registry(path=REGISTRY_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rows(snapshot, registry):
    """List of dicts {row, quantity, live, registry, unit, difference_pct, source}; difference_pct = (live - registry) / registry x 100 (None when not numeric)."""
    v = lambda k: snapshot[k]["value"]          # noqa: E731
    out = []

    def add(row, quantity, live, reg, unit, source):
        diff = None if reg in (None, 0) or live is None else 100.0 * (live - reg) / reg
        out.append({"row": row, "quantity": quantity, "live": live, "registry": reg, "unit": unit, "difference_pct": diff, "source": source})

    go = v(("GA-001", "Outputs"))
    for sa, name, key in (("SA-001", "H2", "H2_mol_pct_dry"), ("SA-002", "CO", "CO_mol_pct_dry"), ("SA-003", "CO2", "CO2_mol_pct_dry"),
                          ("SA-004", "CH4", "CH4_mol_pct_dry"), ("SA-005", "N2", "N2_mol_pct_dry")):
        param = [p["parameter"] for it in registry if it["id"] == sa for p in it["parameters"] if p["parameter"].startswith("Expected")][0]
        add(1, f"syngas {name}, dry", go[key], _num(_registry_value(registry, sa, param)), "vol%", f"GA-001 Outputs vs {sa} '{param}'")
    add(3, "syngas flow, dry", go["dry_flow_nm3_h"], _num(_registry_value(registry, "HB-007", "Feed gas flow rate")), "Nm3/h", "GA-001 Outputs vs HB-007 'Feed gas flow rate'")
    psa = v(("HB-006", "PSA"))
    add(4, "PSA feed H2", 100.0 * psa["y_H2"], _num(_registry_value(registry, "HB-006", "Feed gas H₂ content")), "vol%", "HB-006 PSA y_H2 vs HB-006 'Feed gas H2 content'")
    add(7, "hydrogen product", 24.0 * v(("HB-012", "Compressor"))["h2_kg_h"], 50.0, "kg/day", "HB-012 Compressor h2_kg_h x 24 vs DOK-ING about 50 kg/day (RFI #6, plastic waste)")
    add(7, "hydrogen product (registry design)", 24.0 * v(("HB-012", "Compressor"))["h2_kg_h"], 1.85 * 24.0, "kg/day", "same, vs HB-007 20.6 Nm3/h = 1.85 kg/h x 24")
    add(8, "PSA recovery", 100.0 * psa["recovery"], 75.0, "%", "HB-006 PSA recovery vs HB-007 H2 recovery rate (design)")
    cs = v(("EU-008", "CoolingSupply"))
    add(10, "EU-008 cooling demand", cs["demand_kw"], _num(_registry_value(registry, "EU-008", "Cooling duty")), "kW",
        "EU-008 CoolingSupply demand_kw vs EU-008 'Cooling duty' (its remark scopes the 20 kW to EU-004 jacket cooling)")
    hx = v(("HB-003", "HeatExchanger"))
    reg_hx = _num(_registry_value(registry, "HB-003", "Design heat duty"))
    add(11, "HB-003 hot-side duty", hx["Q_hot_side_kW"], reg_hx, "kW", "HB-003 HeatExchanger vs HB-003 'Design heat duty'")
    add(11, "HB-003 cold-side duty", hx["Q_cold_side_kW"], reg_hx, "kW", "HB-003 HeatExchanger vs HB-003 'Design heat duty'")
    add(12, "GC-009 HCl removal", 100.0 * v(("GC-009", "HCl"))["efficiency"], 97.0, "%", "GC-009 HCl efficiency vs its stated '>97 %' target")
    ca = v(("GA-001", "CarbonAccounting"))
    add(13, "carbon black, engine (derived) vs 5 % rule", ca["carbon_black_kg_h"], ca["datasheet_cross_check"]["datasheet_rule_kg_h"], "kg/h", "GA-001 CarbonAccounting carbon_black_kg_h vs datasheet_rule_kg_h")
    return out


def format_table(rs):
    L = ["| row | quantity | live | registry / stated | unit | difference % | source |", "|---|---|---|---|---|---|---|"]
    for r in rs:
        d = "" if r["difference_pct"] is None else f"{r['difference_pct']:+.1f}"
        L.append(f"| {r['row']} | {r['quantity']} | {r['live']:.3f} | {r['registry']:.3f} | {r['unit']} | {d} | {r['source']} |")
    return "\n".join(L)
