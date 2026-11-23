"""
app.py - Catalog health: a mock telemetry dashboard for a B2B contact catalog.

Run:  streamlit run app.py

This file is the frame only: the prototype banner, the sidebar, the top bar, and the
navigation. Each page is a file in views/. Every number comes from metrics.py, every
row from mockdata.py, and the look from the design system in design/ (see kit.py).

ALL DATA IS SIMULATED. Nothing here is Apollo data, and this is not an Apollo product.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import kit
import ui

PRODUCT = "Catalog health"
ROOT = Path(__file__).resolve().parent

# key, title, file, icon, group in the sidebar
PAGES = [
    ("overview", "Overview", "views/overview.py", "layout-dashboard", "Data health"),
    ("segments", "Segments", "views/segments.py", "layers", "Data health"),
    ("accuracy", "Accuracy and freshness", "views/accuracy.py", "shield-check", "Data health"),
    ("sourcing", "Sourcing", "views/sourcing.py", "database", "Decisions"),
    ("investments", "Investments", "views/investments.py", "chart-column", "Decisions"),
    ("method", "Method", "views/method.py", "file-text", "Reference"),
]

pages = {key: st.Page(str(ROOT / path), title=title, url_path=key, default=(key == "overview"))
         for key, title, path, _, _ in PAGES}
page = st.navigation(list(pages.values()), position="hidden")
current = next(key for key, title, *_ in PAGES if title == page.title)

st.set_page_config(page_title=f"{page.title} · {PRODUCT}", page_icon=str(ROOT / "static" / "mark.png"),
                   layout="wide", initial_sidebar_state="auto")

# The kit's styles, then the PrototypeBanner as the first element of the screen, then the top bar.
kit.inject(PRODUCT, {key: icon for key, _, _, icon, _ in PAGES}, current)
st.html(kit.banner() + kit.topbar("Illustrative data", f"Newest data: week ending {ui.DATA_DATE}"))

with st.sidebar:
    group = None
    for key, title, _, _, group_name in PAGES:
        if group_name != group:
            group = group_name
            st.html(kit.nav_group(group))
        with st.container(key=f"nav-{key}"):
            st.page_link(pages[key], label=title, width="stretch")
    st.html(f'<p class="kit-sidenote">A candidate case study by {kit.esc(kit.AUTHOR)} for Apollo.io. '
            "Every number is simulated.</p>")

page.run()
