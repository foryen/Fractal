# -*- coding: utf-8 -*-
"""
ig_official_post.py — Publie un carrousel sur TON compte via l'API OFFICIELLE
(« Instagram API with Instagram Login », host graph.instagram.com).

Aucun mot de passe, aucune Page Facebook, aucune App Review (compte que tu gères).
L'API exige des images accessibles via URL PUBLIQUE : pour ce test on utilise des
placeholders publics, donc rien à héberger.

Prérequis (voir le setup décrit dans la conversation) :
  - Compte Instagram en Creator (ou Business)
  - App Meta avec produit « Instagram » + permission instagram_business_content_publish
  - Un token d'accès généré dans le dashboard

Variables d'environnement :
  export IG_ACCESS_TOKEN="EAAB...le_token"
  export IG_USER_ID="17841400000000000"     # facultatif : sinon récupéré via /me
  export GRAPH_VERSION="v23.0"               # facultatif

Lancement :
  python ig_official_post.py
  python ig_official_post.py --slides 6 --caption "Mon test officiel"
  # avec tes propres images publiques :
  python ig_official_post.py --urls https://.../1.jpg https://.../2.jpg
"""
import argparse, os, sys, time, requests

HOST = "https://graph.instagram.com"

class IGError(RuntimeError):
    pass

class Publisher:
    def __init__(self):
        self.token = os.environ.get("IG_ACCESS_TOKEN")
        if not self.token:
            sys.exit("❌ Définis IG_ACCESS_TOKEN (généré dans le dashboard Meta).")
        self.v = os.environ.get("GRAPH_VERSION", "v23.0")
        self.base = f"{HOST}/{self.v}"
        self.uid = os.environ.get("IG_USER_ID") or self._me()

    def _check(self, r):
        body = r.json()
        if r.status_code >= 400 or "error" in body:
            raise IGError(body.get("error", body))
        return body

    def _me(self):
        r = requests.get(f"{self.base}/me", params={"fields": "user_id,username", "access_token": self.token}, timeout=30)
        body = self._check(r)
        # selon le flux, l'id utile est user_id (Instagram Login) ou id
        uid = body.get("user_id") or body.get("id")
        print(f"👤 Compte : @{body.get('username','?')} (id {uid})")
        return uid

    def _create_child(self, image_url):
        r = requests.post(f"{self.base}/{self.uid}/media",
                          data={"image_url": image_url, "is_carousel_item": "true", "access_token": self.token},
                          timeout=60)
        return self._check(r)["id"]

    def _wait(self, container_id, tries=20, delay=3):
        for _ in range(tries):
            r = requests.get(f"{self.base}/{container_id}",
                            params={"fields": "status_code", "access_token": self.token}, timeout=30)
            code = self._check(r).get("status_code")
            if code == "FINISHED":
                return
            if code == "ERROR":
                raise IGError(f"Conteneur {container_id} en ERROR")
            time.sleep(delay)
        raise IGError(f"Timeout : {container_id} jamais FINISHED")

    def publish_carousel(self, image_urls, caption):
        if not 2 <= len(image_urls) <= 10:
            raise ValueError("Un carrousel accepte de 2 à 10 médias.")
        print(f"📦 Création de {len(image_urls)} conteneurs enfants...")
        children = []
        for url in image_urls:
            cid = self._create_child(url)
            self._wait(cid)
            children.append(cid)
            print(f"   ✓ {cid}")

        print("📦 Création du conteneur carrousel...")
        r = requests.post(f"{self.base}/{self.uid}/media",
                         data={"media_type": "CAROUSEL", "children": ",".join(children),
                               "caption": caption, "access_token": self.token}, timeout=60)
        parent = self._check(r)["id"]
        self._wait(parent)

        print("🚀 Publication...")
        r = requests.post(f"{self.base}/{self.uid}/media_publish",
                         data={"creation_id": parent, "access_token": self.token}, timeout=60)
        return self._check(r)["id"]

def placeholder_urls(n):
    """Images 'vides' publiques (zéro hébergement), aux couleurs Fractal."""
    return [f"https://placehold.co/1080x1350/09090b/34d399.png?text={i}" for i in range(1, n + 1)]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides", type=int, default=5, help="nombre de slides (2 à 10)")
    ap.add_argument("--caption", default="Test carrousel officiel ✅")
    ap.add_argument("--urls", nargs="+", help="URLs publiques d'images (sinon placeholders)")
    args = ap.parse_args()

    urls = args.urls or placeholder_urls(args.slides)
    print("🖼️  Images :")
    for u in urls:
        print("   ", u)

    media_id = Publisher().publish_carousel(urls, args.caption)
    print(f"✅ Publié ! media_id = {media_id}")
