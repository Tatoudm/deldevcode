
import json 
from datetime import datetime 

import pytz 
from bson .objectid import ObjectId 

import extensions 
from extensions import sock 
from utils .auth_utils import is_admin 


def messages_col ():
    """Collection des messages de chat."""
    return extensions .db .messages 


def reports_col ():
    """Collection des signalements de messages."""
    return extensions .db .message_reports 








@sock .route ("/ws/admin/messages")
def admin_messages_ws (ws ):
    from flask import session as ws_session 


    if "util"not in ws_session or not is_admin ():
        try :
            ws .send (json .dumps ({"type":"error","message":"Accès refusé"}))
        except Exception :
            pass 
        try :
            ws .close ()
        except Exception :
            pass 
        return 

    m_col =messages_col ()
    r_col =reports_col ()
    tz =pytz .timezone ("Europe/Brussels")

    while True :
        data =ws .receive ()
        if data is None :
            break 

        try :
            payload =json .loads (data )
        except Exception :

            continue 

        msg_type =(payload .get ("type")or "").strip ()




        if msg_type =="list":
            author =(payload .get ("author")or "").strip ()
            channel =(payload .get ("channel")or "").strip ()
            limit =int (payload .get ("limit")or 100 )

            query ={}
            if author :
                query ["author"]={"$regex":author ,"$options":"i"}
            if channel :
                query ["channel"]=channel 

            cursor =(
            m_col .find (query )
            .sort ("created_at",-1 )
            .limit (limit )
            )

            messages =[]
            for m in cursor :
                created_at =m .get ("created_at")
                if isinstance (created_at ,datetime ):
                    try :
                        local_dt =created_at .astimezone (tz )
                    except ValueError :

                        local_dt =tz .localize (created_at )
                    time_str =local_dt .strftime ("%d/%m/%Y %H:%M")
                else :
                    time_str =""

                messages .append (
                {
                "id":str (m ["_id"]),
                "author":m .get ("author"),
                "content":m .get ("content"),
                "time":time_str ,
                "channel":m .get ("channel","general"),
                }
                )

            try :
                ws .send (json .dumps ({"type":"update","messages":messages }))
            except Exception :
                break 




        elif msg_type =="list_reports":
            limit =int (payload .get ("limit")or 100 )


            pipeline =[
            {
            "$group":{
            "_id":"$message_id",
            "count":{"$sum":1 },
            "last_reason":{"$last":"$reason"},
            "last_created_at":{"$last":"$created_at"},
            }
            },
            {"$sort":{"count":-1 ,"last_created_at":-1 }},
            {"$limit":limit },
            ]

            reported_messages =[]
            try :
                for rep in r_col .aggregate (pipeline ):
                    msg_id =rep .get ("_id")
                    if not msg_id :
                        continue 

                    msg_doc =m_col .find_one ({"_id":msg_id })
                    if not msg_doc :
                        continue 

                    created_at =msg_doc .get ("created_at")
                    if isinstance (created_at ,datetime ):
                        try :
                            local_dt =created_at .astimezone (tz )
                        except ValueError :
                            local_dt =tz .localize (created_at )
                        time_str =local_dt .strftime ("%d/%m/%Y %H:%M")
                    else :
                        time_str =""

                    reported_messages .append (
                    {
                    "id":str (msg_doc ["_id"]),
                    "author":msg_doc .get ("author"),
                    "content":msg_doc .get ("content"),
                    "time":time_str ,
                    "channel":msg_doc .get ("channel","general"),
                    "reports_count":rep .get ("count",0 ),
                    "last_reason":rep .get ("last_reason")or "",
                    }
                    )
            except Exception :

                reported_messages =[]

            try :
                ws .send (
                json .dumps (
                {
                "type":"reports_update",
                "messages":reported_messages ,
                }
                )
                )
            except Exception :
                break 




        else :
            continue 


    try :
        ws .close ()
    except Exception :
        pass 
