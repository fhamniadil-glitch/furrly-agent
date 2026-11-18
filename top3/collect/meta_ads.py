"""Bibliothèque publicitaire Meta via l'API Graph officielle (endpoint ads_archive).

Signal n°1 : durée de diffusion, variantes (= budget qui monte), annonceurs, nouveaux annonceurs.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

import requests

log = logging.getLogger("top3.meta")

CHAMPS = ",".join([
    "id", "page_id", "page_name", "ad_delivery_start_time", "ad_delivery_stop_time",
    "ad_creative_bodies", "ad_creative_link_titles", "ad_snapshot_url", "eu_total_reach",
])


class MetaIndisponible(Exception):
    pass


def _norm(txt: str) -> str:
    return re.sub(r"\W+", " ", (txt or "").lower()).strip()[:80]


class MetaAdLibrary:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = os.getenv("META_ACCESS_TOKEN", "").strip()
        self.base = f"https://graph.facebook.com/{cfg['version_graph']}/ads_archive"
        self.disponible = bool(self.token)
        self.erreur: str | None = None if self.token else "META_ACCESS_TOKEN absent (repli sur la recherche web)"

    def _get(self, params: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        for essai in range(3):
            try:
                r = requests.get(self.base, params=params, headers=headers, timeout=30)
            except requests.RequestException as e:
                if essai == 2:
                    raise MetaIndisponible(f"réseau : {e}")
                time.sleep(2 ** essai)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503) and essai < 2:
                time.sleep(5 * (essai + 1))
                continue
            try:
                msg = r.json().get("error", {}).get("message", r.text[:200])
            except ValueError:
                msg = r.text[:200]
            raise MetaIndisponible(f"HTTP {r.status_code} : {msg}")
        raise MetaIndisponible("échec après 3 tentatives")

    def analyser(self, mot_cle: str) -> dict | None:
        """Retourne les KPIs Meta d'un mot-clé, ou None si l'API est indisponible."""
        if not self.disponible:
            return None
        params = {
            "search_terms": mot_cle,
            "ad_reached_countries": json.dumps(self.cfg["pays"]),
            "ad_active_status": "ACTIVE",
            "ad_type": "ALL",
            "fields": CHAMPS,
            "limit": 100,
        }
        pubs: list[dict] = []
        try:
            data = self._get(params)
            for _ in range(self.cfg["pages_max"]):
                pubs.extend(data.get("data", []))
                suivant = data.get("paging", {}).get("next")
                if not suivant:
                    break
                time.sleep(self.cfg["delai_requete_s"])
                r = requests.get(suivant, headers={"Authorization": f"Bearer {self.token}"} if self.token else {}, timeout=30)
                if r.status_code != 200:
                    break
                data = r.json()
        except MetaIndisponible as e:
            self.disponible = False
            self.erreur = str(e)
            log.warning("API Meta indisponible → repli web_search. %s", e)
            return None
        time.sleep(self.cfg["delai_requete_s"])
        return self._kpis(mot_cle, pubs)

    @staticmethod
    def _kpis(mot_cle: str, pubs: list[dict]) -> dict:
        now = datetime.now(timezone.utc)
        jours: list[int] = []
        groupes: dict[tuple, list[int]] = defaultdict(list)
        reach_total = 0
        for p in pubs:
            try:
                d = datetime.fromisoformat(p["ad_delivery_start_time"].replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                continue
            j = max(0, (now - d).days)
            jours.append(j)
            pid = p.get("page_id", "?")
            corps = (p.get("ad_creative_bodies") or [""])[0]
            groupes[(pid, _norm(corps))].append(j)
            try:
                reach_total += int(p.get("eu_total_reach") or 0)
            except (TypeError, ValueError):
                pass
        # ancienneté d'un annonceur = sa pub la plus ancienne
        anciennete: dict[str, int] = defaultdict(int)
        for (pid, _), js in groupes.items():
            anciennete[pid] = max(anciennete[pid], max(js))
        gagnantes = [
            {"page": pid, "variantes": len(js), "jours": max(js)}
            for (pid, _), js in groupes.items() if max(js) >= 21 and len(js) >= 2
        ]
        gagnantes.sort(key=lambda g: (g["jours"], g["variantes"]), reverse=True)
        noms = {p.get("page_id"): p.get("page_name") for p in pubs}
        for g in gagnantes:
            g["page"] = noms.get(g["page"], g["page"])
        return {
            "mot_cle": mot_cle,
            "date": now.date().isoformat(),
            "pubs_actives": len(pubs),
            "annonceurs": len(anciennete),
            "nouveaux_annonceurs_14j": sum(1 for a in anciennete.values() if a <= 14),
            "jours_max": max(jours) if jours else 0,
            "jours_median": int(median(jours)) if jours else 0,
            "variantes_max": max((len(v) for v in groupes.values()), default=0),
            "pubs_gagnantes": len(gagnantes),
            "top_gagnantes": gagnantes[:3],
            "eu_total_reach": reach_total,
            "plafond_atteint": len(pubs) >= 100,
        }
