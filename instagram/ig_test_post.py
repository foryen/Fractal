# -*- coding: utf-8 -*-
"""
ig_test_post.py — TEST de publication : poste un carrousel de slides vides
sur un compte Instagram, via instagrapi (API privée non officielle).

⚠️  À utiliser UNIQUEMENT sur ton compte de test (risque de blocage du compte).
    Pour de la prod durable, on repassera sur l'API Graph officielle.

Prérequis :
    pip install instagrapi pillow      (dans un venv de préférence)

Identifiants : passe-les en variables d'environnement, ne les écris jamais en dur.
    export IG_USERNAME="ton_compte_test"
    export IG_PASSWORD="ton_mot_de_passe"
    # si 2FA activée : export IG_2FA="123456"

Lancement :
    python ig_test_post.py
    python ig_test_post.py --slides 6 --caption "Mon test carrousel"
"""
import argparse, os, sys, pathlib
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client

HERE = pathlib.Path(__file__).parent
OUT = HERE / "blank_slides"
SESSION = HERE / "session.json"   # garde la session entre les runs (à .gitignore !)

# Couleurs de test (fond sombre + accent vert, clin d'œil à la charte Fractal)
BG = (9, 9, 11)
FG = (52, 211, 153)
W, H = 1080, 1350   # format portrait 4:5

def _font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def generer_slides(n: int) -> list[str]:
    """Crée n images vides numérotées 1..n. Retourne les chemins (JPEG)."""
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(1, n + 1):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        # petit cadre + numéro de slide pour vérifier l'ordre du carrousel
        d.rectangle([40, 40, W - 40, H - 40], outline=FG, width=4)
        txt = str(i)
        f = _font(280)
        bbox = d.textbbox((0, 0), txt, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((W - tw) / 2 - bbox[0], (H - th) / 2 - bbox[1]), txt, font=f, fill=(255, 255, 255))
        # Instagram préfère le JPEG ; on enregistre directement en .jpg
        p = OUT / f"slide_{i:02d}.jpg"
        img.save(p, "JPEG", quality=90)
        paths.append(str(p))
    return paths

def login() -> Client:
    user = os.environ.get("IG_USERNAME")
    pwd = os.environ.get("IG_PASSWORD")
    if not user or not pwd:
        sys.exit("❌ Définis IG_USERNAME et IG_PASSWORD dans tes variables d'environnement.")

    cl = Client()
    # Réutiliser la session évite de relogger à chaque run (sinon -> challenge_required)
    if SESSION.exists():
        cl.load_settings(SESSION)
        try:
            cl.login(user, pwd)            # reprend la session sauvegardée
            cl.get_timeline_feed()         # vérifie qu'elle est encore valide
            print("🔓 Session existante réutilisée.")
            return cl
        except Exception:
            print("⚠️  Session expirée, reconnexion complète...")
            cl = Client()

    code = os.environ.get("IG_2FA")
    if code:
        cl.login(user, pwd, verification_code=code)
    else:
        cl.login(user, pwd)
    cl.dump_settings(SESSION)
    print("🔓 Connecté et session sauvegardée.")
    return cl

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides", type=int, default=5, help="nombre de slides (2 à 10)")
    ap.add_argument("--caption", default="Test carrousel ✅ (slides vides)")
    args = ap.parse_args()

    if not 2 <= args.slides <= 10:
        sys.exit("❌ Un carrousel accepte de 2 à 10 slides.")

    print(f"🖼️  Génération de {args.slides} slides vides...")
    files = generer_slides(args.slides)
    for f in files:
        print("   ", f)

    cl = login()
    print("📤 Publication du carrousel...")
    media = cl.album_upload(files, caption=args.caption)
    print(f"✅ Publié ! https://www.instagram.com/p/{media.code}/")
