# 🐕 Agent « Top 3 produits chien » — Furrly

Chaque matin à **9h00 (Paris)**, tu reçois par email les **3 produits pour chien les plus prometteurs** :
en pleine expansion, **avant la saturation**, prouvés par des KPIs (durée des pubs, Google Trends, Amazon,
TikTok), avec la fiche « prête à lancer » (prix, marge, ROAS, angles de pub, plan de test, sourcing CJ).

---

## 1. Comment ça marche (en 30 secondes)

1. **8h15** : GitHub lance l'agent (gratuit, rien à installer chez toi).
2. L'agent lit ton catalogue Furrly (pour ne pas te proposer ce que tu vends déjà).
3. L'IA (Gemini gratuit, ou Claude en option) cherche sur le web : pubs, tendances, Amazon, TikTok, prix fournisseurs, avis clients.
4. Si tu as un jeton Meta, la **bibliothèque publicitaire Meta** donne les vrais chiffres de pubs (sinon : recherche web).
5. Python calcule **prix conseillé, marge, ROAS de rentabilité, CPA max, score /100, phase**.
6. Les produits interdits, saturés ou pas assez rentables sont éliminés. Il reste le **TOP 3**.
7. **9h00** : email HTML (lisible sur mobile) + archive dans `rapports/`.

Aucun chiffre n'est inventé : si une donnée manque, le rapport écrit **« non vérifié »**.

---

## 2. Installation pas à pas (15 min, une seule fois)

### Étape 1 — Clé Gemini GRATUITE (obligatoire)
1. Va sur **aistudio.google.com/apikey** (compte Google) → *Create API key*.
2. Copie la clé (`AIza…`). Aucune carte bancaire : le niveau gratuit suffit (1 rapport/jour).
   (Option payante plus précise : Claude — mettre `ia.fournisseur: anthropic` + secret `ANTHROPIC_API_KEY`.)

### Étape 2 — Mot de passe email OVH (obligatoire)
Le mot de passe de la boîte **contact@furrlyrex.fr** (espace client OVH → Emails).

### Étape 3 — Ajouter les secrets dans GitHub
Sur GitHub : ton dépôt → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

| Nom du secret | Valeur | Obligatoire ? |
|---|---|---|
| `GEMINI_API_KEY` | ta clé gratuite `AIza…` | ✅ oui |
| `ANTHROPIC_API_KEY` | clé Claude `sk-ant-…` (payant) | facultatif |
| `SMTP_USER` | `contact@furrlyrex.fr` | ✅ oui |
| `SMTP_PASSWORD` | mot de passe de la boîte email | ✅ oui |
| `EMAIL_TO` | l'adresse qui reçoit le rapport (sinon contact@furrlyrex.fr) | facultatif |
| `META_ACCESS_TOKEN` | jeton Meta (voir § 5) | facultatif |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | bot Telegram | facultatif |

⚠️ Ne mets **jamais** une clé dans un fichier du dépôt ou dans un chat.

### Étape 4 — Faire un test
GitHub → onglet **Actions** → **FURRLY Top 3 produits** → **Run workflow** → mode **test** → *Run*.
Au bout de 5-10 min, ouvre l'exécution → en bas, **Artifacts** → `rapport-top3` → télécharge et ouvre le `.html`.
Le mode **test** n'envoie rien et ne modifie pas la mémoire.

### Étape 5 — C'est tout
Dès que le workflow est sur la branche principale (`main`), il tourne **tous les matins** tout seul.

---

## 3. Tout régler sans toucher au code : `config.yaml`

| Je veux… | Je modifie… |
|---|---|
| Changer l'heure d'envoi | `envoi.heure` (et les 2 crons dans `.github/workflows/top3.yml`) |
| Changer les pondérations du score | `ponderations` (total = 100) |
| Être plus/moins exigeant | `seuils` (marge min, ROAS max, nb d'annonceurs…) |
| Changer les frais / prix cible | `finances` |
| Ajouter un interdit | `interdits` |
| Dépenser moins | `ia.recherches_web_max`, `ia.candidats`, `ia.budget_max_usd` |
| Changer de moteur / modèle IA | `ia.fournisseur`, `ia.modele_gemini`, `ia.modele` |
| Activer Telegram | `envoi.telegram: true` + secrets Telegram |

---

## 4. Lire le rapport

- **Phase** : Émergent (idéal) → Croissance (bon) → Pic (trop tard) → Saturé (fuir). Seuls Émergent/Croissance sont proposés.
- **🟢 À LANCER** : score ≥ 70, prix vérifié, confiance correcte. **🟡 À SURVEILLER** : prometteur mais une donnée manque.
- **ROAS de rentabilité** = prix TTC ÷ marge nette. En dessous de ce ROAS, tu perds de l'argent. Objectif ≤ 2,5.
- **CPA max** = marge nette = ce que tu peux payer au maximum en pub pour 1 vente.
- **📈 en hausse** : produit déjà proposé il y a moins de 14 jours mais dont le score a gagné ≥ 10 points.
- **Watchlist / Alertes / Calendrier / Bilan du lundi** : suivi automatique grâce à la mémoire `furrly.db`.

### Calcul des finances
```
Coût rendu    = prix fournisseur + livraison (5,70 $) + droit UE (3 €)
TVA (IOSS)    = prix TTC − prix TTC ÷ 1,2
Frais paiement= 2,9 % + 0,25 €
Marge nette   = prix TTC − TVA − frais paiement − coût rendu
```

---

## 5. Bibliothèque publicitaire Meta (facultatif)

Sans jeton, l'agent estime la durée des pubs via la recherche web (moins précis, signalé dans le rapport).
Pour les vrais chiffres (jours en ligne, variantes, annonceurs, couverture UE), Meta exige une **vérification
d'identité** (facebook.com/ID), puis : developers.facebook.com → créer une app → *Graph API Explorer* →
*Generate Access Token* → prolonger à 60 jours via *Access Token Debugger*. Mets le jeton dans le secret
`META_ACCESS_TOKEN` et renouvelle-le tous les 2 mois.

---

## 6. Lancer en local (facultatif)

```bash
cd top3
pip install -r requirements.txt
cp .env.example .env      # puis remplis .env
python main.py --dry-run  # affiche le rapport sans l'envoyer
```

## 7. En cas de problème
- **Pas d'email** : onglet *Actions* → ouvre la dernière exécution → lis les journaux (en français).
- **« hors créneau »** : normal, un des 2 horaires est toujours hors créneau (été/hiver).
- **Échec** : l'agent t'envoie un email « ⚠️ Top 3 Furrly — échec » avec la raison.
- **Coût** : 0 € avec Gemini (niveau gratuit). Avec Claude : affiché en bas du rapport, plafond `ia.budget_max_usd`.
- **Quota Gemini dépassé (erreur 429)** : l'agent réessaie ; si ça persiste, relance plus tard.
