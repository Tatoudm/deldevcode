
import os 
import time 
import random 
import string 
from datetime import datetime 

import bcrypt 
from flask import Blueprint ,render_template ,request ,redirect ,url_for ,session 

from extensions import limiter 
import extensions 
from utils .mail_utils import parse_name_from_email ,send_verification_email 

auth_bp =Blueprint ("auth",__name__ )

EMAIL_REQUIRED =os .environ .get ("EMAIL_REQUIRED","0").lower ()in ("1","true","yes")


def users_col ():
    return extensions .db .utilisateurs 


def pending_reg_col ():
    return extensions .db .pending_registrations 


def pending_login_col ():
    return extensions .db .pending_logins 


def temp_logins_col ():
    return extensions .db .temp_logins 



@auth_bp .route ("/register",methods =["GET","POST"])
@limiter .limit ("5 per minute")
def register ():
    if "util"in session :
        return redirect (url_for ("chat.index"))

    u_col =users_col ()
    p_col =pending_reg_col ()

    if request .method =="POST":
        username =request .form ["user"].strip ()
        pswd =request .form ["password"]
        confirm =request .form ["confirm_password"]
        email =request .form .get ("email","").strip ().lower ()

        if email =="67"and pswd =="67"and confirm =="67"and username =="67":
            print ()
            return render_template ("register.html",warn_msg ="67",warn_nbr =67 ,erreur ="67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67 67")

        if email =="67"or pswd =="67"or confirm =="67"or username =="67":
            return render_template ("register.html",erreur ="Termine au moins ce que t'as commencé... Non mais juste un, deux, ou trois 67 et puis quoi encore...")
        if EMAIL_REQUIRED and email =="":
            return render_template ("register.html",erreur ="L'adresse email est obligatoire")

        if email and not email .endswith ("@providencechampion.be"):
            return render_template ("register.html",erreur ="Seules les adresses @providencechampion.be sont acceptées.")

        if email and u_col .find_one ({"email":email }):
            return render_template ("register.html",erreur ="Cette adresse email est déjà utilisée")

        if len (username )<3 :
            return render_template ("register.html",erreur ="Le nom d'utilisateur doit faire au moins 3 caractères")

        if u_col .find_one ({"nom":username }):
            return render_template ("register.html",erreur ="Nom d'utilisateur déjà utilisé")

        p_col .delete_many ({"nom":username })

        if not (any (c .isdigit ()for c in pswd )and len (pswd )>=8 ):
            return render_template (
            "register.html",
            erreur ="Le mot de passe doit faire 8 caractères minimum et contenir au moins 1 chiffre",
            )

        if pswd !=confirm :
            return render_template ("register.html",erreur ="Les mots de passe ne sont pas identiques")

        if email !="":
            code ="".join (random .choices (string .digits ,k =6 ))

            mdp_encrypte =bcrypt .hashpw (pswd .encode ("utf-8"),bcrypt .gensalt ())
            code_hash =bcrypt .hashpw (code .encode ("utf-8"),bcrypt .gensalt ())

            first_name ,last_name =parse_name_from_email (email )

            p_col .insert_one (
            {
            "nom":username ,
            "mdp":mdp_encrypte ,
            "email":email ,
            "pdp":"guest.png",
            "code_hash":code_hash ,
            "created_at":time .time (),
            "attempts":0 ,
            "first_name":first_name ,
            "last_name":last_name ,
            }
            )

            session ["pending_username"]=username 

            try :
                send_verification_email (email ,code )
            except Exception as e :
                print ("Erreur envoi mail:",e )
                p_col .delete_many ({"nom":username })
                session .pop ("pending_username",None )
                return render_template (
                "register.html",
                erreur ="Impossible d'envoyer l'email de vérification pour le moment",
                )

            return redirect (url_for ("auth.verify_email"))

    return render_template ("register.html")


@auth_bp .route ("/verify_email",methods =["GET","POST"])
@limiter .limit ("3 per minute")
def verify_email ():
    u_col =users_col ()
    p_col =pending_reg_col ()

    username =session .get ("pending_username")
    if not username :
        return redirect (url_for ("auth.register"))

    pending =p_col .find_one ({"nom":username })
    if not pending :
        session .pop ("pending_username",None )
        return redirect (url_for ("auth.register"))

    now =time .time ()
    created_at =pending .get ("created_at",now )
    if now -created_at >600 :
        p_col .delete_one ({"_id":pending ["_id"]})
        session .pop ("pending_username",None )
        return render_template (
        "register.html",
        erreur ="Le code a expiré (plus de 10 minutes), veuillez recommencer l'inscription.",
        )

    attempts =pending .get ("attempts",0 )
    if attempts >=5 :
        p_col .delete_one ({"_id":pending ["_id"]})
        session .pop ("pending_username",None )
        return render_template (
        "register.html",
        erreur ="Trop de tentatives de code, veuillez recommencer l'inscription.",
        )

    if request .method =="POST":
        code_saisi =request .form .get ("code","").strip ()

        if bcrypt .checkpw (code_saisi .encode ("utf-8"),pending ["code_hash"]):
            u_col .insert_one (
            {
            "nom":pending ["nom"],
            "mdp":pending ["mdp"],
            "pdp":"../static/guest.png",
            "email":pending ["email"],
            "first_name":pending .get ("first_name"),
            "last_name":pending .get ("last_name"),
            "is_admin":False ,
            "twofa_enabled":False ,
            "banned":0 ,
            "ban_reason":None ,
            }
            )

            p_col .delete_one ({"_id":pending ["_id"]})
            session .pop ("pending_username",None )

            session .clear ()
            session ["util"]=pending ["nom"]
            session .permanent =True 
            return redirect (url_for ("chat.chat"))
        else :
            p_col .update_one ({"_id":pending ["_id"]},{"$inc":{"attempts":1 }})
            return render_template ("verify_email.html",erreur ="Code incorrect.")

    return render_template ("verify_email.html")

@auth_bp .route ("/resend_email_code",methods =["POST"])
@limiter .limit ("3 per minute")
def resend_email_code ():
    u_col =users_col ()
    p_col =pending_reg_col ()

    username =session .get ("pending_username")
    if not username :

        return redirect (url_for ("auth.register"))

    pending =p_col .find_one ({"nom":username })
    if not pending :

        session .pop ("pending_username",None )
        return redirect (url_for ("auth.register"))

    email =pending .get ("email")
    if not email :

        session .pop ("pending_username",None )
        p_col .delete_many ({"nom":username })
        return redirect (url_for ("auth.register"))


    code ="".join (random .choices (string .digits ,k =6 ))
    code_hash =bcrypt .hashpw (code .encode ("utf-8"),bcrypt .gensalt ())


    p_col .update_one (
    {"_id":pending ["_id"]},
    {
    "$set":{
    "code_hash":code_hash ,
    "created_at":time .time (),
    "attempts":0 ,
    }
    },
    )

    try :
        send_verification_email (email ,code )
    except Exception as e :
        print ("Erreur renvoi mail vérif:",e )
        session .pop ("pending_username",None )
        p_col .delete_many ({"nom":username })
        return render_template (
        "register.html",
        erreur ="Impossible de renvoyer le code pour le moment, merci de recommencer l'inscription plus tard.",
        )

    return redirect (url_for ("auth.verify_email"))



@auth_bp .route ("/logout")
def logout ():
    session .clear ()
    return redirect (url_for ("chat.index"))


@auth_bp .route ("/login",methods =["GET","POST"])
@limiter .limit ("5 per minute")
def login ():
    if "util"in session :
        return redirect (url_for ("chat.chat"))

    u_col =users_col ()
    pl_col =pending_login_col ()
    t_col =temp_logins_col ()

    if request .method =="POST":
        username =request .form ["user"].strip ()
        pswd =request .form ["password"]

        util =u_col .find_one ({"nom":username })

        if util :
            if util .get ("banned",0 )==1 :
                ban_reason =util .get ("ban_reason")
                if ban_reason :
                    msg =f"Vous avez été banni pour : {ban_reason }"+'(<a class="text-emerald-600 underline-offset-2 hover:underline" href="/docs/pourquoi-ban">en savoir plus</a>)'
                else :
                    msg ="Vous avez été banni."
                return render_template ("login.html",erreur =msg )

            pswd_hash =util ["mdp"]
            if bcrypt .checkpw (pswd .encode ("utf-8"),pswd_hash ):
                twofa_enabled =util .get ("twofa_enabled",False )
                user_email =util .get ("email")

                if twofa_enabled and user_email :
                    pl_col .delete_many ({"nom":username })

                    code ="".join (random .choices (string .digits ,k =6 ))
                    code_hash =bcrypt .hashpw (code .encode ("utf-8"),bcrypt .gensalt ())

                    pl_col .insert_one (
                    {
                    "nom":username ,
                    "code_hash":code_hash ,
                    "created_at":time .time (),
                    "attempts":0 ,
                    }
                    )
                    session ["pending_2fa_username"]=username 

                    try :
                        send_verification_email (user_email ,code )
                    except Exception as e :
                        print ("Erreur envoi mail A2F:",e )
                        pl_col .delete_many ({"nom":username })
                        session .pop ("pending_2fa_username",None )
                        return render_template (
                        "login.html",
                        erreur ="Impossible d'envoyer le code A2F pour le moment.",
                        )

                    return redirect (url_for ("auth.verify_login_2fa"))

                session .clear ()
                session ["util"]=username 
                session .permanent =True 
                return redirect (url_for ("chat.chat"))
            else :
                return render_template ("login.html",erreur ="Identifiants incorrect")

        temp_login =t_col .find_one ({"temp_username":username })
        if temp_login :
            expires_at =temp_login .get ("expires_at")
            if not expires_at or expires_at <datetime .utcnow ():
                return render_template ("login.html",erreur ="Cet accès spécial a expiré.")

            temp_pw_hash =temp_login ["temp_password_hash"]
            if not bcrypt .checkpw (pswd .encode ("utf-8"),temp_pw_hash ):
                return render_template ("login.html",erreur ="Identifiants incorrect")

            target_username =temp_login .get ("target_username")
            target_user =u_col .find_one ({"nom":target_username })

            if not target_user :
                return render_template (
                "login.html",
                erreur ="Cet accès spécial pointe vers un compte inexistant.",
                )

            if target_user .get ("banned",0 )==1 :
                ban_reason =target_user .get ("ban_reason")
                if ban_reason :
                    msg =f"Vous avez été banni pour : {ban_reason }"
                else :
                    msg ="Vous avez été banni."
                return render_template ("login.html",erreur =msg )

            session .clear ()
            session ["util"]=target_user ["nom"]
            session .permanent =True 
            return redirect (url_for ("chat.chat"))

        return render_template ("login.html",erreur ="Identifiants incorrect")

    return render_template ("login.html")



@auth_bp .route ("/verify_login_2fa",methods =["GET","POST"])
@limiter .limit ("5 per minute")
def verify_login_2fa ():
    u_col =users_col ()
    pl_col =pending_login_col ()

    username =session .get ("pending_2fa_username")
    if not username :
        return redirect (url_for ("auth.login"))

    pending =pl_col .find_one ({"nom":username })
    if not pending :
        session .pop ("pending_2fa_username",None )
        return redirect (url_for ("auth.login"))

    now =time .time ()
    created_at =pending .get ("created_at",now )

    if now -created_at >600 :
        pl_col .delete_one ({"_id":pending ["_id"]})
        session .pop ("pending_2fa_username",None )
        return render_template ("login.html",erreur ="Le code A2F a expiré, veuillez vous reconnecter.")

    attempts =pending .get ("attempts",0 )
    if attempts >=5 :
        pl_col .delete_one ({"_id":pending ["_id"]})
        session .pop ("pending_2fa_username",None )
        return render_template ("login.html",erreur ="Trop de tentatives de code A2F, veuillez vous reconnecter.")

    if request .method =="POST":
        code_saisi =request .form .get ("code","").strip ()

        if bcrypt .checkpw (code_saisi .encode ("utf-8"),pending ["code_hash"]):
            pl_col .delete_one ({"_id":pending ["_id"]})
            session .pop ("pending_2fa_username",None )

            util =u_col .find_one ({"nom":username })
            if not util or util .get ("banned",0 )==1 :
                return render_template ("login.html",erreur ="Connexion impossible, compte invalide ou banni.")

            session .clear ()
            session ["util"]=username 
            session .permanent =True 
            return redirect (url_for ("chat.chat"))
        else :
            pl_col .update_one ({"_id":pending ["_id"]},{"$inc":{"attempts":1 }})
            return render_template ("verify_login_2fa.html",erreur ="Code incorrect.")

    return render_template ("verify_login_2fa.html")

@auth_bp .route ("/resend_login_2fa",methods =["POST"])
@limiter .limit ("3 per minute")
def resend_login_2fa ():
    u_col =users_col ()
    pl_col =pending_login_col ()

    username =session .get ("pending_2fa_username")
    if not username :
        return redirect (url_for ("auth.login"))

    util =u_col .find_one ({"nom":username })
    if not util :
        session .pop ("pending_2fa_username",None )
        pl_col .delete_many ({"nom":username })
        return redirect (url_for ("auth.login"))

    user_email =util .get ("email")
    if not user_email :
        session .pop ("pending_2fa_username",None )
        pl_col .delete_many ({"nom":username })
        return redirect (url_for ("auth.login"))

    pl_col .delete_many ({"nom":username })

    code ="".join (random .choices (string .digits ,k =6 ))
    code_hash =bcrypt .hashpw (code .encode ("utf-8"),bcrypt .gensalt ())

    pl_col .insert_one (
    {
    "nom":username ,
    "code_hash":code_hash ,
    "created_at":time .time (),
    "attempts":0 ,
    }
    )

    try :
        send_verification_email (user_email ,code )
    except Exception as e :
        print ("Erreur renvoi mail A2F:",e )
        pl_col .delete_many ({"nom":username })
        session .pop ("pending_2fa_username",None )
        return render_template (
        "login.html",
        erreur ="Impossible de renvoyer le code A2F pour le moment, merci de réessayer plus tard.",
        )

    return redirect (url_for ("auth.verify_login_2fa"))
