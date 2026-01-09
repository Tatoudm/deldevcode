

def handle (
cmd_name ,
args ,
username ,
channel_type ,
channel_key ,
participants ,
ws ,
u_col ,
m_col ,
g_col ,
):
    """
    Exemple très simple : répond juste un message système
    à l'utilisateur qui a tapé /test.
    """
    from datetime import datetime 



    import json 

    payload ={
    "type":"system",
    "message":f"[TEST] Salut {username }, commande /{cmd_name } bien reçue !",
    "time":datetime .now ().strftime ("%H:%M"),
    }
    try :
        ws .send (json .dumps (payload ))
    except Exception :
        pass 


    return True 
