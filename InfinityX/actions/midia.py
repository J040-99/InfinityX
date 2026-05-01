"""Ações de mídia, clipboard e automação de input (teclado/rato/janelas)."""

import subprocess

from config import (
    PYPERCLIP_AVAILABLE,
    SELENIUM_AVAILABLE,
    SYSTEM_AUTO_AVAILABLE,
)

if SYSTEM_AUTO_AVAILABLE:
    import pyautogui


def action_speak(text: str, lang: str = "pt") -> str:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        for v in engine.getProperty('voices'):
            if lang in str(v.languages).lower() or 'brazil' in v.id.lower() or 'portuguese' in v.id.lower():
                engine.setProperty('voice', v.id)
                break
        engine.setProperty('rate', 150)
        engine.say(text)
        engine.runAndWait()
        return f"🔊 Falando: '{text[:50]}{'...' if len(text) > 50 else ''}'"
    except ImportError:
        return "❌ Instale pyttsx3 para usar TTS"
    except Exception as e:
        return f"❌ Erro ao falar: {e}"


def action_clipboard_copy(text: str) -> str:
    try:
        if PYPERCLIP_AVAILABLE:
            import pyperclip
            pyperclip.copy(text)
        else:
            subprocess.run(["cmd", "/c", "echo", text, "|", "clip"], check=True, shell=True)
        return f"📋 Copiado: '{text[:50]}{'...' if len(text) > 50 else ''}'"
    except (OSError, subprocess.SubprocessError):
        return "❌ Erro ao copiar"


def action_clipboard_paste() -> str:
    try:
        if PYPERCLIP_AVAILABLE:
            import pyperclip
            content = pyperclip.paste()
            return f"📋 Clipboard: '{content[:200]}{'...' if len(content) > 200 else ''}'"
        return "ℹ️ Instale pyperclip para ler clipboard"
    except Exception:
        return "❌ Não foi possível ler"


def action_type_text(text: str, delay: float = 0.1) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instale pyautogui para automação"
    try:
        pyautogui.write(text, interval=delay)
        return f"⌨️ Digitado: '{text[:50]}{'...' if len(text) > 50 else ''}'"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_press_key(key: str) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instale pyautogui"
    try:
        key_map = {
            "enter": "enter", "tab": "tab", "esc": "esc", "ctrl": "ctrl",
            "alt": "alt", "shift": "shift",
            "copy": ["ctrl", "c"], "paste": ["ctrl", "v"],
            "cut": ["ctrl", "x"], "save": ["ctrl", "s"],
        }
        keys = key_map.get(key.lower(), [key.lower()])
        if isinstance(keys, list):
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(keys)
        return f"⌨️ Tecla: {key}"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_click(x: int | None = None, y: int | None = None, button: str = "left") -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instale pyautogui"
    try:
        pyautogui.click(x=x, y=y, button=button)
        coords = f" em ({x}, {y})" if x is not None else ""
        return f"🖱️ Clique{coords}"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_window_control(app_name: str, action: str) -> str:
    if not SELENIUM_AVAILABLE:
        return "❌ Instale selenium para controle de janelas"
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            if app_name.lower() in w.window_text().lower():
                ops = {"minimizar": w.minimize, "maximizar": w.maximize,
                       "fechar": w.close, "focar": w.set_focus}
                ops.get(action, lambda: None)()
                return f"🪟 {action}: {app_name}"
        return f"❌ Janela '{app_name}' não encontrada"
    except ImportError:
        return "❌ Instale pywinauto para controle de janelas"
    except Exception as e:
        return f"❌ Erro: {e}"
