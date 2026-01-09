

import json 
import os 
import importlib 
from datetime import datetime ,timedelta 

import pytz 
from bson .objectid import ObjectId 
from flask import current_app 

import extensions 
from extensions import sock 
from utils .auth_utils import is_superadmin ,get_message_limit_per_hour ,get_user_plan 
from utils .maintenance import is_maintenance_mode 





def users_col ():
    return extensions .db .utilisateurs 


def messages_col ():
    return extensions .db .messages 


def groups_col ():
    return extensions .db .groups 





connections ={}


def send_to_user (username :str ,payload :dict ):
    """Envoie un payload JSON à tous les WS d'un user."""
    dead =[]
    data =json .dumps (payload )
    for conn ,info in list (connections .items ()):
        if info .get ("user")!=username :
            continue 
        try :
            conn .send (data )
        except Exception :
            dead .append (conn )
    for d in dead :
        connections .pop (d ,None )


def send_to_users (usernames ,payload :dict ):
    """Envoie à une liste de users (dedup)."""
    for u in set (usernames or []):
        send_to_user (u ,payload )


def send_to_channel (channel_key :str ,payload :dict ):
    """Broadcast à tous les WS connectés sur un channel précis."""
    dead =[]
    data =json .dumps (payload )
    for conn ,info in list (connections .items ()):
        if info .get ("channel")!=channel_key :
            continue 
        try :
            conn .send (data )
        except Exception :
            dead .append (conn )
    for d in dead :
        connections .pop (d ,None )


def list_command_js ()->list [str ]:
    """
    Liste les plugins JS disponibles dans /static/commands/*.js
    (utilisé pour charger tous les scripts côté client).
    """
    try :
        static_folder =current_app .static_folder 
        base =os .path .join (static_folder ,"commands")
        if not os .path .isdir (base ):
            return []
        out =[]
        for fname in os .listdir (base ):
            if fname .endswith (".js"):
                out .append (fname [:-3 ])
        return sorted (set (out ))
    except Exception :
        return []





class CommandContext :
    def __init__ (
    self ,
    *,
    username :str ,
    channel_type :str ,
    channel_key :str ,
    participants ,
    ws ,
    u_col ,
    m_col ,
    g_col ,
    ):
        self .username =username 
        self .channel_type =channel_type 
        self .channel_key =channel_key 
        self .participants =participants or []
        self .ws =ws 
        self .u_col =u_col 
        self .m_col =m_col 
        self .g_col =g_col 

    def send_to_self (self ,payload :dict ):
        send_to_user (self .username ,payload )

    def send_to_channel (self ,payload :dict ):
        payload =dict (payload or {})
        payload .setdefault ("channel",self .channel_key )
        send_to_channel (self .channel_key ,payload )

    def send_to_users (self ,users ,payload :dict ):
        send_to_users (users ,payload )

    def send_command_to (self ,users ,command_name :str ,payload :dict ):
        send_to_users (
        users ,
        {
        "type":"command",
        "command":command_name ,
        "from":self .username ,
        "channel":self .channel_key ,
        "channel_type":self .channel_type ,
        "payload":payload or {},
        },
        )

    def broadcast_command (self ,command_name :str ,payload :dict ):
        send_to_channel (
        self .channel_key ,
        {
        "type":"command",
        "command":command_name ,
        "from":self .username ,
        "channel":self .channel_key ,
        "channel_type":self .channel_type ,
        "payload":payload or {},
        },
        )





def handle_slash_command (contenu :str ,*,ctx :CommandContext )->bool :
    """
    Gère les /commandes.
    Retourne True si une commande a été traitée, False sinon.
    """
    contenu =(contenu or "").strip ()
    if not contenu .startswith ("/"):
        return False 

    parts =contenu .split ()
    if not parts :
        return False 

    cmd_name =parts [0 ][1 :].lower ()
    args =parts [1 :]

    try :
        module =importlib .import_module (f"commands.{cmd_name }")
    except ModuleNotFoundError :
        ctx .send_to_self (
        {"type":"error","message":f"Commande introuvable : /{cmd_name }"}
        )
        return True 
    except Exception as exc :
        print (f"[COMMAND] Erreur import commands.{cmd_name }: {exc }")
        ctx .send_to_self (
        {"type":"error","message":f"Erreur interne pendant /{cmd_name }."}
        )
        return True 

    handler =getattr (module ,"handle",None )
    if not callable (handler ):
        ctx .send_to_self (
        {
        "type":"error",
        "message":f"Commande /{cmd_name } mal configurée (pas de handle(ctx, args)).",
        }
        )
        return True 

    try :
        handler (ctx ,args )
    except Exception as exc :
        print (f"[COMMAND] Erreur dans commands.{cmd_name }.handle : {exc }")
        ctx .send_to_self (
        {"type":"error","message":f"Erreur interne pendant /{cmd_name }."}
        )

    return True 


def handle_command_event (
cmd_name :str ,
event_name :str ,
payload :dict ,
*,
ctx :CommandContext ,
):
    """
    Gère les évènements de commandes envoyés par les plugins JS
    (command_event côté client).
    """
    cmd_name =(cmd_name or "").lower ().strip ()
    if not cmd_name or not event_name :
        ctx .send_to_self ({"type":"error","message":"Event de commande invalide."})
        return 

    try :
        module =importlib .import_module (f"commands.{cmd_name }")
    except ModuleNotFoundError :
        ctx .send_to_self (
        {"type":"error","message":f"Commande inconnue : {cmd_name }."}
        )
        return 
    except Exception as exc :
        print (f"[COMMAND] Erreur import commands.{cmd_name } (event): {exc }")
        ctx .send_to_self (
        {"type":"error","message":f"Erreur interne dans /{cmd_name }."}
        )
        return 

    handler =getattr (module ,"handle_event",None )
    if not callable (handler ):
        ctx .send_to_self (
        {
        "type":"error",
        "message":f"La commande /{cmd_name } ne gère pas d'évènements.",
        }
        )
        return 

    try :
        handler (ctx ,event_name ,payload or {})
    except Exception as exc :
        print (f"[COMMAND] Erreur dans commands.{cmd_name }.handle_event : {exc }")
        ctx .send_to_self (
        {"type":"error","message":f"Erreur interne pendant /{cmd_name }."}
        )





@sock .route ("/ws/chat")
def chat_ws (ws ):
    from flask import session as ws_session ,request as flask_request 

    username =None 
    channel_key ="unknown"
    channel_type ="general"
    group_id_str =None 
    participants =None 
    group =None 

    def send_fatal_error (message :str ):
        payload ={
        "type":"fatal_error",
        "message":message or "Erreur critique sur le WebSocket.",
        }
        try :
            ws .send (json .dumps (payload ))
        except Exception :
            pass 
        try :
            ws .close ()
        except Exception :
            pass 


    if "util"not in ws_session :
        send_fatal_error ("Non connecté.")
        return 

    u_col =users_col ()
    m_col =messages_col ()
    g_col =groups_col ()

    util =u_col .find_one ({"nom":ws_session ["util"]})
    if not util :
        send_fatal_error ("Utilisateur introuvable.")
        return 


    if is_maintenance_mode ():
        try :
            ws .send (
            json .dumps (
            {
            "type":"maintenance",
            "active":True ,
            "message":"Le site est en maintenance, la connexion WebSocket va être fermée.",
            }
            )
            )
        except Exception :
            pass 
        try :
            ws .close ()
        except Exception :
            pass 
        return 


    if util .get ("banned",0 )==1 :
        reason =util .get ("ban_reason")or "Votre compte a été banni."
        try :
            ws .send (
            json .dumps (
            {
            "type":"force_logout",
            "reason":reason ,
            }
            )
            )
        except Exception :
            pass 
        try :
            ws .close ()
        except Exception :
            pass 
        return 

    username =util ["nom"]



    channel_type =flask_request .args .get ("channel","general")
    channel_key ="general"
    participants =None 
    group_id_str =None 
    group =None 


    if channel_type =="dm":
        raw_target =(flask_request .args .get ("with")or "").strip ()
        target =raw_target .strip ('"').strip ("'")

        if not target :
            send_fatal_error ("Pseudo du destinataire manquant.")
            return 

        if target ==username :
            send_fatal_error ("Tu ne peux pas ouvrir un MP avec toi-même.")
            return 

        target_user =u_col .find_one ({"nom":target })
        if not target_user :
            send_fatal_error ("Utilisateur introuvable pour le MP.")
            return 

        pair =sorted ([username ,target ])
        channel_key =f"dm:{pair [0 ]}:{pair [1 ]}"
        participants =pair 


    elif channel_type =="group":
        group_id_str =(flask_request .args .get ("group_id")or "").strip ()

        if not group_id_str or not ObjectId .is_valid (group_id_str ):
            try :
                ws .send (
                json .dumps (
                {
                "type":"error",
                "message":"ID de groupe invalide.",
                }
                )
                )
            except Exception :
                pass 
            try :
                ws .close ()
            except Exception :
                pass 
            return 

        try :
            group =g_col .find_one ({"_id":ObjectId (group_id_str )})
        except Exception :
            group =None 

        if not group :
            try :
                ws .send (
                json .dumps (
                {
                "type":"error",
                "message":"Groupe introuvable.",
                }
                )
                )
            except Exception :
                pass 
            try :
                ws .close ()
            except Exception :
                pass 
            return 

        members =group .get ("members",[])

        if username not in members and not is_superadmin ():
            try :
                ws .send (
                json .dumps (
                {
                "type":"error",
                "message":"Tu ne fais pas partie de ce groupe.",
                }
                )
                )
            except Exception :
                pass 
            try :
                ws .close ()
            except Exception :
                pass 
            return 

        channel_key =f"group:{group_id_str }"
        participants =members 


    else :
        channel_type ="general"
        channel_key ="general"


    connections [ws ]={"channel":channel_key ,"user":username }


    tz =pytz .timezone ("Europe/Brussels")
    one_hour_ago =datetime .utcnow ()-timedelta (hours =1 )

    q ={"channel":channel_key ,"created_at":{"$gte":one_hour_ago }}
    cursor =m_col .find (q ).sort ("created_at",1 )

    history =[]
    for msg in cursor :
        dt_utc =msg .get ("created_at")
        if dt_utc :
            dt_local =dt_utc .replace (tzinfo =pytz .utc ).astimezone (tz )
            time_str =dt_local .strftime ("%H:%M")
        else :
            time_str ="??:??"

        author_name =msg .get ("author","")
        author_user =u_col .find_one ({"nom":author_name })
        author_pdp =None 

        if author_user :
            raw =(author_user .get ("pdp")or "").strip ()
            author_pdp =os .path .basename (raw )if raw else "guest.png"

            try :
                author_plan =get_user_plan (author_user )
            except Exception :
                author_plan ="free"
            author_is_plus =(author_plan =="plus")
        else :
            author_pdp ="guest.png"
            author_is_plus =False 

        history .append (
        {
        "id":str (msg .get ("_id")),
        "author":author_name ,
        "author_pdp":author_pdp ,
        "content":msg .get ("content","")or "",
        "time":time_str ,
        "reactions":msg .get ("reactions",{})or {},
        "author_is_plus":author_is_plus ,
        }
        )


        history .append (
        {
        "id":str (msg .get ("_id")),
        "author":author_name ,
        "author_pdp":author_pdp ,
        "content":msg .get ("content","")or "",
        "time":time_str ,
        "reactions":msg .get ("reactions",{})or {},
        "author_is_plus":author_is_plus ,
        }
        )




    cmds =list_command_js ()

    try :
        ws .send (
        json .dumps (
        {
        "type":"init",
        "messages":history ,
        "commands":cmds ,
        }
        )
        )
    except Exception :
        connections .pop (ws ,None )
        try :
            ws .close ()
        except Exception :
            pass 
        return 


    try :
        while True :
            try :
                data =ws .receive ()
            except Exception as exc :
                try :
                    ws .send (
                    json .dumps (
                    {
                    "type":"fatal_error",
                    "message":f"Erreur interne de réception WS : {exc }",
                    }
                    )
                    )
                except Exception :
                    pass 
                break 

            if data is None :
                break 


            if is_maintenance_mode ():
                try :
                    ws .send (
                    json .dumps (
                    {
                    "type":"maintenance",
                    "active":True ,
                    "message":(
                    "Le site vient de passer en maintenance. "
                    "La connexion va être fermée."
                    ),
                    }
                    )
                    )
                except Exception :
                    pass 
                try :
                    ws .close ()
                except Exception :
                    pass 
                break 


            util =u_col .find_one ({"nom":username })
            if not util :
                try :
                    ws .send (
                    json .dumps (
                    {
                    "type":"force_logout",
                    "reason":"Utilisateur introuvable.",
                    }
                    )
                    )
                except Exception :
                    pass 
                try :
                    ws .close ()
                except Exception :
                    pass 
                break 

            if util .get ("banned",0 )==1 :
                reason =util .get ("ban_reason")or "Votre compte a été banni."
                try :
                    ws .send (
                    json .dumps (
                    {
                    "type":"force_logout",
                    "reason":reason ,
                    }
                    )
                    )
                except Exception :
                    pass 
                try :
                    ws .close ()
                except Exception :
                    pass 
                break 

            now =datetime .utcnow ()


            if util .get ("muted",0 )==1 :
                muted_until =util .get ("muted_until")

                if muted_until is None or muted_until >now :
                    try :
                        ws .send (
                        json .dumps (
                        {
                        "type":"error",
                        "message":"Tu es actuellement mute et ne peux pas envoyer de messages.",
                        }
                        )
                        )
                    except Exception :
                        pass 
                    continue 
                else :

                    u_col .update_one (
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


            try :
                payload =json .loads (data )
            except json .JSONDecodeError :
                try :
                    ws .send (
                    json .dumps (
                    {
                    "type":"error",
                    "message":"Format JSON invalide.",
                    }
                    )
                    )
                except Exception :
                    pass 
                continue 

            msg_type =payload .get ("type")




            if channel_type =="dm"and participants :
                lower_parts =[p .lower ()for p in participants ]
                is_dm_serveur ="serveur"in lower_parts 
                if (
                is_dm_serveur 
                and username .lower ()!="serveur"
                and msg_type in ("send_message","command_event")
                ):

                    try :
                        ws .send (
                        json .dumps (
                        {
                        "type":"error",
                        "message":"Tu n'as pas l'autorisation de parler dans ce chat.",
                        }
                        )
                        )
                    except Exception :
                        pass 
                    continue 


            if msg_type =="toggle_reaction":
                message_id =(payload .get ("message_id")or "").strip ()
                emoji_raw =(payload .get ("emoji")or "").strip ()

                if emoji_raw :
                    emoji =emoji_raw [0 ]
                else :
                    emoji =""



                plan =get_user_plan (util )
                if plan !="plus":
                    send_to_user (
                    username ,
                    {
                    "type":"error",
                    "message":"Les réactions sont réservées au plan Plus.",
                    },
                    )
                    continue 


                if not emoji or len (emoji )>16 :
                    send_to_user (
                    username ,
                    {
                    "type":"error",
                    "message":"Réaction invalide.",
                    },
                    )
                    continue 


                if not message_id or not ObjectId .is_valid (message_id ):
                    send_to_user (
                    username ,
                    {
                    "type":"error",
                    "message":"Message introuvable pour la réaction.",
                    },
                    )
                    continue 

                msg_doc =m_col .find_one ({"_id":ObjectId (message_id )})
                if not msg_doc :
                    send_to_user (
                    username ,
                    {
                    "type":"error",
                    "message":"Message introuvable pour la réaction.",
                    },
                    )
                    continue 


                if msg_doc .get ("channel")!=channel_key :
                    send_to_user (
                    username ,
                    {
                    "type":"error",
                    "message":"Tu ne peux pas réagir à ce message depuis ce salon.",
                    },
                    )
                    continue 

                reactions =msg_doc .get ("reactions")or {}
                current_users =(reactions .get (emoji )or [])
                field =f"reactions.{emoji }"


                if username in current_users :
                    m_col .update_one (
                    {"_id":msg_doc ["_id"]},
                    {"$pull":{field :username }},
                    )
                else :
                    m_col .update_one (
                    {"_id":msg_doc ["_id"]},
                    {"$addToSet":{field :username }},
                    )

                updated =m_col .find_one ({"_id":msg_doc ["_id"]})
                reactions_raw =updated .get ("reactions")or {}


                clean_reactions ={
                e :users 
                for e ,users in reactions_raw .items ()
                if isinstance (users ,list )and len (users )>0 
                }


                update_ops ={}
                if clean_reactions and clean_reactions !=reactions_raw :
                    update_ops ["$set"]={"reactions":clean_reactions }
                elif not clean_reactions and reactions_raw :
                    update_ops ["$unset"]={"reactions":""}

                if update_ops :
                    m_col .update_one ({"_id":msg_doc ["_id"]},update_ops )

                reactions =clean_reactions 


                send_to_channel (
                channel_key ,
                {
                "type":"reaction_update",
                "message_id":str (updated ["_id"]),
                "reactions":reactions ,
                },
                )
                continue 




            if msg_type =="command_event":
                ctx =CommandContext (
                username =username ,
                channel_type =channel_type ,
                channel_key =channel_key ,
                participants =participants ,
                ws =ws ,
                u_col =u_col ,
                m_col =m_col ,
                g_col =g_col ,
                )
                cmd_name =payload .get ("command")or ""
                event_name =payload .get ("event")or ""
                event_payload =payload .get ("payload")or {}
                handle_command_event (cmd_name ,event_name ,event_payload ,ctx =ctx )
                continue 


            if msg_type !="send_message":

                continue 

            contenu =(payload .get ("content")or "").strip ()

            if not contenu :
                send_to_user (
                username ,
                {
                "type":"error",
                "message":"Ton message est vide.",
                },
                )
                continue 

            if len (contenu )>1000 :
                send_to_user (
                username ,
                {
                "type":"error",
                "message":"Ton message est trop long (1000 caractères max).",
                },
                )
                continue 

            ctx =CommandContext (
            username =username ,
            channel_type =channel_type ,
            channel_key =channel_key ,
            participants =participants ,
            ws =ws ,
            u_col =u_col ,
            m_col =m_col ,
            g_col =g_col ,
            )


            try :
                if not is_superadmin ():

                    spam_times =util .get ("spam_last_msg_ts")or []
                    spam_times =[t for t in spam_times if isinstance (t ,datetime )]


                    spam_times .append (now )


                    prune_cutoff =now -timedelta (seconds =60 )
                    spam_times =[t for t in spam_times if t >=prune_cutoff ]


                    try :
                        u_col .update_one (
                        {"_id":util ["_id"]},
                        {"$set":{"spam_last_msg_ts":spam_times }},
                        )
                    except Exception :
                        pass 



                    hard_window_cutoff =now -timedelta (seconds =12 )
                    hard_count =sum (1 for t in spam_times if t >=hard_window_cutoff )
                    hard_spam =hard_count >=8 


                    fast_spam =False 
                    if len (spam_times )>=4 :
                        a ,b ,c ,d =spam_times [-4 ],spam_times [-3 ],spam_times [-2 ],spam_times [-1 ]
                        if (b -a ).total_seconds ()<1 and (c -b ).total_seconds ()<1 and (d -c ).total_seconds ()<1 :
                            fast_spam =True 

                    is_spam =hard_spam or fast_spam 

                    if is_spam :
                        spam_strikes =int (util .get ("spam_strikes",0 ))
                        spam_window_until =util .get ("spam_window_until")
                        is_recurrence =False 
                        if isinstance (spam_window_until ,datetime )and now <=spam_window_until :
                            if spam_strikes >=1 :
                                is_recurrence =True 


                        if is_recurrence :
                            minutes =30 
                            spam_strikes =max (spam_strikes ,2 )
                        else :
                            minutes =10 
                            spam_strikes =1 

                        muted_until =now +timedelta (minutes =minutes )
                        new_spam_window_until =muted_until +timedelta (hours =6 )


                        try :
                            u_col .update_one (
                            {"_id":util ["_id"]},
                            {
                            "$set":{
                            "muted":1 ,
                            "muted_until":muted_until ,
                            "muted_by":"Sanction auto",
                            "muted_reason":"spam_detected (auto)",
                            "spam_last_msg_ts":spam_times ,
                            "spam_strikes":spam_strikes ,
                            "spam_window_until":new_spam_window_until ,
                            }
                            },
                            )
                        except Exception :
                            pass 


                        try :
                            from blueprints .admin import log_admin_action 
                        except Exception :
                            log_admin_action =None 

                        rule ="8in12s"if hard_spam else "4fast"
                        details =f"minutes={minutes }, rule={rule }, recurrence={is_recurrence }"
                        if log_admin_action :
                            try :
                                log_admin_action (
                                actor ="Sanction auto",
                                action ="auto_mute",
                                target =username ,
                                details =details ,
                                ip ="auto",
                                )
                            except Exception :
                                pass 


                        try :
                            send_to_user (
                            username ,
                            {
                            "type":"auto_mute",
                            "message":f"Spam détecté → mute automatique de {minutes } minutes.",
                            "muted_until":muted_until .isoformat (),
                            },
                            )
                        except Exception :
                            pass 


                        continue 

            except Exception :

                pass 




            if handle_slash_command (contenu ,ctx =ctx ):
                continue 


            one_hour_ago_msg =now -timedelta (hours =1 )
            count_last_hour =m_col .count_documents (
            {
            "author":username ,
            "created_at":{"$gte":one_hour_ago_msg },
            "channel":channel_key ,
            }
            )

            limit_per_hour =get_message_limit_per_hour (util )
            plan =get_user_plan (util )

            if count_last_hour >=limit_per_hour :
                send_to_user (
                username ,
                {
                "type":"error",
                "message":(
                f"Tu as atteint la limite de {limit_per_hour } messages/heure "
                f"pour ton plan {plan }."
                ),
                },
                )
                continue 



            doc ={
            "author":username ,
            "content":contenu ,
            "created_at":now ,
            "channel":channel_key ,
            }
            if participants :
                doc ["participants"]=participants 

            if username .lower ()=="serveur":
                doc ["expiresAt"]=None 
            else :
                doc ["expiresAt"]=now +timedelta (hours =1 )

            result =m_col .insert_one (doc )
            msg_id =str (result .inserted_id )

            dt_local =now .replace (tzinfo =pytz .utc ).astimezone (tz )
            heure =dt_local .strftime ("%H:%M")


            author_user =u_col .find_one ({"nom":username })
            raw =(author_user .get ("pdp")or "").strip ()if author_user else ""
            author_pdp =os .path .basename (raw )if raw else "guest.png"

            msg_obj ={
            "id":msg_id ,
            "author":username ,
            "author_pdp":author_pdp ,
            "content":contenu ,
            "time":heure ,
            "reactions":{},
            "author_is_plus":(plan =="plus"),
            }


            send_to_channel (channel_key ,{"type":"message","message":msg_obj })


            dead =[]

            if participants :
                if channel_type =="dm":

                    for conn ,info in list (connections .items ()):
                        user =info .get ("user")

                        if user not in participants or info .get ("channel")==channel_key :
                            continue 

                        other_candidates =[p for p in participants if p !=user ]
                        other =other_candidates [0 ]if other_candidates else user 

                        notif ={
                        "type":"dm_notification",
                        "from":username ,
                        "other":other ,
                        "content":contenu ,
                        "time":heure ,
                        }

                        try :
                            conn .send (json .dumps (notif ))
                        except Exception :
                            dead .append (conn )

                elif channel_type =="group":
                    notif ={
                    "type":"group_notification",
                    "from":username ,
                    "group_id":group_id_str ,
                    "group_name":group .get ("name","Groupe")if group else "Groupe",
                    "content":contenu ,
                    "time":heure ,
                    }

                    for conn ,info in list (connections .items ()):
                        user =info .get ("user")
                        if user not in participants or info .get ("channel")==channel_key :
                            continue 
                        try :
                            conn .send (json .dumps (notif ))
                        except Exception :
                            dead .append (conn )

            for d in dead :
                connections .pop (d ,None )

    finally :
        connections .pop (ws ,None )
        try :
            ws .close ()
        except Exception :
            pass 
