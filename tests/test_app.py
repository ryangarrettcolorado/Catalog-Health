"""
Runs every page without a browser and fails on any exception.

It also checks the rules that the design system sets for every screen: the prototype
banner comes first, and no page sends inline SVG (Streamlit's st.html removes it, so
an icon or a chart drawn that way would vanish without an error).
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    "overview": "Is the contact data getting better or worse?",
    "segments": "Where is the yield low?",
    "accuracy": "Can you trust the accuracy number?",
    "sourcing": "Which sources earn their cost?",
    "investments": "Where does the next data dollar go?",
    "method": "How each number is defined",
}


@pytest.fixture(scope="module")
def app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def go(app: AppTest, page: str) -> AppTest:
    app.switch_page(f"views/{page}.py").run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def html(app: AppTest) -> list[str]:
    """Every block of HTML on the page, without the stylesheet."""
    return [h.value for h in app.get("html") if not h.value.lstrip().startswith("<style")]


def select(app: AppTest, label: str):
    return next(s for s in app.selectbox if s.label == label)


@pytest.mark.parametrize("page,title", PAGES.items())
def test_every_page_renders_with_the_banner_first(app, page, title):
    go(app, page)
    bodies = html(app)
    assert "cs-proto" in bodies[0] and "Not an Apollo product" in bodies[0]
    assert any(title in b for b in bodies)
    assert all("Illustrative" in b or "illustrative" in b for b in bodies if "cs-chart__sub" in b)


@pytest.mark.parametrize("page", PAGES)
def test_no_page_sends_inline_svg(app, page):
    go(app, page)
    assert not [b[:80] for b in html(app) if "<svg" in b]


@pytest.mark.parametrize("label,value", [
    ("Region", "APAC"), ("Channel", "Phone"), ("Window", "Last 13 weeks"),
    ("Compare with", "vs the weeks before"), ("Industry", "Healthcare"),
])
@pytest.mark.parametrize("page", ["overview", "segments", "accuracy"])
def test_filters_render(app, page, label, value):
    go(app, page)
    before = select(app, label).value
    select(app, label).set_value(value).run()
    assert not app.exception, [e.message for e in app.exception]
    select(app, label).set_value(before).run()


def test_a_filter_stays_when_the_page_changes(app):
    go(app, "overview")
    select(app, "Region").set_value("EMEA").run()
    go(app, "segments")
    assert select(app, "Region").value == "EMEA"
    assert any("Showing" in b for b in html(app))
    select(app, "Region").set_value("All").run()


def test_a_tiny_slice_shows_a_notice_instead_of_a_number(app):
    go(app, "overview")
    picks = {"Region": "LATAM", "Channel": "Phone", "Seniority": "C-suite / VP"}
    for label, value in picks.items():
        select(app, label).set_value(value)
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    bodies = html(app)
    assert any("too few audited requests" in b for b in bodies)
    assert not any("cs-metric" in b for b in bodies)
    for label in picks:
        select(app, label).set_value("All")
    app.run()


def test_chart_tables_switch(app):
    go(app, "overview")
    assert not any("kit-tableview" in b for b in html(app) if "Companies, in brief" not in b)
    app.toggle[0].set_value(True).run()
    assert not app.exception, [e.message for e in app.exception]
    assert sum("kit-tableview" in b for b in html(app)) >= 4
    for page in ("segments", "accuracy", "sourcing", "investments"):
        go(app, page)
    go(app, "overview")
    app.toggle[0].set_value(False).run()
