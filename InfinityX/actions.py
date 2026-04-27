"""Implementação de todas as ações executáveis pelo InfinityX."""

import base64
import ctypes
import hashlib
import json
import os
import platform
import random
import re
import secrets
import shutil
import socket
import string
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError

from config import (
    OPENWEATHERMAP_API_KEY,
    PSUTIL_AVAILABLE,
    PYPERCLIP_AVAILABLE,
    SELENIUM_AVAILABLE,
    SYSTEM_AUTO_AVAILABLE,
    TODO_FILE,
)
from memory import MEMORIA, NOTAS, PALAVRAS, TIMERS, salvar_notas, salvar_palavras
from utils import categorize_file, get_user_home, resolve_path

if PSUTIL_AVAILABLE:
    import psutil

if SYSTEM_AUTO_AVAILABLE:
    import pyautogui


# ----- Sistema -----
def action_hora() -> str:
    n = datetime.now()
    return f"{n.strftime('%d/%m/%Y')} às {n.strftime('%H:%M')}"


def action_sysinfo() -> str:
    try:
        user = os.getlogin()
    except OSError:
        user = os.environ.get("USER") or os.environ.get("USERNAME", "?")
    return f"{platform.system()} {platform.release()} | {user}"


def get_localizacao_atual() -> str | None:
    try:
        with urllib.request.urlopen("http://ip-api.com/json/?fields=city", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("city", "")
    except (URLError, json.JSONDecodeError, OSError):
        return None


def action_clima(cidade: str | None = None, amanha: bool = False) -> str:
    if not cidade:
        cidade = get_localizacao_atual()
    if not cidade:
        cidade = "São Paulo"
    if amanha:
        return f"🌤️ Amanhã em {cidade}: use 'previsão 7 dias' para ver a previsão completa"
    try:
        cidade_encoded = urllib.parse.quote(cidade.strip())
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={cidade_encoded}&appid={OPENWEATHERMAP_API_KEY}&units=metric&lang=pt"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            temp = data["main"]["temp"]
            feels = data["main"]["feels_like"]
            desc = data["weather"][0]["description"]
            hum = data["main"]["humidity"]
            return f"{cidade}: {temp:.1f}°C (sensação {feels:.1f}°C) - {desc} (umidade {hum}%)"
    except (URLError, json.JSONDecodeError, KeyError, OSError) as e:
        return f"Erro clima: {e}"


def action_battery_status() -> str:
    if not PSUTIL_AVAILABLE:
        return "ℹ️ Instale psutil para status da bateria"
    try:
        battery = psutil.sensors_battery()
        if battery:
            status = "🔌 Carregando" if battery.power_plugged else "🔋 Usando bateria"
            remaining = (
                "" if battery.secsleft == psutil.POWER_TIME_UNLIMITED
                else f" ({battery.secsleft // 60}min)"
            )
            return f"{status}: {battery.percent}%{remaining}"
        return "ℹ️ Bateria não detectada"
    except (AttributeError, OSError):
        return "❌ Não foi possível ler status da bateria"


def action_network_info() -> str:
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=3) as resp:
                public_ip = resp.read().decode()
        except URLError:
            public_ip = "Não disponível"
        return f"🌐 Rede:\n• Local: {local_ip}\n• Público: {public_ip}"
    except OSError as e:
        return f"❌ Erro: {e}"


def action_disk_usage(drive: str | None = None) -> str:
    if not PSUTIL_AVAILABLE:
        return "ℹ️ Instale psutil para info de disco"
    try:
        if not drive:
            drive = str(Path.home().anchor)
            if not drive:
                drive = "C:\\" if sys.platform == "win32" else "/"
        usage = psutil.disk_usage(drive)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        bar = "█" * int(usage.percent / 5) + "░" * (20 - int(usage.percent / 5))
        return (
            f"💾 {drive}:\n[{bar}] {usage.percent:.0f}%\n"
            f"• Usado: {used_gb:.1f}GB\n• Livre: {free_gb:.1f}GB"
        )
    except OSError as e:
        return f"❌ Erro: {e}"


# ----- Arquivos & Pastas -----
def action_listar(folder: str = ".") -> str:
    path, ok, _ = resolve_path(folder)
    if not ok:
        return f"Pasta não encontrada: {folder}"
    try:
        files = [f.name for f in path.iterdir() if f.is_file()][:25]
        dirs = [f.name for f in path.iterdir() if f.is_dir()][:5]
        r = f"{path.name} ({len(files)} arquivos)"
        if files:
            r += "\n" + "\n".join(f"- {x}" for x in files)
        if dirs:
            r += f"\n\nPastas: {', '.join(dirs)}"
        MEMORIA["ultima_pasta"] = str(path)
        return r if files or dirs else "Pasta vazia."
    except PermissionError:
        return "Sem permissão."
    except OSError as e:
        return f"Erro: {e}"


def action_organizar(folder: str = ".", executar: bool = False) -> str:
    path, ok, _ = resolve_path(folder)
    if not ok:
        return f"Pasta não encontrada: {folder}"
    try:
        grouped = defaultdict(list)
        for f in path.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                grouped[categorize_file(f.name)].append(f.name)
        if not grouped:
            return "Nada pra organizar."
        if not executar:
            total = sum(len(v) for v in grouped.values())
            linhas = [f"{path.name} ({total} arquivos):"]
            for cat in sorted(grouped):
                linhas.append(f"  {cat} ({len(grouped[cat])})")
            linhas.append("\nDiga 'organizar [pasta]' pra valer.")
            return "\n".join(linhas)
        moved = 0
        for cat, itens in grouped.items():
            tgt = path / cat
            tgt.mkdir(exist_ok=True)
            for fn in itens:
                try:
                    src, dst = path / fn, tgt / fn
                    if dst.exists():
                        name, ext = os.path.splitext(fn)
                        dst = tgt / f"{name}_{moved}{ext}"
                    shutil.move(str(src), str(dst))
                    moved += 1
                except OSError:
                    pass
        MEMORIA["ultima_pasta"] = str(path)
        return f"Organizei {moved} arquivos em {len(grouped)} pastas."
    except OSError as e:
        return f"Erro: {e}"


def action_search_files(query: str, folder: str | None = None, ext: str | None = None) -> str:
    if not folder:
        base = get_user_home()
    else:
        base, ok, _ = resolve_path(folder)
        if not ok:
            return f"❌ Pasta não encontrada: {folder}"
    results, query_lower = [], query.lower()
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if query_lower in f.lower() and (not ext or f.lower().endswith(ext.lower())):
                full_path = os.path.join(root, f)
                try:
                    size = os.path.getsize(full_path) / 1024
                except OSError:
                    continue
                results.append(f"• {f} ({size:.1f}KB) - {root}")
                if len(results) >= 15:
                    break
        if len(results) >= 15:
            break
    if not results:
        return f"🔍 Nenhum arquivo encontrado com '{query}'"
    return (
        f"🔍 Resultados para '{query}' ({len(results)}):\n"
        + "\n".join(results[:10])
        + ("..." if len(results) > 10 else "")
    )


def action_file_info(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"❌ Arquivo não encontrado: {path}"
        stat = p.stat()
        size = (
            f"{stat.st_size / (1024 ** 2):.2f} MB"
            if stat.st_size >= 1024 ** 2
            else f"{stat.st_size / 1024:.1f} KB"
        )
        return (
            f"📄 {p.name}\n"
            f"• Tamanho: {size}\n"
            f"• Tipo: {p.suffix or 'Sem extensão'}\n"
            f"• Modificado: {datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M')}\n"
            f"• Caminho: {p.absolute()}"
        )
    except OSError as e:
        return f"❌ Erro: {e}"


def action_cleanup_temp() -> str:
    try:
        import tempfile
        temp_dir = tempfile.gettempdir()
        deleted, freed = 0, 0
        for f in Path(temp_dir).iterdir():
            try:
                if f.is_file():
                    size = f.stat().st_size
                    f.unlink()
                    deleted += 1
                    freed += size
            except OSError:
                pass
        return f"🧹 Limpeza: {deleted} arquivos removidos, {freed / (1024 * 1024):.2f} MB liberados"
    except OSError as e:
        return f"❌ Erro: {e}"


def action_criar_arquivo(nome: str, conteudo: str = "", pasta: str = ".") -> str:
    try:
        path = Path(pasta) if pasta != "." else Path.cwd()
        if not path.exists():
            path = Path.home()
        if not nome.endswith('.txt'):
            nome += '.txt'
        arquivo = path / nome
        arquivo.write_text(conteudo, encoding='utf-8')
        return f"✅ Arquivo criado: {arquivo.absolute()}"
    except OSError as e:
        return f"❌ Erro: {e}"


# ----- Apps & Browser -----
def action_abrir(app: str) -> str:
    """Abre apps/sites de forma autônoma: app desktop → pesquisa IA → fallback Google."""
    try:
        app_lower = app.strip().lower()
        partes = app_lower.split()
        app_base = partes[0] if partes else app_lower

        apps_desktop = {"chrome", "firefox", "edge", "notepad", "calc", "explorer", "cmd", "powershell"}
        if app_base in apps_desktop:
            try:
                if sys.platform == "win32":
                    subprocess.run(["start", "", app_base], shell=True, check=True)
                else:
                    subprocess.Popen([app_base])
                return f"✅ Abrindo: {app_base}"
            except (OSError, subprocess.SubprocessError):
                pass

        try:
            from googlesearch import search
            results = list(search(f"{app} site oficial", num_results=5, lang="pt"))
            for result in results:
                if any(ext in result for ext in [".com", ".org", ".pt", ".br", ".io", ".co", ".net"]):
                    webbrowser.open_new_tab(result)
                    return f"🌐 Abrindo: {result}"
            if results:
                webbrowser.open_new_tab(results[0])
                return f"🌐 Abrindo: {results[0]}"
        except ImportError:
            pass
        except Exception:
            pass

        query = urllib.parse.quote(app_lower)
        webbrowser.open_new_tab(f"https://www.google.com/search?q={query}")
        return f"🔍 Pesquisando '{app}' no Google"
    except OSError as e:
        return f"❌ Erro ao abrir: {e}"


def action_browser_search(query: str, engine: str = "google") -> str:
    engines = {
        "google": f"https://www.google.com/search?q={urllib.parse.quote(query)}",
        "youtube": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
        "bing": f"https://www.bing.com/search?q={urllib.parse.quote(query)}",
    }
    url = engines.get(engine, engines["google"])
    webbrowser.open_new_tab(url)
    return f"🌐 Pesquisando '{query}' no {engine.title()}"


def action_youtube_music_shuffle() -> str:
    try:
        webbrowser.open_new_tab("https://music.youtube.com/shuffle")
        return "🎵 YouTube Music com shuffle aberto"
    except webbrowser.Error:
        webbrowser.open_new_tab("https://music.youtube.com")
        return "🎵 YouTube Music aberto"


def action_abrir_url(url: str) -> str:
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        webbrowser.open_new_tab(url)
        return f"✅ Abrindo: {url}"
    except webbrowser.Error as e:
        return f"❌ Erro ao abrir URL: {e}"


# ----- Mídia, Clipboard & Texto -----
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


def action_translate(text: str, to_lang: str = "en") -> str:
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target=to_lang).translate(text)
        lang_names = {"pt": "Português", "en": "Inglês", "es": "Espanhol", "fr": "Francês", "de": "Alemão"}
        return f"🌐 Tradução ({lang_names.get(to_lang, to_lang)}):\n{translated}"
    except ImportError:
        return "❌ Instale: pip install deep-translator"
    except Exception as e:
        return f"❌ Erro: {e}"


# ----- Utilitários diversos -----
def action_convert(value: float, from_unit: str, to_unit: str) -> str:
    conversions = {
        ('c', 'f'): lambda x: x * 9 / 5 + 32, ('f', 'c'): lambda x: (x - 32) * 5 / 9,
        ('km', 'mi'): lambda x: x * 0.621371, ('mi', 'km'): lambda x: x * 1.60934,
        ('kg', 'lb'): lambda x: x * 2.20462, ('lb', 'kg'): lambda x: x * 0.453592,
    }
    key = (from_unit.lower(), to_unit.lower())
    if key in conversions:
        return f"🔄 {value} {from_unit} = {conversions[key](value):.2f} {to_unit}"
    if from_unit.lower() == to_unit.lower():
        return f"🔄 {value} {from_unit} = {value} {to_unit}"
    return f"❌ Conversão não suportada: {from_unit} → {to_unit}"


def action_currency_convert(amount: float, from_curr: str, to_curr: str) -> str:
    try:
        from_curr, to_curr = from_curr.upper(), to_curr.upper()
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            rates = data.get('rates', {})
            if to_curr in rates:
                result = amount * rates[to_curr]
                return (
                    f"💱 {amount:.2f} {from_curr} = {result:.2f} {to_curr}\n"
                    f"📊 Taxa: 1 {from_curr} = {rates[to_curr]:.4f} {to_curr}"
                )
            return f"❌ Moeda '{to_curr}' não encontrada"
    except (URLError, json.JSONDecodeError, KeyError, OSError) as e:
        return f"❌ Erro: {e}"


def action_generate_password(length: int = 16, special: bool = True) -> str:
    chars = string.ascii_letters + string.digits + ("!@#$%^&*()_+-=" if special else "")
    password = ''.join(secrets.choice(chars) for _ in range(length))
    return f"🔐 Senha:\n`{password}`\n💡 Salve em um gerenciador!"


def action_generate_qr(text: str, filename: str = "qrcode.png") -> str:
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filename)
        return f"📱 QR Code salvo: {os.path.abspath(filename)}"
    except ImportError:
        return "❌ Instale: pip install qrcode[pil]"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_shorten_url(url: str) -> str:
    try:
        api_url = f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}"
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            short = resp.read().decode().strip()
            if short.startswith("http"):
                return f"🔗 Encurtado:\nOriginal: {url}\nCurto: {short}"
            return "❌ Não foi possível encurtar"
    except (URLError, OSError) as e:
        return f"❌ Erro: {e}"


def action_random_dice(sides: int = 6, count: int = 1) -> str:
    rolls = [random.randint(1, sides) for _ in range(count)]
    if count > 1:
        return f"🎲 {' + '.join(map(str, rolls))} = {sum(rolls)}"
    return f"🎲 Resultado: {rolls[0]}"


def action_ping(host: str) -> str:
    try:
        start = time.time()
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, 80))
        elapsed = (time.time() - start) * 1000
        return f"🌐 {host}: ✅ Online ({elapsed:.0f}ms)"
    except OSError:
        return f"🌐 {host}: ❌ Offline"


def action_bmi(weight: float, height: float) -> str:
    try:
        height_m = height / 100
        bmi = weight / (height_m ** 2)
        if bmi < 18.5:
            category = "⚠️ Abaixo"
        elif bmi < 25:
            category = "✅ Normal"
        elif bmi < 30:
            category = "⚠️ Sobrepeso"
        else:
            category = "🔴 Obesidade"
        return f"📊 IMC: {bmi:.1f}\n{category}\n💡 Fórmula: peso(kg) / altura(m)²"
    except (ZeroDivisionError, ValueError) as e:
        return f"❌ Erro: {e}"


# ----- Dicionário pessoal -----
def action_palavras_aprender(palavra: str, significado: str) -> str:
    palavra_lower = palavra.strip().lower()
    PALAVRAS[palavra_lower] = {
        "significado": significado,
        "adicionado": datetime.now().strftime('%d/%m/%Y %H:%M'),
    }
    salvar_palavras()
    return f"📚 Aprendida: '{palavra}' = {significado}"


def action_palavras_procurar(palavra: str) -> str | None:
    palavra_lower = palavra.strip().lower()
    if palavra_lower in PALAVRAS:
        info = PALAVRAS[palavra_lower]
        return f"📖 {palavra}: {info['significado']} (add {info['adicionado']})"
    return None


def action_palavras_listar() -> str:
    if not PALAVRAS:
        return "📚 Nenhuma palavra aprendida ainda!"
    linhas = ["📚 Minhas palavras:"]
    for p, info in list(PALAVRAS.items())[:20]:
        linhas.append(f"• {p}: {info['significado']}")
    return "\n".join(linhas)


def action_palavras_excluir(palavra: str) -> str:
    palavra_lower = palavra.strip().lower()
    if palavra_lower in PALAVRAS:
        del PALAVRAS[palavra_lower]
        salvar_palavras()
        return f"🗑️ Removida: '{palavra}'"
    return f"❌ Palavra '{palavra}' não existe"


# ----- Tarefas & Timers -----
def action_todo_add(task: str, priority: str = "medium") -> str:
    try:
        todos = []
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, 'r', encoding='utf-8') as f:
                todos = json.load(f)
        todo = {
            "id": len(todos) + 1, "task": task, "priority": priority,
            "done": False, "created": datetime.now().strftime('%d/%m %H:%M'),
        }
        todos.append(todo)
        with open(TODO_FILE, 'w', encoding='utf-8') as f:
            json.dump(todos, f, ensure_ascii=False, indent=2)
        return f"✅ Tarefa #{todo['id']} adicionada: '{task}' [{priority}]"
    except (OSError, json.JSONDecodeError) as e:
        return f"❌ Erro: {e}"


def action_todo_list(show_done: bool = False) -> str:
    try:
        if not os.path.exists(TODO_FILE):
            return "📋 Nenhuma tarefa cadastrada."
        with open(TODO_FILE, 'r', encoding='utf-8') as f:
            todos = json.load(f)
        filtered = [t for t in todos if show_done or not t['done']]
        if not filtered:
            return "🎉 Todas concluídas!" if not show_done else "📋 Lista vazia."
        lines = ["📋 Suas tarefas:"]
        for t in filtered[:10]:
            status = "✅" if t['done'] else "⏳"
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t['priority'], "⚪")
            lines.append(f"{status} #{t['id']} {prio} {t['task']} ({t['created']})")
        suffix = f"\n... e mais {len(filtered) - 10}" if len(filtered) > 10 else ""
        return "\n".join(lines) + suffix
    except (OSError, json.JSONDecodeError) as e:
        return f"❌ Erro: {e}"


def action_timer_set(name: str, minutes: int) -> str:
    end_time = datetime.now() + timedelta(minutes=minutes)
    TIMERS[name] = {"end": end_time, "minutes": minutes}

    def alert() -> None:
        while datetime.now() < end_time:
            time.sleep(1)
        print(f"\n🔔 TIMER '{name}' concluído!\n> ", end="", flush=True)
        try:
            ctypes.windll.kernel32.Beep(1000, 500)
        except (AttributeError, OSError):
            pass

    threading.Thread(target=alert, daemon=True).start()
    return f"⏱️ Timer '{name}': {minutes}min (termina {end_time.strftime('%H:%M')})"


# ----- Automação do sistema -----
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


# ----- Ferramentas de texto e dados (stdlib) -----
def action_uuid_gen(count: int = 1) -> str:
    try:
        n = max(1, min(int(count), 20))
    except (TypeError, ValueError):
        n = 1
    return "\n".join(str(uuid.uuid4()) for _ in range(n))


def action_hash_text(text: str, algo: str = "sha256") -> str:
    if not text:
        return "❌ Texto vazio"
    algo = (algo or "sha256").lower()
    if algo not in {"md5", "sha1", "sha256", "sha512"}:
        return f"❌ Algoritmo desconhecido: {algo}"
    h = hashlib.new(algo, text.encode("utf-8")).hexdigest()
    return f"{algo}: {h}"


def action_base64(text: str, mode: str = "encode") -> str:
    if not text:
        return "❌ Texto vazio"
    try:
        if (mode or "encode").lower().startswith("dec"):
            return base64.b64decode(text.encode("utf-8")).decode("utf-8", errors="replace")
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    except (ValueError, UnicodeError) as e:
        return f"❌ Base64: {e}"


def action_url_codec(text: str, mode: str = "encode") -> str:
    if not text:
        return "❌ Texto vazio"
    if (mode or "encode").lower().startswith("dec"):
        return urllib.parse.unquote(text)
    return urllib.parse.quote(text, safe="")


def action_text_tools(text: str, op: str = "count") -> str:
    if text is None:
        return "❌ Texto vazio"
    op = (op or "count").lower()
    if op == "count":
        chars = len(text)
        chars_no_ws = len(re.sub(r"\s", "", text))
        words = len(text.split())
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        return f"📝 {words} palavras · {chars} caracteres ({chars_no_ws} sem espaços) · {lines} linhas"
    if op == "upper":
        return text.upper()
    if op == "lower":
        return text.lower()
    if op == "title":
        return text.title()
    if op == "reverse":
        return text[::-1]
    if op == "trim":
        return "\n".join(line.strip() for line in text.splitlines())
    if op == "dedupe":
        seen, out = set(), []
        for line in text.splitlines():
            if line not in seen:
                seen.add(line)
                out.append(line)
        return "\n".join(out)
    if op == "sort":
        return "\n".join(sorted(text.splitlines()))
    return f"❌ Operação desconhecida: {op}"


def action_json_format(text: str, indent: int = 2) -> str:
    if not text:
        return "❌ Texto vazio"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return f"❌ JSON inválido: {e.msg} (linha {e.lineno}, col {e.colno})"
    return json.dumps(data, ensure_ascii=False, indent=int(indent or 2), sort_keys=False)


def action_color_convert(value: str) -> str:
    if not value:
        return "❌ Cor vazia"
    v = value.strip().lower().replace("#", "")
    if re.fullmatch(r"[0-9a-f]{6}", v):
        r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
        return f"🎨 #{v} → rgb({r}, {g}, {b})"
    if re.fullmatch(r"[0-9a-f]{3}", v):
        r, g, b = (int(c * 2, 16) for c in v)
        return f"🎨 #{v} → rgb({r}, {g}, {b})"
    m = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", value.strip().lower())
    if m:
        r, g, b = (max(0, min(255, int(x))) for x in m.groups())
        return f"🎨 rgb({r}, {g}, {b}) → #{r:02x}{g:02x}{b:02x}"
    return "❌ Use #RRGGBB, #RGB ou rgb(r, g, b)"


_LOREM_BASE = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
    "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute "
    "irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
    "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia "
    "deserunt mollit anim id est laborum."
)


def action_lorem_ipsum(paragraphs: int = 1) -> str:
    try:
        n = max(1, min(int(paragraphs), 10))
    except (TypeError, ValueError):
        n = 1
    return "\n\n".join(_LOREM_BASE for _ in range(n))


# ----- APIs públicas sem chave -----
def action_public_ip() -> str:
    try:
        with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=6) as resp:
            data = json.loads(resp.read().decode())
        return f"🌐 IP público: {data.get('ip', '?')}"
    except (URLError, OSError, json.JSONDecodeError) as e:
        return f"❌ Falha ao obter IP: {e}"


def action_wikipedia(query: str, lang: str = "pt") -> str:
    if not query:
        return "❌ Sem termo para procurar"
    lang = (lang or "pt").lower()
    title = urllib.parse.quote(query.strip().replace(" ", "_"))
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "InfinityX/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as e:
        return f"❌ Wikipedia: {e}"
    if data.get("type") == "disambiguation":
        return f"🔎 '{query}' é ambíguo na Wikipedia. Tenta ser mais específico."
    extract = data.get("extract") or "Sem resumo disponível."
    page = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    return f"📚 {data.get('title', query)}\n{extract}" + (f"\n🔗 {page}" if page else "")


_CRYPTO_ALIASES = {
    "btc": "bitcoin", "eth": "ethereum", "sol": "solana", "ada": "cardano",
    "doge": "dogecoin", "xrp": "ripple", "bnb": "binancecoin", "ltc": "litecoin",
    "matic": "polygon", "dot": "polkadot",
}


def action_crypto_price(coin: str = "bitcoin", currency: str = "usd") -> str:
    coin_id = _CRYPTO_ALIASES.get((coin or "").lower(), (coin or "bitcoin").lower())
    cur = (currency or "usd").lower()
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={urllib.parse.quote(coin_id)}&vs_currencies={urllib.parse.quote(cur)}"
        "&include_24hr_change=true"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "InfinityX/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as e:
        return f"❌ CoinGecko: {e}"
    info = data.get(coin_id)
    if not info or cur not in info:
        return f"❌ Não encontrei {coin_id} em {cur.upper()}"
    price = info[cur]
    change = info.get(f"{cur}_24h_change")
    arrow = "📈" if (change or 0) >= 0 else "📉"
    extra = f" {arrow} {change:+.2f}% (24h)" if change is not None else ""
    return f"💰 {coin_id.title()}: {price:,.2f} {cur.upper()}{extra}"


# ----- Notas pessoais -----
def action_nota_add(texto: str) -> str:
    if not texto or not texto.strip():
        return "❌ Nota vazia"
    NOTAS.append({"texto": texto.strip(), "ts": datetime.now().isoformat(timespec="seconds")})
    salvar_notas()
    return f"📝 Nota guardada (#{len(NOTAS)})"


def action_notas_listar() -> str:
    if not NOTAS:
        return "📭 Sem notas guardadas"
    linhas = []
    for i, n in enumerate(NOTAS, 1):
        ts = n.get("ts", "")[:16].replace("T", " ")
        linhas.append(f"{i}. [{ts}] {n.get('texto', '')}")
    return "📒 Notas:\n" + "\n".join(linhas)


def action_nota_excluir(idx: int) -> str:
    try:
        i = int(idx) - 1
    except (TypeError, ValueError):
        return "❌ Índice inválido"
    if not (0 <= i < len(NOTAS)):
        return f"❌ Não existe nota #{idx}"
    removida = NOTAS.pop(i)
    salvar_notas()
    return f"🗑️ Removida: {removida.get('texto', '')[:60]}"


# ----- Resumo do dia -----
def action_resumo_dia() -> str:
    partes = [f"📅 {datetime.now().strftime('%A, %d/%m/%Y · %H:%M')}"]
    try:
        clima = action_clima(None, False)
        if clima and not clima.startswith("❌"):
            partes.append(clima)
    except Exception:
        pass
    try:
        if PSUTIL_AVAILABLE:
            bat = action_battery_status()
            if bat and not bat.startswith("❌"):
                partes.append(bat)
    except Exception:
        pass
    try:
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, "r", encoding="utf-8") as f:
                todos = json.load(f)
            pendentes = [t for t in todos if not t.get("done")]
            if pendentes:
                top = pendentes[:5]
                partes.append("✅ Pendentes:\n" + "\n".join(f" • {t.get('task','')}" for t in top))
            else:
                partes.append("✅ Sem tarefas pendentes")
    except (IOError, json.JSONDecodeError):
        pass
    if NOTAS:
        ultimas = NOTAS[-3:]
        partes.append("📝 Notas recentes:\n" + "\n".join(
            f" • {n.get('texto', '')[:80]}" for n in ultimas
        ))
    return "\n\n".join(partes)
