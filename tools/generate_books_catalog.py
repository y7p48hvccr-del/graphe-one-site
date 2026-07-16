import json
from pathlib import Path
from datetime import datetime

BOOKS_ROOT = Path("/Users/richardbillings/Books")

# NOTE: writes into THIS script's repo, not ~/. There are two graphe-one-site
# trees — a live git repo under ~/XcodeOffline and an orphan copy under ~/. The
# original hardcoded Path.home() and wrote to the orphan (dead) tree.
# TODO (books lane): like the modules catalogue, this should be regenerated from
# the PUBLIC books bucket (see generate_catalog_from_bucket.py), not from the
# local ~/Books folder, so catalogue == bucket. Local-folder sourcing drifts.
REPO_ROOT  = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs/ScriptureStudy/resources/books/catalog"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

catalog = {
    "generated": datetime.utcnow().isoformat(),
    "collections": []
}

for collection_dir in sorted(BOOKS_ROOT.iterdir()):

    if not collection_dir.is_dir():
        continue

    collection = {
        "collection": collection_dir.name,
        "resources": []
    }

    for file in sorted(collection_dir.rglob("*")):

        if not file.is_file():
            continue

        collection["resources"].append({
            "title": file.stem,
            "extension": file.suffix,
            "path": str(file.relative_to(BOOKS_ROOT))
        })

    catalog["collections"].append(collection)

with open(OUTPUT_DIR / "master.json", "w", encoding="utf-8") as f:
    json.dump(catalog, f, ensure_ascii=False, indent=2)

print("Generated Books catalogue")
