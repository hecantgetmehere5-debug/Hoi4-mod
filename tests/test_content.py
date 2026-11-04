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


# --- Storting mechanic -------------------------------------------------------

CONTENT = ROOT / "content"
STORTING_FILES = [
    "common/scripted_effects/nwc_storting_effects.txt",
    "common/scripted_triggers/nwc_storting_triggers.txt",
    "common/decisions/nwc_storting.txt",
    "common/decisions/categories/nwc_categories.txt",
    "events/nwc_storting.txt",
    "localisation/english/nwc_storting_l_english.yml",
]
SUPPORT_VARS = {"nwc_ap_support", "nwc_h_support"}


def _parsed(rel):
    from tools.pdx import parse
    return parse((CONTENT / rel).read_text(encoding="utf-8-sig"))


def _all_parsed():
    from tools.pdx import parse
    return {f.relative_to(CONTENT).as_posix(): parse(f.read_text(encoding="utf-8-sig"))
            for f in sorted(CONTENT.rglob("*.txt"))}


def _blocks(tree):
    """Yield every block (list of entries) in a parsed tree, outermost first."""
    yield tree
    for _, _, v in tree:
        if isinstance(v, list):
            yield from _blocks(v)


def _get(block, key):
    return next((v for k, _, v in block if k == key), None)


def _targets(val):
    if not isinstance(val, list):
        return set()
    return {v if k == "var" else k for k, _, v in val if k not in ("value", "tooltip")}


def test_storting_files_exist_and_lint():
    from tools.lint_content import lint
    for rel in STORTING_FILES:
        assert (CONTENT / rel).is_file(), rel
    assert lint(CONTENT) == []


def test_storting_support_clamped():
    found = 0
    for rel, tree in _all_parsed().items():
        for block in _blocks(tree):
            adds = [v for k, _, v in block if k == "add_to_variable" and _targets(v) & SUPPORT_VARS]
            if adds:
                found += len(adds)
                assert ("nwc_storting_clamp", "=", "yes") in block, (rel, adds)
    assert found >= 5  # propose (2), concessions (2), amend


def test_storting_threshold():
    vote = _get(_parsed("common/scripted_effects/nwc_storting_effects.txt"), "nwc_storting_vote")
    assert vote is not None
    gate = next(v for k, _, v in vote if k == "if"
                and ("nwc_vote_share", ">", "70") in (_get(_get(v, "limit") or [], "check_variable") or []))
    rolls = [b for b in _blocks(gate) if any(k == "set_temp_variable_to_random" for k, _, _ in b)]
    assert rolls, "roll must sit inside the > 70 gate"
    idx = vote.index(("if", "=", gate))
    assert vote[idx + 1][0] == "else"
    fail = vote[idx + 1][2]
    assert ("country_event", "=", "nwc_storting.3") in fail
    assert not any(k == "set_temp_variable_to_random" for b in _blocks(fail) for k, _, _ in b)
    assert not any(k == "set_temp_variable_to_random" for k, _, _ in vote)


def test_amend_limited():
    decs = _parsed("common/decisions/nwc_storting.txt")
    amend = next(_get(cat, "nwc_amend_bill") for _, _, cat in decs if _get(cat, "nwc_amend_bill"))
    assert ("nwc_bill_amend", "<", "2") in _get(_get(amend, "available"), "check_variable")
    effects = [(k, v) for _, tree in _all_parsed().items() for k, _, v in tree
               if k.startswith("nwc_bill_") and k.endswith("_effect") and isinstance(v, list)]
    assert effects
    for name, body in effects:
        checks = [_get(_get(v, "limit") or [], "check_variable") or [] for k, _, v in body
                  if k in ("if", "else_if")]
        assert any(c and c[0][0] == "nwc_bill_amend" for c in checks), name


@pytest.mark.xfail(strict=True, reason="Fascism focus lands in Task 5")
def test_fascism_suspends_storting():
    focus_dir = CONTENT / "common" / "national_focus"
    text = "".join(f.read_text(encoding="utf-8-sig") for f in focus_dir.rglob("*.txt")) if focus_dir.exists() else ""
    assert "set_country_flag = nwc_storting_suspended" in text or "nwc_storting_suspend = yes" in text


# --- Swedish Opinion ---------------------------------------------------------

SWE_OPINION = "global.nwc_swe_opinion"


def _sweden_monthly():
    body = _get(_parsed("common/scripted_effects/nwc_sweden_effects.txt"), "nwc_sweden_monthly")
    assert body is not None
    return body


def _sweden_event(eid):
    for k, _, v in _parsed("events/nwc_sweden.txt"):
        if k in ("country_event", "news_event") and isinstance(v, list) and _get(v, "id") == eid:
            return v
    raise AssertionError(f"event {eid} missing")


def _band_bounds(limit):
    lo = hi = None
    for k, _, v in limit:
        if k != "check_variable":
            continue
        for var, op, val in v:
            if var != SWE_OPINION:
                continue
            if op == ">=":
                lo = float(val)
            elif op in ("<", "<="):
                hi = (float(val), op)
    return lo, hi


def test_swedish_bands_partition():
    alive = next(v for k, _, v in _sweden_monthly() if k in ("if", "else_if")
                 and ("nwc_gov_alive", "=", "yes") in (_get(v, "limit") or []))
    bands = [_band_bounds(_get(v, "limit") or []) for k, _, v in alive if k in ("if", "else_if")]
    bands = [b for b in bands if b[0] is not None or b[1] is not None]
    assert len(bands) == 4, bands
    bands.sort(key=lambda b: b[0])
    assert bands[0][0] == 0
    for (_, (hi, op)), (nlo, _) in zip(bands, bands[1:]):
        assert op == "<" and hi == nlo
    assert [b[0] for b in bands] == [0, 20, 55, 80]
    assert bands[-1][1] == (100.0, "<=")


def test_union_denmark_war():
    monthly = _sweden_monthly()
    branches = [v for k, _, v in monthly if k in ("if", "else_if")]
    first = branches[0]
    assert ("has_country_flag", "=", "nwc_union_denmark") in _get(first, "limit")
    assert any(("country_event", "=", "nwc_sweden.6") in b for b in _blocks(first))
    assert monthly.index(("if", "=", first)) < monthly.index(next(e for e in monthly if e[0] == "else_if"))
    ev = _sweden_event("nwc_sweden.6")
    targets = {_get(v, "target") for b in _blocks(ev) for k, _, v in b if k == "declare_war_on"}
    assert targets == {"NOR", "DEN"}
    assert not any(k == "puppet" for b in _blocks(ev) for k, _, _ in b)
    assert not any(v == "nwc_game_over_sweden" for b in _blocks(ev) for _, _, v in b)


def _fires(block, eid):
    return any(("country_event", "=", eid) in b for b in _blocks(block))


def test_displeased_needs_two_months():
    gates = [v for b in _blocks(_sweden_monthly()) for k, _, v in b
             if k in ("if", "else_if") and ("country_event", "=", "nwc_sweden.4") in v]
    assert gates
    for g in gates:
        assert ("nwc_swe_low_months", ">=", "2") in (_get(_get(g, "limit"), "check_variable") or [])


def test_puppet_effects_in_order():
    opt = _get(_sweden_event("nwc_sweden.4"), "option")
    keys = [k for k, _, _ in opt]
    i_p, i_f, i_n = keys.index("SWE"), keys.index("set_global_flag"), keys.index("news_event")
    assert i_p < i_f < i_n
    assert ("puppet", "=", "NOR") in opt[i_p][2]
    assert opt[i_f][2] == "nwc_game_over_sweden"
    assert _get(opt[i_n][2], "id") == "nwc_news.20"


@pytest.mark.xfail(strict=True, reason="NOR focus tree lands in Task 5")
def test_puppet_is_game_over():
    tree = _all_parsed()
    focuses = [f for rel, t in tree.items() if "national_focus" in rel
               for b in _blocks(t) for k, _, f in b if k == "focus" and isinstance(f, list)
               and str(_get(f, "id") or "").startswith("nwc_nor_")]
    assert focuses
    for f in focuses:
        assert ("nwc_gov_alive", "=", "yes") in (_get(f, "available") or []), _get(f, "id")
    cats = _parsed("common/decisions/categories/nwc_categories.txt")
    for name, _, body in cats:
        if ("original_tag", "=", "NOR") in (_get(body, "allowed") or []):
            assert ("nwc_gov_alive", "=", "yes") in (_get(body, "visible") or []), name


def test_swedish_bills_scaled():
    effects = _parsed("common/scripted_effects/nwc_sweden_effects.txt")
    for bill in ("nwc_bill_swe_trade", "nwc_bill_swe_border", "nwc_bill_swe_defence"):
        body = _get(effects, bill + "_effect")
        assert body is not None, bill
        deltas = [_get(b, "set_temp_variable") for b in _blocks(body) if _get(b, "set_temp_variable")]
        assert [d[0] for d in deltas] == [("nwc_swe_delta", "=", "10"), ("nwc_swe_delta", "=", "5"),
                                          ("nwc_swe_delta", "=", "3")], bill
        assert ("nwc_swe_opinion_add", "=", "yes") in body, bill


def test_swedish_displeased_band_clears_stance():
    effects = _parsed("common/scripted_effects/nwc_sweden_effects.txt")
    gov = _get(_get(effects, "nwc_sweden_monthly"), "else_if")
    displeased = _get(gov, "if")
    assert ("check_variable", "=", [("global.nwc_swe_opinion", "<", "20")]) in _get(displeased, "limit") \
        or any("20" in str(x) for x in _get(displeased, "limit"))
    for flag in ("nwc_swe_stance_aid", "nwc_swe_stance_intervene"):
        assert ("clr_global_flag", "=", flag) in displeased
    assert ("set_global_flag", "=", "nwc_swe_stance_neutral") in displeased
