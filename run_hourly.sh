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

push_repo() {
  local msg="$1"
  cd "$REPO"
  git add -A
  if git diff --staged --quiet; then echo "  rien à pousser"; return 0; fi
  git commit -m "$msg" >/dev/null
  for i in 1 2 3; do
    git pull --rebase -X ours origin main && git push && return 0
    echo "  push refusé, tentative $i..."; sleep 5
  done
  echo "  ⚠️ push échoué (on continue quand même)"; return 1
}

echo "→ Pipeline newsletter..."
python fractal_pipeline_v6.py || echo "⚠️ pipeline en erreur (on continue)"

echo "→ Push du site (articles)..."
push_repo "site: maj articles $(date '+%F %H:%M')"

echo "→ Préparation du carrousel..."
cd "$IG"
if ! python run.py prepare; then
  echo "⚠️ prepare a échoué — site déjà à jour, on s'arrête là."
  echo "✅ Terminé $(date '+%T')"; exit 0
fi

echo "→ Push des images..."
push_repo "ig: visuels $(date '+%F %H:%M')"

echo "→ Laisser le CDN servir les images..."; sleep 25
echo "→ Publication Instagram..."
cd "$IG"
python run.py publish || echo "⚠️ publish en erreur (sans impact sur le site)"

push_repo "ig: posted.json $(date '+%F %H:%M')"
echo "✅ Terminé $(date '+%T')"
