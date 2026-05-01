"""Percepção da Infinity: ouvir (microfone) e ver (câmara/imagens).

Tudo nesta camada é opcional: se faltar uma dependência (SpeechRecognition,
PyAudio, OpenCV) ou hardware (microfone, câmara), devolvemos uma mensagem
explicativa em vez de rebentar.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from config import REQUESTS_AVAILABLE


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

    # Tenta usar Faster-Whisper local (Gratuito), caso contrário usa Google
    try:
        # Grava o áudio temporariamente
        with open("temp_audio.wav", "wb") as f:
            f.write(audio.get_wav_data())
            
        try:
            from faster_whisper import WhisperModel
            # Usa o modelo 'tiny' ou 'base' para ser rápido e leve localmente
            model_size = "tiny" 
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            
            segments, info = model.transcribe("temp_audio.wav", beam_size=5, language=idioma.split("-")[0])
            texto = "".join([segment.text for segment in segments]).strip()
            
            import os
            os.remove("temp_audio.wav")
        except ImportError:
            # Se faster-whisper não estiver instalado, usa Google Speech Recognition (Gratuito)
            texto = r.recognize_google(audio, language=idioma)
            
    except sr.UnknownValueError:
        return "🤷 Apanhei o áudio mas não percebi o que disseste."
    except Exception as e:
        # Fallback final para Google
        try:
            texto = r.recognize_google(audio, language=idioma)
        except Exception:
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
    """Tira uma foto pela webcam e descreve-a."""
    path, err = _capturar_webcam(camera_idx)
    if err:
        return err
    return action_descrever_imagem(str(path), prompt or _PROMPT_VER_DEFAULT)


def action_ocr(path: str) -> str:
    """Extrai texto de uma imagem usando Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path), lang='por+eng')
        return text.strip() if text.strip() else "Não detetei texto legível."
    except ImportError:
        return "❌ Tesseract não instalado. Instala 'pytesseract' e o motor Tesseract no sistema."
    except Exception as e:
        return f"❌ Erro no OCR: {e}"

def action_descrever_imagem(path: str, prompt: str | None = None) -> str:
    """Envia uma imagem (local) ao modelo de visão via LM Studio."""
    from config import LM_STUDIO_URL, REQUESTS_AVAILABLE
    import base64
    
    if not REQUESTS_AVAILABLE or not LM_STUDIO_URL:
        return "❌ LM Studio não configurado ou requests não disponível."

    try:
        with open(path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        import requests
        # Endpoint de chat completions do LM Studio suporta visão se o modelo carregado for multimodal
        payload = {
            "model": "moondream2", # Nome sugerido, o utilizador deve ter este ou similar carregado
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt or _PROMPT_VER_DEFAULT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        return result["choices"][0]["message"]["content"].strip()
        
    except Exception as e:
        return f"❌ Erro na visão local (LM Studio): {e}. Certifica-te que tens um modelo de visão (ex: Moondream) carregado."
