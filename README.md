# Agent de publication FURRLY

Un robot gratuit qui publie **tout seul** tes posts Facebook et Instagram (TikTok en option) à l'heure prévue, 24 h/24, **sans ton PC allumé**. Il tourne sur **GitHub Actions** (gratuit) et utilise les **API officielles** de Meta et TikTok.

- Il se réveille **toutes les 30 minutes**, lit `calendar.csv` et publie les posts dont l'heure est arrivée.
- Il retient ce qui est déjà publié dans `state.json` : **jamais de doublon**.
- **Sécurité : il démarre en mode TEST.** Il n'envoie rien tant que tu n'as pas mis `DRY_RUN = false`.

Déjà chargé dans `calendar.csv` : **tes 19 Reels** (23 oct → 10 nov, 18h15, Facebook + Instagram) et **6 cartes « Rejoins la meute »** (12h30).

---

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `publisher.py` | Le moteur : lit le calendrier et publie via les API |
| `calendar.csv` | Ton planning (une ligne = un post) |
| `.github/workflows/publish.yml` | Le réveil automatique toutes les 30 min |
| `requirements.txt` | La seule dépendance (`requests`) |
| `state.json` | La mémoire des posts déjà publiés |
| `media/` | Tes visuels (à remplir, voir étape 2) |
| `responder.py` | L'agent IA qui répond aux commentaires et messages |
| `furrly_knowledge.md` | Ce que l'agent sait de FURRLY (produits, livraison, retours) |
| `.github/workflows/respond.yml` | Le réveil de l'agent de réponses toutes les 30 min |

---

## Mise en route (une seule fois, ~30 min)

### 1. Créer le dépôt GitHub
1. Crée un compte gratuit sur **github.com**.
2. **New repository** → nom : `furrly-agent` → **Public** (voir pourquoi à l'étape 3) → Create.
3. **Add file → Upload files** : glisse **tout le contenu** du dossier `agent` (y compris le dossier `.github`). Commit.

> Si le dossier `.github` ne passe pas en glisser-déposer (dossier caché), crée le fichier à la main : **Add file → Create new file**, nomme-le `.github/workflows/publish.yml` et colle le contenu du fichier.

### 2. Ajouter les visuels dans `media/`
Instagram **n'accepte que le JPEG**. Pour les 6 cartes :
1. Ouvre chaque `furrly-carte-0X-1x1.png` (dossier `export/` de la session) dans **Paint** → **Fichier → Enregistrer sous → JPEG**.
2. Nomme-les exactement `furrly-carte-01-1x1.jpg` … `furrly-carte-06-1x1.jpg`.
3. Dépose-les dans le dossier `media/` du dépôt.

Les 19 Reels n'ont besoin de rien : leurs vidéos sont déjà en ligne (liens Metricool).

### 3. Dire à l'agent où sont tes visuels
Dans le dépôt : **Settings → Secrets and variables → Actions → onglet Variables → New repository variable**
- `MEDIA_BASE_URL` = `https://raw.githubusercontent.com/TON-PSEUDO/furrly-agent/main/media`

> Pourquoi un dépôt **public** : Meta doit pouvoir télécharger tes images. Sur un dépôt privé, les liens « raw » demandent un mot de passe et Meta ne peut pas les lire. Tes visuels marketing sont publics de toute façon ; **tes clés, elles, restent secrètes** (étape 5).

### 4. Obtenir tes clés Meta (Facebook + Instagram)
Prérequis : ton Instagram `furrly.rex` doit être un **compte professionnel** relié à ta **Page Facebook**.

1. Va sur **developers.facebook.com** → **Mes apps → Créer une app** → type **Business**.
2. Ouvre **Outils → Explorateur de l'API Graph**, sélectionne ton app, puis **Générer un jeton** avec ces autorisations :
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`
3. Transforme ce jeton en **jeton longue durée** (bouton « i » → **Ouvrir dans l'outil de débogage** → **Prolonger le jeton d'accès**).
4. Dans l'Explorateur, avec ce jeton longue durée, lance `GET /me/accounts` :
   - `id` de ta page → **FB_PAGE_ID**
   - `access_token` de ta page → **FB_PAGE_TOKEN** (un jeton de Page issu d'un jeton longue durée **n'expire pas**)
5. Lance `GET /TON_FB_PAGE_ID?fields=instagram_business_account` → l'`id` affiché → **IG_USER_ID**.

> Pas besoin de « App Review » : tant que tu es administrateur de l'app et qu'elle publie uniquement sur **ta** Page et **ton** Instagram, le mode Développement suffit.

### 5. Enregistrer les clés (en secret)
**Settings → Secrets and variables → Actions → onglet Secrets → New repository secret**, une par une :

| Nom | Valeur |
|---|---|
| `FB_PAGE_ID` | l'id de ta Page |
| `FB_PAGE_TOKEN` | le jeton de ta Page |
| `IG_USER_ID` | l'id Instagram Business |
| `IG_TOKEN` | le même jeton de Page |
| `TIKTOK_TOKEN` | *(optionnel, voir plus bas)* |

### 6. Tester sans risque
**Actions → FURRLY auto-publish → Run workflow.** En mode TEST, le journal affiche `[TEST] publierait reel-1023:facebook (reel)` sans rien envoyer. Vérifie qu'il n'y a pas de ligne `[ERREUR]`.

### 7. ⚠️ Éviter les doublons avec Metricool
Les 19 Reels sont **aussi** dans ton planner Metricool. Avant de passer en réel, **supprime-les (ou mets-les en brouillon) dans Metricool**, sinon ils partiraient deux fois le jour où Metricool se remet à publier.

### 8. Passer en réel
**Settings → Secrets and variables → Actions → Variables** → crée `DRY_RUN` = `false`.
C'est tout : l'agent publie désormais seul, toutes les 30 min.

---

## Ajouter des posts
Une ligne par post dans `calendar.csv` :

| Colonne | Exemple | Règle |
|---|---|---|
| `id` | `card-07` | unique, jamais réutilisé |
| `datetime` | `2026-11-12T12:30:00` | heure de Paris |
| `platform` | `facebook\|instagram` | un ou plusieurs réseaux, séparés par `\|` |
| `type` | `image`, `reel` ou `text` | `text` = Facebook uniquement |
| `caption` | le texte du post | entre guillemets s'il contient des virgules ou des retours à la ligne |
| `media_url` | `furrly-carte-07-1x1.jpg` ou un lien `https://…` | obligatoire pour Instagram |
| `link` | `https://furrlyrex.fr/...` | utilisé pour les posts Facebook `text` |

Sur GitHub : ouvre `calendar.csv` → crayon ✏️ → ajoute ta ligne → **Commit**. L'agent la prendra au prochain réveil.

---

## TikTok (optionnel)
1. **developers.tiktok.com** → crée une app → ajoute **Content Posting API**.
2. Demande l'**audit** de l'app (quelques jours). Avant l'audit, TikTok n'autorise que des publications **privées** (`SELF_ONLY`).
3. Génère un jeton → secret `TIKTOK_TOKEN`.
4. Ajoute `|tiktok` dans la colonne `platform` des Reels.

---

## Agent IA de réponses (commentaires + messages)

`responder.py` tourne toutes les 30 min (workflow **FURRLY réponses IA**) :
- **Commentaires Facebook + Instagram** : répond au ton FURRLY, **masque** spam et insultes, redirige les problèmes de commande vers le privé.
- **Messages privés Messenger + Instagram** : répond (suivi de colis, tailles, prix, retours…).
- Son savoir vient de **`furrly_knowledge.md`** (produits, prix, livraison, retours, contact). Modifie ce fichier quand une info change.
- Il ne répond jamais deux fois, ignore les messages de plus de 48 h, ne dépasse pas 25 actions par passage, et **n'écrit jamais le contenu des messages privés** dans les journaux.

### Mise en route (~10 min)
1. **Nouveau jeton Meta** : refais l'étape 4 en cochant **en plus** `pages_manage_engagement`, `pages_read_user_content`, `pages_messaging`, `instagram_manage_comments`, `instagram_manage_messages`. Remplace les secrets `FB_PAGE_TOKEN` et `IG_TOKEN` (les publications continuent de marcher avec ce jeton).
2. **Messages Instagram** : dans l'appli Instagram → Paramètres → Messages → **Outils connectés** → active **Autoriser l'accès aux messages**.
3. **IA gratuite** : sur **aistudio.google.com** → **Get API key** → crée la clé → secret `GEMINI_API_KEY`.
   *(Option payante, quelques centimes par mois : clé Claude sur console.anthropic.com → secret `ANTHROPIC_API_KEY`, utilisée en priorité.)*
   Sans clé IA, l'agent répond avec des modèles simples.
4. **Tester** : Actions → **FURRLY réponses IA** → Run workflow. Le journal montre ce qu'il **répondrait**, sans rien envoyer.
5. **Passer en réel** : Settings → Secrets and variables → Actions → **Variables** → `REPONSES_DRY_RUN` = `false`.

Lignes `[À TRAITER]` dans le journal : un client a un souci de commande, l'agent lui a donné le contact, mais jette un œil à ta boîte de réception.

Pour ne gérer qu'une partie : variable `REPONSES_SCOPE` = `commentaires` ou `messages`.

### Limites (imposées par les réseaux, pas par l'agent)
- **Messages privés des clients** : tant que l'app Meta est en mode Développement, Meta ne livre que les messages des personnes qui ont un rôle sur l'app. Pour répondre à **tous** tes clients en privé, demande l'**accès avancé** (App Review) pour `pages_messaging` et `instagram_manage_messages`. En attendant, garde les réponses automatiques de **Meta Business Suite** pour les messages privés, et l'agent gère les commentaires.
- **TikTok** : TikTok n'ouvre ni les commentaires ni les messages aux outils externes. Utilise les réponses automatiques intégrées à TikTok (compte Business → Outils Business → Messages directs). Pour un commentaire, génère la réponse ici et colle-la :
  ```bash
  python responder.py --test "Il existe en XL le harnais ?"
  ```
- **Gemini gratuit** : sur l'offre gratuite, Google peut utiliser les textes envoyés pour améliorer ses modèles. Si ça te gêne, prends l'option Claude.

---

## Bon à savoir
- **Retards GitHub** : les réveils programmés peuvent arriver avec quelques minutes de retard ; l'agent accepte jusqu'à 90 min de décalage, rien n'est perdu.
- **Vidéos Metricool** : les Reels pointent vers les vidéos hébergées par Metricool. Si tu les supprimes de Metricool, garde une copie et héberge-les dans `media/` (ou Google Drive en lien public) puis mets à jour `media_url`.
- **Jeton révoqué** : si tu changes ton mot de passe Facebook ou retires l'accès de l'app, refais l'étape 4.
- **Inactivité** : GitHub met en pause les tâches programmées d'un dépôt sans activité pendant 60 jours. Les mises à jour de `state.json` par l'agent comptent comme activité tant qu'il publie.

## Rendu Instagram (grille propre)

- **Couverture des Reels** : l'agent envoie `thumb_offset` (2 s par défaut, variable `REEL_COVER_MS`) pour éviter la vignette noire du fondu d'ouverture. Colonne optionnelle `cover` dans `calendar.csv` : un nombre (ms) ou une image dédiée (ex. `cover-reel-1030.jpg`, 1080×1920, texte dans le centre 3:4).
- **Images** : la grille Instagram affiche en 3:4. Utiliser des visuels **1080×1350 (4:5)** avec le texte dans la zone centrale (marges latérales ~40 px). Les cartes `furrly-carte-XX-4x5.jpg` respectent ce cadrage.
- **Vidéos** : 1080×1920 (9:16), éléments importants dans le centre 1080×1440.
