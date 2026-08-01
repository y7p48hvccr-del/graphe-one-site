#!/usr/bin/env python3
"""
Generate ScriptureStudy Pro's module catalogue DIRECTLY from the R2 bucket.

Why this exists
---------------
The catalogue the app browses (catalog.json, served from graphe.one) and the
files it downloads (the R2 bucket) must be IDENTICAL — users are promised a
curated, vetted, guaranteed-working list. The old generate_catalog.py walked a
local staging folder, which drifted from the bucket (folder held thousands;
bucket was empty). This script removes the drift by sourcing the file list from
the bucket itself, via rclone. Catalogue == bucket, by construction.

Prerequisites
-------------
An rclone remote (default name below) authenticated against the NEW R2 account
with Object Read on `modules-studioeditions`. Verify with:

    rclone lsf --recursive r2:modules-studioeditions/GrapheModules/

If that 401s, the token is missing/expired — fix rclone first; this script
cannot invent credentials.

Object layout (must match the app's download URL construction)
--------------------------------------------------------------
    modules-studioeditions/GrapheModules/<language>/<category>/<file>.graphe

The app builds each download URL as moduleBaseURL (".../GrapheModules/") + the
catalog `path`, so `path` here is relative to GrapheModules:
    <language>/<category>/<file>.graphe
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime

# --- Configuration -----------------------------------------------------------

RCLONE_REMOTE = "r2"
BUCKET        = "modules-studioeditions"
KEY_PREFIX    = "GrapheModules"        # objects live under this key prefix

# Resolve the output relative to THIS script's repo, not ~/ — there are two
# graphe-one-site trees (a live git repo under ~/XcodeOffline and an orphan copy
# under ~/). The legacy generators hardcoded Path.home() and wrote to the orphan
# (dead) tree. tools/ is at <repo>/tools/, so the repo root is two levels up.
REPO_ROOT   = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "docs/ScriptureStudy/resources/modules/catalog.json"

VALID_SUFFIXES = (".graphe", ".SQLite3")


# Underscore-suffix conventions used by the converter/library (e.g. "Foo_commentary.graphe"),
# including variants observed in the real corpus (_diction, _commentaries, _map).
# Values are the type strings the app's badge matcher recognises (case-insensitive):
# bible / commentary / dictionary / encyclopedia / devotional / cross-ref / lexicon /
# strongs / reading plan / bible maps — anything else badges grey.
_SUFFIX_TYPES = [
    ("_bible",           "Bible"),
    ("_commentary",      "Commentary"),
    ("_commentaries",    "Commentary"),
    ("_dictionary",      "Dictionary"),
    ("_diction",         "Dictionary"),
    ("_encyclopedia",    "Encyclopedia"),
    ("_devotional",      "Devotional"),
    ("_devotions",       "Devotional"),
    ("_crossreference",  "Cross-Ref"),
    ("_crossref",        "Cross-Ref"),
    ("_strongs",         "Strongs"),
    ("_lexicon",         "Lexicon"),
    ("_words",           "Lexicon"),
    ("_readingplan",     "Reading Plan"),
    ("_plan",            "Reading Plan"),
    ("_atlas",           "Bible Maps"),
    ("_maps",            "Bible Maps"),
    ("_map",             "Bible Maps"),
    ("_interlinear",     "Interlinear"),
    ("_linguisticstudy", "Linguistic Study"),
    ("_subheadings",     "Subheadings"),
]


# Structural dot-tokens (companion/type markers) and the trailing "[iso]"
# bracket are part of the FILENAME convention ("A Faithful Version, 2020
# [en].commentaries.graphe") — globally-unique, self-identifying basenames —
# but noise in a catalogue TITLE shown inside a language section. Strip both.
_TITLE_BRACKET = re.compile(r"\s*\[[^\]]+\]\s*$")
_TITLE_DOT_TOKENS = (".commentaries", ".dictionary", ".devotions", ".interlinear", ".plan")


def display_title(filename: str) -> str:
    stem = Path(filename).stem.rstrip()
    # Peel structural dot-tokens off the tail (may chain).
    changed = True
    while changed:
        changed = False
        low = stem.lower()
        for token in _TITLE_DOT_TOKENS:
            if low.endswith(token):
                stem = stem[: -len(token)].rstrip()
                changed = True
                break
    # Peel an underscore type suffix ("Foo_bible").
    low = stem.lower()
    for suffix, _ in _SUFFIX_TYPES:
        if low.endswith(suffix):
            stem = stem[: -len(suffix)].rstrip()
            break
    # Drop the trailing [iso] bracket — the language section already says it.
    stem = _TITLE_BRACKET.sub("", stem).rstrip()
    return stem or filename


# Category-folder fallback: token-less filenames (the majority — Bibles by
# convention carry no dot-token) take their type from the category folder they
# live in, so the catalogue badge is never a generic "Module" for a correctly
# filed module. Filename tokens still win when present (they are more specific).
_CATEGORY_TYPES = {
    "bibles": "Bible",
    "commentaries": "Commentary",
    "dictionaries": "Dictionary",
    "lexicons": "Lexicon",
    "devotionals": "Devotional",
    "reading plans": "Reading Plan",
    "cross-references": "Cross-Reference",
    "cross references": "Cross-Reference",
    "encyclopedias": "Encyclopedia",
    "maps": "Bible Maps",
}


def infer_type(filename: str, category: str = "") -> str:
    lower = filename.lower()
    # Dot-token convention (legacy): "Foo.dictionary.graphe"
    if ".dictionary."   in lower: return "Dictionary"
    if ".commentaries." in lower: return "Commentary"
    if ".devotions."    in lower: return "Devotional"
    if ".interlinear."  in lower: return "Interlinear"
    if ".plan."         in lower: return "Reading Plan"
    # Underscore-suffix convention: "Foo_commentary.graphe" (tolerate trailing
    # whitespace before the extension, seen in real files: "Foo_map .graphe")
    stem = Path(filename).stem.rstrip().lower()
    for suffix, type_name in _SUFFIX_TYPES:
        if stem.endswith(suffix):
            return type_name
    cat = category.split("__")[0].strip().lower()
    if cat in _CATEGORY_TYPES:
        return _CATEGORY_TYPES[cat]
    return "Module"


def list_bucket_objects() -> list[str]:
    """Return object paths relative to KEY_PREFIX, e.g. 'ACHANG/Bibles__ACHANG/ACNB.graphe'."""
    remote_path = f"{RCLONE_REMOTE}:{BUCKET}/{KEY_PREFIX}/"
    try:
        out = subprocess.run(
            ["rclone", "lsf", "--recursive", "--files-only", remote_path],
            check=True, capture_output=True, text=True,
        ).stdout
    except FileNotFoundError:
        sys.exit("ERROR: rclone is not installed or not on PATH.")
    except subprocess.CalledProcessError as e:
        sys.exit(
            "ERROR: could not list the bucket (rclone exited "
            f"{e.returncode}). Most likely the R2 token is missing/expired.\n"
            f"{e.stderr.strip()}"
        )
    return [line.strip() for line in out.splitlines() if line.strip()]


def main() -> None:
    rel_paths = [p for p in list_bucket_objects() if p.endswith(VALID_SUFFIXES)]

    # languages -> categories -> [resources]
    languages: dict[str, dict[str, list[dict]]] = {}
    skipped: list[str] = []

    # The app downloads every module FLAT into one managed folder using only the
    # file name, so basenames must be unique across the ENTIRE catalogue — a
    # collision means one module silently overwrites another on the user's Mac.
    by_basename: dict[str, list[str]] = {}
    for rel in rel_paths:
        by_basename.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
    collisions = {name: paths for name, paths in by_basename.items() if len(paths) > 1}

    for rel in rel_paths:
        parts = rel.split("/")
        if len(parts) < 3:
            # Not language/category/file — cannot classify; record and skip.
            skipped.append(rel)
            continue
        language, category = parts[0], parts[1]
        filename = parts[-1]
        suffix = Path(filename).suffix

        languages.setdefault(language, {}).setdefault(category, []).append({
            "title": display_title(filename),
            "type": infer_type(filename, category),
            "extension": suffix,
            "path": rel,               # relative to GrapheModules/ — matches moduleBaseURL
        })

    catalog = {
        "generated": datetime.utcnow().isoformat(),
        "source": f"{RCLONE_REMOTE}:{BUCKET}/{KEY_PREFIX}/",
        "languages": [
            {
                "language": lang,
                "categories": {
                    cat: sorted(res, key=lambda r: r["title"])
                    for cat, res in sorted(cats.items())
                },
            }
            for lang, cats in sorted(languages.items())
        ],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    total = sum(len(r) for l in catalog["languages"] for r in l["categories"].values())
    print(f"Generated catalogue from bucket: {OUTPUT_FILE}")
    print(f"  languages: {len(catalog['languages'])}   modules: {total}")
    if skipped:
        print(f"  WARNING: {len(skipped)} object(s) skipped (not language/category/file):")
        for s in skipped[:20]:
            print(f"    - {s}")
    if collisions:
        print(f"  WARNING: {len(collisions)} duplicate basename(s) — downloads will OVERWRITE each other:")
        for name, paths in sorted(collisions.items())[:20]:
            print(f"    - {name}")
            for p in paths:
                print(f"        {p}")
        print("    Rename these in the bucket so every file name is globally unique.")
    if total == 0:
        print("  NOTE: bucket is empty — catalogue will list nothing (this is correct).")


if __name__ == "__main__":
    main()
