"""
Chart specs of the "Transient What-If" tab (Tab 11): PRESENTATION ONLY.

Pure Altair + pandas on a result payload that python/ui_transient_sim.py already produced. No Streamlit call, no data access, no simulation,
no number computed here that the response table does not already show: the t63 / t95 markers come from the same table values
(time_cell), so a marker can never disagree with the table.

Conventions (docs/dynamics_v0.md, "Using the what-if tab"):
  * every plotted quantity has ONE fixed colour, ONE fixed line dash and ONE fixed point shape (SERIES_STYLE), used in every chart and in the
    legend; the palette has a single blue and a minimum pairwise colour distance, so the chart also works for colour-blind readers and in
    greyscale print (the dash and the shape still tell the series apart);
  * the time axis starts at 0, is titled with its unit and its ticks follow the duration (tick_step_min);
  * the step is a thin black rule labelled with its time; the old / new steady states are grey / red dashed rules.
"""
import altair as alt
import pandas as pd

from . import ui_transient_sim as sim

ABS_PANEL_HEIGHT = 170          # plot height of ONE absolute-unit panel [px]; the 11 panels together are far above the 320 px minimum
NORM_HEIGHT = 360               # plot height of the normalised chart [px]
ZOOM_NOTE_BELOW_PCT = 0.1       # an absolute panel whose whole excursion is under this % of the quantity's value says that its axis is zoomed
TIME_TITLE = "time since start, min"
STEP_COLOR, OLD_COLOR, NEW_COLOR, GUIDE_COLOR = "#111827", "#6B7280", "#B91C1C", "#9CA3AF"

# key -> colour / dash / shape. Colours: one blue, minimum CIE-Lab distance 33 between any two (tests/test_transient_charts.py checks it).
_STYLE = (
    ("ga001_dry_flow_nm3_h", "#0072B2", [],                     "circle"),
    ("H2_pct_dry",          "#D55E00", [6, 3],                 "square"),
    ("CO_pct_dry",          "#009E73", [2, 2],                 "diamond"),
    ("CO2_pct_dry",         "#7B3294", [8, 3, 2, 3],           "triangle-up"),
    ("CH4_pct_dry",         "#E69F00", [12, 4],                "triangle-down"),
    ("N2_pct_dry",          "#222222", [4, 2, 1, 2],           "cross"),
    ("lhv_mj_nm3",          "#D45A9E", [1, 3],                 "triangle-right"),
    ("h2_production_kg_h",  "#8C6D1F", [10, 3, 2, 3, 2, 3],    "triangle-left"),
    ("eu008_demand_kw",     "#B3224A", [5, 5],                 "arrow"),
    ("eu008_supply_temp_c", "#9A9A9A", [2, 4],                 "wedge"),
    ("T_gasifier_C",        "#5E8C00", [14, 3, 3, 3],          "stroke"),
)
SERIES_STYLE = {key: {"color": color, "dash": dash, "shape": shape} for key, color, dash, shape in _STYLE}
assert set(SERIES_STYLE) == {q[0] for q in sim.PLOT_QUANTITIES}, "every plotted quantity needs a style"


def pretty(text):
    for a, b in (("CO2", "CO₂"), ("CH4", "CH₄"), ("H2", "H₂"), ("N2", "N₂"), ("Nm3", "Nm³")):
        text = text.replace(a, b)
    return text


# ------------------------------------------------------------------------------------------------------------ time axis
def tick_step_min(duration_min):
    """Tick spacing [min] for a run of `duration_min`, so that the labels never overlap on a normal screen:
    up to 30 min every 1 min (the short ER / T runs), up to 60 min every 5, up to 2 h every 10, up to 3 h every 15, longer every 30."""
    if duration_min <= 30:
        return 1
    if duration_min <= 60:
        return 5
    if duration_min <= 120:
        return 10
    if duration_min <= 180:
        return 15
    return 30


def tick_values(duration_min):
    step = tick_step_min(duration_min)
    return list(range(0, int(duration_min) + 1, step))


def _x(duration_min, title=True):
    return alt.X("minute:Q", title=TIME_TITLE if title else None, scale=alt.Scale(domain=[0, duration_min], nice=False),
                 axis=alt.Axis(values=tick_values(duration_min), labelOverlap="greedy", labelSeparation=2, grid=True))


def _step_layers(step_min, x, above=False):
    """The step: a thin black rule with its time as a label, inside the plot at the top, or (above=True) just above the plot."""
    rule = alt.Chart(pd.DataFrame({"minute": [step_min]})).mark_rule(color=STEP_COLOR, strokeWidth=1).encode(x=x)
    label = alt.Chart(pd.DataFrame({"minute": [step_min], "text": [f"step at {step_min:g} min"]})).mark_text(
        align="left", baseline="bottom" if above else "top", dx=4, dy=-3 if above else 2, fontSize=11, color=STEP_COLOR).encode(
        x=x, y=alt.value(0), text="text:N")
    return [rule, label]


# ---------------------------------------------------------------------------------------------------------------- data
def time_cell(row, which):
    """(text shown in the response table, seconds to draw or None) for `which` = "t63" / "t95". The ONE place the table's wording lives:
    a marker is drawn only where the seconds are not None."""
    if not row["meaningful"]:
        return "n/a (change < 0.01 %)", None
    seconds = row[which]
    if seconds is None:
        return "not reached in this run", None
    if row[which + "_unresolved"]:
        return sim.UNRESOLVED_LABEL, None
    return f"{seconds:.0f}", seconds


def long_frames(payload):
    """(absolute, normalised, step_min, duration_min). `is_marker` flags the samples that carry a point shape (about 14 per curve, a different
    set for each curve)."""
    step_min = payload["params"]["step_s"] / 60.0
    duration_min = payload["params"]["duration_s"] / 60.0
    stride = max(1, round(len(payload["series"]) / 14))
    absolute, normalised = [], []
    for n, r in enumerate(payload["response"]):
        label = f"{pretty(r['label'])} [{pretty(r['unit'])}]"
        phase = (n * stride) // len(payload["response"])             # each curve carries its points at other samples, so they do not pile up
        for i, row in enumerate(payload["series"]):
            minute = row["t_s"] / 60.0
            marker = i % stride == phase
            absolute.append({"key": r["key"], "quantity": label, "minute": minute, "value": row[r["key"]], "old_steady": r["before"],
                             "new_steady": r["final"], "step_min": step_min, "is_marker": marker})
            if r["meaningful"]:
                normalised.append({"key": r["key"], "quantity": pretty(r["label"]), "minute": minute,
                                   "pct": (row[r["key"]] - r["before"]) / r["change"] * 100.0, "is_marker": marker})
    return pd.DataFrame(absolute), pd.DataFrame(normalised), step_min, duration_min


def marker_frame(row, step_min):
    """The t63 / t95 vertical markers of ONE response row: only the resolved ones (see time_cell). Empty when none is."""
    items = []
    for which, y in (("t63", 4), ("t95", 18)):
        _text, seconds = time_cell(row, which)
        if seconds is not None:
            items.append({"which": which, "minute": step_min + seconds / 60.0, "ypx": y})
    return pd.DataFrame(items, columns=["which", "minute", "ypx"])


# ------------------------------------------------------------------------------------------------------ absolute panels
def panel_span_pct(frame):
    """Total span of one absolute panel (max - min over the plotted series AND the old / new steady-state lines) as a percentage of the
    quantity's final steady value. None when that value is zero (a percentage of zero is undefined)."""
    final = float(frame["new_steady"].iloc[0])
    if final == 0.0:
        return None
    values = list(frame["value"]) + [float(frame["old_steady"].iloc[0]), final]
    return (max(values) - min(values)) / abs(final) * 100.0


def _two_significant(value):
    text = f"{value:.2g}"
    return f"{value:.12f}".rstrip("0") if "e" in text else text            # 1.2e-05 is shown as 0.000012


def zoom_note(frame):
    """The one-line note printed under a panel's title when the axis is zoomed onto a tiny excursion (span below ZOOM_NOTE_BELOW_PCT of the
    value); None otherwise. The data and the zoom are untouched: the note only says how small the excursion is."""
    span = panel_span_pct(frame)
    if span is None or span >= ZOOM_NOTE_BELOW_PCT:
        return None
    return f"axis zoomed: total change is {_two_significant(span)} % of the value"


def absolute_panel(frame, step_min, duration_min, last=False, from_zero=False):
    """One small multiple: ONE quantity, its own y scale (the quantities differ by up to three orders of magnitude, so no shared or dual
    axis), the time axis shared with every other panel (same domain, same ticks, same left margin). `from_zero` starts the y axis at 0
    instead of zooming onto the data (no zoom note then: the axis is not zoomed)."""
    style = SERIES_STYLE[frame["key"].iloc[0]]
    x = _x(duration_min, title=last)
    y = alt.Y("value:Q", title=None, scale=alt.Scale(zero=from_zero), axis=alt.Axis(format=".6~g", tickCount=5, minExtent=64))
    line = alt.Chart(frame).mark_line(color=style["color"], strokeWidth=2.2, strokeDash=style["dash"]).encode(x=x, y=y)
    points = alt.Chart(frame[frame["is_marker"]]).mark_point(color=style["color"], shape=style["shape"], filled=True, size=40, opacity=1).encode(x=x, y=y)
    old = alt.Chart(frame.iloc[[0]]).mark_rule(color=OLD_COLOR, strokeDash=[4, 3]).encode(y="old_steady:Q")
    new = alt.Chart(frame.iloc[[0]]).mark_rule(color=NEW_COLOR, strokeDash=[4, 3]).encode(y="new_steady:Q")
    note = None if from_zero else zoom_note(frame)
    extra = {"subtitle": note, "subtitleFontSize": 11, "subtitleColor": NEW_COLOR, "subtitlePadding": 4} if note else {}
    title = alt.TitleParams(frame["quantity"].iloc[0], anchor="start", fontSize=13, fontWeight="bold", **extra)
    return alt.layer(old, new, *_step_layers(step_min, x), line, points).properties(height=ABS_PANEL_HEIGHT, width="container", title=title)


def absolute_panels(absolute, step_min, duration_min, from_zero=False):
    """The absolute-unit figure: one panel per plotted quantity, in the order of sim.PLOT_QUANTITIES, one panel per row."""
    keys = list(dict.fromkeys(absolute["key"]))
    panels = [absolute[absolute["key"] == key] for key in keys]
    return [absolute_panel(frame, step_min, duration_min, last=(i == len(panels) - 1), from_zero=from_zero) for i, frame in enumerate(panels)]


# ----------------------------------------------------------------------------------------------------- normalised chart
def normalised_chart(normalised, step_min, duration_min, marker_row=None):
    """% of the change to the new steady state. Every series: its own colour AND dash AND shape (one merged legend at the right, outside the
    plot; clicking an entry highlights that series). 63.2 % and 95 % guide lines; for `marker_row` (a response row) dotted verticals t63 / t95."""
    keys = [q[0] for q in sim.PLOT_QUANTITIES if q[0] in set(normalised["key"])]
    names = {q[0]: pretty(q[1]) for q in sim.PLOT_QUANTITIES}
    domain = [names[k] for k in keys]
    legend = alt.Legend(title=None, orient="right", labelLimit=200, symbolType="stroke", symbolStrokeWidth=2.5, symbolSize=500, padding=6)

    def scale(field):
        return alt.Scale(domain=domain, range=[SERIES_STYLE[k][field] for k in keys])

    color = alt.Color("quantity:N", scale=scale("color"), legend=legend)
    dash = alt.StrokeDash("quantity:N", scale=scale("dash"), legend=legend)
    pick = alt.selection_point(fields=["quantity"], bind="legend")
    opacity = alt.condition(pick, alt.value(1), alt.value(0.12))
    x = _x(duration_min)
    y = alt.Y("pct:Q", title="% of the change to the new steady state")

    lines = alt.Chart(normalised).mark_line(strokeWidth=2.2).encode(
        x=x, y=y, color=color, strokeDash=dash, opacity=opacity,
        tooltip=["quantity:N", alt.Tooltip("minute:Q", title="min", format=".2f"), alt.Tooltip("pct:Q", title="%", format=".1f")]).add_params(pick)
    # the legend shows colour + dash (from the lines); the point SHAPE is a third cue on the curve, one constant-shape layer per series
    # (no shape channel, so it adds nothing to the legend)
    points = [alt.Chart(normalised[normalised["is_marker"] & (normalised["key"] == k)]).mark_point(
        filled=True, size=45, color=SERIES_STYLE[k]["color"], shape=SERIES_STYLE[k]["shape"]).encode(x=x, y=y, opacity=opacity) for k in keys]

    guide_rows = pd.DataFrame({"pct": [0.0, 63.2, 95.0, 100.0]})
    guides = alt.Chart(guide_rows).mark_rule(color=GUIDE_COLOR, strokeDash=[3, 3]).encode(y="pct:Q")
    labelled = pd.DataFrame({"pct": [63.2, 95.0], "text": ["63.2 %", "95 %"], "minute": [0.0, 0.0]})
    guide_text = alt.Chart(labelled).mark_text(align="left", baseline="bottom", dx=4, dy=-2, fontSize=11, color=OLD_COLOR).encode(
        x=x, y="pct:Q", text="text:N")

    layers = [guides, guide_text, *_step_layers(step_min, x, above=True), lines, *points]
    if marker_row is not None:
        tint = SERIES_STYLE[marker_row["key"]]["color"]
        markers = marker_frame(marker_row, step_min)
        for which in ("t63", "t95"):
            part = markers[markers["which"] == which]
            if part.empty:
                continue                                    # unresolved / not reached: no marker (the caption says why)
            rule = alt.Chart(part, name=f"{which}_marker").mark_rule(color=tint, strokeDash=[2, 3], strokeWidth=1.6).encode(x=x)
            text = alt.Chart(part).mark_text(align="left", baseline="top", dx=3, fontSize=11, fontWeight="bold", color=tint).encode(
                x=x, y=alt.Y("ypx:Q", scale=None, axis=None), text="which:N")
            layers += [rule, text]
    return alt.layer(*layers).properties(height=NORM_HEIGHT, width="container", padding={"top": 20, "left": 5, "right": 5, "bottom": 5})
