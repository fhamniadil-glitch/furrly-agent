"""Lecture du catalogue Furrly (products.json de Shopify) pour exclure les produits déjà vendus."""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("top3.catalogue")
UA = {"User-Agent": "Mozilla/5.0 (FurrlyTop3/1.0)"}


def lire_catalogue(url: str, pages_max: int = 5) -> list[dict]:
    produits: list[dict] = []
    for page in range(1, pages_max + 1):
        try:
            r = requests.get(url, params={"limit": 250, "page": page}, headers=UA, timeout=20)
            r.raise_for_status()
            lot = r.json().get("products", [])
        except Exception as e:  # le rapport continue même si le site ne répond pas
            log.warning("Catalogue illisible (page %s) : %s", page, e)
            break
        if not lot:
            break
        for p in lot:
            prix = None
            if p.get("variants"):
                try:
                    prix = float(p["variants"][0].get("price"))
                except (TypeError, ValueError):
                    pass
            produits.append({
                "titre": p.get("title", ""),
                "type": p.get("product_type", ""),
                "tags": p.get("tags", []),
                "prix": prix,
                "handle": p.get("handle", ""),
            })
    log.info("Catalogue Furrly : %d produits", len(produits))
    return produits
