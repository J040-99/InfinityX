"""Camada de IA: chamadas a LM Studio, Perplexity e classificador de intenções."""

import json
import re
import time
import urllib.parse
import webbrowser

import stats
from config import (
    CONFIDENCE_THRESHOLD,
    INTENT_SYSTEM_PROMPT,
    LM_STUDIO_URL,
    REQUESTS_AVAILABLE,
)
from memory import MEMORIA

if REQUESTS_AVAILABLE:
    import requests


def _post_chat(url: str, payload: dict, headers: dict | None = None, timeout: int = 30) -> dict:
    res = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    res.raise_for_status()
    return res.json()


def _build_messages_with_history(prompt: str) -> tuple[list, int]:
    """Constrói messages com histórico recente para contexto.
    Retorna (messages, total_tokens估算)."""
    MAX_TOKENS = 3500  # Reservar para resposta
    SYSTEM_PROMPT = INTENT_SYSTEM_PROMPT[:500] if INTENT_SYSTEM_PROMPT else ""
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    total_chars = len(SYSTEM_PROMPT)
    
    # Adiciona histórico regular (visível no chat)
    if MEMORIA.get("historico"):
        historico = []
        for h in reversed(MEMORIA["historico"]):
            ent = h.get("ent", "")
            res = h.get("res", "")
            tokens_est = len(ent) + len(res)
            historico.append((tokens_est, {"ent": ent, "res": res}))
            if sum(t for t, _ in historico) > (MAX_TOKENS - len(prompt) - 500):
                break
        
        for _, h in reversed(historico):
            messages.append({"role": "user", "content": h["ent"]})
            messages.append({"role": "assistant", "content": h["res"]})
            total_chars += len(h["ent"]) + len(h["res"])
    
    # Adiciona contexto de visão
    if MEMORIA.get("contexto_visao"):
        visao_contexto = []
        for v in reversed(MEMORIA["contexto_visao"]):
            ent = v.get("ent", "")
            res = v.get("res", "")
            tokens_est = len(ent) + len(res)
            visao_contexto.append((tokens_est, {"ent": ent, "res": res}))
            if sum(t for t, _ in visao_contexto) > (MAX_TOKENS - len(prompt) - 500 - sum(t for t, _ in historico if 'historico' in locals())):
                break
        
        for _, v in reversed(visao_contexto):
            messages.append({"role": "user", "content": v["ent"]})
            messages.append({"role": "assistant", "content": v["res"]})
            total_chars += len(v["ent"]) + len(v["res"])
    
    total_chars += len(prompt)
    messages.append({"role": "user", "content": prompt})
    return messages, total_chars


LM_STUDIO_MODEL = "qwen2.5-coder-3b-instruct"


def chamar_lm_studio(prompt: str, tentativa: int = 1) -> str:
    if not LM_STUDIO_URL or not REQUESTS_AVAILABLE:
        raise RuntimeError("LM_STUDIO_URL não configurada")
    t0 = time.perf_counter()
    messages, _ = _build_messages_with_history(prompt)
    data = _post_chat(
        LM_STUDIO_URL,
        {
            "model": LM_STUDIO_MODEL,
            "messages": messages,
            "temperature": 0.4 if tentativa == 1 else 0.6,
            "max_tokens": 512,
        },
        timeout=30,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    stats.set_llm("lm_studio", "local", data.get("usage"), elapsed)
    return data["choices"][0]["message"]["content"].strip()


def self_discuss(prompt: str) -> str:
    versoes = []
    for i in range(2):
        try:
            versoes.append(chamar_lm_studio(prompt, tentativa=i + 1))
        except Exception:
            pass
    if not versoes:
        from actions.web import action_browser_search
        return action_browser_search(prompt)
    if len(versoes) == 1:
        return versoes[0]
    try:
        return chamar_lm_studio(
            "Escolha a MELHOR resposta ou combine o essencial. "
            "Máx 3 frases, sem meta-comentários, em português.\n\n"
            f"1. {versoes[0]}\n2. {versoes[1]}\n\nResposta final:"
        )
    except Exception:
        return versoes[0]


def buscar_info(prompt: str) -> str:
    try:
        return self_discuss(prompt)
    except Exception:
        from actions.web import action_browser_search
        try:
            return action_browser_search(prompt)
        except Exception:
            stats.set_local("erro")
            return "Não consegui encontrar. Tente novamente."


def classify_intent(user_input: str) -> dict | None:
    """Usa LLM (LM Studio) para interpretar intenção. Retorna None se confiança baixa ou resposta vazia."""
    if not REQUESTS_AVAILABLE or not LM_STUDIO_URL:
        return None

    from rag import recuperar_contexto
    contexto_rag = recuperar_contexto(user_input)

    historico_texto = ""
    if MEMORIA.get("historico"):
        ultimos = MEMORIA["historico"][-5:]
        historico_texto = "\n\n### CONTEXTO DA CONVERSA (últimas interações):\n"
        for h in ultimos:
            historico_texto += f"Usuário: {h['ent']}\nAssistente: {h['res']}\n"
        historico_texto += f"\nUsuário agora: {user_input}"

    prompt = f'{contexto_rag}\nEntrada: "{user_input}"{historico_texto}\n\nResponda APENAS com JSON válido:'
    
    try:
        messages, _ = _build_messages_with_history(prompt)
        t0 = time.perf_counter()
        data = _post_chat(
            LM_STUDIO_URL,
            {
                "model": LM_STUDIO_MODEL,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 320,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        stats.set_llm("lm_studio", "local", data.get("usage"), elapsed)
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            return None

        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            return None
        result = json.loads(json_match.group())
        if not result or "action" not in result or "confidence" not in result:
            return None
        return result if result["confidence"] >= CONFIDENCE_THRESHOLD else None
    except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError):
        return None
