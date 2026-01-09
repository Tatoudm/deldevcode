
import uuid 
from datetime import datetime ,timedelta 


GAMES ={}

CHOICES =["rock","paper","scissors"]
EMOJIS ={
"rock":"🪨",
"paper":"📄",
"scissors":"✂️",
}


def _now ():
    return datetime .utcnow ()


def _cleanup_expired ():
    """
    On nettoie les parties vieilles ou terminées.
    """
    expiration =_now ()-timedelta (hours =1 )
    to_delete =[]
    for gid ,g in GAMES .items ():
        if g .get ("created_at")and g ["created_at"]<expiration :
            to_delete .append (gid )
        elif g .get ("status")=="finished":
            to_delete .append (gid )
    for gid in to_delete :
        GAMES .pop (gid ,None )


def _create_game (ctx ,opponent_name :str ):
    host =ctx .username 
    players =[host ,opponent_name ]
    game_id =str (uuid .uuid4 ())


    wins_to =3 

    GAMES [game_id ]={
    "id":game_id ,
    "channel_key":ctx .channel_key ,
    "channel_type":ctx .channel_type ,
    "players":players ,
    "scores":{host :0 ,opponent_name :0 },
    "round":1 ,
    "wins_to":wins_to ,
    "choices":{host :None ,opponent_name :None },
    "status":"pending",
    "created_at":_now (),
    }

    payload ={
    "type":"invite",
    "game_id":game_id ,
    "from":host ,
    "to":opponent_name ,
    "wins_to":wins_to ,
    }
    ctx .send_command_to (players ,"chifoumi",payload )


def _find_user (u_col ,username :str ):
    return u_col .find_one ({"nom":username })


def handle (ctx ,args ):
    """
    Commande /chifoumi pseudo
    """
    _cleanup_expired ()

    if not args :
        ctx .send_to_self (
        {
        "type":"error",
        "message":"Utilisation : /chifoumi pseudo_adversaire",
        }
        )
        return 

    opponent =args [0 ].strip ()
    if opponent .startswith ("@"):
        opponent =opponent [1 :]

    if not opponent :
        ctx .send_to_self (
        {
        "type":"error",
        "message":"Tu dois spécifier un pseudo.",
        }
        )
        return 

    if opponent ==ctx .username :
        ctx .send_to_self (
        {
        "type":"error",
        "message":"Tu ne peux pas jouer contre toi-même.",
        }
        )
        return 

    target_user =_find_user (ctx .u_col ,opponent )
    if not target_user :
        ctx .send_to_self (
        {
        "type":"error",
        "message":f"Utilisateur introuvable : {opponent }.",
        }
        )
        return 


    for g in GAMES .values ():
        if (
        g ["channel_key"]==ctx .channel_key 
        and g ["status"]in ("pending","playing")
        ):
            if ctx .username in g ["players"]or opponent in g ["players"]:
                ctx .send_to_self (
                {
                "type":"error",
                "message":"Un chifoumi est déjà en cours ou en attente entre ces joueurs.",
                }
                )
                return 

    _create_game (ctx ,opponent )
    ctx .send_to_self (
    {
    "type":"info",
    "message":f"Invitation chifoumi envoyée à {opponent }.",
    }
    )


def _get_game_or_error (ctx ,payload ):
    game_id =(payload or {}).get ("game_id")
    if not game_id or game_id not in GAMES :
        ctx .send_to_self (
        {
        "type":"error",
        "message":"Partie chifoumi introuvable ou expirée.",
        }
        )
        return None 
    game =GAMES [game_id ]
    if ctx .username not in game ["players"]:
        ctx .send_to_self (
        {
        "type":"error",
        "message":"Tu ne fais pas partie de cette partie.",
        }
        )
        return None 
    return game 


def _send_start (ctx ,game ):
    payload ={
    "type":"start",
    "game_id":game ["id"],
    "players":game ["players"],
    "scores":game ["scores"],
    "round":game ["round"],
    "wins_to":game ["wins_to"],
    }
    ctx .send_command_to (game ["players"],"chifoumi",payload )


def _beats (a :str ,b :str )->bool :
    return (a =="rock"and b =="scissors")or (a =="paper"and b =="rock")or (a =="scissors"and b =="paper")


def _resolve_round (ctx ,game ):
    p1 ,p2 =game ["players"]
    c1 =game ["choices"][p1 ]
    c2 =game ["choices"][p2 ]

    if c1 not in CHOICES or c2 not in CHOICES :
        return 


    winner =None 
    if c1 ==c2 :
        winner =None 
    elif _beats (c1 ,c2 ):
        winner =p1 
    elif _beats (c2 ,c1 ):
        winner =p2 

    if winner is not None :
        game ["scores"][winner ]+=1 

    current_round =game ["round"]
    wins_to =game ["wins_to"]


    done =False 
    match_winner =None 

    for player in game ["players"]:
        if game ["scores"][player ]>=wins_to :
            done =True 
            match_winner =player 
            break 


    choices_payload =[
    {
    "player":p1 ,
    "choice":c1 ,
    "emoji":EMOJIS .get (c1 ,"❔"),
    },
    {
    "player":p2 ,
    "choice":c2 ,
    "emoji":EMOJIS .get (c2 ,"❔"),
    },
    ]

    payload ={
    "type":"round_result",
    "game_id":game ["id"],
    "round":current_round ,
    "choices":choices_payload ,
    "winner":winner ,
    "scores":game ["scores"],
    "wins_to":wins_to ,
    "finished":done ,
    "match_winner":match_winner ,
    }
    ctx .send_command_to (game ["players"],"chifoumi",payload )

    if done :
        end_payload ={
        "type":"match_end",
        "game_id":game ["id"],
        "winner":match_winner ,
        "scores":game ["scores"],
        "rounds_played":current_round ,
        "players":game ["players"],
        }
        ctx .send_command_to (game ["players"],"chifoumi",end_payload )
        game ["status"]="finished"
        GAMES .pop (game ["id"],None )
    else :

        game ["round"]=current_round +1 
        for player in game ["players"]:
            game ["choices"][player ]=None 


def handle_event (ctx ,event_name :str ,payload :dict ):
    """
    Events envoyés par le JS :
      - accept / decline / cancel
      - choice (rock/paper/scissors)
    """
    _cleanup_expired ()
    event_name =(event_name or "").strip ().lower ()

    if event_name not in ("accept","decline","cancel","choice"):
        ctx .send_to_self (
        {
        "type":"error",
        "message":"Action chifoumi invalide.",
        }
        )
        return 

    game =_get_game_or_error (ctx ,payload )
    if not game :
        return 


    if event_name =="accept":

        if ctx .username !=game ["players"][1 ]:
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Seul l'adversaire peut accepter la partie.",
            }
            )
            return 
        if game ["status"]!="pending":
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Cette partie a déjà été acceptée ou annulée.",
            }
            )
            return 
        game ["status"]="playing"
        _send_start (ctx ,game )
        return 


    if event_name =="decline":
        if ctx .username !=game ["players"][1 ]:
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Seul l'adversaire peut refuser la partie.",
            }
            )
            return 
        if game ["status"]!="pending":
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Cette partie a déjà été acceptée ou annulée.",
            }
            )
            return 
        game ["status"]="finished"
        ctx .send_command_to (
        game ["players"],
        "chifoumi",
        {
        "type":"canceled",
        "game_id":game ["id"],
        "reason":f"{ctx .username } a refusé l'invitation.",
        },
        )
        GAMES .pop (game ["id"],None )
        return 


    if event_name =="cancel":
        if game ["status"]not in ("pending","playing"):
            ctx .send_to_self (
            {
            "type":"error",
            "message":"La partie est déjà terminée.",
            }
            )
            return 
        game ["status"]="finished"
        ctx .send_command_to (
        game ["players"],
        "chifoumi",
        {
        "type":"canceled",
        "game_id":game ["id"],
        "reason":f"{ctx .username } a annulé la partie.",
        },
        )
        GAMES .pop (game ["id"],None )
        return 


    if event_name =="choice":
        if game ["status"]!="playing":
            ctx .send_to_self (
            {
            "type":"error",
            "message":"La partie n'est pas en cours.",
            }
            )
            return 

        raw_choice =(payload or {}).get ("choice")
        if not isinstance (raw_choice ,str ):
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Choix invalide.",
            }
            )
            return 

        choice =raw_choice .strip ().lower ()
        if choice not in CHOICES :
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Choix invalide. Utilise rock, paper ou scissors.",
            }
            )
            return 

        if game ["choices"][ctx .username ]is not None :
            ctx .send_to_self (
            {
            "type":"error",
            "message":"Tu as déjà joué pour cette manche.",
            }
            )
            return 

        game ["choices"][ctx .username ]=choice 

        p1 ,p2 =game ["players"]
        if game ["choices"][p1 ]is not None and game ["choices"][p2 ]is not None :
            _resolve_round (ctx ,game )
        else :
            ctx .send_to_self (
            {
            "type":"info",
            "message":"Choix envoyé, en attente de l'autre joueur.",
            }
            )
