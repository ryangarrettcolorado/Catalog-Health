"""
metrics.py - every number on the dashboard is defined here, once.

The app only draws. If a definition changes, it changes in this file, and the
"Method" page (which reads DEFINITIONS below) changes with it.

All functions take the audited request sample from mockdata.simulate(): one row
per sampled customer request, with the audit outcome on the row.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt

import numpy as np
import pandas as pd

import mockdata as md

Z95 = 1.96
LOW_SAMPLE = 200        # below this many rows a number is marked "low sample"
ALERT_Z = 3.0           # an alert needs a move of 3 standard errors, because many cells are tested
FRESH_MONTHS = 3.0      # "verified in the last 90 days"
ACCURACY_FLOOR = 0.70   # a source whose winning records fall below this gets a "fix the feed" call
EXPAND_ACCURACY = 0.80  # a source is only expanded if its winning records are at least this accurate

AGE_BINS = [0, 1, 3, 6, 12, np.inf]
AGE_LABELS = ["0-30 days", "31-90 days", "91-180 days", "181-365 days", "Over 1 year"]

# Funnel step that each loss reason belongs to.
REASON_STEP = {
    "Not in catalog": "Not found",
    "Withheld (opt-out, deletion, licence)": "Not found",
    "No title": "Not complete",
    "Channel missing": "Not complete",
    "Stale: job or role changed": "Not correct",
    "Source error: wrong person or company": "Not correct",
    "Channel dead": "Not correct",
}
LOSS_STEPS = ["Not found", "Not complete", "Not correct"]


# --------------------------------------------------------------------------
# Definitions (rendered on the Method page)
# --------------------------------------------------------------------------
DEFINITIONS = [
    dict(
        pillar="Headline", metric="Usable yield",
        short="Usable contacts ÷ contact requests. Usable means found, complete and correct.",
        definition=("Usable contacts ÷ contact requests. A request is one customer reveal or enrichment of "
                    "one contact on one channel (email or phone). A contact is usable when it is found, "
                    "complete, and correct."),
        measured_from="Request logs plus the weekly audit sample.",
        trust="Audited",
        blind_spot=("Search has no outside denominator, so the Found step uses requests that name a person. "
                    "The yield cannot fall when a field is filled with a wrong value, so read it with its "
                    "guardrail: wrong contacts delivered per 100 requests."),
    ),
    dict(
        pillar="Breadth", metric="Found rate",
        short="Requests that match one servable catalog contact ÷ valid requests.",
        definition=("Requests that match one servable catalog contact ÷ valid requests. Valid: the request "
                    "names a person (name and company domain, business email, or profile URL). Servable: "
                    "not withheld for opt-out, deletion, or licence limits."),
        measured_from=("Request logs. In production every request is counted and no sample is needed. "
                       "This prototype counts it on the audit sample."),
        trust="Counted",
        blind_spot=("It applies to requests that name a person: enrichment, CSV and API. A reveal from "
                    "search is found by construction, so search coverage needs an outside reference panel. "
                    "The customer's own input can be out of date. Withheld contacts count as not found and "
                    "are reported apart, because they are not a gap to close."),
    ),
    dict(
        pillar="Depth", metric="Complete rate",
        short="Found contacts with a mapped title and a valid value of the requested channel ÷ found contacts.",
        definition=("Found contacts that have a title mapped to seniority and function, and a valid value of "
                    "the requested channel ÷ found contacts. Valid: the value has the right form (an email "
                    "with a real domain; a phone number with digits only, the right length and a real "
                    "country and area code) and it is plausible in context (the right country for the "
                    "person, not one number shared by hundreds of contacts). Rules check this on every "
                    "record, at the feed gate and at delivery."),
        measured_from=("Catalog fields at the time of delivery, after the validity and plausibility rules. "
                       "This prototype simulates no badly formed values, so the rules change no number here."),
        trust="Counted",
        blind_spot=("Populated is not valid, and valid is not correct. A wrong value in a perfect format "
                    "passes every rule. Rules raise the floor on every record; only the audit sets the level."),
    ),
    dict(
        pillar="Accuracy", metric="Correct rate",
        short="Complete contacts that the blind audit confirms ÷ complete contacts in the audit sample.",
        definition=("Complete contacts where the audit confirms the employer, the role (seniority and "
                    "function), and that the requested channel reaches the person ÷ complete contacts in "
                    "the audit sample."),
        measured_from=("A blind weekly audit of 2,500 random requests. The auditor does not use the sources "
                       "that supplied the record."),
        trust="Audited",
        blind_spot=("The audit runs about 7 days behind. Auditors make errors too, so 5% of rows get a "
                    "second audit to measure that; this prototype does not model that error. Employer and "
                    "role are confirmed from public primary sources. A phone number cannot be fully "
                    "confirmed without contact with the person, so the phone channel rests on line-type "
                    "checks and consented connect outcomes, and it is less certain than email."),
    ),
    dict(
        pillar="Freshness", metric="Verified in 90 days",
        short="Found contacts with an independent observation in the last 90 days ÷ found contacts.",
        definition=("Found contacts with an independent observation of employer or channel in the last 90 "
                    "days ÷ found contacts. Independent observation: a reply, a delivered email on a "
                    "domain that is not catch-all, a contributor sighting, a new crawl of a primary page, "
                    "or a completed call. A re-load of the same file does not count. That is the target. "
                    "This prototype reads the newest stamp or signal on the winning record, so it is "
                    "stamp-based: a re-stamped feed does count here."),
        measured_from="The observation log on each record. In this prototype: the newest stamp or signal.",
        trust="Counted",
        blind_spot=("A feed that re-stamps old rows looks fresh. Freshness that goes up while accuracy "
                    "goes down is the warning sign, and the feed gate is what closes the gap. 90 days is "
                    "a convention, not a measured break. That freshness leads accuracy in time is a "
                    "hypothesis: the dashboard shows accuracy by age, not a lagged test."),
    ),
    dict(
        pillar="Freshness", metric="Job-change catch rate (90 days)",
        short="Of found contacts in the audit sample who changed employer in the last 90 days, the share where the catalog shows the new employer.",
        definition=("Among found contacts in the audit sample who changed employer in the last 90 days, the share where the "
                    "catalog already shows the new employer."),
        measured_from="The audit sample. The auditor records the job start date. 13-week window.",
        trust="Audited",
        blind_spot="Small sample: about 100 job changers a week.",
    ),
    dict(
        pillar="Sourcing", metric="Cost per net-new usable contact",
        short="Full yearly cost of a source ÷ the usable contacts customers would lose without it, net of the contacts it breaks.",
        definition=("Fully loaded annual cost of a source ÷ net-new usable contacts a year. Net-new usable: "
                    "usable contacts delivered that would not be usable without the source, minus contacts "
                    "that would be usable if the source were removed. Found by running the merge again "
                    "without the source (leave-one-out). Counted for each delivery, so heavily requested "
                    "contacts count more."),
        measured_from="The audit sample, a replay of the merge, and contract costs. Last 26 weeks, annualised.",
        trust="Audited",
        blind_spot=("It is the average for the contract we have. The next dollar can be worth more or "
                    "less; the Investments page estimates that. It is valid for one removal at a time: a "
                    "source that overlaps another is worth more when that other source goes, so the "
                    "Sourcing page also shows the cost with the nearest overlap removed. It counts "
                    "deliveries, not distinct people, and it comes from a sample, so it has a 95% range."),
    ),
    dict(
        pillar="Guardrail", metric="Withheld share",
        short="Requests where the catalog has the contact but does not serve it ÷ requests.",
        definition=("Requests where the catalog has the contact but does not serve it (opt-out, deletion "
                    "request, or licence limit) ÷ requests."),
        measured_from="Request logs and the suppression list.",
        trust="Counted",
        blind_spot="None. It must never be traded for yield.",
    ),
    dict(
        pillar="Guardrail", metric="Bounce-based accuracy",
        short="1 − hard bounces ÷ first sends, on records that customers chose to email.",
        definition="1 − hard bounces ÷ first sends, on records that customers chose to email.",
        measured_from="Engagement logs. Fast and free.",
        trust="Signal",
        blind_spot=("Customers email verified records first, catch-all domains never bounce, and a "
                    "delivered email says nothing about the person's role."),
    ),
]

TRUST_LEVELS = {
    "Counted": "Counted from complete logs. Exact, but check what the count means.",
    "Audited": "Measured on the blind audit sample. Shown with a 95% interval.",
    "Signal": "A fast outcome signal with a known bias. Use it for direction, never as the level.",
    "Assumption": "An input someone chose. Shown so that you can change it.",
}


# --------------------------------------------------------------------------
# Basic statistics
# --------------------------------------------------------------------------
def wilson(k: float, n: float) -> tuple[float, float]:
    """95% Wilson interval for a share k/n. Returns (low, high)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + Z95 ** 2 / n
    centre = (p + Z95 ** 2 / (2 * n)) / denom
    half = Z95 * sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def half_width(k: float, n: float) -> float:
    """Half of the 95% interval, for a '± x' label."""
    lo, hi = wilson(k, n)
    return (hi - lo) / 2


def z_change(k1: float, n1: float, k0: float, n0: float) -> float:
    """z-score for the difference between two independent shares (k1/n1 minus k0/n0)."""
    if n1 <= 0 or n0 <= 0:
        return 0.0
    p1, p0 = k1 / n1, k0 / n0
    se = sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    return 0.0 if se == 0 else (p1 - p0) / se


# --------------------------------------------------------------------------
# Windows and filters
# --------------------------------------------------------------------------
def window(df: pd.DataFrame, n_weeks: int, end_week: int = md.WEEKS) -> pd.DataFrame:
    """Rows from the n_weeks that end at end_week."""
    return df[(df["week"] > end_week - n_weeks) & (df["week"] <= end_week)]


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """filters = {column: value}; a value of None or 'All' means no filter on that column."""
    out = df
    for col, value in filters.items():
        if value not in (None, "All"):
            out = out[out[col] == value]
    return out


# --------------------------------------------------------------------------
# The funnel
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Funnel:
    """Counts of sampled requests at each step. Every rate on the dashboard comes from these four."""
    n: int
    found: int
    complete: int
    usable: int
    fresh: int = 0          # found and verified in the last 90 days

    @property
    def found_rate(self) -> float:      # Breadth
        return self.found / self.n if self.n else float("nan")

    @property
    def complete_rate(self) -> float:   # Depth
        return self.complete / self.found if self.found else float("nan")

    @property
    def correct_rate(self) -> float:    # Accuracy
        return self.usable / self.complete if self.complete else float("nan")

    @property
    def fresh_rate(self) -> float:      # Freshness
        return self.fresh / self.found if self.found else float("nan")

    @property
    def yield_rate(self) -> float:      # Headline = found_rate x complete_rate x correct_rate
        return self.usable / self.n if self.n else float("nan")

    @property
    def wrong_rate(self) -> float:      # Guardrail: complete contacts that are delivered and wrong, per request
        return (self.complete - self.usable) / self.n if self.n else float("nan")

    def pair(self, metric: str) -> tuple[int, int]:
        """(numerator, denominator) for a metric name."""
        return {
            "wrong_rate": (self.complete - self.usable, self.n),
            "yield_rate": (self.usable, self.n),
            "found_rate": (self.found, self.n),
            "complete_rate": (self.complete, self.found),
            "correct_rate": (self.usable, self.complete),
            "fresh_rate": (self.fresh, self.found),
        }[metric]

    def ci(self, metric: str) -> float:
        return half_width(*self.pair(metric))


def funnel(d: pd.DataFrame) -> Funnel:
    fresh = int((d["found"] & (d["verification_age_months"] <= FRESH_MONTHS)).sum())
    return Funnel(n=len(d), found=int(d["found"].sum()), complete=int(d["complete"].sum()),
                  usable=int(d["usable"].sum()), fresh=fresh)


METRIC_LABELS = {
    "yield_rate": "Usable yield",
    "found_rate": "Found (breadth)",
    "complete_rate": "Complete (depth)",
    "correct_rate": "Correct (accuracy)",
    "fresh_rate": "Verified in 90 days (freshness)",
    "wrong_rate": "Wrong contacts delivered",
}


def verdict(yield_change: dict, wrong_change: dict, base_phrase: str) -> str:
    """
    The one-line answer. Yield cannot fall when a field is filled with a wrong value, so a rise in
    yield only reads as "Better" when wrong contacts delivered did not also rise beyond noise.
    """
    more_wrong = wrong_change["z"] >= Z95
    if yield_change["z"] >= Z95:
        return (f"Mixed: more usable contacts and more wrong ones than {base_phrase}." if more_wrong
                else f"Better than {base_phrase}.")
    if yield_change["z"] <= -Z95:
        return f"Worse than {base_phrase}."
    if more_wrong:
        return f"Worse: no more usable contacts and more wrong ones than {base_phrase}."
    return f"No clear change from {base_phrase}."


def change(cur: Funnel, base: Funnel, metric: str) -> dict:
    """Change in a metric between two windows, in points, with its z-score."""
    k1, n1 = cur.pair(metric)
    k0, n0 = base.pair(metric)
    p1 = k1 / n1 if n1 else float("nan")
    p0 = k0 / n0 if n0 else float("nan")
    z = z_change(k1, n1, k0, n0)
    return dict(now=p1, before=p0, delta=p1 - p0, z=z, significant=abs(z) >= Z95)


def decompose(cur: Funnel, base: Funnel) -> dict:
    """
    Split the change in usable yield into the part from each funnel step.

    Yield = found x complete x correct, so the split uses logs (the "LMDI" method):
    the three parts always add up to the total change exactly.
    """
    y1, y0 = cur.yield_rate, base.yield_rate
    if not (y1 > 0 and y0 > 0):
        return dict(found=0.0, complete=0.0, correct=0.0, total=y1 - y0)
    log_mean = y1 if y1 == y0 else (y1 - y0) / log(y1 / y0)
    parts = {
        "found": log_mean * log(cur.found_rate / base.found_rate),
        "complete": log_mean * log(cur.complete_rate / base.complete_rate),
        "correct": log_mean * log(cur.correct_rate / base.correct_rate),
    }
    parts["total"] = y1 - y0
    return parts


def mix_adjusted_change(cur_df: pd.DataFrame, base_df: pd.DataFrame,
                        dims: tuple[str, ...] = ("region", "channel")) -> dict:
    """
    Change in usable yield with the demand mix held at the base window.

    If demand moves toward harder regions, the raw yield falls even when every
    segment improves. This removes that effect.
    """
    cur = cur_df.groupby(list(dims), observed=True)["usable"].agg(["sum", "size"])
    base = base_df.groupby(list(dims), observed=True)["usable"].agg(["sum", "size"])
    both = cur.join(base, lsuffix="_cur", rsuffix="_base", how="inner")
    both = both[(both["size_cur"] > 0) & (both["size_base"] > 0)]
    if both.empty:
        return dict(within=float("nan"), mix=float("nan"))
    w0 = both["size_base"] / both["size_base"].sum()
    within = float((w0 * (both["sum_cur"] / both["size_cur"] - both["sum_base"] / both["size_base"])).sum())
    raw = cur_df["usable"].mean() - base_df["usable"].mean()
    return dict(within=within, mix=float(raw - within))


def trend(df: pd.DataFrame, rolling: int = 4) -> pd.DataFrame:
    """One row per week with rolling-window rates and the 95% interval of the yield."""
    fresh = df["found"] & (df["verification_age_months"] <= FRESH_MONTHS)
    wk = (df.assign(fresh=fresh).groupby("week")
          .agg(n=("usable", "size"), found=("found", "sum"), complete=("complete", "sum"),
               usable=("usable", "sum"), fresh=("fresh", "sum"))
          .reindex(range(1, md.WEEKS + 1), fill_value=0))
    roll = wk.rolling(rolling, min_periods=rolling).sum().dropna()
    out = pd.DataFrame({
        "week": roll.index,
        "week_end": md.week_end_date(roll.index.to_numpy()),
        "n": roll["n"].to_numpy(),
        "yield_rate": (roll["usable"] / roll["n"]).to_numpy(),
        "found_rate": (roll["found"] / roll["n"]).to_numpy(),
        "complete_rate": (roll["complete"] / roll["found"]).to_numpy(),
        "correct_rate": (roll["usable"] / roll["complete"]).to_numpy(),
        "fresh_rate": (roll["fresh"] / roll["found"]).to_numpy(),
    })
    bounds = [wilson(k, n) for k, n in zip(roll["usable"], roll["n"])]
    out["yield_low"] = [b[0] for b in bounds]
    out["yield_high"] = [b[1] for b in bounds]
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------
# Segments and the loss tree
# --------------------------------------------------------------------------
def segment_table(d: pd.DataFrame, dims: list[str]) -> pd.DataFrame:
    """Funnel rates, sample size, and unmet demand for every combination of the given dimensions."""
    fresh = d["found"] & (d["verification_age_months"] <= FRESH_MONTHS)
    g = (d.assign(fresh=fresh).groupby(dims, observed=False)
         .agg(n=("usable", "size"), found=("found", "sum"), complete=("complete", "sum"),
              usable=("usable", "sum"), fresh=("fresh", "sum"), withheld=("withheld", "sum"))
         .reset_index())
    with np.errstate(divide="ignore", invalid="ignore"):
        g["yield_rate"] = g["usable"] / g["n"]
        g["found_rate"] = g["found"] / g["n"]
        g["complete_rate"] = g["complete"] / g["found"]
        g["correct_rate"] = g["usable"] / g["complete"]
        g["fresh_rate"] = g["fresh"] / g["found"]
    g["yield_ci"] = [half_width(k, n) for k, n in zip(g["usable"], g["n"])]
    g["low_sample"] = g["n"] < LOW_SAMPLE
    # Requests that did not end with a usable contact, scaled to all customer requests.
    weeks = max(d["week"].nunique(), 1)
    per_4_weeks = md.WEIGHT * 4 / weeks
    # Withheld contacts are not a gap to close, so they are not unmet demand.
    g["unmet_requests"] = (g["n"] - g["usable"] - g["withheld"]) * per_4_weeks
    g["lost_not_found"] = (g["n"] - g["found"] - g["withheld"]) * per_4_weeks
    g["lost_not_complete"] = (g["found"] - g["complete"]) * per_4_weeks
    g["lost_not_correct"] = (g["complete"] - g["usable"]) * per_4_weeks
    return g


def loss_tree(d: pd.DataFrame) -> pd.DataFrame:
    """Share of requests by the first reason they failed, in funnel order."""
    counts = d["reason"].value_counts(sort=False)
    out = pd.DataFrame({"reason": counts.index.astype(str), "rows": counts.to_numpy()})
    out["per_100"] = 100 * out["rows"] / max(len(d), 1)
    out["step"] = out["reason"].map(REASON_STEP).fillna("Usable")
    return out


# --------------------------------------------------------------------------
# Alerts: which segment moved more than noise in the last 4 weeks?
# --------------------------------------------------------------------------
def alerts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare the last 4 weeks with the 4 weeks before, for each region and each source.
    An alert needs |z| >= ALERT_Z. The bar is high on purpose: about 25 cells are tested.
    """
    cur, prev = window(df, 4), window(df, 4, md.WEEKS - 4)
    rows = []
    for region in md.REGIONS:
        f1, f0 = funnel(cur[cur["region"] == region]), funnel(prev[prev["region"] == region])
        for metric in ("found_rate", "complete_rate", "correct_rate", "fresh_rate"):
            c = change(f1, f0, metric)
            rows.append(dict(scope="Region", segment=region, metric=METRIC_LABELS[metric], **c))
    for src in md.SOURCES:
        a1, a0 = (source_accuracy(x, src.key) for x in (cur, prev))
        z = z_change(a1[0], a1[1], a0[0], a0[1])
        if a1[1] and a0[1]:
            rows.append(dict(scope="Source", segment=src.label, metric="Accuracy when its record wins",
                             now=a1[0] / a1[1], before=a0[0] / a0[1],
                             delta=a1[0] / a1[1] - a0[0] / a0[1], z=z, significant=abs(z) >= Z95))
    out = pd.DataFrame(rows)
    out = out[out["z"].abs() >= ALERT_Z].copy()
    return out.reindex(out["z"].abs().sort_values(ascending=False).index).reset_index(drop=True)


# --------------------------------------------------------------------------
# Accuracy and freshness
# --------------------------------------------------------------------------
def accuracy_by_age(d: pd.DataFrame) -> pd.DataFrame:
    """Correct rate of complete contacts, by time since the last recorded verification."""
    c = d[d["complete"]]
    age = pd.cut(c["verification_age_months"], bins=AGE_BINS, labels=AGE_LABELS, include_lowest=True)
    g = c.groupby(age, observed=False)["usable"].agg(["sum", "size"]).reset_index()
    g.columns = ["age", "correct", "n"]
    g["age"] = g["age"].astype(str)
    g["correct_rate"] = g["correct"] / g["n"].where(g["n"] > 0)
    bounds = [wilson(k, n) for k, n in zip(g["correct"], g["n"])]
    g["low"], g["high"] = [b[0] for b in bounds], [b[1] for b in bounds]
    g["share_of_delivered"] = g["n"] / max(g["n"].sum(), 1)
    return g


def job_change_catch(d: pd.DataFrame) -> dict:
    """Among found contacts who changed employer in the last 90 days: is the new employer in the catalog?"""
    movers = d[d["found"] & (d["months_since_job_change"] <= FRESH_MONTHS)]
    k, n = int(movers["employer_correct"].sum()), len(movers)
    return dict(rate=k / n if n else float("nan"), n=n, ci=half_width(k, n) if n else float("nan"))


def signal_bias(d: pd.DataFrame) -> pd.DataFrame:
    """
    Walk from the bounce-based number to the audited number, on email requests.

    Each step removes one blind spot of the bounce signal.
    """
    e = d[(d["channel"] == "Email") & d["complete"]]
    sent = e[e["emailed"]]
    steps = [
        ("Sent emails with no bounce", "This is the bounce signal.",
         1 - sent["bounced"].mean() if len(sent) else np.nan, len(sent)),
        ("Sent emails that reach the mailbox", "Catch-all domains accept any address, so dead ones never bounce.",
         sent["email_works"].mean() if len(sent) else np.nan, len(sent)),
        ("All delivered emails that reach the mailbox", "Customers email verified records first.",
         e["email_works"].mean() if len(e) else np.nan, len(e)),
        ("All delivered contacts that are right", "The email arrives, but the employer or role is wrong.",
         e["usable"].mean() if len(e) else np.nan, len(e)),
    ]
    out = pd.DataFrame(steps, columns=["step", "why", "rate", "n"])
    out["drop"] = out["rate"].diff().fillna(0.0)
    return out


def audit_precision(rows_per_week: int, weeks: int, share: float, p: float) -> float:
    """Half-width of the 95% interval for a rate p measured on a segment with the given share of requests."""
    n = rows_per_week * weeks * share
    return Z95 * sqrt(p * (1 - p) / n) if n > 0 else float("nan")


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------
def _bit(key: str) -> int:
    return 1 << md.IDX[key]


def source_accuracy(d: pd.DataFrame, key: str) -> tuple[int, int]:
    """(correct, total) for found contacts whose employer and title came from this source."""
    rows = d[d["found"] & (d["employment_source"] == key)]
    return int((rows["employer_correct"] & rows["title_correct"]).sum()), len(rows)


def usable_without(d: pd.DataFrame, key: str) -> pd.Series:
    """Would each request still end with a usable contact if this source were removed?"""
    bit = _bit(key)
    helped = (d["helps_mask"] & bit) > 0
    harmed = (d["harms_mask"] & bit) > 0
    return (d["usable"] & ~helped) | harmed


def source_scorecard(d: pd.DataFrame, recent: pd.DataFrame, value_per_usable: float) -> pd.DataFrame:
    """
    One row per source.

    d                 the scoring window (26 weeks); results are annualised.
    recent            the last 4 weeks, used for the accuracy alert.
    value_per_usable  what one usable contact delivered is worth to the business (an assumption).
    """
    weeks = max(d["week"].nunique(), 1)
    per_year = md.WEIGHT * 52 / weeks
    usable_total = d["usable"].sum()
    rows = []
    for src in md.SOURCES:
        bit = _bit(src.key)
        has = (d["sources_mask"] & bit) > 0
        helps = ((d["helps_mask"] & bit) > 0).sum() * per_year
        harms = ((d["harms_mask"] & bit) > 0).sum() * per_year
        net = helps - harms
        k, n = source_accuracy(d, src.key)
        k4, n4 = source_accuracy(recent, src.key)
        cost_per_net = src.annual_cost / net if net > 0 else float("inf")
        # 95% range. Net-new is (rows it helps - rows it harms) in a sample; the two counts are
        # close to independent Poisson counts, so the standard error of the difference is sqrt(sum).
        rows_net = (helps - harms) / per_year
        spread = Z95 * sqrt((helps + harms) / per_year)
        net_low, net_high = (rows_net - spread) * per_year, (rows_net + spread) * per_year
        cost_low = src.annual_cost / net_high if net_high > 0 else float("inf")
        cost_high = src.annual_cost / net_low if net_low > 0 else float("inf")
        acc4 = k4 / n4 if n4 else float("nan")
        if n4 >= 50 and acc4 < ACCURACY_FLOOR:
            call = "Fix the feed first"
        elif cost_per_net <= 0.5 * value_per_usable and n and k / n >= EXPAND_ACCURACY:
            call = "Expand"
        elif cost_per_net <= value_per_usable:
            call = "Hold"
        elif cost_per_net <= 3 * value_per_usable:
            call = "Reprice or re-scope"
        else:
            call = "Cut"
        rows.append(dict(
            key=src.key, source=src.label, kind=src.kind, annual_cost=src.annual_cost,
            records_m=src.records_m,
            cost_per_record=src.annual_cost / (src.records_m * 1e6),
            present_in_usable=(has & d["usable"]).sum() / usable_total if usable_total else float("nan"),
            helps=helps, harms=harms, net_new_usable=net,
            accuracy=k / n if n else float("nan"), accuracy_recent=acc4,
            cost_per_net_new_usable=cost_per_net, cost_low=cost_low, cost_high=cost_high,
            sample_rows=int(round(rows_net)), call=call,
        ))
    out = pd.DataFrame(rows)
    out["rank_per_record"] = out["cost_per_record"].rank(method="first").astype(int)
    out["rank_per_usable"] = out["cost_per_net_new_usable"].rank(method="first").astype(int)
    return out


def call_flips(d: pd.DataFrame, recent: pd.DataFrame, value_per_usable: float, factors=(0.5, 1.5)) -> list[dict]:
    """Which calls change when the assumed value of a usable contact is lower or higher?"""
    now = source_scorecard(d, recent, value_per_usable).set_index("key")["call"]
    out = []
    for f in factors:
        other = source_scorecard(d, recent, value_per_usable * f).set_index("key")
        changed = [(other.loc[k, "source"], now[k], other.loc[k, "call"]) for k in now.index if other.loc[k, "call"] != now[k]]
        out.append(dict(value=value_per_usable * f, changed=changed))
    return out


def source_dependence(d: pd.DataFrame, by: str = "region") -> pd.DataFrame:
    """Share of each segment's usable contacts that would be lost without each source."""
    rows = []
    for seg, g in d.groupby(by, observed=True):
        usable = g["usable"].sum()
        for src in md.SOURCES:
            lost = ((g["helps_mask"] & _bit(src.key)) > 0).sum()
            rows.append(dict(segment=str(seg), source=src.label, key=src.key,
                             share_lost=lost / usable if usable else float("nan"), n_usable=int(usable)))
    return pd.DataFrame(rows)


def single_source_share(d: pd.DataFrame) -> float:
    """Share of usable contacts that depend on exactly one or more single sources (helps_mask is not empty)."""
    u = d[d["usable"]]
    return float((u["helps_mask"] > 0).mean()) if len(u) else float("nan")


# --------------------------------------------------------------------------
# Investments on the same unit
# --------------------------------------------------------------------------
REFRESH_TIERS = [(0.00, 0.05), (0.05, 0.10), (0.10, 0.25), (0.25, 0.50), (0.50, 1.00)]


def refresh_tiers(d: pd.DataFrame, distinct_contacts: float, checks_per_year: int,
                  cost_per_check: float, fix_rate: float) -> pd.DataFrame:
    """
    Re-verify requested contacts in order of demand. What does each tier cost per net-new usable contact?

    A re-verification can only recover requests that failed because the record was stale.
    pop_rank is the contact's demand rank (0 = most requested).
    """
    weeks = max(d["week"].nunique(), 1)
    per_year = md.WEIGHT * 52 / weeks
    stale = d["reason"] == "Stale: job or role changed"
    rows = []
    for lo, hi in REFRESH_TIERS:
        in_tier = (d["pop_rank"] >= lo) & (d["pop_rank"] < hi) if hi < 1 else (d["pop_rank"] >= lo)
        gain = (stale & in_tier).sum() * per_year * fix_rate
        cost = (hi - lo) * distinct_contacts * checks_per_year * cost_per_check
        rows.append(dict(
            tier=f"Top {int(hi * 100)}%" if lo == 0 else f"{int(lo * 100)}-{int(hi * 100)}%",
            share_of_requests=in_tier.mean(), contacts=(hi - lo) * distinct_contacts,
            annual_cost=cost, net_new_usable=gain,
            cost_per_net_new_usable=cost / gain if gain > 0 else float("inf"),
        ))
    return pd.DataFrame(rows)


def scenario_gain(base: pd.DataFrame, scenario: pd.DataFrame) -> float:
    """Net-new usable contacts a year from a what-if run against its baseline (same random draws)."""
    weeks = max(base["week"].nunique(), 1)
    return float((scenario["usable"].sum() - base["usable"].sum()) * md.WEIGHT * 52 / weeks)
