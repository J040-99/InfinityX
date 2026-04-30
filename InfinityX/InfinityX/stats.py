"""Métricas da última interacção (origem, tokens, tempo).

Actualizado pelas chamadas em ``llm.py`` e pelo ``parser.executar_acao``;
lido pelo loop principal (``infinityx.py``) e pela GUI (``gui.py``)
para mostrar o rodapé de cada resposta.
"""

from __future__ import annotations


LAST: dict[str, object] = {
    "source": None,       # ex: "groq", "lm_studio", "perplexity", "local", "guardrail", "pre_analyze"
    "model": None,        # ex: "llama-3.1-8b-instant"
    "tokens_in": None,
    "tokens_out": None,
    "tokens_total": None,
    "elapsed_ms": None,
}


def reset() -> None:
    for k in LAST:
        LAST[k] = None


def set_local(source: str, elapsed_ms: float | None = None) -> None:
    """Marca uma resposta servida localmente (sem LLM)."""
    reset()
    LAST["source"] = source
    if elapsed_ms is not None:
        LAST["elapsed_ms"] = round(elapsed_ms, 1)


def set_llm(source: str, model: str, usage: dict | None, elapsed_ms: float) -> None:
    reset()
    LAST["source"] = source
    LAST["model"] = model
    LAST["elapsed_ms"] = round(elapsed_ms, 1)
    if usage:
        LAST["tokens_in"] = usage.get("prompt_tokens")
        LAST["tokens_out"] = usage.get("completion_tokens")
        LAST["tokens_total"] = usage.get(
            "total_tokens",
            (LAST["tokens_in"] or 0) + (LAST["tokens_out"] or 0) or None,
        )


def format_footer() -> str:
    """Devolve uma linha tipo ``groq · llama-3.1-8b-instant · 412 tok · 0.84s``."""
    parts: list[str] = []
    if LAST["source"]:
        parts.append(str(LAST["source"]))
    if LAST["model"]:
        parts.append(str(LAST["model"]))
    if LAST["tokens_total"]:
        if LAST["tokens_in"] and LAST["tokens_out"]:
            parts.append(
                f"{LAST['tokens_total']} tok ({LAST['tokens_in']}↑ {LAST['tokens_out']}↓)"
            )
        else:
            parts.append(f"{LAST['tokens_total']} tok")
    if LAST["elapsed_ms"] is not None:
        ms = float(LAST["elapsed_ms"])
        parts.append(f"{ms / 1000:.2f}s" if ms >= 1000 else f"{int(ms)}ms")
    return " · ".join(parts)
