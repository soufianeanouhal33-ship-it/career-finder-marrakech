"""
scraper_trabajo.py
Collecte des offres de ma.trabajo.org (Marrakech) pour le suivi des stages.

Installation :
    pip install requests beautifulsoup4 pandas openpyxl

Utilisation en ligne de commande :
    python scraper_trabajo.py
    -> cree offres_brutes.xlsx, offres_nettoyees.xlsx et stages_suivi.xlsx

Utilisation depuis ton application :
    from scraper_trabajo import collecter_offres, nettoyer, filtrer_stages
    df = nettoyer(collecter_offres())
    stages = filtrer_stages(df)
"""

import re
import time
import logging
from datetime import date
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
SITE = "https://ma.trabajo.org"
URL_RECHERCHE = f"{SITE}/emploi-information+technology/Marrakech"
# Autres recherches possibles : changer le secteur ou la ville dans l'URL, ex.
# f"{SITE}/emploi-a-marrakech"

MAX_PAGES = 3          # nombre max de pages a lire (10 offres par page)
PARAM_PAGE = "page"    # a verifier sur le site (voir le README ci-dessous)
PAUSE_SECONDES = 2     # pause entre deux requetes (politesse envers le site)
TIMEOUT = 15

MOTS_STAGE = ("stage", "stagiaire", "intern", "internship", "alternance")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (projet etudiant - suivi de stages)",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("scraper_trabajo")


# --------------------------------------------------------------------------
# Collecte
# --------------------------------------------------------------------------
def _parser_page(html: str) -> list[dict]:
    """Extrait les offres d'une page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    offres = []

    for h3 in soup.select("h3"):
        lien = h3.find("a", href=True)
        if not lien or "/offre-" not in lien["href"]:
            continue

        # Conteneur de l'offre : <li> parent, sinon le parent direct du titre
        bloc = h3.find_parent("li") or h3.parent
        texte = bloc.get_text(" ", strip=True)

        img = bloc.find("img")
        entreprise = (img.get("alt") or "").strip() if img else ""

        m_date = re.search(r"Il y a [^A-Z]{1,25}?(?:minute|heure|jour|semaine|mois|an)s?",
                           texte, flags=re.IGNORECASE)

        offres.append({
            "poste": lien.get_text(strip=True),
            "entreprise": entreprise,
            "publication": m_date.group(0).strip() if m_date else "",
            "lien": urljoin(SITE, lien["href"]),
            "apercu": texte[:300],
        })
    return offres


def collecter_offres(url: str = URL_RECHERCHE, max_pages: int = MAX_PAGES) -> pd.DataFrame:
    """Parcourt les pages de resultats et renvoie un DataFrame brut."""
    session = requests.Session()
    session.headers.update(HEADERS)

    toutes, liens_vus = [], set()

    for n in range(1, max_pages + 1):
        page_url = url if n == 1 else f"{url}?{PARAM_PAGE}={n}"
        try:
            r = session.get(page_url, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning("Page %s ignoree (%s)", page_url, e)
            break

        offres = [o for o in _parser_page(r.text) if o["lien"] not in liens_vus]
        if not offres:
            log.info("Plus de nouvelles offres a la page %d, arret.", n)
            break

        liens_vus.update(o["lien"] for o in offres)
        toutes.extend(offres)
        log.info("Page %d : %d offres", n, len(offres))
        time.sleep(PAUSE_SECONDES)

    df = pd.DataFrame(toutes)
    if df.empty:
        log.warning("Aucune offre trouvee : verifie les selecteurs (voir README).")
        return df

    df["source"] = "Trabajo.org"
    df["date_collecte"] = date.today().isoformat()
    return df


# --------------------------------------------------------------------------
# Nettoyage et filtrage
# --------------------------------------------------------------------------
def nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime doublons et espaces superflus, normalise les textes."""
    if df.empty:
        return df
    df = df.copy()
    for col in ("poste", "entreprise", "publication", "apercu"):
        df[col] = (df[col].astype(str)
                   .str.replace(r"\s+", " ", regex=True)
                   .str.strip())
    df["entreprise"] = df["entreprise"].replace("", "Non precisee")
    df = df.drop_duplicates(subset="lien").reset_index(drop=True)
    return df


def filtrer_stages(df: pd.DataFrame) -> pd.DataFrame:
    """Garde les offres de stage et ajoute les colonnes de suivi."""
    if df.empty:
        return df
    motif = "|".join(MOTS_STAGE)
    masque = (df["poste"].str.lower().str.contains(motif, regex=True) |
              df["apercu"].str.lower().str.contains(motif, regex=True))
    stages = df[masque].copy()

    stages["statut_suivi"] = "A postuler"
    stages["date_candidature"] = ""
    stages["remarque"] = ""
    return stages.reset_index(drop=True)


# --------------------------------------------------------------------------
# Execution directe
# --------------------------------------------------------------------------
if __name__ == "__main__":
    brut = collecter_offres()
    brut.to_excel("offres_brutes.xlsx", index=False)

    propre = nettoyer(brut)
    propre.to_excel("offres_nettoyees.xlsx", index=False)

    stages = filtrer_stages(propre)
    stages.to_excel("stages_suivi.xlsx", index=False)

    log.info("Brut : %d | Nettoye : %d | Stages : %d",
             len(brut), len(propre), len(stages))

# --------------------------------------------------------------------------
# README rapide
# --------------------------------------------------------------------------
# - Pagination : ouvre la page 2 sur le site et regarde l'URL. Si le parametre
#   n'est pas "page", change PARAM_PAGE. Si une seule page marche, mets
#   MAX_PAGES = 1.
# - Si aucune offre n'est trouvee : clic droit > Inspecter sur une offre, puis
#   adapte la boucle dans _parser_page (le titre est un <h3> avec un lien
#   contenant "/offre-").
# - Respecte les conditions d'utilisation du site et garde PAUSE_SECONDES >= 1.
