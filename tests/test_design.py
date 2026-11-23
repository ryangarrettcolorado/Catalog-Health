"""
Checks that the app stays on the design system in design/.

The kit is the source: tokens.json for values, bundle.css for components. These
tests fail when a colour is typed by hand, when a style names a token that does
not exist, or when a generated file is out of date.
"""
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "design"))
import build_tokens     # noqa: E402
import kit              # noqa: E402

DESIGN = ROOT / "design"
PYTHON_FILES = [*ROOT.glob("*.py"), *(ROOT / "views").glob("*.py")]


def test_tokens_css_is_built_from_tokens_json():
    tokens = json.loads((DESIGN / "tokens.json").read_text(encoding="utf-8"))
    assert (DESIGN / "tokens.css").read_text(encoding="utf-8") == build_tokens.render(tokens), \
        "run: python design/build_tokens.py"


@pytest.mark.parametrize("name", ["bundle.css", "streamlit.css"])
def test_every_css_variable_exists(name):
    css = (DESIGN / name).read_text(encoding="utf-8")
    defined = set(re.findall(r"--([\w-]+)\s*:", (DESIGN / "tokens.css").read_text(encoding="utf-8") + css))
    defined |= {"kit-i", "kit-nav-icon"}        # set for each icon by kit.inject()
    used = set(re.findall(r"var\(--([\w-]+)", css))
    assert not used - defined, sorted(used - defined)


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda p: p.name)
def test_python_files_do_not_hard_code_a_colour(path):
    hexes = re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{8}\b", path.read_text(encoding="utf-8"))
    assert not hexes, f"use kit.color('<token>') in place of {hexes}"


def test_streamlit_css_has_no_hand_typed_colour():
    css = (DESIGN / "streamlit.css").read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css)


def test_the_streamlit_theme_matches_the_tokens():
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    expected = {"primaryColor": "bg-inverse", "backgroundColor": "bg-secondary", "secondaryBackgroundColor": "bg-control",
                "textColor": "text-primary", "linkColor": "text-link", "borderColor": "border-default"}
    assert {k: theme[k].lower() for k in expected} == {k: kit.color(t).lower() for k, t in expected.items()}
    radius = {t["name"]: t["value"] for t in json.loads((DESIGN / "tokens.json").read_text(encoding="utf-8"))["radius"]["tokens"]}
    assert theme["baseRadius"] == radius["radius-sm"] and theme["baseFontSize"] == 13
    assert "Inter Variable" in theme["font"] and "Inter Variable" in kit.font("sans")


def test_every_font_and_icon_the_app_needs_is_shipped():
    faces = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]["fontFaces"]
    for face in faces:
        assert (ROOT / face["url"].removeprefix("app/")).is_file(), face["url"]
    icons = json.loads((DESIGN / "icons.json").read_text(encoding="utf-8"))["icons"]
    used = set()
    for path in PYTHON_FILES:
        used |= set(re.findall(r"""icon\(\s*["']([a-z0-9-]+)["']""", path.read_text(encoding="utf-8")))
    assert used and not used - set(icons), sorted(used - set(icons))


def test_heat_bins_are_equal_and_cover_the_values():
    for values in ([17, 54], [0, 41], [56.9, 84.4], [25, 31], [0.2, 0.9]):
        first, step = kit.heat_bins(values)
        assert step in (1, 2, 5, 10, 20)
        assert first - step <= min(values) < first, (values, first, step)
