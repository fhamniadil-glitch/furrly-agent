"""Mémoire SQLite : produits, KPIs datés, scores, phases, rapports envoyés."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS produits (
    cle TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    premiere_vue TEXT NOT NULL,
    derniere_proposition TEXT,
    score_proposition REAL
);
CREATE TABLE IF NOT EXISTS releves (
    jour TEXT NOT NULL,
    cle TEXT NOT NULL,
    score REAL,
    phase TEXT,
    kpis TEXT,
    meta TEXT,
    PRIMARY KEY (jour, cle)
);
CREATE TABLE IF NOT EXISTS envois (
    jour TEXT PRIMARY KEY,
    cout_usd REAL,
    fichier TEXT
);
"""


class Memoire:
    def __init__(self, chemin: Path):
        self.db = sqlite3.connect(chemin)
        self.db.executescript(SCHEMA)

    # --- envois ---
    def deja_envoye(self, jour: date) -> bool:
        return self.db.execute("SELECT 1 FROM envois WHERE jour=?", (jour.isoformat(),)).fetchone() is not None

    def marquer_envoye(self, jour: date, cout: float, fichier: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO envois VALUES (?,?,?)", (jour.isoformat(), cout, fichier))
        self.db.commit()

    # --- produits ---
    def cles_connues(self) -> dict[str, str]:
        return dict(self.db.execute("SELECT cle, nom FROM produits"))

    def enregistrer_releve(self, jour: date, cle: str, nom: str, score: float, phase: str, kpis: list, meta: dict | None) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO produits (cle, nom, premiere_vue) VALUES (?,?,?)", (cle, nom, jour.isoformat()))
        self.db.execute(
            "INSERT OR REPLACE INTO releves VALUES (?,?,?,?,?,?)",
            (jour.isoformat(), cle, score, phase, json.dumps(kpis, ensure_ascii=False), json.dumps(meta, ensure_ascii=False)),
        )
        self.db.commit()

    def marquer_propose(self, jour: date, cle: str, score: float) -> None:
        self.db.execute("UPDATE produits SET derniere_proposition=?, score_proposition=? WHERE cle=?",
                        (jour.isoformat(), score, cle))
        self.db.commit()

    def statut_repos(self, cle: str, score: float, jour: date, repos_jours: int, bonus: float) -> tuple[bool, str]:
        """(proposable, badge). Repos de 14 j sauf si le score gagne ≥ 10 points."""
        row = self.db.execute("SELECT derniere_proposition, score_proposition FROM produits WHERE cle=?", (cle,)).fetchone()
        if not row or not row[0]:
            return True, ""
        ecart = (jour - date.fromisoformat(row[0])).days
        if ecart >= repos_jours:
            return True, ""
        if score - (row[1] or 0) >= bonus:
            return True, "📈 en hausse"
        return False, ""

    def score_a(self, cle: str, jour: date) -> tuple[float | None, str | None]:
        row = self.db.execute(
            "SELECT score, phase FROM releves WHERE cle=? AND jour<=? ORDER BY jour DESC LIMIT 1",
            (cle, jour.isoformat())).fetchone()
        return (row[0], row[1]) if row else (None, None)

    # --- rubriques du rapport ---
    def watchlist(self, jour: date, exclure: set[str]) -> list[dict]:
        debut = (jour - timedelta(days=7)).isoformat()
        cles = [r[0] for r in self.db.execute(
            "SELECT DISTINCT cle FROM releves WHERE jour>=? AND jour<?", (debut, jour.isoformat()))]
        lignes = []
        for cle in cles:
            if cle in exclure:
                continue
            nom = self.db.execute("SELECT nom FROM produits WHERE cle=?", (cle,)).fetchone()[0]
            s0, ph0 = self.score_a(cle, jour)
            s1, _ = self.score_a(cle, jour - timedelta(days=1))
            s7, _ = self.score_a(cle, jour - timedelta(days=7))
            lignes.append({"nom": nom, "score": s0, "j1": s1, "j7": s7, "phase": ph0})
        lignes.sort(key=lambda l: l["score"] or 0, reverse=True)
        return lignes[:10]

    def passages_saturation(self, jour: date) -> list[dict]:
        """Produits qui passent en Pic ou Saturé aujourd'hui (alors qu'ils ne l'étaient pas avant)."""
        res = []
        for cle, phase in self.db.execute("SELECT cle, phase FROM releves WHERE jour=?", (jour.isoformat(),)).fetchall():
            if phase not in ("Pic", "Saturé"):
                continue
            avant = self.db.execute(
                "SELECT phase FROM releves WHERE cle=? AND jour<? ORDER BY jour DESC LIMIT 1",
                (cle, jour.isoformat())).fetchone()
            if avant and avant[0] not in ("Pic", "Saturé"):
                nom = self.db.execute("SELECT nom FROM produits WHERE cle=?", (cle,)).fetchone()[0]
                res.append({"produit": nom, "phase": phase, "raison": f"était {avant[0]}"})
        return res

    def bilan_semaine(self, jour: date) -> dict:
        """Ce qui monte / ce qui chute sur 7 jours."""
        evol = []
        for (cle,) in self.db.execute("SELECT DISTINCT cle FROM releves WHERE jour>=?",
                                      ((jour - timedelta(days=7)).isoformat(),)):
            s0, _ = self.score_a(cle, jour)
            s7, _ = self.score_a(cle, jour - timedelta(days=7))
            if s0 is not None and s7 is not None:
                nom = self.db.execute("SELECT nom FROM produits WHERE cle=?", (cle,)).fetchone()[0]
                evol.append((nom, round(s0 - s7, 1)))
        evol.sort(key=lambda e: e[1], reverse=True)
        return {"monte": [e for e in evol if e[1] > 0][:5], "chute": [e for e in evol[::-1] if e[1] < 0][:5]}
