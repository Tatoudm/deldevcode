# app.py
import os
from datetime import timedelta

from flask import Flask, render_template, session, request
from dotenv import load_dotenv

from extensions import limiter, init_db, sock
import extensions
from werkzeug.exceptions import HTTPException
from flask_wtf.csrf import CSRFProtect

from utils.auth_utils import is_superadmin
from utils.maintenance import is_maintenance_mode

csrf = CSRFProtect()


def get_header_user():
    """
    Récupère (nom, pdp) pour le header, ou (None, None) si non connecté / erreur.
    Utilisable partout (erreurs, maintenance, etc.).
    """
    try:
        if "util" not in session:
            return None, None

        u_col = extensions.db.utilisateurs
        user = u_col.find_one({"nom": session["util"]})
        if not user:
            return None, None

        nom = user["nom"]
        pdp = user.get("pdp", "../static/guest.png")
        return nom, pdp
    except Exception:
        return None, None

def register_error_handlers(app):

    @app.errorhandler(HTTPException)
    def handle_http_error(e: HTTPException):
        code = e.code or 500
        nom, pdp = get_header_user()

        if request.path.startswith("/ws/"):
            raise e

        if code == 404:
            return render_template(
                "error.html",
                code=404,
                title="Vous vous êtes perdu !",
                message="La page que tu cherches n'existe pas ou plus. Peut-être un mauvais lien ou une ancienne page.",
                extra="Pas de panique, clique sur le bouton ci-dessous pour revenir à la maison.",
                show_contact=False,
                home_url="/",
                nom=nom,
                pdp=pdp,
            ), 404

        if code == 403:
            return render_template(
                "error.html",
                code=403,
                title="Accès interdit",
                message="Vous n'avez pas accès à cette page car elle est <strong>INTERDITE</strong> à la population basique. (Si c'est survenu après avoir complété un formulaire réessaie)",
                extra="Si tu penses que c’est une erreur, contacte l’administrateur ou le support pour vérifier tes accès.",
                show_contact=True,
                home_url="/",
                nom=nom,
                pdp=pdp,
            ), 403

        if code == 429:
            return render_template(
                "error.html",
                code=429,
                title="Tu vas un peu trop vite 😅",
                message="Oops, il semblerait que tu spam un peu trop. Attends un petit peu avant de réessayer.",
                extra="C’est juste une protection pour éviter les abus. Reviens dans quelques instants et tout devrait refonctionner.",
                show_contact=False,
                home_url="/",
                nom=nom,
                pdp=pdp,
            ), 429

        if code == 500:
            return render_template(
                "error.html",
                code=500,
                title="Oula… une petite coquille côté serveur",
                message="Tatoudm a sûrement fait une petite coquille quelque part dans le code. 😅",
                extra='Contacte-le à <span class="font-mono">contact@deldevcode.org</span> '
                      "et explique-lui ce que tu faisais pour arriver ici.",
                show_contact=True,
                home_url="/",
                nom=nom,
                pdp=pdp,
            ), 500
        
        if code == 400:
            return render_template(
                "error.html",
                code=400,
                title="Bad request",
                message="Oops, je crois bien que la requete est mal formulée! " \
                "Contacte le support et decrit lui comment tu en es arrivé la. "
                "(Si c'est survenu après avoir complété un formulaire réessaie quelques fois)",
                extra='Contacte-le à <span class="font-mono">contact@deldevcode.org</span> '
                      "et explique-lui ce que tu faisais pour arriver ici.",
                show_contact=True,
                home_url="/",
                nom=nom,
                pdp=pdp,
            ), 400

        # 🔸 Autres erreurs HTTP (400, 401, 502, etc.)
        return render_template(
            "error.html",
            code=code,
            title="Oops, une erreur est survenue !",
            message=f"Une erreur inconnue s'est produite. Voici le code d'erreur : {code}.",
            extra='Réessaye un peu plus tard ou contacte le support à '
                  '<span class="font-mono">contact@deldevcode.org</span>.',
            show_contact=True,
            home_url="/",
            nom=nom,
            pdp=pdp,
        ), code

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        app.logger.exception(e)
        nom, pdp = get_header_user()

        return render_template(
            "error.html",
            code=500,
            title="Oula… une petite coquille côté serveur",
            message="Tatoudm a sûrement fait une petite coquille quelque part dans le code. 😅",
            extra='Contacte-le à <span class="font-mono">contact@deldevcode.org</span> '
                  "et explique-lui ce que tu faisais pour arriver ici.",
            show_contact=True,
            home_url="/",
            nom=nom,
            pdp=pdp,
        ), 500


def create_app():
    load_dotenv()

    app = Flask(__name__)

    # ---------- Secret key ----------
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Vous devez définir FLASK_SECRET_KEY dans le .env")
    app.secret_key = secret_key

    # ---------- Détection environnement ----------
    flask_env = os.environ.get("FLASK_ENV", "prod").lower()
    is_dev = flask_env == "dev"

    # ---------- CSRF ----------
    csrf.init_app(app)

    # Désactiver complètement le CSRF en dev
    app.config["WTF_CSRF_ENABLED"] = not is_dev

    if not is_dev:
        # Config stricte seulement en prod
        app.config["WTF_CSRF_TIME_LIMIT"] = 3600          # Token valable 1h
        app.config["WTF_CSRF_METHODS"] = ["POST", "PUT", "PATCH", "DELETE"]

    print(f"[APP] FLASK_ENV={flask_env} → CSRF actif = {not is_dev}")


    # ---------- Sessions / cookies ----------
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
        "SESSION_COOKIE_SECURE", "0"
    ).lower() in ("1", "true", "yes")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=6)

    # ---------- Init DB ----------
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("Vous devez définir la variable d'environnement MONGO_URI")
    init_db(mongo_uri)

    # ---------- Init du flag maintenance en DB (une seule fois) ----------
    settings_col = extensions.db.site_settings
    initial_flag = os.environ.get("MAINTENANCE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    # On ne set QUE à la création du doc, ensuite c'est toi qui pilotes via /superadmin
    settings_col.update_one(
        {"_id": "maintenance"},
        {"$setOnInsert": {"enabled": initial_flag}},
        upsert=True,
    )

    # ---------- WebSocket ----------
    sock.init_app(app)

    import ws.chat_ws
    import ws.admin_ws 

    # ---------- Index Mongo ----------
    messages_col = extensions.db.messages
    messages_col.create_index(
        [("created_at", 1)],
        expireAfterSeconds=3600,
        partialFilterExpression={"ttl": True},
        name="created_at_1",
    )

    # Index pour les recherches par auteur / date
    messages_col.create_index([("author", 1), ("created_at", -1)])

    # ---------- Rate limiting ----------
    limiter.init_app(app)

    @app.before_request
    def maintenance_check():
        """
        Mode maintenance global :
        - Si le flag DB est activé :
            * /static est autorisé
            * /superadmin est autorisé UNIQUEMENT si superadmin
            * tout le reste -> 503
        - Le handshake WebSocket passe car on fait une exception.
        """
        if request.path.startswith("/ws/"):
            return
        
        if not is_maintenance_mode():
            return
        

        # Assets statiques autorisés
        if request.path.startswith("/static"):
            return

        # Autoriser /superadmin uniquement au superadmin pendant la maintenance
        if request.path.startswith("/superadmin") and is_superadmin():
            return

        nom, pdp = get_header_user()

        return render_template(
            "error.html",
            code=503,
            title="Site en maintenance",
            message="DelDevCode est actuellement en maintenance. Tu ne peux actuellement pas y accéder!",
            extra=(
                "Réessaye un peu plus tard. Si la maintenance dure anormalement longtemps, "
                "tu peux écrire à <span class='font-mono'>contact@deldevcode.org</span>."
            ),
            show_contact=True,
            home_url=None,
            nom=nom,
            pdp=pdp,
        ), 503

    # ---------- Blueprints ----------
    from blueprints.auth import auth_bp
    from blueprints.profil import profil_bp
    from blueprints.chat import chat_bp
    from blueprints.admin import admin_bp
    from blueprints.api import api_bp
    from blueprints.docs import docs_bp
    from blueprints.support import support_bp
    from blueprints.dev import dev_bp
    from blueprints.billing import billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profil_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(dev_bp)
    app.register_blueprint(billing_bp)

    # ---------- Handlers d'erreur custom ----------
    register_error_handlers(app)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=81)
