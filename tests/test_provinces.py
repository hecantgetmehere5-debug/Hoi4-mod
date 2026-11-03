import dataclasses

import numpy as np
import pytest
from scipy import ndimage

from tools import geo, provinces, raster


def _clear_caches():
    for f in (raster.kommune_geoms, raster.wasteland, raster._raw_state_raster, raster.lake_mask,
              raster.state_raster, raster.elevation_m, raster.heightmap, provinces.provinces):
        f.cache_clear()


@pytest.fixture(scope="module")
def fresh():
    _clear_caches()
    return provinces.build_provinces([])


def test_province_never_crosses_state(fresh):
    states = raster.state_raster()
    keys = raster.all_state_keys()
    for p in fresh.info.values():
        if p.kind != "land":
            continue
        vals = np.unique(states[fresh.ids == p.id]) if p.size < 5000 else None
        if vals is not None:
            assert [keys[v - 1] for v in vals] == [p.region]
    # Full check: every pixel's state matches its province's region.
    lut = np.zeros(max(fresh.info) + 1, np.int32)
    idx = {k: i + 1 for i, k in enumerate(keys)}
    for p in fresh.info.values():
        lut[p.id] = idx.get(p.region, 0)
    land = states > 0
    assert (lut[fresh.ids][land] == states[land]).all()


def test_all_provinces_connected(fresh):
    bad = []
    for pid, sl in enumerate(ndimage.find_objects(fresh.ids), start=1):
        if sl is None:
            continue
        _, n = ndimage.label(fresh.ids[sl] == pid)
        if n != 1:
            bad.append(pid)
    assert bad == []


def test_ids_are_gapless(fresh):
    assert sorted(fresh.info) == list(range(1, len(fresh.info) + 1))
    assert set(np.unique(fresh.ids)) == set(fresh.info)


def test_min_province_size(fresh):
    small = [p.id for p in fresh.info.values() if p.size < 10]  # vanilla's smallest is 10 px
    assert small == []


def test_province_boxes_not_too_large(fresh):
    wide = []
    for pid, sl in enumerate(ndimage.find_objects(fresh.ids), start=1):
        if sl is not None and max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) > provinces.MAX_BOX_PX:
            wide.append(pid)
    assert wide == []


def test_colours_unique(fresh):
    rgbs = [p.rgb for p in fresh.info.values()]
    assert len(set(rgbs)) == len(rgbs)
    assert (0, 0, 0) not in rgbs


def test_land_province_count(fresh):
    n = sum(1 for p in fresh.info.values() if p.kind == "land" and not p.region.startswith("waste"))
    assert 700 <= n <= 2500


def test_rebuild_unchanged_is_identical(fresh):
    reg = [{"id": p.id, "region": p.region, "kind": p.kind, "seed": list(p.seed), "rgb": list(p.rgb)}
           for p in fresh.info.values()]
    again = provinces.build_provinces(reg)
    assert (again.ids == fresh.ids).all()
    assert {k: v.rgb for k, v in again.info.items()} == {k: v.rgb for k, v in fresh.info.items()}


def test_rerun_ids_stable(fresh, monkeypatch):
    reg = [{"id": p.id, "region": p.region, "kind": p.kind, "seed": list(p.seed), "rgb": list(p.rgb)}
           for p in fresh.info.values()]
    states = geo.load_states()
    moved = []
    for s in states:
        if s.key == "moss":
            s = dataclasses.replace(s, kommuner=tuple(k for k in s.kommuner if k != "3110"))
        elif s.key == "fredrikstad":
            s = dataclasses.replace(s, kommuner=s.kommuner + ("3110",))
        moved.append(s)
    monkeypatch.setattr(geo, "load_states", lambda: moved)
    _clear_caches()
    try:
        after = provinces.build_provinces(reg)
    finally:
        monkeypatch.undo()
        _clear_caches()
    before = {(p.region, p.seed): (p.id, p.rgb) for p in fresh.info.values()
              if p.region not in ("moss", "fredrikstad")}
    now = {(p.region, p.seed): (p.id, p.rgb) for p in after.info.values()}
    changed = {k: (v, now.get(k)) for k, v in before.items() if now.get(k) != v}
    assert changed == {}
    assert sorted(after.info) == list(range(1, len(after.info) + 1))


def test_no_x_crossings(fresh):
    assert len(provinces._x_crossings(fresh.ids)) == 0
