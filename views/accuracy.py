"""Accuracy and freshness - can you trust the accuracy number, and what does the honest number cost?"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import charts as ch
import kit
import metrics as mx
import mockdata as md
import ui

ui.page_head("Can you trust the accuracy number?",
             "Accuracy is the hardest pillar to measure honestly. This page shows why, and what the honest number costs.")
s = ui.filter_bar()

# --------------------------------------------------------------------------
# Three honest answers to three different questions (email requests)
# --------------------------------------------------------------------------
no_channel = {k: v for k, v in s.filters.items() if k != "channel"}
emails = mx.window(mx.apply_filters(s.df, no_channel), s.n_weeks)
bias = mx.signal_bias(emails)
_, catalog = ui.load_data()
f_cat = mx.funnel(mx.apply_filters(catalog, no_channel).query("found"))
w13 = mx.window(s.fdf, 13)
age = mx.accuracy_by_age(w13)
jc = mx.job_change_catch(w13)

if bias["n"].min() < 100 or f_cat.complete < 100:
    ui.small_sample(int(bias["n"].min()))
else:
    signal, audited = bias.iloc[0], bias.iloc[3]
    k_aud, n_aud = int(round(audited["rate"] * audited["n"])), int(audited["n"])
    tiles = [
        kit.metric("Bounce signal says", ui.rate(signal["rate"]), unit="%", change=kit.trust_badge("Signal"),
                   detail=f"of {int(signal['n']):,} emails that customers sent", info=ui.definition("Bounce-based accuracy")),
        kit.metric("Audit says, requested contacts", ui.rate(audited["rate"]), unit="%", change=kit.trust_badge("Audited"),
                   detail=f"±{100 * mx.half_width(k_aud, n_aud):.1f} · of {n_aud:,} complete email contacts",
                   info=ui.definition("Correct rate")),
        kit.metric("Audit says, whole catalog", ui.rate(f_cat.correct_rate), unit="%", change=kit.trust_badge("Audited"),
                   detail=f"±{100 * f_cat.ci('correct_rate'):.1f} · of {f_cat.complete:,} contacts in a uniform sample",
                   info="The same audit on a uniform sample of catalog contacts. It answers a different question: how good "
                        "is a record that nobody has asked for yet?"),
    ]
    if jc["n"] >= 100:
        tiles.append(kit.metric("Job-change catch rate", ui.rate(jc["rate"], 0), unit="%", change=kit.trust_badge("Audited"),
                                detail=f"±{100 * jc['ci']:.0f} · of {jc['n']:,} contacts who changed employer in 90 days",
                                info=ui.definition("Job-change catch rate (90 days)")))
    channel_note = " The channel filter does not apply to them." if "channel" in s.active else ""
    st.html(kit.grid(tiles, len(tiles)) + kit.note(
        f"The first three tiles are for email requests, {s.window}.{channel_note} They are three honest answers to three "
        "different questions. The headline uses the second one: it is what customers pay for."))

    walk = pd.concat([bias, pd.DataFrame([dict(
        step="The same audit on the whole catalog", why="Contacts that nobody asks for are refreshed less often.",
        rate=f_cat.correct_rate, n=f_cat.complete)])], ignore_index=True)
    rows = [dict(name=r.step, value=100 * r.rate, figure=ui.pct(r.rate), extras=[f"{int(r.n):,}"],
                 note=r.why if i == 0 else f"Lower because: {r.why[0].lower()}{r.why[1:]}", strong=i == 3)
            for i, r in enumerate(walk.itertuples())]
    walk_fig = ui.figure(
        "From the signal to the truth, one blind spot at a time",
        f"Share counted as right, email requests, {s.window}. Illustrative data.",
        kit.meter_list(rows, 100.0, "From bounce-based accuracy to audited accuracy", head=["", "", "Counted as right", "Audited rows"]),
        note="The row in bold is the audited accuracy that the headline uses.")
    why_card = kit.text_card(
        "Why accuracy is the hardest pillar",
        kit.bullets([
            "<strong>The truth is in the world, not in the catalog.</strong> Breadth and depth can be counted from logs. Accuracy cannot.",
            "<strong>Fast signals look only where customers looked.</strong> A bounce covers the records that someone chose to email.",
            "<strong>Sources copy each other.</strong> Two feeds that agree are not two proofs.",
            "<strong>Accuracy has a date.</strong> A record that was right at the audit can be wrong a month later.",
        ]) + kit.read("So the page uses a blind audit, shows the interval with every accuracy number, and reads accuracy "
                      "next to freshness."))
    st.html(kit.grid([walk_fig, why_card], 2, "kit-grid--wide-left"))

# --------------------------------------------------------------------------
# Freshness explains accuracy
# --------------------------------------------------------------------------
st.html(kit.section("Freshness explains accuracy",
                    "A record can only be as right as its last independent observation. Last 13 weeks, with the page filters."))
if len(w13) < ui.MIN_ROWS or age["n"].sum() < 200:
    ui.small_sample(len(w13))
else:
    left, right = st.columns(2)
    with left:
        ui.chart_card(
            "age", "Older verification, lower accuracy",
            "Correct rate of complete contacts, percent, by time since the last recorded verification. The lines are 95% intervals. Illustrative data.",
            ch.column_chart(pd.DataFrame({"category": age["age"], "value": 100 * age["correct_rate"], "low": 100 * age["low"],
                                          "high": 100 * age["high"], "n": age["n"]}),
                            "Time since the last recorded verification", intervals=True),
            table=pd.DataFrame({"Age": age["age"], "Audited contacts": age["n"].map("{:,}".format),
                                "Correct %": (100 * age["correct_rate"]).map("{:.1f}".format),
                                "95% low": (100 * age["low"]).map("{:.1f}".format),
                                "95% high": (100 * age["high"]).map("{:.1f}".format)}))
    with right:
        share = 100 * age["share_of_delivered"]
        ui.chart_card(
            "share", "Most delivered contacts were verified lately",
            "Share of the complete contacts that customers received, percent, by the same age bands. Illustrative data.",
            ch.column_chart(pd.DataFrame({"category": age["age"], "value": share, "n": age["n"]}),
                            "Time since the last recorded verification", upper=float(max(60.0, share.max() * 1.2))),
            table=pd.DataFrame({"Age": age["age"], "Audited contacts": age["n"].map("{:,}".format),
                                "Share of delivered %": share.map("{:.1f}".format)}))
    st.html(kit.note("The refresh budget belongs on the contacts that customers ask for most. The Investments page prices that."))

# --------------------------------------------------------------------------
# What honesty costs
# --------------------------------------------------------------------------
st.html(kit.section("What honesty costs: the audit sample",
                    "The sample size is a budget choice. It sets how small a segment the dashboard can read, and how small "
                    "a change it can call. All segments, 4-week window."))
c1, c2, _ = st.columns([1, 1, 2])
rows_week = ui.sticky(c1.selectbox, "Audited requests each week", [500, 1_000, 2_500, 5_000, 10_000], key="audit_rows",
                      default=md.ROWS_PER_WEEK, format_func=lambda v: f"{v:,}")
cost_row = ui.sticky(c2.number_input, "Cost of one audited request, dollars", 0.5, 5.0, key="audit_cost", default=2.0, step=0.5)
last4 = mx.window(s.df, 4)
all_now = mx.funnel(last4)
cells = mx.segment_table(last4, ["region", "company_size"])
smallest = cells.loc[cells["n"].idxmin()]
apac_share = float((last4["region"] == "APAC").mean())
spend = sum(src.annual_cost for src in md.SOURCES)
audit_cost = rows_week * 52 * cost_row
st.html(kit.grid([
    kit.metric("Headline, 4 weeks", f"±{100 * mx.audit_precision(rows_week, 4, 1.0, all_now.yield_rate):.1f}", unit="pts",
               detail=f"{rows_week * 4:,} audited requests"),
    kit.metric("One region, 4 weeks", f"±{100 * mx.audit_precision(rows_week, 4, apac_share, 0.30):.1f}", unit="pts",
               detail=f"APAC: {apac_share:.0%} of requests, {rows_week * 4 * apac_share:,.0f} audited"),
    kit.metric("Smallest region and size cell", f"±{100 * mx.audit_precision(rows_week, 4, smallest['n'] / all_now.n, 0.25):.1f}", unit="pts",
               detail=f"{smallest['region']}, {smallest['company_size']}: {smallest['n'] / all_now.n:.1%} of requests"),
    kit.metric("Audit cost a year", f"${audit_cost / 1e3:,.0f}K", change=kit.trust_badge("Assumption"),
               detail=f"{audit_cost / spend:.1%} of the ${spend / 1e6:.2f}M yearly source spend in this prototype"),
], 4))
