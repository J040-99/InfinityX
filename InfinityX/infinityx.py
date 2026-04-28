#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfinityX - Assistente Local Autônomo com IA Interpretativa
Arquitetura: LLM-first + Fallback inteligente + Ferramentas locais

Ponto de entrada (CLI). A lógica está dividida em:
  config.py   -> constantes, env, mapeamentos, prompt do sistema
  memory.py   -> memória persistente e dicionário de palavras
  utils.py    -> utilitários (safe_eval, paths, categorização)
  llm.py      -> chamadas a Groq, LM Studio, Perplexity, classificador
  actions/    -> implementação das ações
  parser.py   -> pré-análise, parser de intenções e executor
  stats.py    -> métricas (tokens, tempo) da última interacção
"""

import ctypes
import io
import shutil
import sys
import time
from datetime import datetime

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


# ----- Cores ANSI -----
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
GREY = "\033[90m"
BLUE = "\033[34m"
WHITE = "\033[97m"


def _enable_windows_ansi() -> None:
    """No Windows, activa o processamento de sequências ANSI no console."""
    try:
        kernel32 = ctypes.windll.kernel32
        # UTF-8
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        # Virtual terminal processing (cores ANSI no Windows 10+)
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        h = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(h, ctypes.byref(mode))
        kernel32.SetConsoleMode(h, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (AttributeError, OSError):
        pass


def _largura() -> int:
    try:
        return max(40, min(shutil.get_terminal_size((80, 20)).columns, 100))
    except OSError:
        return 80


def _print_banner() -> None:
    w = _largura()
    linha = "═" * w
    titulo = "I N F I N I T Y · X"
    sub = "assistente local autónoma · IA + ferramentas"
    print(f"{CYAN}{linha}{RESET}")
    print(f"{BOLD}{CYAN}{titulo.center(w)}{RESET}")
    print(f"{DIM}{sub.center(w)}{RESET}")
    print(f"{CYAN}{linha}{RESET}")
    print(
        f"{GREY}Olá. Fala comigo em português. Escreve {RESET}{BOLD}ajuda{RESET}"
        f"{GREY} para ver o que faço, ou {RESET}{BOLD}sair{RESET}{GREY} para terminar.{RESET}"
    )


def _imprimir_resposta(resposta: str, dec: dict) -> None:
    w = _largura()
    print(f"{GREY}{'─' * w}{RESET}")
    hora = datetime.now().strftime("%H:%M:%S")
    cabec = f"{MAGENTA}{BOLD}infinity{RESET} {GREY}[{hora}]{RESET}"
    print(cabec)
    # Indenta cada linha da resposta
    for linha in resposta.splitlines() or [resposta]:
        print(f"  {WHITE}{linha}{RESET}")
    rodape = stats.format_footer()
    if not rodape:
        rodape = dec.get("source") or "local"
    print(f"  {DIM}{ITALIC}{rodape}{RESET}")


def _pedir_entrada() -> str:
    hora = datetime.now().strftime("%H:%M:%S")
    prompt = f"\n{CYAN}{BOLD}tu{RESET} {GREY}[{hora}]{RESET}\n  {CYAN}›{RESET} "
    return input(prompt).strip()


def main() -> None:
    _enable_windows_ansi()

    carregar_palavras()
    carregar_memoria()
    carregar_notas()
    carregar_lembretes()
    iniciar_scheduler_lembretes()

    _print_banner()

    while True:
        try:
            entrada = _pedir_entrada()
            if not entrada:
                continue
            if entrada.lower() in ["sair", "exit", "quit"]:
                print(f"{DIM}Até à próxima.{RESET}")
                break

            stats.reset()
            t0 = time.perf_counter()
            dec = analisar(entrada)
            resposta = executar_acao(dec)
            total_ms = (time.perf_counter() - t0) * 1000

            if resposta == "__sair__":
                print(f"{DIM}Até à próxima.{RESET}")
                break

            # Se nenhuma camada LLM marcou stats, marca como local com o tempo total.
            if stats.LAST["source"] is None:
                stats.set_local(dec.get("source") or "local", total_ms)
            else:
                # Sobrepõe com o tempo total (analisar+executar) para o utilizador
                stats.LAST["elapsed_ms"] = round(total_ms, 1)

            MEMORIA["historico"].append({
                "ent": entrada,
                "res": resposta[:100],
                "src": dec.get("source", "?"),
            })
            if len(MEMORIA["historico"]) > MAX_HISTORY:
                MEMORIA["historico"] = MEMORIA["historico"][-MAX_HISTORY:]
            salvar_memoria()

            _imprimir_resposta(resposta, dec)

        except EOFError:
            print(f"\n{DIM}Até à próxima.{RESET}")
            break
        except KeyboardInterrupt:
            print(f"\n\n{DIM}Hasta la vista.{RESET}")
            break
        except Exception as e:
            print(f"{YELLOW}❌ Erro: {e}{RESET}")


if __name__ == "__main__":
    main()
