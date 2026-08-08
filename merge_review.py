# -*- coding: utf-8 -*-
"""
merge_review.py
===============
Merge the hand-reviewed poetry_overrides_generated_review.py
(POETRY_OVERRIDES_ADD) into poetry_overrides.py (POETRY_OVERRIDES).

* New keys        -> inserted (comment-free, one per line) before the brace
* Reviewed values -> WIN when a key already exists (the user just fixed them)
* Identical keys  -> skipped
* Internal dups   -> deduped (first wins)
"""
import ast
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

MAIN = "poetry_overrides.py"
REV = "poetry_overrides_generated_review.py"


def dict_entries(path, var):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == var and isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant):
                            yield k.value, ast.literal_eval(v), k.lineno
                    return


def main():
    add = {}
    for k, v, _ln in dict_entries(REV, "POETRY_OVERRIDES_ADD"):
        add.setdefault(k, v)  # internal dup -> first wins

    main_entries = list(dict_entries(MAIN, "POETRY_OVERRIDES"))
    main_val = {k: v for k, v, _ln in main_entries}
    main_line = {k: ln for k, _v, ln in main_entries}

    to_insert = {k: v for k, v in add.items() if k not in main_val}
    to_update = {k: v for k, v in add.items() if k in main_val and main_val[k] != v}
    same = {k for k in add if k in main_val and main_val[k] == add[k]}

    print("review unique keys     :", len(add))
    print("  new to insert        :", len(to_insert))
    print("  update (review wins) :", len(to_update))
    for k, v in sorted(to_update.items()):
        print("    UPDATE %-14r %s -> %s" % (k, "".join(main_val[k]), "".join(v)))
    print("  identical (skip)     :", len(same))

    src_lines = open(MAIN, encoding="utf-8").read().split("\n")

    # 1) update existing values in place
    for k, v in to_update.items():
        i = main_line[k] - 1
        line = src_lines[i]
        new_val = ", ".join('"%s"' % s for s in v)
        pat = re.compile(r'(\s*"%s"\s*:\s*)\[[^\]]*\]' % re.escape(k))
        src_lines[i] = pat.sub(lambda m: m.group(1) + "[%s]" % new_val, line)

    # 2) insert new before the closing brace (last line that is just '}')
    close_idx = None
    for i in range(len(src_lines) - 1, -1, -1):
        if src_lines[i].strip() == "}":
            close_idx = i
            break
    if close_idx is None:
        raise SystemExit("closing brace not found")

    block = [
        '    "%s": [%s],' % (k, ", ".join('"%s"' % s for s in v))
        for k, v in to_insert.items()
    ]
    src_lines[close_idx:close_idx] = block

    with open(MAIN, "w", encoding="utf-8") as fh:
        fh.write("\n".join(src_lines))
    print("done: inserted %d, updated %d" % (len(to_insert), len(to_update)))


if __name__ == "__main__":
    main()
