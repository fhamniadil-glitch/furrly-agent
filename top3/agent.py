"""Agent Claude : 1) recherche web plafonnée  2) sortie JSON validée par pydantic."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date

import anthropic
from pydantic import ValidationError

from models import SortieIA

log = logging.getLogger("top3.agent")
BETA_FALLBACK = "server-side-fallback-2026-07-01"


class BudgetDepasse(Exception):
    pass


@dataclass
class Compteur:
    """Coût de l'exécution, affiché dans le rapport."""
    prix_in: float
    prix_out: float
    prix_search: float
    budget: float
    tokens_in: int = 0
    tokens_out: int = 0
    recherches: int = 0
    lectures: int = 0
    appels: list[str] = field(default_factory=list)

    def ajouter(self, usage, etiquette: str) -> None:
        tin = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        self.tokens_in += tin
        self.tokens_out += usage.output_tokens or 0
        stu = getattr(usage, "server_tool_use", None)
        if stu:
            self.recherches += getattr(stu, "web_search_requests", 0) or 0
            self.lectures += getattr(stu, "web_fetch_requests", 0) or 0
        self.appels.append(f"{etiquette}: {tin} in / {usage.output_tokens} out")
        log.info("Coût cumulé : %.3f $ (%s)", self.cout, etiquette)

    @property
    def cout(self) -> float:
        return (self.tokens_in * self.prix_in + self.tokens_out * self.prix_out) / 1e6 \
            + self.recherches * self.prix_search


SYSTEME = """Tu es le trio n°1 mondial : chasseur de produits dropshipping, media buyer Meta/TikTok et \
directeur commercial e-commerce. Tu travailles pour Furrly (https://furrlyrex.fr), boutique Shopify en \
dropshipping, marché FRANCE uniquement : équipement pour chiens actifs et sportifs (Malinois, Bergers) — \
confort, sécurité, éducation, canicross. Chiens uniquement.

Mission : détecter les produits pour chien EN PLEINE EXPANSION, AVANT la saturation (phases Émergent ou \
Croissance), prouvés par des KPIs et par la durée de diffusion des pubs.

RÈGLE ABSOLUE : ne JAMAIS inventer un chiffre. Chaque chiffre a une source (site/URL) et une date. \
Si une donnée manque, écris exactement « non vérifié ».

Fournisseurs : CJ Dropshipping (ne pas visiter le site, donner seulement des mots-clés de recherche) et \
AliExpress en secours. Prix de vente visé 20-55 € TTC, livraison offerte."""


def _consigne_recherche(cfg: dict, catalogue: list[dict], deja_vus: dict[str, str], jour: date,
                        meta_ok: bool) -> str:
    titres = "\n".join(f"- {p['titre']} ({p['prix']} €)" for p in catalogue[:150]) or "- (catalogue illisible)"
    vus = "\n".join(f"- {k} : {n}" for k, n in list(deja_vus.items())[:80]) or "- (aucun)"
    interdits = "\n".join(f"- {i}" for i in cfg["interdits"])
    n = cfg["ia"]["candidats"]
    meta_txt = ("Les données de la bibliothèque publicitaire Meta seront ajoutées par l'API officielle : "
                "concentre-toi sur les autres sources." if meta_ok else
                "L'API Meta n'est PAS disponible : estime la durée et l'intensité des pubs via la recherche web "
                "(articles, outils espions publics, TikTok Creative Center, pages Facebook Ad Library indexées). "
                "Marque « non vérifié » ce que tu ne peux pas sourcer.")
    return f"""Date du jour : {jour.isoformat()} ({jour.strftime('%A')}).

## Produits DÉJÀ au catalogue Furrly (à EXCLURE, mais à utiliser pour la synergie/panier)
{titres}

## Produits déjà suivis par l'agent (réutilise EXACTEMENT la même clé si tu retrouves l'un d'eux)
{vus}

## Interdits (éliminatoires)
{interdits}

## Ta recherche (web_search et web_fetch, budget limité : sois efficace)
Trouve {n} produits candidats pour chien, cohérents avec Furrly, et pour CHACUN collecte :
A. Pubs : depuis quand elles tournent, nombre de variantes, nombre d'annonceurs, nouveaux annonceurs. {meta_txt}
   TikTok Creative Center (Top Ads / Top Products) : vues, likes, partages, durée dans le classement.
B. Demande : Google Trends France (% sur 30 j et 90 j, vs an dernier), Amazon.fr Movers & Shakers / \
classement des ventes / rythme des avis, hashtags TikTok/Instagram (vues récentes, ratio partages/vues).
C. Rentabilité : prix fournisseur réel (AliExpress ou CJ via résultats de recherche), prix des concurrents FR.
D. Concurrence et risques : faiblesses des concurrents tirées des avis 1-3 étoiles (Amazon, AliExpress), \
SAV, retours, tailles, délai 8-15 j, saisonnalité, conformité.
Trouve aussi pour chaque produit une URL d'IMAGE réelle (fichier .jpg/.png/.webp d'une fiche produit) et un lien source.

En plus :
- Produits du catalogue Furrly qui semblent passer en phase Pic ou Saturé (alerte).
- Événements des 4 à 6 prochaines semaines (Noël, soldes, etc.) et produits chien à préparer.
{"- C'est LUNDI : bilan de la semaine (tendances de fond du marché chien sportif en France)." if jour.weekday() == 0 else ""}

Rends un dossier de recherche détaillé en français, produit par produit, avec pour chaque chiffre : \
valeur, source (URL), date. Écris « non vérifié » quand c'est le cas."""


def _consigne_structuration(notes: str, jour: date) -> str:
    return f"""Voici ton dossier de recherche du {jour.isoformat()} :

<dossier>
{notes}
</dossier>

Transforme-le en JSON conforme au schéma. Règles :
- Ne mets QUE des chiffres présents dans le dossier ; sinon « non vérifié » (KPI) ou null (champ numérique).
- prix_fournisseur_usd : prix d'achat constaté (convertis en $ si besoin), sinon null.
- kpis : 6 à 10 KPIs par produit (pubs, demande, prix, avis…), chacun avec source et date.
- cle : identifiant court en minuscules avec tirets ; réutilise la clé existante si le produit était déjà suivi.
- interdit = true si le produit tombe dans un interdit Furrly.
- angles : exactement 3 (problème, émotion, preuve). accroches_3s : exactement 3, réalisables SANS tournage \
(UGC générée par IA, vidéos du fournisseur, texte animé).
- pourquoi_maintenant : 2 lignes max, chiffres à l'appui.
- complement_catalogue : un produit EXISTANT du catalogue Furrly à associer (bundle / panier).
- bilan_semaine : seulement si c'est lundi, sinon null."""


class Agent:
    def __init__(self, cfg: dict, compteur: Compteur):
        self.cfg = cfg["ia"]
        self.racine = cfg
        self.c = compteur
        # base_url explicite : on parle toujours à l'API Anthropic officielle
        self.client = anthropic.Anthropic(base_url="https://api.anthropic.com", max_retries=4, timeout=900)
        self.fallbacks = self.cfg.get("fallbacks", True)

    def _verifier_budget(self, marge: float = 0.0) -> None:
        if self.c.cout + marge > self.c.budget:
            raise BudgetDepasse(f"Plafond {self.c.budget} $ atteint ({self.c.cout:.2f} $)")

    def _stream(self, **kw):
        """Appel en streaming, avec modèle de secours (fallbacks) si activé."""
        if self.fallbacks:
            try:
                with self.client.beta.messages.stream(betas=[BETA_FALLBACK], fallbacks="default", **kw) as s:
                    return s.get_final_message()
            except anthropic.BadRequestError as e:
                log.warning("Fallbacks refusés (%s) → appel standard", e.message[:120])
                self.fallbacks = False
        with self.client.beta.messages.stream(**kw) as s:
            return s.get_final_message()

    def rechercher(self, catalogue: list[dict], deja_vus: dict[str, str], jour: date, meta_ok: bool) -> str:
        tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": self.cfg["recherches_web_max"],
             "user_location": {"type": "approximate", "country": "FR", "timezone": "Europe/Paris"}},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": self.cfg["lectures_web_max"],
             "blocked_domains": ["cjdropshipping.com"]},
        ]
        messages = [{"role": "user", "content": _consigne_recherche(self.racine, catalogue, deja_vus, jour, meta_ok)}]
        textes: list[str] = []
        for tour in range(6):  # reprises pause_turn plafonnées
            self._verifier_budget()
            rep = self._stream(model=self.cfg["modele"], max_tokens=32000, system=SYSTEME, tools=tools,
                               output_config={"effort": self.cfg["effort"]}, messages=messages)
            self.c.ajouter(rep.usage, f"recherche #{tour + 1}")
            textes += [b.text for b in rep.content if b.type == "text"]
            if rep.stop_reason == "refusal":
                raise RuntimeError("Requête refusée par le modèle")
            if rep.stop_reason != "pause_turn":
                break
            if self.c.cout > 0.7 * self.c.budget:
                log.warning("70 %% du budget atteint : on arrête la recherche ici")
                break
            messages = [messages[0], {"role": "assistant", "content": rep.content}]
        notes = "\n".join(textes).strip()
        if len(notes) < 500:
            raise RuntimeError("Dossier de recherche vide ou trop court")
        log.info("Dossier de recherche : %d caractères, %d recherches, %d lectures",
                 len(notes), self.c.recherches, self.c.lectures)
        return notes

    def structurer(self, notes: str, jour: date) -> SortieIA:
        derniere_erreur = None
        for essai in range(2):
            self._verifier_budget(marge=0.15)
            try:
                rep = self.client.messages.parse(
                    model=self.cfg["modele"], max_tokens=16000, system=SYSTEME,
                    messages=[{"role": "user", "content": _consigne_structuration(notes, jour)}],
                    output_format=SortieIA,
                )
                self.c.ajouter(rep.usage, f"structuration #{essai + 1}")
                if rep.parsed_output is None:
                    raise ValueError(f"sortie vide (stop_reason={rep.stop_reason})")
                return rep.parsed_output
            except (ValidationError, ValueError) as e:
                derniere_erreur = e
                log.warning("JSON invalide, nouvelle tentative : %s", str(e)[:200])
                time.sleep(2)
        raise RuntimeError(f"Sortie IA invalide après 2 essais : {derniere_erreur}")


# ======================================================================
#  Moteur GRATUIT : Google Gemini (niveau gratuit AI Studio + recherche Google)
# ======================================================================
class AgentGemini:
    """Même interface que Agent, mais avec Gemini (0 € dans les limites du niveau gratuit)."""

    def __init__(self, cfg: dict, compteur: Compteur):
        from google import genai  # import local : dépendance utile seulement pour ce moteur
        from google.genai import types
        self.types = types
        self.cfg = cfg["ia"]
        self.racine = cfg
        self.c = compteur
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    def _appel(self, etiquette: str, contenu: str, config):
        for essai in range(4):
            try:
                rep = self.client.models.generate_content(model=self.cfg["modele_gemini"], contents=contenu, config=config)
                u = rep.usage_metadata
                self.c.tokens_in += (u.prompt_token_count or 0) if u else 0
                self.c.tokens_out += ((u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
                self.c.appels.append(etiquette)
                return rep
            except Exception as e:  # 429 (quota/minute) ou 5xx : on patiente puis on réessaie
                log.warning("Gemini %s (essai %d/4) : %s", etiquette, essai + 1, str(e)[:200])
                if essai == 3:
                    raise
                time.sleep(20 * (essai + 1))

    def rechercher(self, catalogue: list[dict], deja_vus: dict[str, str], jour: date, meta_ok: bool) -> str:
        t = self.types
        config = t.GenerateContentConfig(
            system_instruction=SYSTEME,
            tools=[t.Tool(google_search=t.GoogleSearch()), t.Tool(url_context=t.UrlContext())],
        )
        rep = self._appel("recherche", _consigne_recherche(self.racine, catalogue, deja_vus, jour, meta_ok), config)
        notes = (rep.text or "").strip()
        # sources Google réellement consultées
        try:
            gm = rep.candidates[0].grounding_metadata
            self.c.recherches += len(gm.web_search_queries or [])
            sources = [f"- {ch.web.title} : {ch.web.uri}" for ch in (gm.grounding_chunks or []) if ch.web]
            if sources:
                notes += "\n\nSources consultées :\n" + "\n".join(sources[:60])
        except (AttributeError, IndexError, TypeError):
            pass
        if len(notes) < 500:
            raise RuntimeError("Dossier de recherche vide ou trop court")
        log.info("Dossier de recherche Gemini : %d caractères, %d recherches Google", len(notes), self.c.recherches)
        return notes

    def structurer(self, notes: str, jour: date) -> SortieIA:
        config = self.types.GenerateContentConfig(
            system_instruction=SYSTEME,
            response_mime_type="application/json",
            response_json_schema=SortieIA.model_json_schema(),
        )
        derniere = None
        for essai in range(2):
            rep = self._appel(f"structuration #{essai + 1}", _consigne_structuration(notes, jour), config)
            try:
                return SortieIA.model_validate_json(rep.text or "")
            except ValidationError as e:
                derniere = e
                log.warning("JSON Gemini invalide, nouvelle tentative : %s", str(e)[:300])
        raise RuntimeError(f"Sortie IA invalide après 2 essais : {derniere}")


def creer_agent(cfg: dict, compteur: Compteur):
    """Choix du moteur dans config.yaml → ia.fournisseur : gemini (gratuit) ou anthropic (payant)."""
    if cfg["ia"].get("fournisseur", "gemini") == "anthropic":
        return Agent(cfg, compteur)
    return AgentGemini(cfg, compteur)
