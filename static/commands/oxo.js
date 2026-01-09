// static/commands/oxo.js
(function () {
    const state = {
        gameId: null,
        me: null,
        opponent: null,
        players: [],
        symbols: {}, // {pseudo: "X"|"O"}
        board: Array(9).fill(""),
        currentPlayer: null,
        finished: false,
    };

    function setStateFromStart(payload, me) {
        state.gameId = payload.game_id;
        state.players = payload.players || [];
        state.symbols = payload.symbols || {};
        state.board = payload.board || Array(9).fill("");
        state.currentPlayer = payload.current_player || null;
        state.me = me;
        state.opponent = state.players.find((p) => p !== me) || null;
        state.finished = false;
    }

    function symbolsText() {
        const p1 = state.players[0] || "";
        const p2 = state.players[1] || "";
        const s1 = state.symbols[p1] || "?";
        const s2 = state.symbols[p2] || "?";
        return `${p1} (${s1}) · ${p2} (${s2})`;
    }

    function renderInvite(ctx, payload, me) {
        state.gameId = payload.game_id;
        state.me = me;
        state.players = [payload.from, payload.to];
        state.symbols = payload.symbols || {};
        state.currentPlayer = payload.first_player || payload.from;
        state.opponent = me === payload.to ? payload.from : payload.to;
        state.board = Array(9).fill("");
        state.finished = false;

        const isTarget = me === payload.to;
        const title = "Oxo (Morpion)";
        const subtitle = isTarget
            ? `${payload.from} te défie au morpion !`
            : `Invitation envoyée à ${payload.to}…`;

        ctx.openModal(title, subtitle);

        const symText = symbolsText();

        if (isTarget) {
            ctx.setModalContent(`
                <div class="space-y-3">
                    <p class="text-sm text-slate-700">
                        ${payload.from} te propose une partie de morpion.
                    </p>
                    <p class="text-xs text-slate-500">
                        ${symText}<br>
                        <span class="font-semibold">${payload.first_player}</span> commence.
                    </p>
                </div>
            `);
            ctx.setModalActions(`
                <div class="flex justify-end gap-2">
                    <button id="oxo-decline" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                        Refuser
                    </button>
                    <button id="oxo-accept" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                        Accepter
                    </button>
                </div>
            `);

            const btnAccept = document.getElementById("oxo-accept");
            const btnDecline = document.getElementById("oxo-decline");

            if (btnAccept) {
                btnAccept.addEventListener("click", () => {
                    ctx.sendEvent("oxo", "accept", {
                        game_id: state.gameId,
                    });
                });
            }

            if (btnDecline) {
                btnDecline.addEventListener("click", () => {
                    ctx.sendEvent("oxo", "decline", {
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
                        ${symText}<br>
                        <span class="font-semibold">${payload.first_player}</span> commence.
                    </p>
                </div>
            `);
            ctx.setModalActions(`
                <div class="flex justify-end">
                    <button id="oxo-cancel" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                        Annuler
                    </button>
                </div>
            `);

            const btnCancel = document.getElementById("oxo-cancel");
            if (btnCancel) {
                btnCancel.addEventListener("click", () => {
                    ctx.sendEvent("oxo", "cancel", {
                        game_id: state.gameId,
                    });
                    ctx.closeModal();
                });
            }
        }
    }

    function renderBoard(ctx, opts = {}) {
        const { highlightIndex = null } = opts;
        const me = state.me;
        const opponent = state.opponent || "Adversaire";
        const board = state.board || Array(9).fill("");
        const current = state.currentPlayer;
        const mySymbol = state.symbols[me] || "?";
        const oppSymbol = opponent ? state.symbols[opponent] || "?" : "?";

        let statusText = "";
        if (state.finished) {
            statusText = "Partie terminée.";
        } else if (current === me) {
            statusText = "À toi de jouer.";
        } else {
            statusText = "En attente de l'autre joueur…";
        }

        ctx.openModal(
            "Oxo (Morpion)",
            `${symbolsText()}`
        );

        let cellsHtml = "";
        for (let i = 0; i < 9; i++) {
            const val = board[i] || "";
            const isHighlight = highlightIndex === i;
            const classes = [
                "oxo-cell",
                "w-12 h-12 md:w-14 md:h-14 flex items-center justify-center text-2xl md:text-3xl rounded-lg border border-slate-200",
                "transition",
            ];
            if (val === "X" || val === "O") {
                classes.push("bg-white");
            } else {
                classes.push("hover:bg-emerald-50 cursor-pointer");
            }
            if (isHighlight) {
                classes.push("ring-2 ring-emerald-400");
            }
            cellsHtml += `
                <button data-index="${i}" class="${classes.join(" ")}">
                    ${val === "X" ? "✖️" : val === "O" ? "⭕" : ""}
                </button>
            `;
        }

        ctx.setModalContent(`
            <div class="space-y-4">
                <div class="flex items-center justify-between text-xs text-slate-500">
                    <div class="flex flex-col">
                        <span class="font-semibold text-slate-800">${me}</span>
                        <span>Tu joues <span class="font-semibold">${mySymbol}</span></span>
                    </div>
                    <div class="flex flex-col text-right">
                        <span class="font-semibold text-slate-800">${opponent}</span>
                        <span>Joue <span class="font-semibold">${oppSymbol}</span></span>
                    </div>
                </div>

                <div class="grid grid-cols-3 gap-2 justify-items-center">
                    ${cellsHtml}
                </div>

                <p class="text-xs text-center text-slate-500">
                    ${statusText}
                </p>
            </div>
        `);

        ctx.setModalActions(`
            <div class="flex justify-end">
                <button id="oxo-cancel" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50">
                    Abandonner
                </button>
            </div>
        `);

        const buttons = Array.from(
            document.querySelectorAll(".oxo-cell")
        );
        const myTurn = !state.finished && current === me;

        buttons.forEach((btn) => {
            const index = parseInt(btn.getAttribute("data-index") || "0", 10);
            const val = board[index] || "";

            if (!myTurn || val === "X" || val === "O") {
                btn.disabled = true;
                btn.classList.add("cursor-default");
                return;
            }

            btn.addEventListener("click", () => {
                if (!myTurn || state.finished) return;

                ctx.sendEvent("oxo", "play", {
                    game_id: state.gameId,
                    index,
                });
            });
        });

        const btnCancel = document.getElementById("oxo-cancel");
        if (btnCancel && !state.finished) {
            btnCancel.addEventListener("click", () => {
                ctx.sendEvent("oxo", "cancel", {
                    game_id: state.gameId,
                });
                ctx.closeModal();
            });
        }
    }

    function renderMatchEnd(ctx, payload) {
        const winner = payload.winner;
        const board = payload.board || state.board;
        const players = payload.players || state.players;
        const symbols = payload.symbols || state.symbols;
        const draw = !!payload.draw;

        state.finished = true;
        state.board = board;
        state.players = players;
        state.symbols = symbols;

        const p1 = players[0] || "";
        const p2 = players[1] || "";
        const s1 = symbols[p1] || "?";
        const s2 = symbols[p2] || "?";

        let titleText;
        if (draw) {
            titleText = "Égalité";
        } else if (winner) {
            titleText = `${winner} gagne la partie !`;
        } else {
            titleText = "Partie terminée";
        }

        ctx.openModal("Oxo (Morpion)", titleText);

        let cellsHtml = "";
        for (let i = 0; i < 9; i++) {
            const val = board[i] || "";
            cellsHtml += `
                <div class="w-10 h-10 md:w-12 md:h-12 flex items-center justify-center text-2xl md:text-3xl rounded-lg border border-slate-200">
                    ${val === "X" ? "✖️" : val === "O" ? "⭕" : ""}
                </div>
            `;
        }

        ctx.setModalContent(`
            <div class="space-y-4">
                <div class="grid grid-cols-3 gap-2 justify-items-center">
                    ${cellsHtml}
                </div>
                <div class="text-center text-xs text-slate-500">
                    ${p1} (${s1}) · ${p2} (${s2})
                </div>
                ${
                    draw
                        ? `<p class="text-xs text-center text-slate-600">Aucun des deux joueurs n'a réussi à aligner trois symboles.</p>`
                        : winner
                        ? `<p class="text-xs text-center text-slate-600">${winner} a aligné trois symboles !</p>`
                        : ``
                }
            </div>
        `);

        ctx.setModalActions(`
            <div class="flex justify-end">
                <button id="oxo-close" class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                    Fermer
                </button>
            </div>
        `);

        const btnClose = document.getElementById("oxo-close");
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
        state.finished = true;
        state.gameId = null;
        ctx.closeModal();
    }

    // Enregistrement du client "oxo"
    window.registerCommandClient("oxo", {
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
                renderBoard(ctx);
                return;
            }

            if (payload.type === "update") {
                state.board = payload.board || state.board;
                state.players = payload.players || state.players;
                state.symbols = payload.symbols || state.symbols;
                state.currentPlayer = payload.current_player || state.currentPlayer;
                state.finished = !!payload.winner || !!payload.draw;

                const lastMove = payload.last_move || {};
                const highlight = typeof lastMove.index === "number" ? lastMove.index : null;

                if (payload.winner || payload.draw) {
                    renderMatchEnd(ctx, {
                        winner: payload.winner,
                        board: state.board,
                        players: state.players,
                        symbols: state.symbols,
                        draw: payload.draw,
                    });
                } else {
                    renderBoard(ctx, { highlightIndex: highlight });
                }
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
