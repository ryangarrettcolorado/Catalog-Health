"""Investments - where does the next data dollar go, and what was left out?"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import charts as ch
import kit
import metrics as mx
import ui

ui.page_head("Where does the next data dollar go?",
             "Buying a source, refreshing stale records and growing first-party signals compete for one budget. "
             "So this page compares them on one unit: dollars per net-new usable contact.")

# --------------------------------------------------------------------------
# Assumptions: they scope everything below, like a filter bar
# --------------------------------------------------------------------------
INPUTS = [  # key, label, minimum, maximum, default, step, format
    ("value_per_usable", "Value of one usable contact, dollars", 0.05, 2.0, 0.20, 0.05, None),
    ("inv_check", "Cost of one re-verification, dollars", 0.005, 0.50, 0.02, 0.005, "%.3f"),
    ("inv_fix", "Share of stale records that a re-verification fixes", 0.2, 0.9, 0.6, 0.05, None),
    ("inv_distinct", "Distinct contacts requested a year, millions", 10, 200, 45, 5, None),
    ("inv_b", "Vendor B: 50% more EMEA coverage, $M a year", 0.1, 3.0, 0.55, 0.05, None),
    ("inv_c", "Contributor network: 50% more outside North America, $M a year", 0.1, 3.0, 0.60, 0.05, None),
    ("inv_gate", "Feed gate before the merge, $M a year", 0.05, 1.0, 0.15, 0.05, None),
    ("inv_audit", "Blind audit sample, $M a year", 0.05, 2.0, 0.26, 0.01, None),
]
with st.expander("Assumptions. Change them and the page follows"):
    for start in (0, 4):
        for col, (key, label, low, high, default, step, fmt) in zip(st.columns(4, vertical_alignment="bottom"), INPUTS[start:start + 4]):
            ui.sticky(col.number_input, label, low, high, key=key, default=default, step=step, format=fmt)
value, cost_check, fix_rate, distinct, cost_b, cost_c, cost_gate, cost_audit = (st.session_state[f"kept.{key}"] for key, *_ in INPUTS)

df = ui.load_data()[0]
gains = ui.load_scenarios()
d26, recent = mx.window(df, ui.SCORE_WEEKS), mx.window(df, 4)
tiers = mx.refresh_tiers(d26, distinct * 1e6, 4, cost_check, fix_rate)
sc = mx.source_scorecard(d26, recent, value)
vd = sc[sc["key"] == "vendor_d"].iloc[0]
va = sc[sc["key"] == "vendor_a"].iloc[0]
incident_m = gains["no_incident"] / 1e6 * ui.SCORE_WEEKS / 52      # usable contacts lost so far, millions

rows = [dict(name=f"Refresh each quarter: {t.tier.lower()} of requested contacts", kind="Refresh existing records",
             basis="Assumption", net=t.net_new_usable, annual_cost=t.annual_cost) for t in tiers.itertuples()]
rows += [
    dict(name="Expand Vendor B in EMEA (50% more coverage)", kind="Buy or build coverage", basis="Modeled",
         net=gains["vendor_b"], annual_cost=cost_b * 1e6),
    dict(name="Grow the contributor network outside North America (50%)", kind="Buy or build coverage", basis="Modeled",
         net=gains["contributor"], annual_cost=cost_c * 1e6),
    dict(name="Keep Vendor D (bulk email lists)", kind="Buy or build coverage", basis="Audited",
         net=vd["net_new_usable"], annual_cost=vd["annual_cost"]),
]
inv = pd.DataFrame(rows)
inv["cost"] = np.where(inv["net"] > 0, inv["annual_cost"] / inv["net"].where(inv["net"] > 0), np.inf)
inv["net_m"], inv["annual_cost_m"] = inv["net"] / 1e6, inv["annual_cost"] / 1e6
inv["break_even_m"] = inv["net"] * value / 1e6
inv = inv.sort_values("cost").reset_index(drop=True)
top = tiers.iloc[0]
new_options = inv[inv["name"] != "Keep Vendor D (bulk email lists)"]
cheapest, largest = new_options.iloc[0], new_options.loc[new_options["net"].idxmax()]

st.html(kit.grid([
    kit.metric("Lowest cost per net-new usable", ui.dollars(cheapest["cost"]), detail=cheapest["name"],
               change=kit.trust_badge(cheapest["basis"])),
    kit.metric("Largest gain in usable contacts", ui.millions(largest["net"]), unit="a year", detail=largest["name"],
               change=kit.trust_badge(largest["basis"])),
    kit.metric("Lost to the open incident", f"{incident_m:.2f}M", unit="in 4 weeks",
               detail="Usable contacts. Vendor C re-stamped its APAC feed.", change=kit.trust_badge("Modeled")),
    kit.metric("Savings on the table", f"${vd['annual_cost'] / 1e6:.2f}M", unit="a year",
               detail=f"Cut Vendor D. Customers lose {ui.millions(vd['net_new_usable'])} usable contacts a year.",
               change=kit.trust_badge("Audited")),
], 4))

# --------------------------------------------------------------------------
# The recommendation, then what was left out
# --------------------------------------------------------------------------
e = kit.esc
next_five = kit.bullets([
    f"<strong>Keep the blind audit running</strong> (${cost_audit:.2f}M a year). It is the only honest accuracy number in this "
    "prototype. Every item below depends on it.",
    f"<strong>Refresh by demand rank, the top 5% first.</strong> {ui.millions(top.net_new_usable)} net-new usable contacts a year "
    f"at {ui.dollars(top.cost_per_net_new_usable)} each. Stop where the cost crosses the best source.",
    f"<strong>Expand Vendor B in EMEA.</strong> Phone requests in EMEA are the largest pool of unmet demand with a proven source: "
    f"{ui.millions(gains['vendor_b'])} more usable contacts a year. Pay up to ${gains['vendor_b'] * value / 1e6:.2f}M.",
    f"<strong>Grow the contributor network outside North America.</strong> It is the cheapest and freshest source, and most of "
    f"its value is still in one region: {ui.millions(gains['contributor'])} more usable contacts a year.",
    f"<strong>Gate every feed load with the audit before it can win the merge</strong> (${cost_gate:.2f}M a year). The open "
    f"Vendor C incident has cost {incident_m:.2f}M usable contacts in 4 weeks, and it made APAC look fresher while it did so.",
], ordered=True)
pay = kit.read(
    f"<strong>Pay for it.</strong> Cut Vendor D: it saves ${vd['annual_cost'] / 1e6:.2f}M, and customers lose "
    f"{ui.millions(vd['net_new_usable'])} usable contacts a year at {e(ui.dollars(vd['cost_per_net_new_usable']))} each. "
    f"Tie the renewal of Vendor A to accuracy: when its record wins the merge, it is right {100 * va['accuracy']:.0f}% of the time.")
said_no = kit.bullets([
    "<strong>A composite health score.</strong> A weighted index hides the tradeoff between pillars, and nobody can act on “82”.",
    "<strong>Catalog size as a KPI.</strong> It goes up when a file is loaded.",
    "<strong>Company-level depth.</strong> Same method, later. Contacts decay faster and carry the credits.",
    "<strong>Entity-resolution telemetry.</strong> Duplicates and parent-child links need their own measures.",
    "<strong>A view for each customer.</strong> This prototype is for sourcing decisions, not account health.",
])
st.html(kit.grid([kit.text_card("The next five investments, in order", next_five + pay),
                  kit.text_card("What was left out, on purpose", said_no)], 2, "kit-grid--wide-left"))

# --------------------------------------------------------------------------
# The evidence
# --------------------------------------------------------------------------
st.html(kit.section("The evidence, on one unit",
                    f"Each option against the assumed value of one usable contact, ${value:.2f}. Illustrative data."))
ui.chart_card(
    "options", "Dollars per net-new usable contact, by option",
    "Yearly cost divided by the usable contacts that the option adds in a year. A bar longer than the scale is cut at the edge. Illustrative data.",
    ch.cost_chart(inv, value, {"Refresh existing records": "viz-1", "Buy or build coverage": "viz-2"}, cap=max(1.0, 4 * value)),
    legend=kit.legend([("Refresh existing records", "viz-1"), ("Buy or build coverage", "viz-2")]),
    note="Refresh pays only at the head of demand. Past the top 10% of requested contacts it is cheaper to buy coverage.")

table = pd.DataFrame({
    "Option": inv["name"],
    "Basis": inv["basis"].map(kit.trust_badge),
    "$ per net-new usable": inv["cost"].map(lambda v: ui.dollars(v).lstrip("$")),
    "Net-new usable, M a year": inv["net_m"].map("{:.1f}".format),
    "Cost, $M a year": inv["annual_cost_m"].map("{:.2f}".format),
    "Break-even budget, $M a year": inv["break_even_m"].map("{:.2f}".format),
})
st.html(kit.table(table, num=("$ per net-new usable", "Net-new usable, M a year", "Cost, $M a year", "Break-even budget, $M a year"),
                  raw=("Basis",), label="Investment options")
        + kit.note("Break-even budget = net-new usable × the assumed value: pay less than this. Audited: measured on the sample. "
                   "Modeled: a second run of the simulation with the same random draws, so that any difference comes from the "
                   "change. Assumption: driven by the inputs at the top of the page."))
