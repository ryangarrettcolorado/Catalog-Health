"""Overview - is the contact data getting better or worse, what moved it, and what needs attention?"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import charts as ch
import kit
import metrics as mx
import mockdata as md
import ui

ui.page_head("Is the contact data getting better or worse?",
             "Usable yield: of every 100 contacts that customers ask for, how many are found, complete and correct.")
s = ui.filter_bar()
if not s.enough:
    ui.small_sample(s.f_cur.n, s.f_base.n)
    st.stop()

cur, base = s.f_cur, s.f_base
y = mx.change(cur, base, "yield_rate")
parts = mx.decompose(cur, base)
mix = mx.mix_adjusted_change(s.cur, s.base)
band = 100 * mx.Z95 * np.sqrt(cur.yield_rate * (1 - cur.yield_rate) / cur.n + base.yield_rate * (1 - base.yield_rate) / base.n)
tr = mx.trend(s.fdf)
tr = tr[tr["week"] > md.WEEKS - 53]
year_shape = "over the last 12 months"

# --------------------------------------------------------------------------
# The answer: one hero number and one verdict
# --------------------------------------------------------------------------
if y["z"] >= mx.Z95:
    verdict = f"Better than {s.base_phrase}."
elif y["z"] <= -mx.Z95:
    verdict = f"Worse than {s.base_phrase}."
else:
    verdict = f"No clear change from {s.base_phrase}."

PHRASES = {
    "found": ("the catalog finds more of the contacts customers ask for", "the catalog finds fewer of the contacts customers ask for"),
    "complete": ("more found contacts have the requested channel", "fewer found contacts have the requested channel"),
    "correct": ("more complete contacts are correct", "fewer complete contacts are correct"),
}
moved = sorted(PHRASES, key=lambda k: -abs(parts[k]))
drivers = "; ".join(f"{PHRASES[k][0 if parts[k] >= 0 else 1]} ({100 * parts[k]:+.1f} pts)" for k in moved)
lines = []
if not y["significant"]:
    lines.append(f"The change of {100 * y['delta']:+.1f} points is inside the noise band (±{band:.1f}). Do not act on it.")
lines.append(f"What moved the yield: {drivers}.")
if np.isfinite(mix["mix"]) and abs(100 * mix["mix"]) >= 0.3:
    direction = "lower" if mix["mix"] < 0 else "higher"
    lines.append(f"Demand moved toward segments where the yield is {direction}. With the demand mix held constant, "
                 f"the change is {100 * mix['within']:+.1f} points.")
lines.append(f"Of every 100 complete contacts that customers receive, {100 * (1 - cur.correct_rate):.0f} are wrong. "
             "That number costs trust.")

hero = kit.metric(
    "Usable yield", f"{100 * cur.yield_rate:.1f}", unit="per 100 requests",
    change=kit.delta_badge(100 * y["delta"], y["significant"]), period=s.period,
    detail=f"95% interval ±{100 * cur.ci('yield_rate'):.1f} · {cur.n:,} audited requests · {s.window}",
    spark=kit.sparkline((100 * tr["yield_rate"]).tolist(), f"Usable yield {year_shape}"),
    hero=True, info=ui.definition("Usable yield"))
verdict_card = (f'<section class="cs-card"><div class="cs-card__body"><h2 class="kit-verdict">{kit.esc(verdict)}</h2>'
                f'{kit.read(*[kit.esc(line) for line in lines])}</div></section>')
st.html(kit.grid([hero, verdict_card], 2, "kit-grid--lead"))

# --------------------------------------------------------------------------
# The four pillars. A change inside its noise band is grey.
# --------------------------------------------------------------------------
PILLARS = [
    ("found_rate", "Found rate", f"of {cur.n:,} requests"),
    ("complete_rate", "Complete rate", f"of {cur.found:,} found contacts"),
    ("correct_rate", "Correct rate", f"of {cur.complete:,} complete contacts · ±{100 * cur.ci('correct_rate'):.1f}"),
    ("fresh_rate", "Verified in 90 days", f"of {cur.found:,} found contacts"),
]
tiles = []
for metric, name, detail in PILLARS:
    c = mx.change(cur, base, metric)
    tiles.append(kit.metric(
        mx.METRIC_LABELS[metric], ui.rate(c["now"]), unit="%",
        change=kit.delta_badge(100 * c["delta"], c["significant"]), period=s.period, detail=detail,
        spark=kit.sparkline((100 * tr[metric]).tolist(), f"{name} {year_shape}"), info=ui.definition(name)))
st.html(kit.grid(tiles, 4) + kit.note("Usable yield = found × complete × correct. Freshness explains accuracy; it is not a "
                                      "fourth step. A grey change is inside its noise band. Each trend line covers 12 months."))

# --------------------------------------------------------------------------
# What needs attention. Alerts always scan every segment, whatever the filters say.
# --------------------------------------------------------------------------
al = mx.alerts(s.df)
if al.empty:
    st.html(kit.alert(kit.esc("No region and no source moved more than its noise band in the last 4 weeks."),
                      title="No alerts"))
else:
    moves = "".join(
        f'<li>{kit.icon("arrow-up-right" if r.delta > 0 else "arrow-down-right")}<span><strong>{kit.esc(r.segment)}</strong>. '
        f"{kit.esc(r.metric)}: {ui.pct(r.before)} to {ui.pct(r.now)} ({ui.pts(r.delta)})</span></li>" for r in al.itertuples())
    fresher = set(al[(al["metric"] == mx.METRIC_LABELS["fresh_rate"]) & (al["delta"] > 0)]["segment"])
    wrong = set(al[(al["metric"] == mx.METRIC_LABELS["correct_rate"]) & (al["delta"] < 0)]["segment"])
    read_together = ""
    for region in sorted(fresher & wrong):
        src = al[al["scope"] == "Source"]["segment"].tolist()
        pointer = f" The source alert points at {src[0]}." if src else ""
        read_together += (f"<span><strong>Read these together.</strong> {kit.esc(region)} looks fresher while it gets less "
                          f"accurate. That pattern means a feed re-stamped old rows as new, and the merge let them win."
                          f"{kit.esc(pointer)}</span>")
    count = f"{len(al)} move{'s' if len(al) != 1 else ''} larger than noise in the last 4 weeks"
    st.html(kit.alert(
        f'<ul class="kit-alert-list">{moves}</ul>{read_together}'
        f'<span class="kit-alert-foot">All segments, last 4 weeks vs the 4 weeks before. An alert needs a move of '
        f"{mx.ALERT_Z:.0f} standard errors, because about 25 cells are tested each week.</span>",
        tone="caution", title=count))

# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
events = ui.events_frame()
axis_start = ch.trend_domain(tr)[0]
every_fourth = tr.iloc[::-4].iloc[::-1]
ui.chart_card(
    "trend", "Usable yield over 12 months",
    f"Usable contacts per 100 requests, 4-week rolling, with the 95% interval. The axis starts at {axis_start:.0f}. Illustrative data.",
    ch.trend_chart(tr, events),
    table=pd.DataFrame({"4 weeks to": every_fourth["week_end"].dt.strftime("%d %b %Y"),
                        "Usable per 100": (100 * every_fourth["yield_rate"]).map("{:.1f}".format),
                        "95% low": (100 * every_fourth["yield_low"]).map("{:.1f}".format),
                        "95% high": (100 * every_fourth["yield_high"]).map("{:.1f}".format),
                        "Audited requests": every_fourth["n"].map("{:,.0f}".format)}),
    note="A move inside the band is noise. Events in the illustrative data: "
         + " ".join(f"{e.number}. {e.label}." for e in events.itertuples()))

# Where 100 requests go (a funnel: ordered steps take one hue in steps), and what moved the yield.
before_100 = [100.0, 100 * base.found_rate, 100 * base.found_rate * base.complete_rate, 100 * base.yield_rate]
now_100 = [100.0, 100 * cur.found_rate, 100 * cur.found_rate * cur.complete_rate, 100 * cur.yield_rate]
steps = ["Asked", "Found", "Complete", "Usable"]
funnel_rows = [dict(name=name, value=now, figure=f"{now:.1f}", fill=f"viz-seq-{3 + i}", strong=name == "Usable",
                    extras=["" if name == "Asked" else f"{then:.1f}"])
               for i, (name, now, then) in enumerate(zip(steps, now_100, before_100))]
left, right = st.columns(2)
with left:
    st.html(ui.figure(
        "Where 100 requests go", f"Contacts per 100 requests at each step, {s.window}. Illustrative data.",
        kit.meter_list(funnel_rows, 100.0, "Funnel from 100 requests to usable contacts",
                       head=["", "", "Now", s.base_phrase.capitalize()]),
        table=pd.DataFrame({"Step": steps, "Now, per 100": [f"{v:.1f}" for v in now_100],
                            f"{s.base_phrase.capitalize()}, per 100": [f"{v:.1f}" for v in before_100]}),
        note="Found, then complete, then correct. A contact is usable when it passes all three steps. "
             "The tiles above show the rate of each step."))
with right:
    ui.chart_card(
        "change", "What moved the yield",
        f"Points of usable yield from each step, {s.window} {s.period}. The three bars add up to {100 * parts['total']:+.1f}. Illustrative data.",
        ch.change_chart(parts),
        table=pd.DataFrame({"Step": ["Found", "Complete", "Correct", "Total"],
                            "Points of yield": [f"{100 * parts[k]:+.2f}" for k in ("found", "complete", "correct", "total")]}),
        note="Each bar is the effect of that step on the yield, not the change in its own rate.")

# Why requests fail, and the number this page does not use.
tree_now, tree_before = mx.loss_tree(s.cur), mx.loss_tree(s.base)
before = dict(zip(tree_before["reason"], tree_before["per_100"]))
lost = tree_now[tree_now["reason"] != "Usable"]
step_total = lost.groupby("step", observed=True)["per_100"].sum()
loss_rows, seen = [], set()
for r in lost.itertuples():
    row = dict(name=r.reason, value=r.per_100, figure=f"{r.per_100:.1f}", extras=[f"{before.get(r.reason, float('nan')):.1f}"])
    if r.step not in seen:
        seen.add(r.step)
        row["group"] = f"{r.step}: {step_total[r.step]:.1f} per 100"
    loss_rows.append(row)
top = float(max(lost["per_100"].max(), max(before.get(k, 0.0) for k in lost["reason"])))
left, right = st.columns(2)
with left:
    st.html(ui.figure(
        "Why requests fail", f"Requests per 100 that did not end with a usable contact, {s.window}. Illustrative data.",
        kit.meter_list(loss_rows, float(np.ceil(top / 5) * 5), "Failed requests by the first reason",
                       head=["", "", "Now", s.base_phrase.capitalize()]),
        table=pd.DataFrame({"Reason": lost["reason"].astype(str), "Step": lost["step"].astype(str),
                            "Audited requests": lost["rows"].map("{:,}".format), "Per 100": lost["per_100"].map("{:.1f}".format)}),
        note="Each failed request counts once, at the first step that lost it. Withheld contacts are not a gap to close."))
with right:
    size = md.catalog_size_trend()
    yields = [mx.funnel(mx.window(s.df, 4, int(w))).yield_rate for w in size["week"]]
    idx = pd.concat([
        pd.DataFrame({"quarter": size["quarter"], "series": "Catalog size, rows",
                      "index": 100 * size["contacts_m"] / size["contacts_m"].iloc[0],
                      "detail": size["contacts_m"].map(lambda v: f"{v}M contacts")}),
        pd.DataFrame({"quarter": size["quarter"], "series": "Usable yield",
                      "index": [100 * v / yields[0] for v in yields],
                      "detail": [f"{100 * v:.1f} per 100 requests" for v in yields]}),
    ])
    grow_rows = 100 * (size["contacts_m"].iloc[-1] / size["contacts_m"].iloc[0] - 1)
    grow_yield = 100 * (yields[-1] / yields[0] - 1)
    ui.chart_card(
        "index", "The number this page does not use",
        "Catalog rows and usable yield, both set to 100 a year ago. All segments. Illustrative data; the row counts are fixed values.",
        ch.index_chart(idx, emphasis="Usable yield"),
        table=idx.assign(index=idx["index"].map("{:.1f}".format)).rename(
            columns={"quarter": "Quarter", "series": "Series", "index": "Index", "detail": "Value"})[["Series", "Quarter", "Index", "Value"]],
        legend=kit.legend([("Usable yield", "viz-emphasis"), ("Catalog size, rows", "viz-other")], line=True),
        note=f"Catalog rows grew {grow_rows:.0f}% in a year and usable yield grew {grow_yield:.0f}%. A row count rises "
             "whenever a file is loaded. It cannot say whether a customer got a usable contact.")

# --------------------------------------------------------------------------
# The detail table
# --------------------------------------------------------------------------
dim, dim_label = ("company_size", "Company size") if "region" in s.active else ("region", "Region")
now_seg = mx.segment_table(s.cur, [dim]).set_index(dim)
then_seg = mx.segment_table(s.base, [dim]).set_index(dim)
change_col = f"Change {s.period}"
records = []
for name, r in now_seg.iterrows():
    if r["n"] == 0:
        continue
    b = then_seg.loc[name]
    z = mx.z_change(r["usable"], r["n"], b["usable"], b["n"])
    delta = 100 * (r["yield_rate"] - b["yield_rate"]) if b["n"] else None
    meta = f"{int(r['n']):,} audited requests" + (". Treat the figures as a rough guide." if r["low_sample"] else "")
    records.append({dim_label: kit.entity(str(name), meta), "Found %": ui.rate(r["found_rate"]),
                    "Complete %": ui.rate(r["complete_rate"]), "Correct %": ui.rate(r["correct_rate"]),
                    "Usable per 100": ui.rate(r["yield_rate"]), "± 95%": ui.rate(r["yield_ci"]),
                    change_col: kit.delta_badge(delta, abs(z) >= mx.Z95)})
numeric = ("Found %", "Complete %", "Correct %", "Usable per 100", "± 95%")
st.html(kit.section(f"Usable yield by {dim_label.lower()}",
                    f"{s.window.capitalize()}, {s.period}. Illustrative data.")
        + kit.table(pd.DataFrame(records), num=numeric, raw=(dim_label, change_col), size="relaxed",
                    label=f"Usable yield by {dim_label.lower()}",
                    foot={dim_label: f"All in this view · {cur.n:,} audited requests", "Found %": ui.rate(cur.found_rate),
                          "Complete %": ui.rate(cur.complete_rate), "Correct %": ui.rate(cur.correct_rate),
                          "Usable per 100": ui.rate(cur.yield_rate), "± 95%": ui.rate(cur.ci("yield_rate")),
                          change_col: ui.pts(y["delta"])}))

# --------------------------------------------------------------------------
# Companies in brief, and a way to check the numbers
# --------------------------------------------------------------------------
left, right = st.columns(2)
with left:
    comp = md.company_strip()
    comp_table = pd.DataFrame({"Company metric": comp["metric"], "Now": comp["now"].map("{:.1f}%".format),
                               "A year ago": comp["year_ago"].map("{:.1f}%".format),
                               "Change": (comp["now"] - comp["year_ago"]).map("{:+.1f} pts".format)})
    st.html(kit.figure(
        "Companies, in brief", "The same four pillars for companies. Fixed illustrative values, not computed from the sample.",
        kit.chart_table(comp_table),
        note_text="Company telemetry is out of scope for this prototype on purpose. Contact data decays faster, and "
                  "contacts are what customers spend credits on."))
with right:
    with kit.card("check"):
        st.html(kit.card_head("Check these numbers",
                              "Download the audited requests behind this view. Count the rows where usable is TRUE and "
                              "divide by the number of rows. The result is the usable yield at the top of this page."))
        st.download_button("Download rows as CSV", data=lambda d=s.cur: ui.rows_as_csv(d), file_name="audited_requests.csv",
                           mime="text/csv", type="primary", on_click="ignore", key="download_rows")
