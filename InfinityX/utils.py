"""Utilitários compartilhados (paths, eval seguro, categorização)."""

import os
import re
from pathlib import Path

from config import FILE_CATEGORIES, FOLDER_ALIASES


def safe_eval(expr: str) -> float:
    """Parser de matemática seguro - usa eval() com validação restritiva."""
    if not re.match(r'^[\d\s+\-*/.()%]+$', expr):
        raise ValueError(f"Expressão inválida: {expr}")
    allowed_globals = {"__builtins__": {}}
    try:
        result = eval(expr, allowed_globals, {})
    except Exception as e:
        raise ValueError(f"Expressão inválida: {expr}") from e
    if not isinstance(result, (int, float)):
        raise ValueError("Resultado não é número")
    return float(result)


def get_user_home() -> Path:
    return Path(os.path.expanduser("~"))


def resolve_path(folder: str):
    folder = folder.strip().lower().rstrip('/\\')
    if folder in FOLDER_ALIASES:
        base = get_user_home() / FOLDER_ALIASES[folder]
        if base.exists():
            return base, True, ""
        return base, False, f"Pasta '{FOLDER_ALIASES[folder]}' não existe"
    for p in [Path(folder).resolve(), get_user_home() / folder]:
        if p.exists():
            return p, True, ""
    return Path(folder), False, f"Caminho não encontrado: '{folder}'"


def categorize_file(fn: str) -> str:
    ext = Path(fn).suffix.lower()
    for cat, exts in FILE_CATEGORIES.items():
        if ext in exts:
            return cat
    return "Outros"
