# Measurement replay schema (data-replacement layer, step 1)

Defined by `python/measurement_replay.py`. Offline, file-based; no live feed exists in this task.

## Long format, one reading per row

| column | meaning | rule |
|---|---|---|
| `timestamp` | when the value was valid | UTC ISO-8601 with a zone (`2026-10-30T12:00:00Z`). A naive timestamp is refused (`bad_timestamp`). |
| `tag` | what was measured | `UNIT.quantity`, see below. |
| `value` | the reading | a finite number (`bad_value` otherwise). |
| `unit` | its unit | compared with the tag's unit after `data_precedence.normalise_unit` (`Nm³/h` = `Nm3/h`, `°C` = `degC`). A different unit is `unit_mismatch`; nothing is converted. |
| `quality` | the sender's judgement | `good` / `suspect` / `bad` (anything else: `bad_quality_label`). |
| `source` | where it came from | free text (instrument, lab, export file). |

CSV (header row with at least these six columns, extra columns ignored) or JSON (a list of objects, or `{"readings": [...]}`). A file without the six columns is refused (`ReplayFormatError`), not guessed.

## Tag convention

`UNIT.quantity_unit`: the equipment id that owns the quantity (`GA-001`, `HB-012`, `SA-001`, `GA-003`), a dot, then the quantity with a unit suffix. Examples: `GA-001.T_gasifier_C`, `GA-001.ER`, `HB-012.h2_kg_h`, `SA-001.H2_vol_pct`, `GA-003.air_flow_Nm3_h`. Parameter tags are the `tag` column of `parameter_table.build_table()`; sensor tags are listed in `measurement_replay._SENSORS` (each with its unit, a physical kind and the snapshot entry the model publishes for it, or none).

## What validation reports (never drops a row)

| flag | blocking? | when |
|---|---|---|
| `bad_timestamp`, `bad_value`, `bad_quality_label` | yes | the field cannot be parsed |
| `unit_mismatch` | yes | unit differs from the tag's |
| `non_monotonic_time` | yes | the timestamp is earlier than an earlier-arrived reading of the same tag |
| `duplicate` | yes | a second reading of the same tag at the same instant (identical or conflicting value, said in the issue) |
| `physically_impossible` | yes | outside an identity limit of the quantity (a percentage outside 0-100, a negative flow, below absolute zero); these are not plant numbers |
| `unknown_tag` | no | neither a parameter-table tag nor a known sensor tag |
| `outside_assumed_range` | no | outside the parameter table's range; informational, because a reading outside an Assumed range is what measuring is for |
| `quality_suspect`, `quality_bad` | no (the quality itself blocks) | the sender's label |

`data_precedence` lets a Measured value take part only if `quality == good` and no blocking flag is present.

## Live-feed interface (not implemented here)

```python
class MeasurementSource:
    def read(self, since=None):   # raw readings strictly after `since` (UTC ISO or datetime), in arrival order; must not write
        ...
```

`InMemorySource` and `FileSource` are the only implementations. A later task would implement it for a Supabase measurement table or a SCADA export (see `docs/data_replacement_layer.md`, "Needs your decision").
