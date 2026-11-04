import re

from tools import geo, ideologies, pdx
from tools.geo import ROOT

SPEC = ROOT / "docs" / "superpowers" / "specs" / "2026-11-04-faction-content-design.md"
IDS = {"Marxist-Leninism": "communism", "Left Communism": "left_communism", "Anarchism": "anarchist",
       "Mutualism": "mutualism", "Egoism": "egoism", "Democratic Socialism": "democratic_socialism",
       "Social Democracy": "democratic", "Technocracy": "technocracy", "Green Agrarianism": "green_agrarianism",
       "Libertarianism": "libertarianism", "Conservatism": "conservative", "Monarchism": "monarchism",
       "Theocracy": "theocracy", "Oligarchy": "oligarchy", "Fascism": "fascism",
       "National Socialism": "national_socialism", "Totalitarianism (Ingsoc)": "ingsoc",
       "Neo-Paganism": "neo_paganism", "Indigenous Nationalism": "indigenous_nationalism",
       "Animal Rule": "animal_rule", "Military Council": "military_council", "Autocracy": "neutrality"}
# Starting leader display name prefix per faction, taken verbatim from the spec's leader titles.
TITLES = {"NOR": "Prime Minister ", "WFR": "Prime Minister ", "SWE": "Prime Minister ", "DEN": "Prime Minister ",
          "FIN": "Prime Minister ", "SOV": "President ", "SOC": "President ", "FRP": "President ",
          "BRG": "President ", "NRM": "Führer ", "SAP": "Noaidi ", "JNP": "Emir ", "NCL": "Farmers' Union",
          "ABI": "The Assembly", "ANA": "The Assembly"}


def _spec_ideologies():
    text = SPEC.read_text(encoding="utf-8").split("## Custom ideologies")[1].split("###")[0]
    return [m.group(1).strip() for m in re.finditer(r"^\| ([^|]+?) \|", text, re.M)][1:]


def _loc():
    return dict(re.findall(r'^ (\S+?):0 "(.*)"$', ideologies.localisation(), re.M))


def test_spec_ideologies_all_defined_with_their_names():
    ideos = geo.load_ideologies()
    spec = _spec_ideologies()
    assert len(spec) == 22 and sorted(IDS) == sorted(spec)
    assert len(ideos) == 22
    for name, gid in IDS.items():
        assert ideos[gid]["name"] == name


def test_ideology_file_parses_with_every_group_and_a_random_type():
    tree = pdx.parse(ideologies.ideology_file())
    groups = dict((k, v) for k, _, v in tree[0][2])
    assert set(groups) == set(geo.load_ideologies())
    for gid, body in groups.items():
        types = next(v for k, _, v in body if k == "types")
        randomable = [k for k, _, v in types if ("can_be_randomly_selected", "=", "no") not in v]
        assert randomable == [ideologies.subtype(gid)], gid


def test_vanilla_types_kept():
    text = ideologies.ideology_file()
    for t in ("conservatism", "socialism", "stalinism", "nazism", "despotism", "anarchism"):
        assert re.search(rf"^\t\t\t{t} = {{", text, re.M), t


def test_every_group_localised_and_has_icon():
    loc, gfx = _loc(), ideologies.gfx_file()
    for gid in geo.load_ideologies():
        for key in (gid, f"{gid}_noun", f"{gid}_desc", ideologies.subtype(gid)):
            assert loc.get(key), key
        if gid not in ideologies.FACTION_NAMES:
            assert f'"GFX_ideology_{gid}_group"' in gfx


def test_starting_ideologies_exist_and_popularities_total_100():
    ideos = geo.load_ideologies()
    for tag, f in geo.load_factions().items():
        assert f.ideology in ideos, tag
        pops = ideologies.popularities(f)
        assert set(pops) <= set(ideos) and sum(pops.values()) == 100 and pops.get(f.ideology, 0) > 0, tag


def test_party_names_for_every_tag_and_group():
    loc = _loc()
    for tag in set(geo.load_factions()) - ideologies.DROPPED_TAGS:
        for gid in geo.load_ideologies():
            assert loc.get(f"{tag}_{gid}_party") and loc.get(f"{tag}_{gid}_party_long")
    assert loc["NOR_democratic_party"] == "Ap" and loc["SOV_neutrality_party"] == "United Russia"


def test_leader_titles_verbatim():
    loc = _loc()
    assert loc["SOV_leader"] == "President Vladimir Putin"
    assert loc["NOR_leader"] == "Prime Minister Jonas Gahr Støre"
    for tag, title in TITLES.items():
        assert loc[ideologies.leader_id(tag)].startswith(title), tag
    spec = SPEC.read_text(encoding="utf-8")
    for title in {t.strip() for t in TITLES.values()}:
        assert title in spec or title == "Noaidi" and "Sámi: Noaidi" in spec


def test_leaders_use_declared_types_and_are_recruited():
    from tools import history
    text = ideologies.characters_file()
    pdx.parse(text)
    for tag, f in geo.load_factions().items():
        if f.leader:
            assert f"ideology = {ideologies.subtype(f.ideology)}" in text
            assert f"\t{ideologies.leader_id(tag)} = {{" in text
            assert f"recruit_character = {ideologies.leader_id(tag)}" in history.country_history(f, [])


def test_dropped_tags_have_no_localisation():
    assert not [k for k in _loc() if k.startswith("RDN_")]
