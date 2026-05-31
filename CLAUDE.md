# Projet : Personal CFO Alimentaire — Contexte Claude Code

## Vision produit

Application mobile/web permettant à un utilisateur de **scanner ses tickets de caisse** (photo ou email dématérialisé) pour obtenir une **analyse intelligente de ses dépenses alimentaires** : catégorisation fine par produit, suivi mensuel, benchmarks, et recommandations pour économiser.

Le différenciateur vs Bankin'/Joko : ils voient "Carrefour 87,30€". Nous, on voit "3 tablettes Chabrior, 2 packs Pom'Potes, 1 Président Emmental...". C'est de la data au niveau produit, pas au niveau enseigne.

Le modèle économique cible : freemium B2C (5-8€/mois pour analyses avancées) + data panel anonymisée vendue aux marques CPG à terme.

---

## État du MVP (ce qui existe)

### Script Python fonctionnel : `match_tickets.py`

Pipeline de matching ticket → Open Food Facts testé sur 62 lignes réelles (tickets Lidl + Intermarché Marseille).

Tu dois lire dans la doc https://openfoodfacts.github.io/openfoodfacts-server/api/

Pour accéder à la documentation via Context7 (pas de blocage antibot, 228 snippets) : utilise l'ID `/openfoodfacts/openfoodfacts-server` avec le skill context7-mcp.

**Ce que fait le script :**
1. Prend des lignes de ticket structurées `{libelle, qte, prix}`
2. Expande les abréviations tronquées (`PAQ.BCL POM.POIR.SSA` → `Paquito Boucles Pomme Poire sans sucre ajouté`)
3. Détecte la marque MDD probable selon l'enseigne
4. Appelle l'API Open Food Facts en cascade (avec marque → sans marque → libellé brut)
5. Cache les résultats localement dans `off_cache.json`
6. Produit un `results.json` avec les candidats par ligne et un bilan en console

**Commande :**
```bash
pip install requests
python match_tickets.py          # run complet
python match_tickets.py --test   # test offline (expansion + détection marque)
```

### Endpoint API correct (important — erreur à ne pas reproduire)

```
GET https://world.openfoodfacts.org/cgi/search.pl
  ?search_terms=...
  &json=1              ← OBLIGATOIRE sinon retourne du HTML
  &sort_by=unique_scans_n
  &tagtype_0=countries
  &tag_contains_0=contains
  &tag_0=france
  &tagtype_1=brands    ← optionnel, si marque détectée
  &tag_contains_1=contains
  &tag_1=paquito
```

**NE PAS utiliser** `/api/v2/search` pour du full-text — cet endpoint ne supporte pas `search_terms` (uniquement filtres par tags exacts). Source : doc OFF officielle.

---

## Données : les 2 tickets de test

### Ticket 1 — Lidl, 2 rue Gaston de Flotte, 13012 Marseille
- Format : ticket dématérialisé Lidl Plus (image PNG)
- 31 lignes, total 96,37€
- Libellés plutôt lisibles (ex: "Beurre bio doux", "Banh Bao Porc")
- MDD Lidl : Vitasia (asiatique), Envia (laitier), Vergers Gourmands (compotes), Fin Carré (chocolat), Italiamo (pasta)
- 3 produits au poids sans EAN : 2× Magret de Canard IGP + Banane Bio fairtrade

### Ticket 2 — Intermarché, 37 rue Gaston de Flotte, 13012 Marseille
- Format : ticket dématérialisé PDF (carte fidélité)
- 31 lignes, total 105,02€ (dont 6,40€ de cagnotte fidélité utilisée)
- Libellés très tronqués (ex: "PAQ.BCL POM.POIR.SSA", "BIO PAT CREME UHT 30")
- MDD Intermarché : Paquito (enfants), Chabrior (épicerie/choco), Pâturages (laitier), Labell (hygiène), Odyssée (poisson), Expert Club (alcool), Vrai de Nature (œufs), Regain Bio (bio), Jardin Bio, La Boulangère
- 3 produits sans EAN : 2× Concombre bio (PLU), Cébette (botte), Tomate grappe vrac

---

## Architecture technique cible (MVP)

### Stack minimale viable

```
Entrée ticket
  ├── Photo papier → LLM vision (Claude Haiku ou GPT-4o-mini)
  │     Coût : ~0.02-0.04€/ticket
  │     Sortie : JSON [{libelle, qte, prix_unitaire, prix_total}]
  │
  └── Email dématérialisé → parsing PDF/HTML
        Coût : quasi nul
        Le client configure un forwarding automatique vers tickets@tonapp.fr

Matching produit
  ├── Cache lookup (libelle + enseigne) → réponse instantanée
  ├── Expansion abréviations + détection marque MDD
  ├── API Open Food Facts /cgi/search.pl
  └── Fallback LLM si no_match (~0.005€/ligne)

Enrichissement
  └── Open Food Facts : catégorie, nutriscore, marque canonique
      Base : 3.5M produits, très bonne couverture MDD françaises

Stockage
  └── Table: {user_id, date, enseigne, libelle, libelle_canonique,
              ean, categorie, marque, prix_unitaire, qte, prix_total}
```

### Coûts estimés en croisière

| Volume | Coût OCR LLM | Coût API OFF | Total |
|--------|-------------|--------------|-------|
| 100 users × 4 tickets/mois × 30 lignes | ~5€ | gratuit | ~5€/mois |
| 1000 users × 4 tickets/mois × 30 lignes | ~50€ | gratuit | ~50€/mois |
| 10k users | ~500€ | gratuit | ~500€/mois |

Cache agressif : après 3 mois, 80%+ des lignes sont en cache → coût ÷ 5.

---

## Données et sources

### Open Food Facts
- **URL API** : `https://world.openfoodfacts.org/cgi/search.pl`
- **Couverture** : ~3.5M produits, excellente sur MDD françaises
- **Gratuit**, sans clé API, sans limite raisonnable
- **User-Agent obligatoire** : format `AppName/Version (contact@example.com)`
- Bon pour : marques nationales, MDD (Paquito, Chabrior, Vitasia, Envia...), produits packagés
- Mauvais pour : produits frais au poids, PLU, cebette, champignons en vrac

### Sources complémentaires à intégrer plus tard
- **Open Beauty Facts** : cosmétiques/hygiène (pour matcher "LABELL PH 3 PLIS ROS")
- **Scraping enseignes** (drive Carrefour, Auchan, Leclerc) : prix en temps réel, mais fragile et zone grise légale
- **Tickets dématérialisés** des apps fidélité (Lidl Plus, Carrefour Pass) : accès via reverse-engineering API ou consentement user

---

## Mapping MDD par enseigne (à enrichir)

```python
MDD_BY_ENSEIGNE = {
    "Lidl": [
        "Vitasia",          # asiatique
        "Envia",            # laitier (beurre, fromage)
        "Milbona",          # laitier (yaourts, lait)
        "Vergers Gourmands",# compotes, desserts fruits
        "Fin Carré",        # chocolat
        "Italiamo",         # pâtes, épicerie italienne
        "Sondey",           # biscuits
        "Eridanous",        # produits méditerranéens (feta, olives)
        "Castello",         # sel, condiments
        "Vemondo",          # veggie/vegan
        "Crownfield",       # céréales
        "Bon Gelati",       # glaces
        "Combino",          # pâtes bas de gamme
    ],
    "Intermarché": [
        "Paquito",                  # produits enfants (compotes, jus)
        "Chabrior",                 # épicerie, chocolat, biscuits
        "Pâturages",                # laitier standard
        "Pâturages & Compagnie",    # laitier bio (abrév. "P&C")
        "Labell",                   # hygiène, papeterie
        "Odyssée",                  # conserves poisson
        "Expert Club",              # alcool, cidre
        "Vrai de Nature",           # œufs, volaille plein air
        "Regain Bio",               # boissons végétales bio
        "Itinéraire des Saveurs",   # épicerie monde
        "Monique Ranou",            # charcuterie, traiteur
        "Saint Eloi",               # charcuterie basique
        "Jardin Bio",               # bio (abrév. "J.BIO")
        "La Campanière",            # volaille
        "Paturages Bio",            # laitier bio (abrév. "BIO PAT")
    ],
    "Carrefour": [
        "Carrefour", "Carrefour Bio", "Carrefour Discount",
        "Reflets de France", "Filière Qualité",
    ],
    "Auchan": [
        "Auchan", "Auchan Bio", "Pouce", "Mmm!",
    ],
    "Leclerc": [
        "Marque Repère", "Eco+", "Nos Régions ont du Talent",
    ],
}
```

---

## Abréviations connues par enseigne (à enrichir)

```python
ABBREVIATIONS = {
    # Marques Intermarché
    "PAQ.":          "Paquito",
    "P&C":           "Pâturages & Compagnie",
    "BIO PAT":       "Pâturages Bio",
    "PAT ":          "Pâturages ",
    "CHAB":          "Chabrior",
    "J.BIO":         "Jardin Bio",
    "LA BOUL":       "La Boulangère",
    "DR SCHAR":      "Dr Schär",
    "REGAINBIO":     "Regain Bio",
    # Mots génériques
    "BCL":           "Boucles",
    "POM.":          "Pomme",
    "POIR.":         "Poire",
    "POM ":          "Pomme ",
    "NAT ":          "Nature ",
    "SSA":           "sans sucre ajouté",
    "CIDR":          "Cidre",
    "NOR":           "Normandie",
    "PH":            "Papier Hygiénique",
    "CEREA.":        "Céréales",
    "CHOCOL":        "Chocolat",
    "ECO PA":        "Eco Pack",
    "PECHE C":       "Pêche Canne",
    "AMANDE LEG":    "Amande Légère",
    "CREME UHT":     "Crème UHT",
    "GNOCCHI DI PAT":"Gnocchi di patate",
}
```

---

## Limites connues et comment les traiter

### Produits sans EAN (toujours)
- Fruits/légumes au poids (PLU interne) → catégoriser par libellé uniquement
- Viande à la coupe (Magret 0,364kg) → idem
- Botte de cébette, champignons vrac → idem
- **Stratégie** : catégoriser quand même (frais, légumes, viande...) pour le suivi budget même sans EAN

### Ambiguïté de format (fréquent)
- "Président Emmental" → EAN différent selon 50g/150g/200g/350g
- "Chabrior Tablette Chocolat" → lait ? noir ? 48% ? bio ?
- **Stratégie court terme** : matcher sur le produit canonique (pas le SKU), le prix aide à désambiguïser
- **Stratégie long terme** : quand l'user scanne le code-barre physique dans son placard, on stocke `libelle + prix → EAN exact`. Cache enrichi par les utilisateurs.

### MDD non couvertes dans OFF
- Rares mais existent (certains produits Lidl récents, saisonniers)
- **Stratégie** : fallback LLM (`"Voici un libellé Lidl : 'Galette Sésame Gingembre'. À quelle catégorie appartient ce produit ?"`) pour avoir au minimum la catégorie

### Tickets papier froissés ou mal éclairés
- OCR LLM rate ~5-10% des lignes si image mauvaise qualité
- **Stratégie** : UI qui montre le ticket parsé et permet à l'user de corriger les erreurs. Chaque correction enrichit le cache.

### RGPD
- Scan de ticket = données personnelles de consommation
- Mention obligatoire en inscription : finalité, durée de conservation, droit d'accès/suppression
- Pas de revente de données individuelles (seulement agrégatées et anonymisées)
- Hébergement souverain préférable (OVH, Scaleway) si cible French market

---

## Prochaines étapes recommandées

### Phase 1 — Valider le matching (cette semaine)
- [ ] Lancer `match_tickets.py` sur les 2 tickets de test
- [ ] Mesurer le vrai taux de match (objectif : >60% match ou ambiguous)
- [ ] Identifier les patterns des no_match pour enrichir ABBREVIATIONS et MDD_BY_ENSEIGNE
- [ ] Tester avec 5-10 tickets personnels de différentes enseignes

### Phase 2 — MVP interface (mois 1-2)
- [ ] OCR de ticket photo via API Claude Vision ou GPT-4o
  - Prompt : *"Extrais chaque ligne de ce ticket en JSON : [{libelle, qte, prix_unitaire, prix_total}]. Identifie l'enseigne."*
- [ ] Pipeline email forwarding : adresse `tickets@tonapp.fr`, parsing PDF/HTML entrants
- [ ] Dashboard simple : dépenses par catégorie, par enseigne, par mois
- [ ] Déployer le matching en API REST (FastAPI ou Flask)

### Phase 3 — Enrichissement et valeur utilisateur (mois 3-6)
- [ ] Scan code-barre physique (ZXing ou BarcodeDetector API) → enrichit le cache libellé→EAN
- [ ] "Tu aurais économisé X€ si tu avais acheté ces 5 produits ailleurs"
  - Nécessite des prix de référence → scraping drive ou données OFF prix historiques
- [ ] Budgets par catégorie avec alertes dépassement
- [ ] Nutriscore moyen du panier par semaine
- [ ] Détection des habitudes : "tu achètes du Ricoré toutes les 3 semaines"

### Phase 4 — Monétisation (mois 6-12)
- [ ] Freemium : historique 3 mois gratuit, analyses avancées + export = 5€/mois
- [ ] Data B2B : panel anonymisé vendu aux marques CPG (nécessite >10k users actifs)
- [ ] Partenariats CSE / mutuelles pour distribution captive

---

## Questions ouvertes / décisions à prendre

1. **Mobile first ou web first ?** → Web first (scan photo depuis mobile via browser) = moins de friction, pas de review AppStore
2. **OCR maison ou API LLM ?** → API LLM recommandé pour le MVP (GPT-4o-mini = 0.15$/1M tokens input, très compétitif pour de l'OCR ticket)
3. **Base de données ?** → PostgreSQL (Supabase ou Railway pour démarrer vite)
4. **Auth ?** → Magic link email (pas de password = moins de friction, moins de risque)
5. **Monétisation initiale ?** → Pas de paywall au démarrage. Freemium après 1000 users actifs.

---

## Contexte marché (pour mémoire)

- **86%** des courses alimentaires en France se font encore en magasin physique (2024)
- **14%** en ligne (essentiel en drive, peu en livraison)
- → Le ticket de caisse papier/dématérialisé reste la seule source de data exhaustive
- Marché e-commerce alimentaire : 23Md€ en 2024, +5%/an
- Concurrents directs inexistants sur cet angle précis (analyse niveau produit, pas niveau enseigne)
- Concurrents indirects : Bankin'/Joko (niveau enseigne), Fidme/10%/Shopmium (cashback, pas analyse)

---

## Fichiers du projet

```
match_tickets.py    Script Python principal — matching ticket → OFF
off_cache.json      Cache persistant (généré au premier run)
results.json        Résultats détaillés du dernier run (généré au run)
CLAUDE.md           Ce fichier — contexte complet du projet
```