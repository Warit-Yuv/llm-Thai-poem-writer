# -*- coding: utf-8 -*-
"""
merge_reviewed_add.py
=====================
Merge the MANUALLY-REVIEWED entries (lines 5-181) of
poetry_overrides_generated.py's POETRY_OVERRIDES_ADD into
poetry_overrides.py's POETRY_OVERRIDES.

Only the reviewed head is merged (per the rebuild rule "don't blindly add
everything").  The unreviewed remainder (lines 182+) contains many w2p
over-split hallucinations and is intentionally left out for a review pass.

Output entries are comment-free, one per line, inserted before the dict's
closing brace, preserving ADD order.  Idempotent: keys already present in the
main dict are skipped (build_overrides excluded them, so normally none).
"""
import ast
import sys

sys.stdout.reconfigure(encoding="utf-8")

MAIN = "poetry_overrides.py"
GEN = "poetry_overrides_generated.py"
REVIEW_LINES = (5, 181)  # inclusive source-line range the user reviewed


def dict_entries(path, var):
    """Yield (key, value, src_line) for a dict literal assigned to var."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (
                    isinstance(t, ast.Name)
                    and t.id == var
                    and isinstance(node.value, ast.Dict)
                ):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant):
                            yield k.value, ast.literal_eval(v), k.lineno
                    return


def main():
    add = list(dict_entries(GEN, "POETRY_OVERRIDES_ADD"))
    lo, hi = REVIEW_LINES
    reviewed = [(k, v, ln) for k, v, ln in add if lo <= ln <= hi]

    main_keys = {k for k, _v, _ln in dict_entries(MAIN, "POETRY_OVERRIDES")}

    new_entries = [(k, v) for k, v, _ln in reviewed if k not in main_keys]
    skipped = [(k, v) for k, v, _ln in reviewed if k in main_keys]

    print(f"ADD total                : {len(add)}")
    print(f"reviewed (lines {lo}-{hi})     : {len(reviewed)}")
    print(f"  already in main (skip) : {len(skipped)}")
    print(f"  to insert              : {len(new_entries)}")

    if not new_entries:
        print("nothing to do")
        return

    block = "\n".join(
        '    "%s": [%s],' % (k, ", ".join('"%s"' % s for s in v))
        for k, v in new_entries
    )

    src = open(MAIN, encoding="utf-8").read().rstrip()
    if not src.endswith("}"):
        raise SystemExit("unexpected tail — refusing to edit")
    body = src[:-1].rstrip()  # everything before the closing brace
    with open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(body + "\n" + block + "\n}\n")
    print(f"inserted {len(new_entries)} entries before the closing brace")


if __name__ == "__main__":
    main()
