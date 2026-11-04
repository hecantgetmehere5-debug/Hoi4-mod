"""Minimal parser for Paradox (Clausewitz) script text.

parse() returns a list of (key, op, value) entries; value is a string or a nested list.
Bare values inside a block (e.g. `{ a b c }`) are returned as (value, "", "").
"""
from __future__ import annotations

OPS = ("<=", ">=", "=", "<", ">")
_SPECIAL = set('{}=<>"#')


class ParseError(Exception):
    def __init__(self, line: int, msg: str):
        super().__init__(f"line {line}: {msg}")
        self.line, self.msg = line, msg


def _tokens(text: str):
    """Yield (kind, value, line): kind is 'word', 'str', 'op', '{' or '}'."""
    i, line, n = 0, 1, len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace() or c == "﻿":
            i += 1
        elif c == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif c in "{}":
            yield c, c, line
            i += 1
        elif c in "<>=":
            op = text[i:i + 2] if text[i:i + 2] in ("<=", ">=") else c
            yield "op", op, line
            i += len(op)
        elif c == '"':
            start, j = line, i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    j += 1
                if text[j] == "\n":
                    line += 1
                j += 1
            if j >= n:
                raise ParseError(start, "unterminated string")
            yield "str", text[i + 1:j], start
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in _SPECIAL:
                j += 1
            yield "word", text[i:j], line
            i = j


def parse(text: str) -> list[tuple[str, str, str | list]]:
    toks = list(_tokens(text))
    pos = 0

    def block(depth: int, open_line: int) -> list:
        nonlocal pos
        out = []
        while pos < len(toks):
            kind, val, line = toks[pos]
            if kind == "}":
                if depth == 0:
                    raise ParseError(line, "unexpected '}'")
                pos += 1
                return out
            if kind == "op":
                raise ParseError(line, f"unexpected operator {val}")
            if kind == "{":  # anonymous block, e.g. inside a list
                pos += 1
                out.append(("", "", block(depth + 1, line)))
                continue
            pos += 1
            if pos < len(toks) and toks[pos][0] == "op":
                op = toks[pos][1]
                pos += 1
                if pos >= len(toks):
                    raise ParseError(line, f"missing value after {val} {op}")
                vkind, v, vline = toks[pos]
                pos += 1
                if vkind == "{":
                    out.append((val, op, block(depth + 1, vline)))
                elif vkind in ("word", "str"):
                    out.append((val, op, v))
                else:
                    raise ParseError(vline, f"unexpected {v!r} after {val} {op}")
            else:
                out.append((val, "", ""))
        if depth:
            raise ParseError(open_line, "unbalanced '{'")
        return out

    return block(0, 1)
