from pathlib import Path

import pytest

from tools.geo import ROOT

FIX = Path(__file__).parent / "fixtures" / "lint"


def _lint(case):
    from tools.lint_content import lint
    return lint(FIX / case)


def _has(errors, sub):
    assert any(sub in e for e in errors), errors


def test_parse_nested():
    from tools.pdx import parse
    assert parse('a = { b = 1 c = "x y" }') == [("a", "=", [("b", "=", "1"), ("c", "=", "x y")])]


def test_parse_operators_and_comments():
    from tools.pdx import parse
    assert parse("x >= 2 # note\ny < 3") == [("x", ">=", "2"), ("y", "<", "3")]


def test_parse_unbalanced_raises():
    from tools.pdx import ParseError, parse
    with pytest.raises(ParseError):
        parse("a = {")
    with pytest.raises(ParseError):
        parse('a = "open')


def test_content_lints_clean():
    from tools.lint_content import lint
    assert lint(ROOT / "content") == []


def test_good_fixture_lints_clean():
    assert _lint("good") == []


@pytest.mark.parametrize("case,msg", [
    ("unlocalised_focus", "missing loc: nwc_x_focus"),
    ("unlocalised_focus_desc", "missing loc: nwc_x_focus_desc"),
    ("unknown_prerequisite", "unknown focus"),
    ("mutex_asymmetric", "mutex not symmetric"),
    ("unknown_event", "unknown event"),
    ("unknown_event_days", "unknown event"),
    ("unknown_tag", "unknown tag"),
    ("flag_misspelled", "flag never set"),
    ("flag_global_country_mismatch", "flag never set"),
    ("var_unset", "flag never set"),
    ("unknown_state", "unknown state key"),
    ("loc_no_bom", "no BOM"),
    ("loc_no_header", "missing l_english"),
    ("duplicate_focus", "duplicate focus"),
    ("duplicate_decision", "duplicate decision"),
    ("duplicate_event", "duplicate event"),
    ("unknown_idea", "unknown idea"),
    ("unknown_scripted_effect", "unknown scripted effect"),
    ("tree_no_country_factor", "country factor"),
])
def test_bad_fixture(case, msg):
    _has(_lint(case), msg)


def test_unknown_tag_forms():
    errors = _lint("unknown_tag")
    for t in ("XAA", "XAB", "XAC", "XAD", "XAE", "XAF", "XAG"):
        _has(errors, f"unknown tag {t}")


def test_vanilla_ideas_whitelist(monkeypatch):
    from tools import lint_content
    monkeypatch.setattr(lint_content, "VANILLA_IDEAS", {"some_vanilla_idea"})
    assert not any("some_vanilla_idea" in e for e in lint_content.lint(FIX / "vanilla_idea"))


def test_collect_index():
    from tools.lint_content import collect
    idx = collect(FIX / "good")
    assert {"nwc_x_focus", "nwc_y_focus"} <= idx.focuses
    assert idx.mutex["nwc_x_focus"] == {"nwc_y_focus"}
    assert idx.prereqs["nwc_z_focus"] == {"nwc_x_focus"}
    assert "nwc_x.1" in idx.events and "nwc_x_dec" in idx.decisions
    assert "nwc_x_cat" in idx.categories and "nwc_x_idea" in idx.ideas
    assert "nwc_x_effect" in idx.scripted_effects and "nwc_x_trigger" in idx.scripted_triggers
    assert "nwc_cflag" in idx.country_flags_set and "nwc_gflag" in idx.global_flags_checked
    assert "nwc_v" in idx.vars_set and "nwc_v" in idx.vars_checked
    assert "NOR" in idx.tags_referenced and "nwc_x_focus_desc" in idx.loc_keys
