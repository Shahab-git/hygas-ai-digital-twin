# Blender plant model (stages 1 to 4): what it is and what it is not

A SCHEMATIC ENGINEERING MODEL of the DOK-ING MSW-H2 1 tpd plant, not vendor CAD, not a P&ID, not a surveyed layout, not to scale.
Simulated model state, no plant data. Files: `blender/generate_plant.py` (builds, validates, exports), `blender/plant_layout.py`
(layout and sizes, pure Python), `blender/plant_links.py` (links and routing, pure Python), `assets/plant_model.glb` (what the 3D tab shows).

## Rebuild

```
pip install bpy==5.3.0          # or run inside Blender 5.3
python blender/plant_links.py --write        # only if the engine's dependency graph changed (a test compares it)
python blender/plant_layout.py --write-docs  # regenerates docs/blender_plant_assumptions.md
python blender/generate_plant.py --out build/blender --blend --views isometric,aerial --samples 64 --res 1920x1080
cp build/blender/plant.glb assets/plant_model.glb
cd web3d && npm run build                    # only if web3d/src/main.js changed
```
Outputs in the `--out` folder: `plant.glb`, `HYGAS_AI_Industrial_Plant.blend`, `equipment_mapping.json`, `validation_report.json`, `render_<view>.png`.

## What is drawn

- All 91 registry rows, one assembly each, named by the registry ID, with metadata (equipment_id, name, category, geometry_status, data_provenance, source_registry, process_zone, size_basis, size_note, placement). 12 rows are drawn as an instrument tag on a host unit and 6 software/cloud rows as a rack placeholder (see `docs/blender_plant_assumptions.md`).
- Sizes: only the 5 registry-stated sizes are registry values; 10 are estimated around a registry count or volume; 76 are assumed representative sizes.
- Detail (assumed, illustrative): manways, lifting lugs, cladding bands on vessels, level gauges, idler rollers.
- Access structure (assumed, no DOK-ING drawing): ladders with cages on tall vertical units, stair + platform at FE-001, GA-001, GC-004, EU-008, handrails, pipe support posts.

## Links (piping): only what the model itself documents

The registry has NO connection data. The only links drawn are the 43 dependencies between physical items in the live engine's own same-cycle dependency graph
(`depends_on` in `python/tab1_integration.build_engine()`), stored in `data/plant_links.json` and compared with the engine by `tests/test_blender_links.py`.
A link A -> B means the model of B reads a value computed by the model of A. It does NOT say which medium flows, and it is NOT a verified pipe or conveyor route.
Routing (straight low run between lane neighbours, otherwise an overhead orthogonal run above the items it passes) and the pipe diameter (120 mm outer) are assumptions.
Pairs of items that are not listed are NOT connected in the model: nothing was inferred from the picture or from process-engineering habit. Instruments, analysers, meters, software items and lagged couplings are not links.

| From | To |
|---|---|
| EU-004 Gas Engine (Thermal Eff.) | EU-012 District Heating HX |
| EU-005 Microturbine | EU-011 Heat Recovery Unit |
| EU-011 Heat Recovery Unit | EU-012 District Heating HX |
| FE-001 MSW Receiving Hopper | FE-002 Magnetic & Eddy Current Separator |
| FE-002 Magnetic & Eddy Current Separator | FE-003 Weighing Conveyor |
| FE-003 Weighing Conveyor | FE-004 Shredder / Size Reducer |
| FE-004 Shredder / Size Reducer | FE-005 Feed Dryer (Rotary/Belt) |
| FE-005 Feed Dryer (Rotary/Belt) | FE-007 Feed Screw / Ram Feeder |
| FE-005 Feed Dryer (Rotary/Belt) | GA-001 Gasifier Vessel (Reactor) |
| FE-007 Feed Screw / Ram Feeder | FE-008 Air-lock / Rotary Valve |
| GA-001 Gasifier Vessel (Reactor) | GC-001 Primary Cyclone (Temp) |
| GA-001 Gasifier Vessel (Reactor) | GC-004 Quench Tower (Temp) |
| GC-001 Primary Cyclone (Temp) | GC-003 Secondary Cyclone |
| GC-004 Quench Tower (Temp) | EU-008 Cooling Tower |
| GC-004 Quench Tower (Temp) | GC-007 Wet Scrubber (Tar) |
| GC-004 Quench Tower (Temp) | GC-008 Wet Scrubber (H₂S) |
| GC-004 Quench Tower (Temp) | GC-009 HCl Scrubber (Alkaline) |
| GC-004 Quench Tower (Temp) | GC-013 Gas Blower / ID Fan (Flow) |
| GC-004 Quench Tower (Temp) | GC-015 Condensate Tank |
| GC-006 Tar Removal Unit | GC-007 Wet Scrubber (Tar) |
| GC-007 Wet Scrubber (Tar) | GC-015 Condensate Tank |
| GC-008 Wet Scrubber (H₂S) | GC-012 Activated Carbon Filter |
| GC-008 Wet Scrubber (H₂S) | GC-015 Condensate Tank |
| GC-009 HCl Scrubber (Alkaline) | GC-015 Condensate Tank |
| GC-013 Gas Blower / ID Fan (Flow) | HB-001 WGS Reactor HTS (Temp) |
| GC-013 Gas Blower / ID Fan (Flow) | HB-003 Heat Exchanger (WGS) |
| GC-013 Gas Blower / ID Fan (Flow) | HB-005 Steam Generator (WGS) |
| GC-013 Gas Blower / ID Fan (Flow) | HB-009 PSA Tail Gas Handler |
| HB-001 WGS Reactor HTS (Temp) | HB-004 WGS Reactor LTS |
| HB-001 WGS Reactor HTS (Temp) | HB-005 Steam Generator (WGS) |
| HB-003 Heat Exchanger (WGS) | EU-008 Cooling Tower |
| HB-005 Steam Generator (WGS) | GA-001 Gasifier Vessel (Reactor) |
| HB-005 Steam Generator (WGS) | HB-003 Heat Exchanger (WGS) |
| HB-006 PSA Unit (H₂ Purity) | HB-009 PSA Tail Gas Handler |
| HB-006 PSA Unit (H₂ Purity) | HB-012 H₂ Compressor |
| HB-006 PSA Unit (H₂ Purity) | HB-014 LOHC Hydrogenation / Loading Reactor |
| HB-009 PSA Tail Gas Handler | EU-007 Flare / Emergency Burner |
| HB-009 PSA Tail Gas Handler | HB-012 H₂ Compressor |
| HB-012 H₂ Compressor | EU-008 Cooling Tower |
| HB-012 H₂ Compressor | HB-013 H₂ Storage Vessel |
| HB-014 LOHC Hydrogenation / Loading Reactor | HB-015 LOHC Storage Tank (Lean/Rich Oil) |
| HB-015 LOHC Storage Tank (Lean/Rich Oil) | HB-016 LOHC Dehydrogenation Unit — Auxiliary/Optional |
| HB-016 LOHC Dehydrogenation Unit — Auxiliary/Optional | HB-017 H₂ Purification (Post-LOHC Dehydrogenation) |

## Process flow mode (3D Plant tab, Blender view)

"Process flow" highlights the links. With an item selected, blue = what feeds it (all upstream links, transitively), orange = what it feeds (downstream), the rest dimmed; moving dots show the direction of the dependency, not a measured flow.

## Not verified / not done

- No DOK-ING drawing, P&ID or vendor dimension was used; the layout is not the real plant.
- GitHub Actions, Python 3.11/3.12 and the Streamlit Cloud deployment were not run for this stage.
- Process flow animation is a visual aid for the model's dependency graph only.
