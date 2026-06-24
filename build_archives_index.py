# -*- coding: utf-8 -*-
"""
Fractal — Générateur d'index des archives
Lit tous les fichiers newsletter_*.json du dossier archives/
et construit archives/index.json pour le site web.

Usage :
    python build_archives_index.py

À lancer après chaque exécution du pipeline principal,
ou via automate.py qui orchestre tout.
"""

import os
import json
import sys
from datetime import datetime

# ═══════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════
ARCHIVES_DIR = "archives"
INDEX_FILE = os.path.join(ARCHIVES_DIR, "index.json")
PREFIX = "newsletter_"
SUFFIX = ".json"


def build_index():
    """Scanne le dossier archives/ et génère index.json."""
    
    print("\n" + "=" * 60)
    print("  📚 FRACTAL — Génération de l'index des archives")
    print("=" * 60 + "\n")
    
    # Vérifie que le dossier existe
    if not os.path.isdir(ARCHIVES_DIR):
        print(f"❌ Dossier '{ARCHIVES_DIR}' introuvable.")
        print("   Lancez d'abord le pipeline principal pour créer des archives.")
        return False
    
    # Récupère tous les fichiers newsletter_*.json (sauf index.json)
    archive_files = [
        f for f in os.listdir(ARCHIVES_DIR)
        if f.startswith(PREFIX) and f.endswith(SUFFIX)
    ]
    
    if not archive_files:
        print(f"⚠️  Aucun fichier d'archive trouvé dans '{ARCHIVES_DIR}/'")
        # On crée quand même un index vide pour éviter l'erreur 404 côté site
        empty_index = {"archives": [], "generated_at": datetime.now().isoformat()}
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(empty_index, f, ensure_ascii=False, indent=2)
        print(f"✅ Index vide créé : {INDEX_FILE}")
        return True
    
    print(f"📂 {len(archive_files)} fichiers d'archive détectés.\n")
    
    # Parse chaque fichier
    archives_list = []
    errors = 0
    
    for filename in archive_files:
        filepath = os.path.join(ARCHIVES_DIR, filename)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Extrait la date depuis le nom du fichier (format: newsletter_YYYYMMDD_HHMMSS.json)
            try:
                date_part = filename.replace(PREFIX, "").replace(SUFFIX, "")
                dt = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                iso_date = dt.isoformat()
                readable_date = dt.strftime("%d/%m/%Y à %H:%M")
            except ValueError:
                # Fallback : utilise la date du payload si le nom est mal formé
                iso_date = data.get("derniere_mise_a_jour_raw", datetime.now().isoformat())
                readable_date = data.get("derniere_mise_a_jour", "Date inconnue")
            
            archives_list.append({
                "file": filename,
                "date": iso_date,
                "readableDate": readable_date,
                "articleCount": data.get("nb_articles", len(data.get("articles", []))),
                "size_kb": round(os.path.getsize(filepath) / 1024, 1)
            })
            
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠️  Erreur lecture {filename} : {e}")
            errors += 1
    
    # Trie par date décroissante (plus récent en premier)
    archives_list.sort(key=lambda x: x["date"], reverse=True)
    
    # Construit le payload final
    index_payload = {
        "archives": archives_list,
        "generated_at": datetime.now().isoformat(),
        "total_count": len(archives_list),
        "total_articles": sum(a["articleCount"] for a in archives_list)
    }
    
    # Écrit le fichier index.json
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_payload, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Index généré : {INDEX_FILE}")
    print(f"   • {len(archives_list)} éditions référencées")
    print(f"   • {index_payload['total_articles']} articles au total")
    if errors:
        print(f"   ⚠️  {errors} fichier(s) ignoré(s) suite à une erreur")
    print()
    
    return True


if __name__ == "__main__":
    success = build_index()
    sys.exit(0 if success else 1)