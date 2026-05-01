"""Percepção da Infinity: ouvir (microfone) e ver (câmara/imagens).

Tudo nesta camada é opcional: se faltar uma dependência (SpeechRecognition,
PyAudio, OpenCV) ou hardware (microfone, câmara), devolvemos uma mensagem
explicativa em vez de rebentar.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from config import GROQ_API_KEY, REQUESTS_AVAILABLE


# ---------------------------------------------------------------- ouvir
def action_ouvir(duracao: int = 6, idioma: str = "pt-PT") -> str:
    """Captura áudio do microfone e devolve a transcrição."""
    try:
        import speech_recognition as sr
    except ImportError:
        return ("❌ Não tenho a biblioteca de reconhecimento de voz. "
                "Instala 'SpeechRecognition' e 'pyaudio' "
                "(pip install SpeechRecognition pyaudio).")

    r = sr.Recognizer()
    try:
        mic = sr.Microphone()
    except (OSError, AttributeError) as e:
        return (f"❌ Não encontrei nenhum microfone ({e}). "
                "Verifica os drivers de áudio e instala 'pyaudio'.")

    try:
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=0.4)
            print(f"🎤 A ouvir... (até {duracao}s)")
            try:
                audio = r.listen(source, timeout=4, phrase_time_limit=duracao)
            except sr.WaitTimeoutError:
                return "🔇 Não ouvi nada. Fala mais alto ou tenta outra vez."
    except OSError as e:
        return f"❌ Erro a abrir o microfone: {e}"

    try:
        texto = r.recognize_google(audio, language=idioma)
    except sr.UnknownValueError:
        return "🤷 Apanhei o áudio mas não percebi o que disseste."
    except sr.RequestError as e:
        return f"❌ Serviço de transcrição indisponível: {e}"
    except Exception as e:
        return f"❌ Erro a transcrever: {e}"

    return f"🎤 Ouvi: {texto}"


def action_ouvir_e_responder(duracao: int = 6, idioma: str = "pt-PT") -> str:
    """Ouve do microfone, transcreve e processa como se fosse texto."""
    transcrito = action_ouvir(duracao, idioma)
    if not transcrito.startswith("🎤 Ouvi:"):
        return transcrito

    texto = transcrito.split("🎤 Ouvi:", 1)[1].strip()
    if not texto:
        return "🤷 Não percebi nada."

    # Import local para quebrar o ciclo actions <-> parser.
    from parser import analisar, executar_acao

    dec = analisar(texto)
    resposta = executar_acao(dec)
    return f'🎤 Disseste: "{texto}"\n{resposta}'


# ----------------------------------------------------------------- ver
_PROMPT_VER_DEFAULT = (
    "Descreve brevemente o que vês na imagem em português europeu. "
    "Se houver texto legível, transcreve-o de forma concisa."
)
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _capturar_webcam(camera_idx: int = 0, destino: str = "captura.png"):
    """Captura uma frame da câmara e guarda em PNG. Devolve (caminho, erro)."""
    try:
        import cv2
    except ImportError:
        return None, ("❌ Não tenho OpenCV. Instala 'opencv-python' "
                      "(pip install opencv-python) para usar a câmara.")

    cap = cv2.VideoCapture(camera_idx)
    if not cap.isOpened():
        cap.release()
        return None, f"❌ Câmara {camera_idx} indisponível."

    # As primeiras frames costumam vir escuras; descarta-as.
    frame = None
    for _ in range(6):
        ok, frame = cap.read()
        if ok and frame is not None:
            time.sleep(0.05)
        else:
            time.sleep(0.05)
    cap.release()

    if frame is None:
        return None, "❌ Não consegui capturar imagem da câmara."

    out = Path(destino)
    try:
        cv2.imwrite(str(out), frame)
    except Exception as e:
        return None, f"❌ Erro a gravar a imagem: {e}"
    return out, None


def action_ver(prompt: str | None = None, camera_idx: int = 0) -> str:
    """Tira uma foto pela webcam e descreve-a com o modelo de visão."""
    path, err = _capturar_webcam(camera_idx)
    if err:
        return err
    return action_descrever_imagem(str(path), prompt or _PROMPT_VER_DEFAULT)


def action_descrever_imagem(path: str, prompt: str | None = None) -> str:
    """Envia uma imagem (local) ao modelo de visão e devolve a descrição."""
    if not path:
        return "❌ Indica o caminho da imagem (ex.: 'descreve a imagem foto.png')."

    p = Path(path).expanduser()
    if not p.exists():
        return f"❌ Imagem não encontrada: {path}"
    if not REQUESTS_AVAILABLE:
        return "❌ Falta a biblioteca 'requests' para enviar a imagem."
    if not GROQ_API_KEY:
        return "❌ Configura GROQ_API_KEY no .env para eu poder ver."

    import requests
    import stats

    try:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError as e:
        return f"❌ Erro a ler a imagem: {e}"

    ext = p.suffix.lower().lstrip(".") or "png"
    if ext == "jpg":
        ext = "jpeg"
    data_url = f"data:image/{ext};base64,{b64}"

    body = {
        "model": _VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or _PROMPT_VER_DEFAULT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "temperature": 0.4,
        "max_tokens": 400,
    }

    t0 = time.perf_counter()
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return f"❌ Erro a contactar o modelo de visão: {e}"

    elapsed = (time.perf_counter() - t0) * 1000
    stats.set_llm("groq", _VISION_MODEL, data.get("usage"), elapsed)

    try:
        descricao = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        return "❌ Resposta inesperada do modelo de visão."
    if not descricao:
        return "🤷 O modelo não devolveu descrição."
    return f"👁️ {descricao}"
