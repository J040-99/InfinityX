"""Camada de IA: chamadas a Groq, LM Studio, Perplexity e classificador de intenções."""

import json
import re
import urllib.parse
import webbrowser

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


def chamar_groq(prompt: str, tentativa: int = 1) -> str:
    if not GROQ_API_KEY or not REQUESTS_AVAILABLE:
        raise RuntimeError("GROQ_API_KEY não configurada")
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3 if tentativa == 1 else 0.5,
            "max_tokens": 512,
        },
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"].strip()


def chamar_lm_studio(prompt: str, tentativa: int = 1) -> str:
    if not LM_STUDIO_URL or not REQUESTS_AVAILABLE:
        raise RuntimeError("LM_STUDIO_URL não configurada")
    res = requests.post(
        LM_STUDIO_URL,
        json={
            "model": "local-model",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4 if tentativa == 1 else 0.6,
            "max_tokens": 512,
        },
        timeout=15,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"].strip()


def chamar_perplexity(prompt: str) -> str:
    url = f"https://www.perplexity.ai/search?q={urllib.parse.quote(prompt)}"
    webbrowser.open(url)
    return f"🔍 Buscando no Perplexity: '{prompt}'"


def self_discuss(prompt: str, use_lm_studio: bool = False) -> str:
    chamar = chamar_lm_studio if use_lm_studio else chamar_groq
    versoes = []
    for i in range(2):
        try:
            versoes.append(chamar(prompt, tentativa=i + 1))
        except Exception:
            pass
    if not versoes:
        return chamar_perplexity(prompt)
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
            try:
                return chamar_perplexity(prompt)
            except Exception:
                return "Não consegui encontrar. Tente novamente."


def classify_intent(user_input: str) -> dict | None:
    """Usa LLM para interpretar intenção. Retorna None se confiança baixa ou resposta vazia."""
    if not REQUESTS_AVAILABLE or not GROQ_API_KEY:
        return None

    historico_texto = ""
    if MEMORIA.get("historico"):
        ultimos = MEMORIA["historico"][-5:]
        historico_texto = "\n\n### CONTEXTO DA CONVERSA (últimas interações):\n"
        for h in ultimos:
            historico_texto += f"Usuário: {h['ent']}\nAssistente: {h['res']}\n"
        historico_texto += f"\nUsuário agora: {user_input}"

    try:
        prompt = f'Entrada: "{user_input}"{historico_texto}\n\nResponda APENAS com JSON válido:'
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 320,
                "response_format": {"type": "json_object"},
            },
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=12,
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"].strip()
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
