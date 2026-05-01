"""Camada de IA: chamadas a Groq, LM Studio, Perplexity e classificador de intenções."""

import json
import re
import time
import urllib.parse
import webbrowser

import stats
from config import (
    CONFIDENCE_THRESHOLD,
    GROQ_API_KEY,
    INTENT_SYSTEM_PROMPT,
    LM_STUDIO_URL,
    REQUESTS_AVAILABLE,
)
from memory import MEMORIA

if REQUESTS_AVAILABLE:
    import requests


GROQ_MODEL = "llama-3.1-8b-instant"


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
        # Constrói histórico com limite de tokens
        historico = []
        for h in reversed(MEMORIA["historico"]):
            ent = h.get("ent", "")
            res = h.get("res", "")
            #估算 tokens (aprox 1 token = 4 chars)
            tokens_est = len(ent) + len(res)
            historico.append((tokens_est, {"ent": ent, "res": res}))
            if sum(t for t, _ in historico) > (MAX_TOKENS - len(prompt) - 500):
                break
        
        # Adiciona do mais antigo para mais recente
        for _, h in reversed(historico):
            messages.append({"role": "user", "content": h["ent"]})
            messages.append({"role": "assistant", "content": h["res"]})
            total_chars += len(h["ent"]) + len(h["res"])
    
    # Adiciona contexto de visão (não visível no chat, mas disponível para a IA)
    if MEMORIA.get("contexto_visao"):
        # Constrói contexto de visão com limite de tokens
        visao_contexto = []
        for v in reversed(MEMORIA["contexto_visao"]):
            ent = v.get("ent", "")
            res = v.get("res", "")
            #估算 tokens (aprox 1 token = 4 chars)
            tokens_est = len(ent) + len(res)
            visao_contexto.append((tokens_est, {"ent": ent, "res": res}))
            if sum(t for t, _ in visao_contexto) > (MAX_TOKENS - len(prompt) - 500 - sum(t for t, _ in historico if 'historico' in locals())):
                break
        
        # Adiciona do mais antigo para mais recente
        for _, v in reversed(visao_contexto):
            messages.append({"role": "user", "content": v["ent"]})
            messages.append({"role": "assistant", "content": v["res"]})
            total_chars += len(v["ent"]) + len(v["res"])
    
    total_chars += len(prompt)
    messages.append({"role": "user", "content": prompt})
    return messages, total_chars


def _should_use_groq(prompt: str) -> bool:
    """Determina se deve usar Groq (>4096 tokens) ou LM Studio."""
    _, total_chars = _build_messages_with_history(prompt)
    # 4096 tokens ≈ 16384 chars
    return total_chars > 16000


def chamar_groq(prompt: str, tentativa: int = 1, model: str | None = None) -> str:
    if not GROQ_API_KEY or not REQUESTS_AVAILABLE:
        raise RuntimeError("GROQ_API_KEY não configurada")
    t0 = time.perf_counter()
    messages, _ = _build_messages_with_history(prompt)
    data = _post_chat(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": model or GROQ_MODEL,
            "messages": messages,
            "temperature": 0.3 if tentativa == 1 else 0.5,
            "max_tokens": 512,
        },
        {"Authorization": f"Bearer {GROQ_API_KEY}"},
        timeout=30,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    stats.set_llm("groq", model or GROQ_MODEL, data.get("usage"), elapsed)
    return data["choices"][0]["message"]["content"].strip()


LM_STUDIO_MODEL = "qwen2.5-coder-3b-instruct"


def chamar_lm_studio(prompt: str, tentativa: int = 1) -> str:
    # Se contexto > 4096 tokens, usar Groq em vez de LM Studio
    if _should_use_groq(prompt):
        print(f"   [DEBUG] Contexto grande, usando Groq em vez de LM Studio")
        return chamar_groq(prompt, tentativa)
    
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


def self_discuss(prompt: str, use_lm_studio: bool = False) -> str:
    chamar = chamar_lm_studio if use_lm_studio else chamar_groq
    versoes = []
    for i in range(2):
        try:
            versoes.append(chamar(prompt, tentativa=i + 1))
        except Exception:
            pass
    if not versoes:
        from actions.web import action_browser_search
        return action_browser_search(prompt)
    if len(versoes) == 1:
        return versoes[0]
    try:
        return chamar(
            "Escolha a MELHOR resposta ou combine o essencial. "
            "Máx 3 frases, sem meta-comentários, em português.\n\n"
            f"1. {versoes[0]}\n2. {versoes[1]}\n\nResposta final:"
        )
    except Exception:
        return versoes[0]


def buscar_info(prompt: str) -> str:
    try:
        return self_discuss(prompt, use_lm_studio=True)
    except Exception:
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
    """Usa LLM para interpretar intenção. Retorna None se confiança baixa ou resposta vazia.
    Usa LM Studio por defeito, só usa Groq se contexto > 4096 tokens."""
    if not REQUESTS_AVAILABLE:
        return None

    historico_texto = ""
    if MEMORIA.get("historico"):
        ultimos = MEMORIA["historico"][-5:]
        historico_texto = "\n\n### CONTEXTO DA CONVERSA (últimas interações):\n"
        for h in ultimos:
            historico_texto += f"Usuário: {h['ent']}\nAssistente: {h['res']}\n"
        historico_texto += f"\nUsuário agora: {user_input}"

    prompt = f'Entrada: "{user_input}"{historico_texto}\n\nResponda APENAS com JSON válido:'
    
    # Usar função wrapper que decide automaticamente entre LM Studio e Groq
    try:
        # Tentar usar a lógica de seleção automática (LM Studio ou Groq conforme tamanho)
        messages, _ = _build_messages_with_history(prompt)
        
        if _should_use_groq(prompt):
            # Contexto grande, usar Groq
            if not GROQ_API_KEY:
                return None
            t0 = time.perf_counter()
            data = _post_chat(
                "https://api.groq.com/openai/v1/chat/completions",
                {
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 320,
                    "response_format": {"type": "json_object"},
                },
                {"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=12,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            stats.set_llm("groq", GROQ_MODEL, data.get("usage"), elapsed)
            content = data["choices"][0]["message"]["content"].strip()
        else:
            # Contexto pequeno, usar LM Studio
            if not LM_STUDIO_URL:
                return None
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
