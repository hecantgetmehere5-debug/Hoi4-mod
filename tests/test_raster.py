import numpy as np
import pytest

from tools import geo, raster


@pytest.fixture(scope="module")
def rasters():
    return raster.state_raster(), raster.heightmap(), raster.lake_mask()


def _px(lon, lat):
    x, y = geo.lonlat_to_px(lon, lat)
    return int(y), int(x)


def test_shapes(rasters):
    for a in rasters:
        assert a.shape == (4096, 3072)


def test_oslo_pixel_is_land(rasters):
    states, _, _ = rasters
    keys = raster.all_state_keys()
    assert keys[states[_px(10.75, 59.93)] - 1] == "oslo"


def test_north_sea_pixel_is_sea(rasters):
    states, height, _ = rasters
    assert states[_px(3.0, 60.0)] == 0
    assert height[_px(3.0, 60.0)] < raster.SEA_LEVEL


def test_all_land_heights_above_sea_level(rasters):
    states, height, lakes = rasters
    land = states > 0
    assert height[land].min() > raster.SEA_LEVEL
    assert height[~land & ~lakes].max() < raster.SEA_LEVEL
    assert (height[lakes] < raster.SEA_LEVEL).all()


def test_every_state_has_pixels(rasters):
    states, _, _ = rasters
    counts = np.bincount(states.ravel(), minlength=len(raster.all_state_keys()) + 1)
    small = [k for i, k in enumerate(raster.all_state_keys()) if counts[i + 1] < 40]
    assert small == []


def test_mjosa_is_lake(rasters):
    _, _, lakes = rasters
    assert lakes[_px(10.85, 60.75)]


def test_lakes_only_in_playable_states(rasters):
    _, _, lakes = rasters
    raw = raster._raw_state_raster()
    assert (raw[lakes] <= len(geo.load_states())).all()
