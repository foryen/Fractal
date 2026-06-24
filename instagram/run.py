# -*- coding: utf-8 -*-
"""
run.py — Orchestrateur de l'automatisation Instagram de Fractal.

Deux étapes (séparées car Instagram télécharge les images depuis une URL publique,
donc il faut commiter/pousser les PNG AVANT de publier) :

  python run.py prepare   -> choisit le meilleur article non posté, génère slides + légende,
                             écrit instagram/out/manifest.json. (À committer/pousser ensuite.)
  python run.py publish   -> lit le manifest, construit les URLs publiques, publie le
                             carrousel, marque l'article comme posté dans posted.json.

Variables d'env utiles :
  GROQ_API_KEY, IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_VERSION
  PUBLIC_BASE_URL  -> base publique où seront servis les PNG
                      ex: https://raw.githubusercontent.com/foryen/Fractal/main/instagram/out
                      ou  https://foryen.github.io/Fractal/instagram/out
"""
import argparse, json, os, pathlib, datetime

ROOT = pathlib.Path(__file__).parent
DATA = ROOT.parent / "newsletter_data.json"
OUT = ROOT / "out"
POSTED = ROOT / "posted.json"
MANIFEST = OUT / "manifest.json"

def _load(p, default):
    return json.loads(p.read_text("utf-8")) if p.exists() else default

def _key(article):
    """Clé stable d'un article : son lien source original."""
    return article.get("_meta", {}).get("lien_source") or article["titre_newsletter"]

def select_article(data, posted):
    """Le mieux classé (les articles sont déjà triés par score) non encore posté."""
    for art in data["articles"]:
        if _key(art) not in posted:
            return art
    return None

def cmd_prepare(args):
    from render import render_article
    from slides_copy import generate_slide_copy

    data = _load(DATA, {"articles": []})
    posted = _load(POSTED, {})
    art = select_article(data, posted)
    if art is None:
        print("ℹ️  Aucun nouvel article à publier (tous déjà postés).")
        MANIFEST.write_text(json.dumps({"empty": True}), "utf-8")
        return

    print(f"🎯 Article sélectionné : {art['titre_newsletter']}")
    print("🤖 Génération de la copy des slides (IA)...")
    copy = generate_slide_copy(art)
    files = render_article(art, OUT, copy=copy)
    caption = copy["caption"]

    manifest = {
        "empty": False,
        "key": _key(art),
        "title": art["titre_newsletter"],
        "files": [f.name for f in files],
        "caption": caption,
        "prepared_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    print(f"✅ {len(files)} slides + légende prêtes. Manifest écrit.")

def cmd_publish(args):
    from ig_official_post import Publisher

    manifest = _load(MANIFEST, {"empty": True})
    if manifest.get("empty"):
        print("ℹ️  Rien à publier.")
        return

    base = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    urls = [f"{base}/{name}" for name in manifest["files"]]
    print(f"📤 Publication du carrousel ({len(urls)} slides)...")

    media_id = Publisher().publish_carousel(urls, manifest["caption"])
    print(f"✅ Publié. media_id = {media_id}")

    posted = _load(POSTED, {})
    posted[manifest["key"]] = {
        "title": manifest["title"],
        "media_id": media_id,
        "posted_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    POSTED.write_text(json.dumps(posted, ensure_ascii=False, indent=2), "utf-8")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    sub.add_parser("publish")
    args = ap.parse_args()
    {"prepare": cmd_prepare, "publish": cmd_publish}[args.cmd](args)
