import uuid
from datetime import datetime, timedelta

GAMES = {}

LINES = [
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
]


def _now():
    return datetime.utcnow()


def _cleanup_expired():
    expiration = _now() - timedelta(hours=1)
    to_delete = []
    for gid, g in GAMES.items():
        if g.get("created_at") and g["created_at"] < expiration:
            to_delete.append(gid)
        elif g.get("status") == "finished":
            to_delete.append(gid)
    for gid in to_delete:
        GAMES.pop(gid, None)


def _find_user(u_col, username: str):
    return u_col.find_one({"nom": username})


def _check_winner(board):
    for a, b, c in LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def _is_draw(board):
    return all(cell in ("X", "O") for cell in board)


def _create_game(ctx, opponent_name: str):
    host = ctx.username
    opponent = opponent_name
    players = [host, opponent]
    game_id = str(uuid.uuid4())

    symbols = {
        host: "X",
        opponent: "O",
    }

    GAMES[game_id] = {
        "id": game_id,
        "channel_key": ctx.channel_key,
        "channel_type": ctx.channel_type,
        "players": players,
        "symbols": symbols,
        "board": [""] * 9,
        "current_player": host,
        "status": "pending",
        "created_at": _now(),
    }

    payload = {
        "type": "invite",
        "game_id": game_id,
        "from": host,
        "to": opponent,
        "symbols": symbols,
        "first_player": host,
    }
    ctx.send_command_to(players, "oxo", payload)


def handle(ctx, args):
    _cleanup_expired()

    if not args:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Utilisation : /oxo pseudo_adversaire",
            }
        )
        return

    opponent = args[0].strip()
    if opponent.startswith("@"):
        opponent = opponent[1:]

    if not opponent:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Tu dois spécifier un pseudo.",
            }
        )
        return

    if opponent == ctx.username:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Tu ne peux pas jouer contre toi-même.",
            }
        )
        return

    target_user = _find_user(ctx.u_col, opponent)
    if not target_user:
        ctx.send_to_self(
            {
                "type": "error",
                "message": f"Utilisateur introuvable : {opponent }.",
            }
        )
        return

    for g in GAMES.values():
        if g["channel_key"] == ctx.channel_key and g["status"] in (
            "pending",
            "playing",
        ):
            if ctx.username in g["players"] or opponent in g["players"]:
                ctx.send_to_self(
                    {
                        "type": "error",
                        "message": "Un oxo est déjà en cours ou en attente entre ces joueurs.",
                    }
                )
                return

    _create_game(ctx, opponent)
    ctx.send_to_self(
        {
            "type": "info",
            "message": f"Invitation oxo envoyée à {opponent }.",
        }
    )


def _get_game_or_error(ctx, payload):
    game_id = (payload or {}).get("game_id")
    if not game_id or game_id not in GAMES:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Partie oxo introuvable ou expirée.",
            }
        )
        return None
    game = GAMES[game_id]
    if ctx.username not in game["players"]:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Tu ne fais pas partie de cette partie.",
            }
        )
        return None
    return game


def _send_start(ctx, game):
    payload = {
        "type": "start",
        "game_id": game["id"],
        "players": game["players"],
        "symbols": game["symbols"],
        "board": game["board"],
        "current_player": game["current_player"],
    }
    ctx.send_command_to(game["players"], "oxo", payload)


def _broadcast_update(ctx, game, last_move_index, last_player, winner=None, draw=False):
    payload = {
        "type": "update",
        "game_id": game["id"],
        "players": game["players"],
        "symbols": game["symbols"],
        "board": game["board"],
        "current_player": game["current_player"],
        "winner": winner,
        "draw": draw,
        "last_move": {
            "index": last_move_index,
            "player": last_player,
        },
    }
    ctx.send_command_to(game["players"], "oxo", payload)


def handle_event(ctx, event_name: str, payload: dict):
    _cleanup_expired()
    event_name = (event_name or "").strip().lower()

    if event_name not in ("accept", "decline", "cancel", "play"):
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Action oxo invalide.",
            }
        )
        return

    game = _get_game_or_error(ctx, payload)
    if not game:
        return

    if event_name == "accept":
        invited = game["players"][1]
        if ctx.username != invited:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Seul l'adversaire peut accepter la partie.",
                }
            )
            return
        if game["status"] != "pending":
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Cette partie a déjà été acceptée ou annulée.",
                }
            )
            return
        game["status"] = "playing"
        _send_start(ctx, game)
        return

    if event_name == "decline":
        invited = game["players"][1]
        if ctx.username != invited:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Seul l'adversaire peut refuser la partie.",
                }
            )
            return
        if game["status"] != "pending":
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Cette partie a déjà été acceptée ou annulée.",
                }
            )
            return
        game["status"] = "finished"
        ctx.send_command_to(
            game["players"],
            "oxo",
            {
                "type": "canceled",
                "game_id": game["id"],
                "reason": f"{ctx .username } a refusé l'invitation.",
            },
        )
        GAMES.pop(game["id"], None)
        return

    if event_name == "cancel":
        if game["status"] not in ("pending", "playing"):
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "La partie est déjà terminée.",
                }
            )
            return

        game["status"] = "finished"
        ctx.send_command_to(
            game["players"],
            "oxo",
            {
                "type": "canceled",
                "game_id": game["id"],
                "reason": f"{ctx .username } a annulé la partie.",
            },
        )
        GAMES.pop(game["id"], None)
        return

    if event_name == "play":
        if game["status"] != "playing":
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "La partie n'est pas en cours.",
                }
            )
            return

        if ctx.username != game["current_player"]:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Ce n'est pas ton tour.",
                }
            )
            return

        index = (payload or {}).get("index")
        if not isinstance(index, int) or not (0 <= index <= 8):
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Case invalide.",
                }
            )
            return

        board = game["board"]
        if board[index] in ("X", "O"):
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Cette case est déjà prise.",
                }
            )
            return

        symbol = game["symbols"][ctx.username]
        board[index] = symbol

        winner_symbol = _check_winner(board)
        draw = False
        winner_player = None

        if winner_symbol:
            for player, s in game["symbols"].items():
                if s == winner_symbol:
                    winner_player = player
                    break
            game["status"] = "finished"
            _broadcast_update(
                ctx, game, index, ctx.username, winner=winner_player, draw=False
            )

            ctx.send_command_to(
                game["players"],
                "oxo",
                {
                    "type": "match_end",
                    "game_id": game["id"],
                    "winner": winner_player,
                    "board": board,
                    "players": game["players"],
                    "symbols": game["symbols"],
                },
            )
            GAMES.pop(game["id"], None)
            return

        if _is_draw(board):
            draw = True
            game["status"] = "finished"
            _broadcast_update(ctx, game, index, ctx.username, winner=None, draw=True)

            ctx.send_command_to(
                game["players"],
                "oxo",
                {
                    "type": "match_end",
                    "game_id": game["id"],
                    "winner": None,
                    "board": board,
                    "players": game["players"],
                    "symbols": game["symbols"],
                    "draw": True,
                },
            )
            GAMES.pop(game["id"], None)
            return

        p1, p2 = game["players"]
        game["current_player"] = p2 if ctx.username == p1 else p1

        _broadcast_update(ctx, game, index, ctx.username, winner=None, draw=False)
