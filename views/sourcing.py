"""Sourcing - which sources earn their cost, and who depends on whom?"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import charts as ch
import kit
import metrics as mx
import mockdata as md
import ui

CALL_BADGES = {     # call -> (tone, icon)
    "Expand": ("positive", "arrow-up-right"),
    "Hold": ("", "minus"),
    "Reprice or re-scope": ("caution", "refresh-cw"),
    "Cut": ("negative", "x"),
    "Fix the feed first": ("caution", "triangle-alert"),
}

ui.page_head("Which sources earn their cost?",
             "One number drives sourcing: cost per net-new usable contact. Take the source out, run the merge again, and count what customers lose.")
c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
value = ui.sticky(c1.number_input, "Value of one usable contact, dollars", 0.05, 2.0, key="value_per_usable", default=0.20,
                  step=0.05)
c2.html(kit.note(f"An assumption: what one usable contact in a customer's hands is worth. It sets the break-even line and the calls. "
                 f"All segments, last {ui.SCORE_WEEKS} weeks to {ui.DATA_DATE}, scaled to a year. Contract costs cover the whole "
                 "catalog, so this page has no segment filters. Illustrative data."))

df = ui.load_data()[0]
d26, recent = mx.window(df, ui.SCORE_WEEKS), mx.window(df, 4)
sc = mx.source_scorecard(d26, recent, value).sort_values("cost_per_net_new_usable").reset_index(drop=True)
spend = float(sc["annual_cost"].sum())
best, worst = sc.iloc[0], sc.iloc[-1]
no_backup = mx.single_source_share(d26)

st.html(kit.grid([
    kit.metric("Source spend", f"${spend / 1e6:.2f}M", unit="a year", detail=f"{len(sc)} sources, contract and run cost",
               change=kit.trust_badge("Counted")),
    kit.metric("Lowest cost per net-new usable", ui.dollars(best["cost_per_net_new_usable"]),
               detail=f"{best['source']} · {ui.millions(best['net_new_usable'])} net-new usable a year",
               change=kit.trust_badge("Audited"), info=ui.definition("Cost per net-new usable contact")),
    kit.metric("Highest cost per net-new usable", ui.dollars(worst["cost_per_net_new_usable"]),
               detail=f"{worst['source']} · {ui.millions(worst['net_new_usable'])} net-new usable a year",
               change=kit.trust_badge("Audited")),
    kit.metric("No backup source", ui.rate(no_backup, 0), unit="%", change=kit.trust_badge("Audited"),
               detail="of usable contacts stop being usable if one particular source goes away"),
], 4))

# --------------------------------------------------------------------------
# The two rankings, and the break-even line
# --------------------------------------------------------------------------
cheapest = sc.loc[sc["rank_per_record"].idxmin()]
left, right = st.columns([1.15, 1])
with left:
    flip_note = (f"{cheapest['source']} has the cheapest record. By cost per net-new usable contact it ranks "
                 f"{int(cheapest['rank_per_usable'])} of {len(sc)}.")
    if cheapest["key"] == "vendor_d":
        flip_note += " It mostly copies the upstream of Vendor A, so almost nothing that it sends is new."
    ui.chart_card(
        "flip", "The cheapest record is the most expensive contact",
        f"Each source ranked two ways; 1 is cheapest. Last {ui.SCORE_WEEKS} weeks, scaled to a year. Illustrative data.",
        ch.rank_flip_chart(sc, emphasis=cheapest["source"]),
        table=pd.DataFrame({"Source": sc["source"], "$ per record": sc["cost_per_record"].map("{:.4f}".format),
                            "Rank": sc["rank_per_record"], "$ per net-new usable": sc["cost_per_net_new_usable"].map("{:.3f}".format),
                            "Rank ": sc["rank_per_usable"]}),
        legend=kit.legend([(cheapest["source"], "viz-emphasis"), ("Other sources", "viz-other")], line=True),
        note=flip_note)
with right:
    opts = pd.DataFrame({"name": sc["source"].str.split(" (", regex=False).str[0], "kind": sc["kind"], "cost": sc["cost_per_net_new_usable"],
                         "net_m": sc["net_new_usable"] / 1e6, "annual_cost_m": sc["annual_cost"] / 1e6})
    ui.chart_card(
        "breakeven", "Against the break-even value",
        f"Dollars per net-new usable contact. The line is the assumed value of one usable contact, ${value:.2f}. Illustrative data.",
        ch.cost_chart(opts, value, {"First-party": "viz-1", "Licensed": "viz-2"}),
        table=pd.DataFrame({"Source": sc["source"], "Kind": sc["kind"], "$ per net-new usable": sc["cost_per_net_new_usable"].map(ui.dollars),
                            "Net-new usable, M a year": (sc["net_new_usable"] / 1e6).map("{:.1f}".format),
                            "Cost, $M a year": (sc["annual_cost"] / 1e6).map("{:.2f}".format)}),
        legend=kit.legend([("First-party", "viz-1"), ("Licensed", "viz-2")]),
        note="A source to the left of the line pays for itself at the assumed value.")

# --------------------------------------------------------------------------
# The detail table: the scorecard
# --------------------------------------------------------------------------
accuracy_col = "Accuracy when it wins, %"
records, marks = [], {}
for i, r in enumerate(sc.itertuples()):
    tone, icon_name = CALL_BADGES.get(r.call, ("", ""))
    accuracy = f"{100 * r.accuracy:.0f}"
    if r.accuracy_recent < mx.ACCURACY_FLOOR:
        accuracy += " " + kit.badge(f"{100 * r.accuracy_recent:.0f} in the last 4 weeks", "caution", "triangle-alert")
        marks[(i, accuracy_col)] = "is-caution"
    records.append({
        "Source": kit.entity(r.source, f"{r.kind} · ${r.annual_cost / 1e6:.2f}M a year · ${r.cost_per_record:.3f} a record"),
        "Call": kit.badge(r.call, tone, icon_name),
        "$ per net-new usable": ui.dollars(r.cost_per_net_new_usable).lstrip("$"),
        "Net-new usable, M a year": f"{r.net_new_usable / 1e6:.1f}",
        "Adds, M": f"{r.helps / 1e6:.1f}",
        "Breaks, M": f"{r.harms / 1e6:.1f}",
        accuracy_col: accuracy})
numeric = ("$ per net-new usable", "Net-new usable, M a year", "Adds, M", "Breaks, M", accuracy_col)
st.html(
    kit.section("Source scorecard", f"Last {ui.SCORE_WEEKS} weeks, scaled to a year. One delivery counts once, so a contact "
                                    "that customers ask for often counts more. Illustrative data.")
    + kit.table(pd.DataFrame(records), num=numeric, raw=("Source", "Call", accuracy_col), size="relaxed", marks=marks,
                label="Source scorecard")
    + kit.note("Net-new usable = adds minus breaks. Adds: usable contacts that would not be usable without the source. Breaks: "
               "contacts that would be usable if the source were removed, because its wrong or stale record wins the merge. "
               f"Accuracy: audited employer and role on the records that the source wins. The call follows a fixed rule: expand at half "
               f"the value or less with accuracy of {mx.EXPAND_ACCURACY:.0%} or more; hold up to the value; reprice or re-scope up to "
               f"3 times the value; cut above that; and fix the feed first when accuracy in the last 4 weeks is under "
               f"{mx.ACCURACY_FLOOR:.0%}. The call starts the review. It does not end it."))

# --------------------------------------------------------------------------
# Dependence
# --------------------------------------------------------------------------
st.html(kit.section("Who depends on whom",
                    "A source that one segment cannot lose is a single point of failure, one licence clause away from a hole."))
left, right = st.columns([1.5, 1])
with left:
    split = ui.sticky(st.segmented_control, "Split by", ["Region", "Channel"], key="dep_split", default="Region",
                      required=True) or "Region"
    dep = mx.source_dependence(d26, "region" if split == "Region" else "channel")
    grid = dep.assign(value=100 * dep["share_lost"]).pivot(index="source", columns="segment", values="value")
    order = grid.max(axis=1).sort_values(ascending=False).index
    grid = grid.loc[order, md.REGIONS if split == "Region" else md.CHANNELS]
    st.html(ui.figure(
        "Usable contacts lost without each source",
        f"Percent of each {split.lower()}'s usable contacts that customers would lose. Last {ui.SCORE_WEEKS} weeks. Illustrative data.",
        kit.heat(grid, label=f"Usable contacts lost without each source, by {split.lower()}"),
        table=dep.drop_duplicates("segment")[["segment", "n_usable"]].assign(n_usable=lambda t: t["n_usable"].map("{:,}".format))
        .rename(columns={"segment": split, "n_usable": "Usable contacts in the sample"}),
        note="Sources are sorted by their largest cell. Darker is a larger loss."))
with right:
    labels = [src.label for src in md.SOURCES]
    what_if = ui.sticky(st.selectbox, "Remove a source", labels, key="dep_remove", default=cheapest["source"])
    src = next(src for src in md.SOURCES if src.label == what_if)
    without = float(mx.usable_without(d26, src.key).mean())
    today = float(d26["usable"].mean())
    st.html(kit.grid([
        kit.metric("Usable yield without it", f"{100 * without:.1f}", unit="per 100 requests",
                   change=kit.delta_badge(100 * (without - today)), period="vs today",
                   detail=f"Today: {100 * today:.1f} per 100, last {ui.SCORE_WEEKS} weeks"),
        kit.metric("Cost saved", f"${src.annual_cost / 1e6:.2f}M", unit="a year",
                   detail=f"{src.kind} source, {src.records_m}M records"),
    ], 1))
