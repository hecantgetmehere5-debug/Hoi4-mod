"""Build the mod: python -m tools.build all | install --moddir DIR | preview"""
import argparse
import os
import shutil
from pathlib import Path

from tools import history, mapfiles, preview, provinces
from tools.geo import ROOT

MOD = ROOT / "mod"
MOD_ID = "norway_civil_war"


def build(out: Path = MOD, save_registries: bool = True) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    pm = provinces.provinces()
    if save_registries:
        provinces.save_registry(list(pm.info.values()))
        mapfiles.save_state_registry()
    mapfiles.write_all(out / "map")
    history.write_all(out)
    return out


def install(moddir: Path, src: Path = MOD) -> Path:
    """Link the built mod into the game's mod folder and write the launcher .mod file."""
    moddir.mkdir(parents=True, exist_ok=True)
    link = moddir / MOD_ID
    if link.is_symlink() or link.exists():
        if not link.is_symlink():
            raise SystemExit(f"{link} exists and is not a link; remove it first")
        link.unlink()
    os.symlink(src, link)
    (moddir / f"{MOD_ID}.mod").write_text(history.descriptor(str(link)), encoding="utf-8")
    return link


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["all", "install", "preview"])
    ap.add_argument("--moddir", type=Path,
                    default=Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV" / "mod")
    args = ap.parse_args()
    if args.command == "all":
        print("built", build())
    elif args.command == "install":
        print("linked", install(args.moddir))
    else:
        out = ROOT / "build" / "preview"
        out.mkdir(parents=True, exist_ok=True)
        preview.preview_states(out / "states.png", 0.25)
        print("wrote", out / "states.png")


if __name__ == "__main__":
    main()
