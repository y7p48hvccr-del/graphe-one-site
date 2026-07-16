#!/usr/bin/env bash
#
# Promote a vetted .graphe module to the PUBLIC bucket and regenerate the catalogue.
#
#   publish_module.sh <local.graphe> <catalog-relative-path>
#
# <catalog-relative-path> is the path UNDER GrapheModules/ (== the catalog `path`
# and the app's download URL tail), e.g.:
#   publish_module.sh ~/…/Workbench/ACNB.graphe "ACHANG/Bibles__ACHANG/ACNB'10.graphe"
#
# It uploads to  r2:modules-studioeditions/GrapheModules/<catalog-relative-path>
# then runs generate_catalog_from_bucket.py so catalogue == bucket.
# Deploy (git commit + push of graphe-one-site) is a SEPARATE, deliberate step.
set -euo pipefail

REMOTE="r2"
BUCKET="modules-studioeditions"
PREFIX="GrapheModules"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ $# -eq 2 ] || { echo "usage: publish_module.sh <local.graphe> <catalog-relative-path>"; exit 2; }
SRC="$1"; REL="$2"
[ -f "$SRC" ] || { echo "ERROR: no such file: $SRC"; exit 1; }

# Guard: only real modules (SQLite) get published — never a stray HTML/error file.
if [ "$(head -c 15 "$SRC")" != "SQLite format 3" ]; then
  echo "ERROR: $SRC is not a valid module (missing 'SQLite format 3' header). Aborting."
  exit 1
fi

echo "Uploading → r2:$BUCKET/$PREFIX/$REL"
rclone copyto "$SRC" "$REMOTE:$BUCKET/$PREFIX/$REL" --progress

echo "Regenerating catalogue from bucket…"
python3 "$HERE/generate_catalog_from_bucket.py"

echo
echo "Done. Review + deploy:"
echo "  git -C \"$(cd "$HERE/.." && pwd)\" add docs/ScriptureStudy/resources/modules/catalog.json"
echo "  git -C \"$(cd "$HERE/.." && pwd)\" commit -m 'catalogue: add $REL' && git ... push"
