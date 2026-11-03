import importlib.util
import json

import pytest

from tools.geo import ROOT, SRC, load_factions, load_ownership, load_states, state_owner

CITY_STATES = {"oslo": ["0301"], "bergen": ["4601"], "trondheim": ["5001"],
               "stavanger": ["1103"], "kristiansand": ["4204"], "tromso": ["5501"],
               "drammen": ["3301"], "bodo": ["1804"], "fredrikstad": ["3107", "3105"]}


@pytest.fixture(scope="module")
def kommune_codes():
    feats = json.load(open(SRC / "Kommuner-M.geojson"))["features"]
    return {f["properties"]["kommunenummer"] for f in feats}


def _approved_owner():
    spec = importlib.util.spec_from_file_location("mm", ROOT / "reference" / "make_map.py")
    mm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mm)
    tags = {"GOV": "NOR", "WGOV": "WFR", "MUS": "JNP", "KRF": "KRF", "SOC": "SOC", "FRP": "FRP",
            "NRM": "NRM", "SAMI": "SAM", "CEN": "SPM", "AB": "ABI", "BRG": "BRG", "ANA": "ANA"}
    return lambda k: tags[mm.OVERRIDES.get(k, mm.COUNTY[k[:2]])]


def test_every_kommune_owned_once(kommune_codes):
    assert set(load_ownership()) == kommune_codes


def test_ownership_matches_approved_map(kommune_codes):
    approved = _approved_owner()
    own = load_ownership()
    assert {k: own[k] for k in kommune_codes} == {k: approved(k) for k in kommune_codes}


def test_every_kommune_in_exactly_one_state(kommune_codes):
    seen = [k for s in load_states() for k in s.kommuner if not k.startswith("SE")]
    assert sorted(seen) == sorted(kommune_codes)


def test_each_state_single_owner():
    for s in load_states():
        state_owner(s)  # raises if mixed


def test_city_states_exist():
    states = {s.key: s for s in load_states()}
    for key, codes in CITY_STATES.items():
        assert sorted(states[key].kommuner) == sorted(codes)


def test_state_count_between():
    assert 70 <= len(load_states()) <= 140


def test_sweden_strip_has_cities():
    names = {s.vp for s in load_states() if state_owner(s) == "SWE"}
    assert {"Kiruna", "Östersund", "Karlstad", "Strömstad", "Arvika"} <= names


def test_faction_capitals_owned_by_faction():
    states = {s.key: s for s in load_states()}
    for tag, f in load_factions().items():
        assert state_owner(states[f.capital]) == tag


def test_every_owner_is_a_faction():
    tags = set(load_factions())
    assert {state_owner(s) for s in load_states()} == tags
