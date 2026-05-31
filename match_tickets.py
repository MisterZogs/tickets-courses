#!/usr/bin/env python3
"""
Matcher tickets de caisse → Open Food Facts.

Démo sur les 62 lignes des tickets Lidl + Intermarché (Marseille).

Pipeline en 3 étapes par ligne :
  1. Expansion des abréviations courantes du ticket
  2. Détection de la marque MDD probable selon l'enseigne
  3. Recherche dans l'API Open Food Facts avec stratégies en cascade

Cache local persistant pour éviter de re-appeler l'API entre 2 runs.

Usage :
    pip install requests
    python match_tickets.py
"""

import json
import re
import time
from pathlib import Path
from typing import Optional

import requests

# =============================================================================
# DONNÉES : les 2 tickets déjà extraits par LLM vision
# =============================================================================

TICKETS = [
    {
        "enseigne": "Lidl",
        "magasin": "Marseille Flotte",
        "lignes": [
            {"libelle": "8 raviolis vapeur", "qte": 1, "prix": 3.99},
            {"libelle": "La Laitière île flottante", "qte": 1, "prix": 2.99},
            {"libelle": "Banh Bao Porc", "qte": 1, "prix": 2.99},
            {"libelle": "Tortellini épinards", "qte": 2, "prix": 1.49},
            {"libelle": "Accras de morue", "qte": 1, "prix": 2.99},
            {"libelle": "Meule fruitée râpée", "qte": 1, "prix": 3.69},
            {"libelle": "Galette de pois", "qte": 1, "prix": 1.99},
            {"libelle": "Président Emmental", "qte": 1, "prix": 5.45},
            {"libelle": "Galette soja tomate", "qte": 1, "prix": 1.99},
            {"libelle": "Assortiment vapeur", "qte": 1, "prix": 3.99},
            {"libelle": "Gnocchi au pesto", "qte": 1, "prix": 1.79},
            {"libelle": "Plat.mini nems porc", "qte": 1, "prix": 2.45},
            {"libelle": "Magret de Canard IGP", "qte": 0.364, "unite": "kg", "prix": 7.97},
            {"libelle": "Magret de Canard IGP", "qte": 0.426, "unite": "kg", "prix": 9.33},
            {"libelle": "Shot gingembre Bio", "qte": 2, "prix": 0.99},
            {"libelle": "Shot de gingembre Bio", "qte": 3, "prix": 0.79},
            {"libelle": "Feta grecque", "qte": 1, "prix": 2.45},
            {"libelle": "Beurre bio doux", "qte": 2, "prix": 2.89},
            {"libelle": "Crépinettes x 4", "qte": 1, "prix": 3.99},
            {"libelle": "Camembert de chèvre", "qte": 1, "prix": 2.29},
            {"libelle": "Crème fraîche 30%", "qte": 1, "prix": 1.89},
            {"libelle": "Compote de pommes", "qte": 2, "prix": 2.35},
            {"libelle": "Compote Pomme Banane", "qte": 2, "prix": 2.16},
            {"libelle": "Verseuse de sel fin", "qte": 1, "prix": 1.63},
            {"libelle": "Galettes de riz choc", "qte": 2, "prix": 1.29},
            {"libelle": "Sacs poubelles 30L", "qte": 1, "prix": 1.12, "non_alimentaire": True},
            {"libelle": "Chocolat au lait Bio", "qte": 1, "prix": 1.89},
            {"libelle": "Chocolat noir Bio", "qte": 1, "prix": 1.59},
            {"libelle": "Chocolat noir 85% cacao", "qte": 1, "prix": 1.87},
            {"libelle": "BIO Chocolat noir", "qte": 1, "prix": 2.15},
            {"libelle": "Banane Bio fairtrade", "qte": 0.708, "unite": "kg", "prix": 1.48},
        ],
    },
    {
        "enseigne": "Intermarché",
        "magasin": "Marseille Flotte",
        "lignes": [
            {"libelle": "PAQ.BCL POM.POIR.SSA", "qte": 1, "prix": 2.37},
            {"libelle": "ODYSSEE THON PECHE C", "qte": 1, "prix": 1.70},
            {"libelle": "EXPERT CLUB CIDR NOR", "qte": 1, "prix": 1.95},
            {"libelle": "P&C PAIN COMPLET BIO", "qte": 1, "prix": 2.39},
            {"libelle": "J.BIO PUR JUS CITRON", "qte": 1, "prix": 3.15},
            {"libelle": "RUMMO GNOCCHI DI PAT", "qte": 1, "prix": 2.45},
            {"libelle": "POM'POTE POM NAT BIO", "qte": 1, "prix": 6.94},
            {"libelle": "POM'POTE POM NAT BIO", "qte": 1, "prix": 6.94},
            {"libelle": "NESTLE RICORE ECO PA", "qte": 1, "prix": 3.80},
            {"libelle": "CONCOMBRE PIECE BIO", "qte": 1, "prix": 2.69},
            {"libelle": "CONCOMBRE PIECE BIO", "qte": 1, "prix": 2.69},
            {"libelle": "TOFU NATURE VEGAN BI", "qte": 1, "prix": 2.94},
            {"libelle": "TOFU FUME VEGAN BIO", "qte": 1, "prix": 3.00},
            {"libelle": "NESTLE RICORE ECO PA", "qte": 1, "prix": 3.80},
            {"libelle": "CONCHIGLIE RIGATE N", "qte": 1, "prix": 2.35},
            {"libelle": "CAROTTE SACHET 1KG B", "qte": 1, "prix": 2.89},
            {"libelle": "CHAB TABLETTE CHOCOL", "qte": 1, "prix": 2.32},
            {"libelle": "CEBETTE", "qte": 1, "prix": 2.25},
            {"libelle": "REGAINBIO AMANDE LEG", "qte": 1, "prix": 1.58},
            {"libelle": "BANANE RUBAN 5 FRUIT", "qte": 1, "prix": 1.99},
            {"libelle": "CHAB TABLETTE CHOCOL", "qte": 1, "prix": 2.32},
            {"libelle": "BIO PAT CREME UHT 30", "qte": 1, "prix": 4.11},
            {"libelle": "DR SCHAR PAIN CEREA.", "qte": 1, "prix": 3.40},
            {"libelle": "DR SCHAR PAIN CEREA.", "qte": 1, "prix": 3.40},
            {"libelle": "LA BOUL PAIN MIE CER", "qte": 1, "prix": 2.50},
            {"libelle": "FRAISE DE ROQUEVAIRE", "qte": 1, "prix": 5.95},
            {"libelle": "OEUF VRAI DE NATURE", "qte": 1, "prix": 6.56},
            {"libelle": "OEUF VRAI DE NATURE", "qte": 1, "prix": 6.56},
            {"libelle": "TOMATE GRAPPE VRAC", "qte": 0.660, "unite": "kg", "prix": 2.96},
            {"libelle": "CHAMPIGNON BLANC 200", "qte": 1, "prix": 2.99},
            {"libelle": "LABELL PH 3 PLIS ROS", "qte": 1, "prix": 4.78, "non_alimentaire": True},
        ],
    },
]

# =============================================================================
# CONNAISSANCE PAR ENSEIGNE (à enrichir progressivement)
# =============================================================================

# MDD principales par enseigne — pour orienter la recherche par marque
MDD_BY_ENSEIGNE = {
    "Lidl": [
        "Vitasia", "Envia", "Milbona", "Vergers Gourmands", "Fin Carré",
        "Italiamo", "Sondey", "Eridanous", "Castello", "Vemondo",
        "Crownfield", "Maître Truffout", "Bon Gelati", "Combino",
    ],
    "Intermarché": [
        # MDD Intermarché
        "Paquito", "Chabrior", "Pâturages", "Labell", "Odyssée",
        "Expert Club", "Vrai de Nature", "Pâturages & Compagnie",
        "Regain Bio", "Itinéraire des Saveurs", "Monique Ranou",
        "Saint Eloi", "Jardin Bio", "La Campanière",
        # Marques nationales fréquemment listées chez Intermarché
        "Dr Schär", "La Boulangère", "Rummo", "Pom'Potes", "Materne",
        "Nestlé", "Ricoré",
    ],
}

# Abréviations fréquentes sur les tickets → expansion
ABBREVIATIONS = {
    # Préfixes marques
    "PAQ.": "Paquito",
    "P&C": "Pâturages & Compagnie",
    "BIO PAT": "Pâturages Bio",
    "PAT ": "Pâturages ",
    "CHAB": "Chabrior",
    "J.BIO": "Jardin Bio",
    "LA BOUL": "La Boulangère",
    "DR SCHAR": "Dr Schär",
    "REGAINBIO": "Regain Bio",
    # Mots courants
    "BCL": "Boucles",
    "POM.": "Pomme",
    "POIR.": "Poire",
    "POM ": "Pomme ",
    "NAT ": "Nature ",
    "SSA": "sans sucre ajouté",
    "CIDR": "Cidre",
    "NOR": "Normandie",
    "PH": "Papier Hygiénique",
    "CEREA.": "Céréales",
    "CHOCOL": "Chocolat",
    "ECO PA": "Eco Pack",
    "PECHE C": "Pêche Canne",
    "AMANDE LEG": "Amande Légère",
    "CREME UHT": "Crème UHT",
    "GNOCCHI DI PAT": "Gnocchi di patate",
    # Abréviations en fin de libellé
    "PLAT.": "",          # préfixe "plat cuisiné" parasite
    " CER": " Céréales",  # Céréales tronqué (LA BOUL PAIN MIE CER)
    " BI": " Bio",        # Bio tronqué (TOFU NATURE VEGAN BI)
}

# =============================================================================
# CACHE LOCAL
# =============================================================================

CACHE_FILE = Path(__file__).parent / "off_cache.json"


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# =============================================================================
# EXPANSION DES LIBELLÉS TRONQUÉS
# =============================================================================


def expand_libelle(libelle: str) -> str:
    """Étend les abréviations courantes."""
    expanded = libelle
    for abbr, full in ABBREVIATIONS.items():
        # Remplace en garantissant un espace après (évite "PaquitoBoucles")
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)
        expanded = pattern.sub(full + " ", expanded)
    # Nettoyage : espaces multiples + ponctuation orpheline
    expanded = re.sub(r"\s+", " ", expanded)
    expanded = re.sub(r"\s+([.,])", r"\1", expanded)
    return expanded.strip()


# Mots parasites à retirer avant recherche (conditionnement, format, packaging)
_NOISE_PATTERN = re.compile(
    r'\b(?:Eco\s*Pack|\d+\s*(?:KG|G|L|CL|ML)|SACHET|PIECE|PLIS|RUBAN|\d+\s*FRUITS?)\b',
    re.IGNORECASE,
)


def clean_for_search(text: str) -> str:
    cleaned = _NOISE_PATTERN.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def detect_brand(libelle: str, enseigne: str) -> Optional[str]:
    """Détecte la marque MDD probable à partir du libellé."""
    libelle_norm = libelle.upper()
    for brand in MDD_BY_ENSEIGNE.get(enseigne, []):
        # Match direct sur le nom de marque
        if brand.upper() in libelle_norm:
            return brand
        # Match sur un mot distinctif de la marque (>3 chars)
        for word in brand.split():
            if len(word) > 3 and word.upper() in libelle_norm:
                return brand
    return None


# =============================================================================
# REQUÊTE OPEN FOOD FACTS
# =============================================================================

# NOTE : /api/v2/search ne supporte PAS la recherche full-text (search_terms).
# Il faut utiliser l'API v1 : /cgi/search.pl?search_terms=...&json=1
# Source : https://openfoodfacts.github.io/openfoodfacts-server/api/ref-cheatsheet/
#   "Important: full text search currently works only for v1 API
#    (or search-a-licious, which is in beta)"

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

# User-Agent obligatoire — OFF bloque "python-requests/X.X" générique
# Format : AppName/Version (email-ou-url)
USER_AGENT = "ReceiptMatcher/0.2 (demo@example.com)"


def search_off(
    query: str,
    brand: Optional[str] = None,
    limit: int = 5,
    timeout: int = 15,
    max_retries: int = 6,
    retry_delay: float = 5.0,
    country_filter: bool = True,
) -> list[dict]:
    """Cherche un produit sur Open Food Facts via l'API v1 (seule qui supporte
    le full-text search par search_terms).

    Endpoint : GET https://world.openfoodfacts.org/cgi/search.pl
    Doc      : https://openfoodfacts.github.io/openfoodfacts-server/api/ref-cheatsheet/

    Retry automatique avec backoff exponentiel sur 5xx et timeout.
    Délais : 5s, 10s, 20s, 40s, 80s, 120s (cappé) + jitter aléatoire.
    """
    params = {
        "search_terms": query,
        "json": 1,
        "page_size": limit,
        "sort_by": "unique_scans_n",
        "fields": "code,product_name,product_name_fr,brands,quantity,nutriscore_grade",
    }

    if country_filter:
        params["tagtype_0"] = "countries"
        params["tag_contains_0"] = "contains"
        params["tag_0"] = "france"

    # Filtre par marque si détectée — réduit le bruit considérablement
    if brand:
        idx = 1 if country_filter else 0
        params[f"tagtype_{idx}"] = "brands"
        params[f"tag_contains_{idx}"] = "contains"
        params[f"tag_{idx}"] = brand

    for attempt in range(max_retries + 1):
        try:
            r = requests.get(
                OFF_SEARCH_URL,
                params=params,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
            if r.status_code == 200:
                return r.json().get("products", [])
            elif r.status_code in (429, 500, 502, 503, 504):
                if attempt < max_retries:
                    wait = min(retry_delay * (2 ** attempt), 120)
                    print(f"    ⚠️  HTTP {r.status_code} — retry {attempt + 1}/{max_retries} dans {wait:.0f}s…")
                    time.sleep(wait)
                else:
                    print(f"    ⚠️  HTTP {r.status_code} — abandon après {max_retries} tentatives")
            else:
                print(f"    ⚠️  HTTP {r.status_code} (non retryable)")
                break
        except requests.Timeout:
            if attempt < max_retries:
                wait = min(retry_delay * (2 ** attempt), 120)
                print(f"    ⚠️  Timeout — retry {attempt + 1}/{max_retries} dans {wait:.0f}s…")
                time.sleep(wait)
            else:
                print(f"    ⚠️  Timeout — abandon après {max_retries} tentatives")
        except requests.RequestException as e:
            print(f"    ⚠️  Erreur réseau : {e}")
            break

    return []


# =============================================================================
# STRATÉGIE DE MATCHING
# =============================================================================


def match_line(line: dict, enseigne: str, cache: dict) -> dict:
    """Matche une ligne de ticket avec un produit Open Food Facts."""
    libelle = line["libelle"]
    cache_key = f"{enseigne}::{libelle}"

    # Hit de cache → réponse instantanée et gratuite
    if cache_key in cache:
        return {**line, **cache[cache_key], "from_cache": True}

    expanded = expand_libelle(libelle)
    brand = detect_brand(expanded, enseigne)

    # Stratégie en cascade
    matches = []

    # 1. Recherche avec marque détectée
    if brand:
        matches = search_off(expanded, brand=brand)

    # 2. Si rien, recherche full-text sans marque
    if not matches:
        matches = search_off(expanded)

    # 3. Si rien, recherche sur le libellé brut (sans expansion)
    if not matches and expanded != libelle:
        matches = search_off(libelle)

    # 4. Si rien, recherche après suppression des mots parasites (packaging, format)
    cleaned = clean_for_search(expanded)
    if not matches and cleaned != expanded:
        matches = search_off(cleaned, brand=brand)

    # 5. Si rien, recherche sur les 3 premiers mots (requête trop longue/bruit)
    short = " ".join(expanded.split()[:3])
    if not matches and short != expanded:
        matches = search_off(short)

    # 6. Si rien, même recherche sans filtre pays (marques étrangères vendues en France)
    if not matches:
        matches = search_off(expanded, brand=brand, country_filter=False)

    # Construction du résultat
    if not matches:
        result = {
            "status": "no_match",
            "expanded": expanded,
            "brand_detected": brand,
            "candidates": [],
        }
    else:
        candidates = [
            {
                "code": p.get("code"),
                "name": p.get("product_name_fr") or p.get("product_name", ""),
                "brands": p.get("brands", ""),
                "quantity": p.get("quantity", ""),
                "nutriscore": p.get("nutriscore_grade", ""),
            }
            for p in matches[:3]
        ]
        result = {
            "status": "match" if len(matches) == 1 else "ambiguous",
            "expanded": expanded,
            "brand_detected": brand,
            "best_code": candidates[0]["code"],
            "best_name": candidates[0]["name"],
            "candidates": candidates,
        }

    cache[cache_key] = result
    save_cache(cache)  # sauvegarde au fur et à mesure
    return {**line, **result, "from_cache": False}


# =============================================================================
# MAIN
# =============================================================================


def main():
    cache = load_cache()
    results = []
    stats = {
        "match": 0,
        "ambiguous": 0,
        "no_match": 0,
        "from_cache": 0,
    }

    for ticket in TICKETS:
        enseigne = ticket["enseigne"]
        print(f"\n{'='*70}")
        print(f"  {enseigne} — {ticket['magasin']} ({len(ticket['lignes'])} lignes)")
        print(f"{'='*70}")

        for i, line in enumerate(ticket["lignes"], 1):
            au_poids = "unite" in line and line["unite"] == "kg"
            tag = " [au poids]" if au_poids else ""
            print(f"  {i:2}. {line['libelle'][:35]:35} {line['prix']:>6.2f} €{tag}", end="  → ")

            result = match_line(line, enseigne, cache)

            if result["from_cache"]:
                stats["from_cache"] += 1

            if result["status"] == "match":
                stats["match"] += 1
                print(f"✅ {result['best_name'][:40]} [{result['best_code']}]")
            elif result["status"] == "ambiguous":
                stats["ambiguous"] += 1
                names = " | ".join(c["name"][:25] for c in result["candidates"][:2])
                print(f"🟡 {len(result['candidates'])} candidats : {names}")
            else:
                stats["no_match"] += 1
                print(f"❌ aucun match (essayé : '{result['expanded']}')")

            results.append({**result, "enseigne": enseigne})

            # Politesse envers l'API publique (500ms entre appels non-cachés)
            if not result["from_cache"]:
                time.sleep(0.5)

    # ─── Bilan ──────────────────────────────────────────────────────────────
    total = len(results)

    print(f"\n{'='*70}")
    print(f"  BILAN")
    print(f"{'='*70}")
    print(f"  Total lignes              : {total}")
    print()
    print(f"  ✅ Match unique           : {stats['match']:3} ({stats['match']*100//total if total else 0}%)")
    print(f"  🟡 Match ambigu (>1 SKU)  : {stats['ambiguous']:3} ({stats['ambiguous']*100//total if total else 0}%)")
    print(f"  ❌ Aucun match            : {stats['no_match']:3} ({stats['no_match']*100//total if total else 0}%)")
    print()
    print(f"  Taux d'identification     : {(stats['match']+stats['ambiguous'])*100//total if total else 0}%")
    print(f"  Réponses depuis cache     : {stats['from_cache']}")

    # Export JSON
    out = Path(__file__).parent / "results.json"
    out.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Résultats détaillés       : {out}")
    print(f"  Cache persistant          : {CACHE_FILE}")


# =============================================================================
# TESTS OFFLINE (pour vérifier l'expansion sans appeler l'API)
# =============================================================================


def test_offline():
    """Tests des fonctions qui ne nécessitent pas l'API."""
    print("=== Tests offline ===\n")

    cases = [
        ("PAQ.BCL POM.POIR.SSA", "Intermarché"),
        ("P&C PAIN COMPLET BIO", "Intermarché"),
        ("J.BIO PUR JUS CITRON", "Intermarché"),
        ("BIO PAT CREME UHT 30", "Intermarché"),
        ("CHAB TABLETTE CHOCOL", "Intermarché"),
        ("REGAINBIO AMANDE LEG", "Intermarché"),
        ("LABELL PH 3 PLIS ROS", "Intermarché"),
        ("DR SCHAR PAIN CEREA.", "Intermarché"),
        ("LA BOUL PAIN MIE CER", "Intermarché"),
        ("Beurre bio doux", "Lidl"),
        ("Banh Bao Porc", "Lidl"),
        ("La Laitière île flottante", "Lidl"),
    ]
    for libelle, enseigne in cases:
        expanded = expand_libelle(libelle)
        brand = detect_brand(expanded, enseigne)
        print(f"  '{libelle}'")
        print(f"      → expansion : '{expanded}'")
        print(f"      → marque détectée : {brand or '(aucune)'}")
        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_offline()
    else:
        main()
