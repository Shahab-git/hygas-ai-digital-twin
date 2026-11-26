# RFI2 impact per registry item (2026-11-26)

Project reading of DOK-ING's RFI2 replies (`data/dokink_rfi_answers.md`, end of file) against the 91 registry items. Assumed, not DOK-ING-confirmed. Display/documentation only: the registry is not edited and no model reads `data/rfi2_item_impact.json`.


## 1 Remove / not applicable (3)

| ID | Name | Why |
|---|---|---|
| FE-005 | Feed Dryer (Rotary/Belt) | RFI2 #5: the feed is not dried; up to 15% moisture goes straight into the reactor. |
| GA-003 | Air/Steam Injection (Flow) | RFI2 #1,#4: no air or steam is added to the reactor (0 Nm3/h, 0 kg/h). |
| GA-004 | Air/Steam Injection (Temp) | RFI2 #4,#10: no injected air or steam, so no injection temperature or preheat. |

## 2 Redefine (10)

| ID | Name | Why |
|---|---|---|
| FE-006 | Moisture Analyser | RFI2 #5: moisture range is up to 15%, not the assumed 10%; the dryer outlet reading no longer applies. |
| GA-001 | Gasifier Vessel (Reactor) | RFI2 #1,#3: tubular reactor heated electrically from outside, no carrier loop, no air reactor, no added agent. The twin models an air-blown carrier reactor. |
| GA-005 | Bed Drain / Ash Discharge System | RFI2 #9: ash is separated at the reactor exit and removed by a spindle into a separate container, not a bed drain. |
| GA-006 | Char / Ash Conveyor | RFI2 #8: char/carbon black is 40 to 50% of the feed (17 to 21 kg/h), about 10 times the twin's 1.7 to 2 kg/h. |
| GA-007 | Char Collection Bin | RFI2 #8: bin sizing depends on the 17 to 21 kg/h char flow. |
| GA-008 | Carbon Black Recovery & Classification Unit | RFI2 #8: registry capacity 3 kg/h against 17 to 21 kg/h expected. |
| GA-009 | Ash Aggregate Processing & Packaging Unit | RFI2 #8,#9: ash and carbon-black flows differ; it is unclear whether char includes ash. |
| GA-010 | Carbon Black Packaging & Storage Silo | RFI2 #8: silo and packaging sized for 2 kg/h class flow. |
| HB-005 | Steam Generator (WGS) | RFI2 #4: no steam goes to the reactor; its role (steam for the gasifier) disappears. It may remain only if WGS needs steam. |
| AI-012 | AI Model Server (MPC/RL) | MPC/RL setpoints use equivalence ratio and steam-to-feed as manipulated variables, which no longer exist. |

## 3 Inputs change (30)

| ID | Name | Why |
|---|---|---|
| GC-001 | Primary Cyclone (Temp) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-003 | Secondary Cyclone | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-004 | Quench Tower (Temp) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-007 | Wet Scrubber (Tar) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-008 | Wet Scrubber (H₂S) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-009 | HCl Scrubber (Alkaline) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-013 | Gas Blower / ID Fan (Flow) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| GC-015 | Condensate Tank | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-001 | Gas Analyser (H₂) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-002 | Gas Analyser (CO) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-003 | Gas Analyser (CO₂) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-004 | Gas Analyser (CH₄) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-005 | Gas Analyser (N₂) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-006 | Gas Calorimeter / LHV | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| SA-010 | Gas Flow Meter (Clean) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| HB-001 | WGS Reactor HTS (Temp) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| HB-003 | Heat Exchanger (WGS) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| HB-004 | WGS Reactor LTS | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| HB-006 | PSA Unit (H₂ Purity) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. Note RFI2 #7: DOK-ING does not yet separate hydrogen by PSA; this item is the planned chain, not existing equipment. |
| HB-009 | PSA Tail Gas Handler | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. Note RFI2 #7: DOK-ING does not yet separate hydrogen by PSA; this item is the planned chain, not existing equipment. |
| HB-010 | Membrane Separator | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. Note RFI2 #7: DOK-ING does not yet separate hydrogen by PSA; this item is the planned chain, not existing equipment. |
| HB-012 | H₂ Compressor | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| HB-013 | H₂ Storage Vessel | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| HB-018 | H₂ Dispensing Station (Mobility/FCEV Refuelling) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| EU-007 | Flare / Emergency Burner | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| EU-008 | Cooling Tower | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| EU-009 | Electrical Metering (Grid) | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| EU-010 | UPS / Battery Buffer | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| AI-007 | DCS / SCADA Server | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |
| AI-011 | Time-Series Database | Its live values move with the air ratio, steam ratio or carbon conversion; with no agent and a new char split the gas and flows change. The item itself stays. |

## 4 Check text (8)

| ID | Name | Why |
|---|---|---|
| GC-006 | Tar Removal Unit | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. |
| GC-010 | Bag Filter (Dust) | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. |
| HB-007 | PSA Unit (H₂ Recovery) | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. Note RFI2 #7: DOK-ING does not yet separate hydrogen by PSA; this item is the planned chain, not existing equipment. |
| HB-008 | PSA Unit (Pressure) | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. Note RFI2 #7: DOK-ING does not yet separate hydrogen by PSA; this item is the planned chain, not existing equipment. |
| HB-011 | Electrolyser (Green H₂) — Auxiliary/Optional | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. |
| HB-014 | LOHC Hydrogenation / Loading Reactor | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. |
| HB-017 | H₂ Purification (Post-LOHC Dehydrogenation) | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. |
| AI-015 | RFNBO Compliance & Guarantee-of-Origin Monitor — Auxiliary/Optional | No live value moves, but its registry text mentions air, steam, preheat, drying, char/ash or PSA. Read and confirm. |

## 5 Unchanged (34)

GA-002, GC-002, GC-005, GC-011, GC-012, GC-014, SA-007, SA-008, SA-009, SA-011, SA-012, HB-002, HB-015, HB-016, EU-001, EU-002, EU-003, EU-004, EU-005, EU-006, EU-011, EU-012, EU-013, AI-001, AI-002, AI-003, AI-004, AI-005, AI-006, AI-008, AI-009, AI-010, AI-013, AI-014


## 5 Unchanged (feed only) (6)

FE-001, FE-002, FE-003, FE-004, FE-007, FE-008

