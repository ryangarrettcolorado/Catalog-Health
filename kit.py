"""
kit.py - the design system, applied to Streamlit.

The design system is the "Apollo Case Study Kit" in design/ (tokens.json, bundle.css,
icons.json). It is an unofficial kit for one candidate case study: see design/KIT_README.md.
This module is the only place that turns the kit into page output:

  inject()             loads the kit's tokens and component styles into the page
  banner(), metric(),  the kit's components, returned as HTML strings
  table(), heat() ...
  color(), font()      token values, for the charts

Rules from the kit that this module enforces: every screen starts with the
PrototypeBanner; the brand row shows a name in plain type and a plain square, never a
logo; icons are drawn inline; a status colour always comes with a word or an icon.

Every helper escapes the text it is given. A parameter that takes HTML says so.
"""
from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

DESIGN = Path(__file__).resolve().parent / "design"
AUTHOR = "Ryan Garrett"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


FILES = ("tokens.json", "tokens.css", "bundle.css", "streamlit.css", "icons.json")


def _assets() -> dict:
    """The kit's files, read once. An edit to a file in design/ shows on the next run."""
    return _load(tuple((DESIGN / name).stat().st_mtime_ns for name in FILES))


@lru_cache(maxsize=2)
def _load(stamp: tuple) -> dict:
    tokens = json.loads((DESIGN / "tokens.json").read_text(encoding="utf-8"))
    raw = {t["name"]: (t["value"]["light"] if isinstance(t["value"], dict) else t["value"]) for t in tokens["color"]["tokens"]}

    def resolve(name: str, depth: int = 0) -> str:
        value = str(raw[name])
        ref = re.fullmatch(r"\{([^}]+)\}", value)
        return resolve(ref.group(1), depth + 1) if ref and depth < 8 else value

    icons = json.loads((DESIGN / "icons.json").read_text(encoding="utf-8"))["icons"]
    css = [(DESIGN / n).read_text(encoding="utf-8") for n in ("tokens.css", "bundle.css", "streamlit.css")]
    css.append("\n".join(f".kit-icon--{name} {{ --kit-i: {_mask(paths)}; }}" for name, paths in icons.items()))
    return {
        "css": "\n".join(css),
        "icons": icons,
        "colors": {name: resolve(name) for name in raw},
        "families": tokens["type"]["families"],
    }


def _mask(paths: str) -> str:
    """An icon's outline as a CSS mask image. The element's text colour fills the mask."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.5' "
           f"stroke-linecap='round' stroke-linejoin='round'>{paths}</svg>").replace('"', "'")
    return f'url("data:image/svg+xml,{quote(svg, safe="/:=, ")}")'


def color(token: str) -> str:
    """The light-theme value of a colour token, for example color('viz-1')."""
    return _assets()["colors"][token]


def font(family: str = "sans") -> str:
    return _assets()["families"][family]


# --------------------------------------------------------------------------
# Icons (Lucide outline, 1.5px stroke)
# --------------------------------------------------------------------------
def icon(name: str, md: bool = False) -> str:
    """
    One icon from design/icons.json, at 16px (20px with md). It takes the text colour of its parent.
    The kit draws icons as inline SVG. Streamlit's st.html removes SVG elements, so the outline is a CSS
    mask on a span instead: the same shape, and it still takes the text colour.
    """
    if name not in _assets()["icons"]:
        raise KeyError(f"no icon named {name!r} in design/icons.json")
    size = " cs-icon--md" if md else ""
    return f'<span class="cs-icon{size} kit-icon kit-icon--{name}" aria-hidden="true"></span>'


# --------------------------------------------------------------------------
# Page frame
# --------------------------------------------------------------------------
def inject(product: str, nav_icons: dict[str, str], current: str) -> None:
    """Load the kit's styles, then the few rules that depend on this run: the brand row and the current page."""
    mark = quote(f"<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20'><rect width='20' height='20' rx='4' "
                 f"fill='{color('action-primary')}'/></svg>", safe="/:=, '")
    rules = [f'[data-testid="stSidebarHeader"]::before {{ content: "{esc(product)}"; background-image: url("data:image/svg+xml,{mark}"); }}']
    for key, name in nav_icons.items():
        rules.append(f".st-key-nav-{key} a {{ --kit-nav-icon: {_mask(_assets()['icons'][name])}; }}")
    rules.append(f'[data-testid="stSidebarCollapseButton"] {{ --kit-i: {_mask(_assets()["icons"]["chevron-left"])}; }}')
    rules.append(f'[data-testid="stExpandSidebarButton"] {{ --kit-i: {_mask(_assets()["icons"]["chevron-right"])}; }}')
    link = f'.st-key-nav-{current} a[data-testid="stPageLink-NavLink"]'
    rules.append(f"{link} {{ background: var(--bg-pressed); }}")
    rules.append(f"{link} p {{ font-weight: 450; }}")
    rules.append(f"{link}::before {{ background: var(--icon-primary); }}")
    st.html(f"<style>{_assets()['css']}\n" + "\n".join(rules) + "</style>")


def banner() -> str:
    """The PrototypeBanner. The kit requires it as the first element of every screen."""
    return ('<div class="cs-proto kit-banner kit-fixed"><span class="cs-proto__mark"></span>Prototype. Illustrative data.'
            f'<span class="cs-proto__by">Candidate case study by {esc(AUTHOR)}. Not an Apollo product.</span></div>')


def topbar(lead: str, text: str) -> str:
    """The content of the 48px top bar: a short lead and the date of the newest data."""
    return (f'<div class="kit-topbar kit-fixed"><span class="kit-topbar__lead">{esc(lead)}</span>'
            f'<span class="kit-topbar__text">{esc(text)}</span></div>')


def nav_group(label: str) -> str:
    return f'<p class="kit-navgroup">{esc(label)}</p>'


def page_head(title: str, sub: str) -> str:
    return (f'<div class="cs-pagehead"><div><h1 class="cs-pagehead__title">{esc(title)}</h1>'
            f'<p class="cs-pagehead__sub">{esc(sub)}</p></div></div>')


def section(title: str, sub: str = "") -> str:
    tail = f'<p class="kit-section__sub">{esc(sub)}</p>' if sub else ""
    return f'<div class="kit-sectionhead"><h2 class="kit-section">{esc(title)}</h2>{tail}</div>'


def note(text: str) -> str:
    return f'<p class="cs-note">{esc(text)}</p>'


def read(*paragraphs: str) -> str:
    """Reading copy (15px). Each paragraph is HTML: escape data with esc() and use <strong> for emphasis."""
    return "".join(f'<p class="kit-read">{p}</p>' for p in paragraphs)


def bullets(items: list[str], ordered: bool = False) -> str:
    """A list in reading copy. Each item is HTML."""
    tag = "ol" if ordered else "ul"
    return f'<{tag} class="kit-list">' + "".join(f"<li>{item}</li>" for item in items) + f"</{tag}>"


def grid(items: list[str], columns: int = 2, extra: str = "") -> str:
    cls = f"cs-grid cs-grid--{columns}" + (f" {extra}" if extra else "")
    return f'<div class="{cls}">{"".join(items)}</div>'


def card(key: str):
    """A flat kit card that can hold Streamlit elements (a chart and its head)."""
    return st.container(border=True, key=f"card-{key}")


def text_card(title: str, body: str, sub: str = "") -> str:
    """A Card with a title. body is HTML."""
    sub_html = f'<p class="cs-card__sub">{esc(sub)}</p>' if sub else ""
    return (f'<section class="cs-card"><header class="cs-card__head"><div class="cs-card__titles">'
            f'<h3 class="cs-card__title">{esc(title)}</h3>{sub_html}</div></header><div class="cs-card__body">{body}</div></section>')


def card_head(title: str, sub: str = "") -> str:
    """The head of a Card that holds Streamlit elements and is not a chart."""
    sub_html = f'<p class="cs-card__sub">{esc(sub)}</p>' if sub else ""
    return f'<div class="cs-card__titles"><h3 class="cs-card__title">{esc(title)}</h3>{sub_html}</div>'


def chart_head(title: str, sub: str) -> str:
    """The head of the kit's chart frame. The sub line states the measure, the period and 'Illustrative data'."""
    return (f'<div class="cs-chart__head"><div><h3 class="cs-chart__title">{esc(title)}</h3>'
            f'<p class="cs-chart__sub">{esc(sub)}</p></div></div>')


def figure(title: str, sub: str, body: str, legend_html: str = "", table_html: str = "", note_text: str = "") -> str:
    """The kit's chart frame around content that is drawn in HTML: Meters, a Heatmap or a funnel. body is HTML."""
    tail = table_html + (note(note_text) if note_text else "")
    return f'<figure class="cs-chart">{chart_head(title, sub)}{legend_html}<div class="cs-chart__plot">{body}</div>{tail}</figure>'


# --------------------------------------------------------------------------
# Badge, tooltip, alert
# --------------------------------------------------------------------------
def badge(text: str, tone: str = "", icon_name: str = "", dot: bool = False) -> str:
    cls = f"cs-badge cs-badge--{tone}" if tone else "cs-badge"
    lead = icon(icon_name) if icon_name else ('<span class="cs-badge__dot"></span>' if dot else "")
    return f'<span class="{cls}">{lead}{esc(text)}</span>'


def delta_badge(delta_points: float | None, significant: bool = True, up_is_good: bool = True, digits: int = 1) -> str:
    """A change in points. Green when the change is good, red when it is bad, grey when it is inside its noise band."""
    if delta_points is None or pd.isna(delta_points):
        return badge("No comparison", icon_name="minus")
    text = f"{delta_points:+.{digits}f} pts"
    if not significant or round(delta_points, digits) == 0:
        return badge(text, icon_name="minus")
    good = (delta_points > 0) == up_is_good
    return badge(text, "positive" if good else "negative", "arrow-up-right" if delta_points > 0 else "arrow-down-right")


TRUST_TONES = {"Audited": "positive", "Counted": "", "Signal": "caution", "Assumption": "info", "Modeled": "info"}


def trust_badge(level: str) -> str:
    """How far to trust a number. The word carries the meaning; the tone supports it."""
    return badge(level, TRUST_TONES.get(level, ""), dot=True)


def tip(text: str) -> str:
    """An info icon with a Tooltip that opens on hover and on keyboard focus."""
    return (f'<span class="kit-tip" tabindex="0" role="button" aria-label="Definition">{icon("info")}'
            f'<span class="cs-tooltip cs-tooltip--start" role="tooltip">{esc(text)}</span></span>')


def alert(body: str, tone: str = "", title: str = "") -> str:
    """An inline Alert. body is HTML."""
    icons = {"": "info", "positive": "circle-check", "caution": "triangle-alert", "negative": "circle-alert"}
    cls = f"cs-alert cs-alert--{tone}" if tone else "cs-alert"
    head = f'<span class="cs-alert__title">{esc(title)}</span>' if title else ""
    role = "alert" if tone == "negative" else "status"
    return f'<div class="{cls}" role="{role}">{icon(icons[tone], md=True)}<div class="cs-alert__body">{head}{body}</div></div>'


# --------------------------------------------------------------------------
# Metric tile
# --------------------------------------------------------------------------
def sparkline(values: list[float], label: str) -> str:
    """
    The kit's 12-point trend line. It has no axis: it shows shape, not values.
    The line is an SVG image (st.html removes inline SVG) and the end dot is an element, so that it stays round.
    """
    pts = [float(v) for v in values if v is not None and not pd.isna(v)]
    if len(pts) > 12:
        step = (len(pts) - 1) / 11
        pts = [pts[round(i * step)] for i in range(12)]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    xs = [2 + i * (214 / (len(pts) - 1)) for i in range(len(pts))]
    ys = [26 - 20 * (v - lo) / span for v in pts]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 220 32' preserveAspectRatio='none'><polyline fill='none' "
           f"stroke='{color('viz-other')}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' "
           f"vector-effect='non-scaling-stroke' points='{points}'/></svg>")
    return (f'<span class="cs-metric__spark kit-spark" role="img" aria-label="{esc(label)}"><span class="kit-spark__plot">'
            f'<img alt="" src="data:image/svg+xml,{quote(svg, safe="/:=,")}">'
            f'<i class="kit-spark__dot" style="left:{xs[-1] / 2.2:.2f}%;top:{ys[-1] / 0.32:.1f}%"></i></span></span>')


def metric(label: str, value: str, unit: str = "", change: str = "", period: str = "", detail: str = "",
           spark: str = "", hero: bool = False, info: str = "", plain: bool = False) -> str:
    """
    A MetricTile. change is badge HTML and spark is sparkline HTML; everything else is plain text.
    detail is one line under the change: the denominator, the sample size or the interval.
    """
    cls = "cs-metric" + (" cs-metric--hero" if hero else "") + (" cs-metric--plain" if plain else "")
    word = " kit-unit--word" if unit and unit != "%" else ""          # a word needs more air than a percent sign
    unit_html = f'<span class="cs-metric__unit{word}">{esc(unit)}</span>' if unit else ""
    info_html = tip(info) if info else ""
    foot = f'<div class="cs-metric__foot">{change}<span>{esc(period)}</span></div>' if (change or period) else ""
    extra = f'<p class="kit-metric__detail">{esc(detail)}</p>' if detail else ""
    return (f'<div class="{cls}"><p class="cs-metric__label">{esc(label)}{info_html}</p>'
            f'<p class="cs-metric__value">{esc(value)}{unit_html}</p>{foot}{extra}{spark}</div>')


# --------------------------------------------------------------------------
# Legend, meters, segment bar
# --------------------------------------------------------------------------
def legend(items: list[tuple[str, str]], line: bool = False) -> str:
    """items: (label, colour token). A swatch stands for a fill, a short stroke for a line."""
    key = "cs-linekey" if line else "cs-swatch"
    rows = "".join(f'<li><span class="{key}" style="background:var(--{esc(token)})"></span>{esc(label)}</li>' for label, token in items)
    return f'<ul class="cs-legend">{rows}</ul>'


def meter_list(rows: list[dict], maximum: float = 100.0, label: str = "", head: list[str] | None = None) -> str:
    """
    Horizontal bars with the figure printed on every row: the kit's ranked Meters.

    Each row: name, value, figure (the printed number), and optionally
      extras   more cells after the figure, as HTML
      note     one line under the row
      group    a heading above the row
      fill     a colour token for the bar, for categories with a natural order (viz-seq-*)
      tone     'negative' or 'caution': use it only with a stated threshold, and print the threshold in the note
      strong   print the row at weight 550
    head is an optional row of column labels (one for each column, '' for none).
    """
    tones = {"negative": ("negative-solid", "rust-20"), "caution": ("caution-solid", "ember-20")}
    extra_n = max((len(r.get("extras", [])) for r in rows), default=0)
    out = []
    if head:
        out += [f'<span class="kit-meter-head{" cs-num" if i >= 2 else ""}">{esc(h)}</span>' for i, h in enumerate(head)]
    for row in rows:
        if row.get("group"):
            out.append(f'<span class="kit-meter-group">{esc(row["group"])}</span>')
        width = max(0.0, min(100.0, 100 * row["value"] / maximum)) if maximum else 0.0
        fill, track = tones.get(row.get("tone", ""), (row.get("fill", ""), ""))
        fill_css = f"width:{width:.1f}%" + (f";background:var(--{fill})" if fill else "")
        track_css = f' style="background:var(--{track})"' if track else ""
        strong = " kit-meter-strong" if row.get("strong") else ""
        out.append(f'<span class="kit-meter-name{strong}">{esc(row["name"])}</span>'
                   f'<span class="cs-meter__track"{track_css} role="meter" aria-label="{esc(row["name"])}" '
                   f'aria-valuenow="{row["value"]:.1f}" aria-valuemin="0" aria-valuemax="{maximum:g}">'
                   f'<i class="cs-meter__fill" style="{fill_css}"></i></span>'
                   f'<span class="cs-num kit-meter-figure{strong}">{esc(row["figure"])}</span>')
        extras = list(row.get("extras", []))
        out += [f'<span class="cs-num kit-meter-extra">{cell}</span>' for cell in extras + [""] * (extra_n - len(extras))]
        if row.get("note"):
            out.append(f'<span class="kit-meter-note">{esc(row["note"])}</span>')
    template = f"minmax(min-content, max-content) minmax(96px, 1fr) repeat({1 + extra_n}, max-content)"
    aria = f' aria-label="{esc(label)}"' if label else ""
    return f'<div class="cs-meterlist" style="grid-template-columns:{template}"{aria}>{"".join(out)}</div>'


def segbar(parts: list[tuple[float, int, str]]) -> str:
    """
    A thin SegmentBar for a table row. parts: (share from 0 to 1, fill number 1 to 8, name).
    Use it beside figures that name each part, and put a legend above the table.
    """
    label = ", ".join(f"{name} {100 * share:.0f}%" for share, _, name in parts)
    spans = "".join(f'<span class="cs-fill-{int(fill)}" style="width:{100 * share:.1f}%"></span>' for share, fill, _ in parts if share > 0)
    return f'<span class="cs-segbar kit-segbar" role="img" aria-label="{esc(label)}">{spans}</span>'


# --------------------------------------------------------------------------
# Tables and heat grids
# --------------------------------------------------------------------------
def entity(name: str, meta: str) -> str:
    """A two-line first cell: the name, and one line about it."""
    return (f'<span class="cs-entity"><span><span class="cs-entity__name">{esc(name)}</span>'
            f'<span class="cs-entity__meta">{esc(meta)}</span></span></span>')


def table(df: pd.DataFrame, num: tuple[str, ...] = (), raw: tuple[str, ...] = (), wrap: tuple[str, ...] = (),
          label: str = "", size: str = "", foot: dict | None = None, marks: dict | None = None) -> str:
    """
    The kit's Table. Cells are escaped, except in the columns listed in raw (HTML built with this module).
    num columns align right with tabular figures. size is '', 'compact' or 'relaxed'.
    foot is an optional totals row {column: text}. marks is {(row number, column): 'is-caution'} for one marked cell;
    a marked cell also needs a badge or an icon, because colour alone does not explain it.
    """
    marks = marks or {}

    def attr(*classes: str) -> str:
        names = " ".join(c for c in classes if c)
        return f' class="{names}"' if names else ""

    def kind(c: str) -> str:
        return "is-num" if c in num else ""

    head = "".join(f'<th scope="col"{attr(kind(c))}>{esc(c)}</th>' for c in df.columns)
    body = []
    for i, record in enumerate(df.to_dict("records")):
        cells = []
        for c in df.columns:
            content = str(record[c]) if c in raw else esc(record[c])
            cells.append(f'<td{attr(kind(c), "is-wrap" if c in wrap else "", marks.get((i, c), ""))}>{content}</td>')
        body.append(f'<tr>{"".join(cells)}</tr>')
    tfoot = ""
    if foot:
        cells = "".join(f'<td{attr(kind(c))}>{esc(foot.get(c, ""))}</td>' for c in df.columns)
        tfoot = f"<tfoot><tr>{cells}</tr></tfoot>"
    cls = "cs-table" + (f" cs-table--{size}" if size else "")
    aria = f' aria-label="{esc(label)}"' if label else ""
    return (f'<div class="cs-table-wrap"><table class="{cls}"{aria}><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody>{tfoot}</table></div>')


def chart_table(df: pd.DataFrame) -> str:
    """The table view of a chart: the same numbers, so that no value is reachable only by hover."""
    head = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    rows = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in rec.values()) + "</tr>" for rec in df.to_dict("records"))
    return f'<div class="kit-tableview"><table class="cs-chart__table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'


def heat_bins(values: list[float]) -> tuple[float, float]:
    """
    Seven equal bins for a Heatmap. Returns (the top of step 1, the step size) in the values' own unit.
    Step 1 is everything under the first edge; step 7 is everything from the last edge up.
    """
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    if not clean:
        return 0.0, 1.0
    lo, hi = min(clean), max(clean)
    step = min((1, 2, 5, 10, 20), key=lambda s: (abs(s - (hi - lo) / 7), -s))      # the round step nearest to a seventh of the range
    return (lo // step) * step + step, float(step)


def heat(grid_df: pd.DataFrame, flags: pd.DataFrame | None = None, label: str = "", unit: str = "%") -> str:
    """
    The kit's Heatmap: rows by columns, one hue in seven equal steps, and the number printed in every cell.
    grid_df holds the values. flags may hold 'low' (small sample: an asterisk) or 'empty' (no data: a dash).
    """
    first, step = heat_bins(grid_df.to_numpy(dtype=float).ravel().tolist())
    head = "<th></th>" + "".join(f'<th scope="col">{esc(c)}</th>' for c in grid_df.columns)
    rows = []
    for name, values in grid_df.iterrows():
        cells = []
        for col, v in values.items():
            flag = flags.loc[name, col] if flags is not None else ""
            if flag == "empty" or pd.isna(v):
                cells.append('<td class="is-empty" aria-label="No data">&ndash;</td>')
                continue
            level = 1 if v < first else int(min(7, 2 + (v - first) // step))
            star = "*" if flag == "low" else ""
            cells.append(f'<td class="cs-heat-{level}" title="{esc(name)}, {esc(col)}: {v:.1f}{esc(unit)}">{v:.0f}{esc(unit)}{star}</td>')
        rows.append(f'<tr><th scope="row">{esc(name)}</th>{"".join(cells)}</tr>')
    steps = "".join(f'<i class="cs-heat-{i}"></i>' for i in range(1, 8))
    scale = (f'<div class="cs-scale"><span>Under {first:g}{esc(unit)}</span><span class="cs-scale__steps" aria-hidden="true">{steps}</span>'
             f'<span>{first + 5 * step:g}{esc(unit)} and over, in steps of {step:g} point{"" if step == 1 else "s"}</span></div>')
    aria = f' aria-label="{esc(label)}"' if label else ""
    return (f'<div class="kit-heatwrap"><table class="cs-heat"{aria}><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>{scale}')
