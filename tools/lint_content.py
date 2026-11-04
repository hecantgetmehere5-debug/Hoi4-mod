"""Static checks for hand-written script in content/: python -m tools.lint_content"""
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tools import pdx
from tools.geo import DATA, ROOT

# Vanilla idea ids that content may add/remove without defining them.
VANILLA_IDEAS: set[str] = set()

LOC_KEY = re.compile(r"^\s+([\w.]+):\d?\s")
STATE_TOKEN = re.compile(r"@(STATE|VP):([A-Za-z_0-9]+)@")
TAG_RE = re.compile(r"^[A-Z][A-Z0-9]{2}$")  # scope words (ROOT, PREV, FROM) never match
NOT_TAGS = {"NOT", "AND"}
TAG_VALUE_KEYS = {"tag", "original_tag", "puppet", "has_war_with"}
TAG_TARGET_KEYS = {"annex_country", "declare_war_on"}
VAR_SET_KEYS = {"set_variable", "add_to_variable", "set_variable_to_random",
                "set_temp_variable", "set_temp_variable_to_random", "add_to_temp_variable"}
VAR_ARITH_KEYS = {"subtract_from_variable", "multiply_variable", "divide_variable", "clamp_variable",
                  "round_variable", "modulo_variable", "subtract_from_temp_variable",
                  "multiply_temp_variable", "divide_temp_variable", "clamp_temp_variable",
                  "check_variable"}
IDEA_KEYS = {"add_ideas", "remove_ideas", "swap_ideas"}
EVENT_KEYS = {"country_event", "news_event", "state_event", "unit_leader_event", "operative_leader_event"}


@dataclass
class Index:
    focuses: set = field(default_factory=set)
    decisions: set = field(default_factory=set)
    categories: set = field(default_factory=set)
    events: set = field(default_factory=set)
    ideas: set = field(default_factory=set)
    scripted_effects: set = field(default_factory=set)
    scripted_triggers: set = field(default_factory=set)
    country_flags_set: set = field(default_factory=set)
    country_flags_checked: set = field(default_factory=set)
    global_flags_set: set = field(default_factory=set)
    global_flags_checked: set = field(default_factory=set)
    vars_set: set = field(default_factory=set)
    vars_checked: set = field(default_factory=set)
    loc_keys: set = field(default_factory=set)
    tags_referenced: set = field(default_factory=set)
    mutex: dict = field(default_factory=dict)
    prereqs: dict = field(default_factory=dict)
    # Extra detail used by lint(); not part of the public set list above.
    loc_required: set = field(default_factory=set)
    events_referenced: set = field(default_factory=set)
    ideas_referenced: set = field(default_factory=set)
    effects_referenced: set = field(default_factory=set)
    state_keys: set = field(default_factory=set)
    focus_trees: list = field(default_factory=list)  # (tree id, country-factor tags)
    id_counts: dict = field(default_factory=lambda: {"focus": Counter(), "decision": Counter(), "event": Counter()})
    loc_files: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _kids(block, key):
    return [v for k, _, v in block if k == key] if isinstance(block, list) else []


def _first(block, key):
    vals = _kids(block, key)
    return vals[0] if vals else None


def _flag_name(v):
    if isinstance(v, list):
        v = _first(v, "flag")
    return v.split("@")[0] if isinstance(v, str) else None


def _is_var(v):
    return isinstance(v, str) and v.startswith("nwc_")


def _walk(block, idx: Index):
    """Collect references from every entry of a parsed block, recursively."""
    for key, op, val in block:
        if key == "set_country_flag":
            idx.country_flags_set.add(_flag_name(val))
        elif key == "has_country_flag":
            idx.country_flags_checked.add(_flag_name(val))
        elif key == "set_global_flag":
            idx.global_flags_set.add(_flag_name(val))
        elif key == "has_global_flag":
            idx.global_flags_checked.add(_flag_name(val))
        elif key in VAR_SET_KEYS and isinstance(val, list):
            for k, _, v in val:
                if k == "var":
                    idx.vars_set.add(v)
                elif k not in ("min", "max", "value"):
                    idx.vars_set.add(k)
                if _is_var(v) and k != "var":
                    idx.vars_checked.add(v)
        elif key in VAR_ARITH_KEYS and isinstance(val, list):
            for k, _, v in val:
                if k == "var" and _is_var(v):
                    idx.vars_checked.add(v)
                elif _is_var(k):
                    idx.vars_checked.add(k)
                if k != "var" and _is_var(v):
                    idx.vars_checked.add(v)
        elif key == "var" and _is_var(val):
            idx.vars_checked.add(val)
        if key in EVENT_KEYS:
            ev = _first(val, "id") if isinstance(val, list) else val
            if isinstance(ev, str):
                idx.events_referenced.add(ev)
        if key in IDEA_KEYS:
            vals = [v for v in ([k for k, _, _ in val] + [v for _, _, v in val]) if isinstance(v, str) and v] \
                if isinstance(val, list) else [val]
            idx.ideas_referenced.update(v for v in vals if v not in ("remove_idea", "add_idea"))
        if key.startswith("nwc_") and op == "=" and val == "yes":
            idx.effects_referenced.add(key)
        if TAG_RE.match(key) and key not in NOT_TAGS and isinstance(val, list):
            idx.tags_referenced.add(key)
        if key in TAG_VALUE_KEYS and isinstance(val, str) and TAG_RE.match(val):
            idx.tags_referenced.add(val)
        if key in TAG_TARGET_KEYS and isinstance(val, list):
            t = _first(val, "target")
            if isinstance(t, str) and TAG_RE.match(t):
                idx.tags_referenced.add(t)
        if isinstance(val, list):
            _walk(val, idx)


def _collect_focus_tree(tree, idx: Index):
    tags = set()
    country = _first(tree, "country")
    if isinstance(country, list) and _first(country, "factor") == "0":
        for mod in _kids(country, "modifier"):
            if _first(mod, "add") == "10" and isinstance(_first(mod, "tag"), str):
                tags.add(_first(mod, "tag"))
    idx.focus_trees.append((_first(tree, "id"), tags))
    for focus in _kids(tree, "focus") + _kids(tree, "shared_focus"):
        _collect_focus(focus, idx)


def _collect_focus(focus, idx: Index):
    fid = _first(focus, "id")
    if not isinstance(fid, str):
        return
    idx.focuses.add(fid)
    idx.id_counts["focus"][fid] += 1
    idx.loc_required.update({fid, fid + "_desc"})
    idx.prereqs.setdefault(fid, set()).update(
        f for p in _kids(focus, "prerequisite") for f in _kids(p, "focus"))
    idx.mutex.setdefault(fid, set()).update(
        f for m in _kids(focus, "mutually_exclusive") for f in _kids(m, "focus"))


def _collect_event(ev, idx: Index):
    eid = _first(ev, "id")
    if not isinstance(eid, str):
        return
    idx.events.add(eid)
    idx.id_counts["event"][eid] += 1
    if _first(ev, "hidden") != "yes":
        idx.loc_required.update({eid + ".t", eid + ".d"})
    for opt in _kids(ev, "option"):
        name = _first(opt, "name")
        if isinstance(name, str):
            idx.loc_required.add(name)


def _collect_file(rel: str, tree, idx: Index):
    parts = rel.split("/")
    if "national_focus" in parts:
        for k, _, v in tree:
            if k == "focus_tree":
                _collect_focus_tree(v, idx)
            elif k in ("focus", "shared_focus"):
                _collect_focus(v, idx)
    elif "decisions" in parts and "categories" in parts:
        for k, _, v in tree:
            if isinstance(v, list):
                idx.categories.add(k)
                idx.loc_required.add(k)
    elif "decisions" in parts:
        for cat, _, v in tree:
            for dec, _, body in (v if isinstance(v, list) else []):
                if isinstance(body, list):
                    idx.decisions.add(dec)
                    idx.id_counts["decision"][dec] += 1
                    idx.loc_required.update({dec, dec + "_desc"})
    elif "events" in parts:
        for k, _, v in tree:
            if k in EVENT_KEYS and isinstance(v, list):
                _collect_event(v, idx)
    elif "ideas" in parts:
        for k, _, v in tree:
            for _slot, _, slot in (v if k == "ideas" and isinstance(v, list) else []):
                for idea, _, _body in (slot if isinstance(slot, list) else []):
                    idx.ideas.add(idea)
                    idx.loc_required.add(idea)
    elif "scripted_effects" in parts:
        idx.scripted_effects.update(k for k, _, v in tree if isinstance(v, list))
    elif "scripted_triggers" in parts:
        idx.scripted_triggers.update(k for k, _, v in tree if isinstance(v, list))


def collect(root: Path) -> Index:
    root = Path(root)
    idx = Index()
    for f in sorted(root.rglob("*.txt")):
        rel = f.relative_to(root).as_posix()
        text = f.read_text(encoding="utf-8-sig")
        idx.state_keys.update(m.group(2) for m in STATE_TOKEN.finditer(text))
        try:
            tree = pdx.parse(text)
        except pdx.ParseError as e:
            idx.errors.append(f"{rel}: parse error: {e}")
            continue
        _collect_file(rel, tree, idx)
        # Top-level event definitions are not references; everything nested is walked.
        for k, _, v in tree:
            if isinstance(v, list):
                _walk(v, idx)
    for f in sorted(root.rglob("*.yml")):
        rel = f.relative_to(root).as_posix()
        raw = f.read_bytes()
        text = raw.decode("utf-8-sig")
        idx.loc_files.append((rel, raw.startswith(b"\xef\xbb\xbf"), text))
        idx.state_keys.update(m.group(2) for m in STATE_TOKEN.finditer(text))
        idx.loc_keys.update(m.group(1) for line in text.splitlines() if (m := LOC_KEY.match(line + " ")))
    idx.country_flags_set.discard(None)
    idx.global_flags_set.discard(None)
    idx.country_flags_checked.discard(None)
    idx.global_flags_checked.discard(None)
    return idx


def _known_tags(factions: Path, vanilla: Path) -> set[str]:
    tags = set(yaml.safe_load(open(factions, encoding="utf-8")) or {})
    for line in open(vanilla, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if line:
            tags.add(line)
    return tags


def lint(root: Path, factions: Path = DATA / "factions.yaml", vanilla: Path = DATA / "vanilla_tags.txt",
         states: Path = DATA / "states.yaml") -> list[str]:
    idx = collect(root)
    errors = list(idx.errors)
    tags = _known_tags(factions, vanilla)
    state_keys = set(yaml.safe_load(open(states, encoding="utf-8")) or {})

    for rel, bom, text in idx.loc_files:
        if not bom:
            errors.append(f"{rel}: no BOM")
        first = next((ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")), "")
        if first != "l_english:":
            errors.append(f"{rel}: missing l_english header")
    for key in sorted(idx.loc_required - idx.loc_keys):
        errors.append(f"missing loc: {key}")
    for kind, counts in idx.id_counts.items():
        errors.extend(f"duplicate {kind}: {i}" for i, n in sorted(counts.items()) if n > 1)
    for fid, pre in sorted(idx.prereqs.items()):
        errors.extend(f"unknown focus {p} (prerequisite of {fid})" for p in sorted(pre - idx.focuses))
    for fid, mx in sorted(idx.mutex.items()):
        for other in sorted(mx):
            if other not in idx.focuses:
                errors.append(f"unknown focus {other} (mutually exclusive with {fid})")
            elif fid not in idx.mutex.get(other, set()):
                errors.append(f"mutex not symmetric: {fid} -> {other}")
    errors.extend(f"unknown event {e}" for e in sorted(idx.events_referenced - idx.events))
    errors.extend(f"unknown tag {t}" for t in sorted(idx.tags_referenced - tags))
    errors.extend(f"flag never set: country flag {f}" for f in sorted(idx.country_flags_checked - idx.country_flags_set))
    errors.extend(f"flag never set: global flag {f}" for f in sorted(idx.global_flags_checked - idx.global_flags_set))
    errors.extend(f"flag never set: variable {v}" for v in sorted(idx.vars_checked - idx.vars_set))
    errors.extend(f"unknown state key {k}" for k in sorted(idx.state_keys - state_keys))
    errors.extend(f"unknown idea {i}" for i in sorted(idx.ideas_referenced - idx.ideas - VANILLA_IDEAS))
    errors.extend(f"unknown scripted effect {e}" for e in
                  sorted(idx.effects_referenced - idx.scripted_effects - idx.scripted_triggers))
    for tree_id, ttags in idx.focus_trees:
        if not ttags:
            errors.append(f"focus tree {tree_id}: missing country factor (country = {{ factor = 0 modifier = {{ add = 10 tag = X }} }})")
        errors.extend(f"focus tree {tree_id}: unknown tag {t} in country factor" for t in sorted(ttags - tags))
    return errors


def main() -> int:
    errors = lint(ROOT / "content")
    for e in errors:
        print(e)
    print(f"{len(errors)} content problem(s)" if errors else "content lints clean")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
