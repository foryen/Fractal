# -*- coding: utf-8 -*-
"""render.py — Slides PNG 1080x1350 pour carrousel Instagram (charte Fractal)."""
import argparse, json, os, pathlib, re
from jinja2 import Environment, FileSystemLoader, ChainableUndefined
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent
TREND_MAP = {
    "Haussière": "hausse", "Baissière": "baisse",
    "Neutre": "neutre", "Forte Incertitude": "incertitude",
}
HIGH, MID, LOW = ("high", "#34d399"), ("mid", "#fbbf24"), ("low", "#f87171")

def level_for(value: int, invert: bool = False) -> tuple[str, str]:
    if value == 3:
        return MID
    good = value <= 2
    if invert:
        good = not good
    return HIGH if good else LOW

def build_radar(rf: dict) -> list[dict]:
    rows = [
        ("Volatilité attendue", rf.get("volatilite_attendue", 0), False),
        ("Risque systémique",   rf.get("risque_systemique", 0),   False),
        ("Fiabilité info",      rf.get("fiabilite_information", 0), True),
    ]
    out = []
    for name, v, invert in rows:
        lvl, col = level_for(int(v), invert)
        out.append({"name": name, "value": int(v), "level": lvl, "color": col})
    return out

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "post"

def apply_copy(article: dict, copy: dict | None) -> dict:
    if not copy:
        return article
    a = json.loads(json.dumps(article))
    a["titre_newsletter"] = copy.get("hook_title", a["titre_newsletter"])
    a["synthese_flash"] = copy.get("hook_flash", a["synthese_flash"])
    a["contexte_macro_micro"] = copy.get("contexte", a["contexte_macro_micro"])
    a["mecanique_de_l_evenement"] = copy.get("mecanique", a["mecanique_de_l_evenement"])
    a["impact_financier"]["explication_impact"] = copy.get("impact", a["impact_financier"]["explication_impact"])
    a["analyse_critique_et_biais"]["piege_psychologique"] = copy.get("biais", a["analyse_critique_et_biais"]["piege_psychologique"])
    a["analyse_critique_et_biais"]["ce_que_le_marche_oublie"] = copy.get("oubli", a["analyse_critique_et_biais"]["ce_que_le_marche_oublie"])
    a["catalyseur_a_surveiller"] = copy.get("catalyseur", a["catalyseur_a_surveiller"])
    return a

def render_article(article: dict, out_dir: pathlib.Path, copy: dict | None = None) -> list[pathlib.Path]:
    article = apply_copy(article, copy)
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")), undefined=ChainableUndefined)
    html = env.get_template("carousel.html.j2").render(
        a=article,
        trend_class=TREND_MAP.get(article["impact_financier"]["tendance_marche"], "neutre"),
        radar=build_radar(article["radar_fractal"]),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(article["titre_newsletter"])
    paths = []
    with sync_playwright() as p:
        launch_kwargs = {"args": ["--no-sandbox", "--force-color-profile=srgb",
                                  "--disable-dev-shm-usage", "--disable-gpu"]}
        _chromium = os.environ.get("CHROMIUM_PATH")
        if _chromium:
            launch_kwargs["executable_path"] = _chromium
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        slides = page.query_selector_all(".slide")
        for i, slide in enumerate(slides):
            fp = out_dir / f"{slug}_{i:02d}.png"
            slide.screenshot(path=str(fp))
            paths.append(fp)
        browser.close()
    return paths

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT.parent / "newsletter_data.json"))
    ap.add_argument("--article", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.data).read_text(encoding="utf-8"))
    files = render_article(data["articles"][args.article], pathlib.Path(args.out))
    print(f"✅ {len(files)} slides générées")
    for f in files:
        print("   ", f)
