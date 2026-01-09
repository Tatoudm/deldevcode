
import os 
import json 
import secrets 
import string 
from datetime import datetime ,timedelta 
import stripe 

import bcrypt 
import pytz 
from bson .objectid import ObjectId 
from flask import (
Blueprint ,
render_template ,
request ,
redirect ,
url_for ,
abort ,
session ,
current_app ,
)

import extensions 
from utils .auth_utils import is_admin ,is_superadmin ,is_proutadmin ,is_owner 
from utils .mail_utils import (
parse_name_from_email ,
send_goat_alert ,
send_support_reply_email ,
send_support_status_email ,
)
from ws .chat_ws import connections ,send_to_user ,send_to_channel 

stripe .api_key =os .getenv ("STRIPE_SECRET_KEY")






admin_bp =Blueprint ("admin",__name__ )






def users_col ():
    return extensions .db .utilisateurs 


def messages_col ():
    return extensions .db .messages 


def temp_logins_col ():
    return extensions .db .temp_logins 


def reports_col ():
    return extensions .db .message_reports 


def tickets_col ():
    return extensions .db .support_tickets 


def settings_col ():
    return extensions .db .site_settings 


def warns_col ():
    return extensions .db .warns 


def discounts_col ():
    return extensions .db .discounts 







def get_current_user_info ():
    """
    Retourne (nom, pdp) pour le header si l'utilisateur est connecté.
    """
    try :
        if "util"not in session :
            return None ,None 

        u_col =users_col ()
        user =u_col .find_one ({"nom":session ["util"]})
        if not user :
            return None ,None 

        nom =user ["nom"]
        pdp =user .get ("pdp","../static/guest.png")
        return nom ,pdp 
    except Exception :
        return None ,None 


def build_user_view (user ):
    """
    Formatage générique pour afficher un utilisateur dans les templates admin.
    """
    tz =pytz .timezone ("Europe/Brussels")

    created_at =user .get ("created_at")
    if isinstance (created_at ,datetime ):
        created_local =created_at .astimezone (tz )
        created_str =created_local .strftime ("%d/%m/%Y %H:%M")
    else :
        created_str ="?"

    muted_until =user .get ("muted_until")
    if isinstance (muted_until ,datetime ):
        muted_until_local =muted_until .astimezone (tz )
        muted_until_str =muted_until_local .strftime ("%d/%m/%Y %H:%M")
    else :
        muted_until_str =None 


    plus_active =bool (user .get ("plus_active",False ))
    plus_until =user .get ("plus_until")
    if isinstance (plus_until ,datetime ):
        plus_until_local =plus_until .astimezone (tz )
        plus_until_str =plus_until_local .strftime ("%d/%m/%Y %H:%M")
    else :
        plus_until_str =None 

    return {
    "id":str (user ["_id"]),
    "nom":user .get ("nom"),
    "email":user .get ("email"),
    "pdp":user .get ("pdp","./static/guest.png"),
    "is_admin":bool (user .get ("is_admin")),
    "is_owner":bool (user .get ("is_owner")),

    "created_at":created_str ,
    "created_at_display":created_str ,

    "banned":bool (user .get ("banned")),
    "ban_reason":user .get ("ban_reason"),

    "muted":bool (user .get ("muted")),
    "muted_until":muted_until_str ,
    "muted_until_display":muted_until_str ,

    "warns_count":int (user .get ("warns_count",0 )),
    "last_ip":user .get ("last_ip"),

    "first_name":user .get ("first_name"),
    "last_name":user .get ("last_name"),
    "twofa_enabled":bool (user .get ("twofa_enabled",False )),

    "plan":user .get ("plan","free"),
    }









def get_logs_file_path ():
    """
    Retourne le chemin du fichier de logs admin.
    Par défaut : instance/admin_actions.log
    Peut être override par config["ADMIN_LOG_FILE"].
    """
    path =current_app .config .get ("ADMIN_LOG_FILE")
    if path :
        return path 

    os .makedirs (current_app .instance_path ,exist_ok =True )
    return os .path .join (current_app .instance_path ,"admin_actions.log")


def log_admin_action (actor ,action ,target =None ,details =None ,ip =None ):
    """
    Écrit une ligne JSON dans admin_actions.log
    actor  : pseudo de l'admin
    action : type d'action ("ban", "mute", "warn", "impersonate", etc.)
    target : pseudo ou id du compte ciblé
    details: texte libre (raison, durée, etc.)
    ip     : IP de la requête
    """
    try :
        path =get_logs_file_path ()
        entry ={
        "ts":datetime .utcnow ().isoformat (),
        "actor":actor ,
        "action":action ,
        "target":target ,
        }
        if details :
            entry ["details"]=details 
        if ip :
            entry ["ip"]=ip 

        with open (path ,"a",encoding ="utf-8")as f :
            f .write (json .dumps (entry ,ensure_ascii =False )+"\n")
    except Exception as e :
        print ("Erreur log_admin_action :",e )






@admin_bp .route ("/admin")
def admin_panel ():
    if not is_admin ():
        abort (403 )

    u_col =users_col ()
    mode =request .args .get ("mode","pseudo")
    q =(request .args .get ("q")or "").strip ()

    current_nom ,current_pdp =get_current_user_info ()
    erreur =request .args .get ("erreur")
    message =request .args .get ("message")

    is_superadmin_flag =is_superadmin ()


    users =[]
    if q :
        if mode =="pseudo":
            query ={"nom":{"$regex":q ,"$options":"i"}}
        elif mode =="email":
            query ={"email":{"$regex":q ,"$options":"i"}}
        elif mode =="id":
            try :
                oid =ObjectId (q )
                query ={"_id":oid }
            except Exception :
                query ={"_id":None }
        else :
            query ={"nom":{"$regex":q ,"$options":"i"}}

        cursor =u_col .find (query ).sort ("_id",-1 ).limit (50 )
        for u in cursor :
            if u .get ("nom")=="Serveur"and not is_superadmin ():
                continue 
            users .append (build_user_view (u ))
    else :
        cursor =u_col .find ({}).sort ("_id",-1 ).limit (30 )
        for u in cursor :
            if u .get ("nom")=="Serveur"and not is_superadmin ():
                continue 
            users .append (build_user_view (u ))

    return render_template (
    "admin.html",
    nom =current_nom ,
    pdp =current_pdp ,
    users =users ,
    erreur =erreur ,
    q =q ,
    mode =mode ,
    is_superadmin =is_superadmin_flag ,
    message =message ,
    )

@admin_bp .route ("/admin/discounts/new")
def admin_new_discount ():
    """
    Page complète pour créer une réduction + voir les réductions actives.
    Accès réservé au superadmin.
    """
    if not is_superadmin ():
        abort (403 )

    current_nom ,current_pdp =get_current_user_info ()
    erreur =request .args .get ("erreur")
    message =request .args .get ("message")

    base_price_plus =5.0 

    d_col =discounts_col ()
    active_discounts =[]
    try :
        active_discounts =list (
        d_col .find ({"active":True }).sort ("created_at",-1 )
        )
    except Exception :
        active_discounts =[]

    for d in active_discounts :
        d ["display_code"]=None 
        promo_id =d .get ("stripe_promotion_code_id")
        if d .get ("visibility")=="coupon"and promo_id :
            try :
                promo =stripe .PromotionCode .retrieve (promo_id )
                d ["display_code"]=promo .get ("code")
            except Exception :
                d ["display_code"]=None 

    return render_template (
    "admin_discount_new.html",
    nom =current_nom ,
    pdp =current_pdp ,
    erreur =erreur ,
    message =message ,
    base_price_plus =base_price_plus ,
    active_discounts =active_discounts ,
    )

@admin_bp .route ("/admin/discount/create",methods =["POST"])
def admin_create_discount ():
    """
    Création d'une réduction Stripe :
      - visibility: "coupon" (avec code) ou "auto" (tout le monde)
      - discount_type: "percent" ou "fixed_price"
    """
    if not is_superadmin ():
        abort (403 )

    d_col =discounts_col ()

    visibility =(request .form .get ("visibility")or "coupon").strip ()
    product_scope =(request .form .get ("product_scope")or "plus").strip ()
    discount_type =(request .form .get ("discount_type")or "percent").strip ()

    code =(request .form .get ("code")or "").strip ().upper ()

    percent_str =(request .form .get ("percent_off")or "").strip ()
    fixed_price_str =(request .form .get ("fixed_price_plus")or "").strip ()

    valid_from_str =(request .form .get ("valid_from")or "").strip ()
    valid_until_str =(request .form .get ("valid_until")or "").strip ()
    max_uses_str =(request .form .get ("max_uses")or "").strip ()

    if visibility =="coupon"and not code :
        return redirect (
        url_for (
        "admin.admin_new_discount",
        erreur ="Tu dois saisir un code pour une réduction par coupon.",
        )
        )

    now =datetime .utcnow ()

    def parse_date (s ):
        if not s :
            return None 
        try :
            return datetime .strptime (s ,"%Y-%m-%d")
        except ValueError :
            return None 

    valid_from =parse_date (valid_from_str )or now 
    valid_until =parse_date (valid_until_str )

    max_uses =None 
    if max_uses_str :
        try :
            max_uses =int (max_uses_str )
            if max_uses <=0 :
                max_uses =None 
        except ValueError :
            max_uses =None 

    if product_scope =="all":
        products =["plus"]
    else :
        products =["plus"]

    plus_price_id =os .getenv ("STRIPE_PRICE_ID_PLUS")
    if not plus_price_id :
        return redirect (
        url_for (
        "admin.admin_new_discount",
        erreur ="STRIPE_PRICE_ID_PLUS n'est pas configuré dans .env.",
        )
        )

    try :
        stripe_price =stripe .Price .retrieve (plus_price_id )
    except Exception :
        return redirect (
        url_for (
        "admin.admin_new_discount",
        erreur ="Impossible de récupérer le prix Stripe de Plus.",
        )
        )

    base_amount =stripe_price ["unit_amount"]
    currency =stripe_price ["currency"]

    stripe_coupon =None 
    percent_off =None 
    new_price_eur =None 

    try :
        coupon_args ={}

        if discount_type =="percent":
            try :
                percent_off =float (percent_str )
            except ValueError :
                return redirect (
                url_for (
                "admin.admin_new_discount",
                erreur ="Pourcentage invalide.",
                )
                )

            if percent_off <=0 or percent_off >=100 :
                return redirect (
                url_for (
                "admin.admin_new_discount",
                erreur ="Le pourcentage doit être entre 0 et 100.",
                )
                )

            coupon_args ={
            "percent_off":percent_off ,
            "duration":"forever",
            }

        elif discount_type =="fixed_price":
            try :
                new_price_eur =float (fixed_price_str .replace (",","."))
            except ValueError :
                return redirect (
                url_for (
                "admin.admin_new_discount",
                erreur ="Nouveau prix invalide.",
                )
                )

            if new_price_eur <=0 :
                return redirect (
                url_for (
                "admin.admin_new_discount",
                erreur ="Le prix doit être > 0.",
                )
                )

            new_amount =int (round (new_price_eur *100 ))
            if new_amount >=base_amount :
                return redirect (
                url_for (
                "admin.admin_new_discount",
                erreur ="Le nouveau prix doit être inférieur au prix actuel.",
                )
                )

            amount_off =base_amount -new_amount 

            coupon_args ={
            "amount_off":amount_off ,
            "currency":currency ,
            "duration":"once",
            }

        else :
            return redirect (
            url_for (
            "admin.admin_new_discount",
            erreur ="Type de réduction inconnu.",
            )
            )

        if visibility =="auto"and max_uses is not None :
            coupon_args ["max_redemptions"]=max_uses 
        if valid_until :
            coupon_args ["redeem_by"]=int (valid_until .timestamp ())

        stripe_coupon =stripe .Coupon .create (**coupon_args )

    except Exception as e :
        return redirect (
        url_for (
        "admin.admin_new_discount",
        erreur =f"Erreur Stripe lors de la création du coupon: {e }",
        )
        )



    stripe_coupon_id =stripe_coupon .id if stripe_coupon else None 
    stripe_promo_id =None 

    if visibility =="coupon":
        try :
            promo_args ={
            "promotion":{
            "type":"coupon",
            "coupon":stripe_coupon_id ,
            },
            "code":code ,
            "active":True ,
            }

            if max_uses is not None :
                promo_args ["max_redemptions"]=max_uses 

            if valid_until :
                promo_args ["expires_at"]=int (valid_until .timestamp ())

            promo =stripe .PromotionCode .create (**promo_args )
            stripe_promo_id =promo .id 

        except Exception as e :
            return redirect (
            url_for (
            "admin.admin_new_discount",
            erreur =f"Coupon créé, mais échec création PromotionCode: {e }",
            )
            )


    actor =session .get ("util","inconnu")

    d_col .insert_one (
    {
    "visibility":visibility ,
    "products":products ,
    "discount_type":discount_type ,
    "percent_off":percent_off ,
    "new_price_eur":new_price_eur ,
    "stripe_coupon_id":stripe_coupon_id ,
    "stripe_promotion_code_id":stripe_promo_id ,
    "valid_from":valid_from ,
    "valid_until":valid_until ,
    "max_uses":max_uses ,
    "active":True ,
    "created_at":now ,
    "created_by":actor ,
    }
    )

    log_admin_action (
    actor =actor ,
    action ="create_discount",
    target =stripe_coupon_id ,
    details =f"visibility={visibility }, type={discount_type }, products={products }",
    ip =request .remote_addr or "?",
    )

    return redirect (
    url_for (
    "admin.admin_new_discount",
    message ="Réduction créée avec succès.",
    )
    )

@admin_bp .route ("/admin/discounts/<discount_id>/disable",methods =["POST"])
def admin_disable_discount (discount_id ):
    """
    Désactive une réduction :
      - active=False en DB
      - désactive le PromotionCode Stripe (si présent)
    Réservé au superadmin.
    """
    if not is_superadmin ():
        abort (403 )

    d_col =discounts_col ()
    try :
        oid =ObjectId (discount_id )
    except Exception :
        return redirect (
        url_for ("admin.admin_new_discount",erreur ="ID de réduction invalide.")
        )

    doc =d_col .find_one ({"_id":oid })
    if not doc :
        return redirect (
        url_for ("admin.admin_new_discount",erreur ="Réduction introuvable.")
        )

    promo_id =doc .get ("stripe_promotion_code_id")
    if promo_id :
        try :
            stripe .PromotionCode .modify (promo_id ,active =False )
        except Exception :
            current_app .logger .exception (
            "Erreur Stripe lors de la désactivation du PromotionCode %s",promo_id 
            )

    d_col .update_one (
    {"_id":oid },
    {"$set":{"active":False }},
    )

    actor =session .get ("util","inconnu")
    try :
        log_admin_action (
        actor =actor ,
        action ="disable_discount",
        target =str (discount_id ),
        details =f"visibility={doc .get ('visibility')}, type={doc .get ('discount_type')}",
        ip =request .remote_addr or "?",
        )
    except Exception :
        pass 

    return redirect (
    url_for ("admin.admin_new_discount",message ="Réduction désactivée.")
    )






@admin_bp .route ("/superadmin",methods =["GET","POST"])
def superadmin_panel ():
    username =session .get ("util")
    if not is_proutadmin (username ):
        abort (404 )

    is_superadmin_flag =is_superadmin ()
    current_nom ,current_pdp =get_current_user_info ()
    u_col =users_col ()
    s_col =settings_col ()

    doc =s_col .find_one ({"_id":"maintenance"})or {}
    maintenance_enabled =bool (doc .get ("enabled",False ))

    users =[]
    cursor =u_col .find ({}).sort ("_id",-1 ).limit (20 )
    for u in cursor :
        if u .get ("nom")=="Serveur"and not is_superadmin_flag :
            continue 
        users .append (build_user_view (u ))

    if request .method =="POST":
        action =(request .form .get ("action")or "impersonate").strip ()
        ip =request .remote_addr or "?"

        if action =="toggle_maintenance":
            if not is_owner (username ):
                return render_template (
                "superadmin.html",
                nom =current_nom ,
                pdp =current_pdp ,
                erreur ="Tu n'as pas le droit de modifier le mode maintenance.",
                users =users ,
                maintenance_enabled =maintenance_enabled ,
                is_superadmin =is_superadmin_flag ,
                )

            new_state =request .form .get ("maintenance_enabled")=="on"
            s_col .update_one (
            {"_id":"maintenance"},
            {"$set":{"enabled":new_state }},
            upsert =True ,
            )
            maintenance_enabled =new_state 

            msg =(
            "Maintenance activée : tout le site est maintenant en 503 (sauf toi sur /superadmin)."
            if new_state 
            else "Maintenance désactivée : le site est de nouveau accessible."
            )

            log_admin_action (
            actor =username ,
            action ="toggle_maintenance",
            target =None ,
            details =f"enabled={maintenance_enabled }",
            ip =ip ,
            )

            return render_template (
            "superadmin.html",
            nom =current_nom ,
            pdp =current_pdp ,
            erreur =None ,
            message =msg ,
            users =users ,
            maintenance_enabled =maintenance_enabled ,
            is_superadmin =is_superadmin_flag ,
            )

        ident =(request .form .get ("ident")or "").strip ()
        if not ident :
            return render_template (
            "superadmin.html",
            nom =current_nom ,
            pdp =current_pdp ,
            erreur ="Tu dois indiquer un pseudo ou un email.",
            users =users ,
            maintenance_enabled =maintenance_enabled ,
            is_superadmin =is_superadmin_flag ,
            )

        user =u_col .find_one ({"nom":ident })or u_col .find_one ({"email":ident })
        if not user :
            return render_template (
            "superadmin.html",
            nom =current_nom ,
            pdp =current_pdp ,
            erreur ="Utilisateur introuvable.",
            users =users ,
            maintenance_enabled =maintenance_enabled ,
            is_superadmin =is_superadmin_flag ,
            )

        target_name =user .get ("nom")
        if target_name in ("tatoudm","Serveur","LeGoat")and not is_superadmin_flag :
            return render_template (
            "superadmin.html",
            nom =current_nom ,
            pdp =current_pdp ,
            erreur ="Tu ne peux pas te connecter à la place de ce compte.",
            users =users ,
            maintenance_enabled =maintenance_enabled ,
            is_superadmin =is_superadmin_flag ,
            )

        log_admin_action (
        actor =username ,
        action ="impersonate",
        target =target_name ,
        details =None ,
        ip =ip ,
        )

        session .clear ()
        session ["util"]=user ["nom"]
        session .permanent =True 

        return redirect (url_for ("chat.chat"))

    return render_template (
    "superadmin.html",
    nom =current_nom ,
    pdp =current_pdp ,
    erreur =None ,
    message =None ,
    users =users ,
    maintenance_enabled =maintenance_enabled ,
    is_superadmin =is_superadmin_flag ,
    )






@admin_bp .route ("/superadmin/logs")
def superadmin_logs ():
    if not is_superadmin ():
        abort (404 )

    current_nom ,current_pdp =get_current_user_info ()
    logs =[]

    try :
        path =get_logs_file_path ()
        with open (path ,"r",encoding ="utf-8")as f :
            lines =f .readlines ()[-500 :]
    except FileNotFoundError :
        lines =[]

    tz =pytz .timezone ("Europe/Brussels")

    for line in reversed (lines ):
        line =line .strip ()
        if not line :
            continue 
        try :
            entry =json .loads (line )
        except json .JSONDecodeError :
            continue 

        ts_str =entry .get ("ts")
        local_ts_display =""
        if ts_str :
            try :
                dt =datetime .fromisoformat (ts_str .replace ("Z","+00:00"))
                dt_local =dt .astimezone (tz )
                local_ts_display =dt_local .strftime ("%d/%m/%Y %H:%M:%S")
            except Exception :
                local_ts_display =ts_str 

        logs .append (
        {
        "time":local_ts_display ,
        "actor":entry .get ("actor","?"),
        "action":entry .get ("action",""),
        "target":entry .get ("target"),
        "details":entry .get ("details"),
        "ip":entry .get ("ip"),
        }
        )

    return render_template (
    "superadmin_logs.html",
    nom =current_nom ,
    pdp =current_pdp ,
    logs =logs ,
    )






@admin_bp .route ("/admin/support")
def admin_support_list ():
    if not is_admin ():
        abort (403 )

    t_col =tickets_col ()

    try :
        t_col .delete_many (
        {
        "status":"closed",
        "closed_at":{"$lt":datetime .utcnow ()-timedelta (hours =6 )},
        }
        )
    except Exception as e :
        print ("Erreur nettoyage tickets :",e )

    tz =pytz .timezone ("Europe/Brussels")

    open_tickets =[]
    closed_tickets =[]

    cursor =t_col .find ({}).sort ("created_at",-1 )
    for t in cursor :
        created =t .get ("created_at")
        if isinstance (created ,datetime ):
            created_local =created .astimezone (tz )
            created_at_display =created_local .strftime ("%d/%m/%Y %H:%M")
        else :
            created_at_display ="?"

        ticket_view ={
        "id":str (t ["_id"]),
        "email":t .get ("email"),
        "subject_label":t .get ("subject_label")or t .get ("subject")or "support",
        "title":t .get ("title")or t .get ("subject")or "(Sans titre)",
        "status":t .get ("status","open"),
        "created_at_display":created_at_display ,
        }

        if ticket_view ["status"]=="closed":
            closed_tickets .append (ticket_view )
        else :
            open_tickets .append (ticket_view )

    current_nom ,current_pdp =get_current_user_info ()
    erreur =request .args .get ("erreur")
    message =request .args .get ("message")

    return render_template (
    "admin_support.html",
    nom =current_nom ,
    pdp =current_pdp ,
    open_tickets =open_tickets ,
    closed_tickets =closed_tickets ,
    erreur =erreur ,
    message =message ,
    )


@admin_bp .route ("/admin/support/<ticket_id>")
def admin_support_detail (ticket_id ):
    if not is_admin ():
        abort (403 )

    t_col =tickets_col ()
    try :
        ticket =t_col .find_one ({"_id":ObjectId (ticket_id )})
    except Exception :
        ticket =None 

    if not ticket :
        return redirect (
        url_for (
        "admin.admin_support_list",
        erreur ="Ticket introuvable.",
        )
        )

    tz =pytz .timezone ("Europe/Brussels")

    created =ticket .get ("created_at")
    if isinstance (created ,datetime ):
        created_local =created .astimezone (tz )
        created_at_display =created_local .strftime ("%d/%m/%Y %H:%M")
    else :
        created_at_display ="?"

    last_reply_at =ticket .get ("last_reply_at")
    if isinstance (last_reply_at ,datetime ):
        last_reply_local =last_reply_at .astimezone (tz )
        last_reply_at_display =last_reply_local .strftime ("%d/%m/%Y %H:%M")
    else :
        last_reply_at_display =None 

    ticket_view ={
    "id":str (ticket ["_id"]),
    "email":ticket .get ("email"),
    "title":ticket .get ("title")or ticket .get ("subject")or "(Sans titre)",
    "subject_label":ticket .get ("subject_label")or ticket .get ("subject")or "support",
    "status":ticket .get ("status","open"),
    "created_at_display":created_at_display ,
    "description":ticket .get ("description")or ticket .get ("message")or "",
    "created_by_username":ticket .get ("created_by_username"),
    "last_reply_by":ticket .get ("last_reply_by"),
    "last_reply_at_display":last_reply_at_display ,
    }

    current_nom ,current_pdp =get_current_user_info ()
    erreur =request .args .get ("erreur")
    message =request .args .get ("message")

    return render_template (
    "admin_support_detail.html",
    nom =current_nom ,
    pdp =current_pdp ,
    ticket =ticket_view ,
    erreur =erreur ,
    message =message ,
    )


@admin_bp .route ("/admin/support/<ticket_id>/reply",methods =["POST"])
def admin_support_reply (ticket_id ):
    if not is_admin ():
        abort (403 )

    actor =session .get ("util","inconnu")
    ip =request .remote_addr or "?"

    t_col =tickets_col ()

    try :
        ticket =t_col .find_one ({"_id":ObjectId (ticket_id )})
    except Exception :
        ticket =None 

    if not ticket :
        return redirect (
        url_for (
        "admin.admin_support_list",
        erreur ="Ticket introuvable.",
        )
        )

    reply_body =(request .form .get ("reply_body")or "").strip ()
    reply_subject =(request .form .get ("reply_subject")or "").strip ()
    close_after =request .form .get ("close_after")=="on"

    if not reply_body :
        return redirect (
        url_for (
        "admin.admin_support_detail",
        ticket_id =ticket_id ,
        erreur ="Le message de réponse est vide.",
        )
        )

    email =ticket .get ("email")
    if email :
        try :
            from utils .mail_utils import send_support_reply_email 

            send_support_reply_email (
            to_email =email ,
            subject =reply_subject 
            or f"Réponse à ton ticket : {ticket .get ('title')or ticket .get ('subject')}",
            body =reply_body ,
            author =actor ,
            )
        except Exception as e :
            print ("Erreur envoi mail support reply :",e )

    now =datetime .utcnow ()

    t_col .update_one (
    {"_id":ticket ["_id"]},
    {
    "$set":{
    "last_reply_at":now ,
    "last_reply_by":actor ,
    },
    "$push":{
    "replies":{
    "message":reply_body ,
    "author":actor ,
    "created_at":now ,
    }
    },
    },
    )

    if close_after :
        t_col .update_one (
        {"_id":ticket ["_id"]},
        {"$set":{"status":"closed","closed_at":now }},
        )

        if email :
            try :
                from utils .mail_utils import send_support_status_email 

                send_support_status_email (
                to_email =email ,
                ticket =ticket ,
                action ="closed",
                actor =actor ,
                reason =None ,
                )
            except Exception as e :
                print ("Erreur envoi mail statut support (reply+close) :",e )

    log_admin_action (
    actor =actor ,
    action ="support_reply",
    target =str (ticket ["_id"]),
    details =f"close_after={close_after }",
    ip =ip ,
    )

    return redirect (
    url_for (
    "admin.admin_support_detail",
    ticket_id =ticket_id ,
    message ="Réponse envoyée.",
    )
    )


@admin_bp .route ("/admin/support/<ticket_id>/close",methods =["POST"])
def admin_support_close (ticket_id ):
    if not is_admin ():
        abort (403 )

    actor =session .get ("util","inconnu")
    ip =request .remote_addr or "?"

    t_col =tickets_col ()
    try :
        ticket =t_col .find_one ({"_id":ObjectId (ticket_id )})
    except Exception :
        ticket =None 

    if not ticket :
        return redirect (
        url_for (
        "admin.admin_support_list",
        erreur ="Ticket introuvable.",
        )
        )

    close_reason =(request .form .get ("close_reason")or "").strip ()or None 
    now =datetime .utcnow ()

    t_col .update_one (
    {"_id":ticket ["_id"]},
    {"$set":{"status":"closed","closed_at":now ,"close_reason":close_reason }},
    )

    email =ticket .get ("email")
    if email :
        try :
            from utils .mail_utils import send_support_status_email 

            send_support_status_email (
            to_email =email ,
            ticket =ticket ,
            action ="closed",
            actor =actor ,
            reason =close_reason ,
            )
        except Exception as e :
            print ("Erreur envoi mail statut support (close) :",e )

    log_admin_action (
    actor =actor ,
    action ="support_close",
    target =str (ticket ["_id"]),
    details =f"reason={close_reason }",
    ip =ip ,
    )

    return redirect (
    url_for (
    "admin.admin_support_detail",
    ticket_id =ticket_id ,
    message ="Ticket fermé.",
    )
    )


@admin_bp .route ("/admin/support/<ticket_id>/reopen",methods =["POST"])
def admin_support_reopen (ticket_id ):
    if not is_admin ():
        abort (403 )

    actor =session .get ("util","inconnu")
    ip =request .remote_addr or "?"

    t_col =tickets_col ()
    try :
        ticket =t_col .find_one ({"_id":ObjectId (ticket_id )})
    except Exception :
        ticket =None 

    if not ticket :
        return redirect (
        url_for (
        "admin.admin_support_list",
        erreur ="Ticket introuvable.",
        )
        )

    t_col .update_one (
    {"_id":ticket ["_id"]},
    {"$set":{"status":"open","closed_at":None }},
    )

    email =ticket .get ("email")
    if email :
        try :
            from utils .mail_utils import send_support_status_email 

            send_support_status_email (
            to_email =email ,
            ticket =ticket ,
            action ="reopened",
            actor =actor ,
            reason =None ,
            )
        except Exception as e :
            print ("Erreur envoi mail statut support (reopen) :",e )

    log_admin_action (
    actor =actor ,
    action ="support_reopen",
    target =str (ticket ["_id"]),
    details =None ,
    ip =ip ,
    )

    return redirect (
    url_for (
    "admin.admin_support_detail",
    ticket_id =ticket_id ,
    message ="Ticket rouvert.",
    )
    )


@admin_bp .route ("/admin/support/<ticket_id>/delete",methods =["POST"])
def admin_support_delete (ticket_id ):
    if not is_admin ():
        abort (403 )

    actor =session .get ("util","inconnu")
    ip =request .remote_addr or "?"

    t_col =tickets_col ()
    try :
        ticket =t_col .find_one ({"_id":ObjectId (ticket_id )})
    except Exception :
        ticket =None 

    if ticket :
        t_col .delete_one ({"_id":ticket ["_id"]})

    log_admin_action (
    actor =actor ,
    action ="support_delete",
    target =ticket_id ,
    details =None ,
    ip =ip ,
    )

    return redirect (
    url_for (
    "admin.admin_support_list",
    message ="Ticket supprimé.",
    )
    )






@admin_bp .route ("/admin/user/<user_id>")
def admin_user_detail (user_id ):
    if not is_admin ():
        abort (403 )

    u_col =users_col ()
    try :
        user =u_col .find_one ({"_id":ObjectId (user_id )})
    except Exception :
        user =None 

    if not user :
        return redirect (
        url_for (
        "admin.admin_panel",
        erreur ="Utilisateur introuvable.",
        )
        )

    is_superadmin_flag =is_superadmin ()
    if user .get ("nom")=="Serveur"and not is_superadmin_flag :
        abort (404 )

    current_nom ,current_pdp =get_current_user_info ()
    user_view =build_user_view (user )

    can_manage =True 
    if user .get ("nom")in ("tatoudm","Serveur")and current_nom !="tatoudm":
        can_manage =False 

    warnings =[]
    try :
        w_col =warns_col ()
        tz =pytz .timezone ("Europe/Brussels")
        cursor =w_col .find ({"user":user .get ("nom")}).sort ("created_at",-1 )
        for w in cursor :
            created_at =w .get ("created_at")
            if isinstance (created_at ,datetime ):
                local_dt =created_at .astimezone (tz )
                created_display =local_dt .strftime ("%d/%m/%Y %H:%M")
            else :
                created_display ="?"

            warnings .append (
            {
            "created_at_display":created_display ,
            "moderator":w .get ("moderator")or "?",
            "reason":w .get ("reason")or "",
            }
            )
    except Exception :
        warnings =[]

    return render_template (
    "admin_user.html",
    nom =current_nom ,
    pdp =current_pdp ,
    user =user_view ,
    erreur =None ,
    message =None ,
    is_superadmin =is_superadmin_flag ,
    can_manage =can_manage ,
    warnings =warnings ,
    )




@admin_bp .route ("/admin/user/<user_id>/update",methods =["POST"])
def admin_update_user (user_id ):
    if not is_admin ():
        abort (403 )

    u_col =users_col ()
    try :
        user =u_col .find_one ({"_id":ObjectId (user_id )})
    except Exception :
        user =None 

    if not user :
        return redirect (
        url_for (
        "admin.admin_panel",
        erreur ="Utilisateur introuvable.",
        )
        )


    new_email =(request .form .get ("email")or "").strip ()
    new_pdp =(request .form .get ("pdp")or "").strip ()

    update ={}
    if new_email :
        update ["email"]=new_email 
    if new_pdp :
        update ["pdp"]=new_pdp 

    if update :
        u_col .update_one ({"_id":user ["_id"]},{"$set":update })

    log_admin_action (
    actor =session .get ("util","inconnu"),
    action ="update_user",
    target =user .get ("nom"),
    details =f"fields={list (update .keys ())}",
    ip =request .remote_addr or "?",
    )

    return redirect (url_for ("admin.admin_user_detail",user_id =user_id ))






@admin_bp .route ("/admin/user/<user_id>/create_temp_login",methods =["POST"])
def admin_create_temp_login (user_id ):
    """
    Crée un accès spécial temporaire (6h) pour un compte.
    Réservé au superadmin (tatoudm).
    """
    if not is_superadmin ():
        abort (403 )

    u_col =users_col ()
    try :
        user =u_col .find_one ({"_id":ObjectId (user_id )})
    except Exception :
        user =None 

    if not user :
        return redirect (
        url_for (
        "admin.admin_panel",
        erreur ="Utilisateur introuvable.",
        )
        )


    token ="".join (
    secrets .choice (string .ascii_letters +string .digits )for _ in range (32 )
    )

    expires_at =datetime .utcnow ()+timedelta (hours =6 )
    t_col =temp_logins_col ()

    t_col .insert_one (
    {
    "user_id":user ["_id"],
    "username":user .get ("nom"),
    "token":token ,
    "created_at":datetime .utcnow (),
    "expires_at":expires_at ,
    "created_by":session .get ("util","inconnu"),
    }
    )

    log_admin_action (
    actor =session .get ("util","inconnu"),
    action ="create_temp_login",
    target =user .get ("nom"),
    details ="duration=6h",
    ip =request .remote_addr or "?",
    )


    return redirect (
    url_for (
    "admin.admin_user_detail",
    user_id =user_id ,
    )
    )






@admin_bp .route ("/admin/user_action",methods =["POST"])
def admin_user_action ():
    if not is_admin ():
        abort (403 )

    u_col =users_col ()
    actor =session .get ("util","inconnu")
    ip =request .remote_addr or "?"

    action =(request .form .get ("action")or "").strip ()
    redirect_to =request .form .get ("redirect_to")

    user_id =(request .form .get ("user_id")or "").strip ()
    username_field =(request .form .get ("username")or "").strip ()

    user =None 

    if user_id :
        try :
            user =u_col .find_one ({"_id":ObjectId (user_id )})
        except Exception :
            user =None 

    if user is None and username_field :
        user =u_col .find_one ({"nom":username_field })

    if not user or not action :
        if redirect_to :
            return redirect (
            url_for (
            "admin.admin_panel",
            erreur ="Requête invalide.",
            )
            )
        return redirect (
        url_for (
        "admin.admin_panel",
        erreur ="Requête invalide.",
        )
        )

    username =user .get ("nom")

    if username =="tatoudm":
        if action in ("mute","ban","delete"):
            send_goat_alert (action ,actor )
            log_admin_action (
            actor =actor ,
            action ="forbidden_action",
            target =username ,
            details =f"action={action }",
            ip =ip ,
            )
            return redirect (
            url_for (
            "admin.admin_panel",
            q =username ,
            mode ="pseudo",
            erreur ="Impossible de toucher à la plus goatesque...",
            )
            )

    if username =="Serveur"and not is_superadmin ():
        log_admin_action (
        actor =actor ,
        action ="forbidden_action",
        target =username ,
        details =f"action={action }",
        ip =ip ,
        )
        return redirect (
        url_for (
        "admin.admin_panel",
        q =username ,
        mode ="pseudo",
        erreur ="Tu ne peux pas agir sur le compte Serveur.",
        )
        )

    if action =="make_admin":
        u_col .update_one ({"_id":user ["_id"]},{"$set":{"is_admin":True }})
        log_admin_action (actor ,"make_admin",target =username ,details =None ,ip =ip )

    elif action =="remove_admin":
        u_col .update_one ({"_id":user ["_id"]},{"$set":{"is_admin":False }})
        log_admin_action (actor ,"remove_admin",target =username ,details =None ,ip =ip )

    elif action =="mute":
        minutes_str =(
        (request .form .get ("minutes")or "").strip ()
        or (request .form .get ("duration")or "").strip ()
        )
        try :
            minutes =int (minutes_str )
        except ValueError :
            minutes =0 

        if minutes <=0 :
            minutes =30 


        mute_reason =(
        (request .form .get ("reason")or "").strip ()
        or (request .form .get ("mute_reason")or "").strip ()
        )

        muted_until =datetime .utcnow ()+timedelta (minutes =minutes )
        u_col .update_one (
        {"_id":user ["_id"]},
        {
        "$set":{
        "muted":1 ,
        "muted_until":muted_until ,
        "muted_by":actor ,
        "muted_reason":mute_reason ,
        }
        },
        )

        log_admin_action (
        actor =actor ,
        action ="mute",
        target =username ,
        details =f"minutes={minutes }, reason={mute_reason }",
        ip =ip ,
        )

    elif action =="unmute":
        u_col .update_one (
        {"_id":user ["_id"]},
        {
        "$set":{
        "muted":0 ,
        "muted_until":None ,
        "muted_by":None ,
        "muted_reason":None ,
        }
        },
        )
        log_admin_action (actor ,"unmute",target =username ,details =None ,ip =ip )

    elif action =="warn":
        warn_reason =(request .form .get ("reason")or "").strip ()
        now =datetime .utcnow ()

        w_col =warns_col ()
        w_col .insert_one (
        {
        "user":username ,
        "reason":warn_reason ,
        "moderator":actor ,
        "created_at":now ,
        }
        )

        current_warns =int (user .get ("warns_count",0 ))+1 
        u_col .update_one (
        {"_id":user ["_id"]},{"$set":{"warns_count":current_warns }}
        )

        log_admin_action (
        actor =actor ,
        action ="warn",
        target =username ,
        details =f"reason={warn_reason }",
        ip =ip ,
        )

    elif action =="ban":
        reason =(request .form .get ("reason")or "").strip ()
        u_col .update_one (
        {"_id":user ["_id"]},
        {"$set":{"banned":1 ,"ban_reason":reason }},
        )

        log_admin_action (
        actor =actor ,
        action ="ban",
        target =username ,
        details =f"reason={reason }",
        ip =ip ,
        )

    elif action =="unban":
        u_col .update_one (
        {"_id":user ["_id"]},
        {"$set":{"banned":0 ,"ban_reason":None }},
        )
        log_admin_action (actor ,"unban",target =username ,details =None ,ip =ip )

    elif action =="delete":
        u_col .delete_one ({"_id":user ["_id"]})
        log_admin_action (actor ,"delete_user",target =username ,details =None ,ip =ip )

    elif action =="give_plus":
        if not is_superadmin ():
            log_admin_action (
            actor =actor ,
            action ="forbidden_action",
            target =username ,
            details ="action=give_plus (non superadmin)",
            ip =ip ,
            )
            if redirect_to :
                return redirect (redirect_to )
            return redirect (
            url_for (
            "admin.admin_panel",
            q =username ,
            mode ="pseudo",
            erreur ="Seul le superadmin peut donner Plus.",
            )
            )

        u_col .update_one (
        {"_id":user ["_id"]},
        {
        "$set":{
        "plan":"plus",
        }
        },
        )

        log_admin_action (
        actor =actor ,
        action ="give_plus",
        target =username ,
        details =None ,
        ip =ip ,
        )

    elif action =="remove_plus":
        if not is_superadmin ():
            log_admin_action (
            actor =actor ,
            action ="forbidden_action",
            target =username ,
            details ="action=remove_plus (non superadmin)",
            ip =ip ,
            )
            if redirect_to :
                return redirect (redirect_to )
            return redirect (
            url_for (
            "admin.admin_panel",
            q =username ,
            mode ="pseudo",
            erreur ="Seul le superadmin peut retirer Plus.",
            )
            )

        u_col .update_one (
        {"_id":user ["_id"]},
        {
        "$set":{
        "plan":"free",
        }
        },
        )

        log_admin_action (
        actor =actor ,
        action ="remove_plus",
        target =username ,
        details =None ,
        ip =ip ,
        )


    else :
        log_admin_action (
        actor =actor ,
        action ="unknown_action",
        target =username ,
        details =f"action={action }",
        ip =ip ,
        )

    if redirect_to :
        return redirect (redirect_to )

    return redirect (
    url_for (
    "admin.admin_panel",
    q =username ,
    mode ="pseudo",
    )
    )







@admin_bp .route ("/admin/create_user",methods =["POST"])
def admin_create_user ():
    if not is_admin ():
        abort (403 )

    u_col =users_col ()

    email =(request .form .get ("email")or "").strip ()
    nom =(request .form .get ("nom")or "").strip ()
    make_admin =request .form .get ("make_admin")=="on"

    if not email :
        return redirect (
        url_for (
        "admin.admin_panel",
        erreur ="Email obligatoire pour créer un utilisateur.",
        )
        )

    if not nom :
        nom =parse_name_from_email (email )


    raw_password ="".join (
    secrets .choice (string .ascii_letters +string .digits )for _ in range (10 )
    )
    hashed =bcrypt .hashpw (raw_password .encode ("utf-8"),bcrypt .gensalt ())

    user_doc ={
    "nom":nom ,
    "email":email ,
    "password":hashed ,
    "created_at":datetime .utcnow (),
    "is_admin":make_admin ,
    "banned":0 ,
    "warns_count":0 ,
    "muted":0 ,
    }

    u_col .insert_one (user_doc )

    log_admin_action (
    actor =session .get ("util","inconnu"),
    action ="create_user",
    target =nom ,
    details =f"email={email }, is_admin={make_admin }",
    ip =request .remote_addr or "?",
    )

    return redirect (url_for ("admin.admin_panel",q =nom ,mode ="pseudo"))






@admin_bp .route ("/admin/messages")
def admin_messages ():
    if not is_admin ():
        abort (403 )

    current_nom ,current_pdp =get_current_user_info ()
    erreur =request .args .get ("erreur")
    message =request .args .get ("message")

    return render_template (
    "admin_messages.html",
    nom =current_nom ,
    pdp =current_pdp ,
    erreur =erreur ,
    message =message ,
    )


@admin_bp .route ("/admin/user/by-name/<nom>")
def admin_user_by_name (nom ):
    if not is_admin ():
        abort (403 )
    return redirect (url_for ("admin.admin_panel",q =nom ,mode ="pseudo"))


@admin_bp .route ("/admin/messages/manage")
def admin_messages_manage ():
    if not is_admin ():
        abort (403 )

    current_nom ,current_pdp =get_current_user_info ()

    return render_template (
    "admin_messages_manage.html",
    nom =current_nom ,
    pdp =current_pdp ,
    )


@admin_bp .route ("/admin/delete_message",methods =["POST"])
def admin_delete_message ():
    if not is_admin ():
        abort (403 )

    m_col =messages_col ()
    r_col =reports_col ()

    msg_id =request .form .get ("message_id")
    redirect_to =request .form .get ("redirect_to")or url_for ("admin.admin_messages")

    if not msg_id :
        return redirect (
        url_for (
        "admin.admin_messages",
        erreur ="ID du message manquant.",
        )
        )

    try :
        msg =m_col .find_one ({"_id":ObjectId (msg_id )})
    except Exception :
        msg =None 

    if msg :
        m_col .delete_one ({"_id":msg ["_id"]})
        r_col .delete_many ({"message_id":msg ["_id"]})

        channel =msg .get ("channel","general")
        send_to_channel (
        channel ,
        {
        "type":"message_deleted",
        "message_id":str (msg ["_id"]),
        },
        )

        log_admin_action (
        actor =session .get ("util","inconnu"),
        action ="delete_message",
        target =str (msg ["_id"]),
        details =f"author={msg .get ('author')}",
        ip =request .remote_addr or "?",
        )

    return redirect (redirect_to )