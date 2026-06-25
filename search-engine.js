// search-engine.js — Moteur de recherche Fractal
// Indexe les articles actuels + archives, recherche full-text avec filtres

class FractalSearchEngine {
  constructor() {
    this.articles = [];
    this.index = [];
    this.loaded = false;
  }

  // Charge tous les articles (actuels + archives)
  async loadAll() {
    if (this.loaded) return this.articles;

    try {
      // 1. Articles actuels
      const currentRes = await fetch('newsletter_data.json?t=' + Date.now());
      if (currentRes.ok) {
        const currentData = await currentRes.json();
        (currentData.articles || []).forEach(art => {
          art._meta = art._meta || {};
          art._meta._origin = 'current';
          this.articles.push(art);
        });
      }

      // 2. Archives (via index.json)
      const idxRes = await fetch('archives/index.json?t=' + Date.now());
      if (idxRes.ok) {
        const idx = await idxRes.json();
        const promises = (idx.archives || []).slice(0, 30).map(async arch => {
          try {
            const r = await fetch(`archives/${arch.file}`);
            const d = await r.json();
            (d.articles || []).forEach(art => {
              art._meta = art._meta || {};
              art._meta._origin = 'archive';
              art._meta._archiveDate = arch.date;
              // Évite les doublons avec current
              if (!this.articles.find(a => (a._meta?.lien_source) === (art._meta?.lien_source))) {
                this.articles.push(art);
              }
            });
          } catch {}
        });
        await Promise.all(promises);
      }

      // 3. Construit l'index textuel
      this.articles.forEach((art, i) => {
        this.index.push({
          id: i,
          text: this._buildText(art).toLowerCase(),
          meta: art._meta || {},
          impact: art.impact_financier || {},
          radar: art.radar_fractal || {}
        });
      });

      this.loaded = true;
      return this.articles;
    } catch (err) {
      console.error('SearchEngine load error:', err);
      return [];
    }
  }

  _buildText(art) {
    const parts = [
      art.titre_newsletter,
      art.synthese_flash,
      art.contexte_macro_micro,
      art.mecanique_de_l_evenement,
      art.impact_financier?.explication_impact,
      art.analyse_critique_et_biais?.piege_psychologique,
      art.analyse_critique_et_biais?.ce_que_le_marche_oublie,
      art.catalyseur_a_surveiller,
      (art.impact_financier?.actifs_concernes || []).join(' '),
      art._meta?.source || ''
    ];
    return parts.filter(Boolean).join(' ');
  }

  // Recherche avec filtres
  search(query = '', filters = {}) {
    const q = (query || '').toLowerCase().trim();
    const tokens = q ? q.split(/\s+/).filter(t => t.length > 1) : [];

    let results = this.articles.map((art, i) => ({ art, score: 0 }));

    // Scoring textuel
    if (tokens.length > 0) {
      results = results.filter(({ art }) => {
        const text = this.index[i].text;
        return tokens.every(t => text.includes(t));
      });

      results.forEach(r => {
        const text = this.index[r.art._meta?._id || this.articles.indexOf(r.art)].text;
        let score = 0;
        const title = (r.art.titre_newsletter || '').toLowerCase();
        const synthese = (r.art.synthese_flash || '').toLowerCase();

        tokens.forEach(t => {
          if (title.includes(t)) score += 10;
          if (synthese.includes(t)) score += 5;
          // Occurrences dans le texte complet
          score += (text.match(new RegExp(t, 'g')) || []).length;
        });
        r.score = score;
      });
    }

    // Application des filtres
    if (filters.tendance) {
      results = results.filter(r => {
        const t = (r.art.impact_financier?.tendance_marche || '').toLowerCase();
        return t.includes(filters.tendance.toLowerCase());
      });
    }

    if (filters.categorie) {
      results = results.filter(r => {
        const actifs = (r.art.impact_financier?.actifs_concernes || []).join(' ').toLowerCase();
        const cat = filters.categorie.toLowerCase();
        if (cat === 'crypto') return /btc|eth|crypto|coin|blockchain/.test(actifs);
        if (cat === 'forex') return /eur|usd|gbp|jpy|forex|devise/.test(actifs);
        if (cat === 'actions') return /\b[a-z]{2,5}\b/.test(actifs) && !/btc|eth/.test(actifs);
        if (cat === 'macro') return /pib|inflation|fed|bce|emploi|chômage/.test(this.index[this.articles.indexOf(r.art)].text);
        if (cat === 'matieres') return /or|pétrole|gaz|cuivre|commodit/.test(actifs);
        return true;
      });
    }

    if (filters.source) {
      results = results.filter(r =>
        (r.art._meta?.source || '').toLowerCase().includes(filters.source.toLowerCase())
      );
    }

    if (filters.scoreMin !== undefined) {
      results = results.filter(r =>
        (r.art._meta?.score_composite || 0) >= filters.scoreMin
      );
    }

    if (filters.dateFrom) {
      const from = new Date(filters.dateFrom).getTime();
      results = results.filter(r => {
        const d = new Date(r.art._meta?.date_article || r.art._meta?._archiveDate).getTime();
        return !isNaN(d) && d >= from;
      });
    }

    if (filters.dateTo) {
      const to = new Date(filters.dateTo).getTime();
      results = results.filter(r => {
        const d = new Date(r.art._meta?.date_article || r.art._meta?._archiveDate).getTime();
        return !isNaN(d) && d <= to;
      });
    }

    if (filters.origin) {
      results = results.filter(r => r.art._meta?._origin === filters.origin);
    }

    // Tri
    const sortBy = filters.sortBy || (tokens.length > 0 ? 'relevance' : 'date');
    if (sortBy === 'relevance') {
      results.sort((a, b) => b.score - a.score);
    } else if (sortBy === 'score') {
      results.sort((a, b) =>
        (b.art._meta?.score_composite || 0) - (a.art._meta?.score_composite || 0)
      );
    } else {
      // Tri par date
      results.sort((a, b) => {
        const da = new Date(a.art._meta?.date_article || 0).getTime();
        const db = new Date(b.art._meta?.date_article || 0).getTime();
        return db - da;
      });
    }

    return results.map(r => r.art);
  }

  // Top tendances : articles avec le meilleur score composite
  getTrending(limit = 6) {
    return [...this.articles]
      .sort((a, b) => (b._meta?.score_composite || 0) - (a._meta?.score_composite || 0))
      .slice(0, limit);
  }

  // Liste des sources uniques
  getSources() {
    return [...new Set(this.articles.map(a => a._meta?.source).filter(Boolean))].sort();
  }

  // Stats globales
  getStats() {
    return {
      total: this.articles.length,
      current: this.articles.filter(a => a._meta?._origin === 'current').length,
      archives: this.articles.filter(a => a._meta?._origin === 'archive').length
    };
  }
}

// Instance singleton globale
window.FractalSearch = new FractalSearchEngine();