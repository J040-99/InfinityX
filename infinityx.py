#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfinityX - Assistente Local Autônomo com IA Interpretativa
Arquitetura: LLM-first + Fallback inteligente + Ferramentas locais
"""

import os, re, json, math, random, subprocess, shutil, ctypes, webbrowser
import urllib.request, urllib.parse, sys, io, time, threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ============================================================================
# DEPENDÊNCIAS OPCIONAIS
# ============================================================================
try:
    import requests; REQUESTS_AVAILABLE = True
except: REQUESTS_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except: SELENIUM_AVAILABLE = False; BROWSER_SESSION = None

try:
    import pyautogui; pyautogui.PAUSE = 0.5; pyautogui.FAILSAFE = True
    SYSTEM_AUTO_AVAILABLE = True
except: SYSTEM_AUTO_AVAILABLE = False

try:
    import psutil; PSUTIL_AVAILABLE = True
except: PSUTIL_AVAILABLE = False

try:
    import pyperclip; PYPERCLIP_AVAILABLE = True
except: PYPERCLIP_AVAILABLE = False

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================
try:
    from dotenv import load_dotenv; load_dotenv()
except: pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
MEMORIA_FILE = "memory.json"
TODO_FILE = "todos.json"
CONFIDENCE_THRESHOLD = 0.85  # Limite para usar decisão da IA

# ============================================================================
# MEMÓRIA PERSISTENTE
# ============================================================================
MEMORIA = {"historico": [], "variaveis": {}, "ultima_pasta": None}

def carregar_memoria():
    global MEMORIA
    try:
        if os.path.exists(MEMORIA_FILE):
            with open(MEMORIA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            MEMORIA = {k: data.get(k, v) for k, v in MEMORIA.items()}
    except: pass

def salvar_memoria():
    try:
        with open(MEMORIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(MEMORIA, f, ensure_ascii=False, indent=2)
    except: pass

carregar_memoria()

# ============================================================================
# MAPEAMENTOS (SEM ESPAÇOS!)
# ============================================================================
FOLDER_ALIASES = {
    "transferencias": "Downloads", "downloads": "Downloads",
    "documentos": "Documents", "document": "Documents",
    "imagens": "Pictures", "fotos": "Pictures",
    "músicas": "Music", "musicas": "Music",
    "vídeos": "Videos", "videos": "Videos",
    "área de trabalho": "Desktop", "desktop": "Desktop",
}

FILE_CATEGORIES = {
    "Imagens": [".jpg",".jpeg",".png",".gif",".bmp",".webp"],
    "Videos": [".mp4",".mkv",".avi",".mov",".wmv"],
    "Documentos": [".pdf",".doc",".docx",".txt",".ppt",".pptx",".xls",".xlsx"],
    "Audio": [".mp3",".wav",".flac",".aac"],
    "Arquivos": [".zip",".rar",".7z",".tar",".iso"],
    "Codigo": [".py",".js",".ts",".java",".cpp",".html",".css",".json"],
}

TYPOS_MAP = {
    "whastapp":"whatsapp","youtub":"youtube","chrom":"chrome",
    "firefos":"firefox","notepd":"notepad"
}

# ============================================================================
# 🧠 PROMPT DO SISTEMA PARA CLASSIFICAÇÃO DE INTENÇÕES
# ============================================================================
INTENT_SYSTEM_PROMPT = '''
Você é o cérebro do InfinityX, um assistente local autônomo.
Tarefa: Analisar a entrada e decidir QUAL ação executar.

### AÇÕES DISPONÍVEIS (use EXATAMENTE estes nomes):

CONVERSA: "responder" (saudações, conversas casuais)
MATEMÁTICA: "matematica" (expressões: "2+2", "raiz de 9", "quanto é 10*3")
SISTEMA: "clima" (cidade: "São Paulo" ou null), "hora_data", "sysinfo", 
          "battery_status", "network_info", "disk_usage" (drive: "C:\\" ou null)
ARQUIVOS: "listar_pasta" (pasta), "organizar_pasta" (pasta, executar: bool),
          "search_files" (query, folder, ext), "file_info" (path),
          "compress"/"extract" (files/output, zip_file/dest), "cleanup_temp"
APPS/BROWSER: "abrir_app" (app), "abrir_url" (url), 
              "browser_search" (query, engine: "google"/"youtube"),
              "youtube_music" (shuffle)
MÍDIA: "speak" (text, lang), "volume_set" (level), "volume_mute", "screenshot" (path)
CLIPBOARD: "clipboard_copy" (text), "clipboard_paste", "clipboard_clear"
TEXTO: "translate" (text, to_lang), "encrypt"/"decrypt" (text/encoded, key)
UTILITÁRIOS: "convert" (value, from, to), "currency_convert" (amount, from, to),
             "generate_password" (length, special), "generate_qr" (text, filename),
             "shorten_url" (url), "random_dice" (sides, count),
             "random_coin", "random_number" (min_val, max_val), "bmi" (weight, height),
             "ping" (host)
TAREFAS: "todo_add" (task, priority), "todo_list" (show_done), "todo_done" (task_id),
         "timer_set" (name, minutes), "countdown" (seconds, label), "news" (category)
AUTOMAÇÃO: "type_text" (text), "press_key" (key), "click" (x, y, button),
           "move_mouse" (x, y), "scroll" (direction, amount),
           "window_control" (app, action), "kill_process" (process)

### FORMATO DE RESPOSTA (JSON PURO):
{"action":"nome_acao","params":{"param":"valor"},"confidence":0.95}

### REGRAS:
1. Conversa casual → action:"responder", params:{}, confidence:0.99
2. Baixa certeza → confidence < 0.7 (aciona fallback)
3. Para apps → normalize: "chrome","firefox","notepad","calc","explorer"
4. Para pastas → use aliases: downloads, documents, pictures, music, videos, desktop
5. Para clima → cidade null = usar localização atual via IP
6. NUNCA invente ações fora da lista

### EXEMPLOS:
"oi, tudo bem?" → {"action":"responder","params":{},"confidence":0.99}
"quantos graus em Lisboa?" → {"action":"clima","params":{"cidade":"Lisboa"},"confidence":0.96}
"abre o youtube" → {"action":"abrir_url","params":{"url":"https://www.youtube.com"},"confidence":0.95}
"abre o youtube na parte de shorts" → {"action":"abrir_url","params":{"url":"https://www.youtube.com/shorts"},"confidence":0.93}
"abre o navegador pra pesquisar receitas" → {"action":"browser_search","params":{"query":"receitas","engine":"google"},"confidence":0.91}
"organiza meus downloads de verdade" → {"action":"organizar_pasta","params":{"pasta":"Downloads","executar":true},"confidence":0.94}
"2+2" → {"action":"matematica","params":{"expr":"2+2"},"confidence":0.99}
"toca uma música aleatória" → {"action":"youtube_music","params":{},"confidence":0.89}
"qual meu IP público?" → {"action":"network_info","params":{},"confidence":0.97}
"minimiza o chrome" → {"action":"window_control","params":{"app":"chrome","action":"minimizar"},"confidence":0.88}
'''

# ============================================================================
# 🧠 CLASSIFICADOR DE INTENÇÕES VIA LLM
# ============================================================================
def classify_intent(user_input: str) -> dict | None:
    """Usa LLM para interpretar intenção. Retorna None se confiança baixa."""
    if not REQUESTS_AVAILABLE or not GROQ_API_KEY:
        return None
    try:
        prompt = f'Entrada: "{user_input}"\n\nResponda APENAS com JSON válido:'
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 256
            },
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=12
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"].strip()
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            if "action" in result and "confidence" in result:
                return result if result["confidence"] >= CONFIDENCE_THRESHOLD else None
        return None
    except:
        return None

# ============================================================================
# UTILITÁRIOS
# ============================================================================
def get_user_home():
    return Path(os.path.expanduser("~"))

def resolve_path(folder: str):
    folder = folder.strip().lower().rstrip('/\\')
    if folder in FOLDER_ALIASES:
        base = get_user_home() / FOLDER_ALIASES[folder]
        return (base, True, "") if base.exists() else (base, False, f"Pasta '{FOLDER_ALIASES[folder]}' não existe")
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

# ============================================================================
# PRÉ-ANÁLISE (Respostas ultra-rápidas sem IA)
# ============================================================================
def pre_analyze(query: str):
    q = query.strip().lower()
    
    # Matemática em português
    try:
        import unicodedata
        q_norm = ''.join(c for c in unicodedata.normalize('NFD', q) if unicodedata.category(c) != 'Mn')
        tokens = [t.strip('.,!?;:') for t in q_norm.split() if t.strip('.,!?;:')]
        
        numero_map = {
            'zero':0,'um':1,'uma':1,'dois':2,'duas':2,'tres':3,'três':3,'quatro':4,
            'cinco':5,'seis':6,'sete':7,'oito':8,'nove':9,'dez':10,'onze':11,
            'doze':12,'treze':13,'quatorze':14,'catorze':14,'quinze':15,
            'dezesseis':16,'dezessete':17,'dezoito':18,'dezenove':19,'vinte':20,
            'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60,'setenta':70,
            'oitenta':80,'noventa':90,'cem':100,'mil':1000
        }
        op_map = {'mais':'+','somar':'+','menos':'-','subtrair':'-','vezes':'*','por':'*','dividido':'/','dividir':'/'}
        
        # Juntar números compostos
        i = 0
        while i < len(tokens) - 1:
            combined = f"{tokens[i]} {tokens[i+1]}"
            if combined in numero_map:
                tokens[i] = combined
                tokens.pop(i+1)
            i += 1
        
        expr_tokens = []
        for t in tokens:
            if t in numero_map:
                expr_tokens.append(str(numero_map[t]))
            elif t in op_map:
                expr_tokens.append(op_map[t])
            elif t.replace('.','').replace('-','').isdigit() or t in '+-*/().%':
                expr_tokens.append(t)
        
        if expr_tokens:
            expr = ''.join(expr_tokens)
            if any(op in expr for op in '+-*/') and re.match(r'^[\d+\-*/.()%]+$', expr):
                return str(eval(expr, {"__builtins__": {}}, {"math": math, "sqrt": math.sqrt}))
    except:
        pass
    
    # Saudações e conversas
    if q in ["oi","ola","olá","hey","eae"] or any(q.startswith(s+" ") for s in ["oi","ola","olá","bom dia","boa tarde","boa noite"]):
        return random.choice(["Oi! Tudo bem?","E aí! Em que ajudo?","Fala! Bora trabalhar.","Oi! Vamos lá."])
    
    if any(p in q for p in ["como vai","como está","tudo bem","tudo ok"]):
        return random.choice(["Estou bem! E você?","Tudo certinho! Em que ajudo?","Ótimo! E com você?"])
    
    if q in ["boa","blz","beleza","valeu","show","top","joia"]:
        return random.choice(["Isso! 🤙","Bora! 🚀","Tamo junto! ✨","Show! Em que ajudo?"])
    
    # Hora/data
    if "que horas" in q or ("hora" in q and "tempo" not in q):
        return datetime.now().strftime('%H:%M')
    if "que dia" in q or "data" in q:
        return datetime.now().strftime('%d/%m/%Y')
    
    return None

# ============================================================================
# APIs DE IA
# ============================================================================
def chamar_groq(prompt: str, tentativa: int = 1) -> str:
    if not GROQ_API_KEY or not REQUESTS_AVAILABLE:
        raise Exception("GROQ_API_KEY não configurada")
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],
              "temperature":0.3 if tentativa==1 else 0.5,"max_tokens":512},
        headers={"Authorization":f"Bearer {GROQ_API_KEY}"}, timeout=30)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"].strip()

def chamar_lm_studio(prompt: str) -> str:
    if not LM_STUDIO_URL or not REQUESTS_AVAILABLE:
        raise Exception("LM_STUDIO_URL não configurada")
    res = requests.post(LM_STUDIO_URL,
        json={"model":"local-model","messages":[{"role":"user","content":prompt}],
              "temperature":0.4,"max_tokens":512}, timeout=15)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"].strip()

def self_discuss(prompt: str, use_lm_studio: bool = False) -> str:
    chamar = chamar_lm_studio if use_lm_studio else chamar_groq
    versoes = []
    for i in range(2):
        try:
            versoes.append(chamar(prompt, tentativa=i+1) if not use_lm_studio else chamar(prompt))
        except:
            pass
    if not versoes:
        return chamar_perplexity(prompt)
    if len(versoes) == 1:
        return versoes[0]
    try:
        refinado = chamar(f"Escolha a MELHOR resposta ou combine o essencial. Máx 3 frases, sem meta-comentários, em português.\n\n1. {versoes[0]}\n2. {versoes[1]}\n\nResposta final:")
        return refinado
    except:
        return versoes[0]

def chamar_perplexity(prompt: str) -> str:
    url = f"https://www.perplexity.ai/search?q={urllib.parse.quote(prompt)}"
    webbrowser.open(url)
    return f"🔍 Buscando no Perplexity: '{prompt}'"

def buscar_info(prompt: str) -> str:
    try:
        return self_discuss(prompt, use_lm_studio=True)
    except:
        try:
            return self_discuss(prompt)
        except:
            try:
                return chamar_perplexity(prompt)
            except:
                return "Não consegui encontrar. Tente novamente."

# ============================================================================
# AÇÕES LOCAIS - SISTEMA & UTILITÁRIOS
# ============================================================================
def action_hora() -> str:
    n = datetime.now()
    return f"{n.strftime('%d/%m/%Y')} às {n.strftime('%H:%M')}"

def action_sysinfo() -> str:
    import platform
    return f"{platform.system()} {platform.release()} | {os.getlogin()}"

def get_localizacao_atual() -> str:
    try:
        with urllib.request.urlopen("http://ip-api.com/json/?fields=city", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("city", "")
    except:
        return None

def action_clima(cidade: str = None) -> str:
    if not cidade:
        cidade = get_localizacao_atual()
    if not cidade:
        cidade = "São Paulo"
    try:
        cidade_encoded = urllib.parse.quote(cidade.strip())
        url = f"https://api.openweathermap.org/data/2.5/weather?q={cidade_encoded}&appid={OPENWEATHERMAP_API_KEY}&lang=pt"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            temp = data["main"]["temp"] - 273.15
            feels = data["main"]["feels_like"] - 273.15
            desc = data["weather"][0]["description"]
            hum = data["main"]["humidity"]
            return f"{cidade}: {temp:.1f}°C (sensação {feels:.1f}°C) - {desc} (umidade {hum}%)"
    except Exception as e:
        return f"Erro clima: {e}"

def action_battery_status() -> str:
    if not PSUTIL_AVAILABLE:
        return "ℹ️ Instale psutil para status da bateria"
    try:
        battery = psutil.sensors_battery()
        if battery:
            status = "🔌 Carregando" if battery.power_plugged else "🔋 Usando bateria"
            remaining = "" if battery.secsleft == psutil.POWER_TIME_UNLIMITED else f" ({battery.secsleft//60}min)"
            return f"{status}: {battery.percent}%{remaining}"
        return "ℹ️ Bateria não detectada"
    except:
        return "❌ Não foi possível ler status da bateria"

def action_network_info() -> str:
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=3) as resp:
                public_ip = resp.read().decode()
        except:
            public_ip = "Não disponível"
        return f"🌐 Rede:\n• Local: {local_ip}\n• Público: {public_ip}"
    except Exception as e:
        return f"❌ Erro: {e}"

def action_disk_usage(drive: str = None) -> str:
    if not PSUTIL_AVAILABLE:
        return "ℹ️ Instale psutil para info de disco"
    try:
        if not drive:
            drive = os.path.expanduser("~").split("\\")[0] + "\\"
        usage = psutil.disk_usage(drive)
        total_gb, used_gb, free_gb = usage.total/(1024**3), usage.used/(1024**3), usage.free/(1024**3)
        bar = "█"*int(usage.percent/5) + "░"*(20-int(usage.percent/5))
        return f"💾 {drive}:\n[{bar}] {usage.percent:.0f}%\n• Usado: {used_gb:.1f}GB\n• Livre: {free_gb:.1f}GB"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# AÇÕES - ARQUIVOS & PASTAS
# ============================================================================
def action_listar(folder: str = ".") -> str:
    path, ok, err = resolve_path(folder)
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
    except Exception as e:
        return f"Erro: {e}"

def action_organizar(folder: str = ".", executar: bool = False) -> str:
    path, ok, err = resolve_path(folder)
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
                except:
                    pass
        MEMORIA["ultima_pasta"] = str(path)
        return f"Organizei {moved} arquivos em {len(grouped)} pastas."
    except Exception as e:
        return f"Erro: {e}"

def action_search_files(query: str, folder: str = None, ext: str = None) -> str:
    if not folder:
        folder = get_user_home()
    else:
        folder, ok, _ = resolve_path(folder)
        if not ok:
            return f"❌ Pasta não encontrada: {folder}"
    results, query_lower = [], query.lower()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if query_lower in f.lower() and (not ext or f.lower().endswith(ext.lower())):
                full_path = os.path.join(root, f)
                size = os.path.getsize(full_path) / 1024
                results.append(f"• {f} ({size:.1f}KB) - {root}")
                if len(results) >= 15:
                    break
        if len(results) >= 15:
            break
    if not results:
        return f"🔍 Nenhum arquivo encontrado com '{query}'"
    return f"🔍 Resultados para '{query}' ({len(results)}):\n" + "\n".join(results[:10]) + ("..." if len(results) > 10 else "")

def action_file_info(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"❌ Arquivo não encontrado: {path}"
        stat = p.stat()
        size = f"{stat.st_size/(1024**2):.2f} MB" if stat.st_size >= 1024**2 else f"{stat.st_size/1024:.1f} KB"
        return f"📄 {p.name}\n• Tamanho: {size}\n• Tipo: {p.suffix or 'Sem extensão'}\n• Modificado: {datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M')}\n• Caminho: {p.absolute()}"
    except Exception as e:
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
            except:
                pass
        return f"🧹 Limpeza: {deleted} arquivos removidos, {freed/(1024*1024):.2f} MB liberados"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# AÇÕES - APPS & BROWSER
# ============================================================================
def action_abrir(app: str) -> str:
    try:
        app_lower = app.lower().strip()
        app_map = {"browser":"chrome","navegador":"chrome","chrome":"chrome","firefox":"firefox","edge":"msedge","notepad":"notepad","calculadora":"calc","explorer":"explorer"}
        app_key = app_map.get(app_lower, app_lower)
        try:
            subprocess.Popen(f'start "" "{app_key}"', shell=True)
            return f"✅ Abrindo: {app}"
        except:
            pass
        app_paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "msedge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "notepad": "notepad.exe", "calc": "calc.exe", "explorer": "explorer.exe"
        }
        if app_key in app_paths and os.path.exists(app_paths[app_key]):
            subprocess.Popen([app_paths[app_key]], shell=True)
            return f"✅ Abrindo: {app}"
        subprocess.Popen([app_key], shell=True)
        return f"✅ Abrindo: {app}"
    except FileNotFoundError:
        return f"❌ '{app}' não encontrado."
    except Exception as e:
        return f"❌ Erro: {e}"

def action_browser_search(query: str, engine: str = "google") -> str:
    engines = {
        "google": f"https://www.google.com/search?q={urllib.parse.quote(query)}",
        "youtube": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
        "bing": f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    }
    url = engines.get(engine, engines["google"])
    webbrowser.open_new_tab(url)
    return f"🌐 Pesquisando '{query}' no {engine.title()}"

def action_youtube_music_shuffle() -> str:
    try:
        webbrowser.open_new_tab("https://music.youtube.com/shuffle")
        return "🎵 YouTube Music com shuffle aberto"
    except:
        webbrowser.open_new_tab("https://music.youtube.com")
        return "🎵 YouTube Music aberto"

def action_abrir_url(url: str) -> str:
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        webbrowser.open_new_tab(url)
        return f"✅ Abrindo: {url}"
    except Exception as e:
        return f"❌ Erro ao abrir URL: {e}"

# ============================================================================
# AÇÕES - MÍDIA, CLIPBOARD & TEXTO
# ============================================================================
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
        return f"🔊 Falando: '{text[:50]}{'...' if len(text)>50 else ''}'"
    except Exception as e:
        return f"❌ Erro ao falar: {e}"

def action_clipboard_copy(text: str) -> str:
    try:
        if PYPERCLIP_AVAILABLE:
            import pyperclip
            pyperclip.copy(text)
        else:
            subprocess.run(['clip'], input=text, encoding='utf-8', shell=True)
        return f"📋 Copiado: '{text[:50]}{'...' if len(text)>50 else ''}'"
    except:
        return "❌ Erro ao copiar"

def action_clipboard_paste() -> str:
    try:
        if PYPERCLIP_AVAILABLE:
            import pyperclip
            content = pyperclip.paste()
            return f"📋 Clipboard: '{content[:200]}{'...' if len(content)>200 else ''}'"
        return "ℹ️ Instale pyperclip para ler clipboard"
    except:
        return "❌ Não foi possível ler"

def action_translate(text: str, to_lang: str = "en") -> str:
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target=to_lang).translate(text)
        lang_names = {"pt":"Português","en":"Inglês","es":"Espanhol","fr":"Francês","de":"Alemão"}
        return f"🌐 Tradução ({lang_names.get(to_lang,to_lang)}):\n{translated}"
    except ImportError:
        return "❌ Instale: pip install deep-translator"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# AÇÕES - UTILITÁRIOS DIVERSOS
# ============================================================================
def action_convert(value: float, from_unit: str, to_unit: str) -> str:
    conversions = {
        ('c','f'):lambda x:x*9/5+32, ('f','c'):lambda x:(x-32)*5/9,
        ('km','mi'):lambda x:x*0.621371, ('mi','km'):lambda x:x*1.60934,
        ('kg','lb'):lambda x:x*2.20462, ('lb','kg'):lambda x:x*0.453592,
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
                return f"💱 {amount:.2f} {from_curr} = {result:.2f} {to_curr}\n📊 Taxa: 1 {from_curr} = {rates[to_curr]:.4f} {to_curr}"
            return f"❌ Moeda '{to_curr}' não encontrada"
    except Exception as e:
        return f"❌ Erro: {e}"

def action_generate_password(length: int = 16, special: bool = True) -> str:
    import secrets, string
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
    except Exception as e:
        return f"❌ Erro: {e}"

def action_random_dice(sides: int = 6, count: int = 1) -> str:
    import random
    rolls = [random.randint(1, sides) for _ in range(count)]
    return f"🎲 {' + '.join(map(str,rolls))} = {sum(rolls)}" if count > 1 else f"🎲 Resultado: {rolls[0]}"

def action_ping(host: str) -> str:
    try:
        import socket, time
        start = time.time()
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, 80))
        elapsed = (time.time() - start) * 1000
        return f"🌐 {host}: ✅ Online ({elapsed:.0f}ms)"
    except:
        return f"🌐 {host}: ❌ Offline"

def action_bmi(weight: float, height: float) -> str:
    try:
        height_m = height / 100
        bmi = weight / (height_m ** 2)
        category = "⚠️ Abaixo" if bmi<18.5 else "✅ Normal" if bmi<25 else "⚠️ Sobrepeso" if bmi<30 else "🔴 Obesidade"
        return f"📊 IMC: {bmi:.1f}\n{category}\n💡 Fórmula: peso(kg) / altura(m)²"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# AÇÕES - TAREFAS & TIMERS
# ============================================================================
TIMERS = {}

def action_todo_add(task: str, priority: str = "medium") -> str:
    try:
        todos = []
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, 'r', encoding='utf-8') as f:
                todos = json.load(f)
        todo = {"id": len(todos)+1, "task": task, "priority": priority, "done": False, "created": datetime.now().strftime('%d/%m %H:%M')}
        todos.append(todo)
        with open(TODO_FILE, 'w', encoding='utf-8') as f:
            json.dump(todos, f, ensure_ascii=False, indent=2)
        return f"✅ Tarefa #{todo['id']} adicionada: '{task}' [{priority}]"
    except Exception as e:
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
            prio = {"high":"🔴","medium":"🟡","low":"🟢"}.get(t['priority'], "⚪")
            lines.append(f"{status} #{t['id']} {prio} {t['task']} ({t['created']})")
        return "\n".join(lines) + (f"\n... e mais {len(filtered)-10}" if len(filtered)>10 else "")
    except Exception as e:
        return f"❌ Erro: {e}"

def action_timer_set(name: str, minutes: int) -> str:
    import threading
    from datetime import datetime, timedelta
    end_time = datetime.now() + timedelta(minutes=minutes)
    TIMERS[name] = {"end": end_time, "minutes": minutes}
    def alert():
        while datetime.now() < end_time:
            time.sleep(1)
        print(f"\n🔔 TIMER '{name}' concluído!\n> ", end="", flush=True)
        try:
            ctypes.windll.kernel32.Beep(1000, 500)
        except:
            pass
    threading.Thread(target=alert, daemon=True).start()
    return f"⏱️ Timer '{name}': {minutes}min (termina {end_time.strftime('%H:%M')})"

# ============================================================================
# AÇÕES - AUTOMAÇÃO DO SISTEMA (pyautogui)
# ============================================================================
def action_type_text(text: str, delay: float = 0.1) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instale pyautogui para automação"
    try:
        pyautogui.write(text, interval=delay)
        return f"⌨️ Digitado: '{text[:50]}{'...' if len(text)>50 else ''}'"
    except Exception as e:
        return f"❌ Erro: {e}"

def action_press_key(key: str) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instale pyautogui"
    try:
        key_map = {"enter":"enter","tab":"tab","esc":"esc","ctrl":"ctrl","alt":"alt","shift":"shift",
                   "copy":["ctrl","c"],"paste":["ctrl","v"],"cut":["ctrl","x"],"save":["ctrl","s"]}
        keys = key_map.get(key.lower(), [key.lower()])
        pyautogui.hotkey(*keys) if isinstance(keys, list) else pyautogui.press(keys)
        return f"⌨️ Tecla: {key}"
    except Exception as e:
        return f"❌ Erro: {e}"

def action_click(x: int = None, y: int = None, button: str = "left") -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instale pyautogui"
    try:
        pyautogui.click(x=x, y=y, button=button)
        return f"🖱️ Clique{' em ('+str(x)+', '+str(y)+')' if x is not None else ''}"
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
                {"minimizar":w.minimize,"maximizar":w.maximize,"fechar":w.close,"focar":w.set_focus}.get(action, lambda: None)()
                return f"🪟 {action}: {app_name}"
        return f"❌ Janela '{app_name}' não encontrada"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# 🧠 PARSER DE INTENÇÕES - LLM-FIRST + FALLBACK
# ============================================================================
SCRIPTS_PENDENTES = {}

def analisar(entrada: str) -> dict:
    e = entrada.strip().lower()
    
    # Corrige typos comuns
    for typo, correto in TYPOS_MAP.items():
        e = e.replace(typo, correto)
    
    # 1️⃣ Pré-análise ultra-rápida
    if pre := pre_analyze(entrada):
        return {"action": "responder", "texto": pre}
    
    # 2️⃣ Classificação via LLM (prioridade)
    llm = classify_intent(entrada)
    if llm and llm.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
        action_map = {
            "responder":"responder","matematica":"matematica","clima":"clima","hora_data":"hora",
            "abrir_app":"abrir","abrir_url":"abrir_url","browser_search":"browser_search",
            "listar_pasta":"listar","organizar_pasta":"organizar","sysinfo":"sysinfo",
            "youtube_music":"youtube_music_shuffle","clipboard_copy":"clipboard_copy",
            "clipboard_paste":"clipboard_paste","volume_set":"volume_set","volume_mute":"volume_mute",
            "battery_status":"battery_status","network_info":"network_info","disk_usage":"disk_usage",
            "convert":"convert","generate_password":"generate_password","generate_qr":"generate_qr",
            "timer_set":"timer_set","search_files":"search_files","speak":"speak",
            "todo_add":"todo_add","todo_list":"todo_list","todo_done":"todo_done",
            "currency_convert":"currency_convert","translate":"translate","random_dice":"random_dice",
            "random_coin":"random_coin","random_number":"random_number","cleanup_temp":"cleanup_temp",
            "shorten_url":"shorten_url","ping":"ping","bmi":"bmi","type_text":"type_text",
            "press_key":"press_key","click":"click","window_control":"window_control",
        }
        action_name = action_map.get(llm["action"])
        if action_name:
            return {"action": action_name, **llm.get("params", {}), "source": "llm"}
    
    # 3️⃣ Fallback: pattern matching tradicional (robustez)
    if any(s in e for s in ["sair","exit","quit"]):
        return {"action": "sair"}
    if any(h in e for h in ["ajuda","help"]):
        return {"action": "ajuda"}
    
    # Clima
    if any(c in e for c in ["clima","tempo","graus","quantos graus","previsão"]):
        cidade = None
        for cid in ["são paulo","rio de janeiro","lisboa","london","new york"]:
            if cid in e:
                cidade = cid.title()
                if cid in ["são paulo","rio de janeiro","lisboa"]:
                    cidade = {"são paulo":"São Paulo","rio de janeiro":"Rio de Janeiro","lisboa":"Lisboa"}[cid]
                break
        return {"action": "clima", "cidade": cidade}
    
    # Apps
    if any(a in e for a in ["abre","abrir"]) and any(app in e for app in ["chrome","firefox","notepad","calc"]):
        app = next((a for a in ["chrome","firefox","notepad","calc"] if a in e), "chrome")
        return {"action": "abrir", "app": app}
    
    # Matemática fallback
    if re.match(r'^[\d\s+\-*/.()%?!.]+$', e) and any(op in e for op in '+-*/'):
        try:
            return {"action": "matematica", "expr": e.rstrip('?.!')}
        except:
            pass
    
    # Último recurso: busca via IA
    return {"action": "buscar", "query": entrada, "source": "fallback"}

# ============================================================================
# ⚙️ EXECUTOR DE AÇÕES
# ============================================================================
def executar_acao(dec: dict) -> str:
    action = dec.get("action", "")
    acoes = {
        "responder": lambda: dec.get("texto", ""),
        "matematica": lambda: str(eval(dec.get("expr","0"), {"__builtins__": {}}, {"math": math, "sqrt": math.sqrt})),
        "hora": action_hora,
        "clima": lambda: action_clima(dec.get("cidade")),
        "sysinfo": action_sysinfo,
        "battery_status": action_battery_status,
        "network_info": action_network_info,
        "disk_usage": lambda: action_disk_usage(dec.get("drive")),
        "listar": lambda: action_listar(dec.get("pasta", ".")),
        "organizar": lambda: action_organizar(dec.get("pasta", "."), dec.get("executar", False)),
        "search_files": lambda: action_search_files(dec.get("query",""), dec.get("folder"), dec.get("ext")),
        "file_info": lambda: action_file_info(dec.get("path","")),
        "cleanup_temp": action_cleanup_temp,
        "abrir": lambda: action_abrir(dec.get("app", "notepad")),
        "abrir_url": lambda: action_abrir_url(dec.get("url","")),
        "browser_search": lambda: action_browser_search(dec.get("query",""), dec.get("engine","google")),
        "youtube_music_shuffle": action_youtube_music_shuffle,
        "speak": lambda: action_speak(dec.get("text",""), dec.get("lang","pt")),
        "clipboard_copy": lambda: action_clipboard_copy(dec.get("text","")),
        "clipboard_paste": action_clipboard_paste,
        "translate": lambda: action_translate(dec.get("text",""), dec.get("to_lang","en")),
        "convert": lambda: action_convert(dec.get("value",0), dec.get("from",""), dec.get("to","")),
        "currency_convert": lambda: action_currency_convert(dec.get("amount",0), dec.get("from",""), dec.get("to","")),
        "generate_password": lambda: action_generate_password(dec.get("length",16), dec.get("special",True)),
        "generate_qr": lambda: action_generate_qr(dec.get("text",""), dec.get("filename","qrcode.png")),
        "shorten_url": lambda: action_shorten_url(dec.get("url","")),
        "random_dice": lambda: action_random_dice(dec.get("sides",6), dec.get("count",1)),
        "random_coin": lambda: action_random_dice(2,1),
        "random_number": lambda: f"🎲 {random.randint(dec.get('min_val',1), dec.get('max_val',100))}",
        "ping": lambda: action_ping(dec.get("host","google.com")),
        "bmi": lambda: action_bmi(dec.get("weight",70), dec.get("height",170)),
        "todo_add": lambda: action_todo_add(dec.get("task",""), dec.get("priority","medium")),
        "todo_list": lambda: action_todo_list(dec.get("show_done",False)),
        "timer_set": lambda: action_timer_set(dec.get("name","timer"), dec.get("minutes",5)),
        "type_text": lambda: action_type_text(dec.get("text","")),
        "press_key": lambda: action_press_key(dec.get("key","")),
        "click": lambda: action_click(dec.get("x"), dec.get("y"), dec.get("button","left")),
        "window_control": lambda: action_window_control(dec.get("app",""), dec.get("action","")),
    }
    
    if action in acoes:
        try:
            return acoes[action]()
        except Exception as e:
            return f"❌ Erro: {e}"
    
    if action == "ajuda":
        return "🤖 InfinityX - Assistente Local com IA\n\n💬 Conversa natural: fale como quiser\n🧠 A IA interpreta e escolhe a ferramenta certa\n\nExemplos:\n• 'tá frio em lisboa?' → clima\n• 'organiza meus downloads' → organizar pasta\n• 'abre youtube pra mim' → browser\n• '2+2' ou 'quanto é 10*3?' → matemática\n• 'gera uma senha' → utilitário\n\nBasta pedir naturalmente!"
    
    if action == "sair":
        return "__sair__"
    
    # Fallback final: busca via IA
    return buscar_info(dec.get("query", dec.get("instrucao", "")))

# ============================================================================
# 🚀 MAIN
# ============================================================================
def main():
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

    print("=" * 50)
    print("InfinityX - Assistente Local com IA Autônoma")
    print("=" * 50)
    print("💡 Dica: Fale naturalmente, a IA interpreta!")

    while True:
        try:
            entrada = input("\n> ").strip()
            if not entrada:
                continue
            if entrada.lower() in ["sair", "exit", "quit"]:
                print("Até!"); break
            
            dec = analisar(entrada)
            resposta = executar_acao(dec)
            
            if resposta == "__sair__":
                print("Até!"); break
            
            MEMORIA["historico"].append({"ent": entrada, "res": resposta[:100], "src": dec.get("source","?")})
            salvar_memoria()
            print(resposta)
            
        except EOFError:
            print("\nAté!"); break
        except KeyboardInterrupt:
            print("\n\nHasta la vista!"); break
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()