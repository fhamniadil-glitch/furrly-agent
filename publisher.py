#!/usr/bin/env python3
"""
FURRLY - Agent de publication automatique.
Lit calendar.csv et publie les posts "dus" sur Facebook / Instagram (TikTok en option)
via les API officielles. Conçu pour tourner sur GitHub Actions (gratuit), toutes les 30 min.

Aucune donnée sensible dans le code : les jetons viennent des variables d'environnement
(= GitHub Secrets). L'état des posts déjà publiés est gardé dans state.json (committé par le workflow)
pour ne jamais publier deux fois.
"""

import os
import csv
import json
import time
import pathlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ROOT = pathlib.Path(__file__).parent
CAL = ROOT / "calendar.csv"
STATE = ROOT / "state.json"

GRAPH = "https://graph.facebook.com/v21.0"
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Europe/Paris"))

FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_TOKEN = os.environ.get("IG_TOKEN", "") or FB_PAGE_TOKEN
TIKTOK_TOKEN = os.environ.get("TIKTOK_TOKEN", "")
# Un jeton TikTok expire au bout de 24 h : l'agent en redemande un à chaque passage
# grâce au refresh token (valable 1 an).
TIKTOK_CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REFRESH_TOKEN = os.environ.get("TIKTOK_REFRESH_TOKEN", "")
# SELF_ONLY tant que l'app n'est pas auditée par TikTok, puis PUBLIC_TO_EVERYONE.
TIKTOK_PRIVACY = os.environ.get("TIKTOK_PRIVACY", "") or "SELF_ONLY"
MEDIA_BASE = os.environ.get("MEDIA_BASE_URL", "").rstrip("/")

# Fenêtre : on publie un post si son heure est passée depuis au plus WINDOW_MIN minutes.
# Couvre les retards de déclenchement de GitHub Actions. 90 min par défaut.
WINDOW_MIN = int(os.environ.get("WINDOW_MIN", "90"))
# Sécurité : par défaut l'agent tourne en mode TEST (il n'envoie rien).
# Il ne publie réellement que si la variable DRY_RUN vaut explicitement "false".
DRY_RUN = os.environ.get("DRY_RUN", "").strip().lower() not in ("false", "0", "no")


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"posted": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def media_url(value):
    """Un lien http(s) complet est utilisé tel quel ; sinon on préfixe par MEDIA_BASE_URL
    (= l'URL 'raw' de ton dépôt GitHub, par ex. https://raw.githubusercontent.com/<user>/<repo>/main/media)."""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"{MEDIA_BASE}/{value}" if MEDIA_BASE else value


def is_due(row, now):
    raw = (row.get("datetime") or "").strip()
    if not raw:
        return False
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    delta_min = (now - dt).total_seconds() / 60.0
    return 0 <= delta_min <= WINDOW_MIN


def post_facebook(row):
    cap = row.get("caption", "")
    media = media_url(row.get("media_url", ""))
    typ = (row.get("type") or "text").lower()
    link = (row.get("link") or "").strip()

    if typ == "image" and media:
        url = f"{GRAPH}/{FB_PAGE_ID}/photos"
        data = {"url": media, "caption": cap, "access_token": FB_PAGE_TOKEN}
    elif typ in ("reel", "video") and media:
        url = f"{GRAPH}/{FB_PAGE_ID}/videos"
        data = {"file_url": media, "description": cap, "access_token": FB_PAGE_TOKEN}
    else:
        url = f"{GRAPH}/{FB_PAGE_ID}/feed"
        data = {"message": cap, "access_token": FB_PAGE_TOKEN}
        if link:
            data["link"] = link

    r = requests.post(url, data=data, timeout=180)
    r.raise_for_status()
    return r.json()


def post_instagram(row):
    cap = row.get("caption", "")
    media = media_url(row.get("media_url", ""))
    typ = (row.get("type") or "image").lower()
    if not media:
        raise ValueError("Instagram exige une media_url (image ou vidéo).")

    params = {"caption": cap, "access_token": IG_TOKEN}
    if typ in ("reel", "video"):
        params["media_type"] = "REELS"
        params["video_url"] = media
    else:
        params["image_url"] = media

    c = requests.post(f"{GRAPH}/{IG_USER_ID}/media", data=params, timeout=180)
    c.raise_for_status()
    container = c.json()["id"]

    # Les vidéos/Reels doivent finir d'être traitées avant publication.
    for _ in range(40):
        st = requests.get(
            f"{GRAPH}/{container}",
            params={"fields": "status_code", "access_token": IG_TOKEN},
            timeout=60,
        ).json()
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Conteneur Instagram en erreur : {st}")
        time.sleep(6)

    pub = requests.post(
        f"{GRAPH}/{IG_USER_ID}/media_publish",
        data={"creation_id": container, "access_token": IG_TOKEN},
        timeout=180,
    )
    pub.raise_for_status()
    return pub.json()


def tiktok_access_token():
    if TIKTOK_REFRESH_TOKEN and TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET:
        r = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": TIKTOK_CLIENT_KEY,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": TIKTOK_REFRESH_TOKEN,
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        if "access_token" not in data:
            raise RuntimeError(f"Renouvellement du jeton TikTok refusé : {data}")
        if data.get("refresh_token") and data["refresh_token"] != TIKTOK_REFRESH_TOKEN:
            print("[INFO] TikTok a émis un nouveau refresh token : mets à jour le secret TIKTOK_REFRESH_TOKEN.")
        return data["access_token"]
    if TIKTOK_TOKEN:
        return TIKTOK_TOKEN
    raise RuntimeError("Identifiants TikTok manquants (TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN).")


def post_tiktok(row):
    """Optionnel. Nécessite une app TikTok avec la Content Posting API.
    La vidéo est téléchargée puis envoyée en fichier (FILE_UPLOAD) : TikTok refuse
    PULL_FROM_URL pour un domaine qu'on ne possède pas (ex. static.metricool.com).
    Tant que l'app n'est pas auditée, TikTok ne publie que sur un compte privé."""
    media = media_url(row.get("media_url", ""))
    if not media:
        raise ValueError("TikTok exige une vidéo (media_url).")
    token = tiktok_access_token()
    video = requests.get(media, timeout=300)
    video.raise_for_status()
    blob = video.content
    size = len(blob)

    # Morceaux de 5 à 64 Mo ; sous 64 Mo, un seul envoi. Le dernier morceau absorbe le reste.
    chunk = size if size <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    count = max(1, size // chunk)

    cap = row.get("caption", "")
    init = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
        json={
            "post_info": {
                "title": cap[:2200],
                "privacy_level": TIKTOK_PRIVACY,
                "brand_organic_toggle": True,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk,
                "total_chunk_count": count,
            },
        },
        timeout=120,
    )
    init.raise_for_status()
    data = init.json().get("data", {})
    upload_url = data["upload_url"]

    for i in range(count):
        start = i * chunk
        end = size - 1 if i == count - 1 else start + chunk - 1
        put = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes {start}-{end}/{size}",
            },
            data=blob[start:end + 1],
            timeout=300,
        )
        put.raise_for_status()
    return {"publish_id": data.get("publish_id")}


DISPATCH = {
    "facebook": post_facebook,
    "instagram": post_instagram,
    "tiktok": post_tiktok,
}


def main():
    now = datetime.now(TZ)
    state = load_state()
    posted = set(state.get("posted", []))
    published, skipped, errors = 0, 0, 0

    if not CAL.exists():
        print("Aucun calendar.csv trouvé.")
        return

    with CAL.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        rid = (row.get("id") or "").strip()
        # Une ligne peut viser plusieurs réseaux : "facebook|instagram"
        platforms = [p.strip().lower() for p in (row.get("platform") or "").split("|") if p.strip()]
        if not rid or not platforms:
            continue
        if not is_due(row, now):
            continue

        for platform in platforms:
            key = f"{rid}:{platform}"
            if key in posted:
                continue

            fn = DISPATCH.get(platform)
            if not fn:
                print(f"[SKIP] {key}: plateforme inconnue")
                skipped += 1
                continue

            if DRY_RUN:
                # En test on ne marque rien comme publié : en passant en réel, le post partira bien.
                print(f"[TEST] publierait {key} ({row.get('type', 'text')})")
                published += 1
                continue

            try:
                res = fn(row)
                print(f"[OK] {key} : {res}")
                posted.add(key)
                published += 1
            except Exception as e:
                print(f"[ERREUR] {key} : {e}")
                errors += 1

    state["posted"] = sorted(posted)
    state["last_run"] = now.isoformat()
    save_state(state)
    print(f"Résumé : publiés={published}, ignorés={skipped}, erreurs={errors}")


if __name__ == "__main__":
    main()
