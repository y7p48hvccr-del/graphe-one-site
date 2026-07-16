#!/usr/bin/env python3
"""
Generate the ScriptureStudy Pro BOOKS catalogue DIRECTLY from the R2 bucket.

The books lane mirrors the modules lane (see generate_catalog_from_bucket.py):
the catalogue the app browses must be IDENTICAL to what's actually downloadable,
so it is sourced from the public books bucket itself, via rclone — never from a
local folder (which drifts). Catalogue == bucket, by construction.

Buckets (account ec16e5d19ce633a936c91c080b60ffe9):
    dev-books           PRIVATE staging (raw candidates)
    books-studioeditions PUBLIC vetted shelf  <-- this script reads THIS one

Object layout convention (books have no extra key prefix, unlike modules'
GrapheModules/): the first path segment is the COLLECTION, the rest is the
object key.
    books-studioeditions/<collection>/<...>/<file>.codex

Prerequisites: an rclone remote (default `r2`) authenticated for Object Read on
books-studioeditions. Verify:  rclone lsf --recursive r2:books-studioeditions/
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# --- Configuration -----------------------------------------------------------

RCLONE_REMOTE = "r2"
BUCKET        = "books-studioeditions"
KEY_PREFIX    = ""                     # books sit at the bucket root

REPO_ROOT   = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "docs/ScriptureStudy/resources/books/catalog/master.json"

VALID_SUFFIXES = (".codex", ".epub")


def list_bucket_objects() -> list[str]:
    prefix = f"{KEY_PREFIX}/" if KEY_PREFIX else ""
    remote_path = f"{RCLONE_REMOTE}:{BUCKET}/{prefix}"
    try:
        out = subprocess.run(
            ["rclone", "lsf", "--recursive", "--files-only", remote_path],
            check=True, capture_output=True, text=True,
        ).stdout
    except FileNotFoundError:
        sys.exit("ERROR: rclone is not installed or not on PATH.")
    except subprocess.CalledProcessError as e:
        sys.exit(
            "ERROR: could not list the books bucket (rclone exited "
            f"{e.returncode}). Most likely the R2 token is missing/expired.\n"
            f"{e.stderr.strip()}"
        )
    return [line.strip() for line in out.splitlines() if line.strip()]


def main() -> None:
    rel_paths = [p for p in list_bucket_objects() if p.endswith(VALID_SUFFIXES)]

    collections: dict[str, list[dict]] = {}
    skipped: list[str] = []

    for rel in rel_paths:
        parts = rel.split("/")
        if len(parts) < 2:
            # Not collection/file — cannot classify; record and skip.
            skipped.append(rel)
            continue
        collection = parts[0]
        filename = parts[-1]
        collections.setdefault(collection, []).append({
            "title": Path(filename).stem,
            "extension": Path(filename).suffix,
            "path": rel,               # relative to bucket root
        })

    catalog = {
        "generated": datetime.utcnow().isoformat(),
        "source": f"{RCLONE_REMOTE}:{BUCKET}/",
        "collections": [
            {"collection": name, "resources": sorted(res, key=lambda r: r["title"])}
            for name, res in sorted(collections.items())
        ],
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    total = sum(len(c["resources"]) for c in catalog["collections"])
    print(f"Generated BOOKS catalogue from bucket: {OUTPUT_FILE}")
    print(f"  collections: {len(catalog['collections'])}   books: {total}")
    if skipped:
        print(f"  WARNING: {len(skipped)} object(s) skipped (not collection/file):")
        for s in skipped[:20]:
            print(f"    - {s}")
    if total == 0:
        print("  NOTE: bucket is empty — catalogue will list nothing (this is correct).")


if __name__ == "__main__":
    main()
