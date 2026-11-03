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
    tags = (mod / "common" / "country_tags" / "00_countries.txt").read_text()
    for tag in geo.load_factions():
        assert f"{tag} = " in tags
        assert list((mod / "history" / "countries").glob(f"{tag} - *.txt"))


def test_descriptor_replaces_world(mod):
    text = (mod / "descriptor.mod").read_text()
    for p in ("history/states", "common/country_tags", "map/strategicregions"):
        assert f'replace_path="{p}"' in text


def test_start_date_2030(mod):
    assert '"2030.1.1.12"' in (mod / "common" / "defines" / "00_nwc_defines.lua").read_text()
