"""Memória persistente: histórico, dicionário pessoal de palavras, timers."""

import json
import os

from config import MEMORIA_FILE, PALAVRAS_FILE

MEMORIA: dict = {"historico": [], "variaveis": {}, "ultima_pasta": None}
PALAVRAS: dict = {}
TIMERS: dict = {}


def carregar_palavras() -> None:
    global PALAVRAS
    try:
        if os.path.exists(PALAVRAS_FILE):
            with open(PALAVRAS_FILE, 'r', encoding='utf-8') as f:
                PALAVRAS = json.load(f)
    except (IOError, json.JSONDecodeError):
        pass


def salvar_palavras() -> None:
    try:
        with open(PALAVRAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(PALAVRAS, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


def carregar_memoria() -> None:
    global MEMORIA
    try:
        if os.path.exists(MEMORIA_FILE):
            with open(MEMORIA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            MEMORIA = {**MEMORIA, **data}
    except (IOError, json.JSONDecodeError):
        pass


def salvar_memoria() -> None:
    try:
        with open(MEMORIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(MEMORIA, f, ensure_ascii=False, indent=2)
    except IOError:
        pass
