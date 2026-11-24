"""
ui.py - what every page shares: the data, the filter bar, and the chart frame.

The pages in views/ lay content out. They get the numbers from metrics.py, the look
from kit.py, and the slice that the reader chose from filter_bar() below.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

import kit
import metrics as mx
import mockdata as md

MIN_ROWS = 300              # below this, a page does not show a number for the slice
SCORE_WEEKS = 26            # window for the source scorecard
DATA_DATE = f"{md.LAST_WEEK_END:%d %b %Y}".lstrip("0")

SCENARIOS = {
    "vendor_b": {"coverage_boost": {("vendor_b", "EMEA"): 1.5}},
    "contributor": {"coverage_boost": {("contributor", r): 1.5 for r in md.REGIONS[1:]}},
    "no_incident": {"no_incident": True},
}

WINDOWS = {"Last 4 weeks": 4, "Last 13 weeks": 13}
COMPARISONS = ["vs a year ago", "vs the weeks before"]
# key, label, the text for "no filter", the values
FILTERS = [
    ("channel", "Channel", "Email and phone", md.CHANNELS),
    ("region", "Region", "All regions", md.REGIONS),
    ("company_size", "Company size", "All company sizes", md.SIZES),
    ("seniority", "Seniority", "All seniority levels", md.SENIORITIES),
    ("industry", "Industry", "All industries", md.INDUSTRIES),
]


# --------------------------------------------------------------------------
# Data (built once, then shared by every session)
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Building the illustrative audit sample")
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(customer requests, a uniform sample of catalog contacts). Both are simulated."""
    requests = md.simulate()
    catalog = md.simulate(demand_weighted=False, weeks=(md.WEEKS - 3, md.WEEKS), rows_per_week=5000)
    return requests, catalog


@st.cache_resource(show_spinner="Running the what-if simulations")
def load_scenarios() -> dict[str, float]:
    """Usable contacts a year that each what-if adds, from a second run with the same random draws."""
    span = (md.WEEKS - SCORE_WEEKS + 1, md.WEEKS)
    base = md.simulate(weeks=span)
    return {name: mx.scenario_gain(base, md.simulate(sc, weeks=span)) for name, sc in SCENARIOS.items()}


@st.cache_resource(show_spinner="Running the merge again without each source")
def load_overlap() -> pd.DataFrame:
    """
    For each source: its cost per net-new usable contact when its nearest overlap is gone.

    Leave-one-out is valid for one removal at a time. So this removes each other source in turn
    (a second run with the same random draws), scores the source again, and keeps the removal that
    raises its net-new usable contacts the most. That other source is its nearest overlap.
    """
    span = (md.WEEKS - SCORE_WEEKS + 1, md.WEEKS)
    base = mx.source_scorecard(md.simulate(weeks=span), md.simulate(weeks=span), 1.0).set_index("key")
    best: dict[str, dict] = {}
    for other in md.SOURCES:
        run = md.simulate({"coverage_boost": {(other.key, r): 0.0 for r in md.REGIONS}}, weeks=span)
        sc = mx.source_scorecard(run, run, 1.0).set_index("key")
        for src in md.SOURCES:
            if src.key == other.key:
                continue
            net = float(sc.loc[src.key, "net_new_usable"])
            if src.key not in best or net > best[src.key]["net_without"]:
                best[src.key] = dict(key=src.key, overlap=other.label, net_without=net,
                                     cost_without=float(sc.loc[src.key, "cost_per_net_new_usable"]))
    out = pd.DataFrame(best.values())
    out["net_today"] = out["key"].map(base["net_new_usable"])
    return out


def rows_as_csv(d: pd.DataFrame) -> bytes:
    """The audited rows behind a view, with the bit masks spelled out."""
    d = d.copy()

    def names(mask: pd.Series) -> pd.Series:
        return mask.map(lambda m: "|".join(k for i, k in enumerate(md.SOURCE_KEYS) if m & (1 << i)))

    d["sources"] = names(d.pop("sources_mask"))
    d["usable_only_because_of"] = names(d.pop("helps_mask"))
    d["usable_if_removed"] = names(d.pop("harms_mask"))
    d["week_end"] = d["week_end"].dt.strftime("%Y-%m-%d")
    return d.to_csv(index=False).encode("utf-8")


# --------------------------------------------------------------------------
# Number formats (the kit's compact units: 91.6%, +0.4 pts, 238.4M)
# --------------------------------------------------------------------------
def ok(x) -> bool:
    return x is not None and bool(np.isfinite(x))


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%" if ok(x) else "–"


def rate(x: float, digits: int = 1) -> str:
    """A share as a number without the sign, for a cell whose header carries the unit."""
    return f"{100 * x:.{digits}f}" if ok(x) else "–"


def pts(x: float, digits: int = 1) -> str:
    return f"{100 * x:+.{digits}f} pts" if ok(x) else "–"


def millions(x: float, digits: int = 1) -> str:
    return f"{x / 1e6:.{digits}f}M" if ok(x) else "–"


def dollars(x: float) -> str:
    """Dollars per contact: three decimals under ten cents."""
    if not ok(x):
        return "no gain"
    return f"${x:.3f}" if x < 0.1 else f"${x:.2f}"


def definition(metric: str) -> str:
    """The one-sentence form of a metric definition, for a tooltip. The full text is on the Method page."""
    return next(d["short"] for d in mx.DEFINITIONS if d["metric"] == metric)


# --------------------------------------------------------------------------
# Page head and the table switch
# --------------------------------------------------------------------------
def _keep(key: str) -> None:
    st.session_state[f"kept.{key}"] = st.session_state[key]


def sticky(widget, label: str, *args, key: str, default, **kwargs):
    """
    Draw a widget whose value survives a page change, and return the value.

    Streamlit gives a widget a new state on each page, so a filter would reset each time the
    reader opens another page. This keeps the value in the session under its own name and
    hands it to the widget before the widget is built. widget is the Streamlit function to
    call, for example st.selectbox or a column's number_input.
    """
    store = f"kept.{key}"
    st.session_state.setdefault(store, default)
    st.session_state[key] = st.session_state[store]
    widget(label, *args, key=key, on_change=_keep, args=(key,), **kwargs)
    return st.session_state[store]


def show_tables() -> bool:
    return bool(st.session_state.get("kept.show_tables", False))


def page_head(title: str, sub: str, tables: bool = True) -> None:
    """The page title, and the switch that puts each chart's numbers under the chart (on a page that has charts)."""
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="bottom", key="pagehead"):
        st.html(kit.page_head(title, sub))
        if tables:
            sticky(st.toggle, "Show chart tables", key="show_tables", default=False, width="content")


# --------------------------------------------------------------------------
# The filter bar: one row that scopes everything below it
# --------------------------------------------------------------------------
@dataclass
class Scope:
    """The slice that the reader chose, and the two windows that the page compares."""
    filters: dict
    active: dict
    n_weeks: int
    window: str             # "last 4 weeks"
    period: str             # "vs a year ago"
    base_phrase: str        # "a year ago"
    df: pd.DataFrame        # every audited request
    fdf: pd.DataFrame       # the filtered requests, all weeks
    cur: pd.DataFrame
    base: pd.DataFrame
    f_cur: mx.Funnel
    f_base: mx.Funnel
    enough: bool


def _reset_filters() -> None:
    for key, *_ in FILTERS:
        st.session_state[f"f_{key}"] = st.session_state[f"kept.f_{key}"] = "All"


def filter_bar() -> Scope:
    df, _ = load_data()
    with st.container(key="filterbar"):
        cols = st.columns([1.22, 1.28, 1.44, 1.14, 1.56, 1.62, 1.3], gap="small")     # in proportion to the default labels
        window_label = sticky(cols[0].selectbox, "Window", list(WINDOWS), key="f_window", default="Last 4 weeks",
                              label_visibility="collapsed")
        compare_label = sticky(cols[1].selectbox, "Compare with", COMPARISONS, key="f_compare", default=COMPARISONS[0],
                               label_visibility="collapsed")
        filters = {}
        for col, (key, label, all_label, values) in zip(cols[2:], FILTERS):
            with col.container(key=f"flt-{key}"):
                filters[key] = sticky(st.selectbox, label, ["All"] + values, key=f"f_{key}", default="All",
                                      label_visibility="collapsed", format_func=lambda v, a=all_label: a if v == "All" else v)

    n_weeks = WINDOWS[window_label]
    year = compare_label == COMPARISONS[0]
    offset = 52 if year else n_weeks
    base_phrase = "a year ago" if year else f"the {n_weeks} weeks before"
    active = {k: v for k, v in filters.items() if v != "All"}

    fdf = mx.apply_filters(df, filters)
    cur, base = mx.window(fdf, n_weeks), mx.window(fdf, n_weeks, md.WEEKS - offset)
    f_cur, f_base = mx.funnel(cur), mx.funnel(base)
    enough = min(f_cur.n, f_base.n) >= MIN_ROWS and min(f_cur.complete, f_base.complete) >= 30

    # An active filter takes the kit's selection colours. The result line states what the filters hide.
    if active:
        rules = "".join(f'.st-key-flt-{k} .react-aria-ComboBox > [role="group"] {{ border-color: var(--selected-border); '
                        f"background: var(--selected-bg); color: var(--selected-text); }}" for k in active)
        st.html(f"<style>{rules}</style>")
    total = len(mx.window(df, n_weeks))
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", key="filternote"):
        showing = f"Showing {len(cur):,} of {total:,} audited requests." if active else f"{total:,} audited requests."
        st.html(kit.note(f"{showing} {window_label} to {DATA_DATE}, compared with {base_phrase}. Illustrative data."))
        if active:
            st.button("Reset filters", type="tertiary", on_click=_reset_filters, key="reset_filters", width="content")

    return Scope(filters=filters, active=active, n_weeks=n_weeks, window=window_label.lower(),
                 period=f"vs {base_phrase}", base_phrase=base_phrase, df=df, fdf=fdf, cur=cur, base=base,
                 f_cur=f_cur, f_base=f_base, enough=enough)


def small_sample(n_now: int, n_before: int | None = None) -> None:
    """Say plainly that the slice is too small, and what to do next."""
    counts = f"{n_now:,} audited requests in the window" + (f" and {n_before:,} in the comparison" if n_before is not None else "")
    st.html(kit.alert(kit.esc(f"This slice has too few audited requests to show a number: {counts}. A number needs "
                              f"{MIN_ROWS:,}. Remove a filter, or use the 13-week window."), tone="caution"))


# --------------------------------------------------------------------------
# The chart frame
# --------------------------------------------------------------------------
def chart_card(key: str, title: str, sub: str, chart, table: pd.DataFrame | None = None,
               legend: str = "", note: str = "") -> None:
    """An Altair chart in the kit's chart frame: head, legend, plot, then the table view and a note."""
    with kit.card(key):
        st.html(kit.chart_head(title, sub) + legend)
        st.altair_chart(chart, width="stretch", theme=None, key=f"chart-{key}")
        tail = (kit.chart_table(table) if show_tables() and table is not None else "") + (kit.note(note) if note else "")
        if tail:
            st.html(tail)


def figure(title: str, sub: str, body: str, table: pd.DataFrame | None = None, legend: str = "", note: str = "") -> str:
    """The same frame for content drawn in HTML. Returns HTML, so that two figures can share one grid row."""
    table_html = kit.chart_table(table) if show_tables() and table is not None else ""
    return kit.figure(title, sub, body, legend_html=legend, table_html=table_html, note_text=note)


def events_frame() -> pd.DataFrame:
    """The three built-in events, placed on the time axis of the trend chart."""
    events = pd.DataFrame({"week": list(md.EVENTS), "label": list(md.EVENTS.values())})
    events["week_end"] = md.week_end_date(events["week"].to_numpy())
    events["number"] = [str(i + 1) for i in range(len(events))]
    return events
