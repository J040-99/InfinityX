"""Utilitários compartilhados (paths, eval seguro, categorização)."""

import ast
import operator as op
import os
from pathlib import Path

from config import FILE_CATEGORIES, FOLDER_ALIASES


# Operadores permitidos para avaliação segura de expressões matemáticas
_ALLOWED_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}

def safe_eval(expr: str):
    """Parser de matemática seguro usando AST em vez de eval().
    
    Devolve int quando o resultado é inteiro exato; caso contrário float.
    """
    try:
        node = ast.parse(expr, mode='eval').body
        result = _eval_node(node)
        
        if not isinstance(result, (int, float)):
            raise ValueError("Resultado não é número")
        if isinstance(result, float) and result.is_integer():
            return int(result)
        return result
    except Exception as e:
        raise ValueError(f"Expressão inválida: {expr}") from e

def _eval_node(node):
    if isinstance(node, ast.Num):  # < Python 3.8
        return node.n
    elif isinstance(node, ast.Constant):  # >= Python 3.8
        return node.value
    elif isinstance(node, ast.BinOp):
        return _ALLOWED_OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    elif isinstance(node, ast.UnaryOp):
        return _ALLOWED_OPERATORS[type(node.op)](_eval_node(node.operand))
    else:
        raise TypeError(f"Tipo não suportado: {type(node)}")


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
