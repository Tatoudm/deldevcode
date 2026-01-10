import os
import ssl
import smtplib
from email.message import EmailMessage
from datetime import datetime
import html as html_lib


def parse_name_from_email(email: str):
    if not email:
        return None, None

    email = email.lower().strip()
    if not email.endswith("@providencechampion.be"):
        return None, None

    local_part = email.split("@")[0]
    parts = local_part.split(".")
    if len(parts) < 2:
        return None, None

    first = parts[0].replace("-", " ").title()
    last = " ".join(parts[1:]).replace("-", " ").title()
    return first, last


def send_verification_email(to_email: str, code: str):
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_ADDRESS ou EMAIL_PASSWORD non configuré dans le .env")

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        raise RuntimeError(
            "Vous devez définir SMTP_HOST dans le .env "
            "(ex: serverxxx.web-hosting.com ou mail.privateemail.com)"
        )

    msg = EmailMessage()
    msg["Subject"] = "Votre code de vérification"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(f"Votre code de vérification est : {code }")

    if smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)


def send_group_invite_email(to_email: str, inviter_name: str, group_name: str):
    """
    Envoie un email d'invitation à rejoindre un groupe.
    """
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_ADDRESS ou EMAIL_PASSWORD non configuré dans le .env")

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        raise RuntimeError(
            "Vous devez définir SMTP_HOST dans le .env "
            "(ex: serverxxx.web-hosting.com ou mail.privateemail.com)"
        )

    msg = EmailMessage()
    msg["Subject"] = (
        f"{inviter_name } t'invite à rejoindre le groupe « {group_name } » sur DelDevCode"
    )
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    plain_text = (
        f"{inviter_name } t'invite à rejoindre le groupe « {group_name } » sur DelDevCode.\n\n"
        "Clique sur le lien ci-dessous pour ouvrir le chat :\n"
        "https://deldevcode.org/chat\n\n"
        "A tout de suite sur DelDevCode 👋"
    )
    msg.set_content(plain_text)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Invitation à un groupe DelDevCode</title>
    </head>
    <body style="margin:0;padding:0;background-color:#0f172a;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:480px;background-color:#020617;border-radius:16px;overflow:hidden;border:1px solid #0f766e;">
                        <tr>
                            <td style="padding:20px 24px 12px 24px;text-align:center;">
                                <div style="display:inline-flex;align-items:center;gap:8px;">
                                    <div style="width:36px;height:36px;border-radius:12px;background:#059669;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                                        <img src="/static/favicon.ico" alt="Logo" style="width:100%;height:100%;object-fit:cover;">
                                    </div>

                                    <div style="text-align:left;">
                                        <div style="color:#e5e7eb;font-size:18px;font-weight:600;">DelDevCode</div>
                                        <div style="color:#6ee7b7;font-size:11px;text-transform:uppercase;letter-spacing:0.08em;">Chat anonyme</div>
                                    </div>
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:8px 24px 4px 24px;">
                                <p style="margin:0;color:#9ca3af;font-size:13px;">Invitation de groupe</p>
                                <h1 style="margin:4px 0 0 0;color:#f9fafb;font-size:20px;">{inviter_name } t'invite à rejoindre un groupe</h1>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:8px 24px 16px 24px;">
                                <div style="background:#022c22;border-radius:12px;padding:12px 14px;border:1px solid #065f46;">
                                    <p style="margin:0 0 4px 0;color:#a7f3d0;font-size:13px;">Nom du groupe</p>
                                    <p style="margin:0;color:#ecfdf5;font-size:15px;font-weight:600;">{group_name }</p>
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:0 24px 10px 24px;">
                                <p style="margin:0;color:#d1d5db;font-size:13px;line-height:1.5;">
                                    {inviter_name } t'a ajouté à ce groupe sur DelDevCode.<br>
                                    Clique sur le bouton ci-dessous pour rejoindre la conversation.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:8px 24px 20px 24px;" align="center">
                                <a href="https://deldevcode.org/chat"
                                   style="display:inline-block;background:#059669;color:#ecfdf5;text-decoration:none;
                                          padding:10px 20px;border-radius:999px;font-size:14px;font-weight:600;">
                                    Ouvrir le chat
                                </a>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:0 24px 20px 24px;">
                                <p style="margin:0;color:#6b7280;font-size:11px;line-height:1.4;">
                                    Si le bouton ne fonctionne pas, copie-colle ce lien dans ton navigateur :<br>
                                    <span style="color:#22c55e;">https://deldevcode.org/chat</span>
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:10px 24px 18px 24px;border-top:1px solid #1f2937;">
                                <p style="margin:0;color:#4b5563;font-size:11px;text-align:center;">
                                    Tu reçois cet email parce qu'un utilisateur de DelDevCode t'a invité dans un groupe.
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg.add_alternative(html_content, subtype="html")

    if smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)


def send_goat_alert(action: str, attempted_by: str):
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print(
            "⚠️ Impossible d'envoyer l'email GOAT ALERT : email/password non configurés."
        )
        return

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        print("⚠️ Impossible d'envoyer l'email GOAT ALERT : SMTP_HOST manquant.")
        return

    to_email = "tatoudm1@gmail.com"

    msg = EmailMessage()
    msg["Subject"] = f"⚠️ Tentative d'action sur ton compte ({action })"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    plain = (
        f"Quelqu'un a tenté de {action } ton compte.\n"
        f"Utilisateur responsable : {attempted_by }\n\n"
        f"Vérifie ton panel DelDevCode si nécessaire."
    )
    msg.set_content(plain)

    html = f"""
    <html>
    <body style="font-family:sans-serif;background:#0f172a;padding:20px;color:#e5e7eb;">
        <div style="max-width:500px;margin:auto;background:#020617;padding:20px;border-radius:12px;border:1px solid #065f46;">
            <h2 style="color:#34d399;">⚠️ Alerte de sécurité</h2>
            <p>Une tentative de <strong style="color:#f87171;">{action }</strong> de ton compte a eu lieu.</p>
            <p><strong>Utilisateur responsable :</strong> {attempted_by }</p>
            <p style="margin-top:20px;">Pense à vérifier le panel administrateur si nécessaire.</p>
        </div>
    </body>
    </html>
    """
    msg.add_alternative(html, subtype="html")

    try:
        if smtp_use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)

    except Exception as e:
        print("⚠️ Erreur en envoyant l'email GOAT ALERT :", e)


def _get_support_smtp_client():
    """
    Récupère la config SMTP spécifique pour les réponses support.

    Nécessite dans le .env :
      - SUPPORT_FROM_EMAIL  (ex: contact@deldevcode.org)
      - SUPPORT_PASSWORD    (mot de passe / app password de cette boîte)
    Optionnel :
      - SUPPORT_SMTP_HOST   (sinon fallback sur SMTP_HOST)
      - SUPPORT_SMTP_PORT   (sinon fallback sur SMTP_PORT ou 465)
      - SUPPORT_SMTP_USE_SSL (sinon fallback sur SMTP_USE_SSL ou '1')
    """
    from_email = os.environ.get("SUPPORT_FROM_EMAIL")
    password = os.environ.get("SUPPORT_PASSWORD")

    if not from_email or not password:
        raise RuntimeError(
            "SUPPORT_FROM_EMAIL ou SUPPORT_PASSWORD non configuré dans le .env "
            "(utilisé pour les réponses de support)."
        )

    smtp_host = os.environ.get("SUPPORT_SMTP_HOST") or os.environ.get("SMTP_HOST")
    smtp_port = int(
        os.environ.get("SUPPORT_SMTP_PORT") or os.environ.get("SMTP_PORT", "465")
    )
    smtp_use_ssl = (
        os.environ.get("SUPPORT_SMTP_USE_SSL") or os.environ.get("SMTP_USE_SSL", "1")
    ).lower() in ("1", "true", "yes")

    if not smtp_host:
        raise RuntimeError(
            "Aucun serveur SMTP défini (SUPPORT_SMTP_HOST ni SMTP_HOST)."
        )

    return from_email, password, smtp_host, smtp_port, smtp_use_ssl


def send_support_reply_email(
    to_email: str, subject: str, body: str, author: str | None = None
):
    """
    Envoie une réponse à un ticket de support en utilisant
    SUPPORT_FROM_EMAIL / SUPPORT_PASSWORD pour l'authentification SMTP.

    HTML simple :
    De: auteur
    Objet: subject
    Texte: body (avec sauts de ligne).
    """
    from_email, password, smtp_host, smtp_port, smtp_use_ssl = (
        _get_support_smtp_client()
    )

    if not author:
        author = "Support DelDevCode"

    body_clean = body.strip()

    body_html = html_lib.escape(body_clean).replace("\n", "<br>")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    plain = f"De : {author }\n" f"Objet : {subject }\n\n" f"{body_clean }\n"
    msg.set_content(plain)

    html = f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{html_lib .escape (subject )}</title>
</head>
<body style="margin:0;padding:0;background-color:#0f172a;
             font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                       style="max-width:600px;background-color:#020617;border-radius:16px;
                              overflow:hidden;border:1px solid #0f766e;">
                    <tr>
                        <td style="padding:16px 20px;border-bottom:1px solid #0f172a;">
                            <p style="margin:0;color:#9ca3af;font-size:12px;">Réponse de DelDevCode</p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:16px 20px 8px 20px;">
                            <p style="margin:0;color:#e5e7eb;font-size:14px;">
                                <strong>De :</strong> {html_lib .escape (author )}
                            </p>
                            <p style="margin:6px 0 0 0;color:#e5e7eb;font-size:14px;">
                                <strong>Objet :</strong> {html_lib .escape (subject )}
                            </p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:12px 20px 20px 20px;">
                            <div style="background:#020617;border-radius:12px;
                                        border:1px solid #1f2937;padding:12px 14px;">
                                <p style="margin:0 0 4px 0;color:#9ca3af;font-size:12px;">Texte :</p>
                                <div style="margin:0;color:#e5e7eb;font-size:14px;line-height:1.5;">
{body_html }
                                </div>
                            </div>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    msg.add_alternative(html, subtype="html")

    if smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
            smtp.login(from_email, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(from_email, password)
            smtp.send_message(msg)


def send_support_ticket_email(ticket: dict):
    """
    Envoie un email aux adresses administrateur lors de la création d'un ticket support.
    Utilise EMAIL_ADDRESS / EMAIL_PASSWORD (pas les identifiants support).
    """

    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_ADDRESS ou EMAIL_PASSWORD non configuré dans le .env")

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        raise RuntimeError("Vous devez définir SMTP_HOST dans le .env")

    to_list = [
        "tatoudm@deldevcode.org",
        "contact@deldevcode.org",
        "tatoudm1@gmail.com",
    ]

    subject_label = ticket.get("subject_label", "support")
    title = ticket.get("title", "(Sans titre)")
    email = ticket.get("email", "inconnu")
    created_by = ticket.get("created_by_username", "inconnu")
    description = ticket.get("description", "")

    msg = EmailMessage()
    msg["Subject"] = f"[DelDevCode] Nouveau ticket support - {subject_label }"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ", ".join(to_list)

    plain = (
        f"Nouveau ticket de support : {subject_label }\n\n"
        f"Adresse email : {email }\n"
        f"Par : {created_by }\n"
        f"Objet : {title }\n\n"
        f"Description :\n{description }\n"
    )
    msg.set_content(plain)

    html = f"""
    <html>
    <body style="font-family:sans-serif;">
        <h2>Nouveau ticket de support</h2>
        <p><strong>Type :</strong> {subject_label }</p>
        <p><strong>Email :</strong> {email }</p>
        <p><strong>Pseudo :</strong> {created_by }</p>
        <p><strong>Objet :</strong> {title }</p>
        <p><strong>Description :</strong><br>{description }</p>
    </body>
    </html>
    """
    msg.add_alternative(html, subtype="html")

    if smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)


def send_support_confirmation_email(to_email: str, ticket: dict):
    """
    Envoie un mail de confirmation à l'auteur du ticket.
    Expéditeur = EMAIL_ADDRESS (no-reply).
    """

    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_ADDRESS ou EMAIL_PASSWORD non configuré dans le .env")

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        raise RuntimeError("Vous devez définir SMTP_HOST dans le .env")

    subject_label = ticket.get("subject_label", "support")
    title = ticket.get("title", "(Sans titre)")

    msg = EmailMessage()
    msg["Subject"] = f"[DelDevCode] Confirmation de ton ticket - {subject_label }"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    plain = (
        "Bonjour,\n\n"
        "Ton ticket de support sur DelDevCode a bien été enregistré.\n"
        "Notre équipe te répondra à cette adresse dès que possible.\n\n"
        f"Objet : {title }\n"
        f"Catégorie : {subject_label }\n\n"
        "Merci d'utiliser DelDevCode.\n\n"
        "— Message automatique, merci de ne pas répondre."
    )
    msg.set_content(plain)

    html = f"""
    <html>
    <body style="font-family:sans-serif;background:#0f172a;padding:20px;color:#e5e7eb;">
        <div style="max-width:600px;margin:auto;background:#020617;padding:20px;border-radius:12px;border:1px solid #065f46;">
            <h2 style="color:#34d399;">Confirmation de ton ticket</h2>
            <p>Ton ticket a bien été reçu par l'équipe DelDevCode.</p>

            <p><strong style="color:#a7f3d0;">Objet :</strong> {title }</p>
            <p><strong style="color:#a7f3d0;">Catégorie :</strong> {subject_label }</p>

            <p style="margin-top:20px;">Nous te répondrons dès que possible.</p>

            <p style="margin-top:20px;color:#6b7280;font-size:12px;">
                Ceci est un message automatique. Merci de ne pas répondre.
            </p>
        </div>
    </body>
    </html>
    """
    msg.add_alternative(html, subtype="html")

    if smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)


def send_support_status_email(
    to_email: str, ticket: dict, action: str, actor: str, reason: str | None = None
):
    """
    Envoie un mail quand un ticket est fermé ou réouvert.
    action: "closed" ou "reopened"
    actor: pseudo de l'admin
    """
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("⚠️ Impossible d'envoyer l'email de statut support : config manquante.")
        return

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        print("⚠️ Impossible d'envoyer l'email de statut support : SMTP_HOST manquant.")
        return

    subject_label = ticket.get("subject_label", "support")
    title = ticket.get("title", "(Sans titre)")

    if action == "closed":
        subject = f"[DelDevCode] Ton ticket a été fermé"
        action_text = "a été <strong>fermé</strong>"
    elif action == "reopened":
        subject = f"[DelDevCode] Ton ticket a été réouvert"
        action_text = "a été <strong>réouvert</strong>"
    else:
        subject = "[DelDevCode] Mise à jour de ton ticket"
        action_text = "a été mis à jour"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    reason_text = f"\nRaison : {reason }\n" if reason else ""

    plain = (
        "Bonjour,\n\n"
        f"Ton ticket de support sur DelDevCode {action_text .replace ('<strong>','').replace ('</strong>','')} par {actor }.\n\n"
        f"Objet : {title }\n"
        f"Catégorie : {subject_label }\n"
        f"{reason_text }\n"
        "— Ceci est un message automatique.\n"
    )
    msg.set_content(plain)

    if reason:
        reason_html = f"""
        <p style="margin-top:10px;">
            <strong style="color:#f97316;">Raison :</strong><br>
            <span style="white-space:pre-wrap;">{reason }</span>
        </p>
        """
    else:
        reason_html = ""

    html = f"""
    <html>
    <body style="font-family:sans-serif;background:#0f172a;padding:20px;color:#e5e7eb;">
        <div style="max-width:600px;margin:auto;background:#020617;padding:20px;border-radius:12px;border:1px solid #065f46;">
            <h2 style="color:#34d399;margin-top:0;">Mise à jour de ton ticket</h2>
            <p>
                Ton ticket de support {action_text } par <strong>{actor }</strong>.
            </p>
            <p><strong>Objet :</strong> {title }</p>
            <p><strong>Catégorie :</strong> {subject_label }</p>
            {reason_html }
            <p style="margin-top:20px;color:#6b7280;font-size:12px;">
                Ceci est un message automatique. Merci de ne pas répondre directement.
            </p>
        </div>
    </body>
    </html>
    """
    msg.add_alternative(html, subtype="html")

    try:
        if smtp_use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
    except Exception as e:
        print("⚠️ Erreur en envoyant l'email de statut support :", e)


def send_account_deletion_email(to_email: str, username: str, delete_link: str):
    """
    Envoie un email avec un lien de confirmation de suppression de compte.
    """
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_ADDRESS ou EMAIL_PASSWORD non configuré dans le .env")

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "1").lower() in ("1", "true", "yes")

    if not smtp_host:
        raise RuntimeError(
            "Vous devez définir SMTP_HOST dans le .env "
            "(ex: serverxxx.web-hosting.com ou mail.privateemail.com)"
        )

    msg = EmailMessage()
    msg["Subject"] = "Confirmation de suppression de ton compte DelDevCode"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    plain = (
        f"Bonjour {username },\n\n"
        "Tu as demandé la suppression de ton compte DelDevCode.\n"
        "Si tu confirmes, clique sur le lien ci-dessous (valable 1 heure) :\n\n"
        f"{delete_link }\n\n"
        "Si tu n'es pas à l'origine de cette demande, ignore simplement cet email.\n\n"
        "— L'équipe DelDevCode"
    )
    msg.set_content(plain)

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Suppression de ton compte DelDevCode</title>
    </head>
    <body style="margin:0;padding:0;background-color:#0f172a;
                 font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                           style="max-width:520px;background-color:#020617;border-radius:16px;
                                  overflow:hidden;border:1px solid #b91c1c;">
                        <tr>
                            <td style="padding:20px 24px 10px 24px;">
                                <h1 style="margin:0;color:#fecaca;font-size:20px;">
                                    Confirmation de suppression de compte
                                </h1>
                                <p style="margin:8px 0 0 0;color:#e5e7eb;font-size:14px;">
                                    Bonjour <strong>{username }</strong>,
                                </p>
                                <p style="margin:8px 0 0 0;color:#9ca3af;font-size:13px;line-height:1.5;">
                                    Tu as demandé la suppression de ton compte DelDevCode.
                                    Cette action est <strong>définitive</strong>.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:8px 24px 20px 24px;" align="center">
                                <a href="{delete_link }"
                                   style="display:inline-block;background:#dc2626;color:#fee2e2;text-decoration:none;
                                          padding:10px 22px;border-radius:999px;font-size:14px;font-weight:600;">
                                    Confirmer la suppression de mon compte
                                </a>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:0 24px 18px 24px;">
                                <p style="margin:0;color:#6b7280;font-size:11px;line-height:1.5;">
                                    Si le bouton ne fonctionne pas, copie-colle ce lien dans ton navigateur :<br>
                                    <span style="color:#fca5a5;">{delete_link }</span>
                                </p>
                                <p style="margin:10px 0 0 0;color:#4b5563;font-size:11px;">
                                    Si tu n'es pas à l'origine de cette demande, ignore simplement cet email.
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    msg.add_alternative(html, subtype="html")

    if smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
