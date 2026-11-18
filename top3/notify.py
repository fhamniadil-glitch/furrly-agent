"""Envoi du rapport : SMTP OVH (contact@furrlyrex.fr) + option Telegram."""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import requests

log = logging.getLogger("top3.envoi")


def envoyer_email(html: str, objet: str, cfg: dict, texte: str) -> None:
    user = os.environ["SMTP_USER"]
    mdp = os.environ["SMTP_PASSWORD"]
    dest = os.getenv("EMAIL_TO") or cfg["destinataire"]
    msg = EmailMessage()
    msg["Subject"] = objet
    msg["From"] = f"Furrly Top 3 <{cfg['expediteur']}>"
    msg["To"] = dest
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="furrlyrex.fr")
    msg.set_content(texte)
    msg.add_alternative(html, subtype="html")
    for essai in range(3):
        try:
            with smtplib.SMTP_SSL(cfg["smtp_hote"], cfg["smtp_port"], context=ssl.create_default_context(), timeout=60) as s:
                s.login(user, mdp)
                s.send_message(msg)
            log.info("Email envoyé à %s", dest)
            return
        except (smtplib.SMTPException, OSError) as e:
            log.warning("Échec SMTP (essai %d/3) : %s", essai + 1, e)
            time.sleep(10 * (essai + 1))
    raise RuntimeError("Email non envoyé après 3 essais")


def envoyer_telegram(texte: str, html: str, nom_fichier: str) -> None:
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log.warning("Telegram activé mais TELEGRAM_TOKEN / TELEGRAM_CHAT_ID manquants")
        return
    base = f"https://api.telegram.org/bot{token}"
    try:
        requests.post(f"{base}/sendMessage", data={"chat_id": chat, "text": texte[:4000]}, timeout=30).raise_for_status()
        requests.post(f"{base}/sendDocument", data={"chat_id": chat},
                      files={"document": (nom_fichier, html.encode("utf-8"), "text/html")}, timeout=60).raise_for_status()
        log.info("Telegram envoyé")
    except requests.RequestException as e:
        log.warning("Telegram en échec : %s", e)
