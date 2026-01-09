
import secrets 
from datetime import datetime 
from blueprints .api import TIER_RATE_LIMITS 
from utils .auth_utils import get_user_plan 

from bson .objectid import ObjectId 
from flask import (
Blueprint ,
render_template ,
request ,
redirect ,
url_for ,
session ,
abort ,
)

import extensions 

dev_bp =Blueprint ("dev",__name__ )

MAX_KEYS_BY_PLAN ={
"free":1 ,
"plus":3 ,
}





def users_col ():
    return extensions .db .utilisateurs 


def api_keys_col ():
    """
    Collection des clés d'API dev.

    Schéma:
    {
        _id: ObjectId,
        owner: "tatoudm",              
        key_hash: "sha256(...)",        
        label: "Clé principale",        
        scopes: ["read:messages"],       
        created_at: datetime,
        last_used_at: datetime | None
    }
    """
    return extensions .db .api_keys 





def get_current_user_info ():
    """
    Pour le header : retourne (nom, pdp, email) ou (None, None, None).
    """
    if "util"not in session :
        return None ,None ,None 

    u =users_col ().find_one ({"nom":session ["util"]})
    if not u :
        session .clear ()
        return None ,None ,None 

    nom =u ["nom"]
    pdp =u .get ("pdp","../static/guest.png")
    email =u .get ("email")
    return nom ,pdp ,email 


def require_login_or_redirect ():
    """
    Récupère l'utilisateur connecté.
    Si pas connecté → redirige vers la page de login (auth.login).
    """
    if "util"not in session :
        try :
            return redirect (url_for ("auth.login",next =request .path ))
        except Exception :
            abort (403 )

    u =users_col ().find_one ({"nom":session ["util"]})
    if not u :
        session .clear ()
        try :
            return redirect (url_for ("auth.login",next =request .path ))
        except Exception :
            abort (403 )

    return u 





@dev_bp .route ("/dev")
def dev_dashboard ():
    """
    Portail développeur.
    - Accessible à tout utilisateur connecté.
    - Affiche la (seule) clé d'API de l'utilisateur s'il en a une.
    - Affiche la doc des endpoints dev.
    """
    user_or_response =require_login_or_redirect ()
    if not isinstance (user_or_response ,dict ):
        return user_or_response 
    user =user_or_response 

    plan =get_user_plan (user )
    max_keys =MAX_KEYS_BY_PLAN .get (plan ,1 )

    current_nom ,current_pdp ,current_email =get_current_user_info ()
    k_col =api_keys_col ()
    cursor =(
    k_col .find ({"owner":user ["nom"]})
    .sort ("created_at",-1 )
    )

    keys =[]
    for k in cursor :
        tier =k .get ("tier","free")
        per_min =k .get ("rate_limit_per_minute")
        if not isinstance (per_min ,int )or per_min <=0 :
            per_min =TIER_RATE_LIMITS .get (tier ,TIER_RATE_LIMITS ["free"])

        keys .append (
        {
        "id":str (k ["_id"]),
        "label":k .get ("label")or "Clé API",
        "scopes":", ".join (k .get ("scopes",[]))or "Aucun",
        "created_at":k .get ("created_at"),
        "last_used_at":k .get ("last_used_at"),
        "tier":tier ,
        "rate_limit_per_minute":per_min ,
        }
        )

    nb_keys =len (keys )
    new_key =request .args .get ("new_key","").strip ()or None 
    error =request .args .get ("error","").strip ()or None 

    return render_template (
    "dev/dev_dashboard.html",
    current_nom =current_nom ,
    current_pdp =current_pdp ,
    current_email =current_email ,
    keys =keys ,
    max_keys =max_keys ,
    nb_keys =nb_keys ,
    new_key =new_key ,
    error =error ,
    )


@dev_bp .route ("/dev/api-keys/create",methods =["POST"])
def dev_create_api_key ():
    """
    Génération d'une nouvelle clé d'API pour l'utilisateur connecté.

    Règles :
    - MAX 1 clé active par utilisateur.
    - Si l'utilisateur a déjà une clé → refuse avec un message d'erreur.
    - Génère une clé aléatoire, stocke seulement le hash.
    - Redirige vers /dev avec ?new_key=... pour afficher la clé une seule fois.
    """
    user_or_response =require_login_or_redirect ()
    if not isinstance (user_or_response ,dict ):
        return user_or_response 
    user =user_or_response 

    k_col =api_keys_col ()


    plan =get_user_plan (user )
    max_keys =MAX_KEYS_BY_PLAN .get (plan ,1 )

    existing_count =k_col .count_documents ({"owner":user ["nom"]})
    if existing_count >=max_keys :
        return redirect (
        url_for (
        "dev.dev_dashboard",
        error =(
        f"Tu as déjà {existing_count } clé(s) API, ce qui est le maximum "
        f"pour ton plan {plan } (max {max_keys })."
        ),
        )
        )


    label =(request .form .get ("label")or "").strip ()
    if not label :
        label ="Clé API"

    raw_key =secrets .token_urlsafe (32 )

    from blueprints .api import hash_api_key 


    key_doc ={
    "owner":user ["nom"],
    "key_hash":hash_api_key (raw_key ),
    "label":label ,
    "scopes":["read:messages"],
    "created_at":datetime .utcnow (),
    "last_used_at":None ,
    "tier":"plus"if plan =="plus"else "free",
    "rate_window_start":None ,
    "rate_count":0 ,
    }


    k_col .insert_one (key_doc )

    return redirect (url_for ("dev.dev_dashboard",new_key =raw_key ))


@dev_bp .route ("/dev/api-keys/revoke/<key_id>",methods =["POST"])
def dev_revoke_api_key (key_id ):
    """
    Révoque la clé d'API appartenant à l'utilisateur connecté.

    Ici :
    - On vérifie que la clé existe et appartient au user.
    - Puis on la SUPPRIME de la BDD (pas de flag revoked).
    """
    user_or_response =require_login_or_redirect ()
    if not isinstance (user_or_response ,dict ):
        return user_or_response 
    user =user_or_response 

    k_col =api_keys_col ()
    try :
        oid =ObjectId (key_id )
    except Exception :
        abort (400 )

    key_doc =k_col .find_one ({"_id":oid })
    if not key_doc :
        abort (404 )

    if key_doc .get ("owner")!=user ["nom"]:
        abort (403 )

    k_col .delete_one ({"_id":oid })

    return redirect (url_for ("dev.dev_dashboard"))
