# Blender plant model: layout and geometry assumptions (generated; do not edit by hand)

Regenerate with `python blender/plant_layout.py --write-docs`. This model is a SCHEMATIC ENGINEERING LAYOUT, not vendor CAD, not a P&ID and not a surveyed site plan.

## What is taken from the registry and what is assumed

- Taken from `data/equipment_registry.json`: every ID, name and category (91 items, none invented).
- Sizes stated by the registry (`registry`): 5 items. Footprint estimated around a registry-stated count or volume (`estimate`): 10. Representative size assumed (`assumed`): 76.
- NOT in the registry and therefore NOT drawn: connections between items (no upstream/downstream data). Stage 3 will draw only the documented process chain and mark the rest conceptual.
- Item order inside a zone follows the registry ID order. That is an ASSUMPTION about the process order, not a verified P&ID.
- Lane spacing (8.0 m), item gap (1.4 m), plinth height, site size (64 x 46 m) and all `assumed` sizes are representative values chosen for the picture.

## Registry rows drawn as an instrument tag on another unit (assumption: they describe the same equipment from another measured angle)

- AI-003 (Bed Pressure-Drop Sensor) on GA-001
- EU-002 (SOFC Stack (Efficiency)) on EU-001
- EU-004 (Gas Engine (Thermal Eff.)) on EU-003
- GA-002 (Gasifier Vessel (Pressure)) on GA-001
- GA-004 (Air/Steam Injection (Temp)) on GA-003
- GC-002 (Primary Cyclone (ΔP)) on GC-001
- GC-005 (Quench Tower (Water)) on GC-004
- GC-011 (Bag Filter (ΔP)) on GC-010
- GC-014 (Gas Blower (Pressure)) on GC-013
- HB-002 (WGS Reactor HTS (CO Conv.)) on HB-001
- HB-007 (PSA Unit (H₂ Recovery)) on HB-006
- HB-008 (PSA Unit (Pressure)) on HB-006

## Registry rows that are software or cloud services (drawn as a rack placeholder, not as hardware)

- AI-006: MQTT broker (software)
- AI-010: cloud service (off-site)
- AI-011: database (software)
- AI-012: AI model server (software on a server)
- AI-013: digital twin engine (software)
- AI-014: orchestration controller (software)

## Per-item size basis

| ID | Name | Recipe | Size (w x d x h, m) | Basis |
|---|---|---|---|---|
| FE-001 | MSW Receiving Hopper | hopper | 2.00 x 2.00 x 2.00 | assumed |
| FE-002 | Magnetic & Eddy Current Separator | separator | 1.60 x 1.00 x 1.20 | assumed |
| FE-003 | Weighing Conveyor | conveyor | 3.00 x 0.40 x 0.35 | registry |
| FE-004 | Shredder / Size Reducer | shredder | 1.40 x 1.00 x 1.20 | estimate |
| FE-005 | Feed Dryer (Rotary/Belt) | dryer | 3.00 x 1.00 x 1.10 | assumed |
| FE-006 | Moisture Analyser | analyser | 0.60 x 0.50 x 0.90 | assumed |
| FE-007 | Feed Screw / Ram Feeder | screw | 2.00 x 0.50 x 0.60 | assumed |
| FE-008 | Air-lock / Rotary Valve | rotary_valve | 0.50 x 0.50 x 0.50 | assumed |
| GA-001 | Gasifier Vessel (Reactor) | reactor | 0.60 x 0.60 x 4.00 | registry |
| GA-002 | Gasifier Vessel (Pressure) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| GA-003 | Air/Steam Injection (Flow) | skid | 1.20 x 0.80 x 1.00 | assumed |
| GA-004 | Air/Steam Injection (Temp) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| GA-005 | Bed Drain / Ash Discharge System | drain | 0.70 x 0.70 x 0.90 | assumed |
| GA-006 | Char / Ash Conveyor | screw | 2.00 x 0.50 x 0.60 | assumed |
| GA-007 | Char Collection Bin | bin | 1.00 x 1.00 x 1.00 | assumed |
| GA-008 | Carbon Black Recovery & Classification Unit | process_unit | 1.60 x 1.20 x 1.80 | assumed |
| GA-009 | Ash Aggregate Processing & Packaging Unit | process_unit | 1.60 x 1.20 x 1.80 | assumed |
| GA-010 | Carbon Black Packaging & Storage Silo | silo | 0.90 x 0.90 x 2.20 | assumed |
| GC-001 | Primary Cyclone (Temp) | cyclone | 0.40 x 0.40 x 1.50 | assumed |
| GC-002 | Primary Cyclone (ΔP) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| GC-003 | Secondary Cyclone | cyclone | 0.50 x 0.50 x 1.40 | estimate |
| GC-004 | Quench Tower (Temp) | tower | 0.40 x 0.40 x 3.00 | registry |
| GC-005 | Quench Tower (Water) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| GC-006 | Tar Removal Unit | adsorber | 0.35 x 0.35 x 1.50 | registry |
| GC-007 | Wet Scrubber (Tar) | tower | 0.30 x 0.30 x 2.00 | assumed |
| GC-008 | Wet Scrubber (H₂S) | tower | 0.30 x 0.30 x 2.00 | registry |
| GC-009 | HCl Scrubber (Alkaline) | tower | 0.30 x 0.30 x 2.00 | assumed |
| GC-010 | Bag Filter (Dust) | bag_filter | 1.00 x 0.80 x 1.80 | estimate |
| GC-011 | Bag Filter (ΔP) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| GC-012 | Activated Carbon Filter | adsorber | 0.28 x 0.28 x 0.83 | estimate |
| GC-013 | Gas Blower / ID Fan (Flow) | blower | 0.80 x 0.50 x 0.60 | assumed |
| GC-014 | Gas Blower (Pressure) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| GC-015 | Condensate Tank | tank_h | 1.20 x 0.70 x 0.70 | assumed |
| SA-001 | Gas Analyser (H₂) | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-002 | Gas Analyser (CO) | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-003 | Gas Analyser (CO₂) | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-004 | Gas Analyser (CH₄) | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-005 | Gas Analyser (N₂) | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-006 | Gas Calorimeter / LHV | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-007 | Tar Sampling Port | instrument | 0.30 x 0.30 x 0.50 | assumed |
| SA-008 | H₂S / COS Analyser | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-009 | Dust / Particulate Monitor | analyser | 0.60 x 0.50 x 0.90 | assumed |
| SA-010 | Gas Flow Meter (Clean) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| SA-011 | Gas Temperature Sensor | instrument | 0.30 x 0.30 x 0.50 | assumed |
| SA-012 | Gas Pressure Sensor | instrument | 0.30 x 0.30 x 0.50 | assumed |
| HB-001 | WGS Reactor HTS (Temp) | wgs_reactor | 0.50 x 0.50 x 2.00 | assumed |
| HB-002 | WGS Reactor HTS (CO Conv.) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| HB-003 | Heat Exchanger (WGS) | hx | 1.80 x 0.50 x 0.50 | assumed |
| HB-004 | WGS Reactor LTS | wgs_reactor | 0.50 x 0.50 x 2.00 | assumed |
| HB-005 | Steam Generator (WGS) | vessel_h | 1.20 x 0.80 x 0.80 | assumed |
| HB-006 | PSA Unit (H₂ Purity) | psa | 2.00 x 0.60 x 2.20 | estimate |
| HB-007 | PSA Unit (H₂ Recovery) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| HB-008 | PSA Unit (Pressure) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| HB-009 | PSA Tail Gas Handler | vessel_v | 0.50 x 0.50 x 1.50 | assumed |
| HB-010 | Membrane Separator | membrane | 1.40 x 0.50 x 0.40 | estimate |
| HB-011 | Electrolyser (Green H₂) — Auxiliary/Optional | container | 2.40 x 1.20 x 2.00 | assumed |
| HB-012 | H₂ Compressor | compressor | 1.60 x 0.80 x 1.20 | estimate |
| HB-013 | H₂ Storage Vessel | bank | 2.40 x 0.90 x 0.50 | estimate |
| HB-014 | LOHC Hydrogenation / Loading Reactor | vessel_v | 0.68 x 0.68 x 1.37 | estimate |
| HB-015 | LOHC Storage Tank (Lean/Rich Oil) | tank_h | 2.19 x 0.95 x 1.42 | estimate |
| HB-016 | LOHC Dehydrogenation Unit — Auxiliary/Optional | vessel_v | 0.50 x 0.50 x 1.50 | assumed |
| HB-017 | H₂ Purification (Post-LOHC Dehydrogenation) | adsorber | 0.35 x 0.35 x 1.50 | assumed |
| HB-018 | H₂ Dispensing Station (Mobility/FCEV Refuelling) | dispenser | 0.80 x 0.60 x 2.00 | assumed |
| EU-001 | SOFC Stack (Temp) | cabinet | 1.00 x 0.80 x 1.80 | assumed |
| EU-002 | SOFC Stack (Efficiency) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| EU-003 | Gas Engine / Genset (Power) | genset | 3.00 x 1.20 x 1.80 | assumed |
| EU-004 | Gas Engine (Thermal Eff.) | instrument | 0.30 x 0.30 x 0.50 | assumed |
| EU-005 | Microturbine | microturbine | 1.50 x 0.80 x 1.60 | assumed |
| EU-006 | H₂ Fuel Cell (Stationary) | cabinet | 1.00 x 0.80 x 1.80 | assumed |
| EU-007 | Flare / Emergency Burner | flare | 0.40 x 0.40 x 6.00 | assumed |
| EU-008 | Cooling Tower | cooling_tower | 1.60 x 1.60 x 2.40 | assumed |
| EU-009 | Electrical Metering (Grid) | meter | 0.60 x 0.30 x 0.90 | assumed |
| EU-010 | UPS / Battery Buffer | cabinet | 1.00 x 0.80 x 1.80 | assumed |
| EU-011 | Heat Recovery Unit | hx | 1.80 x 0.50 x 0.50 | assumed |
| EU-012 | District Heating HX | plate_hx | 0.60 x 0.40 x 1.00 | assumed |
| EU-013 | Thermal Energy Metering (District Heat) | meter | 0.60 x 0.30 x 0.90 | assumed |
| AI-001 | Weather Station | mast | 0.30 x 0.30 x 4.00 | assumed |
| AI-002 | Camera / Vision System | pole | 0.30 x 0.30 x 3.00 | assumed |
| AI-003 | Bed Pressure-Drop Sensor | instrument | 0.30 x 0.30 x 0.50 | assumed |
| AI-004 | PLC (Main Control) | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-005 | OPC-UA Gateway | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-006 | MQTT Broker | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-007 | DCS / SCADA Server | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-008 | Edge Computing Server | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-009 | Cybersecurity Firewall (ICS) | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-010 | Cloud IoT Hub | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-011 | Time-Series Database | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-012 | AI Model Server (MPC/RL) | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-013 | Digital Twin Engine | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-014 | Multi-Module Orchestration Controller | rack | 0.60 x 0.90 x 2.00 | assumed |
| AI-015 | RFNBO Compliance & Guarantee-of-Origin Monitor — Auxiliary/Optional | workstation | 1.20 x 0.70 x 1.10 | assumed |

## Missing vendor dimensions and unverified connections

- Vendor dimensions are missing for the 76 `assumed` items and the footprints of the 10 `estimate` items.
- All connections between items are unverified (none in the registry).
