# -*- coding: utf-8 -*-
"""
slides_copy.py — "Agent Slides" : transforme un article (JSON Agent 2) en
COPY optimisée pour un carrousel Instagram (texte court, calibré par slide)
+ la légende. Le rendu visuel reste géré par render.py (charte Fractal).

Deux fournisseurs possibles (variable IA_PROVIDER) :
  - "groq"      (défaut)  -> réutilise GROQ_API_KEY + llama-3.3-70b
  - "anthropic"           -> ANTHROPIC_API_KEY + Claude (copy plus fine)

Sortie : dict JSON consommé par render.apply_copy() + champ "caption".
"""
import os, json

# Budgets de caractères par slide (calibrés sur le template 1080x1350)
PROMPT = """Tu es Directeur Artistique éditorial de "Fractal", média de vulgarisation
financière (Gen Z / Millennials). À partir de l'analyse JSON d'un article, produis le
TEXTE d'un carrousel Instagram de 7 slides. Pas de design, juste le texte, calibré court.

CONTRAINTES STRICTES (respecte les longueurs, c'est pour un visuel) :
- hook_title : l'accroche, percutante, MAX 8 mots, sans point final.
- hook_flash : 1 phrase choc qui donne envie de glisser. MAX 140 caractères.
- contexte   : pourquoi on en arrive là. MAX 220 caractères.
- mecanique  : ce qui se passe concrètement, métaphore bienvenue. MAX 240 caractères.
- impact     : effet concret sur les actifs/valorisation. MAX 220 caractères.
- biais      : explique le piège psychologique (garde le même biais que la source). MAX 200 caractères.
- oubli      : ce que le marché sous-estime. MAX 200 caractères.
- catalyseur : le signal précis à surveiller. MAX 180 caractères.
- caption    : légende Instagram. Hook en 1re ligne, 3-5 lignes, 2-4 émojis max,
               ton direct, finit par un appel vers le lien en bio. JAMAIS de conseil
               d'achat/vente. Reformule, ne recopie pas.
- hashtags   : 10 à 14 hashtags pertinents (sans #, minuscules), finance FR/EN + thème.

Ton : clair, moderne, sans jargon inutile, neutre et éducatif.
RETOURNE STRICTEMENT ce JSON, rien d'autre :
{"hook_title","hook_flash","contexte","mecanique","impact","biais","oubli","catalyseur","caption","hashtags":[...]}"""

def _payload(article: dict) -> str:
    keep = {
        "titre": article["titre_newsletter"],
        "synthese": article["synthese_flash"],
        "contexte": article["contexte_macro_micro"],
        "mecanique": article["mecanique_de_l_evenement"],
        "impact": article["impact_financier"]["explication_impact"],
        "actifs": article["impact_financier"]["actifs_concernes"],
        "tendance": article["impact_financier"]["tendance_marche"],
        "biais": article["analyse_critique_et_biais"]["piege_psychologique"],
        "oubli": article["analyse_critique_et_biais"]["ce_que_le_marche_oublie"],
        "catalyseur": article["catalyseur_a_surveiller"],
    }
    return json.dumps(keep, ensure_ascii=False)

def _extract_json(text: str) -> dict:
    """Récupère un objet JSON même si le modèle ajoute du texte ou des ``` autour."""
    import json
    text = text.strip().replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def _via_groq(article: dict) -> dict:
    from groq import Groq
    cl = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b")
    msgs = [{"role": "system", "content": PROMPT},
            {"role": "user", "content": _payload(article)}]

    # Qwen3 = modèle de raisonnement : on coupe le "thinking" pour un JSON propre
    extra = {"reasoning_effort": "none"} if "qwen3" in model else {}

    # 1re tentative : mode JSON strict
    try:
        r = cl.chat.completions.create(
            model=model, messages=msgs, temperature=0.5,
            response_format={"type": "json_object"}, **extra,
        )
        return _extract_json(r.choices[0].message.content)
    except Exception as e:
        print(f"⚠️  JSON strict échoué ({type(e).__name__}), nouvelle tentative tolérante...")

    # 2e tentative : sans format imposé, puis extraction tolérante du JSON
    r = cl.chat.completions.create(model=model, messages=msgs, temperature=0.3, **extra)
    return _extract_json(r.choices[0].message.content)

def _via_anthropic(article: dict) -> dict:
    import anthropic
    cl = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = cl.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=1200,
        system=PROMPT + "\nRéponds uniquement avec le JSON, sans balises Markdown.",
        messages=[{"role": "user", "content": _payload(article)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text.replace("```json", "").replace("```", "").strip())

def generate_slide_copy(article: dict) -> dict:
    provider = os.environ.get("IA_PROVIDER", "groq").lower()
    copy = _via_anthropic(article) if provider == "anthropic" else _via_groq(article)

    # Assemble la légende finale (copy + disclaimer + hashtags)
    tags = " ".join("#" + t.lstrip("#") for t in copy.get("hashtags", []))
    disclaimer = "\n\n⚠️ Contenu éducatif, pas un conseil en investissement."
    copy["caption"] = f"{copy.get('caption','').strip()}{disclaimer}\n\n{tags}".strip()
    return copy

if __name__ == "__main__":
    import pathlib, sys
    data = json.loads((pathlib.Path(__file__).parent.parent / "newsletter_data.json").read_text("utf-8"))
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(json.dumps(generate_slide_copy(data["articles"][idx]), ensure_ascii=False, indent=2))
