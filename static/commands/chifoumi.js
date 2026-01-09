// static/commands/chifoumi.js
(function () {
    const state = {
        gameId: null,
        me: null,
        opponent: null,
        players: [],
        scores: {},
        round: 1,
        winsTo: 3, // 3 manches gagnantes
    };

    function setStateFromStart(payload, me) {
        state.gameId = payload.game_id;
        state.players = payload.players || [];
        state.scores = payload.scores || {};
        state.round = payload.round || 1;
        state.winsTo = payload.wins_to || 3;
        state.me = me;
        state.opponent = state.players.find((p) => p !== me) || null;
    }

    function renderInvite(ctx, payload, me) {
        state.gameId = payload.game_id;
        state.me = me;
        state.opponent = me === payload.to ? payload.from : payload.to;
        state.winsTo = payload.wins_to || 3;

        const isTarget = me === payload.to;
        const title = "Chifoumi – 3 manches gagnantes";
        const subtitle = isTarget
            ? `${payload.from} te défie en chifoumi !`
            : `Invitation envoyée à ${payload.to}…`;

        ctx.openModal(title, subtitle);

        if (isTarget) {
            ctx.setModalContent(`
                <div class="space-y-3">
                    <p class="text-sm text-slate-700">
                        Premier à <span class="font-semibold">${state.winsTo}</span> manches gagnantes.
                        Tu acceptes le défi ?
                    </p>
                </div>
            `);
            ctx.setModalActions(`
                <div class="flex justify-end gap-2">
                    <button id="chifoumi-decline" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                        Refuser
                    </button>
                    <button id="chifoumi-accept" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                        Accepter
                    </button>
                </div>
            `);

            const btnAccept = document.getElementById("chifoumi-accept");
            const btnDecline = document.getElementById("chifoumi-decline");

            if (btnAccept) {
                btnAccept.addEventListener("click", () => {
                    ctx.sendEvent("chifoumi", "accept", {
                        game_id: state.gameId,
                    });
                });
            }

            if (btnDecline) {
                btnDecline.addEventListener("click", () => {
                    ctx.sendEvent("chifoumi", "decline", {
                        game_id: state.gameId,
                    });
                    ctx.closeModal();
                });
            }
        } else {
            ctx.setModalContent(`
                <div class="space-y-3">
                    <p class="text-sm text-slate-700">
                        En attente de la réponse de <span class="font-semibold">${payload.to}</span>…
                    </p>
                    <p class="text-xs text-slate-500">
                        Format : premier à ${state.winsTo} manches gagnantes.
                    </p>
                </div>
            `);
            ctx.setModalActions(`
                <div class="flex justify-end">
                    <button id="chifoumi-cancel" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                        Annuler
                    </button>
                </div>
            `);

            const btnCancel = document.getElementById("chifoumi-cancel");
            if (btnCancel) {
                btnCancel.addEventListener("click", () => {
                    ctx.sendEvent("chifoumi", "cancel", {
                        game_id: state.gameId,
                    });
                    ctx.closeModal();
                });
            }
        }
    }

    function renderChoiceScreen(ctx) {
        const me = state.me;
        const opponent = state.opponent || "Adversaire";
        const round = state.round;
        const winsTo = state.winsTo;

        ctx.openModal(
            "Chifoumi – 3 manches gagnantes",
            `Manche ${round} · ${me} vs ${opponent}`
        );

        ctx.setModalContent(`
            <div class="space-y-4">
                <div class="flex items-center justify-between text-xs text-slate-500">
                    <div class="flex flex-col">
                        <span class="font-semibold text-slate-800">${state.players[0] || ""}</span>
                        <span>Score : ${state.scores[state.players[0]] || 0}</span>
                    </div>
                    <div class="text-[10px] uppercase tracking-wide text-slate-400">
                        1ᵉʳ à ${winsTo} manches gagnantes
                    </div>
                    <div class="flex flex-col text-right">
                        <span class="font-semibold text-slate-800">${state.players[1] || ""}</span>
                        <span>Score : ${state.scores[state.players[1]] || 0}</span>
                    </div>
                </div>

                <div class="text-center text-xs text-slate-500">
                    Choisis ton coup :
                </div>

                <div class="flex items-center justify-center gap-4">
                    <button data-choice="rock" class="chifoumi-choice text-4xl md:text-5xl px-3 py-2 rounded-2xl border border-slate-200 hover:bg-emerald-50">
                        🪨
                    </button>
                    <button data-choice="paper" class="chifoumi-choice text-4xl md:text-5xl px-3 py-2 rounded-2xl border border-slate-200 hover:bg-emerald-50">
                        📄
                    </button>
                    <button data-choice="scissors" class="chifoumi-choice text-4xl md:text-5xl px-3 py-2 rounded-2xl border border-slate-200 hover:bg-emerald-50">
                        ✂️
                    </button>
                </div>

                <p id="chifoumi-status" class="text-xs text-center text-slate-500">
                    En attente de ton choix…
                </p>
            </div>
        `);

        ctx.setModalActions(`
            <div class="flex justify-end">
                <button id="chifoumi-cancel" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                    Abandonner
                </button>
            </div>
        `);

        const btns = Array.from(
            document.querySelectorAll(".chifoumi-choice")
        );

        let choiceLocked = false;

        btns.forEach((btn) => {
            btn.addEventListener("click", () => {
                if (choiceLocked) return;
                const choice = btn.getAttribute("data-choice");
                if (!choice) return;

                choiceLocked = true;
                btns.forEach((b) => {
                    if (b !== btn) b.classList.add("opacity-40");
                    else
                        b.classList.add(
                            "bg-emerald-50",
                            "border-emerald-300"
                        );
                });

                const statusEl = document.getElementById("chifoumi-status");
                if (statusEl) {
                    statusEl.textContent =
                        "Choix envoyé. En attente de l'autre joueur…";
                }

                ctx.sendEvent("chifoumi", "choice", {
                    game_id: state.gameId,
                    choice,
                });
            });
        });

        const btnCancel = document.getElementById("chifoumi-cancel");
        if (btnCancel) {
            btnCancel.addEventListener("click", () => {
                ctx.sendEvent("chifoumi", "cancel", {
                    game_id: state.gameId,
                });
                ctx.closeModal();
            });
        }
    }

    function renderRoundResult(ctx, payload) {
        const me = state.me;
        const opponent = state.opponent || "Adversaire";
        const round = payload.round;
        const winner = payload.winner;
        const finished = !!payload.finished;
        const matchWinner = payload.match_winner;
        const scores = payload.scores || {};
        const choices = payload.choices || [];
        const winsTo = payload.wins_to || state.winsTo || 3;

        let p1 = state.players[0] || "";
        let p2 = state.players[1] || "";

        let choiceP1 = choices.find((c) => c.player === p1) || null;
        let choiceP2 = choices.find((c) => c.player === p2) || null;

        const emoji1 = choiceP1 ? choiceP1.emoji : "❔";
        const emoji2 = choiceP2 ? choiceP2.emoji : "❔";

        let lineResult;
        if (!winner) {
            lineResult = `Égalité pour la manche ${round} !`;
        } else {
            lineResult = `${winner} remporte la manche ${round} !`;
        }

        const s1 = scores[p1] || 0;
        const s2 = scores[p2] || 0;

        ctx.openModal(
            "Chifoumi – 3 manches gagnantes",
            `Résultat de la manche ${round}`
        );

        ctx.setModalContent(`
            <div class="space-y-4">
                <div class="flex items-center justify-center gap-8 text-5xl">
                    <div class="flex flex-col items-center gap-1">
                        <span>${emoji1}</span>
                        <span class="text-xs text-slate-500">${p1}</span>
                    </div>
                    <div class="text-2xl text-slate-400">vs</div>
                    <div class="flex flex-col items-center gap-1">
                        <span>${emoji2}</span>
                        <span class="text-xs text-slate-500">${p2}</span>
                    </div>
                </div>

                <div class="text-center text-sm font-semibold text-slate-800">
                    ${lineResult}
                </div>

                <div class="text-center text-xs text-slate-500">
                    Score actuel : <span class="font-semibold">${p1}</span> ${s1} – ${s2} <span class="font-semibold">${p2}</span>
                </div>

                <div class="text-xs text-center text-slate-400">
                    Premier à ${winsTo} manches gagnantes.
                </div>
            </div>
        `);

        if (finished) {
            ctx.setModalActions(`
                <div class="flex flex-col w-full gap-2">
                    <div class="text-center text-xs text-slate-600">
                        ${
                            matchWinner
                                ? `${matchWinner} remporte la partie !`
                                : `La partie se termine sur une égalité.`
                        }
                    </div>
                    <div class="flex justify-end">
                        <button id="chifoumi-close" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                            Fermer
                        </button>
                    </div>
                </div>
            `);

            const btnClose = document.getElementById("chifoumi-close");
            if (btnClose) {
                btnClose.addEventListener("click", () => {
                    state.gameId = null;
                    ctx.closeModal();
                });
            }
        } else {
            ctx.setModalActions(`
                <div class="flex justify-end">
                    <button id="chifoumi-next" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                        Manche suivante
                    </button>
                </div>
            `);

            const btnNext = document.getElementById("chifoumi-next");
            if (btnNext) {
                btnNext.addEventListener("click", () => {
                    state.scores = scores;
                    state.round = round + 1;
                    state.winsTo = winsTo;
                    renderChoiceScreen(ctx);
                });
            }
        }
    }

    function renderMatchEnd(ctx, payload) {
        const winner = payload.winner;
        const scores = payload.scores || {};
        const players = payload.players || [];

        const p1 = players[0] || "";
        const p2 = players[1] || "";
        const s1 = scores[p1] || 0;
        const s2 = scores[p2] || 0;

        ctx.openModal("Chifoumi – 3 manches gagnantes", "Partie terminée");

        ctx.setModalContent(`
            <div class="space-y-3">
                <div class="text-center text-sm text-slate-800 font-semibold">
                    ${
                        winner
                            ? `${winner} remporte la partie !`
                            : `La partie se termine sur une égalité.`
                    }
                </div>
                <div class="text-center text-xs text-slate-500">
                    Score final : <span class="font-semibold">${p1}</span> ${s1} – ${s2} <span class="font-semibold">${p2}</span>
                </div>
            </div>
        `);

        ctx.setModalActions(`
            <div class="flex justify-end">
                <button id="chifoumi-close" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                    Fermer
                </button>
            </div>
        `);

        const btnClose = document.getElementById("chifoumi-close");
        if (btnClose) {
            btnClose.addEventListener("click", () => {
                state.gameId = null;
                ctx.closeModal();
            });
        }
    }

    function renderCanceled(ctx, payload) {
        const reason = payload.reason || "La partie a été annulée.";
        if (typeof ctx.toast === "function") {
            ctx.toast(reason, "info");
        }
        state.gameId = null;
        ctx.closeModal();
    }

    // Enregistrement du client de commande "chifoumi"
    window.registerCommandClient("chifoumi", {
        onServerMessage(data, ctx) {
            const payload = data.payload || {};
            const me = ctx.getCurrentUser();

            if (!payload.type) return;
            if (payload.game_id && state.gameId && payload.game_id !== state.gameId) {
                return;
            }

            if (payload.type === "invite") {
                renderInvite(ctx, payload, me);
                return;
            }

            if (payload.type === "start") {
                setStateFromStart(payload, me);
                renderChoiceScreen(ctx);
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
