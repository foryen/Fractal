# -*- coding: utf-8 -*-
"""
Fractal Project - Pipeline Newsletter Financière
Version 6.0 - Score composite Pertinence × Fraîcheur | 15 articles | Flux vivant
@author: fayen / Fractal Project
"""

import feedparser
import sqlite3
import json
import time
import os
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from groq import Groq

# ==============================================================================
# CONFIGURATION
# ==============================================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY non définie. Configure-la dans les variables d'environnement.")

MODELE_GROQ     = "qwen/qwen3.6-27b"
FICHIER_NEWSLETTER = "newsletter_data.json"

NOMBRE_ARTICLES_SITE  = 15   # Articles affichés sur le site
TAILLE_LOT            = 25   # Articles envoyés par lot à Groq (Agent 1)
DELAI_LOTS            = 3    # Secondes entre lots Agent 1
DELAI_ARTICLES        = 1    # Secondes entre articles Agent 2

# --- Pondération du score composite (doit sommer à 1.0) ---
POIDS_PERTINENCE = 0.70   # 70 % : qualité éditoriale de l'info
POIDS_FRAICHEUR  = 0.30   # 30 % : âge de l'article (décroît avec le temps)

# --- flux persistant ---
MAX_REMPLACEMENTS_PAR_RUN = 5    # Stabilité : max 5 nouveaux articles par run
BOOST_PERSISTANCE         = 0.5  # Bonus pour les articles déjà publiés
SEUIL_MIN_REMPLACEMENT    = 0.3  # Le nouveau doit dépasser l'ancien d'au moins 0.3

# Durée de vie maximale pour le calcul de fraîcheur (en heures)
# Au-delà, la fraîcheur est 0. En dessous, elle décroît exponentiellement.
FRAICHEUR_DUREE_VIE_H = 72   # 3 jours

# Score composite minimum pour qu'un article remplace un article existant
SEUIL_REMPLACEMENT = 0.0  # 0 = toujours réévaluer (le classement fait le tri)

client = Groq(api_key=GROQ_API_KEY)

# ==============================================================================
# SOURCES RSS
# ==============================================================================

flux_rss_sources = {
    "Le Monde - Bourse":             "https://www.lemonde.fr/bourse/rss_full.xml",
    "Le Monde - Devises":            "https://www.lemonde.fr/devises/rss_full.xml",
    "Le Figaro - Bourse":            "https://www.lefigaro.fr/rss/figaro_bourse.xml",
    "Les Échos - Marchés":           "https://feeds.feedburner.com/lesechos/4MR4suAcqTl",
    "Les Échos - Conseils":          "https://services.lesechos.fr/rss/investir-conseils-boursiers.xml",
    "Les Échos - Valeurs":           "https://feeds.feedburner.com/lesechos/BrFLB6ZLde7",
    "France Info - Bourse":          "https://www.franceinfo.fr/economie/bourse.rss",
    "France Info - Marchés":         "https://www.franceinfo.fr/economie/bourse/marches.rss",
    "France Info - Croissance":      "https://www.franceinfo.fr/economie/croissance.rss",
    "France 24 - Bourses":           "https://www.france24.com/fr/tag/bourses/rss",
    "Libération - Marchés":          "https://www.liberation.fr/arc/outboundfeeds/rss/tags_slug/marches-financiers/?outputType=xml",
    "Euronews - Marchés":            "https://fr.euronews.com/rss?level=theme&name=markets",
    "L'Opinion - Bourse":            "https://www.lopinion.fr/theme/bourse.rss",
    "La Presse - Marchés":           "https://www.lapresse.ca/affaires/marches/rss",
    "AGEFI - Marchés Actions":       "https://www.agefi.fr/theme/marches-actions.rss",
    "AGEFI - ETF":                   "https://www.agefi.fr/theme/etf.rss",
    "AGEFI - Matières Premières":    "https://www.agefi.fr/theme/marches-de-matieres-premieres.rss",
    "AGEFI - Obligations":           "https://www.agefi.fr/theme/marches-obligataires.rss",
    "ABC Bourse - Actu":             "https://www.abcbourse.com/rss/displaynewsrss",
    "ABC Bourse - Analyses":         "https://www.abcbourse.com/rss/lastanalysisrss",
    "Bourse Direct - Analyses":      "https://www.boursedirect.fr/fr/actualites/flux/analyses/rss",
    "Café de la Bourse":             "https://www.cafedelabourse.com/feed",
    "Café de la Bourse - Crypto":    "https://www.cafedelabourse.com/crypto/feed",
    "Investing - Vue Ensemble":      "https://fr.investing.com/rss/market_overview.rss",
    "Investing - Actions":           "https://fr.investing.com/rss/news_25.rss",
    "Coin Journal - Marchés":        "https://coinjournal.net/fr/actualites/category/marches/feed/",
    "Coin Tribune - Trading":        "https://www.cointribune.com/tag/trading/feed/",
    "Broker Forex":                  "https://www.broker-forex.fr/rss/forex.xml",
    "AMF - Toutes Actualités":       "https://www.amf-france.org/fr/flux-rss/display/21",
    "TradingSat - Bourse":           "https://www.tradingsat.com/rssbourse.xml",
    # --- Spécialisés finance/bourse ---
"AGEFI - Marchés Actions":      "https://www.agefi.fr/theme/marches-actions.rss",
"AGEFI - ETF":                  "https://www.agefi.fr/theme/etf.rss",
"AGEFI - Matières Premières":   "https://www.agefi.fr/theme/marches-de-matieres-premieres.rss",
"AGEFI - Obligations":          "https://www.agefi.fr/theme/marches-obligataires.rss",
"AGEFI - Économie Marchés":     "https://www.agefi.fr/news/economie-marches.rss",
"AGEFI - Indices":              "https://www.agefi.fr/theme/indices.rss",
"AGEFI - Introductions Bourse": "https://www.agefi.fr/theme/introduction-en-bourse.rss",
"AGEFI - Hedge Funds":          "https://www.agefi.fr/theme/hedge-funds.rss",
"ABC Bourse - Actu":            "https://www.abcbourse.com/rss/displaynewsrss",
"ABC Bourse - Analyses":        "https://www.abcbourse.com/rss/lastanalysisrss",
"ABC Bourse - Chroniques":      "https://www.abcbourse.com/rss/chroniquesrss",
"Bourse Direct - Analyses":     "https://www.boursedirect.fr/fr/actualites/flux/analyses/rss",
"Café de la Bourse":            "https://www.cafedelabourse.com/feed",
"Café de la Bourse - Crypto":   "https://www.cafedelabourse.com/crypto/feed",
"Café de la Bourse - Trading":  "https://www.cafedelabourse.com/trading/feed",
"Investing - Vue Ensemble":     "https://fr.investing.com/rss/market_overview.rss",
"Investing - Actions":          "https://fr.investing.com/rss/news_25.rss",
"Investing - Marchés":          "https://fr.investing.com/rss/stock.rss",
"Investing - Matières Premières":"https://fr.investing.com/rss/commodities.rss",
"Investing - Obligations":      "https://fr.investing.com/rss/bonds.rss",
"EasyBourse":                   "https://www.easybourse.com/flux/media.rss",
"France Bourse - À la Une":     "https://www.francebourse.com/JOUR/rss.xml",
"France Bourse - Finance":      "https://www.francebourse.com/BOURSE/rss.xml",
"Idéal Investisseur":           "https://www.ideal-investisseur.fr/RSS.xml",
"AllNews - Bourse":             "https://www.allnews.ch/taxonomy/term/5/feed",
"CFnews - Bourse":              "https://www.cfnews.net/rss/feed/bourse",
"CFnews - Marché Général":      "https://www.cfnews.net/rss/feed/marche_general",
"ActusNewsWire":                "https://www.actusnews.com/fr/rss",
"Novethic - Tendances":         "https://www.novethic.fr/category/finance-durable/tendances-de-marche/feed",
"Décideurs - Finance":          "https://www.decideurs-magazine.com/finance.feed?type=rss",

# --- Crypto ---
"Coin Journal - Marchés":       "https://coinjournal.net/fr/actualites/category/marches/feed/",
"Coin Tribune - Trading":       "https://www.cointribune.com/tag/trading/feed/",
"Coin Tribune - Exchange":      "https://www.cointribune.com/actu/actu-exchange/feed/",

# --- Forex ---
"Broker Forex":                 "https://www.broker-forex.fr/rss/forex.xml",

# --- Google Actualités (agrégateurs) ---
"Google Actu - Bourse":         "https://news.google.com/rss/search?tbm=nws&q=bourse&oq=bourse&scoring=n&hl=fr&gl=FR&ceid=FR:fr",
"Google Actu - NYSE":           "https://news.google.com/rss/search?tbm=nws&q=Bourse%20de%20New%20York&scoring=n&hl=fr&gl=FR&ceid=FR:fr",
"Google Actu - Paris":          "https://news.google.com/rss/search?tbm=nws&q=Bourse%20de%20Paris&scoring=n&hl=fr&gl=FR&ceid=FR:fr",

# --- Réglementaire (AMF) ---
"AMF - Toutes Actualités":      "https://www.amf-france.org/fr/flux-rss/display/21",
"AMF - Communiqués de Presse":  "https://www.amf-france.org/fr/flux-rss/display/23",
"AMF - Réglementation":         "https://www.amf-france.org/fr/flux-rss/display/31",

# --- BFM / TradingSat ---
"TradingSat - Bourse":          "https://www.tradingsat.com/rssbourse.xml",
}

# ==============================================================================
# BASE DE DONNÉES — connexion unique par session
# ==============================================================================

def ouvrir_connexion():
    conn = sqlite3.connect("fractal_news.db", timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # Accès par nom de colonne
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def initialiser_base_donnees(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            titre            TEXT,
            lien             TEXT UNIQUE,
            lien_source      TEXT,
            date_article     TEXT,
            date_collecte    TEXT,
            source           TEXT,
            est_pertinent    INTEGER DEFAULT 0,
            score_pertinence REAL    DEFAULT 0.0,
            score_composite  REAL    DEFAULT 0.0,
            justification    TEXT,
            contenu_json     TEXT    -- Analyse Agent 2 sérialisée
        );

        CREATE TABLE IF NOT EXISTS newsletter_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date_export  TEXT,
            nb_articles  INTEGER
        );
    """)
    conn.commit()

def est_deja_enregistre(conn, lien):
    return conn.execute("SELECT 1 FROM articles WHERE lien = ?", (lien,)).fetchone() is not None

def enregistrer_articles_batch(conn, rows):
    conn.executemany("""
        INSERT OR IGNORE INTO articles
            (titre, lien, lien_source, date_article, date_collecte, source,
             est_pertinent, score_pertinence, score_composite, justification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()

def sauvegarder_contenu_agent2(conn, lien, contenu_json):
    conn.execute(
        "UPDATE articles SET contenu_json = ? WHERE lien = ?",
        (json.dumps(contenu_json, ensure_ascii=False), lien)
    )
    conn.commit()

# ==============================================================================
# CALCUL DU SCORE COMPOSITE
# ==============================================================================

def calculer_fraicheur(date_str):
    """
    Retourne un score de fraîcheur entre 0.0 et 1.0.
    Décroissance exponentielle sur FRAICHEUR_DUREE_VIE_H heures.
    Article de moins d'1h → ~0.99 | 24h → ~0.70 | 72h → ~0.00
    """
    try:
        dt = parsedate_to_datetime(date_str)
        # Normalise en UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_heures = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        age_heures = max(0, age_heures)
        # Décroissance exponentielle : e^(-lambda * age)
        # lambda calibré pour que fraîcheur(DUREE_VIE_H) ≈ 0.05
        lam = -math.log(0.05) / FRAICHEUR_DUREE_VIE_H
        return round(math.exp(-lam * age_heures), 4)
    except Exception:
        return 0.5  # Valeur neutre si date non parseable

def calculer_score_composite(score_pertinence_10, fraicheur):
    """
    score_pertinence_10 : 0.0 → 10.0 (Groq)
    fraicheur           : 0.0 → 1.0
    Retourne un score composite 0.0 → 10.0 (2 décimales)
    """
    pertinence_norm = score_pertinence_10 / 10.0
    composite = (POIDS_PERTINENCE * pertinence_norm) + (POIDS_FRAICHEUR * fraicheur)
    return round(composite * 10, 2)   # Ramené sur 10 pour lisibilité

# ==============================================================================
# AGENT 1 : FILTRE SÉLECTIF — prompt "caviar" (score à la décimale)
# ==============================================================================

def analyser_lot_articles_avec_groq(liste_articles):
    if not liste_articles:
        return {}

    prompt_systeme = """Tu es le directeur éditorial de Fractal, un média financier d'élite.
Ta mission : identifier uniquement les nouvelles qui ont un impact RÉEL et MESURABLE sur les marchés financiers.

CRITÈRES DE SÉLECTION STRICTS — ne retiens que les articles qui :
✅ Annoncent une décision concrète (banque centrale, gouvernement, entreprise cotée)
✅ Révèlent un chiffre macro important (inflation, PIB, emploi, bénéfices)
✅ Signalent un mouvement de prix ou de volume significatif (>2% sur un actif majeur)
✅ Décrivent un événement géopolitique avec impact direct sur l'énergie, les devises ou les indices
✅ Annoncent une fusion, acquisition, faillite, introduction en bourse ou émission obligataire

REJETTE systématiquement :
❌ Guides pédagogiques génériques ("comment investir en 2024")
❌ Opinions sans données concrètes
❌ Répétitions d'une info déjà connue (reformulation de la veille)
❌ Articles promotionnels ou publicitaires
❌ Titres vagues sans contenu actionnable

NOTATION : Sois précis à la décimale. Utilise toute l'échelle :
- 9.0 à 10.0 : Impact systémique majeur (ex: décision Fed, crise bancaire, guerre)
- 7.0 à 8.9  : Impact significatif sur un secteur ou une classe d'actif
- 5.0 à 6.9  : Information utile mais impact limité ou incertain
- 3.0 à 4.9  : Anecdotique, impact très marginal
- 0.0 à 2.9  : Bruit éditorial, aucun intérêt marché

Réponds STRICTEMENT en JSON :
{
  "evaluations": [
    {
      "index": <int>,
      "score": <float à 1 décimale, entre 0.0 et 10.0>,
      "pertinent": <true si score >= 6.0, sinon false>,
      "raison": "<1 phrase factuelle expliquant le score — cite l'actif ou le chiffre concerné si possible>"
    }
  ]
}"""

    lignes = [
        f"Index: {idx}\nSource: {a['source']}\nTitre: {a['titre']}\n---"
        for idx, a in enumerate(liste_articles)
    ]

    try:
        response = client.chat.completions.create(
            model=MODELE_GROQ,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user",   "content": "\n".join(lignes)}
            ],
            temperature=0.05,   # Quasi-déterministe pour la notation
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return {
            int(e["index"]): {
                "score":     round(float(e["score"]), 1),
                "pertinent": bool(e["pertinent"]),
                "raison":    str(e["raison"])
            }
            for e in data.get("evaluations", [])
        }
    except Exception as e:
        print(f"  ⚠️  Erreur Agent 1 (Groq) : {e}")
        return {}

# ==============================================================================
# COLLECTE + FILTRAGE + SCORING COMPOSITE
# ==============================================================================

def recuperer_et_filtrer_actualites(conn, sources):
    print("\n" + "="*60)
    print("  [AGENT 1] COLLECTE & FILTRAGE SÉLECTIF")
    print("="*60 + "\n")

    initialiser_base_donnees(conn)
    tous_les_nouveaux = []

    print("🌐 Scan des flux RSS...")
    for nom_source, url_flux in sources.items():
        try:
            flux = feedparser.parse(url_flux)
            for article in flux.entries[:3]:
                lien = article.get("link", "")
                if not lien or est_deja_enregistre(conn, lien):
                    continue
                tous_les_nouveaux.append({
                    "titre":       str(article.get("title", "Sans titre")),
                    "lien":        lien,
                    "lien_source": lien,   # Lien original conservé
                    "date":        article.get("published", article.get("updated", "")),
                    "source":      nom_source
                })
        except Exception:
            continue

    total = len(tous_les_nouveaux)
    print(f"📊 {total} nouveaux articles découverts.\n")
    if total == 0:
        return []

    # --- Scoring par lots ---
    resultats = {}
    for i in range(0, total, TAILLE_LOT):
        sous_lot = tous_les_nouveaux[i:i + TAILLE_LOT]
        print(f"   → Lot {i // TAILLE_LOT + 1} ({len(sous_lot)} articles)...")
        analyses = analyser_lot_articles_avec_groq(sous_lot)
        for local_idx, ev in analyses.items():
            resultats[i + local_idx] = ev
        if i + TAILLE_LOT < total:
            time.sleep(DELAI_LOTS)

    # --- Calcul du score composite et insertion en base ---
    rows = []
    articles_pertinents = []

    for idx, art in enumerate(tous_les_nouveaux):
        ev        = resultats.get(idx, {"score": 0.0, "pertinent": False, "raison": "Non évalué"})
        fraicheur = calculer_fraicheur(art["date"])
        composite = calculer_score_composite(ev["score"], fraicheur)
        pertinent = ev["pertinent"]

        rows.append((
            art["titre"], art["lien"], art["lien_source"],
            art["date"], datetime.now().isoformat(), art["source"],
            1 if pertinent else 0, ev["score"], composite, ev["raison"]
        ))

        if pertinent:
            articles_pertinents.append({
                **art,
                "score_pertinence": ev["score"],
                "score_composite":  composite,
                "fraicheur":        fraicheur,
                "raison":           ev["raison"]
            })

    enregistrer_articles_batch(conn, rows)

    print(f"\n✅ {len(articles_pertinents)} articles pertinents retenus (sur {total} analysés).")
    return articles_pertinents

# ==============================================================================
# SÉLECTION DU MEILLEUR FLUX VIVANT (15 articles)
# ==============================================================================
def lire_flux_actuel():
    """
    Lit le fichier newsletter_data.json actuel pour connaître
    les articles déjà publiés sur le site (le "top 15 en ligne").
    Retourne un dict {lien: article_data} pour comparaison rapide.
    """
    if not os.path.isfile(FICHIER_NEWSLETTER):
        return {}
    
    try:
        with open(FICHIER_NEWSLETTER, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        flux = {}
        for art in data.get("articles", []):
            lien = art.get("_meta", {}).get("lien_source") or art.get("_meta", {}).get("lien")
            if lien:
                flux[lien] = art
        return flux
    except Exception as e:
        print(f"  ⚠️  Impossible de lire le flux actuel : {e}")
        return {}
    
def selectionner_flux_vivant(conn, nouveaux_articles, n=NOMBRE_ARTICLES_SITE):
    """
    NOUVELLE LOGIQUE — Flux persistant avec remplacement conditionnel
    
    Stratégie :
    1. On lit le flux actuel (les 15 articles en ligne sur le site)
    2. On récupère aussi les articles de la base avec contenu_json
    3. Pour les articles DÉJÀ PUBLIÉS : on applique un boost de persistance
       (ils gardent leur place sauf si un nouveau les dépasse largement)
    4. Pour les NOUVEAUX articles : on les compare au plus faible du top actuel
    5. Remplacements limités à MAX_REMPLACEMENTS_PAR_RUN pour stabilité
    """
    print("\n" + "=" * 60)
    print("  📊 SÉLECTION DU FLUX VIVANT (mode persistant)")
    print("=" * 60 + "\n")
    
    # ── ÉTAPE 1 : Lire le flux actuellement en ligne ──
    flux_actuel_dict = lire_flux_actuel()
    print(f"📄 Flux actuel en ligne : {len(flux_actuel_dict)} articles")
    
    # ── ÉTAPE 2 : Récupérer TOUS les articles rédigés de la base ──
    rows = conn.execute("""
        SELECT titre, lien, lien_source, date_article, source,
               score_pertinence, contenu_json
        FROM articles
        WHERE contenu_json IS NOT NULL
        ORDER BY score_pertinence DESC
        LIMIT 200
    """).fetchall()
    
    pool_articles = []
    for row in rows:
        fraicheur = calculer_fraicheur(row["date_article"])
        composite_base = calculer_score_composite(row["score_pertinence"], fraicheur)
        
        # Boost de persistance si l'article est déjà publié
        est_publie = row["lien"] in flux_actuel_dict or (row["lien_source"] or row["lien"]) in flux_actuel_dict
        boost = BOOST_PERSISTANCE if est_publie else 0.0
        composite_final = min(10.0, composite_base + boost)
        
        pool_articles.append({
            "titre":            row["titre"],
            "lien":             row["lien"],
            "lien_source":      row["lien_source"] or row["lien"],
            "date":             row["date_article"],
            "source":           row["source"],
            "score_pertinence": row["score_pertinence"],
            "score_composite":  round(composite_final, 2),
            "composite_base":   round(composite_base, 2),
            "contenu_json":     json.loads(row["contenu_json"]),
            "est_nouveau":      False,
            "est_publie":       est_publie,
            "boost":            boost
        })
    
    print(f"🗄️  Pool base de données : {len(pool_articles)} articles rédigés")
    print(f"   dont {sum(1 for a in pool_articles if a['est_publie'])} déjà publiés (boost +{BOOST_PERSISTANCE})")
    
    # ── ÉTAPE 3 : Identifier le "seuil d'entrée" ──
    # Tri du pool par score composite décroissant
    pool_tries = sorted(pool_articles, key=lambda x: x["score_composite"], reverse=True)
    
    # Le top N actuel forme notre "référence"
    top_actuel = pool_tries[:n]
    score_plus_faible_top = top_actuel[-1]["score_composite"] if top_actuel else 0.0
    
    print(f"\n🏆 Top {n} actuel — score du plus faible : {score_plus_faible_top:.2f}")
    print(f"   Seuil d'entrée pour un nouveau : {score_plus_faible_top + SEUIL_MIN_REMPLACEMENT:.2f} minimum")
    
    # ── ÉTAPE 4 : Évaluer les nouveaux articles ──
    nouveaux_candidats = []
    for a in nouveaux_articles:
        a["est_nouveau"] = True
        a["est_publie"] = False
        a["boost"] = 0.0
        a["composite_base"] = a["score_composite"]
        nouveaux_candidats.append(a)
    
    # Trier les nouveaux par score composite décroissant
    nouveaux_candidats = sorted(nouveaux_candidats, key=lambda x: x["score_composite"], reverse=True)
    
    # ── ÉTAPE 5 : Remplacements conditionnels ──
    remplacements = []
    flux_final = list(top_actuel)  # On part du top actuel
    nb_remplacements = 0
    
    for nouv in nouveaux_candidats:
        if nb_remplacements >= MAX_REMPLACEMENTS_PAR_RUN:
            print(f"\n Limite de {MAX_REMPLACEMENTS_PAR_RUN} remplacements atteinte")
            break
        
        # Trouver le plus faible du flux actuel
        flux_tries = sorted(flux_final, key=lambda x: x["score_composite"])
        plus_faible = flux_tries[0]
        
        # Condition de remplacement
        seuil_min = plus_faible["score_composite"] + SEUIL_MIN_REMPLACEMENT
        if nouv["score_composite"] >= seuil_min:
            # Remplacer
            flux_final.remove(plus_faible)
            flux_final.append(nouv)
            
            remplacements.append({
                "entrant": nouv,
                "sortant": plus_faible
            })
            nb_remplacements += 1
            
            print(f"\n🔄 REMPLACEMENT #{nb_remplacements}")
            print(f"   ➕ ENTRE : [{nouv['score_composite']:.2f}] {nouv['titre'][:55]}")
            print(f"   ➖ SORT  : [{plus_faible['score_composite']:.2f}] {plus_faible['titre'][:55]}")
        else:
            # Premier nouveau qui n'entre pas → on arrête (les suivants seront pires)
            print(f"\n Arrêt : {nouv['titre'][:50]}... ({nouv['score_composite']:.2f}) < seuil ({seuil_min:.2f})")
            break
    
    # ── ÉTAPE 6 : Tri final et dédoublonnage ──
    flux_final = sorted(flux_final, key=lambda x: x["score_composite"], reverse=True)
    
    # Dédoublonnage par lien
    vus = set()
    flux_dedup = []
    for a in flux_final:
        if a["lien"] not in vus:
            vus.add(a["lien"])
            flux_dedup.append(a)
        if len(flux_dedup) >= n:
            break
    
    # Articles à rédiger (nouveaux qui sont entrés dans le top)
    a_rediger = [a for a in flux_dedup if a.get("contenu_json") is None]
    
    # ── Résumé final ──
    print("\n" + "=" * 60)
    print(f"   RÉSUMÉ DE LA SESSION")
    print("=" * 60)
    print(f"  • Nouveaux articles analysés : {len(nouveaux_candidats)}")
    print(f"  • Remplacements effectués    : {nb_remplacements} / {MAX_REMPLACEMENTS_PAR_RUN} max")
    print(f"  • Articles à rédiger (Agent2): {len(a_rediger)}")
    print(f"  • Flux final                 : {len(flux_dedup)} articles")
    print("=" * 60 + "\n")
    
    if nb_remplacements == 0:
        print("✨ Aucun remplacement : le flux actuel reste stable.\n")
    
    return flux_dedup, a_rediger

# ==============================================================================
# AGENT 2 : RÉDACTEUR EN CHEF
# ==============================================================================

def analyser_article_pour_newsletter(article):
    prompt_systeme = """Tu es le Rédacteur en Chef et Analyste Financier Senior de "Fractal", un média de vulgarisation financière destiné aux jeunes investisseurs (Gen Z / Millennials).

TA MISSION : Transformer une dépêche brute en analyse claire, neutre, pointue mais accessible.

RÈGLES IMPÉRATIVES :
1. Précision : cite des données concrètes (taux, %, noms d'actifs) si elles sont dans la source.
2. Perspective : distingue toujours Micro (entreprise) de Macro (économie globale).
3. Anti-Biais : identifie le comportement irrationnel que cette news pourrait déclencher.
4. Objectivité absolue : JAMAIS de conseil d'achat ou de vente.
5. Ton : direct, moderne, sans jargon inutile — comme un ami analyste qui t'explique au café.

RETOURNE STRICTEMENT un objet JSON valide, sans texte autour :
{
  "titre_newsletter": "<Titre accrocheur et précis, max 10 mots>",
  "synthese_flash": "<L'essentiel en UNE phrase percutante — commence par le fait, pas le contexte>",
  "contexte_macro_micro": "<2 phrases : pourquoi on en arrive là ? Quel contexte sous-jacent ?>",
  "mecanique_de_l_evenement": "<3 phrases : ce qui se passe concrètement, avec métaphores si utiles>",
  "impact_financier": {
    "actifs_concernes": ["<Ticker ou nom d'actif 1>", "<Ticker ou nom d'actif 2>"],
    "tendance_marche": "<Haussière | Baissière | Neutre | Forte Incertitude>",
    "explication_impact": "<2 phrases : effet concret sur l'offre, la demande ou la valorisation>"
  },
  "analyse_critique_et_biais": {
    "piege_psychologique": "<Choisis UN SEUL biais cognitif précis dans cette liste exclusive que tu developperas en 2 lignes. INTERDICTION FORMELLE d'utiliser le mot FOMO ou 'Peur de manquer'. Liste : Aversion à la perte, Biais d'ancrage, Biais de confirmation, Effet de halo, Biais de disponibilité, Excès de confiance, Biais de représentativité, Biais du survivant, Effet de levier émotionnel, Biais de normalité, Illusion de contrôle, Aversion à l'ambiguïté, Biais de récence.>",
    "ce_que_le_marche_oublie": "<La nuance ou le risque caché que la majorité sous-estime>"
  },
  "radar_fractal": {
    "volatilite_attendue": <entier 1 à 5>,
    "risque_systemique": <entier 1 à 5>,
    "fiabilite_information": <entier 1 à 5>,
    "horizon_impact": "<Intraday | Court terme (semaines) | Moyen terme (mois) | Long terme (années)>"
  },
  "catalyseur_a_surveiller": "<L'événement ou métrique précis qui confirmera ou invalidera cette analyse>",
  "disclaimer": "L'équipe Fractal fournit cette analyse à des fins strictement éducatives. Ceci ne constitue en aucun cas un conseil en investissement. Faites vos propres recherches."
}"""

    try:
        response = client.chat.completions.create(
            model=MODELE_GROQ,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user",   "content":
                    f"Titre : {article['titre']}\n"
                    f"Source : {article['source']}\n"
                    f"Lien original : {article.get('lien_source', article['lien'])}\n"
                    f"Raison de sélection : {article.get('raison', '')}\n"
                    f"Score pertinence : {article.get('score_pertinence', '')}/10\n"
                    f"Score composite (pertinence×fraîcheur) : {article.get('score_composite', '')}/10"
                }
            ],
            temperature=0.25,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"  ⚠️  Erreur Agent 2 (Groq) : {e}")
        return None

def rediger_nouveaux_articles(conn, articles_a_rediger):
    if not articles_a_rediger:
        print("  Aucun nouvel article à rédiger.\n")
        return

    print(f"\n{'='*60}")
    print(f"  [AGENT 2] RÉDACTION — {len(articles_a_rediger)} nouveaux articles")
    print(f"{'='*60}\n")

    for i, article in enumerate(articles_a_rediger, 1):
        print(f"  ✍️  #{i} : {article['titre'][:65]}...")
        contenu = analyser_article_pour_newsletter(article)
        if contenu:
            article["contenu_json"] = contenu
            sauvegarder_contenu_agent2(conn, article["lien"], contenu)
            print(f"  ✅ Rédigé et sauvegardé.\n")
        else:
            print(f"  ❌ Échec rédaction #{i}.\n")
        time.sleep(DELAI_ARTICLES)

# ==============================================================================
# EXPORT JSON POUR LE SITE
# ==============================================================================

def exporter_newsletter(conn, flux_final):
    """
    Construit le payload JSON lu par index.html.
    Chaque article contient : contenu Agent 2 + métadonnées scores + lien source original.
    """
    articles_export = []

    for art in flux_final:
        contenu = art.get("contenu_json")
        if not contenu:
            continue   # Article sans rédaction Agent 2, on passe

        # Enrichit le contenu avec les métadonnées de classement
        contenu["_meta"] = {
            "source":           art["source"],
            "lien_source":      art.get("lien_source", art["lien"]),
            "date_article":     art.get("date", ""),
            "score_pertinence": art.get("score_pertinence", 0),
            "score_composite":  art.get("score_composite", 0),
            "est_nouveau":      art.get("est_nouveau", False)
        }
        articles_export.append(contenu)

    timestamp = datetime.now().strftime("%d/%m/%Y à %H:%M")
    payload = {
        "derniere_mise_a_jour": timestamp,
        "nb_articles":          len(articles_export),
        "articles":             articles_export
    }

    # Fichier principal du site
    with open(FICHIER_NEWSLETTER, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ {FICHIER_NEWSLETTER} mis à jour — {len(articles_export)} articles.")

    # Archive horodatée
    os.makedirs("archives", exist_ok=True)
    ts_fichier = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"archives/newsletter_{ts_fichier}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Log en base
    conn.execute(
        "INSERT INTO newsletter_log (date_export, nb_articles) VALUES (?, ?)",
        (datetime.now().isoformat(), len(articles_export))
    )
    conn.commit()

# ==============================================================================
# PIPELINE PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    print("\n🚀 Fractal Pipeline v6.0 — Flux vivant 15 articles\n")
    conn = ouvrir_connexion()

    try:
        # --- Phase 1 : Collecte + filtrage sélectif ---
        nouveaux_pertinents = recuperer_et_filtrer_actualites(conn, flux_rss_sources)

        # --- Phase 2 : Construction du flux vivant ---
        flux_final, a_rediger = selectionner_flux_vivant(conn, nouveaux_pertinents, n=NOMBRE_ARTICLES_SITE)

        # Affichage du classement complet
        print(f"{'='*60}")
        print(f"  🏆 CLASSEMENT FLUX VIVANT ({len(flux_final)} articles)")
        print(f"{'='*60}")
        for i, a in enumerate(flux_final, 1):
            nouveau_tag = " 🆕" if a.get("est_nouveau") else ""
            print(f"  #{i:02d} [{a['score_composite']:05.2f}/10] "
                  f"[P:{a.get('score_pertinence',0):.1f}] "
                  f"{a['titre'][:55]}{nouveau_tag}")
        print()

        # --- Phase 3 : Rédaction des nouveaux articles ---
        rediger_nouveaux_articles(conn, a_rediger)

        # Recharge les contenu_json des articles existants depuis la base
        for art in flux_final:
            if art.get("contenu_json") is None:
                row = conn.execute(
                    "SELECT contenu_json FROM articles WHERE lien = ?", (art["lien"],)
                ).fetchone()
                if row and row["contenu_json"]:
                    art["contenu_json"] = json.loads(row["contenu_json"])

        # --- Phase 4 : Export JSON pour le site ---
        exporter_newsletter(conn, flux_final)

        print(f"\n{'='*60}")
        print(f"  🎉 Pipeline terminé !")
        print(f"  📄 {FICHIER_NEWSLETTER} prêt pour le site.")
        print(f"{'='*60}\n")

    finally:
        conn.close()
        print("🔒 Connexion base fermée.")
