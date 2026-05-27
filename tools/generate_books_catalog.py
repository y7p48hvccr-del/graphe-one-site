import json
from pathlib import Path
from datetime import datetime

BOOKS_ROOT = Path("/Users/richardbillings/Books")

OUTPUT_DIR = Path.home() / "graphe-one-site/docs/ScriptureStudy/resources/books/catalog"

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
