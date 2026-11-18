"""Schémas pydantic : la sortie de l'IA est validée ici AVANT de générer le rapport."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Phase = Literal["Émergent", "Croissance", "Pic", "Saturé"]
NV = "non vérifié"


class KPI(BaseModel):
    """Un chiffre = une valeur + sa source + sa date. Jamais inventé."""
    nom: str
    valeur: str = Field(description="Valeur telle que trouvée, ou 'non vérifié'")
    source: str = Field(description="Nom du site ou URL, ou 'non vérifié'")
    date: str = Field(description="Date de la donnée AAAA-MM-JJ, ou 'non vérifié'")


class AnglePub(BaseModel):
    type: Literal["problème", "émotion", "preuve"]
    texte: str


class Candidat(BaseModel):
    cle: str = Field(description="Identifiant court et stable, ex: 'harnais-canicross-reflechissant'")
    nom: str
    image_url: Optional[str] = Field(None, description="URL d'une photo réelle du produit")
    lien_source: Optional[str] = None
    mots_cles_meta: list[str] = Field(description="2-3 mots-clés FR pour la bibliothèque pub Meta")
    mots_cles_cj: list[str]
    mots_cles_aliexpress: list[str]
    prix_fournisseur_usd: Optional[float] = Field(None, description="Prix d'achat constaté ; null si non vérifié")
    prix_concurrents_eur: list[float] = Field(default_factory=list, description="Prix TTC concurrents FR constatés")
    phase_estimee: Phase
    tendance_30j_pct: Optional[float] = None
    tendance_90j_pct: Optional[float] = None
    tendance_vs_an_dernier_pct: Optional[float] = None
    annonceurs_estimes: Optional[int] = Field(None, description="Si l'API Meta n'a rien donné")
    note_virale: int = Field(ge=0, le=10, description="Effet wow / problème montrable en vidéo")
    note_adequation: int = Field(ge=0, le=10, description="Adéquation Furrly + synergie catalogue")
    interdit: bool = False
    raison_interdit: Optional[str] = None
    kpis: list[KPI]
    pourquoi_maintenant: str = Field(description="2 lignes, chiffres à l'appui")
    duree_avant_saturation: str
    faiblesses_concurrents: list[str]
    risques: list[str]
    bundle: str
    montee_en_gamme: str
    complement_catalogue: str = Field(description="Produit du catalogue Furrly à associer")
    persona: str
    interets_meta: list[str]
    interets_tiktok: list[str]
    angles: list[AnglePub]
    accroches_3s: list[str] = Field(description="3 accroches vidéo réalisables sans tournage")
    canal: Literal["Meta", "TikTok"]
    confiance: Literal["faible", "moyenne", "élevée"]


class AlerteCatalogue(BaseModel):
    produit: str
    phase: Phase
    raison: str


class EvenementProduits(BaseModel):
    evenement: str
    produits_a_preparer: list[str]


class SortieIA(BaseModel):
    candidats: list[Candidat]
    alertes_catalogue: list[AlerteCatalogue] = Field(default_factory=list)
    calendrier: list[EvenementProduits] = Field(default_factory=list)
    bilan_semaine: Optional[str] = Field(None, description="Uniquement le lundi")
    tendances_de_fond: list[str] = Field(default_factory=list)
