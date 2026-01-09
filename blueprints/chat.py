
from datetime import datetime ,timedelta 
import os 

from flask import Blueprint ,render_template ,request ,redirect ,url_for ,session ,jsonify ,flash ,current_app 
from bson .objectid import ObjectId 
import json 
import pytz 
import html 
import uuid 
import random 
import importlib 






COMMAND_HANDLERS ={}


DUEL_GAMES ={}


import extensions 
from extensions import sock 
from utils .auth_utils import is_admin ,is_superadmin ,get_user_plan ,get_message_limit_per_hour 
from utils .mail_utils import send_group_invite_email 
from utils .maintenance import is_maintenance_mode 



chat_bp =Blueprint ("chat",__name__ )


def users_col ():
    return extensions .db .utilisateurs 


def messages_col ():
    return extensions .db .messages 


def groups_col ():
    return extensions .db .groups 

def announcements_col ():
    return extensions .db .announcements 

def reports_col ():
    return extensions .db .message_reports 



def is_effective_group_owner (username :str ,group :dict )->bool :
    """
    Owner effectif = owner stocké dans le groupe OU superadmin (tatoudm).
    Utilisé pour les permissions et l'affichage des contrôles, 
    mais pas pour les labels visuels "Owner".
    """
    if is_superadmin ():
        return True 
    return group .get ("owner")==username 




@chat_bp .route ("/")
def index ():
    if "util"in session :
        u_col =users_col ()
        util =u_col .find_one ({"nom":session ["util"]})

        if not util :
            session .clear ()
            return render_template ("index.html")

        if util .get ("banned",0 )==1 :
            reason =util .get ("ban_reason")or "Votre compte a été banni."
            session .clear ()
            return render_template ("login.html",erreur =reason )

        raw_pdp =(util .get ("pdp")or "").strip ()
        pdp =os .path .basename (raw_pdp )if raw_pdp else "guest.png"

        return render_template (
        "index.html",
        nom =session ["util"],
        pdp =pdp ,
        )
    else :
        return render_template ("index.html")


@chat_bp .route ("/chat",methods =["GET","POST"])
def chat ():
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    m_col =messages_col ()
    g_col =groups_col ()


    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))


    user_plan =get_user_plan (util )
    message_limit =get_message_limit_per_hour (util )

    if util .get ("banned",0 )==1 :
        reason =util .get ("ban_reason")or "Votre compte a été banni."
        session .clear ()
        return render_template ("login.html",erreur =reason )


    now =datetime .utcnow ()
    muted_active =False 
    mute_message =None 

    if util .get ("muted",0 )==1 :
        muted_until =util .get ("muted_until")
        muted_by =util .get ("muted_by","un modérateur")

        if muted_until is None or muted_until >now :
            muted_active =True 

            if muted_until is None :
                durée_txt ="indéfiniment"
            else :
                import pytz 
                tz =pytz .timezone ("Europe/Brussels")
                local_dt =muted_until .replace (tzinfo =pytz .utc ).astimezone (tz )
                durée_txt =f"jusqu'au {local_dt .strftime ('%d/%m %H:%M')}"

            mute_message =f"Tu as été mute {durée_txt } par le modérateur : {muted_by }."
        else :

            users_col ().update_one (
            {"_id":util ["_id"]},
            {
            "$set":{
            "muted":0 ,
            "muted_until":None ,
            "muted_by":None ,
            "muted_reason":None ,
            }
            },
            )


    username =util ["nom"]
    raw_pdp =(util .get ("pdp")or "").strip ()
    pdp =os .path .basename (raw_pdp )if raw_pdp else "guest.png"


    dm_target =(request .args .get ("dm")or "").strip ()
    initial_channel ="general"
    initial_dm_with =None 

    if dm_target :
        if dm_target ==username :
            session ["chat_error"]="Tu ne peux pas ouvrir un DM avec toi-même."
            return redirect (url_for ("chat.chat"))

        target_user =u_col .find_one ({"nom":dm_target })
        if not target_user :
            session ["chat_error"]=f"Utilisateur introuvable : {dm_target }"
            return redirect (url_for ("chat.chat"))

        initial_channel ="dm"
        initial_dm_with =dm_target 




    if request .method =="POST":
        contenu =(request .form .get ("message")or "").strip ()

        if not contenu :
            erreur ="Ton message est vide."
        elif len (contenu )>1000 :
            erreur ="Ton message est trop long (1000 caractères max)."
        else :
            now =datetime .utcnow ()

            one_hour_ago =now -timedelta (hours =1 )

            count_last_hour =m_col .count_documents (
            {
            "author":username ,
            "created_at":{"$gte":one_hour_ago },
            "channel":"general",
            }
            )

            if count_last_hour >=1000 :
                erreur ="Tu as atteint la limite de 1000 messages pour cette heure."
            else :
                safe_author =html .escape (username )
                safe_content =html .escape (contenu )

                doc ={
                "author":safe_author ,
                "content":safe_content ,
                "created_at":now ,
                "channel":"general",
                }

                if safe_author .lower ()=="serveur":
                    doc ["expiresAt"]=None 
                else :
                    doc ["expiresAt"]=now +timedelta (hours =1 )

                m_col .insert_one (doc )



                return redirect (url_for ("chat.chat"))


    one_hour_ago =datetime .utcnow ()-timedelta (hours =1 )
    messages_cursor =(
    m_col .find (
    {
    "channel":"general",
    "created_at":{"$gte":one_hour_ago },
    }
    )
    .sort ("created_at",1 )
    .limit (200 )
    )

    messages =[]
    for msg in messages_cursor :
        author_name =msg .get ("author","")
        author_user =u_col .find_one ({"nom":author_name })
        if author_user :
            raw =(author_user .get ("pdp")or "").strip ()
            author_pdp =os .path .basename (raw )if raw else "guest.png"
        else :
            author_pdp ="guest.png"


        msg ["author_pdp"]=author_pdp 
        messages .append (msg )



    last_seen_dm =util .get ("last_seen_dm")
    if not last_seen_dm :
        last_seen_dm =datetime .utcnow ()-timedelta (hours =1 )


    dm_convos_map ={}
    dm_cursor =m_col .find (
    {
    "channel":{"$regex":r"^dm:"},
    "participants":username ,
    }
    ).sort ("created_at",-1 )

    for msg in dm_cursor :
        participants =msg .get ("participants")or []
        other =None 
        for p in participants :
            if p !=username :
                other =p 
                break 
        if not other :
            continue 

        conv =dm_convos_map .get (other )
        if not conv :
            conv ={
            "other":other ,
            "last_message":msg .get ("content",""),
            "last_time":msg .get ("created_at"),
            "unread_count":0 ,
            }
            dm_convos_map [other ]=conv 

        if (
        msg .get ("author")!=username 
        and msg .get ("created_at")
        and msg ["created_at"]>last_seen_dm 
        ):
            conv ["unread_count"]+=1 

    dm_convos =list (dm_convos_map .values ())
    dm_convos .sort (
    key =lambda x :x ["last_time"]or datetime .utcnow (),
    reverse =True ,
    )


    groups_data =[]
    if is_superadmin ():

        groups_cursor =g_col .find ({}).sort ("created_at",-1 )
    else :

        groups_cursor =g_col .find ({"members":username }).sort ("created_at",-1 )


    for g in groups_cursor :
        gid =str (g ["_id"])
        channel =f"group:{gid }"

        last_msg =m_col .find_one (
        {"channel":channel },
        sort =[("created_at",-1 )],
        )

        unread_count =0 
        if last_msg and last_msg .get ("created_at")and last_msg ["created_at"]>last_seen_dm :
            unread_count =m_col .count_documents (
            {
            "channel":channel ,
            "author":{"$ne":username },
            "created_at":{"$gt":last_seen_dm },
            }
            )

        effective_owner =is_effective_group_owner (username ,g )

        groups_data .append (
        {
        "id":gid ,
        "name":g .get ("name","Groupe sans nom"),
        "owner":g .get ("owner"),

        "is_owner":g .get ("owner")==username ,

        "can_manage":effective_owner ,
        "allow_member_invites":g .get ("allow_member_invites",False ),
        "members":g .get ("members",[]),
        "unread_count":unread_count ,
        "last_message":last_msg ["content"]if last_msg else "",
        "last_time":last_msg ["created_at"]if last_msg else None ,
        }
        )


    a_col =announcements_col ()
    ann_cursor =a_col .find ({}).sort ("created_at",-1 ).limit (20 )

    announcements =[]
    for a in ann_cursor :
        announcements .append (
        {
        "id":str (a ["_id"]),
        "author":a .get ("author"),
        "title":a .get ("title",""),
        "description":a .get ("description",""),
        "created_at":a .get ("created_at"),
        }
        )





    u_col .update_one (
    {"_id":util ["_id"]},
    {"$set":{"last_seen_dm":datetime .utcnow ()}},
    )

    success =session .pop ("chat_success",None )
    error =session .pop ("chat_error",None )

    return render_template (
    "chat.html",
    nom =username ,
    pdp =pdp ,
    messages =messages ,
    erreur =error ,
    success =success ,
    is_admin =is_admin (),
    dm_convos =dm_convos ,
    groups =groups_data ,
    announcements =announcements ,
    is_muted =muted_active ,
    mute_message =mute_message ,
    user_plan =user_plan ,
    message_limit =message_limit ,
    initial_channel =initial_channel ,
    initial_dm_with =initial_dm_with ,
    )



@chat_bp .route ("/announcements/json")
def announcements_json ():
    if "util"not in session :
        return jsonify ({"announcements":[]}),401 

    a_col =announcements_col ()
    cursor =a_col .find ({}).sort ("created_at",-1 ).limit (20 )

    data =[]
    for a in cursor :
        data .append (
        {
        "id":str (a ["_id"]),
        "author":a .get ("author"),
        "title":a .get ("title",""),
        "description":a .get ("description",""),
        }
        )

    return jsonify ({"announcements":data })

@chat_bp .route ("/announcements/create",methods =["POST"])
def create_announcement ():
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    if not is_admin ():
        session ["chat_error"]="Tu n'as pas la permission de créer une annonce."
        return redirect (url_for ("chat.chat"))

    u_col =users_col ()
    a_col =announcements_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    if util .get ("banned",0 )==1 :
        session ["chat_error"]="Votre compte a été banni."
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    title =(request .form .get ("title")or "").strip ()
    description =(request .form .get ("description")or "").strip ()

    if not title :
        session ["chat_error"]="Le titre de l'annonce est obligatoire."
        return redirect (url_for ("chat.chat"))

    if len (title )>100 :
        session ["chat_error"]="Le titre de l'annonce est trop long (100 caractères max)."
        return redirect (url_for ("chat.chat"))

    if len (description )>1000 :
        session ["chat_error"]="La description de l'annonce est trop longue (1000 caractères max)."
        return redirect (url_for ("chat.chat"))

    a_col .insert_one (
    {
    "author":username ,
    "title":title ,
    "description":description ,
    "created_at":datetime .utcnow (),
    }
    )

    return redirect (url_for ("chat.chat"))


@chat_bp .route ("/announcements/<ann_id>/delete",methods =["POST"])
def delete_announcement (ann_id ):
    if "util"not in session :
        return redirect (url_for ("auth.login"))



    if not is_admin ():
        session ["chat_error"]="Tu n'as pas la permission de supprimer une annonce."
        return redirect (url_for ("chat.chat"))

    u_col =users_col ()
    a_col =announcements_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    if util .get ("banned",0 )==1 :
        session ["chat_error"]="Votre compte a été banni."
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    from bson .objectid import ObjectId 
    if not ObjectId .is_valid (ann_id ):
        session ["chat_error"]="Annonce introuvable."
        return redirect (url_for ("chat.chat"))

    ann =a_col .find_one ({"_id":ObjectId (ann_id )})
    if not ann :
        session ["chat_error"]="Annonce introuvable."
        return redirect (url_for ("chat.chat"))

    author =ann .get ("author")



    if author =="tatoudm"and not is_superadmin ():
        session ["chat_error"]="Seul le superadmin peut supprimer ses propres annonces."
        return redirect (url_for ("chat.chat"))


    a_col .delete_one ({"_id":ann ["_id"]})

    return redirect (url_for ("chat.chat"))




@chat_bp .route ("/groups/<group_id>/rename",methods =["POST"])
def rename_group (group_id ):
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    g_col =groups_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    if not ObjectId .is_valid (group_id ):
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    group =g_col .find_one ({"_id":ObjectId (group_id )})
    if not group :
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))


    if not is_effective_group_owner (username ,group ):
        session ["chat_error"]="Seul le propriétaire du groupe peut le renommer."
        return redirect (url_for ("chat.chat"))

    new_name =(request .form .get ("new_name")or "").strip ()
    if not new_name :
        session ["chat_error"]="Le nouveau nom du groupe est vide."
        return redirect (url_for ("chat.chat"))


    if len (new_name )>50 :
        session ["chat_error"]="Le nom du groupe est trop long (50 caractères max)."
        return redirect (url_for ("chat.chat"))

    g_col .update_one (
    {"_id":group ["_id"]},
    {"$set":{"name":new_name }}
    )

    return redirect (url_for ("chat.chat"))

@chat_bp .route ("/groups/create",methods =["POST"])
def create_group ():
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    g_col =groups_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    if util .get ("banned",0 )==1 :
        session ["chat_error"]="Votre compte a été banni."
        return redirect (url_for ("auth.login"))

    username =util ["nom"]
    name =(request .form .get ("group_name")or "").strip ()

    if not name :
        session ["chat_error"]="Le nom du groupe est vide."
        return redirect (url_for ("chat.chat"))

    existing_count =g_col .count_documents ({"owner":username })
    if existing_count >=3 :
        session ["chat_error"]="Tu as déjà créé 3 groupes, limite atteinte."
        return redirect (url_for ("chat.chat"))

    g_col .insert_one (
    {
    "name":name ,
    "owner":username ,
    "members":[username ],
    "allow_member_invites":False ,
    "created_at":datetime .utcnow (),
    }
    )

    return redirect (url_for ("chat.chat"))



@chat_bp .route ("/groups/<group_id>/add_member",methods =["POST"])
def add_group_member (group_id ):
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    g_col =groups_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    if not ObjectId .is_valid (group_id ):
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    group =g_col .find_one ({"_id":ObjectId (group_id )})
    if not group :
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    members =group .get ("members",[])
    allow_member_invites =group .get ("allow_member_invites",False )




    if not (
    is_effective_group_owner (username ,group )
    or (allow_member_invites and username in members )
    ):
        session ["chat_error"]="Tu n'as pas la permission d'ajouter des membres dans ce groupe."
        return redirect (url_for ("chat.chat"))

    identifier =(request .form .get ("identifier")or "").strip ()
    if not identifier :
        session ["chat_error"]="Pseudo ou email vide."
        return redirect (url_for ("chat.chat"))

    invited_by_email =False 
    target =None 


    if "@"in identifier :
        invited_by_email =True 
        target =u_col .find_one ({"email":identifier })
    else :
        target =u_col .find_one ({"nom":identifier })


    if invited_by_email and not target :

        try :
            send_group_invite_email (
            to_email =identifier ,
            inviter_name =username ,
            group_name =group .get ("name","Groupe")
            )

        except Exception as e :
            print ("Erreur envoi email d'invitation (invité sans compte) :",e )
            session ["chat_error"]=(
            "Impossible d'envoyer l'email d'invitation, réessaie plus tard."
            )
        return redirect (url_for ("chat.chat"))


    if not target :
        session ["chat_error"]="Utilisateur introuvable avec ce pseudo/email."
        return redirect (url_for ("chat.chat"))

    target_name =target ["nom"]

    if target_name in members :
        session ["chat_error"]=f"{target_name } est déjà dans le groupe."
        return redirect (url_for ("chat.chat"))


    members .append (target_name )
    g_col .update_one ({"_id":group ["_id"]},{"$set":{"members":members }})


    if invited_by_email :
        try :
            to_email =target .get ("email")or identifier 
            send_group_invite_email (
            to_email =to_email ,
            inviter_name =username ,
            group_name =group .get ("name","Groupe")
            )
        except Exception as e :
            print ("Erreur envoi email d'invitation :",e )

    return redirect (url_for ("chat.chat"))




@chat_bp .route ("/groups/<group_id>/delete",methods =["POST"])
def delete_group (group_id ):
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    g_col =groups_col ()
    m_col =messages_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    if not ObjectId .is_valid (group_id ):
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    group =g_col .find_one ({"_id":ObjectId (group_id )})
    if not group :
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    if not is_effective_group_owner (username ,group ):
        session ["chat_error"]="Seul le propriétaire du groupe peut le supprimer."
        return redirect (url_for ("chat.chat"))



    channel_key =f"group:{group_id }"
    m_col .delete_many ({"channel":channel_key })


    g_col .delete_one ({"_id":group ["_id"]})

    return redirect (url_for ("chat.chat"))



@chat_bp .route ("/groups/<group_id>/kick_member",methods =["POST"])
def kick_group_member (group_id ):
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    g_col =groups_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    if not ObjectId .is_valid (group_id ):
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    group =g_col .find_one ({"_id":ObjectId (group_id )})
    if not group :
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))


    if not is_effective_group_owner (username ,group ):
        session ["chat_error"]="Seul le propriétaire du groupe peut exclure des membres."
        return redirect (url_for ("chat.chat"))

    member_name =(request .form .get ("member")or "").strip ()
    if not member_name :
        session ["chat_error"]="Membre à exclure invalide."
        return redirect (url_for ("chat.chat"))


    if member_name ==group .get ("owner"):
        session ["chat_error"]="Impossible de retirer le propriétaire du groupe."
        return redirect (url_for ("chat.chat"))

    if member_name ==username :
        session ["chat_error"]="Tu ne peux pas te retirer toi-même (owner)."
        return redirect (url_for ("chat.chat"))

    members =group .get ("members",[])
    if member_name not in members :
        session ["chat_error"]="Ce membre n'est pas dans le groupe."
        return redirect (url_for ("chat.chat"))

    members =[m for m in members if m !=member_name ]
    g_col .update_one ({"_id":group ["_id"]},{"$set":{"members":members }})

    return redirect (url_for ("chat.chat"))


@chat_bp .route ("/groups/<group_id>/toggle_invites",methods =["POST"])
def toggle_group_invites (group_id ):
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    g_col =groups_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    username =util ["nom"]

    if not ObjectId .is_valid (group_id ):
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    group =g_col .find_one ({"_id":ObjectId (group_id )})
    if not group :
        session ["chat_error"]="Groupe introuvable."
        return redirect (url_for ("chat.chat"))

    if not is_effective_group_owner (username ,group ):
        session ["chat_error"]="Seul le propriétaire du groupe peut changer ce paramètre."
        return redirect (url_for ("chat.chat"))


    current =group .get ("allow_member_invites",False )
    g_col .update_one (
    {"_id":group ["_id"]},
    {"$set":{"allow_member_invites":not current }},
    )

    return redirect (url_for ("chat.chat"))


@chat_bp .route ("/chat/report",methods =["POST"])
def report_message ():
    if "util"not in session :
        return redirect (url_for ("auth.login"))

    u_col =users_col ()
    m_col =messages_col ()
    r_col =reports_col ()

    util =u_col .find_one ({"nom":session ["util"]})
    if not util :
        session .clear ()
        return redirect (url_for ("auth.login"))

    if util .get ("banned",0 )==1 :
        session ["chat_error"]="Votre compte a été banni."
        return redirect (url_for ("auth.login"))

    msg_id =(request .form .get ("message_id")or "").strip ()
    if not msg_id or not ObjectId .is_valid (msg_id ):
        session ["chat_error"]="Message introuvable."
        return redirect (url_for ("chat.chat"))

    msg =m_col .find_one ({"_id":ObjectId (msg_id )})
    if not msg :
        session ["chat_error"]="Message introuvable."
        return redirect (url_for ("chat.chat"))

    reporter =util ["nom"]


    if msg .get ("author")==reporter :
        session ["chat_error"]="Tu ne peux pas signaler ton propre message."
        return redirect (url_for ("chat.chat"))


    existing =r_col .find_one ({"message_id":msg ["_id"],"reported_by":reporter })
    if existing :
        session ["chat_error"]="Tu as déjà signalé ce message."
        return redirect (url_for ("chat.chat"))

    r_col .insert_one (
    {
    "message_id":msg ["_id"],
    "reported_by":reporter ,
    "author":msg .get ("author"),
    "channel":msg .get ("channel","general"),
    "created_at":datetime .utcnow (),
    }
    )

    session ["chat_success"]="Message signalé"
    return redirect (url_for ("chat.chat"))