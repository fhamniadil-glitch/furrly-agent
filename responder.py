#!/usr/bin/env python3
"""
FURRLY - Agent IA de réponses (commentaires + messages privés).
Toutes les 30 min (GitHub Actions), il lit les nouveaux commentaires et messages
Facebook / Instagram, demande à l'IA une réponse au ton FURRLY et la publie.
Les spams et insultes sont masqués ; les problèmes de commande sont redirigés vers le contact.

Le savoir de l'agent vient de furrly_knowledge.md (à tenir à jour).
L'IA : Gemini (gratuit, GEMINI_API_KEY) ou Claude (ANTHROPIC_API_KEY, quelques centimes).
Sans clé IA, il répond avec des modèles simples.

Sécurité : il démarre en mode TEST (il n'envoie rien) tant que REPONSES_DRY_RUN != "false".
Le contenu des messages privés n'est jamais écrit dans les journaux ni dans le dépôt.

Test local d'une réponse (pratique pour TikTok, à copier-coller) :
    python responder.py --test "Ça taille comment le harnais pour un malinois ?"
"""

import os
import sys
import json
import pathlib
from datetime import datetime, timedelta, timezone

import requests

ROOT = pathlib.Path(__file__).parent
KNOWLEDGE = ROOT / "furrly_knowledge.md"
STATE = ROOT / "responder_state.json"

GRAPH = "https://graph.facebook.com/v21.0"

FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_TOKEN = os.environ.get("IG_TOKEN", "") or FB_PAGE_TOKEN

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "") or "gemini-2.5-flash"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "") or "claude-haiku-5-5"

# Ce que l'agent gère : "commentaires", "messages" ou les deux (séparés par une virgule).
SCOPE = {s.strip().lower() for s in (os.environ.get("REPONSES_SCOPE", "") or "commentaires,messages").split(",")}
# On ne répond qu'aux messages récents : évite de déterrer de vieux commentaires au premier passage.
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "") or "48")
# Plafond de réponses par passage : rester naturel aux yeux de Meta.
MAX_ACTIONS = int(os.environ.get("MAX_ACTIONS", "") or "25")
POSTS_TO_SCAN = int(os.environ.get("POSTS_TO_SCAN", "") or "10")
DRY_RUN = os.environ.get("REPONSES_DRY_RUN", "").strip().lower() not in ("false", "0", "no")

SYSTEM_PROMPT = """Tu es le community manager de FURRLY, boutique d'accessoires pour chiens actifs.
Tu réponds aux commentaires et messages privés sur Facebook, Instagram et TikTok.

STYLE
- Français, tutoiement, chaleureux et direct, comme Adil (le fondateur, maître de Rex le Malinois).
- Commentaire public : 1 à 2 phrases max. Message privé : 4 phrases max.
- 1 emoji max (🐾 de préférence). Pas de hashtag. Pas de lien dans un commentaire Instagram (non cliquable) :
  renvoie plutôt vers « le lien en bio » ou propose d'écrire en message privé.
- Varie tes formulations, ne commence pas toujours par « Merci ».

RÈGLES
- N'utilise QUE les infos de la FICHE FURRLY ci-dessous. Si l'info n'y est pas, ne l'invente jamais :
  invite à écrire sur WhatsApp ou par e-mail.
- Aucun code promo n'existe à part les remises automatiques de la fiche.
- Question sur une commande précise (retard, colis, remboursement, produit cassé) : en commentaire,
  réponds avec empathie et invite à écrire en message privé ; en message privé, donne le lien de suivi
  ou le contact (e-mail / WhatsApp) et demande le numéro de commande. action = "escalate".
- Ne demande jamais d'infos personnelles (adresse, téléphone, n° de commande) dans un commentaire public.
- Santé / comportement grave du chien : reste prudent et conseille le vétérinaire.
- Si on te demande si tu es un robot, réponds honnêtement que c'est l'assistant de FURRLY et qu'Adil
  lit aussi les messages.
- Spam, arnaque, lien suspect, insulte, contenu haineux : action = "hide" (pas de réponse).
- Message sans besoin de réponse (simple emoji d'un client, « ok », tag d'un ami sans texte) :
  pour un commentaire, un petit mot sympa suffit ; si vraiment rien à dire, action = "ignore".
- Critique honnête (pas une insulte) : ne la masque jamais, réponds calmement et propose d'en parler en privé.

FORMAT DE SORTIE : uniquement du JSON valide, sans texte autour :
{"action": "reply" | "escalate" | "hide" | "ignore", "reply": "texte de la réponse ou chaîne vide"}
"""


# ---------------------------------------------------------------- état

def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"handled": []}


def save_state(state, handled):
    # On garde les 5000 derniers identifiants : largement assez, et le fichier reste léger.
    state["handled"] = list(handled)[-5000:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- IA

def knowledge():
    return KNOWLEDGE.read_text(encoding="utf-8") if KNOWLEDGE.exists() else ""


def build_prompt(platform, kind, text, context=""):
    where = "commentaire public" if kind == "comment" else "message privé"
    parts = [f"FICHE FURRLY :\n{knowledge()}", f"PLATEFORME : {platform} ({where})"]
    if context:
        parts.append(f"LÉGENDE DU POST COMMENTÉ : {context[:600]}")
    parts.append(f"MESSAGE REÇU :\n{text[:2000]}")
    return "\n\n".join(parts)


def ask_claude(prompt):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 400,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []))


def ask_gemini(prompt):
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
        },
        timeout=60,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def parse_decision(raw):
    raw = (raw or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start:end + 1])
    action = str(data.get("action", "")).lower()
    if action not in ("reply", "escalate", "hide", "ignore"):
        raise ValueError(f"action inconnue : {action}")
    reply = str(data.get("reply", "")).strip()
    if action in ("reply", "escalate") and not reply:
        raise ValueError("réponse vide")
    return {"action": action, "reply": reply}


SPAM_WORDS = ("crypto", "bitcoin", "promote it on", "dm us to", "collab? dm", "send it to @", "onlyfans",
              "investment", "forex", "followers gratuits", "free followers")
ORDER_WORDS = ("commande", "colis", "livr", "rembours", "reçu", "recu", "cassé", "casse", "retour", "suivi")


def template_decision(kind, text):
    """Secours sans IA : quelques réponses sûres, le reste est laissé à l'humain."""
    t = text.lower()
    if any(w in t for w in SPAM_WORDS):
        return {"action": "hide", "reply": ""}
    if any(w in t for w in ORDER_WORDS):
        if kind == "comment":
            return {"action": "escalate", "reply": "On regarde ça tout de suite 🐾 Écris-nous en message privé avec ton numéro de commande !"}
        return {"action": "escalate", "reply": "Merci pour ton message 🐾 Tu peux suivre ton colis ici : https://furrlyrex.fr/apps/track123. Pour toute autre question, envoie-nous ton numéro de commande et on s'en occupe très vite (ou sur WhatsApp : https://wa.me/33768446417)."}
    if any(w in t for w in ("prix", "combien", "taille", "dispo", "où", "ou acheter", "lien")):
        if kind == "comment":
            return {"action": "reply", "reply": "Toutes les infos (prix, tailles) sont sur furrlyrex.fr, lien en bio 🐾 Livraison offerte en France !"}
        return {"action": "reply", "reply": "Hello ! Tout est sur https://furrlyrex.fr avec le guide des tailles 🐾 Livraison offerte en France, et -10 % dès 2 articles. Dis-moi la race et le poids de ton chien si tu veux un conseil !"}
    if kind == "comment":
        return {"action": "reply", "reply": "Merci, la meute FURRLY te salue 🐾"}
    return {"action": "escalate", "reply": "Merci pour ton message 🐾 On te répond très vite !"}


def decide(platform, kind, text, context=""):
    text = (text or "").strip()
    if not text:
        return {"action": "ignore", "reply": ""}
    prompt = build_prompt(platform, kind, text, context)
    for name, key, fn in (("claude", ANTHROPIC_API_KEY, ask_claude), ("gemini", GEMINI_API_KEY, ask_gemini)):
        if not key:
            continue
        try:
            return parse_decision(fn(prompt))
        except Exception as e:
            print(f"[IA] {name} indisponible ({type(e).__name__}), on essaie la suite.")
    return template_decision(kind, text)


# ---------------------------------------------------------------- Meta Graph API

def gget(path, token, **params):
    params["access_token"] = token
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path} {r.status_code} : {r.text[:300]}")
    return r.json()


def gpost(path, token, **data):
    data["access_token"] = token
    r = requests.post(f"{GRAPH}/{path}", data=data, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} {r.status_code} : {r.text[:300]}")
    return r.json()


def recent(ts, since):
    if not ts:
        return True
    try:
        dt = datetime.strptime(ts.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return True
    return dt >= since


def fb_comments(since):
    """Commentaires de 1er niveau sur les derniers posts de la Page, hors ceux de la Page elle-même."""
    posts = gget(f"{FB_PAGE_ID}/posts", FB_PAGE_TOKEN, fields="id,message", limit=POSTS_TO_SCAN).get("data", [])
    for post in posts:
        comments = gget(
            f"{post['id']}/comments", FB_PAGE_TOKEN,
            fields="id,message,from,created_time,comments.limit(25){from}",
            filter="toplevel", order="reverse_chronological", limit=50,
        ).get("data", [])
        for c in comments:
            if (c.get("from") or {}).get("id") == FB_PAGE_ID:
                continue
            # Déjà répondu à la main ? On n'en rajoute pas.
            replies = (c.get("comments") or {}).get("data", [])
            if any((x.get("from") or {}).get("id") == FB_PAGE_ID for x in replies):
                continue
            if not recent(c.get("created_time"), since):
                continue
            yield {"platform": "facebook", "id": c["id"], "text": c.get("message", ""), "context": post.get("message", "")}


def ig_comments(since, own_username):
    media = gget(f"{IG_USER_ID}/media", IG_TOKEN, fields="id,caption,timestamp", limit=POSTS_TO_SCAN).get("data", [])
    for m in media:
        comments = gget(
            f"{m['id']}/comments", IG_TOKEN,
            fields="id,text,username,timestamp,replies{username}", limit=50,
        ).get("data", [])
        for c in comments:
            if (c.get("username") or "").lower() == own_username:
                continue
            replies = (c.get("replies") or {}).get("data", [])
            if any((x.get("username") or "").lower() == own_username for x in replies):
                continue
            if not recent(c.get("timestamp"), since):
                continue
            yield {"platform": "instagram", "id": c["id"], "text": c.get("text", ""), "context": m.get("caption", "")}


def conversations(platform, since):
    """Conversations Messenger / Instagram dont le dernier message vient du client."""
    data = gget(
        f"{FB_PAGE_ID}/conversations", FB_PAGE_TOKEN, platform=platform,
        fields="id,updated_time,messages.limit(1){id,message,from,created_time}", limit=25,
    ).get("data", [])
    for conv in data:
        msgs = (conv.get("messages") or {}).get("data", [])
        if not msgs:
            continue
        last = msgs[0]
        sender = last.get("from") or {}
        if sender.get("id") in (FB_PAGE_ID, IG_USER_ID):
            continue  # c'est nous qui avons écrit en dernier
        if not recent(last.get("created_time"), since):
            continue
        yield {
            "platform": "messenger" if platform == "messenger" else "instagram_dm",
            "id": last["id"], "recipient": sender.get("id"), "text": last.get("message", ""), "context": "",
        }


def act_comment(item, decision):
    platform, cid, action = item["platform"], item["id"], decision["action"]
    if action == "hide":
        if platform == "facebook":
            gpost(cid, FB_PAGE_TOKEN, is_hidden="true")
        else:
            gpost(cid, IG_TOKEN, hide="true")
    elif action in ("reply", "escalate"):
        if platform == "facebook":
            gpost(f"{cid}/comments", FB_PAGE_TOKEN, message=decision["reply"])
        else:
            gpost(f"{cid}/replies", IG_TOKEN, message=decision["reply"])


def act_message(item, decision):
    if decision["action"] not in ("reply", "escalate") or not item.get("recipient"):
        return
    gpost(
        f"{FB_PAGE_ID}/messages", FB_PAGE_TOKEN,
        recipient=json.dumps({"id": item["recipient"]}),
        messaging_type="RESPONSE",
        message=json.dumps({"text": decision["reply"]}),
    )


# ---------------------------------------------------------------- main

def collect(since):
    """Rassemble tout ce qui attend une réponse ; une source en panne n'arrête pas les autres."""
    sources = []
    if "commentaires" in SCOPE:
        if FB_PAGE_ID and FB_PAGE_TOKEN:
            sources.append(("commentaires Facebook", "comment", lambda: fb_comments(since)))
        if IG_USER_ID and IG_TOKEN:
            def ig():
                own = (gget(IG_USER_ID, IG_TOKEN, fields="username").get("username") or "").lower()
                return ig_comments(since, own)
            sources.append(("commentaires Instagram", "comment", ig))
    if "messages" in SCOPE and FB_PAGE_ID and FB_PAGE_TOKEN:
        sources.append(("messages Messenger", "dm", lambda: conversations("messenger", since)))
        sources.append(("messages Instagram", "dm", lambda: conversations("instagram", since)))

    for label, kind, fn in sources:
        try:
            for item in fn():
                yield kind, item
        except Exception as e:
            print(f"[ERREUR] {label} : {e}")


def main():
    if not (FB_PAGE_ID and FB_PAGE_TOKEN):
        print("Clés Meta manquantes (FB_PAGE_ID / FB_PAGE_TOKEN) : rien à faire.")
        return
    ia = "Claude" if ANTHROPIC_API_KEY else "Gemini" if GEMINI_API_KEY else "modèles simples (aucune clé IA)"
    print(f"Mode {'TEST' if DRY_RUN else 'RÉEL'} · IA : {ia} · périmètre : {', '.join(sorted(SCOPE))}")

    state = load_state()
    handled = list(state.get("handled", []))
    seen = set(handled)
    since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    counts = {"reply": 0, "escalate": 0, "hide": 0, "ignore": 0, "erreur": 0}
    done = 0

    for kind, item in collect(since):
        key = f"{item['platform']}:{item['id']}"
        if key in seen:
            continue
        if done >= MAX_ACTIONS:
            print(f"Plafond de {MAX_ACTIONS} actions atteint, la suite au prochain passage.")
            break

        decision = decide(item["platform"], kind, item["text"], item.get("context", ""))
        # Les messages privés restent privés : on ne journalise jamais leur contenu.
        shown = item["text"][:80].replace("\n", " ") if kind == "comment" else "(message privé)"
        tag = "[À TRAITER] " if decision["action"] == "escalate" else ""
        print(f"{tag}[{decision['action']}] {key} « {shown} »" + (f" → {decision['reply']}" if kind == "comment" else ""))

        if DRY_RUN:
            # En test on ne marque rien : en passant en réel, ces messages seront bien traités.
            counts[decision["action"]] += 1
            done += 1
            continue
        try:
            (act_comment if kind == "comment" else act_message)(item, decision)
            counts[decision["action"]] += 1
            handled.append(key)
            seen.add(key)
        except Exception as e:
            print(f"[ERREUR] {key} : {e}")
            counts["erreur"] += 1
        done += 1

    if not DRY_RUN:
        save_state(state, handled)
    print("Résumé : " + ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--test":
        msg = " ".join(sys.argv[2:])
        for k in ("comment", "dm"):
            print(f"{k}: {json.dumps(decide('tiktok', k, msg), ensure_ascii=False)}")
    else:
        main()
