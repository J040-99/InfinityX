"""Memória persistente: histórico, dicionário pessoal, notas, lembretes, timers."""

import json
import os

from config import LEMBRETES_FILE, MEMORIA_FILE, NOTAS_FILE, PALAVRAS_FILE

MEMORIA: dict = {"historico": [], "variaveis": {}, "ultima_pasta": None, "ultima_pesquisa": None, "ultima_resposta": None, "contexto_visao": []}
PALAVRAS: dict = {}
NOTAS: list = []
LEMBRETES: list = []
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


def carregar_notas() -> None:
    global NOTAS
    try:
        if os.path.exists(NOTAS_FILE):
            with open(NOTAS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    NOTAS = data
    except (IOError, json.JSONDecodeError):
        pass


def salvar_notas() -> None:
    try:
        with open(NOTAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(NOTAS, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


def carregar_lembretes() -> None:
    global LEMBRETES
    try:
        if os.path.exists(LEMBRETES_FILE):
            with open(LEMBRETES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    LEMBRETES = data
    except (IOError, json.JSONDecodeError):
        pass


def salvar_lembretes() -> None:
    try:
        with open(LEMBRETES_FILE, 'w', encoding='utf-8') as f:
            json.dump(LEMBRETES, f, ensure_ascii=False, indent=2)
    except IOError:
        pass
