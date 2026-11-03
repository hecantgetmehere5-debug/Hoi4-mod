"""Download every source dataset into build/src, verifying checksums."""
import hashlib
import math
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from tools.geo import DATA, SRC, map_bounds_lonlat


class ChecksumError(Exception):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, expected: str) -> Path:
    actual = sha256(path)
    if actual != expected:
        raise ChecksumError(f"{path.name}: expected {expected}, got {actual}")
    return path


def _download(url: str, dest: Path, attempts: int = 4) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as r, open(tmp, "wb") as f:
                f.write(r.read())
            tmp.replace(dest)
            return
        except OSError:
            if attempt == attempts - 1:
                raise


def _tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def dem_tiles(z: int) -> list[tuple[int, int]]:
    lon0, lat0, lon1, lat1 = map_bounds_lonlat()
    x0, y0 = _tile_xy(lon0, lat1, z)
    x1, y1 = _tile_xy(lon1, lat0, z)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def fetch_all(dest: Path = SRC) -> dict[str, Path]:
    cfg = yaml.safe_load(open(DATA / "sources.yaml"))
    out = {}
    for key, spec in cfg["files"].items():
        path = dest / spec["url"].rsplit("/", 1)[1]
        if not path.exists() or sha256(path) != spec["sha256"]:
            print(f"downloading {path.name}")
            _download(spec["url"], path)
        out[key] = verify(path, spec["sha256"])
    z = cfg["dem"]["zoom"]
    tile_dir = dest / f"dem{z}"
    tiles = dem_tiles(z)
    missing = [(x, y) for x, y in tiles if not (tile_dir / f"{x}_{y}.png").exists()]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda t: _download(cfg["dem"]["url"].format(z=z, x=t[0], y=t[1]),
                                          tile_dir / f"{t[0]}_{t[1]}.png"), missing))
    if len(list(tile_dir.glob("*.png"))) < len(tiles):
        raise ChecksumError("missing elevation tiles")
    out["dem_tiles"] = tile_dir
    return out


if __name__ == "__main__":
    for k, v in fetch_all().items():
        print(k, v)
    sys.exit(0)
