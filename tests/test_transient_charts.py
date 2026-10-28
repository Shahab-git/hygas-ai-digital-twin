"""Chart conventions of the Transient What-If tab (python/ui_transient_charts.py): presentation only, no simulation, no Streamlit run.

Payloads here are synthetic exponentials pushed through sim.response_table (a pure function), so the tests need no child process, no database
and no network, and cost about a second in total.
"""
import itertools
import json
import math
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from python import ui_transient_charts as ch, ui_transient_sim as sim, ui_transient_tab as tab

KEYS = [q[0] for q in sim.PLOT_QUANTITIES]


def _payload(dt=30, duration_min=60, step_min=5, tau_s=300.0, taus=None):
    """A synthetic result: every plotted quantity relaxes exponentially from 10 to 20 (each with its own tau when `taus` is given)."""
    step_s, duration_s = step_min * 60, duration_min * 60
    taus = taus or {}
    series = []
    for t in range(0, duration_s + 1, dt):
        row = {"t_s": t}
        for key in KEYS:
            lag = taus.get(key, tau_s)
            row[key] = 10.0 if t < step_s else 20.0 - 10.0 * math.exp(-(t - step_s) / lag)
        series.append(row)
    final = {key: 20.0 for key in KEYS}
    return {"params": {"step_s": step_s, "duration_s": duration_s, "dt_s": dt}, "series": series,
            "response": sim.response_table(series, step_s, final, dt)}


def _normalised(payload, key="ga001_dry_flow_nm3_h"):
    _absolute, normalised, step_min, duration_min = ch.long_frames(payload)
    row = next(r for r in payload["response"] if r["key"] == key)
    return ch.normalised_chart(normalised, step_min, duration_min, row).to_dict(), normalised, row


def _layers(spec):
    return spec["layer"]


def _mark(layer):
    return layer["mark"] if isinstance(layer["mark"], dict) else {"type": layer["mark"]}


# ------------------------------------------------------------------------------------------------ distinct series (C)
def _lab(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    x = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _hue(hex_colour):
    import colorsys
    return colorsys.rgb_to_hls(*(int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)))[0] * 360


def test_every_plotted_quantity_has_a_distinct_colour_dash_and_shape():
    assert set(ch.SERIES_STYLE) == set(KEYS)
    colours = [ch.SERIES_STYLE[k]["color"] for k in KEYS]
    dashes = [tuple(ch.SERIES_STYLE[k]["dash"]) for k in KEYS]
    shapes = [ch.SERIES_STYLE[k]["shape"] for k in KEYS]
    assert len(set(colours)) == len(set(dashes)) == len(set(shapes)) == len(KEYS), (colours, dashes, shapes)


def test_the_palette_is_not_several_blues_and_every_pair_of_colours_is_far_apart():
    colours = [ch.SERIES_STYLE[k]["color"] for k in KEYS]
    assert sum(190 <= _hue(c) <= 260 for c in colours) <= 1, "the colours must not be several blues"
    nearest = min(math.dist(_lab(a), _lab(b)) for a, b in itertools.combinations(colours, 2))
    assert nearest >= 25, nearest                                   # CIE-Lab distance of the two closest colours (ours: 33)


def test_normalised_chart_carries_the_style_of_every_series_in_its_scales_and_point_layers():
    spec, normalised, _row = _normalised(_payload())
    keys = [k for k in KEYS if k in set(normalised["key"])]
    assert len(keys) == len(KEYS)
    lines = next(layer for layer in _layers(spec) if _mark(layer)["type"] == "line")
    scales = {c: lines["encoding"][c]["scale"] for c in ("color", "strokeDash")}
    names = [ch.pretty(q[1]) for q in sim.PLOT_QUANTITIES]
    for channel, field in (("color", "color"), ("strokeDash", "dash")):
        assert scales[channel]["domain"] == names
        assert scales[channel]["range"] == [ch.SERIES_STYLE[k][field] for k in keys]
        assert len({json.dumps(v) for v in scales[channel]["range"]}) == len(keys)
    points = [layer for layer in _layers(spec) if _mark(layer)["type"] == "point"]
    assert [(_mark(p)["color"], _mark(p)["shape"]) for p in points] == [(ch.SERIES_STYLE[k]["color"], ch.SERIES_STYLE[k]["shape"]) for k in keys]
    assert len({_mark(p)["shape"] for p in points}) == len(keys)


def test_the_same_quantity_has_the_same_colour_and_dash_in_the_absolute_panels():
    payload = _payload()
    absolute, _n, step_min, duration_min = ch.long_frames(payload)
    for key, panel in zip(KEYS, ch.absolute_panels(absolute, step_min, duration_min)):
        spec = panel.to_dict()
        line = next(layer for layer in _layers(spec) if _mark(layer)["type"] == "line")
        style = ch.SERIES_STYLE[key]
        assert _mark(line)["color"] == style["color"] and _mark(line)["strokeDash"] == style["dash"], key
        point = next(layer for layer in _layers(spec) if _mark(layer)["type"] == "point")
        assert _mark(point)["shape"] == style["shape"], key


def test_the_legend_is_interactive_and_sits_outside_the_plot():
    spec, _n, _row = _normalised(_payload())
    params = list(spec.get("params", [])) + [p for layer in _layers(spec) for p in layer.get("params", [])]       # Altair hoists them to the top
    assert len(params) == 1 and params[0]["bind"] == "legend" and params[0]["select"]["fields"] == ["quantity"]
    lines = next(layer for layer in _layers(spec) if _mark(layer)["type"] == "line")
    assert lines["encoding"]["color"]["legend"]["orient"] == "right"
    assert lines["encoding"]["opacity"]["condition"]["param"] == params[0]["name"]


# ------------------------------------------------------------------------------------------------ size and layout (B)
def test_charts_are_full_width_and_tall_enough_one_per_row():
    payload = _payload()
    absolute, _n, step_min, duration_min = ch.long_frames(payload)
    panels = [p.to_dict() for p in ch.absolute_panels(absolute, step_min, duration_min)]
    spec, _normalised_frame, _row = _normalised(payload)
    assert len(panels) == len(KEYS), "one panel per quantity"
    assert spec["width"] == "container" and all(p["width"] == "container" for p in panels)
    assert spec["height"] >= 360
    assert sum(p["height"] for p in panels) >= 320 and all(p["height"] >= 150 for p in panels)
    assert all("facet" not in p and "hconcat" not in p and "vconcat" not in p and "columns" not in p for p in panels + [spec])   # no side by side


def test_each_absolute_panel_is_one_quantity_with_its_own_y_scale_and_no_dual_axis():
    payload = _payload()
    absolute, _n, step_min, duration_min = ch.long_frames(payload)
    for key, panel in zip(KEYS, ch.absolute_panels(absolute, step_min, duration_min)):
        spec = panel.to_dict()
        frames = [d for d in spec["datasets"].values()]
        quantities = {row["quantity"] for frame in frames for row in frame if "quantity" in row}
        assert len(quantities) == 1, (key, quantities)
        axes = [layer["encoding"]["y"].get("axis", {}) for layer in _layers(spec) if "y" in layer.get("encoding", {}) and "axis" in layer["encoding"]["y"]]
        assert "orient" not in json.dumps(axes), "no second (dual) axis"


# ----------------------------------------------------------------------------------------------------- time axis (D)
@pytest.mark.parametrize("duration,step", [(5, 1), (10, 1), (30, 1), (31, 5), (60, 5), (61, 10), (120, 10), (121, 15), (180, 15), (181, 30), (240, 30)])
def test_tick_step_follows_the_duration(duration, step):
    assert ch.tick_step_min(duration) == step
    assert ch.tick_values(duration) == list(range(0, duration + 1, step))


def test_ticks_never_crowd_the_axis_and_runs_up_to_two_hours_use_at_most_ten_minutes():
    for duration in range(1, 241):
        assert len(ch.tick_values(duration)) <= 32, duration              # at most ~30 labels, which fit a normal chart width
        if duration <= 120:
            assert ch.tick_step_min(duration) <= 10, duration


@pytest.mark.parametrize("dt,duration", [(10, 30), (15, 30), (30, 120), (60, 240)])
def test_the_axis_spec_carries_the_ticks_title_and_a_labelled_step_rule(dt, duration):
    spec, _n, _row = _normalised(_payload(dt=dt, duration_min=duration, step_min=5))
    lines = next(layer for layer in _layers(spec) if _mark(layer)["type"] == "line")
    x = lines["encoding"]["x"]
    assert x["axis"]["values"] == ch.tick_values(duration) and x["title"] == "time since start, min"
    assert x["scale"]["domain"] == [0, duration]
    texts = [row["text"] for d in spec["datasets"].values() for row in d if "text" in row]
    assert "step at 5 min" in texts


# ------------------------------------------------------------------------------------------- response-time markers (E)
def _marker_names(spec):
    return {layer["name"] for layer in _layers(spec) if layer.get("name", "").endswith("_marker")}


def test_markers_are_drawn_for_resolved_times_at_the_table_values():
    payload = _payload(dt=30, tau_s=300.0)                          # t63 ~ 300 s, t95 ~ 900 s, both far above 2 dt = 60 s
    spec, _frame, row = _normalised(payload)
    assert _marker_names(spec) == {"t63_marker", "t95_marker"}
    frame = ch.marker_frame(row, payload["params"]["step_s"] / 60.0)
    table = tab._response_frame(payload)
    shown = table.iloc[0]
    for which, column in (("t63", "t63 [s]"), ("t95", "t95 [s]")):
        minute = float(frame[frame["which"] == which]["minute"].iloc[0])
        assert round(minute * 60 - payload["params"]["step_s"]) == int(shown[column]), (which, minute, shown[column])
    texts = [r["which"] for d in spec["datasets"].values() for r in d if "which" in r]
    assert sorted(texts) == ["t63", "t95"]


def test_an_unresolved_time_gets_no_marker_and_the_table_label():
    payload = _payload(dt=30, taus={"ga001_dry_flow_nm3_h": 20.0})  # t63 ~ 20 s and t95 ~ 60 s, both under 2 dt = 60 s ... t95 borderline
    row = next(r for r in payload["response"] if r["key"] == "ga001_dry_flow_nm3_h")
    assert row["t63_unresolved"] is True
    spec, _frame, _row = _normalised(payload)
    assert "t63_marker" not in _marker_names(spec)
    assert ch.time_cell(row, "t63") == (sim.UNRESOLVED_LABEL, None)
    assert tab._response_frame(payload).iloc[0]["t63 [s]"] == sim.UNRESOLVED_LABEL
    assert "t63" not in {r["which"] for d in spec["datasets"].values() for r in d if "which" in r}


def test_nothing_is_marked_when_both_times_are_unresolved_or_not_reached():
    fast = _payload(dt=120, duration_min=240, step_min=6, taus={"ga001_dry_flow_nm3_h": 20.0})        # lag far below dt: both unresolved
    spec, _f, row = _normalised(fast)
    assert row["t63_unresolved"] and row["t95_unresolved"] and _marker_names(spec) == set()
    slow = _payload(dt=30, duration_min=10, step_min=5, taus={"ga001_dry_flow_nm3_h": 5000.0})         # 5 min of a 5000 s lag: 63 % never reached
    spec, _f, row = _normalised(slow)
    assert row["t63"] is None and ch.time_cell(row, "t63") == ("not reached in this run", None) and _marker_names(spec) == set()


def test_the_marker_wording_is_the_response_tables_wording_for_every_row():
    payload = _payload(dt=30, duration_min=60, taus={"CO_pct_dry": 15.0, "H2_pct_dry": 100.0, "N2_pct_dry": 3000.0})
    table = tab._response_frame(payload)
    for i, row in enumerate(payload["response"]):
        for which, column in (("t63", "t63 [s]"), ("t95", "t95 [s]")):
            assert ch.time_cell(row, which)[0] == table.iloc[i][column], (row["key"], which)


def test_guide_lines_sit_at_63_2_and_95_percent_and_are_labelled():
    spec, _n, _row = _normalised(_payload())
    values = sorted(r["pct"] for d in spec["datasets"].values() for r in d if "pct" in r and "text" not in r and "quantity" not in r)
    assert {0.0, 63.2, 95.0, 100.0} <= set(values)
    texts = [r["text"] for d in spec["datasets"].values() for r in d if "text" in r]
    assert "63.2 %" in texts and "95 %" in texts
