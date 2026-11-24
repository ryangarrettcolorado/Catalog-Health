"""
Checks that do not trust the dashboard code.

Each test recomputes a number by a second route (plain Python loops, or a fresh
run of the simulation) and compares it with what metrics.py reports.

Run:  pytest -q
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metrics as mx      # noqa: E402
import mockdata as md     # noqa: E402


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return md.simulate()


@pytest.fixture(scope="module")
def last4(df) -> pd.DataFrame:
    return mx.window(df, 4)


def test_same_seed_gives_the_same_rows(df):
    again = md.simulate()
    pd.testing.assert_frame_equal(df, again)


def test_funnel_matches_a_row_by_row_count(last4):
    n = found = complete = usable = 0
    for row in last4[["found", "complete", "usable"]].itertuples(index=False):
        n += 1
        found += 1 if row.found else 0
        complete += 1 if row.complete else 0
        usable += 1 if row.usable else 0
    f = mx.funnel(last4)
    assert (f.n, f.found, f.complete, f.usable) == (n, found, complete, usable)
    assert n == 4 * md.ROWS_PER_WEEK


def test_funnel_steps_nest(df):
    # usable implies complete implies found, on every row
    assert not (df["usable"] & ~df["complete"]).any()
    assert not (df["complete"] & ~df["found"]).any()


def test_yield_is_the_product_of_the_three_steps(last4):
    f = mx.funnel(last4)
    assert math.isclose(f.yield_rate, f.found_rate * f.complete_rate * f.correct_rate, rel_tol=1e-12)


def test_decomposition_adds_up_to_the_total_change(df, last4):
    base = mx.window(df, 4, md.WEEKS - 52)
    parts = mx.decompose(mx.funnel(last4), mx.funnel(base))
    assert math.isclose(parts["found"] + parts["complete"] + parts["correct"], parts["total"], abs_tol=1e-12)
    assert math.isclose(parts["total"], last4["usable"].mean() - base["usable"].mean(), abs_tol=1e-12)


def test_mix_adjustment_splits_the_raw_change(df, last4):
    base = mx.window(df, 4, md.WEEKS - 52)
    mix = mx.mix_adjusted_change(last4, base)
    raw = last4["usable"].mean() - base["usable"].mean()
    assert math.isclose(mix["within"] + mix["mix"], raw, abs_tol=1e-12)


def test_every_request_has_exactly_one_reason(last4):
    f = mx.funnel(last4)
    tree = mx.loss_tree(last4)
    by_step = tree.groupby("step")["rows"].sum()
    assert tree["rows"].sum() == f.n
    assert by_step["Usable"] == f.usable
    assert by_step["Not found"] == f.n - f.found
    assert by_step["Not complete"] == f.found - f.complete
    assert by_step["Not correct"] == f.complete - f.usable
    assert ((last4["reason"] == "Usable") == last4["usable"]).all()


@pytest.mark.parametrize("key", md.SOURCE_KEYS)
def test_leave_one_out_matches_a_real_rerun_without_the_source(key):
    """The scorecard uses stored bit masks. Here the source is really removed and the model is run again."""
    span = (md.WEEKS - 5, md.WEEKS)
    with_all = md.simulate(weeks=span)
    removed = md.simulate({"coverage_boost": {(key, region): 0.0 for region in md.REGIONS}}, weeks=span)
    from_masks = mx.usable_without(with_all, key)
    assert (from_masks.to_numpy() == removed["usable"].to_numpy()).all()


def test_wilson_interval_against_a_known_value():
    lo, hi = mx.wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=5e-4)
    assert hi == pytest.approx(0.5962, abs=5e-4)


def test_scorecard_arithmetic(df, last4):
    d26 = mx.window(df, 26)
    sc = mx.source_scorecard(d26, last4, 0.20)
    assert np.allclose(sc["net_new_usable"], sc["helps"] - sc["harms"])
    assert np.allclose(sc["cost_per_net_new_usable"], sc["annual_cost"] / sc["net_new_usable"])
    # by hand for one source: count rows, scale to all requests, annualise
    bit = 1 << md.IDX["vendor_b"]
    helps = sum(1 for m in d26["helps_mask"] if m & bit)
    harms = sum(1 for m in d26["harms_mask"] if m & bit)
    by_hand = (helps - harms) * md.WEIGHT * 52 / 26
    assert sc.set_index("key").loc["vendor_b", "net_new_usable"] == pytest.approx(by_hand)


def test_the_story_the_dashboard_tells_still_holds(df, last4):
    """Guards the storyline. If one of these fails after a change, the page text needs a review."""
    f = mx.funnel(last4)
    assert 0.40 < f.yield_rate < 0.48
    year = mx.change(f, mx.funnel(mx.window(df, 4, md.WEEKS - 52)), "yield_rate")
    assert year["delta"] > 0 and year["significant"]                      # better than a year ago
    month = mx.change(f, mx.funnel(mx.window(df, 4, md.WEEKS - 4)), "yield_rate")
    assert not month["significant"]                                       # no clear change in 4 weeks
    al = mx.alerts(df)
    assert {"APAC", "Vendor C (APAC business data)"} <= set(al["segment"])  # the open incident is caught
    sc = mx.source_scorecard(mx.window(df, 26), last4, 0.20).set_index("key")
    assert sc.loc["vendor_d", "rank_per_record"] == 1                      # cheapest per record ...
    assert sc.loc["vendor_d", "rank_per_usable"] == len(md.SOURCES)        # ... most expensive per usable contact
    assert sc.loc["contributor", "rank_per_usable"] == 1
    assert sc.loc["vendor_c", "call"] == "Fix the feed first"
    assert sc.loc["vendor_d", "call"] == "Cut"


# --------------------------------------------------------------------------
# Added after the panel dry run: the guardrail, the range, and the overlap
# --------------------------------------------------------------------------
def test_wrong_delivered_is_recounted_row_by_row(last4):
    f = mx.funnel(last4)
    by_hand = sum(1 for c, u in zip(last4["complete"], last4["usable"]) if c and not u)
    assert f.wrong_rate == pytest.approx(by_hand / len(last4))
    # the guardrail and the yield split the complete contacts between them
    assert f.wrong_rate + f.yield_rate == pytest.approx(f.complete / f.n)


def test_the_verdict_is_mixed_when_yield_and_wrong_contacts_both_rise(df, last4):
    f, base = mx.funnel(last4), mx.funnel(mx.window(df, 4, md.WEEKS - 52))
    y, w = mx.change(f, base, "yield_rate"), mx.change(f, base, "wrong_rate")
    assert y["z"] >= mx.Z95 and w["z"] >= mx.Z95
    assert mx.verdict(y, w, "a year ago").startswith("Mixed")
    calm = dict(z=0.0)
    assert mx.verdict(y, calm, "a year ago") == "Better than a year ago."
    assert mx.verdict(calm, w, "a year ago").startswith("Worse")
    assert mx.verdict(calm, calm, "a year ago").startswith("No clear change")


def test_the_cost_range_holds_the_point_estimate(df, last4):
    sc = mx.source_scorecard(mx.window(df, 26), last4, 0.20).set_index("key")
    assert ((sc["cost_low"] <= sc["cost_per_net_new_usable"]) & (sc["cost_per_net_new_usable"] <= sc["cost_high"])).all()
    d = sc.loc["vendor_d"]
    assert d["cost_high"] / d["cost_low"] > 2          # few net rows, so a wide range: do not read $0.80 as exact


def test_withheld_requests_are_not_unmet_demand(last4):
    t = mx.segment_table(last4, ["region"])
    per_row = md.WEIGHT * 4 / last4["week"].nunique()
    by_hand = sum(1 for u, w in zip(last4["usable"], last4["withheld"]) if not u and not w) * per_row
    assert t["unmet_requests"].sum() == pytest.approx(by_hand)
    assert np.allclose(t["unmet_requests"], t["lost_not_found"] + t["lost_not_complete"] + t["lost_not_correct"])


def test_a_source_is_worth_more_when_its_nearest_overlap_goes():
    """Leave-one-out holds for one removal at a time. Vendor D is cheap insurance against the loss of Vendor A."""
    span = (md.WEEKS - 25, md.WEEKS)
    base = mx.source_scorecard(md.simulate(weeks=span), md.simulate(weeks=span), 0.20).set_index("key")
    gone = md.simulate({"coverage_boost": {("vendor_a", r): 0.0 for r in md.REGIONS}}, weeks=span)
    without_a = mx.source_scorecard(gone, gone, 0.20).set_index("key")
    assert without_a.loc["vendor_a", "net_new_usable"] == 0
    assert without_a.loc["vendor_d", "cost_per_net_new_usable"] < 0.25 * base.loc["vendor_d", "cost_per_net_new_usable"]
