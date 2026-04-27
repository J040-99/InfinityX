#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfinityX - Assistente Local Autônomo com IA Interpretativa
Arquitetura: LLM-first + Fallback inteligente + Ferramentas locais

Ponto de entrada. A lógica está dividida em:
  config.py   -> constantes, env, mapeamentos, prompt do sistema
  memory.py   -> memória persistente e dicionário de palavras
  utils.py    -> utilitários (safe_eval, paths, categorização)
  llm.py      -> chamadas a Groq, LM Studio, Perplexity, classificador
  actions.py  -> implementação das ações
  parser.py   -> pré-análise, parser de intenções e executor
"""

import ctypes
import io
import sys

from config import MAX_HISTORY
from memory import MEMORIA, carregar_memoria, carregar_notas, carregar_palavras, salvar_memoria
from parser import analisar, executar_acao


def main() -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except (AttributeError, OSError):
        pass

    carregar_palavras()
    carregar_memoria()
    carregar_notas()

    print("=" * 50)
    print("InfinityX - Assistente Local com IA Autônoma")
    print("=" * 50)
    print("👩 Sou a Infinity! Fale naturalmente comigo 💬")

    while True:
        try:
            entrada = input("\n> ").strip()
            if not entrada:
                continue
            if entrada.lower() in ["sair", "exit", "quit"]:
                print("Até!")
                break

            dec = analisar(entrada)
            resposta = executar_acao(dec)

            if resposta == "__sair__":
                print("Até!")
                break

            MEMORIA["historico"].append({
                "ent": entrada,
                "res": resposta[:100],
                "src": dec.get("source", "?"),
            })
            if len(MEMORIA["historico"]) > MAX_HISTORY:
                MEMORIA["historico"] = MEMORIA["historico"][-MAX_HISTORY:]
            salvar_memoria()
            print(resposta)

        except EOFError:
            print("\nAté!")
            break
        except KeyboardInterrupt:
            print("\n\nHasta la vista!")
            break
        except Exception as e:
            print(f"❌ Erro: {e}")


if __name__ == "__main__":
    main()
