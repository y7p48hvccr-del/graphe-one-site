import json
import os
from pathlib import Path
from datetime import datetime

MODULES_ROOT = Path("/Users/richardbillings/Library/Containers/com.graphe.scripturystudy/Data/Library/Application Support/Graphe/Modules/GrapheModules")

OUTPUT_FILE = Path.home() / "graphe-one-site/docs/ScriptureStudy/resources/modules/catalog.json"

VALID_EXTENSIONS = {
    ".graphe",
    ".SQLite3"
}


def infer_type(filename: str):
    lower = filename.lower()

    if ".dictionary." in lower:
        return "Dictionary"

    if ".commentaries." in lower:
        return "Commentary"

    if ".devotions." in lower:
        return "Devotional"

    if ".interlinear." in lower:
        return "Interlinear"

    if ".plan." in lower:
        return "Reading Plan"

    return "Module"


catalog = {
    "generated": datetime.utcnow().isoformat(),
    "languages": []
}

for language_dir in sorted(MODULES_ROOT.iterdir()):
    if not language_dir.is_dir():
        continue

    language_entry = {
        "language": language_dir.name,
        "categories": {}
    }

    for category_dir in sorted(language_dir.iterdir()):
        if not category_dir.is_dir():
            continue

        resources = []

        for file in sorted(category_dir.iterdir()):
            if not file.is_file():
                continue

            if file.suffix not in VALID_EXTENSIONS and not file.name.endswith(".graphe"):
                continue

            resources.append({
                "title": file.name,
                "type": infer_type(file.name),
                "extension": file.suffix,
                "path": str(file.relative_to(MODULES_ROOT))
            })

        language_entry["categories"][category_dir.name] = resources

    catalog["languages"].append(language_entry)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(catalog, f, ensure_ascii=False, indent=2)

print(f"Generated catalog: {OUTPUT_FILE}")
