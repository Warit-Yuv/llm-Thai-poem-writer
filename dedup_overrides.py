# -*- coding: utf-8 -*-
"""
dedup_overrides.py
==================
Remove duplicate keys from poetry_overrides.py's POETRY_OVERRIDES dict.

The dict is a single literal merged from two blocks: MAIN (curated, lines
10-425) then GOLD (bulk draft, lines 426+).  When GOLD was pasted in, some
words that already existed in MAIN got repeated -> duplicate keys.

Python silently keeps the LAST value, so the GOLD copy was overriding the
curated MAIN reading at runtime.  This script drops the later (GOLD)
occurrence so MAIN always wins and Pylint stops complaining.

Usage:
    python dedup_overrides.py            # rewrites poetry_overrides.py in place
    python dedup_overrides.py --dry-run  # just report what would be removed
"""
import ast
import sys

sys.stdout.reconfigure(encoding="utf-8")

PATH = "poetry_overrides.py"


def find_dict(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (
                    isinstance(t, ast.Name)
                    and t.id == "POETRY_OVERRIDES"
                    and isinstance(node.value, ast.Dict)
                ):
                    return node.value
    raise SystemExit("POETRY_OVERRIDES dict not found")


def main():
    dry = "--dry-run" in sys.argv
    with open(PATH, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    d = find_dict(tree)

    # safety: entries must be single-line for a clean line-level removal
    multi = [
        (k.lineno, k.end_lineno, v.lineno, v.end_lineno)
        for k, v in zip(d.keys, d.values)
        if not (
            isinstance(k, ast.Constant)
            and k.lineno == v.lineno
            and v.lineno == v.end_lineno
        )
    ]
    if multi:
        print("Refusing: multi-line entries found:", multi)
        sys.exit(1)

    seen = set()
    drop = []
    for k, v in zip(d.keys, d.values):
        if not isinstance(k, ast.Constant):
            continue
        key = k.value
        if key in seen:
            drop.append((k.lineno, key, ast.literal_eval(v)))
        else:
            seen.add(key)

    print("duplicate keys found: %d" % len(drop))
    for lineno, key, val in drop:
        print("  line %-5d %-16r %s" % (lineno, key, "".join(val)))
    if dry:
        return

    lines = src.split("\n")
    drop_set = {lineno for lineno, _k, _v in drop}
    kept = [ln for i, ln in enumerate(lines, start=1) if i not in drop_set]
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept))
    print("removed %d lines -> %s" % (len(drop), PATH))


if __name__ == "__main__":
    main()
