"""Scan HOI4's error.log for problems this mod can cause.

Usage: python tools/check_log.py ~/Documents/Paradox\\ Interactive/Hearts\\ of\\ Iron\\ IV/logs/error.log
Exit 1 and print the lines if any map, state, province, country or localisation errors are found.
"""
import re
import sys

PATTERNS = re.compile(
    r"province|state|strategic|map[/\\]|definition\.csv|adjacenc|railway|supply|building|"
    r"unitstack|weatherposition|country_tag|countries/|history/|bookmark|localisation|"
    r"provinces\.bmp|heightmap|terrain|rivers",
    re.IGNORECASE)
# Vanilla scripts mention vanilla states and tags that this mod removes; those lines are noise.
NOISE = re.compile(r"common/(national_focus|decisions|ideas|scripted_|ai_|on_actions)|events/|"
                   r"interface/|gfx/", re.IGNORECASE)


def relevant(lines):
    return [l for l in lines if PATTERNS.search(l) and not NOISE.search(l)]


def main(path: str) -> int:
    with open(path, encoding="utf-8", errors="replace") as f:
        hits = relevant(f.read().splitlines())
    for line in hits:
        print(line)
    print(f"{len(hits)} relevant error line(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
