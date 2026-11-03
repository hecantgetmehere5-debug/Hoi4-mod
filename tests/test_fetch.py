import hashlib

import pytest

from tools.fetch import ChecksumError, verify


def test_fetch_verifies_checksum(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    good = hashlib.sha256(b"hello").hexdigest()
    assert verify(f, good) == f
    with pytest.raises(ChecksumError):
        verify(f, "0" * 64)


def test_dem_tile_range_covers_norway():
    from tools.fetch import dem_tiles
    tiles = dem_tiles(8)
    xs = {x for x, _ in tiles}
    ys = {y for _, y in tiles}
    # Lindesnes (7.0E, 58.0N) and Vardø (31.1E, 70.4N) at zoom 8
    assert 132 in xs and 150 in xs
    assert 77 in ys and 56 in ys
