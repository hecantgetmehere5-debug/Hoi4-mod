import re

import pytest

from tools import geo, history, mapfiles


@pytest.fixture(scope="module")
def mod(tmp_path_factory):
    d = tmp_path_factory.mktemp("mod")
    history.write_all(d)
    return d


def _owner(text):
    return re.search(r"owner = (\w+)", text).group(1)


def test_every_state_file_has_owner_from_ownership(mod):
    owners = {s.key: geo.state_owner(s) for s in geo.load_states()}
    files = {p.name: p.read_text() for p in (mod / "history" / "states").iterdir()}
    for key, owner in owners.items():
        name = f"{mapfiles.state_ids()[key]}-{key}.txt"
        assert _owner(files[name]) == owner


def test_state_ids_match_registry(mod):
    sid = mapfiles.state_ids()
    for p in (mod / "history" / "states").iterdir():
        num, key = p.stem.split("-", 1)
        assert sid[key] == int(num)
        assert f"id = {num}\n" in p.read_text()


def test_wfr_is_puppet_of_nor(mod):
    nor = next((mod / "history" / "countries").glob("NOR - *.txt")).read_text()
    assert "set_autonomy = { target = WFR autonomous_state = autonomy_puppet }" in nor


def test_ana_owns_every_pocket_state():
    pockets = {"grane", "sigdal", "flesberg", "valer_hedmark", "alvdal", "sel", "vestre_slidre",
               "gulen", "rennebu", "skaun", "meraker", "sor_varanger"}
    owned = {s.key for s in geo.load_states() if geo.state_owner(s) == "ANA"}
    assert owned == pockets


def test_oslo_is_jnp(mod):
    name = f"{mapfiles.state_ids()['oslo']}-oslo.txt"
    assert _owner((mod / "history" / "states" / name).read_text()) == "JNP"


def test_localisation_has_bom(mod):
    data = (mod / "localisation" / "english" / "nwc_map_l_english.yml").read_bytes()
    assert data.startswith(b"\xef\xbb\xbfl_english:")


def test_every_tag_has_flag_files(mod):
    for tag in geo.load_factions():
        for sub in ("", "medium", "small"):
            assert (mod / "gfx" / "flags" / sub / f"{tag}.tga").exists()


def test_every_tag_has_history_and_country_file(mod):
    tags = (mod / "common" / "country_tags" / "nwc_countries.txt").read_text()
    for tag in geo.load_factions():
        assert (f"{tag} = " in tags) != (tag in history.VANILLA_COUNTRY_FILES)
        assert list((mod / "history" / "countries").glob(f"{tag} - *.txt"))


def test_descriptor_replaces_world(mod):
    text = (mod / "descriptor.mod").read_text()
    for p in ("history/states", "map/strategicregions"):
        assert f'replace_path="{p}"' in text


def test_start_date_2030(mod):
    assert '"2030.1.1.12"' in (mod / "common" / "defines" / "00_nwc_defines.lua").read_text()


def test_new_tags_do_not_clash_with_vanilla():
    import os
    vanilla = os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Hearts of Iron IV/"
                                 "common/country_tags/00_countries.txt")
    if not os.path.exists(vanilla):
        pytest.skip("HOI4 not installed")
    taken = {l.split("=")[0].strip() for l in open(vanilla, encoding="utf-8", errors="ignore") if "=" in l}
    for tag in geo.load_factions():
        assert (tag in taken) == (tag in history.VANILLA_COUNTRY_FILES), tag


def test_supported_version_format(mod):
    assert re.search(r'supported_version="\d+\.\d+\.\*"', (mod / "descriptor.mod").read_text())


def test_tutorial_has_no_vanilla_map_ids(mod):
    """Vanilla's tutorial moves the camera to vanilla state 550; any state/province id there crashes game start."""
    text = (mod / "tutorial" / "tutorial.txt").read_text()
    assert not re.search(r"\b(state|target|direction_pointer|highlight_\w+)\s*=", text)


EXPECTED_DIVISIONS = {"NOR": 24, "WFR": 20, "FRP": 22, "KRF": 13, "SOC": 13, "NRM": 13, "SAP": 13, "ABI": 13,
                      "NCL": 8, "BRG": 0, "JNP": 5, "SWE": 0, "FIN": 0, "SOV": 0, "DEN": 0}


def _units(mod, tag):
    return (mod / "history" / "units" / f"{tag}_2030.txt").read_text()


def _locations(text):
    return [int(x) for x in re.findall(r"location = (\d+)", text)]


def test_division_counts_per_tag(mod):
    for tag, n in EXPECTED_DIVISIONS.items():
        assert len(_locations(_units(mod, tag))) == n, tag


def test_ana_has_three_per_pocket_at_low_equipment(mod):
    text = _units(mod, "ANA")
    sp = mapfiles.state_provinces()
    pockets = [s.key for s in geo.load_states() if geo.state_owner(s) == "ANA"]
    locs = _locations(text)
    assert len(locs) == 3 * len(pockets)
    for k in pockets:
        assert sum(p in sp[k] for p in locs) == 3, k
    assert set(re.findall(r"start_equipment_factor = ([\d.]+)", text)) == {"0.2"}


def test_division_locations_are_owned_land_not_wasteland(mod):
    sp = mapfiles.state_provinces()
    owner_of = {p: geo.state_owner(s) for s in geo.load_states() for p in sp[s.key]}
    waste = {p for k, v in sp.items() if mapfiles.is_wasteland(k) for p in v}
    for tag, f in geo.load_factions().items():
        if f.spawn:
            assert not (mod / "history" / "units" / f"{tag}_2030.txt").exists(), tag
            continue
        for p in _locations(_units(mod, tag)):
            assert owner_of.get(p) == tag, (tag, p)
            assert p not in waste


def test_ncl_and_brg_get_economy_idea(mod):
    for tag in ("NCL", "BRG"):
        text = next((mod / "history" / "countries").glob(f"{tag} - *.txt")).read_text()
        assert "\tnwc_civilian_boom" in text


REUSED_SPAWN = {"EST": "Estonia", "LAT": "Latvia", "LIT": "Lithuania", "ICE": "Iceland", "SCO": "Scotland"}


def _spawn_tags():
    return [t for t, f in geo.load_factions().items() if f.spawn]


def test_spawn_tags_have_files_but_no_states(mod):
    spawn = _spawn_tags()
    assert set(spawn) == {"RDN", "GMO"} | set(REUSED_SPAWN)
    owners = {geo.state_owner(s) for s in geo.load_states()}
    sid = mapfiles.state_ids()
    for tag in spawn:
        f = geo.load_factions()[tag]
        country = history.VANILLA_COUNTRY_FILES.get(tag, history._file_name(f))
        assert (mod / "common" / "countries" / f"{country}.txt").exists(), tag
        files = list((mod / "history" / "countries").glob(f"{tag} - *.txt"))
        assert len(files) == 1, tag
        text = files[0].read_text()
        assert f"capital = {sid[f.capital]}\n" in text
        assert "owner" not in text
        assert (mod / "gfx" / "flags" / f"{tag}.tga").exists()
        assert tag not in owners, tag


def test_spawn_tags_in_tag_list(mod):
    tags = (mod / "common" / "country_tags" / "nwc_countries.txt").read_text()
    for tag in ("RDN", "GMO"):
        assert tag not in history.VANILLA_COUNTRY_FILES
        assert tags.count(f"{tag} = ") == 1
    for tag in REUSED_SPAWN:
        assert f"{tag} = " not in tags


def test_reused_tag_history_overwrites_vanilla(mod):
    for tag, name in REUSED_SPAWN.items():
        assert history.VANILLA_COUNTRY_FILES[tag] == name
        text = (mod / "history" / "countries" / f"{tag} - {name}.txt").read_text()
        assert "owner" not in text and "set_politics" not in text and "oob" not in text


def test_canton_states_owned_by_ncl(mod):
    keys = {s.key for s in geo.load_states()}
    files = {p.name: p.read_text() for p in (mod / "history" / "states").iterdir()}
    sid = mapfiles.state_ids()
    for tag, f in geo.load_factions().items():
        for key in f.cantons:
            assert key in keys
            assert _owner(files[f"{sid[key]}-{key}.txt"]) == "NCL", (tag, key)
    expected = {"EST": ["hamar", "ringsaker"], "LAT": ["lillehammer", "midt_gudbrandsdal", "nord_gudbrandsdal"],
                "LIT": ["valdres"], "ICE": ["sor_osterdal", "nord_osterdal", "trysil"], "SCO": ["land"]}
    for tag, states in expected.items():
        f = geo.load_factions()[tag]
        assert list(f.cantons) == states and f.capital == states[0]
