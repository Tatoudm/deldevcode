import random
import time
from datetime import datetime

import bcrypt
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, session

import extensions
from utils.mail_utils import (
    send_support_ticket_email,
    send_support_confirmation_email,
    send_verification_email,
)

support_bp = Blueprint("support", __name__)


SUBJECT_CHOICES = {
    "ban_mute": "Contestation de ban / mute",
    "connexion": "Problème de connexion / inscription",
    "compte": "Problème de compte",
    "bug": "Signaler un bug",
    "autre": "Autre",
}


def tickets_col():
    return extensions.db.support_tickets


def pending_tickets_col():
    return extensions.db.pending_support_tickets


def users_col():
    return extensions.db.utilisateurs


def get_current_user_info():
    """
    Retourne (nom, pdp, email) pour le header si l'utilisateur est connecté.
    """
    if "util" not in session:
        return None, None, None

    u_col = users_col()
    util = u_col.find_one({"nom": session["util"]})
    if not util:
        return None, None, None

    nom = util["nom"]
    pdp = util.get("pdp", "../static/guest.png")
    email = util.get("email")
    return nom, pdp, email


@support_bp.route("/support", methods=["GET", "POST"])
def support_form():
    nom, pdp, user_email = get_current_user_info()

    erreur = None
    success = False

    form_subject = "ban_mute"
    form_objet = ""
    form_description = ""
    email_locked = False

    if user_email:
        form_email = user_email.strip().lower()
        email_locked = True
    else:
        form_email = ""

    if request.method == "POST":

        if user_email:
            form_email = user_email.strip().lower()
            email_locked = True
        else:
            form_email = (request.form.get("email") or "").strip().lower()
            email_locked = False

        form_subject = (request.form.get("subject") or "").strip()
        form_objet = (request.form.get("objet") or "").strip()
        form_description = (request.form.get("description") or "").strip()

        if not form_email:
            erreur = "L'adresse email est obligatoire."
        elif not form_email.endswith("@providencechampion.be"):
            erreur = "L'adresse email doit obligatoirement se terminer par @providencechampion.be."
        elif form_subject not in SUBJECT_CHOICES:
            erreur = "Sujet invalide."
        elif not form_objet:
            erreur = "L'objet du ticket est obligatoire."
        elif not form_description:
            erreur = "La description du problème est obligatoire."
        else:
            t_col = tickets_col()
            p_col = pending_tickets_col()

            open_count = t_col.count_documents(
                {
                    "email": form_email,
                    "status": "open",
                }
            )
            pending_count = p_col.count_documents(
                {
                    "email": form_email,
                }
            )

            if open_count + pending_count >= 3:
                erreur = (
                    "Tu as déjà 3 tickets de support ouverts ou en attente avec cette adresse. "
                    "Merci d'attendre qu'un admin les traite avant d'en créer de nouveaux."
                )
            else:
                subject_label = SUBJECT_CHOICES[form_subject]

                if user_email:
                    creator_username = session.get("util")

                    ticket_doc = {
                        "email": form_email,
                        "subject_code": form_subject,
                        "subject_label": subject_label,
                        "title": form_objet,
                        "description": form_description,
                        "status": "open",
                        "created_at": datetime.utcnow(),
                        "created_by_username": creator_username,
                    }

                    inserted = t_col.insert_one(ticket_doc)
                    ticket_doc["_id"] = inserted.inserted_id

                    try:
                        send_support_ticket_email(ticket_doc)
                    except Exception as e:
                        print("Erreur en envoyant l'email de ticket :", e)

                    try:
                        send_support_confirmation_email(form_email, ticket_doc)
                    except Exception as e:
                        print("Erreur en envoyant l'email de confirmation :", e)

                    success = True
                    form_subject = "ban_mute"
                    form_objet = ""
                    form_description = ""

                else:

                    code = f"{random .randint (0 ,999999 ):06d}"
                    code_hash = bcrypt.hashpw(
                        code.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8")

                    pending_doc = {
                        "email": form_email,
                        "subject_code": form_subject,
                        "subject_label": subject_label,
                        "title": form_objet,
                        "description": form_description,
                        "created_at": time.time(),
                        "code_hash": code_hash,
                    }

                    inserted = p_col.insert_one(pending_doc)
                    pending_id = str(inserted.inserted_id)

                    session["pending_support_id"] = pending_id

                    try:
                        send_verification_email(form_email, code)
                    except Exception as e:
                        print("Erreur en envoyant le code de vérification support :", e)

                        p_col.delete_one({"_id": inserted.inserted_id})
                        session.pop("pending_support_id", None)
                        erreur = (
                            "Impossible d'envoyer le code de vérification pour le moment. "
                            "Merci de réessayer plus tard."
                        )
                    else:

                        return redirect(url_for("support.support_verify"))

    return render_template(
        "support.html",
        nom=nom,
        pdp=pdp,
        erreur=erreur,
        success=success,
        subject_choices=SUBJECT_CHOICES,
        form_email=form_email,
        form_subject=form_subject,
        form_objet=form_objet,
        form_description=form_description,
        email_locked=email_locked,
    )


@support_bp.route("/support/verify", methods=["GET", "POST"])
def support_verify():
    nom, pdp, _ = get_current_user_info()

    p_col = pending_tickets_col()
    t_col = tickets_col()

    pending_id = session.get("pending_support_id")
    if not pending_id:
        return redirect(url_for("support.support_form"))

    try:
        pending = p_col.find_one({"_id": ObjectId(pending_id)})
    except Exception:
        pending = None

    if not pending:
        session.pop("pending_support_id", None)
        return redirect(url_for("support.support_form"))

    now = time.time()
    created_at = pending.get("created_at", now)
    if now - created_at > 600:
        p_col.delete_one({"_id": pending["_id"]})
        session.pop("pending_support_id", None)
        return render_template(
            "support.html",
            nom=nom,
            pdp=pdp,
            erreur="Le code a expiré. Merci de recréer un ticket.",
            success=False,
            subject_choices=SUBJECT_CHOICES,
            form_email="",
            form_subject="ban_mute",
            form_objet="",
            form_description="",
            email_locked=False,
        )

    email = pending["email"]
    erreur = None

    if request.method == "POST":
        code_input = (request.form.get("code") or "").strip()

        if not code_input:
            erreur = "Le code est obligatoire."
        else:
            stored_hash = pending.get("code_hash")
            if not stored_hash:
                erreur = "Code incorrect. Vérifie l'email et réessaie."
            else:
                try:
                    ok = bcrypt.checkpw(
                        code_input.encode("utf-8"), stored_hash.encode("utf-8")
                    )
                except Exception:
                    ok = False

                if not ok:
                    erreur = "Code incorrect. Vérifie l'email et réessaie."
                else:
                    subject_code = pending.get("subject_code")
                    subject_label = pending.get("subject_label")
                    title = pending.get("title")
                    description = pending.get("description")

                    u = users_col().find_one({"email": email})
                    creator_username = u.get("nom") if u else None

                    ticket_doc = {
                        "email": email,
                        "subject_code": subject_code,
                        "subject_label": subject_label,
                        "title": title,
                        "description": description,
                        "status": "open",
                        "created_at": datetime.utcnow(),
                        "created_by_username": creator_username,
                    }

                    inserted = t_col.insert_one(ticket_doc)
                    ticket_doc["_id"] = inserted.inserted_id

                    p_col.delete_one({"_id": pending["_id"]})
                    session.pop("pending_support_id", None)

                    try:
                        send_support_ticket_email(ticket_doc)
                    except Exception as e:
                        print("Erreur en envoyant l'email de ticket (après vérif) :", e)

                    try:
                        send_support_confirmation_email(email, ticket_doc)
                    except Exception as e:
                        print(
                            "Erreur en envoyant l'email de confirmation (après vérif) :",
                            e,
                        )

                    return render_template(
                        "support_success.html",
                        nom=nom,
                        pdp=pdp,
                        email=email,
                    )

    return render_template(
        "support_verify.html",
        nom=nom,
        pdp=pdp,
        email=email,
        erreur=erreur,
    )
