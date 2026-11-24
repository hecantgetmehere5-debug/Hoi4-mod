"""Map projection constants and geometry loaders shared by every build stage."""
from pathlib import Path

from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = ROOT / "build" / "src"

CRS = "EPSG:25833"  # UTM zone 33N
PIXEL_M = 400
WIDTH, HEIGHT = 3072, 4096
ORIGIN_E, ORIGIN_N = -100_000, 7_980_000  # top-left corner

_to_map = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
_to_lonlat = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)


def lonlat_to_px(lon, lat):
    e, n = _to_map.transform(lon, lat)
    return (e - ORIGIN_E) / PIXEL_M, (ORIGIN_N - n) / PIXEL_M


def px_to_lonlat(x, y):
    return _to_lonlat.transform(ORIGIN_E + x * PIXEL_M, ORIGIN_N - y * PIXEL_M)


def map_bounds_lonlat(samples=64):
    """Lon/lat bounding box of the whole map rectangle."""
    pts = []
    for i in range(samples + 1):
        t = i / samples
        for x, y in ((t * WIDTH, 0), (t * WIDTH, HEIGHT), (0, t * HEIGHT), (WIDTH, t * HEIGHT)):
            pts.append(px_to_lonlat(x, y))
    lons, lats = zip(*pts)
    return min(lons), min(lats), max(lons), max(lats)


# --- data loaders -----------------------------------------------------------
from dataclasses import dataclass  # noqa: E402

import yaml  # noqa: E402


@dataclass(frozen=True)
class State:
    key: str
    name: str
    vp: str
    kommuner: tuple[str, ...]


@dataclass(frozen=True)
class Faction:
    tag: str
    name: str
    adjective: str
    colour: tuple[int, int, int]
    ideology: str
    capital: str
    puppet_of: str | None = None
    background: bool = False
    spawn: bool = False  # Owns no states at start; released by events.
    cantons: tuple[str, ...] = ()  # NCL states this tag receives when released.
    popularities: tuple[tuple[str, int], ...] = ()  # (group, %) pairs; empty means the default split.
    leader: str | None = None  # Starting leader's display name, title included.
    parties: tuple[tuple[str, str, str], ...] = ()  # (group, short name, long name) overrides.
    portrait: str | None = None  # Slug of content/gfx/leaders/nwc/<slug>.png.


def _yaml(name):
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_ownership() -> dict[str, str]:
    return {str(k): v for k, v in _yaml("ownership.yaml").items()}


def load_sweden() -> dict[str, dict]:
    return {f"SE{k}": v for k, v in _yaml("sweden_strip.yaml").items()}


def load_population() -> dict[str, int]:
    pop = {str(k): v for k, v in _yaml("population_no.yaml").items()}
    pop.update({k: v["pop"] for k, v in load_sweden().items()})
    return pop


def load_states() -> list[State]:
    return [State(k, v["name"], v["vp"], tuple(v["kommuner"])) for k, v in _yaml("states.yaml").items()]


def load_factions() -> dict[str, Faction]:
    return {t: Faction(t, v["name"], v["adjective"], tuple(v["colour"]), v["ideology"],
                       v["capital"], v.get("puppet_of"), v.get("background", False),
                       v.get("spawn", False), tuple(v.get("cantons", ())),
                       tuple(v.get("popularities", {}).items()), v.get("leader"),
                       tuple((g, s, l) for g, (s, l) in v.get("parties", {}).items()),
                       v.get("portrait"))
            for t, v in _yaml("factions.yaml").items()}


def load_ideologies() -> dict[str, dict]:
    return _yaml("ideologies.yaml")


def kommune_owner(code: str) -> str:
    return "SWE" if code.startswith("SE") else load_ownership_cached()[code]


_OWN = None


def load_ownership_cached():
    global _OWN
    if _OWN is None:
        _OWN = load_ownership()
    return _OWN


def state_owner(state: State) -> str:
    owners = {kommune_owner(k) for k in state.kommuner}
    if len(owners) != 1:
        raise ValueError(f"state {state.key} has several owners: {sorted(owners)}")
    return owners.pop()
