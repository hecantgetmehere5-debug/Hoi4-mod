from collections import Counter

import numpy as np
import pytest
from PIL import Image

from tools import geo, mapfiles, provinces, terrain


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    d = tmp_path_factory.mktemp("map")
    mapfiles.write_provinces_bmp(d / "provinces.bmp")
    mapfiles.write_definition(d / "definition.csv")
    mapfiles.write_unitstacks(d / "unitstacks.txt")
    mapfiles.write_supply_nodes(d / "supply_nodes.txt")
    mapfiles.write_railways(d / "railways.txt")
    return d


def test_definition_matches_bitmap(out):
    rows = [l.split(";") for l in (out / "definition.csv").read_text().splitlines()]
    assert rows[0] == ["0", "0", "0", "0", "land", "false", "unknown", "0"]
    csv_rgb = {tuple(map(int, r[1:4])) for r in rows[1:]}
    a = np.asarray(Image.open(out / "provinces.bmp").convert("RGB")).reshape(-1, 3)
    bmp_rgb = {tuple(c) for c in np.unique(a, axis=0).tolist()}
    assert csv_rgb == bmp_rgb
    assert [int(r[0]) for r in rows] == list(range(len(rows)))


def test_every_province_in_one_strategic_region():
    counts = Counter(p for r in mapfiles.strategic_regions() for p in r.provinces)
    assert set(counts) == set(provinces.provinces().info)
    assert max(counts.values()) == 1


def test_sea_regions_hold_only_sea():
    info = terrain.annotate().info
    for r in mapfiles.strategic_regions():
        kinds = {info[p].kind for p in r.provinces}
        assert kinds <= ({"sea"} if r.weather == "sea" else {"land", "lake"})


def test_railways_connect_only_adjacent_provinces(out):
    adj = terrain.adjacency()
    lines = (out / "railways.txt").read_text().split("\n")
    segs = [list(map(int, l.split())) for l in lines if l]
    assert len(segs) > 100
    for lvl, n, a, b in segs:
        assert n == 2 and 1 <= lvl <= 5 and b in adj[a]


def test_railways_connect_every_mainland_capital():
    rails = mapfiles.railways()
    nodes = {a for _, a, _ in rails} | {b for _, _, b in rails}
    land, index, g = mapfiles._land_graph()
    from scipy.sparse.csgraph import connected_components
    _, comp = connected_components(g, directed=False)
    vps = mapfiles.victory_points()
    caps = [vps[s.key] for s in geo.load_states()]
    sizes = Counter(comp[index[c]] for c in caps)
    shared = {c for c in caps if sizes[comp[index[c]]] > 1}
    assert shared <= nodes


def test_straits_join_all_playable_land():
    info = terrain.annotate().info
    land = [p.id for p in info.values() if p.kind == "land" and not p.region.startswith("waste")]
    adj = terrain.adjacency()
    edges = [(a, b) for a in land for b in adj.get(a, ()) if b in set(land)]
    edges += [(a, b) for a, b, _ in mapfiles.straits()]
    assert len(mapfiles._components(land, edges)) == 1
    for a, b, t in mapfiles.straits():
        if t > 0:
            assert info[t].kind == "sea"
            assert t in adj[a] and t in adj[b]


def test_supply_node_in_every_state_capital(out):
    nodes = {int(l.split()[1]) for l in (out / "supply_nodes.txt").read_text().splitlines()}
    vps = mapfiles.victory_points()
    assert {vps[s.key] for s in geo.load_states()} == nodes


def test_unitstacks_cover_every_province(out):
    provs = {int(l.split(";")[0]) for l in (out / "unitstacks.txt").read_text().splitlines()}
    assert provs == set(provinces.provinces().info)


def test_victory_point_in_own_state():
    sp = mapfiles.state_provinces()
    for key, pid in mapfiles.victory_points().items():
        assert pid in sp[key]


def test_state_ids_gapless():
    ids = sorted(mapfiles.state_ids().values())
    assert ids == list(range(1, len(ids) + 1))


VANILLA_BUILDING_NAMES = {
    "air_base", "anti_air_building", "arms_factory", "bunker", "coastal_bunker", "dam_spawn", "dockyard",
    "floating_harbor", "fuel_silo", "industrial_complex", "landmark_spawn", "locks_spawn", "naval_base_spawn",
    "naval_headquarters", "naval_supply_hub", "nuclear_reactor_spawn", "radar_station", "rocket_site_spawn",
    "special_project_facility_spawn", "stronghold_network", "supply_node", "synthetic_refinery",
}


def test_building_names_match_vanilla(tmp_path):
    mapfiles.write_buildings(tmp_path / "buildings.txt")
    rows = [l.split(";") for l in (tmp_path / "buildings.txt").read_text().splitlines()]
    assert {r[1] for r in rows} <= VANILLA_BUILDING_NAMES
    assert all(len(r) == 7 for r in rows)
    sea = {p.id for p in terrain.annotate().info.values() if p.kind == "sea"}
    for r in rows:
        if r[1] in mapfiles.SEA_LINKED_BUILDINGS:
            assert int(r[6]) in sea


def test_port_positions_land_in_coastal_province(tmp_path):
    """The game finds a building's province from its position; every coastal province needs its port there."""
    mapfiles.write_buildings(tmp_path / "buildings.txt")
    ids = provinces.provinces().ids
    info = terrain.annotate().info
    found = set()
    for line in (tmp_path / "buildings.txt").read_text().splitlines():
        f = line.split(";")
        if f[1] != "naval_base_spawn":
            continue
        x, z = float(f[2]), float(f[4])
        pid = int(ids[int(ids.shape[0] - 1 - z), int(x)])
        assert info[pid].kind == "land" and info[pid].coastal
        found.add(pid)
    coastal = {p.id for p in info.values() if p.kind == "land" and p.coastal}
    assert coastal == found


def test_every_state_in_one_strategic_region():
    region_of = {p: r.id for r in mapfiles.strategic_regions() for p in r.provinces}
    lakes = mapfiles.state_lakes()
    for key, provs in mapfiles.state_provinces().items():
        assert len({region_of[p] for p in provs + lakes.get(key, [])}) == 1, key


def test_sea_regions_are_contiguous():
    adj = terrain.adjacency()
    for r in mapfiles.strategic_regions():
        if r.weather == "sea":
            s = set(r.provinces)
            edges = [(a, b) for a in s for b in adj.get(a, ()) if b in s]
            assert len(mapfiles._components(list(s), edges)) == 1, r.name


def test_all_sea_is_one_connected_ocean():
    info = terrain.annotate().info
    adj = terrain.adjacency()
    sea = [p.id for p in info.values() if p.kind == "sea"]
    s = set(sea)
    assert len(mapfiles._components(sea, [(a, b) for a in sea for b in adj.get(a, ()) if b in s])) == 1


def test_buildings_stand_on_land_in_their_state(tmp_path):
    """The game ignores (and logs) building positions that are not over land."""
    from tools import raster
    mapfiles.write_buildings(tmp_path / "buildings.txt")
    ids = provinces.provinces().ids
    hm = raster.heightmap()
    info = terrain.annotate().info
    key_of = {v: k for k, v in mapfiles.state_ids().items()}
    bad = []
    for line in (tmp_path / "buildings.txt").read_text().splitlines():
        f = line.split(";")
        x, z = int(float(f[2])), int(float(f[4]))
        y = ids.shape[0] - 1 - z
        p = info[int(ids[y, x])]
        if hm[y, x] <= raster.SEA_LEVEL or p.kind != "land" or p.region != key_of[int(f[0])]:
            bad.append(line)
    assert bad == []


def test_state_province_lists_have_no_duplicates(tmp_path):
    from tools import history
    for name, text in history.state_files().items():
        import re
        provs = re.search(r"provinces = \{([^}]*)\}", text).group(1).split()
        assert len(provs) == len(set(provs)), name
