
from flask import session 
import extensions 
from datetime import datetime 

def get_users_col ():
    return extensions .db .utilisateurs 

def get_user_plan (user_doc ):
    """
    Retourne "free" ou "plus".
    Si le plan plus est expiré -> downgrade en base.
    """
    now =datetime .utcnow ()
    plan =user_doc .get ("plan")or "free"

    if plan =="plus":
        exp =user_doc .get ("plan_expires_at")
        if exp is not None and exp <now :
            get_users_col ().update_one (
            {"_id":user_doc ["_id"]},
            {"$set":{"plan":"free","plan_expires_at":None }},
            )
            plan ="free"

    return plan 


def get_message_limit_per_hour (user_doc )->int :
    """
    Limite de messages / heure selon le plan.
      - free : 1000
      - plus : 2000
    """
    plan =get_user_plan (user_doc )
    if plan =="plus":
        return 1000 
    else :
        return 500 


def is_owner (username :str )->bool :
    if not username :
        return False 

    username =username .lower ()

    superadmins ={"tatoudm"}

    if username in superadmins :
        return True 
    else :
        return False 

def is_superadmin ():
    return session .get ("util")=="tatoudm"

def is_proutadmin (username :str )->bool :

    if not username :
        return False 

    username =username .lower ()

    SUPERADMINS_PERMANENTS ={
    "tatoudm",
    }

    SUPERADMINS_TEMP ={
    "chikirin26":datetime (2025 ,12 ,10 ,23 ,59 ,59 ),
    }

    if username in SUPERADMINS_PERMANENTS :
        return True 

    if username in SUPERADMINS_TEMP :
        if datetime .now ()<=SUPERADMINS_TEMP [username ]:
            return True 
        else :
            return False 

    return False 


def is_admin ():
    if is_superadmin ():
        return True 

    username =session .get ("util")
    if not username :
        return False 

    users_col =get_users_col ()
    user =users_col .find_one ({"nom":username })
    if not user :
        return False 

    return bool (user .get ("is_admin",False ))
