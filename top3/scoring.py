"""Finances, phase et score sur 100. Calculés en Python (pas par l'IA) pour être fiables."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from models import Candidat


@dataclass
class Finances:
    prix_achat_eur: float | None
    cout_rendu_eur: float | None
    prix_conseille_eur: float | None
    tva_eur: float | None
    frais_paiement_eur: float | None
    marge_nette_eur: float | None
    marge_nette_pct: float | None
    roas_rentabilite: float | None
    cpa_max_eur: float | None
    verifie: bool


@dataclass
class Resultat:
    candidat: Candidat
    meta: dict | None
    finances: Finances
    phase: str
    score: float
    detail: dict[str, float]
    elimine: bool
    raisons_elimination: list[str] = field(default_factory=list)
    verdict: str = ""
    badge: str = ""


def _prix_psy(prix: float, terminaisons: list[float]) -> float:
    """Arrondit au-dessus vers 24,90 / 29,95 …"""
    base = math.floor(prix)
    choix = []
    for e in range(base - 1, base + 6):
        for t in terminaisons:
            v = e + t
            if v >= prix and (e % 5 in (4, 9)):
                choix.append(v)
    return round(min(choix), 2) if choix else round(prix, 2)


def calcul_finances(c: Candidat, f: dict) -> Finances:
    if c.prix_fournisseur_usd is None:
        return Finances(None, None, None, None, None, None, None, None, None, False)
    achat = c.prix_fournisseur_usd * f["taux_usd_eur"]
    cout = achat + f["livraison_usd"] * f["taux_usd_eur"] + f["droit_ue_eur"]
    pct, fixe, tva = f["frais_paiement_pct"], f["frais_paiement_fixe_eur"], f["tva"]
    # prix minimum pour atteindre le ROAS objectif : marge ≥ prix / ROAS
    k = 1 / (1 + tva) - pct - 1 / f["roas_objectif"]
    prix_min = (cout + fixe) / k if k > 0 else f["prix_max_eur"]
    # on se cale sur les concurrents si c'est plus haut, sans dépasser le plafond
    cible = prix_min
    if c.prix_concurrents_eur:
        conc = sorted(c.prix_concurrents_eur)[len(c.prix_concurrents_eur) // 2]
        cible = max(prix_min, conc * 0.95)
    cible = min(max(cible, f["prix_min_eur"]), f["prix_max_eur"])
    prix = _prix_psy(cible, f["terminaisons_psy"])
    if prix > f["prix_max_eur"]:  # jamais au-dessus du plafond : 54,90 au lieu de 59,90
        prix = _prix_psy(f["prix_max_eur"] - 5, f["terminaisons_psy"])
    tva_eur = prix - prix / (1 + tva)
    frais = prix * pct + fixe
    marge = prix - tva_eur - frais - cout
    roas = prix / marge if marge > 0 else 99.0
    return Finances(
        prix_achat_eur=round(achat, 2), cout_rendu_eur=round(cout, 2), prix_conseille_eur=prix,
        tva_eur=round(tva_eur, 2), frais_paiement_eur=round(frais, 2), marge_nette_eur=round(marge, 2),
        marge_nette_pct=round(100 * marge / prix, 1), roas_rentabilite=round(roas, 2),
        cpa_max_eur=round(max(marge, 0), 2), verifie=True,
    )


def determiner_phase(c: Candidat, meta: dict | None, s: dict) -> str:
    annonceurs = meta["annonceurs"] if meta else c.annonceurs_estimes
    if annonceurs is None:
        return c.phase_estimee
    if annonceurs > s["annonceurs_sature"]:
        return "Saturé"
    if annonceurs >= s["annonceurs_pic"]:
        return "Pic"
    if not meta and c.phase_estimee in ("Pic", "Saturé"):
        return c.phase_estimee  # sans API, on garde la prudence de l'IA
    if annonceurs >= s["annonceurs_expansion_max"]:
        return "Croissance"
    # moins de 15 annonceurs : Émergent si le marché vient de démarrer, sinon on suit l'IA
    if meta and (meta["jours_max"] < 45 or meta["nouveaux_annonceurs_14j"] >= max(1, annonceurs // 2)):
        return "Émergent"
    return c.phase_estimee if c.phase_estimee in ("Émergent", "Croissance") else "Croissance"


def _borne(x: float) -> float:
    return max(0.0, min(1.0, x))


def scorer(c: Candidat, meta: dict | None, cfg: dict) -> Resultat:
    p, s = cfg["ponderations"], cfg["seuils"]
    fin = calcul_finances(c, cfg["finances"])
    phase = determiner_phase(c, meta, s)

    # 1. Pubs : durée + variantes + nouveaux annonceurs
    if meta and meta["pubs_actives"]:
        duree = _borne(meta["jours_max"] / 60)
        variantes = _borne(meta["variantes_max"] / 5)
        gagnant = 1.0 if meta["pubs_gagnantes"] else 0.0
        nouveaux = _borne(meta["nouveaux_annonceurs_14j"] / 5)
        x_pubs = 0.35 * duree + 0.25 * variantes + 0.25 * gagnant + 0.15 * nouveaux
    else:
        x_pubs = 0.3  # signal non vérifié par l'API → note prudente
    # 2. Demande
    t30, t90 = c.tendance_30j_pct, c.tendance_90j_pct
    if t30 is None and t90 is None:
        x_dem = 0.3
    else:
        x_dem = 0.6 * _borne((t30 or 0) / 50) + 0.4 * _borne((t90 or 0) / 100)
    # 3. Marge / ROAS
    if fin.verifie and fin.roas_rentabilite:
        x_marge = _borne((3.5 - fin.roas_rentabilite) / 1.5)  # ROAS 2,0 → 1 ; 3,5 → 0
    else:
        x_marge = 0.2
    # 4. Viral / 6. Adéquation
    x_viral = c.note_virale / 10
    x_adeq = c.note_adequation / 10
    # 5. Fenêtre d'opportunité
    x_fen = {"Émergent": 1.0, "Croissance": 0.7, "Pic": 0.2, "Saturé": 0.0}[phase]
    if meta:
        x_fen = 0.7 * x_fen + 0.3 * _borne(1 - meta["annonceurs"] / s["annonceurs_sature"])

    detail = {
        "pubs": round(p["pubs"] * x_pubs, 1),
        "demande": round(p["demande"] * x_dem, 1),
        "marge": round(p["marge"] * x_marge, 1),
        "viral": round(p["viral"] * x_viral, 1),
        "fenetre": round(p["fenetre"] * x_fen, 1),
        "adequation": round(p["adequation"] * x_adeq, 1),
    }
    score = round(sum(detail.values()), 1)

    raisons = []
    if c.interdit:
        raisons.append(f"Interdit : {c.raison_interdit or 'règle Furrly'}")
    if phase in ("Pic", "Saturé"):
        raisons.append(f"Phase {phase}")
    if fin.verifie:
        if fin.marge_nette_pct < s["marge_nette_min_pct"]:
            raisons.append(f"Marge nette {fin.marge_nette_pct} % < {s['marge_nette_min_pct']} %")
        if fin.roas_rentabilite > s["roas_max"]:
            raisons.append(f"ROAS de rentabilité {fin.roas_rentabilite} > {s['roas_max']}")

    r = Resultat(c, meta, fin, phase, score, detail, bool(raisons), raisons)
    r.verdict = "🟢 À LANCER" if (score >= s["verdict_lancer_score"] and fin.verifie and c.confiance != "faible") else "🟡 À SURVEILLER"
    return r


def plan_test(fin: Finances, cfg: dict) -> dict:
    """Plan de test chiffré à partir du CPA max."""
    cpa = fin.cpa_max_eur or 15.0
    budget = max(20, min(50, round(cpa * 1.5)))
    roas_be = fin.roas_rentabilite or cfg["finances"]["roas_objectif"]
    return {
        "budget_jour_eur": budget,
        "duree_jours": 4,
        "couper": f"Couper une pub après {round(2 * cpa)} € dépensés sans vente (2 × CPA max), "
                  f"ou CTR < 1 % après 1 500 impressions.",
        "augmenter": f"+20 % de budget toutes les 48 h si ROAS > {round(1.3 * roas_be, 2)} "
                     f"(1,3 × ROAS de rentabilité).",
        "structure": "1 campagne CBO/ABO, 3 publicités (une par angle), large audience FR 25-55 ans + centres d'intérêt.",
    }
