"""
Liquid-carrier (LOHC) split scenarios (Phase 1, task P1-14) -- READ-ONLY, offline.

Question: HB-007's split fraction (the share of the PSA hydrogen sent to the LOHC branch HB-014 -> HB-015 -> HB-016 -> HB-017) is not stated anywhere, so the
twin keeps ("HB-007","H2SplitFraction") and the whole branch Missing. This script does NOT choose a split. It sweeps the split over 0 to 1 and shows what each
value would mean for the branch, from the registry's own capacities and efficiencies, so the owner and DOK-ING can see the consequences of any value.

  * nothing is written to the engine: no default, no persisted key, no model changes (the Missing key stays Missing);
  * the split is a scenario parameter in [0, 1]; the PSA hydrogen basis is one of three, all shown: the live engine in `regasify`, the live engine in
    `heat_only` (both read from HB-012 at 30 cycles), and the registry's own ~1.85 kg/h (HB-014 remark, Unverified (registry));
  * every constant below is a registry value (Unverified (registry), not DOK-ING-confirmed) or derived from one; the carrier density is DERIVED from the
    registry (HB-015 remark: 0.031 m3/h of carrier at 2 kg H2/h, with HB-014's 6.2 wt% loading) and labelled Estimated;
  * the model is the simplest mass balance: H2 to the branch = min(split x PSA hydrogen, the 2 kg/h capacity of HB-014/016/017); carrier throughput = H2 / loading;
    H2 released = H2 loaded x release / loading x recovery; heat = moles of H2 x the registry's ~67 kJ/mol H2 (the same magnitude assumed for the exothermic
    hydrogenation). Not modelled: reaction kinetics (Missing), start-up, carrier losses and ageing, heat integration, the off-site transport of rich oil.

    python scripts/run_lohc_split_scenarios.py        about 1 minute (two engine runs)

Writes outputs/lohc_split/lohc_split_scenarios.md and .csv (outputs/ is git-ignored). Offline: in-memory fake store of tests/_fakes.py, no database, no network.
"""
import csv
import os
import socket
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.pop("HYGAS_ALLOW_DB_WRITES", None)

from python import hb_remaining_chain as hbrem          # noqa: E402
from python import hb_wgs_psa_storage_chain as hbchain  # noqa: E402
from python import plant_status as ps                   # noqa: E402
from python import tab1_integration as t1               # noqa: E402

OUT_DIR = os.path.join(ROOT, "outputs", "lohc_split")
N_CONV = 30
SPLITS = (0.0, 0.25, 0.5, 0.75, 1.0)
CAPACITY_KG_H = 2.0                          # HB-014 loading, HB-016 release, HB-017 design capacity (registry, Unverified)
DEHYDRO_KJ_PER_MOL_H2 = 67.0                 # HB-016 remark ("DBT's ~67 kJ/mol H2"); hydrogenation assumed the same magnitude (exothermic)
RICH_TANK_M3 = 1.0                           # HB-015 rich tank (registry)
REGISTRY_PSA_KG_H = 1.85                     # HB-014 remark: "HB-007's established ~1.85 kg/h PSA product rate"
CARRIER_M3_H_AT_CAPACITY = 0.031             # HB-015 remark: HB-014 carrier throughput at 2 kg H2/h
MODES = ("regasify", "heat_only")

_real_getaddrinfo = socket.getaddrinfo


def _guard(host, *a, **k):
    if "supabase" in str(host).lower():
        raise RuntimeError(f"offline script refused to resolve {host!r}")
    return _real_getaddrinfo(host, *a, **k)


def carrier_density_kg_m3():
    """Derived, Estimated: the registry's own carrier throughput at capacity (0.031 m3/h at 2 kg H2/h) and HB-014's 6.2 wt% loading give the mass flow / volume flow."""
    return (CAPACITY_KG_H / (hbrem.HB014_LOADING_EFFICIENCY_WT_PCT / 100.0)) / CARRIER_M3_H_AT_CAPACITY


def scenario(psa_h2_kg_h, split):
    """Mass and heat balance of the LOHC branch for one PSA hydrogen flow (kg/h) and one split in [0, 1]. Pure function."""
    if not 0.0 <= split <= 1.0:
        raise ValueError("split must be in [0, 1]")
    wanted = split * psa_h2_kg_h
    loaded = min(wanted, CAPACITY_KG_H)
    carrier_kg_h = loaded / (hbrem.HB014_LOADING_EFFICIENCY_WT_PCT / 100.0) if loaded else 0.0
    carrier_m3_h = carrier_kg_h / carrier_density_kg_m3() if loaded else 0.0
    released = loaded * (hbrem.HB016_RELEASE_EFFICIENCY_WT_PCT / hbrem.HB014_LOADING_EFFICIENCY_WT_PCT) * hbrem.HB017_RECOVERY_EFFICIENCY
    mol_loaded = loaded * 1000.0 / hbchain.M_H2
    mol_released = released * 1000.0 / hbchain.M_H2
    return {
        "split": split, "psa_h2_kg_h": psa_h2_kg_h, "wanted_kg_h": wanted, "loaded_kg_h": loaded, "clipped": wanted > CAPACITY_KG_H + 1e-12,
        "to_compressed_route_kg_h": psa_h2_kg_h - loaded,
        "carrier_kg_h": carrier_kg_h, "carrier_m3_h": carrier_m3_h,
        "rich_tank_hours": RICH_TANK_M3 / carrier_m3_h if carrier_m3_h else None,
        "hydrogenation_heat_kw": mol_loaded * DEHYDRO_KJ_PER_MOL_H2 / 3600.0,
        "released_kg_h": released, "dehydrogenation_heat_kw": mol_released * DEHYDRO_KJ_PER_MOL_H2 / 3600.0,
        "round_trip": released / loaded if loaded else None,
    }


def _const(v):
    def fn(get_input):
        return {"value": v, "status": ps.STATUS_ASSUMED, "inputs": [], "validation_basis": ps.VALIDATION_NA,
                "confidence_note": "LOHC SPLIT STUDY ONLY (override; the engine default is unchanged)."}
    return fn


def live_psa_h2_kg_h(mode):
    """The engine's hydrogen flow at HB-012 (converged), as in the operating-point study. Read-only."""
    from _fakes import FakeSupabase, patched_supabase
    ov = {("GA-001-INPUT", "tail_gas_mode"): _const(mode)}      # P1-06e: always explicit ("regasify" used to mean "no override" because it was the default; since P1-06 that ran heat_only under the regasify label)
    fake = FakeSupabase()
    with patched_supabase(fake):
        snap = t1.build_live_snapshot(n_cycles=N_CONV, overrides=ov)[0]
    assert [c for c in fake.calls if c[0] != "select"] == [], "the study must not write"
    return float(snap[("HB-012", "Compressor")]["value"]["h2_kg_h"])


def bases():
    out = [(f"live engine, {m}", live_psa_h2_kg_h(m)) for m in MODES]
    out.append(("registry (HB-014 remark)", REGISTRY_PSA_KG_H))
    return out


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    socket.getaddrinfo = _guard
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, md = [], []
    for name, h2 in bases():
        md.append(f"### Basis: {name} (PSA hydrogen {h2:.3f} kg/h)\n")
        table = []
        for s in SPLITS:
            r = scenario(h2, s)
            rows.append(dict(basis=name, **r))
            table.append([f"{s:.2f}", f"{r['loaded_kg_h']:.3f}" + (" (clipped)" if r["clipped"] else ""), f"{r['to_compressed_route_kg_h']:.3f}",
                          f"{r['carrier_m3_h']:.4f}", "-" if r["rich_tank_hours"] is None else f"{r['rich_tank_hours']:.1f}",
                          f"{r['hydrogenation_heat_kw']:.1f}", f"{r['released_kg_h']:.3f}", f"{r['dehydrogenation_heat_kw']:.1f}"])
        md.append(md_table(["split", "H2 loaded kg/h", "H2 to compressed route kg/h", "carrier m3/h", "rich tank 1 m3 fills in h",
                            "hydrogenation heat kW", "H2 released kg/h", "dehydrogenation heat kW"], table) + "\n")
    with open(os.path.join(OUT_DIR, "lohc_split_scenarios.md"), "w", encoding="utf-8") as fh:
        fh.write("# LOHC split scenarios (P1-14)\n\nScenario sweep, not a choice of split. Carrier density (derived, Estimated): "
                 f"{carrier_density_kg_m3():.0f} kg/m3.\n\n" + "\n".join(md))
    with open(os.path.join(OUT_DIR, "lohc_split_scenarios.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n".join(md))


if __name__ == "__main__":
    main()
