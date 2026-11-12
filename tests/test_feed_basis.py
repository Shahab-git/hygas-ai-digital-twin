"""Feed-basis tests (task P0-FB1): which kind of kg/h each feed number is, and what the repo does with it today.

The three numbers (see CLAUDE.md, "Feed-rate bases"):
    41.67 kg/h   DOK-ING's stated 1 tonne/day, 1,000 kg/day / 24 h. DOK-ING did not say wet or dry; the project TREATS it as as-received.
    37.503 kg/h  dry solids INCLUDING ash = 41.67 x (1 - 0.10 inlet moisture, an Assumed value): the live engine's GA-001 dry feed.
    33.753 kg/h  dry ASH-FREE = 37.503 x (1 - 0.10 ash, an Assumed value): computed inside GA-001 for the C/H/O/N atoms.

The file has two parts, kept apart on purpose:

PART 1, CORRECTNESS tests. They state what must stay true after any later correction of the known limitations (the arithmetic of the live chain, the
dry-including-ash / dry-ash-free distinction, the carbon-black identity, the documentation not presenting an assumed basis as a DOK-ING statement).

PART 2, CHARACTERIZATION tests of KNOWN LIMITATIONS (every test name starts with `test_known_limitation_`). They record what the code does TODAY and
do NOT say it is right. P1-05(c) closed three of them (the 41.67 kg/h cycle-1 fallback, the `DEFAULT_DRY_FEED_KG_H` constant that held an as-received value under a
"dry" name, the static ash / carbon-black figures on 41.67); their tests became correctness tests above. What remains is the carbon-black definitions. When one of these is corrected
(an owner decision, not made here), the matching test must be updated or replaced in the same change; its failure message says so.

No default, equation, registry value or persisted key is touched here, and nothing here is validation against DOK-ING data (none exists).
Offline: counting fake store, no credentials, no network."""
import os
import re

import pytest

from _fakes import FakeSupabase, patched_supabase
from python import balance_audit as ba
from python import circularity, cycle_clock, fe_feed_handling as fe
from python import ga001_gasifier_model as ga001
from python import gasifier_mass_balance as gmb
from python import tab1_integration as t1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
N = 6                                   # cycle 6 reads the tail gas of cycle 5; the identities below hold at every cycle, so no convergence is needed
AS_RECEIVED = 41.67                     # 1,000 kg/day / 24 h, rounded as the repo writes it
DRY_INCL_ASH = 41.67 * (1.0 - 0.10)     # 37.503
DRY_ASH_FREE = DRY_INCL_ASH * (1.0 - 0.10)   # 33.7527
FIX = ("When a known limitation is corrected (an owner decision, see CLAUDE.md 'Known limitations'), update or replace this "
       "characterization test in the same change; do not edit it to keep the old behaviour.")


@pytest.fixture(scope="module")
def snaps():
    cycle_clock.set_elapsed_hours(None)
    out = {}
    with patched_supabase(FakeSupabase()):
        for n in (1, N - 1, N):
            out[n] = t1.build_live_snapshot(n_cycles=n)[0]
    return out


@pytest.fixture(scope="module")
def snaps_regasify():
    """P1-06g: the same runs with the tail-gas recycle explicitly ON (the default before P1-06); `snaps` is the real default, "heat_only"."""
    from test_tail_gas_mode import _mode
    cycle_clock.set_elapsed_hours(None)
    out = {}
    with patched_supabase(FakeSupabase()):
        for n in (N - 1, N):
            out[n] = t1.build_live_snapshot(n_cycles=n, overrides=_mode("regasify"))[0]
    return out


@pytest.fixture(scope="module")
def real_snap():
    """P1-06 (deliberate edit): the STATIC carbon black (circularity, fills) is pinned on tail_gas_mode "heat_only", set explicitly (since P1-06g the module's `snaps` are also the real default)."""
    from test_tail_gas_mode import _mode
    cycle_clock.set_elapsed_hours(None)
    with patched_supabase(FakeSupabase()):
        return t1.build_live_snapshot(n_cycles=N, overrides=_mode("heat_only"))[0]


def _text(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def _val(snap, key):
    return snap[key]["value"]


# =====================================================================================================================================
# PART 1: CORRECTNESS tests (must stay true after any correction)
# =====================================================================================================================================
def test_the_three_feed_numbers_follow_from_the_two_assumed_fractions():
    assert fe.FE005_INLET_MOISTURE_FRACTION == 0.10 and ga001.ASH_FRACTION == 0.10      # Assumed project values, not DOK-ING-stated points
    assert DRY_INCL_ASH == pytest.approx(37.503, abs=1e-9)
    assert DRY_ASH_FREE == pytest.approx(33.7527, abs=1e-9)
    assert round(DRY_ASH_FREE, 3) == 33.753
    assert DRY_INCL_ASH != pytest.approx(DRY_ASH_FREE, rel=0.05)                         # dry including ash and dry ash-free are different quantities


def test_fe005_turns_the_as_received_feed_into_dry_solids_including_ash(snaps):
    fe005 = _val(snaps[N], ("FE-005", "MoistureBalance"))
    wet = _val(snaps[N], ("FE-004", "ShredderPower"))["outlet_kg_h"]
    assert wet == pytest.approx(AS_RECEIVED, abs=1e-9)
    assert fe005["dry_solids_kg_h"] == pytest.approx(wet * (1.0 - fe.FE005_INLET_MOISTURE_FRACTION), rel=1e-12)
    assert fe005["dry_solids_kg_h"] == pytest.approx(37.503, abs=1e-9)
    assert fe005["outlet_wet_kg_h"] == pytest.approx(fe005["dry_solids_kg_h"] / (1.0 - fe.FE005_OUTLET_MOISTURE_FRACTION), rel=1e-12)
    assert fe005["residual_water_kg_h"] == pytest.approx(fe005["outlet_wet_kg_h"] - fe005["dry_solids_kg_h"], rel=1e-12)


def test_from_cycle_two_ga001_receives_the_lagged_fe005_dry_solids(snaps):
    assert _val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")) == pytest.approx(_val(snaps[N - 1], ("FE-005", "MoistureBalance"))["dry_solids_kg_h"], rel=1e-12)
    assert _val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")) == pytest.approx(37.503, abs=1e-9)


def test_ga001_carbon_atoms_come_from_the_dry_ash_free_feed_not_the_dry_feed_with_ash(snaps):
    """33.753 kg/h daf x 0.50 C = 16.876 kg C/h; the dry-including-ash feed would give 18.75 kg C/h (a 11.1 % difference)."""
    feed = float(_val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    comp = _val(snaps[N], ("GA-001-INPUT", "feedstock_composition"))
    terms = ba.ga001_terms(snaps[N], snaps[N - 1])
    c_kg_h = terms["feed_atoms"]["C"] * ga001.M_C / 1000.0
    assert c_kg_h == pytest.approx(feed * (1.0 - ga001.ASH_FRACTION) * comp["C"], rel=1e-9)
    assert c_kg_h == pytest.approx(DRY_ASH_FREE * 0.50, rel=1e-6)
    assert c_kg_h != pytest.approx(feed * comp["C"], rel=0.05)


@pytest.mark.parametrize("mode", ["heat_only", "regasify"])
def test_the_derived_carbon_black_is_the_unconverted_carbon_recomputed_independently(snaps, snaps_regasify, mode):
    """(1 - conversion) x (feed carbon + recycled CO/CH4 carbon) x split, from the composition and the previous cycle's HB-009 tail gas. P1-06g: run for the real default
    (heat_only: nothing is recycled, so the recycle term is zero) and, explicitly, for regasify (the original case)."""
    src = snaps if mode == "heat_only" else snaps_regasify
    snap, prev = src[N], src[N - 1]
    feed = float(_val(snap, ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    comp = _val(snap, ("GA-001-INPUT", "feedstock_composition"))
    conv = float(_val(snap, ("GA-001-INPUT", "carbon_conversion_efficiency")))
    feed_c = feed * (1.0 - ga001.ASH_FRACTION) * comp["C"]
    assert _val(snap, ("GA-001", "Outputs"))["recycle_active"] is (mode == "regasify")
    tail = _val(prev, ("HB-009", "TailGas"))["species_nm3_h"]
    rec_c = (float(tail["CO"]) + float(tail["CH4"])) / ga001.NM3_PER_MOL * ga001.M_C / 1000.0 if mode == "regasify" else 0.0
    expected = (1.0 - conv) * (feed_c + rec_c) * ga001.CARBON_BLACK_SPLIT_DEFAULT
    got = _val(snap, ("GA-001", "CarbonAccounting"))["carbon_black_kg_h"]
    assert got == pytest.approx(expected, rel=1e-9)


def test_the_documentation_does_not_present_an_assumed_basis_as_a_dok_ing_statement():
    answers = _text("data/dokink_rfi_answers.md")
    feed_line = next(line for line in answers.split("\n") if line.startswith("1. **Feed rate.**"))
    block = answers[answers.index("1. **Feed rate.**"):answers.index("2. **Composition.**")]
    assert "1 tonne/day" in feed_line
    assert not re.search(r"\b(wet|dry|as[- ]received)\b", block, re.IGNORECASE), "DOK-ING's answer 1 states no wet/dry basis"
    comp = answers[answers.index("2. **Composition.**"):answers.index("3. **Feedstock form.**")]
    assert comp.count("(dry basis)") == 1 and comp.index("(dry basis)") > comp.index("LHV"), "'(dry basis)' appears once, after the LHV"
    doc = _text("CLAUDE.md")
    assert "Feed-rate bases" in doc and "Known limitations" in doc
    for needle in ("41.67 kg/h", "37.503 kg/h", "33.753 kg/h", "as-received", "dry ASH-FREE", "INCLUDING ash", "not DOK-ING-confirmed"):
        assert needle in doc, needle
    assert "did NOT state whether it is wet or dry" in doc
    assert "41.67 kg/h dry\nfeed = 1,000 kg/day" not in doc, "the old 'use this in any new work: 41.67 kg/h dry feed' sentence must not return"
    assert "own confirmed WET rate" not in doc


def test_the_circularity_section_names_its_feed_basis_and_its_remaining_limitations():
    # P0-FB2 step 1 (deliberate edit): the section no longer mixes bases, so the old "known limitation / not the intended final
    # behaviour" needles are replaced by the statement of the dry default and of the limitations that remain.
    src = _text("app.py")
    assert "Feed rate treated as dry (kg/h) \u2014 default 41.67 is the as-received figure" not in src, "the old mixed-basis label must not return"
    section = src[src.index('st.header("Circularity Scoring")'):src.index("Section 14")]
    for needle in ("as-received", "37.503", "33.753", "including ash", "not a DOK-ING statement", 
                   "DEFAULT_DRY_FEED_KG_H", "P1-05(c)"):
        assert needle in section, needle
    assert "Recalibrated to DOK-ING's confirmed feed rate" not in section
    assert "value=circularity.DEFAULT_DRY_SOLIDS_FEED_KG_H" in section and "circularity.circularity_summary(circ_feed_kg_h)" in section


def test_the_circularity_default_is_the_dry_solids_the_live_engine_feeds_ga001(snaps, real_snap):
    """P0-FB2 step 1 (replaces the known-limitation test of the same default): the circularity default is derived from the two feed-chain
    constants, equals FE-005's dry solids and the live GA-001 feed, and its static ash equals the same fraction on the live feed. P1-05(d) (deliberate edit): its carbon black is now the engine's derived value (was the 5 % rule, 1.87515)."""
    s = circularity.circularity_summary()
    live_feed = float(_val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    assert circularity.DEFAULT_DRY_SOLIDS_FEED_KG_H == fe.FE001_DEFAULT_DELIVERY_RATE_KG_H * (1.0 - fe.FE005_INLET_MOISTURE_FRACTION)
    assert s["dry_feed_kg_h"] == circularity.DEFAULT_DRY_SOLIDS_FEED_KG_H == pytest.approx(DRY_INCL_ASH, abs=1e-9) == pytest.approx(live_feed, abs=1e-9)
    assert s["ash_kg_h"] == pytest.approx(3.7503, abs=1e-9) and s["carbon_black_kg_h"] == pytest.approx(1.687635, abs=1e-5)
    assert s["carbon_black_rule_kg_h"] == pytest.approx(1.87515, abs=1e-9)             # the legacy rule, kept as the cross-check
    assert s["ash_kg_h"] == pytest.approx(gmb.byproduct_mass_flows(live_feed)["ash_kg_h"], rel=1e-12)
    assert s["carbon_black_rule_kg_h"] == pytest.approx(gmb.CARBON_BLACK_FRACTION * live_feed, rel=1e-12)
    assert s["diversion_fraction"] == pytest.approx(gmb.ASH_FRACTION + circularity.ENGINE_CARBON_BLACK_FRACTION_OF_DRY_FEED, rel=1e-12)       # P1-05(d): was 0.15 (ash + 5 % rule), now 0.1537
    assert gmb.DEFAULT_DRY_FEED_KG_H == pytest.approx(DRY_INCL_ASH, abs=1e-9) and gmb.DEFAULT_AS_RECEIVED_FEED_KG_H == AS_RECEIVED     # P1-05(c) (deliberate edit): the constant is now the dry solids


# =====================================================================================================================================
# PART 2: CHARACTERIZATION of KNOWN LIMITATIONS (what the code does today; not the intended final behaviour)
# =====================================================================================================================================
def test_cycle_one_now_feeds_ga001_the_dry_solids_like_every_later_cycle(snaps):
    """P1-05(c) (deliberate edit; was test_known_limitation_cycle_one_feeds_ga001_the_as_received_figure_as_if_it_were_dry): on cycle 1 GA-001 has no FE-005 value yet and falls
    back to the dry solids 37.503 kg/h, the same figure FE-005 hands over from cycle 2 (it used the as-received 41.67 as 'dry', +11.1 %, before)."""
    got = _val(snaps[1], ("GA-001-INPUT", "dry_feed_rate_kg_h"))
    fe005_same_cycle = _val(snaps[1], ("FE-005", "MoistureBalance"))["dry_solids_kg_h"]
    assert got == gmb.DEFAULT_DRY_FEED_KG_H == pytest.approx(37.503, abs=1e-9)
    assert got == pytest.approx(fe005_same_cycle, abs=1e-9)
    assert _val(snaps[1], ("GA-001", "Outputs"))["recycle_active"] is False


def test_the_dry_named_default_constant_is_the_dry_solids_and_the_as_received_rate_has_its_own_name():
    """P1-05(c) (deliberate edit; was test_known_limitation_the_dry_named_default_constant_holds_the_as_received_value)."""
    assert gmb.DEFAULT_DRY_FEED_KG_H == pytest.approx(fe.FE001_DEFAULT_DELIVERY_RATE_KG_H * (1.0 - fe.FE005_INLET_MOISTURE_FRACTION), abs=1e-12)
    assert gmb.DEFAULT_AS_RECEIVED_FEED_KG_H == fe.FE001_DEFAULT_DELIVERY_RATE_KG_H == fe.FE003_NOMINAL_KG_H == AS_RECEIVED


def test_the_equipment_datasheet_ga_fills_use_the_dry_solids_feed_the_live_engine_feeds_ga001(snaps, real_snap):
    """P0-FB2 step 2: the GA-006/007/008/010 estimate fills are computed from the dry solids (37.503 kg/h), so they equal the live GA-001 ash and, since P1-05(d) (deliberate edit), the engine's derived carbon black (was the 5 % rule)."""
    from python import equipment_engineering_estimates as eee
    live_feed = float(_val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    live = gmb.byproduct_mass_flows(live_feed)
    assert eee._GA_ASH_KG_H == pytest.approx(live["ash_kg_h"], rel=1e-12) == pytest.approx(3.7503, abs=1e-9)
    derived = _val(real_snap, ("GA-001", "CarbonAccounting"))["carbon_black_kg_h"]
    assert eee._GA_CARBON_BLACK_KG_H == pytest.approx(derived, rel=1e-4) and eee._GA_CARBON_BLACK_KG_H != pytest.approx(live["carbon_black_kg_h"], rel=1e-3)
    assert eee._GA_RECOVERED_CARBON_BLACK_KG_H == pytest.approx(0.95 * derived, rel=1e-4)
    fills = eee.ESTIMATE_FILLS
    got = {(i, r["parameter"]): r["value"] for i, secs in fills.items() for rows in secs.values() for r in rows}
    assert got[("GA-006", "Estimated ash mass flow rate (to GA-007)")] == "~3.750"
    assert got[("GA-007", "Estimated ash mass inflow rate (from GA-006)")] == "~3.750"
    assert got[("GA-007", "Estimated ash mass outflow rate (to GA-008/GA-009)")] == "~3.750"
    assert got[("GA-008", "Estimated carbon-black-laden fines inflow rate")] == "~1.688"
    assert got[("GA-010", "Estimated recovered carbon-black inflow rate (from GA-008)")] == ">=1.60"


def test_the_static_default_ash_and_carbon_black_rule_are_on_the_live_dry_feed(snaps):
    """P1-05(c) (deliberate edit; was test_known_limitation_static_ash_and_carbon_black_apply_the_dry_fractions_to_the_as_received_figure): `byproduct_mass_flows()` at its own default is
    3.7503 / 1.87515 kg/h, the same fractions on the live dry feed (it was 4.167 / 2.0835, 11.1 % above)."""
    static = gmb.byproduct_mass_flows()
    live_feed = float(_val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    live = gmb.byproduct_mass_flows(live_feed)
    assert static["ash_kg_h"] == pytest.approx(3.7503, abs=1e-9) and static["carbon_black_kg_h"] == pytest.approx(1.87515, abs=1e-9)
    assert static == pytest.approx(live, rel=1e-12)


def test_known_limitation_three_different_carbon_black_numbers_coexist_on_the_real_default(snaps):
    """P1-06g: on the real default (heat_only) nothing is recycled, so the derived value is exactly 4.5 % of the dry feed and sits BELOW both 5 % rules (the ordering differs from regasify)."""
    live_feed = float(_val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    rule_static = gmb.CARBON_BLACK_FRACTION * AS_RECEIVED
    rule_live = gmb.CARBON_BLACK_FRACTION * live_feed
    derived = _val(snaps[N], ("GA-001", "CarbonAccounting"))["carbon_black_kg_h"]
    assert rule_static == pytest.approx(2.0835, abs=1e-9) and rule_live == pytest.approx(1.87515, abs=1e-9)
    assert derived == pytest.approx(0.045 * live_feed, rel=1e-9) and derived < rule_live < rule_static, FIX
    cross = _val(snaps[N], ("GA-001", "CarbonAccounting"))["datasheet_cross_check"]
    assert cross["datasheet_rule_kg_h"] == pytest.approx(rule_live, rel=1e-12)


def test_known_limitation_three_different_carbon_black_numbers_coexist(snaps_regasify):
    snaps = snaps_regasify                                                      # P1-06g: the original case, regasify explicitly
    """KNOWN LIMITATION: 5 % rule on 41.67 (2.0835), 5 % rule on the live dry feed (1.87515) and the carbon-balance value are not one quantity.
    Only the ordering and the definitions are characterized, not a preferred value."""
    live_feed = float(_val(snaps[N], ("GA-001-INPUT", "dry_feed_rate_kg_h")))
    rule_static = gmb.CARBON_BLACK_FRACTION * AS_RECEIVED                  # the rule applied to the as-received figure: no longer a default anywhere (P1-05(c))
    rule_live = gmb.CARBON_BLACK_FRACTION * live_feed
    derived = _val(snaps[N], ("GA-001", "CarbonAccounting"))["carbon_black_kg_h"]
    assert rule_static == pytest.approx(2.0835, abs=1e-9) and rule_live == pytest.approx(1.87515, abs=1e-9)
    assert rule_live < derived < rule_static, FIX
    cross = _val(snaps[N], ("GA-001", "CarbonAccounting"))["datasheet_cross_check"]
    assert cross["datasheet_rule_kg_h"] == pytest.approx(rule_live, rel=1e-12)             # the engine's own cross-check uses the live feed, not 41.67


