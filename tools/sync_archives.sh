#!/bin/bash

REPO="$HOME/graphe-one-site"

cd "$REPO" || exit

python3 "$HOME/graphe-one-site/tools/generate_catalog.py"
python3 "$HOME/graphe-one-site/tools/generate_books_catalog.py"
if [[ -n $(git status --porcelain) ]]; then
    git add .
    git commit -m "Automatic catalogue update"
    git push origin main
fi
