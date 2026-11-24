"""Method - how each number is defined, where not to trust it, and how the data flows."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st

import kit
import metrics as mx
import mockdata as md
import ui

ROOT = Path(__file__).resolve().parents[1]

ui.page_head("How each number is defined",
             "Every metric is defined once, in metrics.py, the same file that computes it. This page prints those definitions.",
             tables=False)

# --------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------
definitions = pd.DataFrame([{
    "Metric": kit.entity(d["metric"], d["pillar"]),
    "Definition": d["definition"],
    "Measured from": d["measured_from"],
    "Trust": kit.trust_badge(d["trust"]),
    "Where not to trust it": d["blind_spot"],
} for d in mx.DEFINITIONS])
st.html(kit.table(definitions, raw=("Metric", "Trust"), wrap=("Definition", "Measured from", "Where not to trust it"),
                  size="relaxed", label="Metric definitions"))

st.html(kit.section("How far to trust a number", "Every number in this prototype carries one of these labels.")
        + kit.grid([f'<div class="cs-card"><div class="cs-card__body kit-trust">{kit.trust_badge(level)}'
                    f"<p>{kit.esc(text)}</p></div></div>" for level, text in mx.TRUST_LEVELS.items()]
                   + [f'<div class="cs-card"><div class="cs-card__body kit-trust">{kit.trust_badge("Modeled")}'
                      "<p>A second run of the simulation with one change and the same random draws. Used for what-if options.</p></div></div>"],
                   5, "kit-grid--trust"))


# --------------------------------------------------------------------------
# The data flow: where the measurement sits, and where the loop closes
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def flow_diagram() -> str:
    """
    Boxes and arrows in the kit's tokens. Dark boxes are the measurement that this design adds.
    Streamlit's st.html removes inline SVG, so the diagram is an SVG image. An image cannot use the
    page's fonts, so the SVG carries the kit's product font inside it.
    """
    w, h = 160, 72
    col = [0, 192, 384, 576, 768, 960]
    row = [8, 152, 296]
    nodes = [  # column, row, title, two caption lines, new?
        (0, 0, "Sources", "Contributors, web", "crawl, licensed feeds", False),
        (1, 0, "Ingest", "Tag source, lawful", "basis, licence terms", False),
        (2, 0, "Feed gate", "Rules on every row,", "audit on a sample.", True),
        (3, 0, "Merge", "Newest independent", "observation wins", False),
        (4, 0, "Catalog", "Contacts and", "companies", False),
        (5, 0, "Suppression list", "Opt-outs, deletions:", "always withheld", False),
        (0, 1, "Decisions", "Buy, renew, cut,", "refresh", False),
        (3, 1, "Outcome signals", "Bounces, replies,", "calls, flags", False),
        (4, 1, "Delivered contacts", "What customers asked", "for and received", False),
        (5, 1, "Customer requests", "Reveals and", "enrichment", False),
        (3, 2, "Telemetry", "Usable yield, loss", "tree, scorecard", True),
        (4, 2, "Weekly blind audit", "2,500 random requests", "set the level", True),
    ]
    out = []

    def head(x: float, y: float, direction: str) -> str:
        """An arrowhead whose tip is at (x, y)."""
        a, b = 7, 4
        pts = {"right": [(x, y), (x - a, y - b), (x - a, y + b)], "left": [(x, y), (x + a, y - b), (x + a, y + b)],
               "down": [(x, y), (x - b, y - a), (x + b, y - a)], "up": [(x, y), (x - b, y + a), (x + b, y + a)]}[direction]
        return '<polygon class="head" points="' + " ".join(f"{px},{py}" for px, py in pts) + '"/>'

    def edge(path: str, x: float, y: float, direction: str) -> None:
        out.append(f'<path class="edge" d="{path}"/>{head(x, y, direction)}')

    def label(x: float, y: float, *lines: str, anchor: str = "start") -> None:
        for i, line in enumerate(lines):
            out.append(f'<text class="label" x="{x}" y="{y + 16 * i}" text-anchor="{anchor}">{kit.esc(line)}</text>')

    mid = [r + h / 2 for r in row]
    for c in range(4):                                          # the data path, left to right
        edge(f"M{col[c] + w},{mid[0]} H{col[c + 1] - 5}", col[c + 1], mid[0], "right")
    edge(f"M{col[5]},{mid[0]} H{col[4] + w + 5}", col[4] + w, mid[0], "left")            # suppression -> catalog
    edge(f"M{col[4] + w / 2},{row[0] + h} V{row[1] - 5}", col[4] + w / 2, row[1], "down")  # catalog -> delivered
    edge(f"M{col[5]},{mid[1]} H{col[4] + w + 5}", col[4] + w, mid[1], "left")            # requests -> delivered
    edge(f"M{col[4]},{mid[1]} H{col[3] + w + 5}", col[3] + w, mid[1], "left")            # delivered -> signals
    edge(f"M{col[3] + w / 2},{row[1]} V{row[0] + h + 5}", col[3] + w / 2, row[0] + h, "up")   # signals -> merge
    label(col[3] + w / 2 + 10, row[0] + h + 40, "re-verify")
    edge(f"M{col[4] + w / 2},{row[1] + h} V{row[2] - 5}", col[4] + w / 2, row[2], "down")  # delivered -> audit
    label(col[4] + w / 2 + 10, row[1] + h + 40, "blind sample")
    edge(f"M{col[3] + w / 2},{row[1] + h} V{row[2] - 5}", col[3] + w / 2, row[2], "down")  # signals -> telemetry
    label(col[3] + w / 2 + 10, row[1] + h + 40, "alerts only")
    edge(f"M{col[4]},{mid[2]} H{col[3] + w + 5}", col[3] + w, mid[2], "left")            # audit -> telemetry
    edge(f"M{col[3]},{mid[2]} H{col[0] + w / 2} V{row[1] + h + 5}", col[0] + w / 2, row[1] + h, "up")   # telemetry -> decisions
    label((col[0] + w / 2 + col[3]) / 2, mid[2] - 10, "usable yield, loss tree, source scorecard, alerts", anchor="middle")
    edge(f"M{col[0] + w / 2},{row[1]} V{row[0] + h + 5}", col[0] + w / 2, row[0] + h, "up")   # decisions -> sources
    label(col[0] + w / 2 + 10, row[0] + h + 32, "priced by cost per", "net-new usable contact")

    for c, r, title, line1, line2, new in nodes:
        x, y, mod = col[c], row[r], " new" if new else ""
        out.append(f'<rect class="node{mod}" x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="8"/>'
                   f'<text class="title{mod}" x="{x + 12}" y="{y + 24}">{kit.esc(title)}</text>'
                   f'<text class="text{mod}" x="{x + 12}" y="{y + 43}">{kit.esc(line1)}</text>'
                   f'<text class="text{mod}" x="{x + 12}" y="{y + 59}">{kit.esc(line2)}</text>')

    c = kit.color
    font = base64.b64encode((ROOT / "static" / "InterVariable-latin.woff2").read_bytes()).decode("ascii")
    style = (f'@font-face{{font-family:"Inter Variable";src:url(data:font/woff2;base64,{font}) format("woff2");font-weight:100 900}}'
             f'text{{font-family:{kit.font("sans")}}}'
             f'.node{{fill:{c("bg-primary")};stroke:{c("border-strong")}}}.node.new{{fill:{c("bg-inverse")};stroke:{c("bg-inverse")}}}'
             f'.title{{fill:{c("text-primary")};font-size:13px;font-weight:450}}.title.new{{fill:{c("text-inverse")}}}'
             f'.text{{fill:{c("text-tertiary")};font-size:12px}}.text.new{{fill:{c("sand-30")}}}'
             f'.label{{fill:{c("text-secondary")};font-size:12px}}'
             f'.edge{{fill:none;stroke:{c("sand-50")};stroke-width:1.5}}.head{{fill:{c("sand-50")}}}')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 376" width="1120" height="376"><style>{style}</style>'
           f'{"".join(out)}</svg>')
    summary = ("Data flows from sources through ingest, a feed gate, the merge and the catalog to delivered contacts. Outcome "
               "signals and a weekly blind audit feed the telemetry. The telemetry drives sourcing decisions, which change the sources.")
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="kit-flow" alt="{kit.esc(summary)}" src="data:image/svg+xml;base64,{encoded}">'


st.html(kit.figure(
    "How the data flows, and where the loop closes",
    "The path of a contact from a source to a customer, and of a measurement back to a sourcing decision. "
    "An illustrative design, not a description of Apollo's systems.",
    flow_diagram(),
    legend_html=kit.legend([("Dark boxes: the measurement that this design adds", "bg-inverse")]),
    note_text="The loop: the telemetry prices each source, the price drives sourcing, and the next audit shows whether the "
              "decision worked. The feed gate runs validity and plausibility rules on every record of a new load, then the same audit method on a sample. It passes the load or holds it."))

# --------------------------------------------------------------------------
# Guardrails
# --------------------------------------------------------------------------
g = md.guardrails()
withheld = float(mx.window(ui.load_data()[0], 4)["withheld"].mean())
guard = pd.concat([pd.DataFrame([dict(
    guardrail="Withheld share of requests", value=ui.pct(withheld), target="Report it. Never reduce it.",
    what_it_means="Requests where the catalog has the contact and does not serve it. Computed from the sample, last 4 weeks.")]), g])
guard = guard.rename(columns={"guardrail": "Guardrail", "value": "Now", "target": "Target", "what_it_means": "What it means"})
st.html(kit.section("Guardrails that sit beside the yield",
                    "A rise in yield never counts if one of these moves the wrong way. Illustrative data: the last three rows are fixed values.")
        + kit.table(guard, wrap=("What it means",), label="Guardrails")
        + kit.note("The telemetry holds counts and rates only. No personal data leaves the catalog to reach these pages. The audit "
                   "checks public primary sources and consented signals. It does not contact the person."))

# --------------------------------------------------------------------------
# About the data
# --------------------------------------------------------------------------
df = ui.load_data()[0]
about = kit.bullets([
    f"Each row is one sampled customer request: {md.ROWS_PER_WEEK:,} a week for {md.WEEKS} weeks, {len(df):,} rows. "
    f"One row stands for {md.WEIGHT:,.0f} requests.",
    "Every person has a hidden clock: months since the last job change. A source is right only if it observed the person after that change.",
    "The catalog merges sources. The most recently stamped record wins employer and title.",
    "The audit knows the truth, so every row carries the real outcome. All charts are computed from these rows.",
    "Three events are built in: the contract of Vendor A expands, the pilot of Vendor B starts in EMEA, and the feed of Vendor C "
    "re-stamps old APAC rows 4 weeks ago.",
    "Fixed, not computed: catalog row counts, the company table, and three guardrail values. Each one is marked where it appears.",
    "Same seed, same numbers. The tests recompute the headline numbers by a second route: run <code>pytest</code>.",
])
built = kit.bullets([
    "<strong>mockdata.py</strong> builds the rows. <strong>metrics.py</strong> defines every number once. "
    "<strong>charts.py</strong> and <strong>kit.py</strong> draw. <strong>views/</strong> holds one file for each page.",
    "The look is the Apollo Case Study Kit in <strong>design/</strong>: an unofficial kit made for this case study. "
    "Its tokens record what the public pages of Apollo.io show, and its components are original.",
    "Built with Streamlit and Altair, with Claude as the AI pair.",
])
st.html(kit.section("About the illustrative data", "A seeded model builds every row. Nothing here is Apollo data.")
        + kit.grid([kit.text_card("The model", about), kit.text_card("How this prototype is built", built)], 2, "kit-grid--wide-left"))
