import uuid
import random
from datetime import datetime, timedelta


GAMES = {}

MAX_HP = 100
MAX_ENERGY = 5

ACTIONS = {
    "light": {
        "label": "Attaque rapide",
        "cost": 1,
        "min_dmg": 10,
        "max_dmg": 18,
        "hit_chance": 0.95,
    },
    "heavy": {
        "label": "Attaque puissante",
        "cost": 2,
        "min_dmg": 22,
        "max_dmg": 35,
        "hit_chance": 0.7,
    },
    "heal": {
        "label": "Soin",
        "cost": 2,
        "min_heal": 12,
        "max_heal": 24,
    },
    "shield": {
        "label": "Bouclier",
        "cost": 1,
    },
    "charge": {
        "label": "Recharge",
        "cost": 0,
        "energy_gain": 2,
    },
    "counter": {
        "label": "Contre-attaque",
        "cost": 2,
    },
}


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


def _create_game(ctx, opponent_name: str):
    host = ctx.username
    opponent = opponent_name
    players = [host, opponent]
    game_id = str(uuid.uuid4())

    hp = {host: MAX_HP, opponent: MAX_HP}

    energy = {host: 3, opponent: 3}

    GAMES[game_id] = {
        "id": game_id,
        "channel_key": ctx.channel_key,
        "channel_type": ctx.channel_type,
        "players": players,
        "hp": hp,
        "energy": energy,
        "choices": {host: None, opponent: None},
        "status": "pending",
        "turn": 1,
        "created_at": _now(),
    }

    payload = {
        "type": "invite",
        "game_id": game_id,
        "from": host,
        "to": opponent,
        "hp": hp,
        "energy": energy,
        "max_hp": MAX_HP,
        "max_energy": MAX_ENERGY,
    }
    ctx.send_command_to(players, "duel", payload)


def handle(ctx, args):
    _cleanup_expired()

    if not args:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Utilisation : /duel pseudo_adversaire",
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
                "message": "Tu ne peux pas te défier toi-même.",
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
                        "message": "Un duel est déjà en cours ou en attente entre ces joueurs.",
                    }
                )
                return

    _create_game(ctx, opponent)
    ctx.send_to_self(
        {
            "type": "info",
            "message": f"Invitation à un duel envoyée à {opponent }.",
        }
    )


def _get_game_or_error(ctx, payload):
    game_id = (payload or {}).get("game_id")
    if not game_id or game_id not in GAMES:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Duel introuvable ou expiré.",
            }
        )
        return None
    game = GAMES[game_id]
    if ctx.username not in game["players"]:
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Tu ne fais pas partie de ce duel.",
            }
        )
        return None
    return game


def _send_start(ctx, game):
    payload = {
        "type": "start",
        "game_id": game["id"],
        "players": game["players"],
        "hp": game["hp"],
        "energy": game["energy"],
        "max_hp": MAX_HP,
        "max_energy": MAX_ENERGY,
        "turn": game["turn"],
    }
    ctx.send_command_to(game["players"], "duel", payload)


def _resolve_turn(ctx, game):
    players = game["players"]
    p1, p2 = players[0], players[1]
    hp = game["hp"]
    energy = game["energy"]
    choices = game["choices"]
    turn = game["turn"]

    energy_regen = {p: energy[p] for p in players}

    actions_data = {}
    pending_damage = {p1: [], p2: []}
    damage_dealt = {p1: 0, p2: 0}
    damage_taken = {p1: 0, p2: 0}
    heal_done = {p1: 0, p2: 0}
    counter_flags = {p1: False, p2: False}
    self_damage_from_counter_fail = {p1: 0, p2: 0}

    for p in players:
        other = p2 if p == p1 else p1
        action_key = choices.get(p)
        spec = ACTIONS.get(action_key) if action_key else None

        if not spec:
            actions_data[p] = {
                "action": None,
                "label": "Rien",
                "cost": 0,
                "enough": True,
                "result": "none",
                "energy_after": energy_regen[p],
                "shield": False,
            }
            continue

        cost = spec["cost"]
        energy_after = energy_regen[p]
        enough = energy_after >= cost

        result_type = None
        shield_active = False

        if not enough:

            result_type = "no_energy"
        else:

            energy_after -= cost

            if action_key in ("light", "heavy"):
                hit_chance = spec["hit_chance"]
                if random.random() <= hit_chance:
                    dmg = random.randint(spec["min_dmg"], spec["max_dmg"])
                    pending_damage[other].append((dmg, p))
                    result_type = "hit"
                else:
                    result_type = "miss"

            elif action_key == "heal":
                heal = random.randint(spec["min_heal"], spec["max_heal"])
                heal_done[p] += heal
                result_type = "heal"

            elif action_key == "shield":
                shield_active = True
                result_type = "shield"

            elif action_key == "charge":
                gain = spec.get("energy_gain", 2)
                energy_after = min(MAX_ENERGY, energy_after + gain)
                result_type = "charge"

            elif action_key == "counter":
                counter_flags[p] = True
                result_type = "counter_wait"

        actions_data[p] = {
            "action": action_key,
            "label": spec["label"],
            "cost": cost,
            "enough": enough,
            "result": result_type,
            "energy_after": energy_after,
            "shield": shield_active,
        }

    for p in players:
        if not counter_flags[p]:
            continue
        if not actions_data[p]["enough"]:
            continue

        other = p2 if p == p1 else p1

        hits = pending_damage[p]
        if hits:

            total_reflected = sum(d for d, _ in hits)
            pending_damage[p] = []
            pending_damage[other].append((total_reflected, p))

            actions_data[p]["result"] = "counter_success"
            actions_data[p]["reflected"] = total_reflected
        else:

            fail_dmg = random.randint(8, 16)
            self_damage_from_counter_fail[p] += fail_dmg
            actions_data[p]["result"] = "counter_fail"
            actions_data[p]["self_damage"] = fail_dmg

    delta_hp_total = {p1: 0, p2: 0}

    for p in players:
        delta_hp_total[p] += heal_done[p]

    for p in players:
        if self_damage_from_counter_fail[p] > 0:
            dmg = self_damage_from_counter_fail[p]
            delta_hp_total[p] -= dmg
            damage_taken[p] += dmg

    for target in players:
        shielded = actions_data[target]["shield"]
        for dmg_raw, source in pending_damage[target]:
            if shielded:
                dmg_final = max(1, int(dmg_raw * 0.5))
            else:
                dmg_final = dmg_raw

            delta_hp_total[target] -= dmg_final
            damage_taken[target] += dmg_final
            damage_dealt[source] += dmg_final

    new_hp = {}
    for p in players:
        val = hp[p] + delta_hp_total[p]
        if val > MAX_HP:
            val = MAX_HP
        if val < 0:
            val = 0
        new_hp[p] = val

    new_energy = {p: actions_data[p]["energy_after"] for p in players}

    winner_player = None
    draw = False

    if new_hp[p1] <= 0 and new_hp[p2] <= 0:
        draw = True
    elif new_hp[p1] <= 0:
        winner_player = p2
    elif new_hp[p2] <= 0:
        winner_player = p1

    finished = bool(winner_player or draw)

    results = []
    for p in players:
        results.append(
            {
                "player": p,
                "hp_before": hp[p],
                "hp_after": new_hp[p],
                "energy_before": energy[p],
                "energy_after": new_energy[p],
                "action": actions_data[p]["action"],
                "label": actions_data[p]["label"],
                "result": actions_data[p]["result"],
                "damage_dealt": damage_dealt[p],
                "damage_taken": damage_taken[p],
                "healed": heal_done[p],
            }
        )

    ctx.send_command_to(
        players,
        "duel",
        {
            "type": "round_result",
            "game_id": game["id"],
            "turn": turn,
            "hp": new_hp,
            "energy": new_energy,
            "max_hp": MAX_HP,
            "max_energy": MAX_ENERGY,
            "results": results,
            "winner": winner_player,
            "draw": draw,
            "finished": finished,
        },
    )

    if finished:
        ctx.send_command_to(
            players,
            "duel",
            {
                "type": "match_end",
                "game_id": game["id"],
                "winner": winner_player,
                "hp": new_hp,
                "energy": new_energy,
                "players": players,
                "draw": draw,
            },
        )
        game["status"] = "finished"
        GAMES.pop(game["id"], None)
    else:
        game["hp"] = new_hp
        game["energy"] = new_energy
        game["turn"] = turn + 1
        for p in players:
            game["choices"][p] = None


def handle_event(ctx, event_name: str, payload: dict):
    _cleanup_expired()
    event_name = (event_name or "").strip().lower()

    if event_name not in ("accept", "decline", "cancel", "action"):
        ctx.send_to_self(
            {
                "type": "error",
                "message": "Action de duel invalide.",
            }
        )
        return

    game = _get_game_or_error(ctx, payload)
    if not game:
        return

    players = game["players"]
    p1, p2 = players[0], players[1]

    if event_name == "accept":
        invited = p2
        if ctx.username != invited:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Seul l'adversaire peut accepter le duel.",
                }
            )
            return
        if game["status"] != "pending":
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Ce duel a déjà été accepté ou annulé.",
                }
            )
            return
        game["status"] = "playing"
        _send_start(ctx, game)
        return

    if event_name == "decline":
        invited = p2
        if ctx.username != invited:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Seul l'adversaire peut refuser le duel.",
                }
            )
            return
        if game["status"] != "pending":
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Ce duel a déjà été accepté ou annulé.",
                }
            )
            return
        game["status"] = "finished"
        ctx.send_command_to(
            players,
            "duel",
            {
                "type": "canceled",
                "game_id": game["id"],
                "reason": f"{ctx .username } a refusé le duel.",
            },
        )
        GAMES.pop(game["id"], None)
        return

    if event_name == "cancel":
        if game["status"] not in ("pending", "playing"):
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Le duel est déjà terminé.",
                }
            )
            return

        game["status"] = "finished"
        ctx.send_command_to(
            players,
            "duel",
            {
                "type": "canceled",
                "game_id": game["id"],
                "reason": f"{ctx .username } a annulé le duel.",
            },
        )
        GAMES.pop(game["id"], None)
        return

    if event_name == "action":
        if game["status"] != "playing":
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Le duel n'est pas en cours.",
                }
            )
            return

        action_key = (payload or {}).get("action")
        if not isinstance(action_key, str) or action_key not in ACTIONS:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Action inconnue.",
                }
            )
            return

        if game["choices"][ctx.username] is not None:
            ctx.send_to_self(
                {
                    "type": "error",
                    "message": "Tu as déjà choisi ton action pour ce tour.",
                }
            )
            return

        game["choices"][ctx.username] = action_key

        if all(game["choices"].get(p) is not None for p in players):
            _resolve_turn(ctx, game)
        else:
            ctx.send_to_self(
                {
                    "type": "info",
                    "message": "Action enregistrée, en attente de l'autre joueur.",
                }
            )
