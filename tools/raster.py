"""Rasterise states, lakes and elevation onto the fixed map grid."""
import json
import math
from functools import cache

import numpy as np
from affine import Affine
from PIL import Image
from rasterio.features import rasterize
from scipy import ndimage
from shapely.geometry import shape
import shapely
from shapely.ops import unary_union

from tools import geo
from tools.geo import HEIGHT, ORIGIN_E, ORIGIN_N, PIXEL_M, SRC, WIDTH

TRANSFORM = Affine(PIXEL_M, 0, ORIGIN_E, 0, -PIXEL_M, ORIGIN_N)
SEA_LEVEL = 95
MAX_HEIGHT_M = 2470
MIN_LAKE_KM2 = 25
LAKE_HEIGHT = 92
MIN_WASTELAND_PX = 3000
HEIGHT_SPAN = 110  # heightmap value above sea level at MAX_HEIGHT_M


def _project(g):
    return shapely.transform(g, lambda xy: np.column_stack(geo._to_map.transform(xy[:, 0], xy[:, 1])))


def _load(name):
    with open(SRC / name, encoding="utf-8") as f:
        return json.load(f)["features"]


@cache
def kommune_geoms() -> dict:
    out = {}
    for f in _load("Kommuner-L.geojson"):
        out[f["properties"]["kommunenummer"]] = _project(shape(f["geometry"]).buffer(0))
    for f in _load("swedish_municipalities.geojson"):
        out["SE" + f["properties"]["id"]] = _project(shape(f["geometry"]).buffer(0))
    return out


@cache
def wasteland() -> list[tuple[str, str, object]]:
    """(key, owner, geometry) for impassable land outside the playable area."""
    strip = set(geo.load_sweden())
    by_lan: dict[str, list] = {}
    for f in _load("swedish_municipalities.geojson"):
        if "SE" + f["properties"]["id"] not in strip:
            by_lan.setdefault(f["properties"]["lan_code"], []).append(
                _project(shape(f["geometry"]).buffer(0)))
    out = [(f"waste_se_{lan}", "SWE", unary_union(gs)) for lan, gs in sorted(by_lan.items())]
    names = {"Finland": ("waste_fin", "FIN"), "Russia": ("waste_sov", "SOV"), "Denmark": ("waste_den", "DEN")}
    for f in _load("ne_10m_admin_0_countries.geojson"):
        n = f["properties"]["ADMIN"]
        if n in names:
            key, owner = names[n]
            out.append((key, owner, _project(shape(f["geometry"]).buffer(0))))
    box = _map_box()
    min_area = MIN_WASTELAND_PX * PIXEL_M ** 2
    clipped = [(k, o, g.intersection(box)) for k, o, g in out]
    return [(k, o, g) for k, o, g in clipped if g.area >= min_area]


def all_state_keys() -> list[str]:
    """State keys in raster index order (index = position + 1)."""
    return [s.key for s in geo.load_states()] + [k for k, _, _ in wasteland()]


def _rasterize(shapes, fill=0, dtype="uint16"):
    return rasterize(shapes, out_shape=(HEIGHT, WIDTH), transform=TRANSFORM, fill=fill, dtype=dtype)


@cache
def _raw_state_raster() -> np.ndarray:
    geoms = kommune_geoms()
    states = geo.load_states()
    n = len(states)
    shapes = [(g, n + i + 1) for i, (_, _, g) in enumerate(wasteland())]
    shapes += [(unary_union([geoms[k] for k in s.kommuner]), i + 1) for i, s in enumerate(states)]
    r = _rasterize(shapes)
    # Make sure every playable state has pixels even if it is a thin sliver.
    for i, s in enumerate(states):
        if not (r == i + 1).any():
            r |= 0
            touched = _rasterize([(unary_union([geoms[k] for k in s.kommuner]), 1)], dtype="uint8")
            r[touched.astype(bool) & (r == 0)] = i + 1
    return r


@cache
def lake_mask() -> np.ndarray:
    lakes = []
    for name in ("ne_10m_lakes.geojson", "ne_10m_lakes_europe.geojson"):
        for f in _load(name):
            g = _project(shape(f["geometry"]).buffer(0))
            if g.area / 1e6 >= MIN_LAKE_KM2 and g.intersects(_map_box()):
                lakes.append(g)
    m = _rasterize([(g, 1) for g in lakes], dtype="uint8").astype(bool)
    playable = (_raw_state_raster() > 0) & (_raw_state_raster() <= len(geo.load_states()))
    return m & playable


def _map_box():
    from shapely.geometry import box
    return box(ORIGIN_E, ORIGIN_N - HEIGHT * PIXEL_M, ORIGIN_E + WIDTH * PIXEL_M, ORIGIN_N)


@cache
def state_raster() -> np.ndarray:
    """uint16 per pixel: 0 = sea or lake, else index into all_state_keys() + 1."""
    r = _raw_state_raster().copy()
    lakes = lake_mask()
    r[lakes] = 0
    # Fill enclosed slivers between datasets (gaps along borders) with the nearest state.
    water = r == 0
    labels, n = ndimage.label(water)
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    lake_labels = set(np.unique(labels[lakes]))
    sizes = ndimage.sum(water, labels, index=np.arange(n + 1))
    fill = np.zeros(n + 1, bool)
    for lab in range(1, n + 1):
        if lab not in edge and lab not in lake_labels and sizes[lab] < 400:
            fill[lab] = True
    holes = fill[labels]
    if holes.any():
        _, (iy, ix) = ndimage.distance_transform_edt(r == 0, return_indices=True)
        r[holes] = r[iy[holes], ix[holes]]
    return r


def land_mask() -> np.ndarray:
    return state_raster() > 0


def _tile_mosaic(z: int):
    tiles = sorted((tuple(map(int, p.stem.split("_"))), p) for p in (SRC / f"dem{z}").glob("*.png"))
    xs = sorted({t[0][0] for t in tiles})
    ys = sorted({t[0][1] for t in tiles})
    mosaic = np.zeros((len(ys) * 256, len(xs) * 256), np.float32)
    for (x, y), p in tiles:
        a = np.asarray(Image.open(p).convert("RGB"), np.float32)
        h = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
        oy, ox = (y - ys[0]) * 256, (x - xs[0]) * 256
        mosaic[oy:oy + 256, ox:ox + 256] = h
    return mosaic, xs[0], ys[0]


@cache
def elevation_m() -> np.ndarray:
    z = 8
    mosaic, x0, y0 = _tile_mosaic(z)
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float64)
    lon, lat = geo._to_lonlat.transform(ORIGIN_E + (xx + 0.5) * PIXEL_M, ORIGIN_N - (yy + 0.5) * PIXEL_M)
    n = 256 * 2 ** z
    gx = (lon + 180) / 360 * n - x0 * 256 - 0.5
    gy = (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n - y0 * 256 - 0.5
    return ndimage.map_coordinates(mosaic, [gy, gx], order=1, mode="nearest").astype(np.float32)


@cache
def heightmap() -> np.ndarray:
    h = elevation_m()
    land = land_mask()
    out = np.empty(h.shape, np.uint8)
    depth = np.clip(-h, 0, 1000)
    out[:] = np.round(94 - 30 * np.sqrt(depth / 1000)).astype(np.uint8)
    hl = np.clip(h, 0, MAX_HEIGHT_M)
    out[land] = (96 + np.round(HEIGHT_SPAN * (hl[land] / MAX_HEIGHT_M) ** 0.7)).astype(np.uint8)
    out[lake_mask()] = LAKE_HEIGHT
    return out


def write_heightmap(path) -> None:
    Image.fromarray(heightmap(), "L").save(path)
