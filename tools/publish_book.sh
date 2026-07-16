#!/usr/bin/env bash
#
# Promote a vetted .codex book to the PUBLIC books bucket and regenerate the books catalogue.
#
#   publish_book.sh <local.codex> <catalog-relative-path>
#
# <catalog-relative-path> is <collection>/<...>/<file>.codex (== the catalog `path`), e.g.:
#   publish_book.sh ~/…/Workbench/Institutes.codex "Reformed/Calvin/Institutes.codex"
#
# Uploads to  r2:books-studioeditions/<catalog-relative-path>  then runs
# generate_books_catalog_from_bucket.py so catalogue == bucket.
# Deploy (git commit + push of graphe-one-site) is a SEPARATE, deliberate step.
set -euo pipefail

REMOTE="r2"
BUCKET="books-studioeditions"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ $# -eq 2 ] || { echo "usage: publish_book.sh <local.codex> <catalog-relative-path>"; exit 2; }
SRC="$1"; REL="$2"
[ -f "$SRC" ] || { echo "ERROR: no such file: $SRC"; exit 1; }

echo "Uploading → r2:$BUCKET/$REL"
rclone copyto "$SRC" "$REMOTE:$BUCKET/$REL" --progress

echo "Regenerating books catalogue from bucket…"
python3 "$HERE/generate_books_catalog_from_bucket.py"

echo
echo "Done. Review the books catalogue, then git add/commit/push graphe-one-site to deploy."
