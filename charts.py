"""
charts.py - Altair charts drawn with the design system's chart tokens and mark rules.

From the kit (design/KIT_README.md, and its BarChart and LineChart notes):
  - one series is viz-1 for every bar; two series take viz-1 and viz-2 in fixed order;
  - when one series is the point, it is viz-emphasis and the rest are viz-other;
  - values around a midpoint (up versus down) take the viz-div-* pair;
  - 2px lines, an 8px end dot with a surface ring, bars 24px wide at most with a 4px rounded end;
  - solid hairline gridlines, one axis, and text in text tokens, never in a series colour.

The title, the subtitle, the legend and the table view are not drawn here. They sit in
the card around the chart (see ui.chart_card), so that every chart has the same frame.
Charts that are ranked lists, grids or funnels are not here at all: the kit draws those
as Meters, a Heatmap and a Table (see kit.py).
"""
from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd

import kit


def _c(token: str) -> str:
    return kit.color(token)


def finish(chart: alt.TopLevelMixin, height: int) -> alt.TopLevelMixin:
    """Apply the kit's chart frame. Call this last."""
    sans = kit.font("sans")
    return (
        chart.properties(height=height, usermeta={"embedOptions": {"renderer": "svg", "actions": False}})
        .configure(background=_c("bg-primary"), font=sans, padding={"left": 2, "right": 12, "top": 6, "bottom": 2})
        .configure_view(stroke=None)
        .configure_axis(gridColor=_c("viz-grid"), gridWidth=1, domainColor=_c("viz-axis"), tickColor=_c("viz-axis"),
                        labelColor=_c("text-tertiary"), titleColor=_c("text-tertiary"), labelFontSize=12, titleFontSize=12,
                        labelFontWeight=400, titleFontWeight=400, labelLimit=320, titlePadding=8, labelFont=sans, titleFont=sans)
        .configure_text(font=sans, fontSize=12)
    )


# Vega-Lite takes font weights in hundreds only. The charts ask for 500 and 600, and
# design/streamlit.css maps those to the kit's label and strong weights on the drawn text.
LABEL_WEIGHT, STRONG_WEIGHT = 500, 600


def _label(**kw) -> dict:
    """A direct label: text-primary at the kit's label weight."""
    return dict(color=_c("text-primary"), fontSize=12, fontWeight=LABEL_WEIGHT, **kw)


def _cat_axis(**kw) -> alt.Axis:
    """Axis for a category scale: names only, in text-primary."""
    return alt.Axis(grid=False, domain=False, ticks=False, labelPadding=8, labelColor=_c("text-primary"), **kw)


# --------------------------------------------------------------------------
# Lines
# --------------------------------------------------------------------------
def trend_domain(tr: pd.DataFrame) -> tuple[float, float]:
    """The y range of the trend chart. The card's subtitle states where the axis starts."""
    lo, hi = 100 * float(tr["yield_low"].min()), 100 * float(tr["yield_high"].max())
    pad = max(1.0, (hi - lo) * 0.25)
    return float(np.floor(lo - pad * 0.3)), float(np.ceil(hi + pad))


def trend_chart(tr: pd.DataFrame, events: pd.DataFrame) -> alt.TopLevelMixin:
    """Usable yield, 4-week rolling, with its 95% band and the events that moved it."""
    d = tr.assign(y=100 * tr["yield_rate"], lo=100 * tr["yield_low"], hi=100 * tr["yield_high"])
    domain = trend_domain(tr)
    scale = alt.Scale(domain=list(domain), nice=False)
    x = alt.X("week_end:T", title=None, axis=alt.Axis(format="%b %Y", tickCount=8, grid=False))
    base = alt.Chart(d).encode(x=x)
    band = base.mark_area(color=_c("viz-1"), opacity=0.1).encode(
        y=alt.Y("lo:Q", scale=scale, title=None, axis=alt.Axis(tickCount=6)), y2="hi:Q")
    line = base.mark_line(color=_c("viz-1"), strokeWidth=2, strokeJoin="round", strokeCap="round").encode(
        y=alt.Y("y:Q", scale=scale))
    last = d.tail(1).assign(label=lambda t: t["y"].map(lambda v: f"{v:.1f}"))
    end_dot = alt.Chart(last).mark_point(color=_c("viz-1"), filled=True, size=64, stroke=_c("bg-primary"), strokeWidth=2,
                                         opacity=1).encode(x="week_end:T", y=alt.Y("y:Q", scale=scale))
    end_label = alt.Chart(last).mark_text(align="left", dx=8, **_label()).encode(
        x="week_end:T", y=alt.Y("y:Q", scale=scale), text="label:N")

    hover = alt.selection_point(fields=["week_end"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    tips = [alt.Tooltip("week_end:T", format="%d %b %Y", title="4 weeks to"),
            alt.Tooltip("y:Q", format=".1f", title="Usable per 100"),
            alt.Tooltip("lo:Q", format=".1f", title="95% low"),
            alt.Tooltip("hi:Q", format=".1f", title="95% high")]
    crosshair = base.mark_rule(color=_c("viz-axis"), strokeWidth=1).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)), tooltip=tips).add_params(hover)
    dot = base.mark_point(color=_c("viz-1"), filled=True, size=64, stroke=_c("bg-primary"), strokeWidth=2).encode(
        y=alt.Y("y:Q", scale=scale), opacity=alt.condition(hover, alt.value(1), alt.value(0)))

    layers = [band, line, end_dot, end_label, crosshair, dot]
    if len(events):                                 # a numbered rule for each event; the card's note names them
        ev = events.assign(top=domain[1])
        layers.append(alt.Chart(ev).mark_rule(color=_c("viz-axis"), strokeWidth=1).encode(x="week_end:T"))
        layers.append(alt.Chart(ev).mark_text(align="left", dx=5, dy=4, baseline="top", color=_c("text-secondary"), fontSize=12,
                                              fontWeight=LABEL_WEIGHT).encode(
            x="week_end:T", y=alt.Y("top:Q", scale=scale), text="number:N",
            tooltip=[alt.Tooltip("label:N", title="Event"), alt.Tooltip("week_end:T", format="%d %b %Y", title="Week ending")]))
    return finish(alt.layer(*layers), height=252)


def index_chart(data: pd.DataFrame, emphasis: str) -> alt.TopLevelMixin:
    """Two series set to 100 a year ago. The series that is the point is viz-emphasis; the other is viz-other."""
    series = [s for s in data["series"].unique() if s != emphasis] + [emphasis]
    colors = alt.Scale(domain=series, range=[_c("viz-other")] * (len(series) - 1) + [_c("viz-emphasis")])
    lo, hi = float(data["index"].min()), float(data["index"].max())
    scale = alt.Scale(domain=[np.floor(lo - 2), np.ceil(hi + 3)], nice=False)
    x = alt.X("quarter:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, grid=False), scale=alt.Scale(padding=0.45))
    base = alt.Chart(data).encode(x=x, y=alt.Y("index:Q", scale=scale, title=None, axis=alt.Axis(tickCount=5)),
                                  color=alt.Color("series:N", scale=colors, legend=None))
    tips = [alt.Tooltip("series:N", title="Series"), alt.Tooltip("quarter:N", title="Quarter"),
            alt.Tooltip("index:Q", format=".1f", title="Index"), alt.Tooltip("detail:N", title="Value")]
    lines = base.mark_line(strokeWidth=2, strokeJoin="round", strokeCap="round").encode(tooltip=tips)
    dots = base.mark_point(filled=True, size=64, stroke=_c("bg-primary"), strokeWidth=2, opacity=1).encode(tooltip=tips)
    last = data[data["quarter"] == data["quarter"].iloc[-1]].assign(label=lambda t: t["index"].map(lambda v: f"{v - 100:+.0f}%"))
    labels = alt.Chart(last).mark_text(align="left", dx=10, **_label()).encode(x=x, y=alt.Y("index:Q", scale=scale), text="label:N")
    return finish(lines + dots + labels, height=256)


# --------------------------------------------------------------------------
# Bars
# --------------------------------------------------------------------------
def change_chart(parts: dict) -> alt.TopLevelMixin:
    """Points of change in usable yield that come from each funnel step. Up and down take the diverging pair."""
    data = pd.DataFrame({
        "step": ["Found", "Complete", "Correct"],
        "points": [100 * parts["found"], 100 * parts["complete"], 100 * parts["correct"]],
    })
    data["label"] = data["points"].map(lambda v: f"{v:+.1f}")
    data["direction"] = np.where(data["points"] >= 0, "Up", "Down")
    span = max(1.0, float(data["points"].abs().max())) * 1.45
    y = alt.Y("step:N", sort=None, title=None, axis=_cat_axis(), scale=alt.Scale(paddingInner=0.5, paddingOuter=0.3))
    x = alt.X("points:Q", title=None, scale=alt.Scale(domain=[-span, span]), axis=alt.Axis(tickCount=6))
    bars = alt.Chart(data).mark_bar(size=20, cornerRadiusEnd=4).encode(
        y=y, x=x,
        color=alt.Color("direction:N", scale=alt.Scale(domain=["Up", "Down"], range=[_c("viz-div-pos-2"), _c("viz-div-neg-2")]), legend=None),
        tooltip=[alt.Tooltip("step:N", title="Step"), alt.Tooltip("points:Q", format="+.2f", title="Points of yield")],
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=_c("viz-axis")).encode(x="x:Q")
    pos = alt.Chart(data[data["points"] >= 0]).mark_text(align="left", dx=6, **_label()).encode(y=y, x="points:Q", text="label:N")
    neg = alt.Chart(data[data["points"] < 0]).mark_text(align="right", dx=-6, **_label()).encode(y=y, x="points:Q", text="label:N")
    return finish(bars + zero + pos + neg, height=136)


def column_chart(data: pd.DataFrame, x_title: str, upper: float = 100.0, intervals: bool = False) -> alt.TopLevelMixin:
    """
    One series as columns: viz-1 for every bar, and the value axis starts at zero.
    data: category, value (0 to 100), n, and low and high when intervals is on.
    """
    d = data.assign(label=data["value"].map(lambda v: "" if pd.isna(v) else f"{v:.0f}%"))
    order = d["category"].tolist()
    x = alt.X("category:N", sort=order, title=x_title,
              axis=alt.Axis(labelAngle=0, grid=False, domain=False, ticks=False, labelPadding=8, labelColor=_c("text-primary")))
    y = alt.Y("value:Q", title=None, scale=alt.Scale(domain=[0, upper]), axis=alt.Axis(tickCount=5, format=".0f"))
    tips = [alt.Tooltip("category:N", title=x_title), alt.Tooltip("value:Q", format=".1f", title="%"),
            alt.Tooltip("n:Q", format=",", title="Audited contacts")]
    if intervals:
        tips += [alt.Tooltip("low:Q", format=".1f", title="95% low"), alt.Tooltip("high:Q", format=".1f", title="95% high")]
    layers = [alt.Chart(d).mark_bar(size=24, cornerRadiusEnd=4, color=_c("viz-1")).encode(x=x, y=y, tooltip=tips)]
    if intervals:
        layers.append(alt.Chart(d).mark_rule(color=_c("text-primary"), strokeWidth=1.5).encode(x=x, y="low:Q", y2="high:Q", tooltip=tips))
    layers.append(alt.Chart(d).mark_text(dy=-8, **_label()).encode(x=x, y="high:Q" if intervals else "value:Q", text="label:N"))
    return finish(alt.layer(*layers), height=236)


def cost_chart(options: pd.DataFrame, value_per_usable: float, palette: dict[str, str], cap: float | None = None) -> alt.TopLevelMixin:
    """
    Dollars per net-new usable contact for each option, with the break-even value as a rule.
    palette maps each kind to a chart token, in legend order. A bar longer than cap is cut at the edge.
    """
    d = options.sort_values("cost", ascending=True).copy()
    cap = cap or float(d["cost"].replace(np.inf, np.nan).max()) * 1.25
    d["shown"] = d["cost"].clip(upper=cap)
    d["label"] = d["cost"].map(lambda v: "no gain" if not np.isfinite(v) else f"${v:.3f}" if v < 0.1 else f"${v:.2f}")
    order = d["name"].tolist()
    kinds = [k for k in palette if k in set(d["kind"])]
    y = alt.Y("name:N", sort=order, title=None, axis=_cat_axis(labelLimit=380))
    x_scale = alt.Scale(domain=[0, cap * 1.15])
    bars = alt.Chart(d).mark_bar(size=18, cornerRadiusEnd=4).encode(
        y=y, x=alt.X("shown:Q", title=None, scale=x_scale, axis=alt.Axis(format="$.2f", tickCount=5, labelOverlap=True)),
        color=alt.Color("kind:N", scale=alt.Scale(domain=kinds, range=[_c(palette[k]) for k in kinds]), legend=None),
        tooltip=[alt.Tooltip("name:N", title="Option"), alt.Tooltip("label:N", title="Per net-new usable"),
                 alt.Tooltip("net_m:Q", format=".1f", title="Net-new usable, M a year"),
                 alt.Tooltip("annual_cost_m:Q", format="$.2f", title="Cost a year, $M")])
    rule_data = pd.DataFrame({"x": [value_per_usable], "label": [f"Break-even ${value_per_usable:.2f}"]})
    rule = alt.Chart(rule_data).mark_rule(color=_c("border-inverse"), strokeWidth=1).encode(x=alt.X("x:Q", scale=x_scale))
    rule_label = alt.Chart(rule_data).mark_text(align="left", dx=6, dy=-4, baseline="bottom", color=_c("text-secondary"), fontSize=12).encode(
        x=alt.X("x:Q", scale=x_scale), y=alt.value(0), text="label:N")
    text = alt.Chart(d).encode(y=y, x=alt.X("shown:Q", scale=x_scale), text="label:N")
    halo = text.mark_text(align="left", dx=8, fontSize=12, fontWeight=LABEL_WEIGHT, stroke=_c("bg-primary"), strokeWidth=5,
                          strokeJoin="round", color=_c("bg-primary"))
    labels = text.mark_text(align="left", dx=8, **_label())
    return finish(bars + rule + rule_label + halo + labels, height=30 * len(order) + 52)


# --------------------------------------------------------------------------
# Rank flip
# --------------------------------------------------------------------------
def rank_flip_chart(sc: pd.DataFrame, emphasis: str) -> alt.TopLevelMixin:
    """Rank by cost per record (left) against rank by cost per net-new usable contact (right). One source is the point."""
    left, right = "By cost per record", "By cost per net-new usable contact"
    rows = []
    for r in sc.itertuples():
        name = r.source.split(" (")[0]                 # the short name; the scorecard below has the full one
        rows.append(dict(source=r.source, side=left, rank=r.rank_per_record, label=f"{name}   ${r.cost_per_record:.3f}"))
        rows.append(dict(source=r.source, side=right, rank=r.rank_per_usable, label=f"${r.cost_per_net_new_usable:.2f}   {name}"))
    d = pd.DataFrame(rows)
    x = alt.X("side:N", sort=[left, right], title=None,
              axis=alt.Axis(orient="top", labelAngle=0, domain=False, ticks=False, grid=False, labelColor=_c("text-secondary"),
                            labelFontWeight=LABEL_WEIGHT, labelPadding=10),
              scale=alt.Scale(type="point", padding=1.15))
    y = alt.Y("rank:Q", scale=alt.Scale(domain=[len(sc) + 0.4, 0.6]), axis=None)
    tips = [alt.Tooltip("source:N", title="Source"), alt.Tooltip("side:N", title="List"),
            alt.Tooltip("rank:Q", title="Rank, 1 is cheapest")]
    layers = []
    for is_point, token in ((False, "viz-other"), (True, "viz-emphasis")):      # the point is drawn last, on top
        base = alt.Chart(d[(d["source"] == emphasis) == is_point]).encode(x=x, y=y, detail="source:N", tooltip=tips)
        layers.append(base.mark_line(strokeWidth=2, strokeCap="round", color=_c(token)))
        layers.append(base.mark_point(filled=True, size=64, stroke=_c("bg-primary"), strokeWidth=2, opacity=1, color=_c(token)))
    for side, align, dx in ((left, "right", -12), (right, "left", 12)):
        for is_point, weight in ((False, 400), (True, STRONG_WEIGHT)):
            part = d[(d["side"] == side) & ((d["source"] == emphasis) == is_point)]
            layers.append(alt.Chart(part).mark_text(align=align, dx=dx, color=_c("text-primary"), fontSize=12, fontWeight=weight).encode(
                x=x, y=y, text="label:N"))
    return finish(alt.layer(*layers), height=30 * len(sc) + 64)
