import os
import re
import secrets
from datetime import datetime, timedelta
from bson import ObjectId
from bson.errors import InvalidId

import bcrypt
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    current_app,
)

import extensions
from utils.auth_utils import get_user_plan
from utils.mail_utils import send_account_deletion_email

profil_bp = Blueprint("profil", __name__)

PSEUDO_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


ALLOWED_PDP_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

PUBLIC_HIDE_FIELDS = {
    "email",
    "first_name",
    "last_name",
    "twofa_enabled",
    "ban_reason",
    "last_seen_dm",
    "muted_by",
    "muted_reason",
    "muted_until",
    "_id",
    "pdp",
    "is_admin",
    "stripe_subscription_id",
    "plan_expires_at",
    "mdp",
    "delete_token",
    "delete_token_expires_at",
}


def users_col():
    return extensions.db.utilisateurs


def messages_col():
    return extensions.db.messages


def _get_current_header_user():
    """
    Pour base.html (header avatar + nom).
    """
    username = session.get("util")
    if not username:
        return None, "guest.png"
    u = users_col().find_one({"nom": username})
    if not u:
        session.pop("util", None)
        return None, "guest.png"
    return u.get("nom"), _get_pdp_filename_from_user(u)


def _format_value(v):
    try:
        if isinstance(v, ObjectId):
            return str(v)
    except Exception:
        pass

    try:
        if hasattr(v, "isoformat"):
            return v.isoformat()
    except Exception:
        pass

    if isinstance(v, (bytes, bytearray)):
        return f"<{len (v )} bytes>"

    return v


def _build_public_fields(user: dict):
    items = []

    for k, v in user.items():
        if k in PUBLIC_HIDE_FIELDS:
            continue
        if k.startswith("_"):
            continue

        if k == "banned":
            value = "❌ Banni" if bool(v) else "✅ Pas banni"
        elif k == "muted":
            value = "❌ Mute" if v and v != 0 else "✅ Pas mute"
        else:
            value = _format_value(v)

        if value is None:
            value = "null"
        else:
            value = str(value)

        items.append((k, value))

    items.sort(key=lambda kv: kv[0].lower())
    return items


def _allowed_pdp_file(filename: str) -> bool:
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext in ALLOWED_PDP_EXTENSIONS


def _get_pdp_filename_from_user(user) -> str:
    """
    On ne garde en mémoire que le nom de fichier (ex: 'guest.png').
    Si l'ancien format contenait un chemin (../static/pdp/guest.png),
    on prend juste le basename.
    """
    raw = (user.get("pdp") or "").strip()
    if not raw:
        return "guest.png"
    return os.path.basename(raw)


@profil_bp.route("/profil", methods=["GET", "POST"])
def profil():
    """
    Page de gestion du profil :
      - changement de pseudo (sans mdp)
      - changement de mot de passe
      - gestion A2F
      - changement de photo de profil (Plus uniquement, via upload)
      - demande de suppression de compte (avec lien de confirmation)
    """
    username = session.get("util")
    if not username:

        return redirect(url_for("auth.login"))

    u_col = users_col()
    m_col = messages_col()

    user = u_col.find_one({"nom": username})
    if not user:

        session.pop("util", None)
        return redirect(url_for("auth.login"))

    erreur = None
    success = None

    plan = get_user_plan(user)
    is_plus = plan == "plus"

    if request.method == "POST":
        action = request.form.get("action") or ""

        if action == "update_username":
            new_username = (request.form.get("new_username") or "").strip()

            if not new_username:
                erreur = "Merci d'entrer un pseudo."
            elif new_username == user["nom"]:
                erreur = "Ton pseudo est déjà celui-ci."
            elif not PSEUDO_REGEX.match(new_username):
                erreur = "Le pseudo doit faire entre 3 et 20 caractères et contenir uniquement des lettres, chiffres, tirets et underscores."
            else:

                existing = u_col.find_one({"nom": new_username})
                if existing and existing["_id"] != user["_id"]:
                    erreur = "Ce pseudo est déjà utilisé."
                else:
                    old_username = user["nom"]
                    u_col.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"nom": new_username}},
                    )
                    try:
                        m_col.update_many(
                            {"author": old_username},
                            {"$set": {"author": new_username}},
                        )
                    except Exception as e:
                        print(
                            "Erreur mise à jour messages après changement de pseudo:",
                            e,
                        )

                    session["util"] = new_username
                    user["nom"] = new_username
                    username = new_username
                    success = "Ton pseudo a été mis à jour."

        elif action == "update_password":
            current_password = request.form.get("current_password") or ""
            new_password = request.form.get("new_password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not current_password or not new_password or not confirm_password:
                erreur = "Merci de remplir tous les champs de mot de passe."
            elif not bcrypt.checkpw(current_password.encode("utf-8"), user["mdp"]):
                erreur = "Mot de passe actuel incorrect."
            elif new_password != confirm_password:
                erreur = "La confirmation du nouveau mot de passe ne correspond pas."
            elif len(new_password) < 8:
                erreur = "Le nouveau mot de passe doit contenir au moins 8 caractères."
            elif not re.search(r"\d", new_password):
                erreur = "Le nouveau mot de passe doit contenir au moins un chiffre."
            else:
                hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
                u_col.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"mdp": hashed}},
                )
                success = "Ton mot de passe a été mis à jour."

        elif action == "toggle_twofa":
            want_twofa = request.form.get("twofa_enabled") == "on"

            if want_twofa and not user.get("email"):
                erreur = "Tu dois avoir une adresse email pour activer l'A2F."
            else:
                u_col.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"twofa_enabled": bool(want_twofa)}},
                )
                user["twofa_enabled"] = bool(want_twofa)
                success = (
                    "Authentification à deux facteurs activée."
                    if want_twofa
                    else "Authentification à deux facteurs désactivée."
                )

        elif action == "update_pdp":
            if not is_plus:
                erreur = "Seuls les membres Plus peuvent changer leur photo de profil."
            else:
                file = request.files.get("pdp_file")
                if not file or file.filename == "":
                    erreur = "Merci de choisir une image."
                elif not _allowed_pdp_file(file.filename):
                    erreur = (
                        "Format d'image non supporté. Formats autorisés : "
                        "PNG, JPG, JPEG, WEBP."
                    )
                else:

                    upload_folder = os.path.join(current_app.root_path, "static", "pdp")
                    os.makedirs(upload_folder, exist_ok=True)

                    ext = os.path.splitext(file.filename)[1].lower()

                    random_part = secrets.token_hex(4)
                    filename = f"{user ['_id']}_{random_part }{ext }"

                    old_pdp = _get_pdp_filename_from_user(user)
                    if old_pdp and old_pdp != "guest.png":
                        try:
                            os.remove(os.path.join(upload_folder, old_pdp))
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            print(
                                "Erreur lors de la suppression de l'ancienne PDP :", e
                            )

                    file_path = os.path.join(upload_folder, filename)
                    try:
                        file.save(file_path)
                    except Exception as e:
                        print("Erreur lors de l'enregistrement de la PDP :", e)
                        erreur = "Impossible d'enregistrer l'image pour l'instant."
                    else:
                        u_col.update_one(
                            {"_id": user["_id"]},
                            {"$set": {"pdp": filename}},
                        )
                        user["pdp"] = filename
                        success = "Ta photo de profil a été mise à jour."

        elif action == "request_delete_account":
            if not user.get("email"):
                erreur = "Tu dois avoir une adresse email valide pour demander la suppression de ton compte."
            else:
                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=1)

                u_col.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "delete_token": token,
                            "delete_token_expires_at": expires_at,
                        }
                    },
                )

                delete_link = url_for(
                    "profil.confirm_delete_account", token=token, _external=True
                )

                try:
                    send_account_deletion_email(
                        to_email=user["email"],
                        username=user["nom"],
                        delete_link=delete_link,
                    )
                    success = (
                        "Un email de confirmation vient de t'être envoyé. "
                        "Clique sur le lien dans cet email pour confirmer la suppression de ton compte."
                    )
                except Exception as e:
                    print("[SUPPRESSION COMPTE] Erreur lors de l'envoi de l'email :", e)
                    erreur = (
                        "Impossible d'envoyer l'email de confirmation pour l'instant. "
                        "Merci de réessayer plus tard."
                    )

        if not erreur:
            user = u_col.find_one({"_id": user["_id"]})
            plan = get_user_plan(user)
            is_plus = plan == "plus"

    pdp_filename = _get_pdp_filename_from_user(user)
    email = user.get("email") or ""
    twofa_enabled = bool(user.get("twofa_enabled", False))

    return render_template(
        "profil.html",
        nom=user["nom"],
        pdp=pdp_filename,
        email=email,
        twofa_enabled=twofa_enabled,
        plan=plan,
        is_plus=is_plus,
        erreur=erreur,
        success=success,
    )


@profil_bp.route("/profil/<userid>")
def profil_public(userid: str):
    if not session.get("util"):
        return redirect(url_for("auth.login"))

    current_nom, current_pdp = _get_current_header_user()
    if not current_nom:
        return redirect(url_for("auth.login"))

    try:
        oid = ObjectId(userid)
    except (InvalidId, TypeError):
        return (
            render_template(
                "profil_public_not_found.html",
                nom=current_nom,
                pdp=current_pdp,
                query=userid,
            ),
            404,
        )

    u = users_col().find_one({"_id": oid})
    if not u:
        return (
            render_template(
                "profil_public_not_found.html",
                nom=current_nom,
                pdp=current_pdp,
                query=userid,
            ),
            404,
        )

    profile_pdp = _get_pdp_filename_from_user(u)
    fields = _build_public_fields(u)

    plan = (u.get("plan") or "free").lower()
    is_plus = plan == "plus"
    is_admin = bool(u.get("is_admin", False))
    banned = bool(u.get("banned", 0))
    muted = u.get("muted", 0)

    return render_template(
        "profil_public.html",
        nom=current_nom,
        pdp=current_pdp,
        profile=u,
        profile_pdp=profile_pdp,
        fields=fields,
        plan=plan,
        is_plus=is_plus,
        is_admin=is_admin,
        banned=banned,
        muted=muted,
    )


@profil_bp.route("/profil/by-name/<pseudo>")
def profil_public_by_name(pseudo: str):
    if not session.get("util"):
        return redirect(url_for("auth.login"))

    pseudo = (pseudo or "").strip()
    if not PSEUDO_REGEX.match(pseudo):
        current_nom, current_pdp = _get_current_header_user()
        return (
            render_template(
                "profil_public_not_found.html",
                nom=current_nom,
                pdp=current_pdp,
                query=pseudo,
            ),
            404,
        )

    u = users_col().find_one({"nom": pseudo})
    if not u:
        current_nom, current_pdp = _get_current_header_user()
        return (
            render_template(
                "profil_public_not_found.html",
                nom=current_nom,
                pdp=current_pdp,
                query=pseudo,
            ),
            404,
        )

    return redirect(url_for("profil.profil_public", userid=str(u["_id"])))


@profil_bp.route("/profil/delete/<token>")
def confirm_delete_account(token: str):
    """
    Route appelée via le lien de confirmation de suppression de compte.
    Supprime le compte si le token est valide et non expiré.
    """
    if not token:
        return "Lien de suppression invalide.", 400

    u_col = users_col()
    user = u_col.find_one({"delete_token": token})
    if not user:
        return "Lien de suppression invalide ou déjà utilisé.", 400

    expires_at = user.get("delete_token_expires_at")
    if not expires_at or expires_at < datetime.utcnow():
        return "Ce lien de suppression a expiré.", 400

    username = user.get("nom")

    try:
        messages_col().delete_many({"author": username})
    except Exception as e:
        print("Erreur suppression messages lors suppression de compte:", e)

    u_col.delete_one({"_id": user["_id"]})

    current_username = session.get("util")
    if current_username == username:
        session.pop("util", None)

    return "Ton compte a bien été supprimé."
