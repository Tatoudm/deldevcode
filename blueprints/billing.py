import os
from datetime import datetime, timezone
from app import csrf

import stripe
from bson.objectid import ObjectId
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    current_app,
    abort,
)

import extensions


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_PRICE_ID_PLUS = os.getenv("STRIPE_PRICE_ID_PLUS")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


BASE_PRICE_PLUS_EUR = 5.0

billing_bp = Blueprint("billing", __name__)


def users_col():
    return extensions.db.utilisateurs


def discounts_col():
    return extensions.db.discounts


def require_login():
    """
    Retourne le doc utilisateur si connecté, sinon None.
    (Les routes qui l'utilisent feront la redirection vers /login.)
    """
    if "util" not in session:
        return None

    user = users_col().find_one({"nom": session["util"]})
    if not user:
        session.clear()
        return None

    return user


def get_user_plan(user_doc):
    """
    Retourne le plan de l'utilisateur stocké en DB.
    """
    return user_doc.get("plan", "free")


def get_external_base_url():
    """
    URL publique de ton site pour les callbacks Stripe.
    Tu peux la mettre dans config["EXTERNAL_BASE_URL"] ou dans .env.
    """
    cfg = current_app.config.get("EXTERNAL_BASE_URL")
    if cfg:
        return cfg.rstrip("/")
    env_url = os.getenv("EXTERNAL_BASE_URL")
    if env_url:
        return env_url.rstrip("/")

    return "https://deldevcode.org"


@billing_bp.route("/plus")
def plus_page():
    """
    Page présentant les offres (Gratuit / DelDevCode Plus).
    """
    user = require_login()
    if not user:
        return redirect(url_for("auth.login"))

    plan = get_user_plan(user)

    nom = user["nom"]
    pdp = user.get("pdp", "../static/guest.png")

    return render_template(
        "plus.html",
        nom=nom,
        pdp=pdp,
        plan=plan,
        base_price_plus=BASE_PRICE_PLUS_EUR,
    )


@billing_bp.route("/plus/confirm", methods=["GET", "POST"])
def plus_confirm():
    """
    Page de checkout AVANT Stripe :
      - Résumé de la commande (DelDevCode Plus 5€/an)
      - Champ code promo (optionnel)
      - Bouton "Appliquer le code" (juste un check Stripe côté serveur)
      - Bouton "Payer" qui redirige ensuite vers Stripe Checkout

    On NE contacte pas Stripe pour le paiement ici,
    seulement pour vérifier un éventuel code promo.
    """
    user = require_login()
    if not user:
        return redirect(url_for("auth.login"))
    plan = get_user_plan(user)

    nom = user["nom"]
    pdp = user.get("pdp", "../static/guest.png")

    error = request.args.get("erreur")
    promo_code_value = ""

    if request.method == "POST":

        action = request.form.get("action") or ""
        promo_code_value = (request.form.get("promo_code") or "").strip().upper()

        if action == "apply_code":
            if not promo_code_value:
                error = "Le code de réduction est vide."

                session.pop("plus_promo_id", None)
                session.pop("plus_promo_code", None)
            else:

                try:
                    promos = stripe.PromotionCode.list(
                        code=promo_code_value,
                        active=True,
                        limit=1,
                    )
                    if not promos.data:
                        error = "Code de réduction inconnu ou expiré."
                        session.pop("plus_promo_id", None)
                        session.pop("plus_promo_code", None)
                    else:
                        promo = promos.data[0]

                        session["plus_promo_id"] = promo.id
                        session["plus_promo_code"] = promo_code_value
                except Exception:
                    error = (
                        "Erreur lors de la vérification du code. Réessaie plus tard."
                    )
    else:

        promo_code_value = session.get("plus_promo_code", "") or ""

    has_promo_applied = bool(session.get("plus_promo_id"))

    base_price = BASE_PRICE_PLUS_EUR
    discount_amount = 0.0
    total_price = base_price
    has_auto_discount = False

    now = datetime.now(timezone.utc)
    d_col = discounts_col()

    discount_doc = None

    if has_promo_applied:
        promo_id = session.get("plus_promo_id")
        if promo_id:

            discount_doc = d_col.find_one(
                {
                    "stripe_promotion_code_id": promo_id,
                    "active": True,
                    "products": {"$in": ["plus", "all"]},
                    "valid_from": {"$lte": now},
                    "$or": [
                        {"valid_until": None},
                        {"valid_until": {"$gte": now}},
                    ],
                }
            )
    else:

        discount_doc = d_col.find_one(
            {
                "visibility": "auto",
                "active": True,
                "products": {"$in": ["plus", "all"]},
                "valid_from": {"$lte": now},
                "$or": [
                    {"valid_until": None},
                    {"valid_until": {"$gte": now}},
                ],
            },
            sort=[("created_at", -1)],
        )
        if discount_doc:
            has_auto_discount = True

    if discount_doc:
        dtype = discount_doc.get("discount_type")
        percent_off = discount_doc.get("percent_off")
        new_price_eur = discount_doc.get("new_price_eur")

        if dtype == "percent" and percent_off:
            try:
                p = float(percent_off)
            except (ValueError, TypeError):
                p = 0.0
            if 0 < p < 100:
                discount_amount = round(base_price * p / 100.0, 2)
        elif dtype == "fixed_price" and new_price_eur is not None:
            try:
                np = float(new_price_eur)
            except (ValueError, TypeError):
                np = base_price
            if 0 < np < base_price:
                discount_amount = round(base_price - np, 2)

    if discount_amount < 0:
        discount_amount = 0.0
    total_price = max(0.0, round(base_price - discount_amount, 2))

    return render_template(
        "plus_confirm.html",
        nom=nom,
        pdp=pdp,
        plan=plan,
        error=error,
        promo_code=promo_code_value,
        has_promo_applied=has_promo_applied,
        has_auto_discount=has_auto_discount,
        base_price_plus=base_price,
        discount_amount=discount_amount,
        total_price=total_price,
    )


@billing_bp.route("/plus/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """
    Crée une session Stripe Checkout pour l'abonnement Plus.

    - Applique une réduction par coupon si un PromotionCode a été validé
      dans /plus/confirm (session["plus_promo_id"]).
    - Sinon, applique une réduction automatique si une discount "auto" est active.
    """
    user = require_login()

    if not user:
        return redirect(url_for("auth.login"))

    if not STRIPE_PRICE_ID_PLUS:
        abort(500, "STRIPE_PRICE_ID_PLUS n'est pas configuré")

    base_url = get_external_base_url()

    discounts_for_stripe = []

    promo_id = session.get("plus_promo_id")
    if promo_id:
        discounts_for_stripe.append({"promotion_code": promo_id})
    else:

        now = datetime.now(timezone.utc)

        query = {
            "visibility": "auto",
            "active": True,
            "products": {"$in": ["plus", "all"]},
            "valid_from": {"$lte": now},
            "$or": [
                {"valid_until": None},
                {"valid_until": {"$gte": now}},
            ],
        }

        auto_discount = discounts_col().find_one(
            query,
            sort=[("created_at", -1)],
        )

        if auto_discount and auto_discount.get("stripe_coupon_id"):
            discounts_for_stripe.append({"coupon": auto_discount["stripe_coupon_id"]})

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            customer_email=user.get("email"),
            line_items=[
                {
                    "price": STRIPE_PRICE_ID_PLUS,
                    "quantity": 1,
                }
            ],
            discounts=discounts_for_stripe if discounts_for_stripe else None,
            success_url=base_url + "/plus/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=base_url + "/plus/cancel",
            client_reference_id=str(user["_id"]),
            metadata={
                "user_id": str(user["_id"]),
                "username": user["nom"],
                "plan": "plus",
            },
        )
    except Exception as e:
        current_app.logger.exception("Erreur Stripe create_checkout_session: %s", e)

        return redirect(
            url_for(
                "billing.plus_confirm",
                erreur="Erreur Stripe lors de la création de la session de paiement.",
            )
        )

    session.pop("plus_promo_id", None)
    session.pop("plus_promo_code", None)

    return redirect(checkout_session.url, code=303)


@billing_bp.route("/plus/success")
def plus_success():
    """
    Page affichée après un paiement réussi (Stripe redirige ici).
    Le passage effectif en plan Plus est géré par le webhook Stripe.
    """
    user = require_login()
    if not user:
        return redirect(url_for("auth.login"))
    plan = get_user_plan(user)

    nom = user["nom"]
    pdp = user.get("pdp", "../static/guest.png")

    return render_template(
        "plus_success.html",
        nom=nom,
        pdp=pdp,
        plan=plan,
    )


@billing_bp.route("/plus/cancel")
def plus_cancel():

    user = require_login()
    if not user:
        return redirect(url_for("auth.login"))
    plan = get_user_plan(user)

    nom = user["nom"]
    pdp = user.get("pdp", "../static/guest.png")

    return render_template(
        "plus_cancel.html",
        nom=nom,
        pdp=pdp,
        plan=plan,
    )


@billing_bp.route("/stripe/webhook", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    """
    Réception des événements Stripe.
    On gère au minimum :
      - checkout.session.completed : paiement OK, on passe l'utilisateur en 'plus'
      - customer.subscription.deleted : on repasse en 'free'
      - invoice.payment_failed : on peut repasser en 'free'
    """
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        current_app.logger.error("STRIPE_WEBHOOK_SECRET non configuré")
        return "", 400

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:

        return "", 400
    except stripe.error.SignatureVerificationError:

        return "", 400

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        mode = data_object.get("mode")
        if mode == "subscription":
            user_id_str = data_object.get("client_reference_id") or data_object.get(
                "metadata", {}
            ).get("user_id")
            sub_id = data_object.get("subscription")

            if user_id_str and sub_id:
                try:
                    user_oid = ObjectId(user_id_str)
                except Exception:
                    user_oid = None

                if user_oid:
                    users_col().update_one(
                        {"_id": user_oid},
                        {
                            "$set": {
                                "plan": "plus",
                                "stripe_subscription_id": sub_id,
                                "plan_expires_at": None,
                            }
                        },
                    )

    elif event_type == "customer.subscription.deleted":
        sub_id = data_object.get("id")
        if sub_id:
            users_col().update_one(
                {"stripe_subscription_id": sub_id},
                {
                    "$set": {
                        "plan": "free",
                    },
                    "$unset": {
                        "stripe_subscription_id": "",
                        "plan_expires_at": "",
                    },
                },
            )

    elif event_type == "invoice.payment_failed":
        sub_id = data_object.get("subscription")
        if sub_id:
            users_col().update_one(
                {"stripe_subscription_id": sub_id},
                {
                    "$set": {
                        "plan": "free",
                    },
                    "$unset": {
                        "stripe_subscription_id": "",
                        "plan_expires_at": "",
                    },
                },
            )

    return "", 200
