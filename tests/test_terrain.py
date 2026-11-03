import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

from tools import raster, terrain


@pytest.fixture(scope="module")
def pm():
    return terrain.annotate()


def test_lake_only_province_not_coastal(pm):
    adj = terrain.adjacency()
    for p in pm.info.values():
        if p.kind == "land" and not any(pm.info[q].kind == "sea" for q in adj.get(p.id, ())):
            assert not p.coastal


def test_sea_touching_province_is_coastal(pm):
    adj = terrain.adjacency()
    for p in pm.info.values():
        if p.kind == "land" and any(pm.info[q].kind == "sea" for q in adj.get(p.id, ())):
            assert p.coastal


def test_every_province_has_known_terrain(pm):
    assert {p.terrain for p in pm.info.values()} <= set(terrain.TERRAIN_INDEX)


def test_city_provinces_are_urban(pm):
    oslo = [p for p in pm.info.values() if p.region == "oslo"]
    assert oslo and all(p.terrain == "urban" for p in oslo)


def test_mountains_exist_in_jotunheimen(pm):
    terr = [p.terrain for p in pm.info.values() if p.region in ("nord_gudbrandsdal", "indre_sogn")]
    assert terr.count("mountain") >= 3


def test_rivers_are_one_pixel_wide():
    r = terrain.river_bitmap()
    river = r < terrain.R_WATER
    block = river[:-1, :-1] & river[1:, :-1] & river[:-1, 1:] & river[1:, 1:]
    assert not block.any()


def test_rivers_only_on_land():
    r = terrain.river_bitmap()
    assert raster.land_mask()[r < terrain.R_WATER].all()


def test_every_river_has_a_source():
    r = terrain.river_bitmap()
    lab, n = ndimage.label(r < terrain.R_WATER)
    assert n > 10
    sources = set(np.unique(lab[r == terrain.R_SOURCE]))
    assert set(range(1, n + 1)) <= sources


def test_bmp_formats(tmp_path):
    terrain.write_terrain_bmp(tmp_path / "terrain.bmp")
    terrain.write_rivers_bmp(tmp_path / "rivers.bmp")
    terrain.write_trees_bmp(tmp_path / "trees.bmp")
    terrain.write_normal_map(tmp_path / "world_normal.bmp")
    for name, mode in (("terrain.bmp", "P"), ("rivers.bmp", "P"), ("trees.bmp", "P"), ("world_normal.bmp", "RGB")):
        im = Image.open(tmp_path / name)
        assert im.mode == mode
    assert Image.open(tmp_path / "terrain.bmp").size == (3072, 4096)
    assert Image.open(tmp_path / "world_normal.bmp").size == (1536, 2048)
    assert Image.open(tmp_path / "trees.bmp").size == terrain.trees_size()


def test_dds_header(tmp_path):
    terrain._write_dds_rgba(tmp_path / "a.dds", np.zeros((4, 8, 4), np.uint8))
    data = (tmp_path / "a.dds").read_bytes()
    assert data[:4] == b"DDS " and len(data) == 128 + 4 * 8 * 4
