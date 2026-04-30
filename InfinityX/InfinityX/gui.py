#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interface gráfica (Tkinter) para o InfinityX.

Reutiliza exactamente o mesmo pipeline da versão CLI (`analisar` +
`executar_acao` + `MEMORIA`), só envolve numa janela de chat. As acções
correm numa thread em background para a UI nunca congelar.

Como executar:
    cd InfinityX
    python gui.py
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext

import stats
from actions import iniciar_scheduler_lembretes
from config import MAX_HISTORY
from memory import (
    MEMORIA,
    carregar_lembretes,
    carregar_memoria,
    carregar_notas,
    carregar_palavras,
    salvar_memoria,
)
from parser import analisar, executar_acao


# ---------------------------------------------------------------- paleta
BG = "#0f1115"
PANEL = "#161a22"
INPUT_BG = "#1f2530"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#8f74ff"
USER_BUBBLE = "#2a2f3d"
BOT_BUBBLE = "#1a2332"
TEXT = "#e8ecf1"
MUTED = "#8a93a6"
ERROR = "#ff6b6b"


class InfinityGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("InfinityX — Assistente")
        self.root.geometry("760x640")
        self.root.minsize(540, 460)
        self.root.configure(bg=BG)

        self._fila_respostas: queue.Queue[tuple[str, str]] = queue.Queue()
        self._a_processar = False

        self._fonte_titulo = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self._fonte_sub = tkfont.Font(family="Segoe UI", size=9)
        self._fonte_msg = tkfont.Font(family="Segoe UI", size=11)
        self._fonte_input = tkfont.Font(family="Segoe UI", size=11)
        self._fonte_btn = tkfont.Font(family="Segoe UI", size=10, weight="bold")

        self._construir_header()
        self._construir_chat()
        self._construir_input()

        self._mensagem_bot(
            "Olá! Sou a Infinity 💬 Fala comigo naturalmente — pergunta horas, "
            "matemática, abre apps, toca música, pede um resumo do dia ou da "
            "conversa."
        )

        self.root.after(80, self._poll_respostas)
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        self.entry.focus_set()

    # ----------------------------------------------------------- layout
    def _construir_header(self) -> None:
        header = tk.Frame(self.root, bg=PANEL, height=64)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        avatar = tk.Label(
            header, text="∞", bg=ACCENT, fg="white",
            font=tkfont.Font(family="Segoe UI", size=18, weight="bold"),
            width=2,
        )
        avatar.pack(side="left", padx=(16, 12), pady=12)

        col = tk.Frame(header, bg=PANEL)
        col.pack(side="left", fill="y", pady=10)
        tk.Label(
            col, text="Infinity", bg=PANEL, fg=TEXT, font=self._fonte_titulo,
            anchor="w",
        ).pack(anchor="w")
        self.lbl_estado = tk.Label(
            col, text="● online", bg=PANEL, fg="#4ade80",
            font=self._fonte_sub, anchor="w",
        )
        self.lbl_estado.pack(anchor="w")

        botoes = tk.Frame(header, bg=PANEL)
        botoes.pack(side="right", padx=12)
        self._btn_pequeno(botoes, "Limpar", self._limpar_chat).pack(side="left", padx=4)
        self._btn_pequeno(botoes, "Resumo", self._pedir_resumo).pack(side="left", padx=4)

    def _construir_chat(self) -> None:
        wrapper = tk.Frame(self.root, bg=BG)
        wrapper.pack(fill="both", expand=True, padx=14, pady=(12, 6))

        self.chat = scrolledtext.ScrolledText(
            wrapper, bg=BG, fg=TEXT, font=self._fonte_msg,
            wrap="word", borderwidth=0, highlightthickness=0,
            padx=4, pady=4, state="disabled", cursor="arrow",
        )
        self.chat.pack(fill="both", expand=True)

        self.chat.tag_configure(
            "user", justify="right", background=USER_BUBBLE, foreground=TEXT,
            lmargin1=120, lmargin2=120, rmargin=8,
            spacing1=4, spacing3=4, relief="flat",
        )
        self.chat.tag_configure(
            "bot", justify="left", background=BOT_BUBBLE, foreground=TEXT,
            lmargin1=8, lmargin2=8, rmargin=120,
            spacing1=4, spacing3=4, relief="flat",
        )
        self.chat.tag_configure(
            "meta", justify="left", foreground=MUTED,
            font=self._fonte_sub, spacing1=2, spacing3=8,
        )
        self.chat.tag_configure(
            "meta_right", justify="right", foreground=MUTED,
            font=self._fonte_sub, spacing1=2, spacing3=8,
        )
        self.chat.tag_configure("erro", foreground=ERROR)

    def _construir_input(self) -> None:
        barra = tk.Frame(self.root, bg=BG)
        barra.pack(side="bottom", fill="x", padx=14, pady=(6, 14))

        caixa = tk.Frame(barra, bg=INPUT_BG, highlightthickness=1,
                         highlightbackground="#2a3142")
        caixa.pack(fill="x")

        self.entry = tk.Text(
            caixa, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
            font=self._fonte_input, height=2, wrap="word",
            borderwidth=0, highlightthickness=0, padx=12, pady=10,
        )
        self.entry.pack(side="left", fill="both", expand=True)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", lambda _e: None)

        self.btn_enviar = tk.Button(
            caixa, text="Enviar", command=self._enviar,
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            activeforeground="white", font=self._fonte_btn,
            relief="flat", borderwidth=0, padx=18, pady=6, cursor="hand2",
        )
        self.btn_enviar.pack(side="right", padx=8, pady=8)
        self.btn_enviar.bind("<Enter>", lambda _e: self.btn_enviar.config(bg=ACCENT_HOVER))
        self.btn_enviar.bind("<Leave>", lambda _e: self.btn_enviar.config(bg=ACCENT))

    def _btn_pequeno(self, parent: tk.Widget, texto: str, cmd) -> tk.Button:
        b = tk.Button(
            parent, text=texto, command=cmd,
            bg=PANEL, fg=MUTED, activebackground=INPUT_BG, activeforeground=TEXT,
            font=self._fonte_sub, relief="flat", borderwidth=0,
            padx=10, pady=4, cursor="hand2",
        )
        b.bind("<Enter>", lambda _e: b.config(fg=TEXT))
        b.bind("<Leave>", lambda _e: b.config(fg=MUTED))
        return b

    # ---------------------------------------------------------- mensagens
    def _mensagem_user(self, texto: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", "Tu\n", "meta_right")
        self.chat.insert("end", f" {texto} \n\n", "user")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _mensagem_bot(self, texto: str, fonte: str | None = None,
                       rodape: str | None = None) -> None:
        self.chat.configure(state="normal")
        rotulo = "Infinity" if not fonte else f"Infinity · {fonte}"
        self.chat.insert("end", f"{rotulo}\n", "meta")
        self.chat.insert("end", f" {texto} \n", "bot")
        if rodape:
            self.chat.insert("end", f"  {rodape}\n", "meta")
        self.chat.insert("end", "\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _mensagem_erro(self, texto: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", "⚠ ", "meta")
        self.chat.insert("end", f"{texto}\n\n", ("bot", "erro"))
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _limpar_chat(self) -> None:
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._mensagem_bot("Conversa limpa. Em que te posso ajudar agora?")

    def _pedir_resumo(self) -> None:
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", "resumo da conversa")
        self._enviar()

    # ----------------------------------------------------------- eventos
    def _on_enter(self, event: tk.Event) -> str:
        if event.state & 0x0001:  # Shift pressionado
            return ""
        self._enviar()
        return "break"

    def _enviar(self) -> None:
        if self._a_processar:
            return
        texto = self.entry.get("1.0", "end").strip()
        if not texto:
            return
        self.entry.delete("1.0", "end")

        if texto.lower() in ("sair", "exit", "quit"):
            self.root.after(50, self._ao_fechar)
            return

        self._mensagem_user(texto)
        self._a_processar = True
        self.btn_enviar.config(state="disabled", text="...")
        self.lbl_estado.config(text="● a pensar", fg="#fbbf24")

        threading.Thread(target=self._worker, args=(texto,), daemon=True).start()

    def _worker(self, texto: str) -> None:
        try:
            stats.reset()
            t0 = time.perf_counter()
            dec = analisar(texto)
            resposta = executar_acao(dec)
            total_ms = (time.perf_counter() - t0) * 1000

            if stats.LAST["source"] is None:
                stats.set_local(dec.get("source") or "local", total_ms)
            else:
                stats.LAST["elapsed_ms"] = round(total_ms, 1)

            fonte = dec.get("source") or dec.get("action", "?")
            rodape = stats.format_footer()
            self._fila_respostas.put((resposta or "(sem resposta)", str(fonte), rodape))

            MEMORIA["historico"].append({
                "ent": texto,
                "res": (resposta or "")[:100],
                "src": dec.get("source", dec.get("action", "?")),
            })
            if len(MEMORIA["historico"]) > MAX_HISTORY:
                MEMORIA["historico"] = MEMORIA["historico"][-MAX_HISTORY:]
            try:
                salvar_memoria()
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            self._fila_respostas.put((f"__ERRO__{exc}", "erro", ""))

    def _poll_respostas(self) -> None:
        try:
            while True:
                resposta, fonte, rodape = self._fila_respostas.get_nowait()
                if resposta.startswith("__ERRO__"):
                    self._mensagem_erro(resposta.replace("__ERRO__", ""))
                else:
                    self._mensagem_bot(resposta, fonte=fonte, rodape=rodape)
                self._a_processar = False
                self.btn_enviar.config(state="normal", text="Enviar")
                self.lbl_estado.config(text="● online", fg="#4ade80")
        except queue.Empty:
            pass
        self.root.after(80, self._poll_respostas)

    def _ao_fechar(self) -> None:
        try:
            salvar_memoria()
        except Exception:
            pass
        self.root.destroy()


def main() -> int:
    carregar_palavras()
    carregar_memoria()
    carregar_notas()
    carregar_lembretes()
    iniciar_scheduler_lembretes()

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Não consegui abrir a janela gráfica: {exc}", file=sys.stderr)
        print("Em ambientes sem ecrã (ex.: terminal remoto sem X), corre "
              "antes a versão de consola: python infinityx.py", file=sys.stderr)
        return 1

    InfinityGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
