"""
mockdata.py - the seeded simulation behind the mock dashboard.

NOTHING HERE IS REAL APOLLO DATA. The simulation exists so that every number on
the dashboard is computed from rows, the same way production telemetry would
compute it from a weekly audit sample. Same seed, same rows, same numbers.

The model in six sentences
--------------------------
1. Each row is one sampled customer request for a contact: an email reveal or a
   phone reveal (2,500 rows a week).
2. Every person has a hidden clock: months since their last job change.
3. Each source either has the person or not, and last OBSERVED them some months
   ago. A source is right about the employer only if it observed the person
   after the last job change.
4. The catalog merges sources: the most recently STAMPED record wins for
   employer and title; email and phone come from the best available source.
5. The audit knows the truth, so every row carries the real outcome.
6. Leave-one-out: the merge runs again without each source. That shows what the
   source really adds, and what it breaks.

"Observed" and "stamped" are the same thing until a feed re-stamps old rows as
new. The simulated incident (the last 4 weeks, Vendor C, APAC) does exactly that.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Scale and calendar
# --------------------------------------------------------------------------
SEED = 20261123
WEEKS = 65                       # 52 weeks back plus a 13-week window a year ago
ROWS_PER_WEEK = 2_500            # audited sample size per week
REQUESTS_PER_WEEK = 12_000_000   # all customer contact requests per week (illustrative)
WEIGHT = REQUESTS_PER_WEEK / ROWS_PER_WEEK   # requests represented by one sampled row
LAST_WEEK_END = pd.Timestamp("2026-11-22")

# Events that the trend chart annotates (week numbers are 1..WEEKS).
EVENT_VENDOR_A_EXPANSION = WEEKS - 38     # about 9 months ago
EVENT_VENDOR_B_PILOT = WEEKS - 27         # about 6 months ago
EVENT_VENDOR_C_INCIDENT = WEEKS - 3       # 4 weeks ago, still open
EVENTS = {
    EVENT_VENDOR_A_EXPANSION: "Vendor A contract expanded",
    EVENT_VENDOR_B_PILOT: "Vendor B pilot starts, EMEA",
    EVENT_VENDOR_C_INCIDENT: "Vendor C re-stamps its feed, APAC",
}

# --------------------------------------------------------------------------
# Segments (the demand mix of customer requests)
# --------------------------------------------------------------------------
REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
REGION_SHARE_START = [0.58, 0.25, 0.12, 0.05]    # a year ago
REGION_SHARE_END = [0.53, 0.28, 0.14, 0.05]      # today: demand moves to harder regions

CHANNELS = ["Email", "Phone"]                    # what the customer asked to reveal
PHONE_REQUEST_SHARE = [0.28, 0.24, 0.18, 0.15]   # share of requests that ask for a phone, by region

SIZES = ["Small (1-50)", "Mid-market (51-1,000)", "Enterprise (1,001+)"]
SIZE_SHARE = [0.30, 0.45, 0.25]
SIZE_FINDABILITY = [-0.25, 0.00, 0.15]

SENIORITIES = ["C-suite / VP", "Director", "Manager", "Individual contributor"]
SENIORITY_SHARE = [0.22, 0.24, 0.30, 0.24]
SENIORITY_FINDABILITY = [0.15, 0.05, 0.00, -0.15]
EMPLOYER_CHANGE_HAZARD = [0.012, 0.015, 0.018, 0.023]   # per month, by seniority

INDUSTRIES = ["Software & tech", "Professional services", "Financial services",
              "Manufacturing", "Healthcare", "Other"]
INDUSTRY_SHARE = [0.34, 0.16, 0.12, 0.14, 0.10, 0.14]
INDUSTRY_FINDABILITY = [0.25, 0.05, 0.00, -0.20, -0.25, -0.10]
INDUSTRY_HAZARD_MULT = [1.20, 1.00, 0.95, 0.85, 0.90, 1.00]

TITLE_ONLY_CHANGE_HAZARD = 0.009     # promotions and role changes, per month
PARSE_ERROR = 0.015                  # title mapped to the wrong seniority or function
CATCH_ALL_SHARE = 0.22               # domains that accept any address (no bounce)
TITLE_FILL = 0.97
WITHHELD_SHARE = [0.022, 0.034, 0.010, 0.008]   # opt-out, deletion, licence limits, by region
POPULARITY_SKEW = 0.35               # top 10% of requested contacts get about 45% of requests
ENGAGEMENT_LAG_MONTHS = 2.0          # mean months since the last bounce or reply signal

# Why a request did not end with a usable contact (the loss tree), in funnel order.
REASONS = [
    "Usable",
    "Not in catalog",
    "Withheld (opt-out, deletion, licence)",
    "No title",
    "Channel missing",
    "Stale: job or role changed",
    "Source error: wrong person or company",
    "Channel dead",
]


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    key: str
    label: str
    kind: str              # "First-party" or "Licensed"
    annual_cost: float     # fully loaded USD per year: licence, processing, verification, compliance
    records_m: float       # records in the feed, millions (the number a vendor quotes)
    coverage: tuple        # share of requested contacts it has: (NA, EMEA, APAC, LATAM)
    lag_months: float      # mean months since it last observed a person
    entity_error: float    # share of its records tied to the wrong person or employer
    email_fill: float
    email_error: float     # share of its emails that are wrong even when the employer is right
    phone_fill: float
    mobile_share: float    # share of its phones that are mobiles (they survive a job change)
    pop_sensitivity: float  # how much fresher it is for heavily requested contacts
    echoes: str = ""       # key of a source it largely copies (same upstream), if any


SOURCES: list[Source] = [
    Source("contributor", "Contributor network", "First-party", 1_600_000, 95,
           (0.58, 0.25, 0.12, 0.14), 2.5, 0.02, 0.92, 0.02, 0.35, 0.50, 0.60),
    Source("crawl", "Public web crawl", "First-party", 1_400_000, 180,
           (0.64, 0.56, 0.44, 0.42), 4.0, 0.03, 0.12, 0.10, 0.04, 0.20, 0.35),
    Source("vendor_a", "Vendor A (global aggregator)", "Licensed", 4_000_000, 210,
           (0.66, 0.56, 0.42, 0.40), 9.0, 0.05, 0.85, 0.06, 0.22, 0.50, 0.15),
    Source("vendor_b", "Vendor B (EMEA mobile)", "Licensed", 1_100_000, 28,
           (0.01, 0.34, 0.01, 0.01), 4.0, 0.03, 0.60, 0.04, 0.80, 0.95, 0.15),
    Source("vendor_c", "Vendor C (APAC business data)", "Licensed", 900_000, 40,
           (0.02, 0.02, 0.34, 0.02), 6.0, 0.05, 0.65, 0.06, 0.35, 0.50, 0.15),
    Source("vendor_d", "Vendor D (bulk email lists)", "Licensed", 750_000, 150,
           (0.36, 0.28, 0.11, 0.13), 20.0, 0.08, 0.95, 0.15, 0.08, 0.30, 0.00, "vendor_a"),
    Source("vendor_e", "Vendor E (US direct dials)", "Licensed", 1_500_000, 45,
           (0.26, 0.01, 0.01, 0.01), 5.0, 0.04, 0.50, 0.05, 0.85, 0.80, 0.15),
]
SOURCE_KEYS = [s.key for s in SOURCES]
SOURCE_LABELS = {s.key: s.label for s in SOURCES}
N_SRC = len(SOURCES)
IDX = {s.key: i for i, s in enumerate(SOURCES)}

# Vendor A before its contract expansion (same NA coverage, thinner elsewhere).
VENDOR_A_COVERAGE_BEFORE = (0.66, 0.40, 0.27, 0.25)
# Which source's phone the catalog prefers, best first.
PHONE_PRIORITY = ["vendor_b", "vendor_e", "contributor", "vendor_c", "vendor_a", "crawl", "vendor_d"]
# Generalist sources hold fewer phones outside North America.
PHONE_REGION_MULT = [1.0, 0.5, 0.7, 0.7]
# How closely an "echo" source's coverage follows the source it copies.
ECHO_CORRELATION = 0.97
# During the incident, this share of the re-stamped feed carries the wrong employer.
INCIDENT_ENTITY_ERROR = 0.22
# Contacts that nobody asks for are refreshed less often (used for the catalog-wide sample).
LONG_TAIL_LAG_MULT = 1.8

_FINDABILITY_NOISE = 0.9
_SIGMA = float(np.sqrt(1 + _FINDABILITY_NOISE ** 2))
_NORMAL = NormalDist()


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _pick_category(u: np.ndarray, shares) -> np.ndarray:
    """Turn uniform draws into category codes with the given shares."""
    edges = np.cumsum(np.asarray(shares, dtype=float))
    edges[-1] = 1.0
    return np.searchsorted(edges, u, side="right").clip(0, len(edges) - 1)


def _argmin_where(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Column index of the smallest value where mask is True; -1 if the row has none."""
    masked = np.where(mask, values, np.inf)
    idx = masked.argmin(axis=1)
    idx[~mask.any(axis=1)] = -1
    return idx


def _take(matrix: np.ndarray, idx: np.ndarray, default=False) -> np.ndarray:
    """matrix[row, idx[row]] with a default where idx is -1."""
    rows = np.arange(len(idx))
    picked = matrix[rows, np.clip(idx, 0, None)]
    return np.where(idx >= 0, picked, default)


def week_end_date(week):
    """Week number (1..WEEKS) to the Sunday that ends it."""
    return LAST_WEEK_END - pd.to_timedelta((WEEKS - np.asarray(week)) * 7, unit="D")


# --------------------------------------------------------------------------
# The simulation
# --------------------------------------------------------------------------
def _draw(rng: np.random.Generator, n: int) -> dict:
    """All randomness, drawn in a fixed order so that scenarios share the same luck."""
    return dict(
        u_region=rng.random(n), u_size=rng.random(n), u_sen=rng.random(n), u_ind=rng.random(n),
        u_channel=rng.random(n),
        z=rng.standard_normal(n), eps=rng.standard_normal((n, N_SRC)),
        u_pop=rng.random(n),
        e_emp=rng.exponential(1.0, n), e_title=rng.exponential(1.0, n),
        e_lag=rng.exponential(1.0, (n, N_SRC)), e_stamp=rng.exponential(1.0, (n, N_SRC)),
        u_ent=rng.random((n, N_SRC)), u_parse=rng.random((n, N_SRC)),
        u_email=rng.random((n, N_SRC)), u_email_err=rng.random((n, N_SRC)),
        u_phone=rng.random((n, N_SRC)), u_mobile=rng.random((n, N_SRC)),
        u_phone_ok=rng.random((n, N_SRC)),
        u_title=rng.random(n), u_catch=rng.random(n), u_withheld=rng.random(n),
        u_eng=rng.random(n), e_eng=rng.exponential(1.0, n),
        u_sent=rng.random(n), u_dial=rng.random(n), u_wrong=rng.random(n), u_flag=rng.random(n),
    )


def _coverage_table(scenario: dict) -> np.ndarray:
    """Coverage probability for every (week, region, source), with the time story applied."""
    table = np.zeros((WEEKS, len(REGIONS), N_SRC))
    boost = scenario.get("coverage_boost", {})          # {(source_key, region): multiplier}
    for w in range(WEEKS):
        week = w + 1
        t = w / (WEEKS - 1)
        for s, src in enumerate(SOURCES):
            cov = np.array(src.coverage, dtype=float)
            if src.key == "contributor":
                cov = cov * (0.88 + 0.12 * t)            # the network grows through the year
            if src.key == "vendor_a" and week < EVENT_VENDOR_A_EXPANSION:
                cov = np.array(VENDOR_A_COVERAGE_BEFORE)
            if src.key == "vendor_b":
                ramp = np.clip((week - EVENT_VENDOR_B_PILOT + 1) / 4, 0, 1)
                cov = cov * ramp                         # nothing before the pilot, full after 4 weeks
            for r, region in enumerate(REGIONS):
                cov[r] *= boost.get((src.key, region), 1.0)
            table[w, :, s] = np.clip(cov, 0.0, 0.97)
    return table


def simulate(scenario: dict | None = None, *, demand_weighted: bool = True,
             weeks: tuple[int, int] = (1, WEEKS), rows_per_week: int = ROWS_PER_WEEK,
             seed: int = SEED) -> pd.DataFrame:
    """
    Build the audited request sample.

    scenario           optional what-if, for example
                       {"coverage_boost": {("contributor", "EMEA"): 1.5}} or {"no_incident": True}.
                       Scenarios reuse the same random draws, so any difference in
                       the result comes from the change itself.
    demand_weighted    True: rows are customer requests (popular contacts appear more often).
                       False: rows are a uniform sample of catalog contacts, all scored
                       on the email channel.
    """
    scenario = scenario or {}
    first, last = weeks
    n = (last - first + 1) * rows_per_week
    rng = np.random.default_rng(seed)
    d = _draw(rng, n)

    week = np.repeat(np.arange(first, last + 1), rows_per_week)
    w_idx = week - 1
    t = w_idx / (WEEKS - 1)

    # ---- who is being asked for, and on which channel ----------------------
    start, end = np.array(REGION_SHARE_START), np.array(REGION_SHARE_END)
    share_by_week = start[None, :] + (end - start)[None, :] * (np.arange(WEEKS) / (WEEKS - 1))[:, None]
    edges = np.cumsum(share_by_week, axis=1)
    edges[:, -1] = 1.0
    region = (d["u_region"][:, None] > edges[w_idx]).sum(axis=1).clip(0, len(REGIONS) - 1)
    size = _pick_category(d["u_size"], SIZE_SHARE)
    seniority = _pick_category(d["u_sen"], SENIORITY_SHARE)
    industry = _pick_category(d["u_ind"], INDUSTRY_SHARE)
    wants_phone = d["u_channel"] < np.array(PHONE_REQUEST_SHARE)[region]
    if not demand_weighted:
        wants_phone = np.zeros(n, dtype=bool)

    # Popularity rank of the contact, 0 = most requested. Requests concentrate on
    # popular contacts; a uniform catalog sample does not.
    pop_rank = d["u_pop"] ** (1 / POPULARITY_SKEW) if demand_weighted else d["u_pop"]

    # ---- the hidden truth: time since the last change ----------------------
    hazard = np.array(EMPLOYER_CHANGE_HAZARD)[seniority] * np.array(INDUSTRY_HAZARD_MULT)[industry]
    t_emp = d["e_emp"] / hazard                                   # months since employer change
    t_title = np.minimum(t_emp, d["e_title"] / TITLE_ONLY_CHANGE_HAZARD)   # months since any role change

    # ---- which sources have the person -------------------------------------
    cov = _coverage_table(scenario)                                # (week, region, source)
    theta = np.vectorize(lambda c: _SIGMA * _NORMAL.inv_cdf(1 - min(max(c, 1e-6), 1 - 1e-6)))(cov)
    findability = (d["z"] + np.array(SIZE_FINDABILITY)[size] + np.array(SENIORITY_FINDABILITY)[seniority]
                   + np.array(INDUSTRY_FINDABILITY)[industry])
    eps = d["eps"].copy()
    for s, src in enumerate(SOURCES):                              # echo sources copy another source's reach
        if src.echoes:
            eps[:, s] = ECHO_CORRELATION * d["eps"][:, IDX[src.echoes]] + np.sqrt(1 - ECHO_CORRELATION ** 2) * d["eps"][:, s]
    reach = findability[:, None] + _FINDABILITY_NOISE * eps
    has = (reach > theta[w_idx, region, :]) & (cov[w_idx, region, :] > 0)
    # What each feed holds before any what-if. An echo source copies its upstream's
    # feed, and that does not change when we stop licensing the upstream.
    if scenario.get("coverage_boost"):
        cov0 = _coverage_table({})
        theta0 = np.vectorize(lambda c: _SIGMA * _NORMAL.inv_cdf(1 - min(max(c, 1e-6), 1 - 1e-6)))(cov0)
        has_native = (reach > theta0[w_idx, region, :]) & (cov0[w_idx, region, :] > 0)
    else:
        has_native = has

    # ---- how fresh each source's record is ---------------------------------
    lag_mean = np.empty((n, N_SRC))
    ent_err = np.empty((n, N_SRC))
    for s, src in enumerate(SOURCES):
        m = np.full(n, src.lag_months)
        m *= 1 + src.pop_sensitivity * (2 * pop_rank - 0.6)        # fresher for popular contacts
        if src.kind == "Licensed" and src.key != "vendor_b":
            m *= 1 + 0.45 * t                                      # refresh did not keep pace with volume
        if src.key == "vendor_a":
            m *= np.where((week >= EVENT_VENDOR_A_EXPANSION) & (region != 0), 1.50, 1.0)   # staler batch
        if not demand_weighted:
            m *= LONG_TAIL_LAG_MULT                                # the long tail is refreshed less often
        lag_mean[:, s] = m
        ent_err[:, s] = src.entity_error
    lag_true = d["e_lag"] * lag_mean          # months since the source last OBSERVED the person
    lag_stamp = lag_true.copy()               # the date the feed puts on the record

    incident = (week >= EVENT_VENDOR_C_INCIDENT) & (region == REGIONS.index("APAC"))
    if not scenario.get("no_incident", False):
        c = IDX["vendor_c"]
        lag_stamp[incident, c] = d["e_stamp"][incident, c] * 0.6   # old rows re-stamped as new
        ent_err[incident, c] = INCIDENT_ENTITY_ERROR                # and the employer mapping broke

    # ---- what each source would say ----------------------------------------
    src_entity_ok = d["u_ent"] >= ent_err
    src_emp_ok = (lag_true < t_emp[:, None]) & src_entity_ok
    src_title_ok = src_emp_ok & (lag_true < t_title[:, None]) & (d["u_parse"] >= PARSE_ERROR)
    email_fill = np.array([s.email_fill for s in SOURCES])
    email_err = np.array([s.email_error for s in SOURCES])
    phone_fill = np.array([s.phone_fill for s in SOURCES])[None, :] * np.array(PHONE_REGION_MULT)[region][:, None]
    phone_fill[:, IDX["vendor_b"]] = SOURCES[IDX["vendor_b"]].phone_fill    # the specialist is exempt
    mobile_share = np.array([s.mobile_share for s in SOURCES])
    src_has_email = d["u_email"] < email_fill
    for s_i, src in enumerate(SOURCES):                            # an echo source has no email its upstream lacks
        if src.echoes:
            up = IDX[src.echoes]
            src_has_email[:, s_i] &= src_has_email[:, up] | ~has_native[:, up]
    src_email_ok = src_has_email & (lag_true < t_emp[:, None]) & (d["u_email_err"] >= email_err)
    src_has_phone = d["u_phone"] < phone_fill
    src_is_mobile = d["u_mobile"] < mobile_share
    mobile_ok = d["u_phone_ok"] < np.clip(0.93 - 0.006 * lag_true, 0.5, 1.0)   # numbers churn slowly
    desk_ok = (lag_true < t_emp[:, None]) & (d["u_phone_ok"] < 0.90)           # desk lines die with the job
    src_phone_ok = src_has_phone & np.where(src_is_mobile, mobile_ok, desk_ok)
    phone_rank = np.array([PHONE_PRIORITY.index(k) for k in SOURCE_KEYS], dtype=float)

    has_title = d["u_title"] < TITLE_FILL
    catch_all = d["u_catch"] < CATCH_ALL_SHARE
    withheld_draw = d["u_withheld"] < np.array(WITHHELD_SHARE)[region]
    engaged = d["u_eng"] < (0.03 + 0.62 * (1 - pop_rank) ** 1.5)   # a customer emailed this contact lately
    lag_eng = d["e_eng"] * ENGAGEMENT_LAG_MONTHS

    def merge(active: np.ndarray) -> dict:
        """Build the catalog record from the active sources and score it against the truth."""
        any_source = active.any(axis=1)
        withheld = any_source & withheld_draw
        found = any_source & ~withheld

        # Employer and title: the most recently stamped record wins.
        emp_src = _argmin_where(lag_stamp, active)
        emp_ok = _take(src_emp_ok, emp_src) & found
        title_ok = _take(src_title_ok, emp_src) & found & has_title
        # Did the winning record really observe the person after the last change?
        change_seen = _take(lag_true, emp_src, np.inf) < t_emp
        role_change_seen = _take(lag_true, emp_src, np.inf) < t_title

        # Email: freshest source that has one. If the job change was seen, older
        # emails fail the domain check and are dropped.
        email_cand = active & src_has_email & (~change_seen[:, None] | (lag_true < t_emp[:, None]))
        email_src = _argmin_where(lag_stamp, email_cand)
        has_email = (email_src >= 0) & found
        email_works = _take(src_email_ok, email_src) & has_email
        # Engagement signal: a send after the job change bounces a dead address,
        # unless the domain is catch-all. A bounced address is removed.
        bounced_out = has_email & ~email_works & engaged & (lag_eng < t_emp) & ~catch_all
        has_email = has_email & ~bounced_out

        # Phone: by source priority. A desk line from before a seen job change is dropped.
        phone_cand = active & src_has_phone & (src_is_mobile | ~change_seen[:, None] | (lag_true < t_emp[:, None]))
        phone_src = _argmin_where(np.broadcast_to(phone_rank, active.shape), phone_cand)
        has_phone = (phone_src >= 0) & found
        phone_works = _take(src_phone_ok, phone_src) & has_phone

        # What the system believes about freshness: the newest stamp or signal.
        ver_age = _take(lag_stamp, emp_src, np.inf)
        ver_age = np.where(engaged & has_email, np.minimum(ver_age, lag_eng), ver_age)

        has_channel = np.where(wants_phone, has_phone, has_email)
        channel_works = np.where(wants_phone, phone_works, email_works & has_email)
        complete = found & has_title & has_channel
        usable = complete & emp_ok & title_ok & channel_works

        # The loss tree: the first reason, in funnel order, that the request failed.
        reason = np.zeros(len(found), dtype=np.int8)                       # 0 = usable
        stale = ~role_change_seen
        person_wrong = ~(emp_ok & title_ok)
        reason = np.where(complete & ~usable & ~person_wrong, 7, reason)            # channel dead
        reason = np.where(complete & person_wrong & ~stale, 6, reason)              # source error
        reason = np.where(complete & person_wrong & stale, 5, reason)               # stale
        reason = np.where(found & has_title & ~has_channel, 4, reason)              # channel missing
        reason = np.where(found & ~has_title, 3, reason)                            # no title
        reason = np.where(withheld, 2, reason)
        reason = np.where(~any_source, 1, reason)

        return dict(found=found, withheld=withheld, emp_src=emp_src, emp_ok=emp_ok, title_ok=title_ok,
                    has_email=has_email, has_phone=has_phone, email_works=email_works & has_email,
                    phone_works=phone_works, ver_age=ver_age, complete=complete, usable=usable,
                    reason=reason)

    full = merge(has)

    # ---- leave-one-out: what does each source add, and what does it break? --
    helps = np.zeros(n, dtype=np.int16)      # bit s set: usable only because source s is there
    harms = np.zeros(n, dtype=np.int16)      # bit s set: would be usable if source s were removed
    for s in range(N_SRC):
        active = has.copy()
        active[:, s] = False
        without = merge(active)
        helps |= ((full["usable"] & ~without["usable"]).astype(np.int16) << s)
        harms |= ((~full["usable"] & without["usable"]).astype(np.int16) << s)

    # ---- fast signals that exist without an audit (and their blind spots) ---
    verified_badge = full["has_email"] & (full["ver_age"] <= 6)
    emailed = full["has_email"] & (d["u_sent"] < np.where(verified_badge, 0.70, 0.20))
    bounced = emailed & ~full["email_works"] & ~catch_all
    dialed = full["has_phone"] & (d["u_dial"] < 0.25)
    wrong_number = dialed & ~full["phone_works"] & (d["u_wrong"] < 0.5)
    flagged = full["complete"] & ~full["usable"] & (d["u_flag"] < 0.06)

    sources_mask = (has.astype(np.int16) << np.arange(N_SRC, dtype=np.int16)).sum(axis=1).astype(np.int16)
    emp_source = np.where(full["emp_src"] >= 0, np.array(SOURCE_KEYS)[np.clip(full["emp_src"], 0, None)], "")

    return pd.DataFrame({
        "week": week,
        "week_end": week_end_date(week),
        "region": pd.Categorical.from_codes(region, REGIONS, ordered=True),
        "channel": pd.Categorical.from_codes(wants_phone.astype(int), CHANNELS, ordered=True),
        "company_size": pd.Categorical.from_codes(size, SIZES, ordered=True),
        "seniority": pd.Categorical.from_codes(seniority, SENIORITIES, ordered=True),
        "industry": pd.Categorical.from_codes(industry, INDUSTRIES, ordered=True),
        "pop_rank": pop_rank.round(4),
        "weight": WEIGHT,
        "n_sources": has.sum(axis=1).astype(np.int8),
        "sources_mask": sources_mask,
        "employment_source": emp_source,
        # the funnel
        "found": full["found"],
        "complete": full["complete"],
        "usable": full["usable"],
        "reason": pd.Categorical.from_codes(full["reason"], REASONS, ordered=True),
        # the pieces behind it
        "withheld": full["withheld"],
        "has_title": has_title & full["found"],
        "has_email": full["has_email"],
        "has_phone": full["has_phone"],
        "employer_correct": full["emp_ok"],
        "title_correct": full["title_ok"],
        "email_works": full["email_works"],
        "phone_works": full["phone_works"],
        "catch_all_domain": catch_all,
        "verification_age_months": np.where(full["found"], np.round(full["ver_age"], 2), np.nan),
        "months_since_job_change": np.round(t_emp, 2),
        # leave-one-out (bit i = SOURCES[i])
        "helps_mask": helps,
        "harms_mask": harms,
        # fast signals
        "verified_badge": verified_badge,
        "emailed": emailed,
        "bounced": bounced,
        "dialed": dialed,
        "wrong_number_logged": wrong_number,
        "flagged_by_customer": flagged,
    })


# --------------------------------------------------------------------------
# Small illustrative tables that are NOT computed from the request sample
# --------------------------------------------------------------------------
def catalog_size_trend() -> pd.DataFrame:
    """Catalog row counts by quarter. This is the number the dashboard argues against."""
    return pd.DataFrame({
        "quarter": ["2025 Q4", "2026 Q1", "2026 Q2", "2026 Q3", "2026 Q4"],
        "week": [WEEKS - 52, WEEKS - 39, WEEKS - 26, WEEKS - 13, WEEKS],
        "contacts_m": [212, 221, 243, 252, 258],
        "companies_m": [33.1, 33.6, 34.2, 34.8, 35.2],
    })


def company_strip() -> pd.DataFrame:
    """Company telemetry is out of scope for this wedge. These are fixed illustrative values."""
    return pd.DataFrame({
        "metric": ["Found: company match rate", "Complete: industry, size band, HQ country",
                   "Correct: audited size band and industry", "Fresh: verified in the last 180 days"],
        "now": [91.2, 83.5, 81.0, 58.0],
        "year_ago": [90.1, 81.5, 81.5, 61.0],
    })


def guardrails() -> pd.DataFrame:
    """Compliance guardrails that sit beside the yield. Fixed illustrative values."""
    return pd.DataFrame({
        "guardrail": [
            "Suppression latency, 95th percentile",
            "Fields with full provenance",
            "Licensed fields past their contract term",
        ],
        "value": ["6 days", "94%", "0"],
        "target": ["7 days or less", "100%", "0"],
        "what_it_means": [
            "Days from an opt-out or deletion request to removal from every surface. "
            "The legal ceiling is far looser than the target (for example the 45-day cycle of "
            "California's deletion platform), so the target is ours.",
            "Share of served field values that carry their source, lawful basis, and licence terms. "
            "Without it, a cut vendor cannot be purged and a deletion request cannot be proved.",
            "Field values still served after the licence that supplied them ended.",
        ],
    })
