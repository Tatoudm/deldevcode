// static/commands/duel.js
(function () {
    const ACTIONS = {
        light: {
            key: "light",
            label: "Attaque rapide",
            desc: "Dégâts moyens, peu coûteux.",
            cost: 1,
            icon: "⚔️",
        },
        heavy: {
            key: "heavy",
            label: "Attaque puissante",
            desc: "Gros dégâts, peut rater.",
            cost: 2,
            icon: "💥",
        },
        heal: {
            key: "heal",
            label: "Soin",
            desc: "Récupère des PV.",
            cost: 2,
            icon: "✨",
        },
        shield: {
            key: "shield",
            label: "Bouclier",
            desc: "Réduit les dégâts reçus ce tour.",
            cost: 1,
            icon: "🛡️",
        },
        charge: {
            key: "charge",
            label: "Recharge",
            desc: "Ne fait rien ce tour mais +2 énergie.",
            cost: 0,
            icon: "⚡",
        },
        counter: {
            key: "counter",
            label: "Contre-attaque",
            desc: "Si l'autre attaque, ses dégâts se retournent contre lui. Sinon tu te blesses.",
            cost: 2,
            icon: "🔁",
        },
    };

    const state = {
        gameId: null,
        me: null,
        opponent: null,
        players: [],
        hp: {},
        energy: {},
        maxHp: 100,
        maxEnergy: 5,
        turn: 1,
        finished: false,
        waitingForResolution: false,
    };

    function resetState() {
        state.gameId = null;
        state.me = null;
        state.opponent = null;
        state.players = [];
        state.hp = {};
        state.energy = {};
        state.maxHp = 100;
        state.maxEnergy = 5;
        state.turn = 1;
        state.finished = false;
        state.waitingForResolution = false;
    }

    function setStateFromStart(payload, me) {
        state.gameId = payload.game_id;
        state.players = payload.players || [];
        state.hp = payload.hp || {};
        state.energy = payload.energy || {};
        state.maxHp = payload.max_hp || state.maxHp;
        state.maxEnergy = payload.max_energy || state.maxEnergy;
        state.turn = payload.turn || 1;
        state.me = me;
        state.opponent = state.players.find((p) => p !== me) || null;
        state.finished = false;
        state.waitingForResolution = false;
    }

    function renderInvite(ctx, payload, me) {
        resetState();
        state.gameId = payload.game_id;
        state.me = me;
        state.players = [payload.from, payload.to];
        state.hp = payload.hp || {};
        state.energy = payload.energy || {};
        state.maxHp = payload.max_hp || state.maxHp;
        state.maxEnergy = payload.max_energy || state.maxEnergy;
        state.opponent = me === payload.to ? payload.from : payload.to;
        state.turn = 1;
        state.finished = false;
        state.waitingForResolution = false;

        const isTarget = me === payload.to;
        const title = "Duel RPG";
        const subtitle = isTarget
            ? `${payload.from} te défie en duel !`
            : `Invitation envoyée à ${payload.to}…`;

        ctx.openModal(title, subtitle);

        const hpInfo = `
            <p class="text-xs text-slate-500">
                PV de départ : <span class="font-semibold">${state.maxHp}</span><br>
                Énergie max : <span class="font-semibold">${state.maxEnergy}</span>
            </p>
        `;

        const actionsInfo = `
            <ul class="text-xs text-slate-500 list-disc list-inside space-y-1">
                <li>⚔️ Attaque rapide : dégâts moyens, 1 énergie</li>
                <li>💥 Attaque puissante : gros dégâts mais peut rater, 2 énergies</li>
                <li>✨ Soin : récupère des PV, 2 énergies</li>
                <li>🛡️ Bouclier : réduit les dégâts ce tour, 1 énergie</li>
                <li>⚡ Recharge : +2 énergie, 0 énergie</li>
                <li>🔁 Contre-attaque : si l'autre t'attaque, ses dégâts se retournent contre lui. Sinon tu prends des dégâts.</li>
            </ul>
        `;

        if (isTarget) {
            ctx.setModalContent(`
                <div class="space-y-3">
                    <p class="text-sm text-slate-700">
                        ${payload.from} te propose un mini duel RPG.
                    </p>
                    ${hpInfo}
                    ${actionsInfo}
                </div>
            `);
            ctx.setModalActions(`
                <div class="flex justify-end gap-2">
                    <button id="duel-decline" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                        Refuser
                    </button>
                    <button id="duel-accept" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                        Accepter
                    </button>
                </div>
            `);

            const btnAccept = document.getElementById("duel-accept");
            const btnDecline = document.getElementById("duel-decline");

            if (btnAccept) {
                btnAccept.addEventListener("click", () => {
                    ctx.sendEvent("duel", "accept", {
                        game_id: state.gameId,
                    });
                });
            }

            if (btnDecline) {
                btnDecline.addEventListener("click", () => {
                    ctx.sendEvent("duel", "decline", {
                        game_id: state.gameId,
                    });
                    ctx.closeModal();
                    resetState();
                });
            }
        } else {
            ctx.setModalContent(`
                <div class="space-y-3">
                    <p class="text-sm text-slate-700">
                        En attente de la réponse de <span class="font-semibold">${payload.to}</span>…
                    </p>
                    ${hpInfo}
                    ${actionsInfo}
                </div>
            `);
            ctx.setModalActions(`
                <div class="flex justify-end">
                    <button id="duel-cancel" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                        Annuler
                    </button>
                </div>
            `);

            const btnCancel = document.getElementById("duel-cancel");
            if (btnCancel) {
                btnCancel.addEventListener("click", () => {
                    ctx.sendEvent("duel", "cancel", {
                        game_id: state.gameId,
                    });
                    ctx.closeModal();
                    resetState();
                });
            }
        }
    }

    function renderHpBar(current, max) {
        const pct = Math.max(0, Math.min(100, (current / max) * 100));
        return `
            <div class="w-full h-2 rounded-full bg-slate-200/80 overflow-hidden">
                <div class="h-2 rounded-full bg-emerald-500" style="width:${pct}%;"></div>
            </div>
        `;
    }

    function renderActionScreen(ctx) {
        const me = state.me;
        const opponent = state.opponent || "Adversaire";
        const hpMe = state.hp[me] ?? state.maxHp;
        const hpOpp = state.hp[opponent] ?? state.maxHp;
        const enMe = state.energy[me] ?? 0;
        const enOpp = state.energy[opponent] ?? 0;

        state.finished = false;
        state.waitingForResolution = false;

        ctx.openModal(
            "Duel RPG",
            `Tour ${state.turn} · ${me} vs ${opponent}`
        );

        let actionsHtml = "";
        Object.values(ACTIONS).forEach((a) => {
            actionsHtml += `
                <button
                    data-action="${a.key}"
                    class="duel-action flex-1 min-w-[120px] px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-emerald-50 text-xs text-left space-y-1 transition"
                >
                    <div class="flex items-center justify-between gap-2">
                        <span class="text-lg">${a.icon}</span>
                        <span class="font-semibold text-slate-800 flex-1 truncate">
                            ${a.label}
                        </span>
                        <span class="text-[11px] text-slate-500">
                            ${a.cost} ⚡
                        </span>
                    </div>
                    <p class="text-[11px] text-slate-500">
                        ${a.desc}
                    </p>
                </button>
            `;
        });

        ctx.setModalContent(`
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-4 text-xs text-slate-600">
                    <div class="space-y-1">
                        <div class="flex items-center justify-between">
                            <span class="font-semibold text-slate-800">${me}</span>
                            <span>${hpMe}/${state.maxHp} PV</span>
                        </div>
                        ${renderHpBar(hpMe, state.maxHp)}
                        <div class="mt-1 text-[11px] text-slate-500">
                            Énergie : <span class="font-semibold">${enMe}</span> / ${state.maxEnergy}
                        </div>
                    </div>
                    <div class="space-y-1 text-right">
                        <div class="flex items-center justify-between">
                            <span>${hpOpp}/${state.maxHp} PV</span>
                            <span class="font-semibold text-slate-800">${opponent}</span>
                        </div>
                        ${renderHpBar(hpOpp, state.maxHp)}
                        <div class="mt-1 text-[11px] text-slate-500">
                            Énergie : <span class="font-semibold">${enOpp}</span> / ${state.maxEnergy}
                        </div>
                    </div>
                </div>

                <div class="space-y-2">
                    <p class="text-[11px] text-slate-500 text-center">
                        Choisis ton action pour ce tour :
                    </p>
                    <div class="flex flex-wrap gap-2 justify-center">
                        ${actionsHtml}
                    </div>
                </div>

                <p id="duel-status" class="text-[11px] text-center text-slate-500">
                    À toi de jouer.
                </p>
            </div>
        `);

        ctx.setModalActions(`
            <div class="flex justify-end">
                <button id="duel-cancel" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                    Abandonner
                </button>
            </div>
        `);

        const statusEl = document.getElementById("duel-status");
        const btnCancel = document.getElementById("duel-cancel");
        const buttons = Array.from(
            document.querySelectorAll(".duel-action")
        );

        if (btnCancel) {
            btnCancel.addEventListener("click", () => {
                if (state.finished) {
                    ctx.closeModal();
                    resetState();
                    return;
                }
                ctx.sendEvent("duel", "cancel", {
                    game_id: state.gameId,
                });
                ctx.closeModal();
                resetState();
            });
        }

        buttons.forEach((btn) => {
            const actionKey = btn.getAttribute("data-action");
            const a = ACTIONS[actionKey];
            if (!a) return;

            btn.addEventListener("click", () => {
                if (state.finished || state.waitingForResolution) return;

                const currentEnergy = state.energy[me] ?? 0;
                if (currentEnergy < a.cost) {
                    if (typeof ctx.toast === "function") {
                        ctx.toast(
                            `Tu n'as pas assez d'énergie pour ${a.label} (coût ${a.cost}).`,
                            "error"
                        );
                    }
                    if (statusEl) {
                        statusEl.textContent = "Pas assez d'énergie pour cette action.";
                    }
                    return;
                }

                state.waitingForResolution = true;

                buttons.forEach((b) => {
                    b.classList.add("opacity-60");
                    b.classList.remove("hover:bg-emerald-50");
                    b.disabled = true;
                });
                btn.classList.add("ring-2", "ring-emerald-400");

                if (statusEl) {
                    statusEl.textContent =
                        "Action envoyée. En attente de l'autre joueur…";
                }

                ctx.sendEvent("duel", "action", {
                    game_id: state.gameId,
                    action: actionKey,
                });
            });
        });
    }

    function renderRoundResult(ctx, payload) {
        const turn = payload.turn || state.turn;
        const results = payload.results || [];
        const hp = payload.hp || state.hp;
        const energy = payload.energy || state.energy;
        const winner = payload.winner || null;
        const draw = !!payload.draw;
        const finished = !!payload.finished;

        state.hp = hp;
        state.energy = energy;
        state.turn = turn + (finished ? 0 : 1);
        state.finished = finished;
        state.waitingForResolution = false;

        const me = state.me;
        const opponent = state.opponent || "Adversaire";

        const rMe = results.find((r) => r.player === me) || {};
        const rOpp = results.find((r) => r.player === opponent) || {};

        function actionEmoji(res) {
            const a = ACTIONS[res.action];
            return a ? a.icon : "❔";
        }

        function actionLabel(res) {
            if (!res.action) return "Aucune action";
            const a = ACTIONS[res.action];
            return a ? a.label : res.action;
        }

        function resultText(res) {
            if (res.result === "hit") {
                return `touche et inflige ${res.damage_dealt || 0} dégâts.`;
            }
            if (res.result === "miss") {
                return "rate son attaque.";
            }
            if (res.result === "heal") {
                return `se soigne de ${res.healed || 0} PV.`;
            }
            if (res.result === "shield") {
                return "se protège derrière un bouclier.";
            }
            if (res.result === "charge") {
                return "se concentre et recharge son énergie.";
            }
            if (res.result === "counter_success") {
                return "réussit sa contre-attaque : les dégâts se retournent contre l'adversaire.";
            }
            if (res.result === "counter_fail") {
                return "tente une contre-attaque dans le vide et se blesse.";
            }
            if (res.result === "no_energy") {
                return "n'avait pas assez d'énergie, l'action échoue.";
            }
            return "ne fait rien de spécial.";
        }

        let globalLine = "";
        if (draw) {
            globalLine = `Égalité ! Les deux combattants tombent en même temps…`;
        } else if (winner) {
            globalLine = `${winner} met fin au duel à ce tour !`;
        } else {
            globalLine = `Le combat continue…`;
        }

        ctx.openModal(
            "Duel RPG",
            `Résultat du tour ${turn}`
        );

        ctx.setModalContent(`
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-4 text-xs text-slate-600">
                    <div class="space-y-1">
                        <div class="flex items-center justify-between">
                            <span class="font-semibold text-slate-800">${me}</span>
                            <span>${hp[me] ?? 0}/${state.maxHp} PV</span>
                        </div>
                        ${renderHpBar(hp[me] ?? 0, state.maxHp)}
                        <div class="mt-1 text-[11px] text-slate-500">
                            Énergie : <span class="font-semibold">${energy[me] ?? 0}</span> / ${state.maxEnergy}
                        </div>
                    </div>
                    <div class="space-y-1 text-right">
                        <div class="flex items-center justify-between">
                            <span>${hp[opponent] ?? 0}/${state.maxHp} PV</span>
                            <span class="font-semibold text-slate-800">${opponent}</span>
                        </div>
                        ${renderHpBar(hp[opponent] ?? 0, state.maxHp)}
                        <div class="mt-1 text-[11px] text-slate-500">
                            Énergie : <span class="font-semibold">${energy[opponent] ?? 0}</span> / ${state.maxEnergy}
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-center gap-8 text-3xl md:text-4xl">
                    <div class="flex flex-col items-center gap-1">
                        <span>${actionEmoji(rMe)}</span>
                        <span class="text-[11px] text-slate-500">${me}</span>
                    </div>
                    <div class="text-xl text-slate-400">vs</div>
                    <div class="flex flex-col items-center gap-1">
                        <span>${actionEmoji(rOpp)}</span>
                        <span class="text-[11px] text-slate-500">${opponent}</span>
                    </div>
                </div>

                <div class="space-y-1 text-xs text-slate-700">
                    <p><span class="font-semibold">${me}</span> ${actionLabel(rMe)} et ${resultText(rMe)}</p>
                    <p><span class="font-semibold">${opponent}</span> ${actionLabel(rOpp)} et ${resultText(rOpp)}</p>
                </div>

                <div class="text-center text-xs text-slate-600">
                    ${globalLine}
                </div>
            </div>
        `);

        if (finished) {
            ctx.setModalActions(`
                <div class="flex justify-end">
                    <button id="duel-close" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                        Fermer
                    </button>
                </div>
            `);

            const btnClose = document.getElementById("duel-close");
            if (btnClose) {
                btnClose.addEventListener("click", () => {
                    ctx.closeModal();
                    resetState();
                });
            }
        } else {
            ctx.setModalActions(`
                <div class="flex justify-end">
                    <button id="duel-next" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                        Tour suivant
                    </button>
                </div>
            `);

            const btnNext = document.getElementById("duel-next");
            if (btnNext) {
                btnNext.addEventListener("click", () => {
                    renderActionScreen(ctx);
                });
            }
        }
    }

    function renderMatchEnd(ctx, payload) {
        const winner = payload.winner || null;
        const draw = !!payload.draw;
        const hp = payload.hp || state.hp;
        const players = payload.players || state.players;

        state.hp = hp;
        state.finished = true;

        const p1 = players[0] || "";
        const p2 = players[1] || "";

        let title;
        if (draw) {
            title = "Égalité !";
        } else if (winner) {
            title = `${winner} remporte le duel !`;
        } else {
            title = "Duel terminé";
        }

        ctx.openModal("Duel RPG", title);

        ctx.setModalContent(`
            <div class="space-y-3 text-xs text-slate-600">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="font-semibold text-slate-800">${p1}</p>
                        <p>PV restants : ${hp[p1] ?? 0}/${state.maxHp}</p>
                    </div>
                    <div class="text-right">
                        <p class="font-semibold text-slate-800">${p2}</p>
                        <p>PV restants : ${hp[p2] ?? 0}/${state.maxHp}</p>
                    </div>
                </div>
                <p class="text-center text-[11px] text-slate-500">
                    Merci d'avoir joué !
                </p>
            </div>
        `);

        ctx.setModalActions(`
            <div class="flex justify-end">
                <button id="duel-close" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                    Fermer
                </button>
            </div>
        `);

        const btnClose = document.getElementById("duel-close");
        if (btnClose) {
            btnClose.addEventListener("click", () => {
                ctx.closeModal();
                resetState();
            });
        }
    }

    function renderCanceled(ctx, payload) {
        const reason = payload.reason || "Le duel a été annulé.";
        if (typeof ctx.toast === "function") {
            ctx.toast(reason, "info");
        }
        ctx.closeModal();
        resetState();
    }

    // Enregistrement du client de commande "duel"
    window.registerCommandClient("duel", {
        onServerMessage(data, ctx) {
            const payload = data.payload || {};
            const me = ctx.getCurrentUser();

            if (!payload.type) return;

            if (
                payload.game_id &&
                state.gameId &&
                payload.game_id !== state.gameId
            ) {
                return;
            }

            if (payload.type === "invite") {
                renderInvite(ctx, payload, me);
                return;
            }

            if (payload.type === "start") {
                setStateFromStart(payload, me);
                renderActionScreen(ctx);
                return;
            }

            if (payload.type === "round_result") {
                renderRoundResult(ctx, payload);
                return;
            }

            if (payload.type === "match_end") {
                renderMatchEnd(ctx, payload);
                return;
            }

            if (payload.type === "canceled") {
                renderCanceled(ctx, payload);
                return;
            }
        },
    });
})();
