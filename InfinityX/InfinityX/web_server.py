#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor web (Flask) para a Infinity em modo "live".

Expõe uma página única (`/`) onde o cliente liga/desliga microfone e câmara
e recebe respostas em tempo real. Toda a captura de áudio/vídeo é feita no
browser:

  • Áudio  -> Web Speech API (transcrição local) -> POST /api/chat
  • Vídeo  -> getUserMedia -> frame periódico em base64 -> POST /api/vision

O backend reutiliza exactamente o mesmo pipeline da CLI/GUI
(`analisar` + `executar_acao`) e a mesma camada de visão usada por
`action_descrever_imagem`.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

import stats
from actions import (
    action_descrever_imagem,
    iniciar_scheduler_lembretes,
)
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


app = Flask(__name__)


# ---------------------------------------------------------- helpers
def _registar_no_historico(entrada: str, resposta: str, dec: dict) -> None:
    MEMORIA["historico"].append({
        "ent": entrada,
        "res": (resposta or "")[:100],
        "src": dec.get("source", dec.get("action", "?")),
    })
    if len(MEMORIA["historico"]) > MAX_HISTORY:
        MEMORIA["historico"] = MEMORIA["historico"][-MAX_HISTORY:]
    try:
        salvar_memoria()
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------ rotas
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    texto = (data.get("text") or "").strip()
    if not texto:
        return jsonify({"reply": "", "source": "vazio", "footer": ""})

    stats.reset()
    t0 = time.perf_counter()
    try:
        dec = analisar(texto)
        resposta = executar_acao(dec)
    except Exception as exc:  # noqa: BLE001
        return jsonify({
            "reply": f"❌ Erro: {exc}",
            "source": "erro",
            "footer": "",
        }), 200
    elapsed = (time.perf_counter() - t0) * 1000

    if stats.LAST.get("source") is None:
        stats.set_local(dec.get("source") or "local", elapsed)
    else:
        stats.LAST["elapsed_ms"] = round(elapsed, 1)

    _registar_no_historico(texto, resposta, dec)

    return jsonify({
        "reply": resposta or "",
        "source": dec.get("source", dec.get("action", "?")),
        "footer": stats.format_footer() or "",
    })


@app.route("/api/vision", methods=["POST"])
def vision():
    data = request.get_json(silent=True) or {}
    image_data_url = data.get("image", "")
    prompt = (data.get("prompt") or "").strip() or None

    if not isinstance(image_data_url, str) or not image_data_url.startswith("data:image/"):
        return jsonify({
            "reply": "❌ Imagem inválida (esperado data URL).",
            "source": "erro",
            "footer": "",
        }), 200

    try:
        header, b64 = image_data_url.split(",", 1)
    except ValueError:
        return jsonify({
            "reply": "❌ Formato de imagem inválido.",
            "source": "erro",
            "footer": "",
        }), 200

    ext = "jpg" if "jpeg" in header or "jpg" in header else "png"
    tmp = Path(f"_live_capture.{ext}")
    try:
        tmp.write_bytes(base64.b64decode(b64))
    except Exception as exc:  # noqa: BLE001
        return jsonify({
            "reply": f"❌ Erro a descodificar imagem: {exc}",
            "source": "erro",
            "footer": "",
        }), 200

    stats.reset()
    t0 = time.perf_counter()
    try:
        resposta = action_descrever_imagem(str(tmp), prompt)
    except Exception as exc:  # noqa: BLE001
        return jsonify({
            "reply": f"❌ Erro ao analisar imagem: {exc}",
            "source": "erro",
            "footer": "",
        }), 200
    elapsed = (time.perf_counter() - t0) * 1000

    if stats.LAST.get("source") is None:
        stats.set_local("vision", elapsed)
    else:
        stats.LAST["elapsed_ms"] = round(elapsed, 1)

    # Armazena no contexto de visão privado (não visível no chat) para a Infinity ter contexto visual
    MEMORIA["contexto_visao"].append({
        "ent": "[câmara ao vivo]",
        "res": (resposta or "")[:100],
        "src": "vision"
    })
    if len(MEMORIA["contexto_visao"]) > MAX_HISTORY:
        MEMORIA["contexto_visao"] = MEMORIA["contexto_visao"][-MAX_HISTORY:]
    try:
        salvar_memoria()
    except Exception:  # noqa: BLE001
        pass

    # Para requisições de visão, não retornamos a descrição como mensagem visível
    # A descrição é armazenada em MEMORIA["contexto_visao"] para uso posterior pela IA
    return jsonify({
        "reply": "",  # Mensagem vazia - não mostra descrição de visão ao usuário
        "source": "vision",
        "footer": "",
    })


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "interacoes": len(MEMORIA.get("historico", []))})


_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='14' fill='#7c5cff'/>"
    "<text x='50%' y='54%' text-anchor='middle' dominant-baseline='middle' "
    "font-family='Segoe UI, sans-serif' font-size='40' font-weight='700' fill='white'>"
    "&#8734;</text></svg>"
)


@app.route("/favicon.ico")
def favicon():
    return Response(_FAVICON_SVG, mimetype="image/svg+xml")


@app.after_request
def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------- main
def main() -> None:
    carregar_palavras()
    carregar_memoria()
    carregar_notas()
    carregar_lembretes()
    iniciar_scheduler_lembretes()

    print("∞ Infinity · live em http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
