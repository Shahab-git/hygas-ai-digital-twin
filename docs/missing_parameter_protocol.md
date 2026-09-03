# HYGAS-AI Digital Twin — Missing Parameter Resolution Protocol

## Objective

The HYGAS-AI Digital Twin must be completed as a full, internally consistent engineering model without waiting for further DOK-ING responses.

From this point forward, **no Missing, Unconfirmed, or DOK-ING-dependent parameter should block Digital Twin development**, unless it is genuinely impossible to establish even a defensible engineering baseline.

Do not create additional RFI questions simply because a parameter is missing.

Instead, resolve missing parameters using the evidence hierarchy and engineering methodology defined below.

The purpose is to create a **complete engineering baseline**, not to reproduce unknown DOK-ING plant-specific information.

---

# 1. Mandatory Evidence Hierarchy

For EVERY Missing or Unconfirmed parameter, determine its value using the strongest available evidence in this order:

### Level 1 — Project-Confirmed Data

Search the complete existing project for confirmed information, including:

* Equipment registry
* Design basis
* RFI records
* Existing engineering documentation
* Validated equipment models
* Existing Python modules
* Existing calculations
* Existing test/self-test outputs
* Previously established project parameters
* Other internally consistent project data

If a reliable confirmed value exists, use it.

Status:

`Confirmed`

---

### Level 2 — Existing Modeled Equipment / Internal Consistency

If no confirmed value exists, derive the parameter from existing validated models and connected equipment.

Use:

* Upstream equipment requirements
* Downstream equipment requirements
* Existing mass balances
* Energy balances
* Thermodynamic relationships
* Existing equipment capacities
* Existing operating conditions
* Existing utility requirements
* Existing process flows

The Digital Twin itself should be treated as an engineering source when its underlying model has already been validated.

Status:

`Internal-model-derived`

---

### Level 3 — Comparable Industrial Equipment

If the parameter cannot be established from project data, identify technically comparable industrial equipment.

The comparison should consider, where relevant:

* Equipment type
* Process duty
* Capacity
* Operating temperature
* Operating pressure
* Feed/product characteristics
* Scale
* Industrial application
* Technology maturity

Use comparable industrial equipment to establish a realistic baseline.

Status:

`Comparable-equipment estimate`

Do not select a value merely because it is available online. The equipment must be technically comparable.

---

### Level 4 — Manufacturer Datasheets

If suitable comparable equipment exists, use manufacturer datasheets and technical specifications as evidence.

Prefer:

* Established industrial manufacturers
* Actual equipment specifications
* Published technical datasheets
* Technical manuals
* Application documentation

Use the closest technically relevant equipment rather than simply choosing the largest or most convenient specification.

Status:

`Literature-based` or `Comparable-equipment estimate`

Record the source and explain why the equipment is considered comparable.

---

### Level 5 — Peer-Reviewed Literature

If suitable manufacturer/comparable-equipment data are unavailable, use:

* Peer-reviewed papers
* Technical publications
* Established engineering references
* Experimental studies
* Published process data

Prefer sources that provide actual operating data or experimentally validated ranges.

Status:

`Literature-based`

---

### Level 6 — Engineering Calculation / Correlation

If no suitable direct value exists, calculate the parameter using recognised engineering relationships.

Examples include:

* Mass balances
* Energy balances
* Heat-transfer equations
* Thermodynamic equations
* Reaction stoichiometry
* Equipment sizing correlations
* Pressure-drop correlations
* Heat-exchanger calculations
* Compressor relationships
* Pump calculations
* Flow relationships
* Efficiency relationships
* Standard engineering design practice

The calculation and assumptions must be recorded.

Status:

`Engineering estimate`

---

### Level 7 — Explicit Engineering Assumption

Only when no stronger evidence is available may an explicit engineering assumption be introduced.

The assumption must:

* Be physically plausible
* Be appropriate for the equipment scale
* Be consistent with connected systems
* Have a reasonable range
* Be clearly labelled
* Be replaceable later

Status:

`Engineering assumption`

**Never invent a number without identifying it as an assumption.**

---

# 2. Do Not Wait for DOK-ING

DOK-ING-specific confirmation is NOT a prerequisite for continuing Digital Twin development.

If the actual installed value is unavailable:

1. Preserve the fact that the actual value is unknown.
2. Establish the best defensible engineering baseline.
3. Use that baseline in the Digital Twin.
4. Clearly record its source and confidence.
5. Make the parameter replaceable when actual plant/vendor data become available.

The Digital Twin should therefore contain both:

`Actual plant value = Missing / Unverified`

and, where possible:

`Engineering baseline = [estimated value]`

These two concepts must never be conflated.

---

# 3. Mandatory Internal Consistency Check

Every estimated parameter MUST be checked against the surrounding system.

At minimum, evaluate the following where applicable:

### Mass balance

Check:

* Feed
* Product
* Recycle
* Losses
* Conversion
* Yield
* Composition

### Energy balance

Check:

* Heat input
* Heat generation
* Heat rejection
* Utility demand
* Equipment power
* Thermal losses

### Pressure

Check:

* Upstream pressure
* Downstream pressure
* Required pressure differential
* Equipment pressure limits

### Temperature

Check:

* Inlet temperature
* Outlet temperature
* Operating range
* Material/equipment limitations

### Flow

Check:

* Mass flow
* Volumetric flow
* Gas flow
* Liquid flow
* Utility flow

### Capacity

Check:

* Rated capacity
* Peak demand
* Normal operating demand
* Design margin

### Efficiency

Check:

* Equipment efficiency
* Conversion efficiency
* Thermal efficiency
* Electrical efficiency
* System efficiency

Do not accept an estimated parameter if it creates an unexplained physical inconsistency elsewhere in the Digital Twin.

---

# 4. Resolve Conflicting Existing Values Carefully

If two values appear to conflict, do NOT immediately decide that one is wrong.

First determine:

1. What does each value represent?
2. Is one value associated with a narrower duty?
3. Is one value a nominal value and the other a calculated peak?
4. Are they associated with different operating conditions?
5. Could separate equipment or utility paths exist?
6. Could the current Digital Twin topology be incorrectly aggregating loads?
7. Is one value a confirmed project value while the other is a model-derived estimate?

Only after this investigation should the discrepancy be resolved.

### Example: EU-008

Do NOT automatically conclude:

`20 kW = wrong`

and do NOT automatically replace it with:

`66.7 kW = correct`

Instead determine whether the 20 kW value was originally intended for a narrower duty, such as EU-004 jacket cooling, and whether other cooling consumers have a separate cooling path.

The original value must remain traceable.

---

# 5. Avoid False Precision

Do not report unnecessary numerical precision for estimated parameters.

The number of significant figures must reflect the confidence of the underlying evidence.

For example:

Do NOT present:

`66.73 kW`

as though it were an exact plant specification if it is only an engineering estimate.

Prefer:

`approximately 65–70 kW`

or another appropriate engineering range.

Likewise, avoid excessive decimal places in:

* Equipment capacities
* Flow rates
* Efficiencies
* Temperatures
* Pressures
* Reaction parameters
* Utility requirements

unless the underlying source genuinely supports that precision.

---

# 6. Required Parameter Metadata

Every parameter established through estimation MUST have traceable metadata.

At minimum record:

```text
parameter_name
baseline_value
unit
status
evidence_level
source
source_reference
engineering_basis
uncertainty_or_range
confidence
assumptions
date_established
replaceable_with_actual_data = true
```

Where possible also record:

```text
alternative_values_considered
reason_for_selected_baseline
upstream_consistency_check
downstream_consistency_check
```

---

# 7. Required Status Classification

Use the following status categories consistently:

### Confirmed

Directly supported by reliable project-specific information.

### Internal-model-derived

Derived from an existing validated project model or established internal relationship.

### Comparable-equipment estimate

Derived from technically comparable industrial equipment.

### Literature-based

Supported primarily by published technical/literature data.

### Engineering estimate

Calculated using engineering equations, correlations, or established engineering practice.

### Engineering assumption

Introduced because stronger evidence is unavailable.

### Missing / Unverified

The actual plant-specific value remains unknown.

**Important:**

An estimated baseline does NOT change the actual plant parameter from:

`Missing / Unverified`

to:

`Confirmed`.

---

# 8. Actual Value vs Engineering Baseline

For every important missing parameter, maintain this distinction:

```text
ACTUAL / DOK-ING VALUE:
Missing / Unverified

DIGITAL TWIN ENGINEERING BASELINE:
[best defensible estimated value]

STATUS OF BASELINE:
[appropriate status]

UNCERTAINTY:
[range]

SOURCE / BASIS:
[traceable evidence]
```

This allows the Digital Twin to operate now while remaining ready for future calibration.

---

# 9. Critical Parameters

For high-impact parameters, do not fabricate a precise value merely to make the model run.

This applies particularly to:

* Feedstock composition
* Gasifier operating conditions
* Syngas composition
* Hydrogen production rate
* Hydrogen purity
* Product pressure
* Major equipment capacity
* Safety limits
* Pressure limits
* Temperature limits
* Critical reaction parameters

If a defensible single value cannot be established:

1. Establish a bounded engineering scenario if possible.
2. Provide a range.
3. Mark the actual value as Missing / Unverified.
4. Document the uncertainty.
5. Keep the model calibration-ready.

Do not convert an unknown critical parameter into a falsely precise "known" parameter.

---

# 10. No New RFI Dependency

The purpose of this protocol is specifically to prevent the Digital Twin from becoming dependent on unanswered DOK-ING questions.

Therefore:

**Do not create or escalate a new RFI question simply because a parameter is missing.**

First attempt to resolve it through the full evidence hierarchy.

Only classify a parameter as genuinely unresolved when:

* No project evidence exists,
* No suitable comparable equipment exists,
* No reliable literature value exists,
* No defensible engineering calculation is possible,
* and no physically reasonable assumption can be made without creating unacceptable uncertainty.

Even then, provide the best possible bounded scenario rather than stopping the Digital Twin.

---

# 11. Retroactive Application

This protocol applies NOT ONLY to future parameters.

Review existing estimates and assumptions throughout the Digital Twin.

In particular, review:

* EU-008
* HB-010
* HB-014
* HB-016
* Existing equipment-registry gaps
* Previously generated engineering estimates
* Any parameter currently labelled as Missing but for which a defensible engineering baseline can now be established

Existing estimates must be checked against this methodology and corrected where necessary.

---

# 12. Final Objective

The goal is to deliver a:

**COMPLETE + INTERNALLY CONSISTENT + TRACEABLE + CALIBRATION-READY DIGITAL TWIN**

without waiting for DOK-ING to provide every missing parameter.

The model must distinguish clearly between:

**What is known**

**What is derived**

**What is estimated**

**What is assumed**

**What remains genuinely unknown**

The absence of DOK-ING data should no longer stop engineering development.

However, estimated values must NEVER be presented as confirmed plant-specific facts.

### Core principle

Do not ask:

> "What number would DOK-ING probably provide?"

Ask:

> "What is the strongest technically defensible value that can be established from the available evidence?"

Use that value as the Digital Twin engineering baseline, document its provenance and uncertainty, maintain internal consistency, and keep it replaceable when real plant data become available.
