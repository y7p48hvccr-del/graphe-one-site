#!/usr/bin/env python3
"""
Pre-upload check for a local curated module tree, BEFORE rclone-ing it to R2.

Usage:
    python3 tools/preflight_module_tree.py "/path/to/curated-root"

The curated root is the folder whose CONTENTS will land under GrapheModules/,
i.e. it must contain   <language>/<category>/<file>.graphe   and nothing else.

Checks (mirrors exactly what generate_catalog_from_bucket.py + the app enforce):
  1. Structure — every module file sits exactly two levels deep
     (language/category/file). Loose or deeper files are flagged.
  2. Extensions — only .graphe / .SQLite3 are catalogued; anything else is
     listed so you can decide whether it belongs in the upload at all.
  3. Global basename uniqueness — the app downloads every module flat into one
     managed folder by file name, so a duplicate basename ANYWHERE in the tree
     means one module silently overwrites another on the user's Mac.
  4. Type-badge coverage — how many file names carry a recognised type token
     (dot or underscore convention) vs. will badge as generic grey "Module".
  5. Name hygiene — leading dots, path-hostile characters, trailing whitespace.

Exit status: 0 = clean, 1 = at least one blocking problem (structure/extension
problems and basename collisions block; badge coverage is informational).
"""

import sys
from collections import defaultdict
from pathlib import Path

# Keep in lock-step with generate_catalog_from_bucket.py
VALID_SUFFIXES = (".graphe", ".SQLite3")
_SUFFIX_TYPES = [
    "_bible", "_commentary", "_commentaries", "_dictionary", "_diction",
    "_encyclopedia", "_devotional", "_devotions", "_crossreference",
    "_crossref", "_strongs", "_lexicon", "_words", "_readingplan", "_plan",
    "_atlas", "_maps", "_map", "_interlinear", "_linguisticstudy",
    "_subheadings",
]
_DOT_TOKENS = [".dictionary.", ".commentaries.", ".devotions.", ".interlinear.", ".plan."]


def has_type_token(filename: str) -> bool:
    lower = filename.lower()
    if any(tok in lower for tok in _DOT_TOKENS):
        return True
    stem = Path(filename).stem.rstrip().lower()
    return any(stem.endswith(s) for s in _SUFFIX_TYPES)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1]).expanduser()
    if not root.is_dir():
        sys.exit(f"ERROR: not a directory: {root}")

    module_files:   list[Path] = []   # correctly-placed language/category/file
    misplaced:      list[Path] = []   # module files at the wrong depth
    foreign:        list[Path] = []   # non-module files (ignored by catalogue)
    hygiene:        list[str]  = []

    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(root)
        if p.name.endswith(VALID_SUFFIXES):
            if len(rel.parts) == 3:
                module_files.append(rel)
            else:
                misplaced.append(rel)
            stem = p.name[: -len(p.suffix)] if p.suffix else p.name
            if stem != stem.strip():
                hygiene.append(f"leading/trailing whitespace in name: {rel}")
            if any(c in p.name for c in ':\\'):
                hygiene.append(f"path-hostile character in name: {rel}")
        else:
            foreign.append(rel)

    by_basename: dict[str, list[Path]] = defaultdict(list)
    for rel in module_files + misplaced:
        by_basename[rel.name].append(rel)
    collisions = {n: ps for n, ps in by_basename.items() if len(ps) > 1}

    untyped = [rel for rel in module_files if not has_type_token(rel.name)]
    languages = sorted({rel.parts[0] for rel in module_files})

    print(f"Scanned: {root}")
    print(f"  module files placed correctly (language/category/file): {len(module_files)}")
    print(f"  languages: {len(languages)}")

    blocking = False

    if misplaced:
        blocking = True
        print(f"\nBLOCKER — {len(misplaced)} module file(s) NOT at language/category/file depth")
        print("(too shallow = skipped from catalogue; too deep = subfolder collapses):")
        for rel in misplaced[:30]:
            print(f"    - {rel}")

    if collisions:
        blocking = True
        print(f"\nBLOCKER — {len(collisions)} duplicate basename(s) — downloads would overwrite each other:")
        for name, paths in sorted(collisions.items())[:30]:
            print(f"    - {name}")
            for rel in paths:
                print(f"        {rel}")

    if hygiene:
        blocking = True
        print(f"\nBLOCKER — {len(hygiene)} name-hygiene issue(s):")
        for h in hygiene[:30]:
            print(f"    - {h}")

    if foreign:
        print(f"\nNote — {len(foreign)} non-module file(s) (catalogue ignores them; "
              "they'd still upload and cost storage):")
        for rel in foreign[:15]:
            print(f"    - {rel}")

    if untyped:
        pct = 100 * len(untyped) // max(len(module_files), 1)
        print(f"\nInfo — {len(untyped)} file(s) ({pct}%) have no type token in the name "
              "and will badge as generic \"Module\" in the catalogue browser:")
        for rel in untyped[:15]:
            print(f"    - {rel.name}")

    print("\nRESULT:", "PROBLEMS FOUND — fix before uploading." if blocking
          else "CLEAN — safe to upload.")
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
