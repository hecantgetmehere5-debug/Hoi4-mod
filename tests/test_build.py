import filecmp
import subprocess
import sys

from tools import build, check_log
from tools.geo import ROOT


def _same_tree(a, b):
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    return not mismatch and not errors and all(_same_tree(a / d, b / d) for d in cmp.common_dirs)


def test_build_twice_is_identical(tmp_path):
    a = build.build(tmp_path / "a", save_registries=False)
    b = build.build(tmp_path / "b", save_registries=False)
    assert _same_tree(a, b)
    for f in ("map/provinces.bmp", "map/definition.csv", "map/default.map", "descriptor.mod",
              "common/bookmarks/nwc_2030.txt"):
        assert (a / f).exists()


def test_check_log_flags_province_errors(tmp_path):
    bad = tmp_path / "bad.log"
    bad.write_text("[12:00:01][map.cpp:1]: Province 123 has no pixels in provinces.bmp\n")
    good = tmp_path / "good.log"
    good.write_text("[12:00:01][common/national_focus/germany.txt:10]: Invalid state 64\n"
                    "[12:00:02][audio.cpp:4]: sound not found\n")
    run = lambda p: subprocess.run([sys.executable, str(ROOT / "tools" / "check_log.py"), str(p)]).returncode
    assert run(bad) == 1
    assert run(good) == 0


def test_install_links_mod(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    link = build.install(tmp_path / "mods", src)
    assert link.is_symlink() and link.resolve() == src.resolve()
    text = (tmp_path / "mods" / "norway_civil_war.mod").read_text()
    assert f'path="{link}"' in text
