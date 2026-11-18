"""Génération du rapport HTML (email lisible sur mobile) + archive dans /rapports."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from jinja2 import Environment, select_autoescape

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def date_fr(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"


def eur(x) -> str:
    if x is None:
        return "non vérifié"
    return f"{x:,.2f} €".replace(",", " ").replace(".", ",")


def evenements_a_venir(cfg: dict, jour: date) -> list[dict]:
    res = []
    for ev in cfg["calendrier"]:
        mm, jj = map(int, ev["date"].split("-"))
        for annee in (jour.year, jour.year + 1):
            d = date(annee, mm, jj)
            if jour <= d <= jour + timedelta(weeks=6):
                res.append({"date": d, "nom": ev["nom"], "dans": (d - jour).days})
    return sorted(res, key=lambda e: e["date"])


GABARIT = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ objet }}</title></head>
<body style="margin:0;background:#f3f1ec;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1d1d1b;">
<div style="max-width:640px;margin:0 auto;padding:12px;">

<div style="background:#1d1d1b;color:#fff;border-radius:12px;padding:18px 16px;">
  <div style="font-size:13px;opacity:.7;">FURRLY · Chasseur de produits</div>
  <div style="font-size:22px;font-weight:700;margin-top:4px;">🐕 Top 3 du {{ date_fr }}</div>
  <div style="font-size:13px;opacity:.8;margin-top:6px;">{{ nb_analyses }} produits analysés · {{ top|length }} retenus · coût {{ "%.2f"|format(cout) }} $</div>
</div>

{% for a in avertissements %}
<div style="background:#fff4d6;border-left:4px solid #e0a100;border-radius:8px;padding:10px 12px;margin-top:10px;font-size:13px;">⚠️ {{ a }}</div>
{% endfor %}

{% if not top %}
<div style="background:#fff;border-radius:12px;padding:16px;margin-top:12px;">Aucun produit ne passe les filtres aujourd'hui (phase, marge, ROAS, interdits). Mieux vaut ne rien lancer que lancer un produit saturé.</div>
{% endif %}

{% for r in top %}{% set c = r.candidat %}{% set f = r.finances %}
<div style="background:#fff;border-radius:12px;margin-top:14px;overflow:hidden;border:1px solid #e6e2d8;">
  {% if c.image_url %}<img src="{{ c.image_url }}" alt="{{ c.nom }}" style="width:100%;max-height:320px;object-fit:cover;display:block;background:#eee;">{% endif %}
  <div style="padding:14px 16px;">
    <div style="font-size:12px;color:#7a7568;">#{{ loop.index }} · Phase <b>{{ r.phase }}</b> · Confiance {{ c.confiance }} {% if r.badge %}· <b>{{ r.badge }}</b>{% endif %}</div>
    <div style="font-size:19px;font-weight:700;margin:4px 0;">{{ c.nom }}</div>
    <div style="font-size:16px;font-weight:700;">{{ r.verdict }} — {{ r.score }}/100</div>
    {% if c.lien_source %}<div style="font-size:12px;margin-top:4px;"><a href="{{ c.lien_source }}" style="color:#b5541c;">Lien source</a>{% if not c.image_url %} · photo : non vérifié{% endif %}</div>{% endif %}

    <div style="background:#f7f5f0;border-radius:8px;padding:10px;margin-top:10px;font-size:14px;"><b>Pourquoi maintenant :</b> {{ c.pourquoi_maintenant }}<br><span style="color:#7a7568;font-size:13px;">⏳ Avant saturation : {{ c.duree_avant_saturation }}</span></div>

    <div style="font-weight:700;margin-top:14px;">📊 Score détaillé</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:4px;">
    {% for k, lib, maxi in criteres %}<tr><td style="padding:3px 0;">{{ lib }}</td><td style="text-align:right;white-space:nowrap;"><b>{{ r.detail[k] }}</b> / {{ maxi }}</td></tr>{% endfor %}
    </table>

    <div style="font-weight:700;margin-top:14px;">💶 Finances</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:4px;">
      <tr><td>Prix d'achat</td><td style="text-align:right;">{{ eur(f.prix_achat_eur) }}{% if c.prix_fournisseur_usd %} ({{ c.prix_fournisseur_usd }} $){% endif %}</td></tr>
      <tr><td>Coût rendu (achat + livraison + droit UE)</td><td style="text-align:right;">{{ eur(f.cout_rendu_eur) }}</td></tr>
      <tr><td><b>Prix conseillé TTC</b></td><td style="text-align:right;"><b>{{ eur(f.prix_conseille_eur) }}</b></td></tr>
      <tr><td>TVA 20 % (IOSS) + frais paiement</td><td style="text-align:right;">{{ eur(f.tva_eur) }} + {{ eur(f.frais_paiement_eur) }}</td></tr>
      <tr><td><b>Marge nette</b></td><td style="text-align:right;"><b>{{ eur(f.marge_nette_eur) }}{% if f.marge_nette_pct is not none %} ({{ f.marge_nette_pct }} %){% endif %}</b></td></tr>
      <tr><td>ROAS de rentabilité</td><td style="text-align:right;">{{ f.roas_rentabilite if f.roas_rentabilite is not none else "non vérifié" }}</td></tr>
      <tr><td>CPA maximum</td><td style="text-align:right;">{{ eur(f.cpa_max_eur) }}</td></tr>
      {% if c.prix_concurrents_eur %}<tr><td>Prix concurrents FR</td><td style="text-align:right;">{{ c.prix_concurrents_eur|join(" · ") }} €</td></tr>{% endif %}
    </table>

    <div style="font-weight:700;margin-top:14px;">🔎 KPIs</div>
    <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:4px;">
      <tr style="color:#7a7568;"><td>KPI</td><td>Valeur</td><td>Source · date</td></tr>
      {% if r.meta %}
      <tr style="border-top:1px solid #eee;"><td>Pubs Meta actives (UE)</td><td><b>{{ r.meta.pubs_actives }}{% if r.meta.plafond_atteint %}+{% endif %}</b></td><td>API Meta « {{ r.meta.mot_cle }} » · {{ r.meta.date }}</td></tr>
      <tr style="border-top:1px solid #eee;"><td>Annonceurs / nouveaux 14 j</td><td><b>{{ r.meta.annonceurs }} / {{ r.meta.nouveaux_annonceurs_14j }}</b></td><td>API Meta · {{ r.meta.date }}</td></tr>
      <tr style="border-top:1px solid #eee;"><td>Durée max / médiane</td><td><b>{{ r.meta.jours_max }} j / {{ r.meta.jours_median }} j</b></td><td>API Meta · {{ r.meta.date }}</td></tr>
      <tr style="border-top:1px solid #eee;"><td>Variantes max · pubs gagnantes (≥21 j, ≥2 var.)</td><td><b>{{ r.meta.variantes_max }} · {{ r.meta.pubs_gagnantes }}</b></td><td>API Meta · {{ r.meta.date }}</td></tr>
      {% if r.meta.eu_total_reach %}<tr style="border-top:1px solid #eee;"><td>Couverture UE</td><td><b>{{ "{:,}".format(r.meta.eu_total_reach).replace(",", " ") }}</b></td><td>API Meta · {{ r.meta.date }}</td></tr>{% endif %}
      {% endif %}
      {% for k in c.kpis %}<tr style="border-top:1px solid #eee;"><td>{{ k.nom }}</td><td><b>{{ k.valeur }}</b></td><td>{{ k.source }} · {{ k.date }}</td></tr>{% endfor %}
    </table>

    <div style="font-weight:700;margin-top:14px;">🛒 Offre commerciale</div>
    <ul style="margin:4px 0;padding-left:18px;font-size:13px;">
      <li><b>Lot / bundle :</b> {{ c.bundle }}</li>
      <li><b>Montée en gamme :</b> {{ c.montee_en_gamme }}</li>
      <li><b>Complément Furrly :</b> {{ c.complement_catalogue }}</li>
    </ul>

    <div style="font-weight:700;margin-top:14px;">📣 Marketing — canal conseillé : {{ c.canal }}</div>
    <div style="font-size:13px;margin-top:4px;"><b>Persona :</b> {{ c.persona }}</div>
    <div style="font-size:13px;margin-top:4px;"><b>Intérêts Meta :</b> {{ c.interets_meta|join(", ") }}<br><b>Intérêts TikTok :</b> {{ c.interets_tiktok|join(", ") }}</div>
    <ul style="margin:6px 0;padding-left:18px;font-size:13px;">{% for a in c.angles %}<li><b>Angle {{ a.type }} :</b> {{ a.texte }}</li>{% endfor %}</ul>
    <div style="font-size:13px;"><b>Accroches vidéo 3 s (sans tournage) :</b></div>
    <ol style="margin:4px 0;padding-left:18px;font-size:13px;">{% for h in c.accroches_3s %}<li>{{ h }}</li>{% endfor %}</ol>

    <div style="font-weight:700;margin-top:14px;">🧪 Plan de test</div>
    <ul style="margin:4px 0;padding-left:18px;font-size:13px;">
      <li><b>Budget :</b> {{ r.plan.budget_jour_eur }} €/jour pendant {{ r.plan.duree_jours }} jours</li>
      <li><b>Structure :</b> {{ r.plan.structure }}</li>
      <li><b>Stop :</b> {{ r.plan.couper }}</li>
      <li><b>Scale :</b> {{ r.plan.augmenter }}</li>
    </ul>

    <div style="font-weight:700;margin-top:14px;">📦 Sourcing</div>
    <div style="font-size:13px;margin-top:4px;"><b>CJ Dropshipping :</b> {{ c.mots_cles_cj|join(" · ") }}<br><b>AliExpress :</b> {{ c.mots_cles_aliexpress|join(" · ") }}</div>

    <div style="font-weight:700;margin-top:14px;">⚔️ Concurrence & risques</div>
    <ul style="margin:4px 0;padding-left:18px;font-size:13px;">
      {% for x in c.faiblesses_concurrents %}<li>Faiblesse concurrent → argument : {{ x }}</li>{% endfor %}
      {% for x in c.risques %}<li>Risque : {{ x }}</li>{% endfor %}
    </ul>
  </div>
</div>
{% endfor %}

{% if watchlist %}
<div style="background:#fff;border-radius:12px;padding:14px 16px;margin-top:14px;">
  <div style="font-weight:700;">📈 Watchlist</div>
  <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:6px;">
    <tr style="color:#7a7568;"><td>Produit</td><td>Auj.</td><td>J-1</td><td>J-7</td><td>Phase</td></tr>
    {% for w in watchlist %}<tr style="border-top:1px solid #eee;"><td>{{ w.nom }}</td><td><b>{{ w.score }}</b></td><td>{{ w.j1 if w.j1 is not none else "–" }}</td><td>{{ w.j7 if w.j7 is not none else "–" }}</td><td>{{ w.phase }}</td></tr>{% endfor %}
  </table>
</div>
{% endif %}

{% if alertes %}
<div style="background:#fff;border-radius:12px;padding:14px 16px;margin-top:14px;">
  <div style="font-weight:700;">⚠️ Alertes saturation</div>
  <ul style="margin:6px 0;padding-left:18px;font-size:13px;">{% for a in alertes %}<li><b>{{ a.produit }}</b> → {{ a.phase }} : {{ a.raison }}</li>{% endfor %}</ul>
</div>
{% endif %}

<div style="background:#fff;border-radius:12px;padding:14px 16px;margin-top:14px;">
  <div style="font-weight:700;">🗓️ Calendrier (6 semaines)</div>
  <ul style="margin:6px 0;padding-left:18px;font-size:13px;">
  {% for e in evenements %}<li><b>{{ e.nom }}</b> — {{ e.date.strftime('%d/%m') }} (J-{{ e.dans }})</li>{% else %}<li>Aucun événement majeur.</li>{% endfor %}
  {% for e in calendrier_ia %}<li>{{ e.evenement }} : {{ e.produits_a_preparer|join(", ") }}</li>{% endfor %}
  </ul>
</div>

{% if lundi %}
<div style="background:#fff;border-radius:12px;padding:14px 16px;margin-top:14px;">
  <div style="font-weight:700;">📅 Bilan de la semaine</div>
  {% if bilan_ia %}<p style="font-size:13px;">{{ bilan_ia }}</p>{% endif %}
  {% if bilan.monte %}<div style="font-size:13px;">⬆️ Monte : {% for n, d in bilan.monte %}{{ n }} (+{{ d }}){{ ", " if not loop.last }}{% endfor %}</div>{% endif %}
  {% if bilan.chute %}<div style="font-size:13px;">⬇️ Chute : {% for n, d in bilan.chute %}{{ n }} ({{ d }}){{ ", " if not loop.last }}{% endfor %}</div>{% endif %}
  {% if tendances %}<ul style="font-size:13px;padding-left:18px;">{% for t in tendances %}<li>{{ t }}</li>{% endfor %}</ul>{% endif %}
</div>
{% endif %}

{% if elimines %}
<div style="background:#fff;border-radius:12px;padding:14px 16px;margin-top:14px;font-size:12px;color:#7a7568;">
  <b>Écartés aujourd'hui :</b> {% for r in elimines %}{{ r.candidat.nom }} ({{ r.raisons_elimination|join(", ") or r.raison_ecart }}){{ " · " if not loop.last }}{% endfor %}
</div>
{% endif %}

<div style="font-size:11px;color:#7a7568;text-align:center;margin:16px 0;">
  Coût de l'exécution : {{ "%.3f"|format(cout) }} $ · {{ recherches }} recherches web · {{ lectures }} pages lues · modèle {{ modele }}<br>
  « non vérifié » = donnée introuvable, jamais inventée. Généré le {{ genere }}.
</div>
</div></body></html>"""

CRITERES = [
    ("pubs", "Durée & intensité des pubs", "pubs"),
    ("demande", "Croissance de la demande", "demande"),
    ("marge", "Marge & ROAS", "marge"),
    ("viral", "Potentiel viral / effet wow", "viral"),
    ("fenetre", "Fenêtre d'opportunité", "fenetre"),
    ("adequation", "Adéquation Furrly", "adequation"),
]


def generer(ctx: dict, cfg: dict) -> str:
    env = Environment(autoescape=select_autoescape(["html"]))
    env.globals["eur"] = eur
    p = cfg["ponderations"]
    ctx = dict(ctx, criteres=[(k, lib, p[k]) for k, lib, _ in CRITERES],
               genere=datetime.now().strftime("%d/%m/%Y %H:%M"))
    return env.from_string(GABARIT).render(**ctx)
