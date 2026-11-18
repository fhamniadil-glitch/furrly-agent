"""FURRLY — Agent « Top 3 produits chien » du matin.

Utilisation :
    python main.py --dry-run     # affiche/archive le rapport SANS l'envoyer
    python main.py               # mode normal (GitHub Actions) : vérifie l'heure de Paris, envoie à 9h00
    python main.py --force       # envoie tout de suite, sans vérifier l'heure
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml
from dotenv import load_dotenv

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

from agent import BudgetDepasse, Compteur, creer_agent  # noqa: E402
from collect.catalog import lire_catalogue  # noqa: E402
from collect.meta_ads import MetaAdLibrary  # noqa: E402
from memory import Memoire  # noqa: E402
from notify import envoyer_email, envoyer_telegram  # noqa: E402
from report import date_fr, evenements_a_venir, generer  # noqa: E402
from scoring import plan_test, scorer  # noqa: E402

RAPPORTS = ICI.parent / "rapports"
log = logging.getLogger("top3")


def _mots(txt: str) -> set[str]:
    txt = unicodedata.normalize("NFKD", txt.lower()).encode("ascii", "ignore").decode()
    return {m for m in re.findall(r"[a-z]{4,}", txt) if m not in {"pour", "chien", "chiens", "avec", "dogs"}}


def deja_au_catalogue(nom: str, catalogue: list[dict]) -> str | None:
    m = _mots(nom)
    for p in catalogue:
        t = _mots(p["titre"])
        if m and t and len(m & t) / len(m) >= 0.6:
            return p["titre"]
    return None


def verifier_image(url: str | None) -> str | None:
    """Garde l'URL si elle pointe vers une vraie image (ou si on ne peut pas vérifier)."""
    if not url or not url.startswith("http"):
        return None
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, stream=True)
        ctype = r.headers.get("content-type", "")
        r.close()
        if r.status_code in (404, 410) or (r.status_code == 200 and not ctype.startswith("image")):
            return None
    except requests.RequestException:
        pass  # réseau indisponible : on ne peut pas trancher, on garde l'URL
    return url


def attendre_heure(cible: datetime) -> None:
    reste = (cible - datetime.now(cible.tzinfo)).total_seconds()
    if 0 < reste <= 3600:
        log.info("Rapport prêt. Attente de %d min pour un envoi à %s.", reste // 60, cible.strftime("%H:%M"))
        time.sleep(reste)


def executer(args) -> int:
    load_dotenv(ICI / ".env")
    load_dotenv(ICI.parent / ".env")
    cfg = yaml.safe_load((ICI / "config.yaml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["envoi"]["fuseau"])
    now = datetime.now(tz)
    jour = now.date()
    h_envoi = cfg["envoi"]["heure"]

    db_path = ICI / "furrly.db"
    if args.dry_run:  # le test ne modifie pas la vraie mémoire
        tmp = Path(tempfile.mkdtemp()) / "furrly.db"
        if db_path.exists():
            shutil.copy(db_path, tmp)
        db_path = tmp
    mem = Memoire(db_path)

    if not (args.dry_run or args.force):
        if not (h_envoi - 1 <= now.hour <= h_envoi):
            log.info("Il est %s à Paris : hors créneau (%dh-%dh). Rien à faire.", now.strftime("%H:%M"), h_envoi - 1, h_envoi)
            return 0
        if mem.deja_envoye(jour):
            log.info("Rapport du %s déjà envoyé. Rien à faire.", jour)
            return 0

    ia = cfg["ia"]
    compteur = Compteur(ia["prix_entree_mtok"], ia["prix_sortie_mtok"], ia["prix_recherche_web"], ia["budget_max_usd"])
    avertissements: list[str] = []

    # 1. Catalogue Furrly
    catalogue = lire_catalogue(cfg["boutique"]["catalogue_json"])
    if not catalogue:
        avertissements.append("Catalogue Furrly illisible : l'exclusion des produits déjà vendus n'est pas garantie.")

    # 2. Recherche IA + sortie structurée
    meta = MetaAdLibrary(cfg["meta"])
    agent = creer_agent(cfg, compteur)
    try:
        notes = agent.rechercher(catalogue, mem.cles_connues(), jour, meta.disponible)
        sortie = agent.structurer(notes, jour)
    except BudgetDepasse as e:
        log.error("%s", e)
        raise
    log.info("%d candidats validés par pydantic", len(sortie.candidats))

    # 3. Bibliothèque pub Meta + scoring
    resultats = []
    for c in sortie.candidats:
        donnees_meta = None
        for mc in c.mots_cles_meta[:2]:
            donnees_meta = meta.analyser(mc)
            if donnees_meta is not None or not meta.disponible:
                break
        r = scorer(c, donnees_meta, cfg)
        r.plan = plan_test(r.finances, cfg)
        doublon = deja_au_catalogue(c.nom, catalogue)
        if doublon:
            r.elimine = True
            r.raisons_elimination.append(f"déjà au catalogue (« {doublon} »)")
        mem.enregistrer_releve(jour, c.cle, c.nom, r.score, r.phase, [k.model_dump() for k in c.kpis], donnees_meta)
        resultats.append(r)
    if not meta.disponible:
        avertissements.append(f"API Meta non utilisée — {meta.erreur}. Durée/intensité des pubs estimées via la recherche web.")

    # 4. Sélection du TOP 3 (repos de 14 j, sauf +10 points)
    s = cfg["seuils"]
    top, ecartes = [], []
    for r in sorted(resultats, key=lambda x: x.score, reverse=True):
        if r.elimine:
            ecartes.append(r)
            continue
        ok, badge = mem.statut_repos(r.candidat.cle, r.score, jour, s["repos_jours"], s["repos_bonus_points"])
        if not ok:
            r.raison_ecart = f"déjà proposé il y a moins de {s['repos_jours']} j"
            ecartes.append(r)
            continue
        r.badge = badge
        if len(top) < 3:
            top.append(r)
    for r in top:
        r.candidat.image_url = verifier_image(r.candidat.image_url)
        if not r.candidat.image_url:
            avertissements.append(f"Photo de « {r.candidat.nom} » non vérifiée.")

    # 5. Rubriques
    cles_top = {r.candidat.cle for r in top}
    alertes = mem.passages_saturation(jour) + [a.model_dump() for a in sortie.alertes_catalogue]
    alertes += [{"produit": r.candidat.nom, "phase": r.phase, "raison": "candidat écarté"}
                for r in resultats if r.phase in ("Pic", "Saturé")]
    ctx = {
        "objet": cfg["envoi"]["objet"].format(date=jour.strftime("%d/%m/%Y")),
        "date_fr": date_fr(jour), "top": top, "elimines": ecartes, "nb_analyses": len(resultats),
        "avertissements": avertissements, "watchlist": mem.watchlist(jour, cles_top), "alertes": alertes,
        "evenements": evenements_a_venir(cfg, jour), "calendrier_ia": sortie.calendrier,
        "lundi": jour.weekday() == 0, "bilan": mem.bilan_semaine(jour), "bilan_ia": sortie.bilan_semaine,
        "tendances": sortie.tendances_de_fond, "cout": compteur.cout, "recherches": compteur.recherches,
        "lectures": compteur.lectures,
        "modele": (getattr(agent, "modele_ok", None) or "gemini") if ia.get("fournisseur", "gemini") != "anthropic" else ia["modele"],
    }
    html = generer(ctx, cfg)

    # 6. Archive
    RAPPORTS.mkdir(exist_ok=True)
    fichier = RAPPORTS / f"{jour.isoformat()}{'-test' if args.dry_run else ''}.html"
    fichier.write_text(html, encoding="utf-8")
    texte = "\n".join([ctx["objet"], ""] + [
        f"{i}. {r.candidat.nom} — {r.score}/100 — {r.verdict} — phase {r.phase} — "
        f"prix {r.finances.prix_conseille_eur or 'non vérifié'} € — ROAS BE {r.finances.roas_rentabilite or 'non vérifié'}"
        for i, r in enumerate(top, 1)] + ["", f"Coût : {compteur.cout:.3f} $"])
    print("\n" + texte + f"\n\nRapport : {fichier}\n")

    if args.dry_run:
        log.info("Mode --dry-run : rien n'est envoyé.")
        return 0

    # 7. Envoi à l'heure pile
    for r in top:
        mem.marquer_propose(jour, r.candidat.cle, r.score)
    if not args.force:
        attendre_heure(now.replace(hour=h_envoi, minute=0, second=0, microsecond=0))
    envoyer_email(html, ctx["objet"], cfg["envoi"], texte)
    if cfg["envoi"].get("telegram"):
        envoyer_telegram(texte, html, fichier.name)
    mem.marquer_envoye(jour, compteur.cout, fichier.name)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Furrly — Top 3 produits chien")
    ap.add_argument("--dry-run", action="store_true", help="génère le rapport sans l'envoyer")
    ap.add_argument("--force", action="store_true", help="envoie tout de suite, sans contrôle d'heure")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
                        datefmt="%H:%M:%S")
    try:
        return executer(args)
    except Exception as e:
        log.exception("Échec de l'exécution : %s", e)
        if not args.dry_run:
            try:  # on prévient quand même par email
                cfg = yaml.safe_load((ICI / "config.yaml").read_text(encoding="utf-8"))
                envoyer_email(f"<p>L'agent Top 3 a échoué : {e}</p><p>Voir les journaux GitHub Actions.</p>",
                              "⚠️ Top 3 Furrly — échec", cfg["envoi"], f"Échec : {e}")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
