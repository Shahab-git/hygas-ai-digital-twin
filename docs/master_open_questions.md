# HYGAS-AI — Master List of Open Questions and Missing Parameters

**Purpose.** This document consolidates *every* open question and missing
parameter currently on file across the whole project — the original RFI,
the equipment registry gap-analysis, and every "permanently Missing" or
"honest mismatch" finding surfaced while building the live Digital Twin
(Phases 0–6). **It supersedes the need to check the older lists
separately** for the purpose of deciding what to ask whom next; those
older lists (`equipment_data_requests.py`'s generated document,
`equipment_request_routing.py`'s routed document, `design_basis.py`'s RFI
tracker, CLAUDE.md's registry-issue log) remain the *itemized, full-detail*
backing record for the large generic buckets referenced below — this
document does not reproduce all 291+ of those lines, because doing so
would recreate exactly the "too numerous to answer" problem this document
exists to avoid.

**How this was built.** Every figure below was pulled by directly running
or reading the project's current, real state on 2026-09-02 — `design_basis.py`
was executed (not recalled), `equipment_data_requests.py` and
`equipment_request_routing.py` were executed, `CLAUDE.md`'s own numbered
list was read to its actual end (32 items), and the digital-twin build's
own "honest mismatch"/"permanently Missing" findings were re-verified
against the live self-test output of the relevant module, not against
memory of earlier conversation.

**Deduplication note.** Feedstock composition, for example, appears as an
old RFI item, an engineering-plan limitation, a GA-001 model input, and a
Tab 1 KPI blocker — all four are the *same underlying unknown* and are
consolidated into ONE entry (Section 1, item 3) with every downstream
implication listed together, not four separate near-identical asks.

**Missing Parameter Resolution Protocol.** This project now maintains a
`docs/missing_parameter_protocol.md` — a methodology for establishing a
defensible engineering baseline for a missing parameter (an evidence
hierarchy from Confirmed data down through Internal-model-derived,
Comparable-equipment, Literature-based, Engineering-estimate, and
Engineering-assumption) without treating "Missing" and "no DOK-ING
answer yet" as blocking. It does **not** replace this register's own
Section 1 questions — those stay genuinely open, and answering them still
matters — but items resolved under that protocol (currently: EU-008, see
Section 1 item 1 below) now carry a full `ACTUAL/DOK-ING VALUE` vs.
`DIGITAL TWIN ENGINEERING BASELINE` structure rather than a single
number, and are flagged as such.

---

## Section 1 — DOK-ING (technical/design team)

Ordered by real consequence, biggest first, per the explicit request. Every
entry states the exact parameter/unit, the exact equipment ID(s) affected,
a specific answerable question, and what it unlocks or corrects.

### 1. EU-008 second cooling path — the single biggest finding
**Reformatted under the Missing Parameter Resolution Protocol**
(`docs/missing_parameter_protocol.md`, Sections 4/5/6/8) — the scoping
question below is **already investigated and answered**, not open;
what remains open is a narrower, more specific question.

- **Equipment ID(s):** EU-008 (Cooling Tower); consumers GC-004/GC-005
  (Quench), HB-003 (WGS interstage HX), HB-012 (H₂ Compressor); EU-004
  (Gas Engine jacket cooling).
- **ACTUAL/DOK-ING VALUE:** Confirmed — 20 kW, scoped to EU-004 jacket
  cooling only. EU-008's own registry remark states this directly: *"Some
  margin above EU-004's established 12 kWth jacket cooling load."* This
  was found and reported during the original Phase 2 build.
- **DIGITAL TWIN ENGINEERING BASELINE:** approximately **65–70 kW**
  (Section 5 — a rounded engineering range, not a false-precision point
  value; the underlying unrounded computation, ~58–67 kW peak × 15%
  margin depending on the operating-envelope sample, is unchanged from
  the original resizing-estimate task).
  - **Status of baseline:** `Internal-model-derived` (Section 7).
  - **Engineering basis:** sum of three independently-validated real
    duties — GC-004 quench sensible-heat duty + HB-003 cold-side duty +
    HB-012 compressor power — running peak across ER=0.25–0.55, × a 15%
    design margin (standard 10–20% HVAC/process-cooling convention).
  - **Confidence:** Medium — each summed duty is independently real, but
    their *simultaneous aggregation onto EU-008* is this project's own
    modeling choice, not a DOK-ING-specified configuration.
  - **Assumptions:** the three-consumer aggregation itself; the 15%
    margin point-value within the standard 10–20% range.
  - **Replaceable with actual data:** yes.
- **The real question (not "is 20 kW wrong"):** *Does the real plant
  have a separate cooling path for EU-004 alone (matching the original
  20 kW scope), with GC-004/005/HB-003/HB-012 served by different or
  additional cooling capacity — or does everything genuinely run through
  one 20 kW unit today?* Honestly unknown from anything in this project.
- **Why it matters:** Resolves whether a second, currently-unmodeled
  cooling path needs to be added to the Digital Twin's own topology (if
  one exists in the real plant), or whether the real plant genuinely
  needs the larger capacity this model's own three-consumer aggregation
  implies. Already surfaces live either way — `fault_status_as_specified`
  (Confirmed-basis, `FAULT`) and `fault_status_if_resized` (Internal-
  model-derived baseline, `RUNNING`) both display on Tab 1, distinctly
  tagged (`Calculated` vs. `Estimated`) so neither can be mistaken for
  the plant's confirmed state.
- **Source:** `python/eu_utilities_chp.py` (`eu008_cooling_supply`,
  `eu008_recommended_capacity_estimate`, `EU008_REGISTRY_REMARK`,
  `EU008_REAL_OPEN_QUESTION`); `python/ai_automation_layer.py`
  (`get_ai004_eu009_state`, `get_ai004_eu009_state_if_resized`);
  `docs/missing_parameter_protocol.md`; `docs/digital_twin_engineering_
  plan.md` Section 10, item 11.

### 2. Feed-rate basis: is 41.67 kg/h (1,000 kg/day) wet (as-received) or dry?
- **Equipment ID(s):** FE-003 (Weighing Conveyor), FE-005 (Feed Dryer),
  GA-001 (Gasifier).
- **Parameter:** DOK-ING's own confirmed **1,000 kg/day (41.67 kg/h)**
  nominal feed-rate figure (RFI #1) — **basis: wet/as-received, or dry?**
- **The question:** *DOK-ING's RFI #1 answer confirms 1,000 kg/day as the
  plant's nominal feed rate, but does not state whether this is the
  as-delivered (wet, ~10% moisture per FE-005's own Confirmed inlet
  moisture) mass or the dry-solids mass. This project found the two
  existing internal treatments of this number actually disagreed:
  `equipment_engineering_estimates.py`'s own FE-007 static fill already
  treated it as WET, deriving ~37.5 kg/h dry; an earlier recalibration
  decision in this project treated the same number as already DRY. Which
  is correct?*
- **Why it matters:** This is now a **resolved-by-project-decision**
  question (Phase 3: treated as wet, per the FE-007 precedent), but it
  changes GA-001's own live dry feed rate by ~10% (41.67 → 37.5 kg/h),
  which ripples through every downstream number in the plant (syngas
  flow, H₂ production, electrical/thermal output). A direct DOK-ING
  confirmation would close this out definitively rather than resting on
  an internal precedent match.
- **Source:** `python/fe_feed_handling.py` module docstring (full
  resolution history); `CLAUDE.md`, "Phase 3 update" note.

### 3. Full feedstock ultimate analysis — precise C/H/O/N split, not just ranges
- **Equipment ID(s):** GA-001 (Gasifier — direct model input); also
  affects the "Overall efficiency" and "H₂ yield" KPIs (Tab 1),
  `gasifier_mass_balance.py`, `circularity.py`.
- **Parameter:** Elemental (C/H/O/N, dry ash-free basis, **wt%**), and
  volatile matter / fixed carbon (**wt%, dry basis**).
- **The question:** *DOK-ING's RFI #2 answer already confirms real
  RANGES — Moisture 5–15(20)%, Ash 5–15%, Volatile Matter >65%, Carbon
  >45%, Hydrogen >5%. This project's own GA-001 model currently uses a
  literature-typical point-value ultimate analysis (Tchobanoglous et al.,
  representative "typical MSW/RDF"), which falls inside these confirmed
  ranges but is not DOK-ING's own figure. Can DOK-ING provide (a) a
  precise point-value C/H/O/N split (not a range), OR (b) confirm the
  literature point value this project currently uses is an acceptable
  stand-in given the confirmed range, OR (c) is a full proximate/
  ultimate lab analysis of the actual feedstock blend available/
  plannable?*
- **Why it matters:** Feed composition is the single largest assumption
  in the whole gasifier model (GA-001's own module docstring calls it
  exactly that) — it directly sets the H/C, O/C, N/C ratios the entire
  stoichiometric+WGS-equilibrium solve is built on. A precise value here
  would let GA-001 be re-tagged from `Literature` to `DOKINGDesignTarget`
  basis (once combined with real performance data — see item 8) and
  would sharpen every downstream number in the plant.
- **UPDATE (feedstock-composition wiring task, 2026-09-03): the stale
  docstring flagged above is FIXED, and the wiring/implementation gap
  itself is closed** — `ga001_gasifier_model.py`'s own
  `_input_feedstock_composition()` now reads
  `design_basis.get_feedstock_composition_ranges()` LIVE, every run (not a
  hardcoded copy), and cross-validates the literature C/H/ash figures
  against DOK-ING's confirmed floors/range
  (`feedstock_composition_dokink_cross_check()`, exercised in the module's
  own self-test). **HONEST RESULT, not forced:** every figure this model
  actually uses already satisfies DOK-ING's confirmed constraints (Carbon
  50%>45%, Hydrogen 6%>5%, Ash 10% inside [5,15]%), so the composition
  VALUES and every downstream syngas number are numerically **unchanged**
  by this wiring — confirmed by re-running the model's own point-estimate
  and Monte Carlo self-test sections. **The underlying question below
  remains genuinely open** — this closes the wiring gap (data existed but
  wasn't connected), not the DOK-ING data gap itself: O/N are still not
  confirmed at all, and Carbon/Hydrogen are still only open floors, not a
  precise point split, so GA-001's status stays `Assumed`/`Literature`,
  deliberately NOT upgraded to `DOKINGDesignTarget`.
- **Source:** `data/dokink_rfi_answers.md` (RFI #2); `python/design_
  basis.py` (`feedstock_composition`, `get_feedstock_composition_ranges()`);
  `python/ga001_gasifier_model.py` (`_input_feedstock_composition()`,
  `feedstock_composition_dokink_cross_check()`).

### 4. Feedstock LHV — precise value or confirm the range is final
- **Equipment ID(s):** Tab 1 "Overall efficiency" KPI; GA-001 (indirectly).
- **Parameter:** Feedstock LHV, **MJ/kg, dry basis**.
- **The question:** *DOK-ING's RFI #2 answer already states LHV 15–20
  MJ/kg (dry basis) — a real range. Tab 1's own "Overall efficiency" KPI
  is currently reported `Missing / Cannot Calculate`, citing "no
  feedstock LHV ever confirmed" — this framing is now stale given the
  range above. Is a precise point value available, or should the 15–20
  MJ/kg range itself be adopted as the calculation basis (reporting an
  efficiency RANGE rather than a point value)?*
- **Why it matters:** This is the single missing piece needed to compute
  Tab 1's own "overall efficiency" KPI (useful output energy / feedstock
  input energy) — currently the only Tab 1 KPI blocked purely by a
  numeric gap rather than a genuine model limitation.
- **UPDATE (feedstock-composition wiring task, 2026-09-03): option (b)
  above is now implemented — resolved, not left stale.** Tab 1's
  `overall_efficiency` KPI is no longer unconditionally
  `Missing / Cannot Calculate`; it reads DOK-ING's confirmed LHV range
  live (`design_basis.get_feedstock_composition_ranges()`) and reports a
  bounded H2-conversion-efficiency range (approximately 52–69% at this
  session's baseline load) — HB-012's live H2 output energy divided by
  FE-005's live dry feed rate × DOK-ING's confirmed 15–20 MJ/kg dry LHV
  range, per the Missing Parameter Protocol's Section 9 false-precision
  rule for a critical parameter given only as a range.
  **NEW open question surfaced by this exact change, not swept under the
  rug:** a first attempt also summed in EU-009's net electrical and
  EU-012's thermal output as one combined "plant overall efficiency" —
  and it came out **above 100%** for part of DOK-ING's own LHV range. Real
  cause, investigated: EU-009's own generation total includes EU-006's PEM
  Fuel Cell, dispatched from HB-013's *stored* H2
  (`eu_utilities_chp._h2_budget_kw`) — the SAME underlying H2 pool
  HB-012's `h2_kg_h` already counts once — and `eu_chp_dispatch`'s own
  syngas budget is GC-013's FULL flow, with no established split against
  whatever the WGS/PSA route already consumed to make that H2. This
  project's Phase 2 dispatch model was built with two independent budget
  inputs (syngas-for-CHP, H2-for-FuelCell) and no explicit allocation
  split between them — invisible until a real feedstock LHV existed to
  reveal it. **Deliberately NOT summed into `overall_efficiency`** (would
  have forced a misleading, occasionally-impossible number); electrical
  and thermal stay reported as their own separate live KPIs above. A real
  multi-carrier plant efficiency needs the actual physical gas-flow
  allocation traced across GA-001→GC→HB→EU first — a new, genuine
  candidate item for this list, not resolved here.
- **UPDATE (H2/syngas double-counting fix, 2026-09-03): the double-counting
  root cause above is FIXED.** `eu_utilities_chp.py` now allocates GC-013's
  syngas explicitly: `WGS_PSA_SYNGAS_CLAIM_FRACTION` (=100%, justified by
  DOK-ING's own confirmed RFI #10 answer, "H2 is primary; CHP using excess
  heat/syngas is optional, not fixed", *and* independently by this
  project's own already-tested 100% tail-gas recycle wiring) gives WGS/PSA
  its real first claim; `_syngas_budget_kw()` now returns the genuine
  EXCESS (a real conservation relationship, `total = claim + excess`, not
  a clamp). `hb_wgs_psa_storage_chain.py`'s `hb013_storage_level()` also
  gained a real, lagged outflow term for EU-006's own H2 consumption,
  previously computed but never subtracted from storage. **Honest,
  substantial consequence:** under this project's real 100% claim,
  SOFC/Gas Engine/Microturbine dispatch ~0 load and EU-012's district
  heating is genuinely ~0kW at every tested ER — not a residual bug, the
  correct reflection of DOK-ING's own stated priority once the masking bug
  is corrected. `overall_efficiency`'s own H2-only value is unchanged
  (52–69%, unaffected since it never used electrical/thermal). A full
  multi-carrier efficiency remains not implemented — a smaller, different
  timing concern (production-rate vs. accumulated-stock) than the
  double-count bug, documented in `tab1_integration.py`'s own KPI text.
- **Source:** `data/dokink_rfi_answers.md` (RFI #2, RFI #10);
  `python/tab1_integration.py` (`compute_tab1_kpis`, `overall_efficiency`);
  `python/eu_utilities_chp.py` (`WGS_PSA_SYNGAS_CLAIM_FRACTION`,
  `_total_syngas_energy_kw`, `_wgs_psa_syngas_claim_kw`, `_syngas_budget_kw`,
  `eu_chp_dispatch`); `python/hb_wgs_psa_storage_chain.py`
  (`hb013_storage_level`).

### 5. Fe₂O₃/Fe₃O₄ chemical-looping oxygen-carrier circulation rate/capacity
- **Equipment ID(s):** GA-001 (Gasifier).
- **Parameter:** Oxygen-carrier circulation rate, **kg/h**, at nominal
  load; oxygen-carrier conversion degree (reduction/oxidation extent),
  **fraction**; oxygen-carrier inventory/capacity, **kg**.
- **The question:** *GA-001's own Confirmed registry data states its
  real technology is "Bubbling Fluidized Bed (BFB), steam-blown, Fe₂O₃/
  Fe₃O₄ chemical looping oxygen carrier" — not a conventional simple
  air-blown gasifier. This project's own live gasifier model captures
  the real, confirmed air (ER=0.25) partial-oxidation contribution and
  the real, confirmed steam addition, closed with standard elemental/
  WGS-equilibrium stoichiometry — but it does NOT, and cannot, model the
  oxygen carrier's own separate reduction/regeneration chemistry and
  circulation loop, because no circulation rate, conversion degree, or
  carrier inventory figure exists anywhere in this project. What is the
  real Fe₂O₃/Fe₃O₄ circulation rate (kg/h) at nominal load, and the
  carrier's own typical conversion degree per pass?*
- **Why it matters:** This is a genuine, material simplification of the
  real equipment (stated as such in the model's own docstring, not
  hidden) — without it, GA-001's syngas composition/yield is a
  partial-oxidation+WGS approximation, not a true chemical-looping-
  gasification result. This is the single largest physics gap in the
  entire Digital Twin.
- **UPDATE (Missing Parameter Resolution Protocol applied, 2026-09-03; REVISED
  to a Comparable-equipment/Literature-based baseline, same date, after a
  real literature search grounded the earlier draft's citations more
  rigorously) — the underlying question above remains genuinely open,
  DOK-ING has not answered it.** Levels 1–2 re-confirmed empty (re-searched
  `design_basis.py`, `data/dokink_rfi_answers.md`, and the full equipment
  registry specifically for "circulation", "carrier-to-fuel", "carrier
  loading/inventory", "Fe₂O₃"/"Fe₃O₄" — nothing found beyond GA-001's own
  technology-name field). Level 3 (Comparable-equipment) and Level 5
  (peer-reviewed literature), COMBINED — a real, directly-numeric industrial
  pilot-plant source: **Graf, C., Coors, F., Marx, F., Dieringer, P.,
  Zeneli, M., Stamatopoulos, P., Atsonios, K., Alobaid, F., Ströhle, J., &
  Epple, B. (2024), "Development of a CFD-DEM Model for a 1 MWth Chemical
  Looping Gasification Pilot Plant Using Biogenic Residues as Feedstock,"
  *Energy & Fuels*, 38(19), 18660–18673** (DOI 10.1021/acs.energyfuels.4c02571)
  — reports EXPLICIT oxygen-carrier-circulation/fuel-feed-rate mass ratios
  for three real biomass feedstocks (18.4×–44.7×), not a generic "literature
  suggests" figure. Scaled to GA-001's own confirmed 37.5 kg/h dry feed
  rate: **DIGITAL TWIN ENGINEERING BASELINE ≈ 690–1,676 kg/h.**
  **Consistency check performed, not skipped (Section 4):** checked against
  this project's own confirmed O₂ demand (ER × stoichiometric O₂) and
  Fe₂O₃/Fe₃O₄'s own real, computed theoretical oxygen transport capacity
  (Ro = 3.34%, direct stoichiometry of 3Fe₂O₃ → 2Fe₃O₄ + ½O₂) — the
  literature-scaled range implies a **20.8%–50.5% per-pass carrier
  utilization**, against a ~10–30% conservative-practice reference for iron
  carriers. **Verdict: PARTIAL, flagged not forced** — the range's lower end
  (higher implied utilization) sits above that conservative window. A
  SEPARATE, structural caveat, not smoothed over: Graf et al.'s own carrier
  is **ilmenite** (Fe₂O₃+TiO₂+FeTiO₃) in a **dual circulating fluidized
  bed**, not GA-001's own confirmed **pure Fe₂O₃/Fe₃O₄** in a **bubbling**
  fluidized bed — CFB systems are generally capable of materially higher
  solids throughput than BFB, so the ratio may not transfer cleanly.
  Supporting, non-numeric context: Adánez et al. (2012), *Prog. Energy
  Combust. Sci.* 38(2), 215–282 (the field's foundational review); Sampron,
  Diego, Garcia-Labiano, Izquierdo, Abad & Adánez (2020), *Bioresource
  Technology* (a materially closer Fe₂O₃/Al₂O₃ carrier-chemistry match at
  smaller scale — its own specific circulation figure was paywalled and
  could not be directly verified, so not used as the quantitative source).
  `python/ga001_gasifier_model.py`: `oxygen_carrier_circulation_estimate()`,
  registered as `("GA-001","OxygenCarrierCirculationEstimate")`, tagged
  `Estimated`/`Comparable-equipment, Literature-based` — does NOT feed back
  into `ga001_model()`'s own physics; a full reduction/oxidation reaction-
  network model remains the separate, larger physics gap named above, not
  attempted here. **ACTUAL/DOK-ING VALUE: still Missing/Unverified** — the
  real open question (DOK-ING's own actual circulation rate, carrier
  inventory, and per-pass conversion degree) is unchanged and explicitly
  still open, alongside a SEPARATE, deliberately undecided follow-up
  question: whether/how this baseline should ever feed into GA-001's own
  calculations at all.
- **Source:** `python/ga001_gasifier_model.py` module docstring (the
  "MAJOR FINDING" paragraph) and `oxygen_carrier_circulation_estimate()`;
  `data/equipment_registry.json` GA-001; Graf et al. (2024), *Energy &
  Fuels* 38(19), 18660–18673 (DOI 10.1021/acs.energyfuels.4c02571), Table 8
  (primary numeric source); Adánez et al. (2012), *Prog. Energy Combust.
  Sci.* 38(2), 215–282 (supporting review).

### 6. GA-001/GA-003 primary air-flow reconciliation
- **Equipment ID(s):** GA-001, GA-003 (Air/Steam Injection, Flow).
- **Parameter:** Primary air flow rate at ER=0.25, **Nm³/h**.
- **The question:** *This model's own independently-derived air
  requirement at ER=0.25 (37.5 kg/h dry feed basis) is 38.79 Nm³/h.
  GA-003's own registry-stated "Primary air flow rate (design)" is 60
  Nm³/h — a ratio of 0.646. GA-003's own remark states its 60 Nm³/h
  figure was itself "Derived from ER=0.25 × stoichiometric air demand for
  the dry feed rate — not DOK-ING-confirmed," i.e., a prior estimate
  using the same method but evidently a different assumed feedstock
  composition. Which of these two air-flow figures (if either) reflects
  the actual specified/installed air-blower capacity, and what feedstock
  composition was GA-003's own 60 Nm³/h figure originally computed from?*
- **Why it matters:** This is the same underlying gap as item 3 (feed
  composition) surfacing a second time as a numeric cross-check — closing
  item 3 would very likely resolve this discrepancy directly, without a
  separate answer.
- **Source:** `python/ga001_gasifier_model.py` self-test ("Cross-check
  against GA-003's own registry-stated air flow").

### 7. HB-003 heat-exchanger duty reconciliation (three-way mismatch)
- **Equipment ID(s):** HB-003 (Heat Exchanger, WGS interstage).
- **Parameter:** Design heat duty, **kW**.
- **The question:** *HB-003's own Confirmed "Design heat duty" is 5 kW.
  This model's own two independently-computed values are: gas-side
  (hot-side) sensible-heat duty = 6.360 kW; water-side (cold-side) duty
  (feedwater heating to HB-005's own steam-generation requirement) =
  9.436 kW. None of the three figures agree. Which is closest to the
  real, installed unit's actual rating, and does the 5 kW Confirmed
  figure include only part of the real duty (e.g., a different
  temperature/flow basis)?*
- **Why it matters:** This propagates into HB-005's own live steam
  generation rate and, via GA-001's own recycle-moisture and steam
  balance, into the whole downstream H₂ production chain.
- **Source:** `python/hb_wgs_psa_storage_chain.py` self-test ("HB-003
  duty" cross-check).

### 8. GC-009 HCl removal efficiency — below its own stated target
- **Equipment ID(s):** GC-009 (HCl Scrubber).
- **Parameter:** HCl removal efficiency, **%**.
- **The question:** *This model's own computed efficiency, using GC-009's
  own Confirmed inlet/outlet concentrations, is 96.67% — GC-009's own
  stated target is ">97%". Is the >97% figure a guarantee at a different
  (e.g., lower) inlet loading than the Confirmed design-point figures
  this calculation used, or is the scrubber's real performance genuinely
  slightly below its own stated target at the stated design point?*
- **Why it matters:** A real, if small, gap between a stated removal
  target and the equipment's own Confirmed inlet/outlet numbers —
  relevant to downstream WGS/PSA catalyst chlorine tolerance.
- **Source:** `python/gc_gas_cleaning_chain.py` self-test.

### 9. HB-007 H₂ split fraction — LOHC branch feed allocation
- **Equipment ID(s):** HB-007 (PSA Unit, H₂ Recovery), HB-014 (LOHC
  Hydrogenation), HB-015 (LOHC Storage), HB-016 (LOHC Dehydrogenation),
  HB-017 (H₂ Purification, Post-LOHC).
- **Parameter:** H₂ split fraction to the LOHC branch, **fraction (0–1)**
  of HB-007's own PSA product H₂ flow.
- **The question:** *No data anywhere specifies what fraction (if any) of
  HB-007's own PSA product H₂ stream is diverted to the LOHC hydrogenation
  branch (HB-014) versus the primary compressed-storage route (HB-012 →
  HB-013). HB-014's own registry remark only describes its 2 kg H₂/h
  capacity as a sizing "margin above HB-007's established ~1.85 kg/h PSA
  product rate" — a capacity comparison, not a confirmed allocation. Is
  there a real, planned split fraction (or a control strategy for
  determining one dynamically)?*
- **Why it matters:** This single missing value is the ONE root cause
  blocking HB-014/015/016/017's entire mass-balance chain — proven by
  this project's own structural-propagation mechanism (all four
  downstream Missing statuses trace to this one key, not four
  independent gaps). Answering it converts the whole LOHC branch from
  Missing to genuinely live.
- **Source:** `python/hb_remaining_chain.py` (`hb007_h2_split_fraction`).

### 10. HB-010 membrane separator selectivity
- **Equipment ID(s):** HB-010 (Membrane Separator).
- **Parameter:** H₂/other-species selectivity (dimensionless ratio, e.g.
  H₂/CO₂ selectivity), at the Confirmed 50 GPU H₂ permeance operating
  point.
- **The question:** *HB-010's own registry gives H₂ permeance (50 GPU)
  and a static design-point recovery/purity figure (85% / 95–98%), but no
  membrane selectivity. What is the real H₂/CO₂ (and H₂/CH₄, H₂/CO)
  selectivity of the specified membrane?*
- **Why it matters:** Solution-diffusion membrane transport theory needs
  permeance AND selectivity together (with feed composition and pressure
  ratio) to compute a live, composition-dependent recovery/purity — this
  is the one piece needed to make HB-010's own second output (beyond
  its already-live feed pass-through) genuinely calculated instead of
  permanently Missing.
- **UPDATE (Missing Parameter Resolution Protocol applied, 2026-09-03) —
  the underlying question above remains genuinely open, DOK-ING has not
  answered it.** Levels 1–2 re-checked, not assumed empty: `design_basis.py`
  and `data/dokink_rfi_answers.md` searched for "selectivity" — genuinely
  nothing Confirmed. **Level 2 (Internal-model-derived) is NOT empty,
  unlike the chemical-looping item** — HB-010's own registry already
  confirms a design-point recovery (85%) and permeate purity (95–98%) AT a
  Confirmed 55% feed H₂ content (matching HB-006's own Confirmed feed H₂
  content exactly). Standard solution-diffusion membrane transport theory
  (the "low back-permeation" approximation, y_p/(1−y_p) = α·x_f/(1−x_f);
  Baker, R.W., *Membrane Technology and Applications*, Wiley) back-derives
  what EFFECTIVE H₂/(everything else) selectivity those confirmed numbers
  themselves imply, evaluated **at that same Confirmed 55% design-point
  feed basis** (a real error — re-deriving it at HB-010's own live,
  fluctuating feed composition instead — was caught and fixed by this
  module's own self-test before being shipped; selectivity is
  approximately a material property, recovery/purity are outputs that
  genuinely vary with feed composition). **DIGITAL TWIN ENGINEERING
  BASELINE ≈ 15.5–40.1** (dimensionless). **Consistency check performed
  (Section 4): PASS, not forced** — a real comparable polyimide
  hollow-fiber membrane module (~39 GPU H₂ permeance, closely matching
  HB-010's own Confirmed 50 GPU) reports a measured H₂/CO₂ selectivity of
  **20.2**, which falls cleanly inside the internally-derived range — a
  genuine convergence between two independent methods ("Recent advances in
  H₂ purification and CO₂ capture: Evolving from flat sheet to hollow fiber
  membranes," ScienceDirect, Oct. 2024, PII S2772656824001465 — full
  author/journal/volume details could not be retrieved, paywalled; cited
  by title/identifier/date only, not a fabricated author list). Justified
  as representative of H₂/CO₂ specifically, not just a generic lump:
  `psa.py`'s own already-documented default composition (CO₂ ≈ 78% of the
  45% non-H₂ fraction) confirms CO₂ is the overwhelmingly dominant
  non-H₂ species in this exact feed stream. **HONEST SCOPE LIMIT:** this
  gives one lumped, effective selectivity, not separate H₂/CO₂, H₂/CH₄,
  H₂/CO figures individually — the original question named all three;
  only an aggregate is resolved here. `python/hb_remaining_chain.py`:
  `hb010_selectivity_estimate()`, registered as
  `("HB-010","SelectivityEstimate")`, tagged `Estimated`/`Internal-model-
  derived` — ADDITIVE; `hb010_separation()`'s own permanently-Missing
  status is deliberately UNCHANGED. **ACTUAL/DOK-ING VALUE: still
  Missing/Unverified** — the real question (DOK-ING's own actual, species-
  specific selectivity) is unchanged and explicitly still open, alongside
  a SEPARATE, deliberately undecided follow-up question: whether/how this
  baseline should ever feed `hb010_separation()`'s own recovery/purity
  calculation at all.
- **Source:** `python/hb_remaining_chain.py` (`hb010_separation`,
  `hb010_selectivity_estimate`); `data/equipment_registry.json` HB-010;
  "Recent advances in H₂ purification and CO₂ capture: Evolving from flat
  sheet to hollow fiber membranes," ScienceDirect, Oct. 2024, PII
  S2772656824001465 (primary numeric comparable-equipment source).

### 11. HB-014/HB-016 LOHC catalyst reaction kinetics
- **Equipment ID(s):** HB-014 (LOHC Hydrogenation, Pt/Pd/Al₂O₃ catalyst),
  HB-016 (LOHC Dehydrogenation, Pt/Al₂O₃ catalyst).
- **Parameter:** Reaction rate constants / activation energy (kinetic
  parameters) for both directions, at the Confirmed operating conditions
  (HB-014: 170°C/40 bar; HB-016: 300°C/2 bar).
- **The question:** *No catalyst kinetic data (rate constants, activation
  energy) exists for either the DBT hydrogenation (HB-014) or
  dehydrogenation (HB-016) reaction. Is vendor/catalyst-supplier kinetic
  data available, or would this need dedicated lab characterization?*
- **Why it matters:** Independent of item 9 (the split-fraction block) —
  even once HB-007's split fraction is confirmed, HB-014/016's own
  REACTION KINETICS outputs stay permanently Missing without this; only
  their mass-balance outputs would become calculable.
- **Source:** `python/hb_remaining_chain.py` (`hb014_reaction_kinetics`,
  `hb016_reaction_kinetics`).

### 12. Remaining registry-level project-knowledge gaps (bucketed)
33 category-level gaps (Inputs/Operating Conditions for DOK-ING's own
core process technology — the gasifier train and primary WGS+PSA route —
plus site/external-infrastructure interconnection items for EU-009/
EU-012/EU-013) were already classified by this project's own routing
logic as realistically answerable only by DOK-ING (not a vendor, not a
generic process engineer). **Not re-itemized here** — see `python.
equipment_request_routing.generate_routed_request_markdown()`'s own
"DOK-ING (project-level knowledge)" section for the full, itemized list
(33 lines, each already stating the specific equipment/category and the
routing rationale).

---

## Section 2 — Equipment vendors (once selected)

**163 category-level gaps** (57.4% of the 284 already-routed registry
gaps) are genuinely vendor-spec-dependent: instrument accuracy/response-
time/calibration-interval (Measurements), a rated discharge/output
capacity (Outputs), guaranteed efficiency/recovery-rate (Performance
Indicators), dimensions/materials/construction (Parameters). **No amount
of process engineering or DOK-ING's own project knowledge can supply
these before a specific manufacturer/model is chosen** — this bucket
closes only via the vendor-sourcing process (`python/vendor_log.py`).

**Not re-itemized here** — the full, itemized 163-line list (plus the
broader 291-line pre-routing list, which additionally includes items not
yet run through the routing classifier) already exists as generated
documents:
- `python.equipment_data_requests.generate_request_list_markdown()` — all
  291 real "Missing Data — Required" category slots, by equipment section
  (FE 22, GA 33, GC 38, SA 46, HB 52, EU 33, AI 67).
- `python.equipment_request_routing.generate_routed_request_markdown()` —
  the 163 items specifically routed to "Vendor (equipment not yet
  selected)," with the routing rationale stated per item.

Representative categories, for context (not exhaustive): SA-001–012's own
Measurements (accuracy, response time, calibration interval) for every
gas analyser/sensor; AI-005–010's own infrastructure hardware specs; most
equipment items' own Outputs/Performance Indicators once a specific
vendor unit is picked.

---

## Section 3 — Process/design engineer

**UPDATE (bucket reconciliation, 2026-09-03): the 77-item bucket below was
generated from the STATIC equipment registry, independent of the live
Python model, and had never been checked against it — done for this task,
item by item, not sampled.** Correct function name: `python.
equipment_request_routing.generate_routed_request_document()` (the
`generate_routed_request_markdown()` name previously cited here does not
exist in the module — a stale reference, fixed here).

**Result of the full 77-item reconciliation:**
- **21 of 77 lines are STALE — the live model already computes a real
  value.** Verified directly in code: `fe002_mass_balance`/`fe003_weighing`/
  `fe004_shredder_power`/`fe006_moisture_reading` (all 4 FE lines);
  `gc001_temperature`/`gc003_temperature`/`gc004_quench_gas`/
  `gc005_blowdown`/`gc008_h2s`/`gc012_h2s_cos_polish`/`gc013_gas_final`
  (7 GC lines); `hb011_electrolyser`/`hb018_dispensing` (2 HB lines);
  `eu004_gas_engine_thermal`/`eu006_fuel_cell`/`eu007_flare`/
  `eu008_cooling_supply`/`eu010_ups_battery` (7 EU lines) — plus EU-001
  (1 line), which is not a live gap at all: its own module docstring
  already states it is a controlled setpoint deliberately, correctly not
  modeled separately, not an oversight.
- **5 lines (4 equipment IDs) are genuinely open AND newly A-eligible** —
  no live implementation exists, and each is a real, standard chemical/
  process-engineering calculation the evidence hierarchy can address (see
  the prioritized list below): **GC-002** (Primary Cyclone ΔP), **GC-011**
  (Bag Filter ΔP), **GC-014** (Gas Blower discharge pressure, 2 lines),
  **GC-015** (Condensate Tank operating conditions).
- **1 line is genuinely open, A-eligible IN CATEGORY, but already
  investigated and correctly left unresolved — not a fresh opportunity:**
  **GC-006** (Tar Removal Unit inlet loading). `gc006_tar_inlet_missing()`
  already states why: raw MSW-gasification tar loadings are commonly cited
  across a 1–100+ g/Nm³ literature range — too wide to state with real
  confidence for this specific plant (the same finding
  `equipment_engineering_estimates.py` already reached independently).
  Re-litigating this is not recommended without new information.
- **4 lines (HB-014/015/016/017) are genuinely open but are NOT independent
  gaps** — each is a live-registered function already correctly blocked by
  item 9's own structural propagation (HB-007's Missing split fraction).
  Resolving item 9 (Category C, a business/commercial decision — see
  Section 1) resolves these automatically; they are not separate A-work.
- **46 lines (12 AI/IT-infrastructure equipment IDs) are Category B, not
  A**, regardless of staleness: `ai_automation_layer.py` already models a
  connectivity/identity/orchestration-state ASPECT of every one of AI-004
  through AI-015 (confirmed in code), but the SPECIFIC fields this bucket
  asks for (network-protocol choice, redundancy scheme, SLA/throughput
  targets) are systems-architecture decisions specific to this project's
  own control-system implementation — not derivable from process-
  engineering or materials-science literature the way GC-002/011/014/015
  are.
- **21 + 5 + 1 + 4 + 46 = 77.** Every line accounted for.

**Also resolved — the audit's own flagged incompleteness (the "18
unaccounted items"):** `route_requests()` itself correctly assigns an
owner to all 291 generated gaps (verified directly: 164 Vendor + 78
Design + 38 DOK-ING + 11 Uncertain = 291) — the 284-vs-291 discrepancy is
**not** "7 items never run through the routing classifier" as this
document previously speculated. It is a real, verified **rendering bug**
in `generate_routed_request_document()` itself: 7 specific
`(item_id, category)` pairs are computed with a real owner but silently
dropped from the rendered text (**FE-001** Inputs, **GA-001** Inputs +
Performance Indicators, **GA-005** Inputs, **GA-009** Inputs, **HB-013**
Inputs, **EU-009** Inputs). Checked individually: FE-001, GA-001, HB-013,
and EU-009 are all already live-modeled (confirmed in code) — stale, no
action needed. GA-005 and GA-009 are genuinely open, correctly B (DOK-ING's
own proprietary ash/carbon-black handling equipment, no live model exists
for either) — already covered in spirit by item 12's own bucket, just
invisible in the rendered document due to this bug. **Not a code change
made here** (out of this task's scope) — flagged as a real, small,
low-priority bug in `equipment_request_routing.py`'s own rendering logic.
The separate **11-item "Uncertain/needs discussion" bucket** (all
`Measurements` fields for the same AI-004..015 items above) is genuinely
ambiguous between Vendor and Design/process-engineer routing, per its own
stated reasoning — same B classification as the 46 AI lines above, now
referenced here for completeness.

### Prioritized new A-candidates from this reconciliation (ordered by real impact)

1. **GC-014 — Gas Blower discharge pressure.** Directly determines whether
   GC-013's own fan/blower can deliver gas at HB-008's own Confirmed 8
   bar(a) PSA feed pressure — a real, calculable systems value (cumulative
   train pressure drop + the confirmed downstream requirement), with
   direct consequence for the whole WGS/PSA route's own feasibility.
2. **GC-002 — Primary Cyclone ΔP.** A standard, well-established cyclone
   pressure-drop correlation (particle-laden gas, known flow/geometry) —
   feeds directly into the SAME gas-train pressure budget GC-014 needs.
3. **GC-011 — Bag Filter ΔP.** Same class of standard, well-established
   fabric-filter pressure-drop correlation, same gas-train pressure
   budget.
4. **GC-015 — Condensate Tank operating conditions.** Lowest impact of the
   four — likely a trivial ambient/atmospheric-conditions determination
   for a gravity-drained collection tank, not a load-bearing calculation.

Specific, already-identified items worth an engineer's direct judgment
(distinct from the bucketed 77, called out individually because they
already have a real, documented consequence in the live model):

1. **EU-008 sizing margin** (once item 1 above is answered): if a genuine
   resizing is needed, this project's own live model uses a standard
   10–20% HVAC/process-cooling design-margin convention (15% representative
   point used) — a design engineer should confirm the actual margin
   convention to apply for this specific duty/site.
2. **ASSUMED_HOURS_PER_CYCLE mapping** (`python/hb_wgs_psa_storage_chain.py`):
   this project's own simulation cycle currently has no defined real-world
   wall-clock duration; 1 hour/cycle is a stated, explicit modeling choice
   for inventory-accumulation demonstrations (HB-013 H₂ storage, FE-001
   hopper, EU-010 battery SOC) — a control/automation engineer should set
   the real intended PLC scan-to-digital-twin-cycle mapping once the
   actual control architecture is designed.
3. **Compressor polytropic exponent** (HB-012, `COMPRESSOR_POLYTROPIC_N =
   1.3`): a standard, literature-typical value for a well-intercooled
   multistage compressor, not derived from HB-012's own specific data —
   confirm once a vendor unit (Section 2) is selected and its own
   isentropic/polytropic efficiency curve is available.
4. **PEM electrolyser (HB-011) part-load parameters**
   (`HB011_MIN_LOAD_FRACTION = 0.10`, `HB011_BOP_POWER_FRACTION = 0.08`):
   literature-typical PEM turndown/balance-of-plant figures, not
   HB-011-specific — confirm against the selected stack's own real
   part-load curve once available.

---

## Section 4 — Registry data-quality maintainer (kept explicitly separate)

**This section is NOT for DOK-ING.** These are internal cross-reference
errors within `data/equipment_registry.json`'s own free-text remarks
(one item's remark citing the wrong other item's ID/name) — not a
missing fact, but a mislabeled existing one. Conflating this list with
Section 1 is exactly the kind of vagueness this document exists to avoid.

**32 items** are already fully documented, each with the exact field, the
wrong reference, and the almost-certainly-correct one, in `CLAUDE.md`'s
own "Known source-data issues" section — not re-itemized here in full.
Summary by pattern:
- **Items 1–13:** a systematic GC-006 (Tar)/GC-008 (H₂S)/GC-009 (HCl)/
  GC-012 (Activated Carbon) confusion, recurring across GC, SA, and HB
  items' own remarks (the same species-handling mix-up appearing 13
  times).
- **Items 14–20:** a second cluster — HB-004/HB-005/EU-004/EU-011/EU-012/
  EU-013's own cross-references to each other and to HB-003, including
  the EU-012 "EU-004 + EU-006" thermal-output attribution (should read
  EU-011, since EU-006 the H₂ Fuel Cell has no thermal output anywhere
  in this project).
- **Items 21–32:** AI-002/007/010/012/013/014/015's own cross-references
  to FE, EU, and AI items.

**Found during the digital twin build, not yet cross-posted into
CLAUDE.md's own numbered list** — flagged here so they aren't lost:
- **FE-002's** own remark calls FE-003 "the Shredder" — FE-003 is the
  Weighing Conveyor; FE-004 is the actual Shredder/Size Reducer.
- **FE-003's** own remark describes its connecting run as "between FE-008
  and FE-003" — a literal self-reference, garbled (the real sequence is
  FE-002 → FE-003 → FE-004).
- **FE-006's** own remark says it "reads material right as it leaves
  FE-007, before FE-005" — physically backwards (a moisture analyser
  reading material as it leaves a RAM FEEDER, before a DRYER, makes no
  sense); almost certainly means "leaves FE-005 [the dryer], before
  FE-007 [the ram feeder]."
- **FE-007's** own remark says its feed plug "works with FE-006
  downstream to hold reactor pressure" — FE-006 is the Moisture Analyser,
  not a valve; almost certainly FE-008 (the Air-lock/Rotary Valve).
- **FE-008's** own remark says its own seal "works with FE-005's
  compacted plug" — FE-005 is the Dryer, with no plug feature; FE-007's
  own data is the one that actually describes a compacted feed plug.

(Source: `python/fe_feed_handling.py` module docstring, Phase 3.)

---

## Final counts

| Section | Item count |
|---|---|
| **1 — DOK-ING** | **11 individually detailed, high-value items** + 1 bucketed reference (33 registry-level gaps, itemized elsewhere) |
| **2 — Equipment vendors** | **163 gaps** (bucketed/referenced; not re-itemized) |
| **3 — Process/design engineer** | **4 individually detailed items** + 1 bucketed reference (77 registry-level gaps, **RECONCILED against the live model 2026-09-03: 21 stale, 5 new A-candidates, 1 already-investigated-and-declined, 4 duplicate-of-item-9, 46 Category B — see the update above**) |
| **4 — Registry data-quality maintainer** | **32 items** already in `CLAUDE.md` (bucketed/referenced) + **5 newly found, not yet cross-posted** (listed in full above) |

**Grand total of distinct open items tracked across the project:** 291
registry-level category gaps (Sections 1's bucket + all of Section 2 +
Section 3's bucket) + 11 high-value DOK-ING-specific findings from the
digital twin build (Section 1, individually detailed; these are largely
NOT part of the 291, since they're numeric/model-structural findings, not
registry category gaps) + 4 design-engineer-specific findings (Section 3)
+ 37 registry mislabels (Section 4) = **291 registry-category gaps + 15
build-derived findings + 37 mislabels**, none double-counted between
sections.

**UPDATE (2026-09-03):** the "284 routed" figure cited throughout Sections
1–3 (33+163+77+11) undercounts the true routed total by 7 — verified
directly: `route_requests()` actually assigns a real owner to all 291
generated gaps (164 Vendor + 78 Design + 38 DOK-ING + 11 Uncertain = 291).
The gap is a rendering bug in `generate_routed_request_document()`, not a
"never classified" set — see the Section 3 update above for the 7 exact
items and their disposition (5 already stale, 2 genuinely open and
correctly B).

*Generated 2026-09-02, from the project's actual current state — every
number above was produced by running or reading the live code and
documents listed as each item's own source, not recalled from earlier
conversation. Section 3's own bucket reconciled against the live model
2026-09-03 (see above); no other section's figures were re-verified in
that pass.*
