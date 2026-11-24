"""Segments - where is the yield low, which source is the cause, and where is the unmet demand?"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import kit
import metrics as mx
import mockdata as md
import ui

DIMENSIONS = {"Region": "region", "Channel": "channel", "Company size": "company_size",
              "Seniority": "seniority", "Industry": "industry"}
NATURAL_ORDER = {"company_size", "seniority"}      # size bands and levels keep their own order; the rest sort by value

ui.page_head("Where is the yield low?",
             "One average hides the story. Read the yield by segment, find the source behind a weak cell, then follow the unmet demand.")
s = ui.filter_bar()
if not s.enough:
    ui.small_sample(s.f_cur.n, s.f_base.n)
    st.stop()

# --------------------------------------------------------------------------
# Tiles: the spread across single segments
# --------------------------------------------------------------------------
by_dim = {label: mx.segment_table(s.cur, [col]) for label, col in DIMENSIONS.items()}
singles = pd.concat([t.rename(columns={DIMENSIONS[label]: "segment"}).assign(dimension=label) for label, t in by_dim.items()],
                    ignore_index=True)
singles["segment"] = singles["segment"].astype(str)
readable = singles[(singles["n"] >= mx.LOW_SAMPLE) & (singles["n"] < len(s.cur))]
requests = float(s.cur["weight"].sum())
unmet = float(s.cur.loc[~s.cur["usable"] & ~s.cur["withheld"], "weight"].sum())   # withheld is not a gap to close
tiles = []
if len(readable) >= 2:
    hi, lo = readable.loc[readable["yield_rate"].idxmax()], readable.loc[readable["yield_rate"].idxmin()]
    tiles += [
        kit.metric("Highest segment", ui.rate(hi["yield_rate"]), unit="per 100",
                   detail=f"{hi['segment']} · {int(hi['n']):,} audited requests"),
        kit.metric("Lowest segment", ui.rate(lo["yield_rate"]), unit="per 100",
                   detail=f"{lo['segment']} · {int(lo['n']):,} audited requests"),
        kit.metric("Gap between them", f"{100 * (hi['yield_rate'] - lo['yield_rate']):.1f}", unit="pts",
                   detail=f"Segments with {mx.LOW_SAMPLE} or more audited requests"),
    ]
tiles.append(kit.metric("Unmet demand", ui.millions(unmet), unit="requests",
                        detail=f"{ui.pct(unmet / requests)} of {ui.millions(requests)} requests in the {s.window}, scaled from the sample",
                        info="Customer requests that did not end with a usable contact. Withheld contacts are left out: they are not a gap to close."))
st.html(kit.grid(tiles, len(tiles)))

# --------------------------------------------------------------------------
# One measure across two dimensions, beside the root cause by source
# --------------------------------------------------------------------------
measures = {label: key for key, label in mx.METRIC_LABELS.items()}
splits = [label for label in DIMENSIONS if label != "Region"]
c1, c2 = st.columns([1, 3.2])
measure_label = ui.sticky(c1.selectbox, "Measure", list(measures), key="seg_measure", default="Usable yield")
split_label = ui.sticky(c2.segmented_control, "Split regions by", splits, key="seg_split", default="Company size",
                        required=True) or "Company size"
measure, split = measures[measure_label], DIMENSIONS[split_label]
left, right = st.columns([1.45, 1])
with left:
    seg = mx.segment_table(s.cur, ["region", split])
    values = seg.assign(value=100 * seg[measure]).pivot(index="region", columns=split, values="value")
    counts = seg.pivot(index="region", columns=split, values="n")
    flags = pd.DataFrame(np.where(counts == 0, "empty", np.where(counts < mx.LOW_SAMPLE, "low", "")),
                         index=counts.index, columns=counts.columns)
    rows_kept = [r for r in values.index if counts.loc[r].sum() > 0]
    cols_kept = [c for c in values.columns if counts[c].sum() > 0]
    values, counts, flags = values.loc[rows_kept, cols_kept], counts.loc[rows_kept, cols_kept], flags.loc[rows_kept, cols_kept]
    for frame in (values, counts, flags):
        frame.index, frame.columns = frame.index.astype(str), frame.columns.astype(str)
    unit = "" if measure == "yield_rate" else "%"
    what = "Usable contacts per 100 requests" if measure == "yield_rate" else "Percent"
    st.html(ui.figure(
        f"{measure_label} by region and {split_label.lower()}",
        f"{what}, {s.window}. An asterisk marks a cell with fewer than {mx.LOW_SAMPLE} audited requests. Illustrative data.",
        kit.heat(values, flags, label=f"{measure_label} by region and {split_label.lower()}", unit=unit),
        table=counts.map("{:,.0f}".format).rename_axis("Audited requests in each cell").reset_index(),
        note="Darker is higher. Read a cell with an asterisk as a hint, not as a number."))
with right:
    source_rows = []
    for src in md.SOURCES:
        k, n = mx.source_accuracy(s.cur, src.key)
        if n >= 30:
            row = dict(name=src.label.split(" (")[0], value=100 * k / n, figure=f"{100 * k / n:.0f}%",
                       extras=[f"±{100 * mx.half_width(k, n):.0f}", f"{n:,}"])
            if k / n < mx.ACCURACY_FLOOR:
                row.update(tone="negative", note=f"Under the {mx.ACCURACY_FLOOR:.0%} floor. Fix the feed before the merge trusts it.")
            source_rows.append(row)
    source_rows.sort(key=lambda r: -r["value"])
    if source_rows:
        source_body = kit.meter_list(source_rows, 100.0, "Audited accuracy by source", head=["", "", "Correct", "± 95%", "Audited"])
    else:
        source_body = kit.note("This slice has too few audited records for each source.")
    st.html(ui.figure(
        "Which source's records are wrong here?",
        f"Audited accuracy of the records that each source wins in the merge: correct employer and role. {s.window.capitalize()}. Illustrative data.",
        source_body,
        note="The merge takes employer and title from the most recently stamped record. Set the region to APAC to see the open incident."))

# --------------------------------------------------------------------------
# Every dimension at once
# --------------------------------------------------------------------------
top = float(np.ceil(100 * singles.loc[singles["n"] >= 30, "yield_rate"].max() / 10) * 10)


def dimension_rows(labels: list[str]) -> list[dict]:
    rows = []
    for label in labels:
        t = by_dim[label]
        t = t[t["n"] > 0]
        if DIMENSIONS[label] not in NATURAL_ORDER:
            t = t.sort_values("yield_rate", ascending=False)
        for i, r in enumerate(t.itertuples()):
            row = dict(name=str(getattr(r, DIMENSIONS[label])), value=100 * r.yield_rate, figure=ui.rate(r.yield_rate),
                       extras=[f"±{100 * r.yield_ci:.1f}", f"{r.n:,}{'*' if r.low_sample else ''}"])
            if i == 0:
                row["group"] = label
            rows.append(row)
    return rows


head = ["", "", "Per 100", "± 95%", "Audited"]
spread = kit.grid([kit.meter_list(dimension_rows(["Region", "Channel", "Company size"]), top, "Usable yield by segment", head=head),
                   kit.meter_list(dimension_rows(["Seniority", "Industry"]), top, "Usable yield by segment", head=head)],
                  2, "kit-grid--inner")
st.html(ui.figure(
    "Usable yield across each dimension", f"Usable contacts per 100 requests, {s.window}. Illustrative data.", spread,
    table=singles.loc[singles["n"] > 0, ["dimension", "segment", "n", "yield_rate", "found_rate", "complete_rate", "correct_rate"]]
    .assign(n=lambda t: t["n"].map("{:,}".format),
            **{c: (lambda t, c=c: (100 * t[c]).map("{:.1f}".format)) for c in ("yield_rate", "found_rate", "complete_rate", "correct_rate")})
    .rename(columns={"dimension": "Dimension", "segment": "Segment", "n": "Audited requests", "yield_rate": "Usable per 100",
                     "found_rate": "Found %", "complete_rate": "Complete %", "correct_rate": "Correct %"}),
    note="Regions, channels and industries are sorted by value. Size bands and seniority levels keep their own order."
         + (f" An asterisk marks a segment with fewer than {mx.LOW_SAMPLE} audited requests: treat its figure as a rough guide."
            if (singles.loc[singles["n"] > 0, "n"] < mx.LOW_SAMPLE).any() else "")))

# --------------------------------------------------------------------------
# The detail table: where to point sourcing
# --------------------------------------------------------------------------
pools = mx.segment_table(s.cur, ["region", "company_size", "channel"])
pools = pools[pools["n"] > 0].sort_values("unmet_requests", ascending=False).head(8)
unmet_col = f"Unmet requests, M in {s.n_weeks} weeks"
records = []
for r in pools.itertuples():
    shares = [r.lost_not_found / r.unmet_requests, r.lost_not_complete / r.unmet_requests, r.lost_not_correct / r.unmet_requests]
    records.append({
        "Segment": kit.entity(f"{r.region} · {r.company_size} · {r.channel}",
                              f"{r.n:,} audited requests" + (". Rough guide only." if r.low_sample else "")),
        unmet_col: f"{r.unmet_requests / 1e6:.1f}",
        "Lost at": kit.segbar([(shares[0], 1, "Not found"), (shares[1], 2, "Not complete"), (shares[2], 3, "Not correct")]),
        "Not found %": f"{100 * shares[0]:.0f}", "Not complete %": f"{100 * shares[1]:.0f}",
        "Not correct %": f"{100 * shares[2]:.0f}", "Usable per 100": ui.rate(r.yield_rate)})
st.html(
    kit.section("Where to point sourcing",
                f"The largest pools of unmet demand: requests that did not end with a usable contact, {s.window}, "
                "scaled from the sample to all requests. Withheld contacts are left out. Illustrative data.")
    + kit.legend([("Not found: buy breadth", "viz-1"), ("Not complete: buy the channel", "viz-2"),
                  ("Not correct: refresh, or fix the feed", "viz-3")])
    + kit.table(pd.DataFrame(records), num=(unmet_col, "Not found %", "Not complete %", "Not correct %", "Usable per 100"),
                raw=("Segment", "Lost at"), size="relaxed", label="Largest pools of unmet demand"))
