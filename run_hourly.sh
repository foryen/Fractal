#!/usr/bin/env bash
set -uo pipefail
REPO="$HOME/Fractal"
IG="$REPO/instagram"
VENV="$IG/.venv"
LOG="$IG/cron.log"

exec >> "$LOG" 2>&1
echo "==================== $(date '+%F %T') ===================="
cd "$REPO" || { echo "❌ repo introuvable: $REPO"; exit 1; }
set -a; [ -f "$IG/.env" ] && . "$IG/.env"; set +a
. "$VENV/bin/activate" || { echo "❌ venv introuvable: $VENV"; exit 1; }

echo "→ Pipeline newsletter..."
python fractal_pipeline_v6.py || echo "⚠️ pipeline en erreur (on continue)"

echo "→ Préparation du carrousel..."
cd "$IG"
python run.py prepare || { echo "❌ prepare a échoué"; exit 1; }

echo "→ Push GitHub..."
cd "$REPO"
git add -A
if git diff --staged --quiet; then
  echo "  rien à pousser"
else
  git commit -m "auto: maj $(date '+%F %H:%M')" >/dev/null
  for i in 1 2 3; do
    git pull --rebase -X ours origin main && git push && break
    echo "  push refusé, tentative $i..."; sleep 5
  done
fi

echo "→ Laisser le CDN servir les images..."; sleep 25
echo "→ Publication Instagram..."
cd "$IG"
python run.py publish || echo "⚠️ publish en erreur"

cd "$REPO"
git add -A
if ! git diff --staged --quiet; then
  git commit -m "auto: posted.json $(date '+%F %H:%M')" >/dev/null
  for i in 1 2 3; do git pull --rebase -X ours origin main && git push && break; sleep 5; done
fi
echo "✅ Terminé $(date '+%T')"
