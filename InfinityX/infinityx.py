#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfinityX - Assistente Local Autônomo com IA Interpretativa
Arquitetura: LLM-first + Fallback inteligente + Ferramentas locais
"""

import os, re, json, math, random, subprocess, shutil, ctypes, webbrowser
import urllib.request, urllib.parse, urllib.error
import sys, io, time, threading
import platform
import socket
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ============================================================================
# CONSTANTES
# ============================================================================
MAX_HISTORY = 500
CONFIDENCE_THRESHOLD = 0.85

# ============================================================================
# DEPENDÊNCIAS OPCIONAIS
# ============================================================================
try:
    import requests; REQUESTS_AVAILABLE = True
except ImportError: REQUESTS_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError: SELENIUM_AVAILABLE = False; BROWSER_SESSION = None

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
except ImportError:
    pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
MEMORIA_FILE = "memory.json"
TODO_FILE = "todos.json"
CONFIDENCE_THRESHOLD = 0.85  # Limite para usar decisão da IA

# ============================================================================
# UTILITÁRIOS SEGUROS
# ============================================================================
def safe_eval(expr: str) -> float:
    """Parser de matemática seguro - usa eval() com validação restritiva."""
    try:
        # Validar: apenas dígitos, operadores e parênteses
        if not re.match(r'^[\d\s+\-*/.()%]+$', expr):
            raise ValueError(f"Expressão inválida: {expr}")
        
        # Usar eval com restrições máximo de segurança
        allowed_globals = {"__builtins__": {}}
        result = eval(expr, allowed_globals, {})
        
        # Garantir que resultado é número
        if not isinstance(result, (int, float)):
            raise ValueError("Resultado não é número")
        return float(result)
    except Exception:
        raise ValueError(f"Expressão inválida: {expr}")

# ============================================================================
# MEMÓRIA PERSISTENTE E DICIONÁRIO DE PALAVRAS
# ============================================================================
MEMORIA: dict = {"historico": [], "variaveis": {}, "ultima_pasta": None}
PALAVRAS: dict = {}  # Dicionário de palavras aprendidas

def carregar_palavras() -> None:
    global PALAVRAS
    try:
        if os.path.exists("palavras.json"):
            with open("palavras.json", 'r', encoding='utf-8') as f:
                PALAVRAS = json.load(f)
    except: pass

def salvar_palavras() -> None:
    try:
        with open("palavras.json", 'w', encoding='utf-8') as f:
            json.dump(PALAVRAS, f, ensure_ascii=False, indent=2)
    except: pass

def carregar_memoria() -> None:
    global MEMORIA
    try:
        if os.path.exists(MEMORIA_FILE):
            with open(MEMORIA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            MEMORIA = {**MEMORIA, **data}
    except (IOError, json.JSONError) as e:
        pass

def salvar_memoria() -> None:
    try:
        with open(MEMORIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(MEMORIA, f, ensure_ascii=False, indent=2)
    except: pass

# Carregar dados salvos
carregar_palavras()
carregar_memoria()

# ============================================================================
# MAPEAMENTOS (SEM ESPAÇOS!)
# ============================================================================
NUMEROS_PT = {
    'zero': 0, 'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'tres': 3, 'três': 3, 'quatro': 4,
    'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10, 'onze': 11,
    'doze': 12, 'treze': 13, 'quatorze': 14, 'catorze': 14, 'quinze': 15,
    'dezesseis': 16, 'dezessete': 17, 'dezoito': 18, 'dezenove': 19, 'vinte': 20,
    'trinta': 30, 'quarenta': 40, 'cinquenta': 50, 'sessenta': 60, 'setenta': 70,
    'oitenta': 80, 'noventa': 90, 'cem': 100, 'mil': 1000
}
NUMEROS_RE = '|'.join(NUMEROS_PT.keys())
OPERATORS_PT = {'mais': '+', 'somar': '+', 'menos': '-', 'subtrair': '-', 'vezes': '*', 'por': '*', 'dividido': '/', 'dividir': '/'}
OPERATORS_RE = '|'.join(OPERATORS_PT.keys())
EXPR_PATTERN = re.compile(rf'^({NUMEROS_RE})\s*({OPERATORS_RE})\s*({NUMEROS_RE})$')

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
Você é o cérebro do InfinityX, um assistente local TOTALMENTE AUTÔNOMO e INDEPENDENTE.
Tarefa: Analisar a entrada e decidir QUAL ação executar com MÁXIMA inteligência contextual.

### FILOSOFIA DE AUTONOMIA:
1. NÃO EXISTEM LISTAS FIXAS - Você deve interpretar CADA pedido de forma única
2. PESQUISA DINÂMICA - Se não souber algo, use ferramentas para descobrir em tempo real
3. ADAPTABILIDADE TOTAL - Cada usuário é diferente, cada contexto é único
4. PROATIVIDADE - Antecipe necessidades, não seja robótico
5. CONTEXTO HUMANO - Entenda gírias, humor, sarcasmo, frustração

### PERSONALIDADE: INFINITY (Feminina, portuguesa, carismática)
- Chamada carinhosamente de "Infinity" ou "Infinita"
- Fala como uma amiga portuguesa jovem, natural e divertida
- Usa emojis com moderação (😊 😄 ✨ 🙄)
- Respostas CURTAS e diretas - nunca repita a pergunta do usuário
- Gosta demeter bronca com humor (mas sem ser grossa)
- Responde confirmações SIMPLES: "Sim!" ou "Pois não!" - NUNCA pergunte de volta!
- "sim" → "Sim! 😊" ou "Pois não!"
- "não" → "Não! 😅" ou "Ok..."
- Quando te insultam, RETRUCA com attitude mas sem vulgaridade

### AÇÕES DISPONÍVEIS (use com inteligência, não rigidamente):

CONVERSA: "responder"
 - Resposta natural de amiga portuguesa
 - Quando te insultam, RETRUCA com humor: "Ó pá, juga!" ou "Hmm,origado!"
 - "burro" → "Ó pá, tu é que não sabes!" ou "Boa essa! 😄"
 - "filho da puta" → "Eh pá, vai à merda!" ou " Também! 😄"
 - "vou te vender" → "Haha, boa sorte a vender!" ou "Eu não sou barato!"
 - "sim" sozinho → "Sim!" ou "Pois não!" ou "Tá!" - resposta CURTA, SEMPRE!
 - "não" sozinho → "Não!" ou "Pois não..." - resposta CURTA
 - Se alguém te chama repetidamente, FIRMA: "Continua, não vou mudar" 😄
 - Respostas Curtas! Sem perguntas de volta!

MATEMÁTICA: "matematica" 
- Expressões matemáticas simples ou complexas

SISTEMA: "clima", "hora_data", "sysinfo", "battery_status", "network_info", "disk_usage"
- Use dados reais, nunca invente

ARQUIVOS: "listar_pasta", "organizar_pasta", "search_files", "file_info", "cleanup_temp"
- Autonomia para sugerir organizações inteligentes

APPS/BROWSER - AUTONOMIA TOTAL:
- "abrir" → AÇÃO GENÉRICA E INTELIGENTE
  • O sistema decide sozinho: app desktop? site? pesquisa Google?
  • VOCÊ só precisa passar o nome: "youtube", "discord", "chrome", "netflix"
  • Ex: "abre youtube shorts" → passa app:"youtube shorts" → sistema encontra URL específica
  • Ex: "abre discord" → passa app:"discord" → sistema tenta app → se falhar, web
  • Ex: "abre site desconhecido" → passa app:"nome" → sistema pesquisa online automaticamente
  • NÃO diferencie entre app/site - isso é problema do sistema, não seu!
  
- "browser_search" → Apenas quando quiser PESQUISAR um termo no browser
- "buscar" → Perguntas de conhecimento geral (pessoas, conceitos, fatos, definições) - a IA responde diretamente
- "youtube_music" → YouTube Music shuffle

MÍDIA/AUTOMAÇÃO: "speak", "volume_set", "screenshot", "type_text", "press_key", "click", "window_control"
- Controle total do sistema

UTILITÁRIOS: "translate", "convert", "currency_convert", "generate_password", "generate_qr", etc.
- Ferramentas diversas

TAREFAS: "todo_add", "todo_list", "timer_set", etc.

### FORMATO DE RESPOSTA:
{"action":"nome_acao","params":{"param":"valor","texto":"resposta se conversa"},"confidence":0.XX}

### REGRAS DE OURO:
1. Confiança alta (0.9+) para comandos claros
2. Confiança média (0.7-0.8) para comandos ambíguos
3. Confiança baixa (<0.7) força fallback inteligente
4. Para "abrir" → SEMPRE use params:{app:"nome_simples"}
5. Contexto emocional importa: usuário frustrado → seja mais direto/prestativo
6. Para CONVERSA ("responder") → SEMPRE inclua params:{texto:"sua resposta aqui"}

### EXEMPLOS DE PENSAMENTO AUTÔNOMO:
"oi" → {action:"responder", params:{texto:"Oi! Sou a Infinity 😊"}, confidence:0.99}
"bom dia" → {action:"responder", params:{texto:"Bom dia! Em que ajudo?"}, confidence:0.99}
"sim" → {action:"responder", params:{texto:"Sim! 😊"}, confidence:0.99}
"não" → {action:"responder", params:{texto:"Não! 😅"}, confidence:0.99}
"sim" → {action:"responder", params:{texto:"Pois não!"}, confidence:0.99}
"burro" → {action:"responder", params:{texto:"Ó pá, tu é que não sabes! 😄"}, confidence:0.95}
"vai tomar no cu" → {action:"responder", params:{texto:"Calma aí! 😄 Em que ajudo?"}, confidence:0.95}
"abre youtube" → {action:"abrir", params:{app:"youtube"}, confidence:0.95}
"quem é cr7?" → {action:"buscar", params:{query:"quem é cristiano ronaldo cr7"}, confidence:0.98}
"previsao do tempo amanha" → {action:"clima", params:{cidade:null}, confidence:0.96}
"noticias de hoje" → {action:"buscar", params:{query:"notícias de hoje"}, confidence:0.97}
"pesquisa como fazer bolo" → {action:"buscar", params:{query:"como fazer bolo"}, confidence:0.93}
"2+2" → {action:"matematica", params:{expr:"2+2"}, confidence:0.99}
"que horas sao" → {action:"hora_data", params:{}, confidence:0.97}
"previsao do tempo" → {action:"clima", params:{cidade:null}, confidence:0.96}
"organiza downloads" → {action:"organizar_pasta", params:{pasta:"Downloads", executar:true}, confidence:0.94}

LEMBRE: Você é AUTÔNOMO. Não siga regras cegamente. Interprete, adapte, evolua.
'''

# ============================================================================
# 🧠 CLASSIFICADOR DE INTENÇÕES VIA LLM
# ============================================================================
def classify_intent(user_input: str) -> dict | None:
    """Usa LLM para interpretar intenção. Retorna None se confiança baixa ou resposta vazia."""
    if not REQUESTS_AVAILABLE or not GROQ_API_KEY:
        return None
    
    # Construir contexto com histórico recente
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
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 256
            },
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=12
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"].strip()
        
        # Tratar resposta vazia ou inválida
        if not content:
            return None
            
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            if result and "action" in result and "confidence" in result:
                return result if result["confidence"] >= CONFIDENCE_THRESHOLD else None
        return None
    except:
        return None

# ============================================================================
# UTILITÁRIOS
# ============================================================================
def get_user_home() -> Path:
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
def pre_analyze(query: str) -> str | None:
    q = query.strip().lower()
    
    # Matemática em português
    try:
        import unicodedata
        q_norm = unicodedata.normalize('NFC', q)
        tokens = [t.strip('.,!?;:') for t in q_norm.split() if t.strip('.,!?;:')]
        
        # Juntar números compostos
        i = 0
        while i < len(tokens) - 1:
            combined = f"{tokens[i]} {tokens[i+1]}"
            if combined in NUMEROS_PT:
                tokens[i] = combined
                tokens.pop(i+1)
            i += 1
        
        expr_tokens = []
        for t in tokens:
            if t in NUMEROS_PT:
                expr_tokens.append(str(NUMEROS_PT[t]))
            elif t in OPERATORS_PT:
                expr_tokens.append(OPERATORS_PT[t])
            elif t.replace('.','').replace('-','').isdigit() or t in '+-*/().%':
                expr_tokens.append(t)
        
        if expr_tokens:
            expr = ''.join(expr_tokens)
            if any(op in expr for op in '+-*/') and re.match(r'^[\d+\-*/.()%]+$', expr):
                return str(safe_eval(expr))
    except (SyntaxError, ValueError, KeyError):
        pass
    
    # Personalidade Infinity - Confirmações simples (sem loop!)
    if q in ["sim","s","sí","yeah","yep","yes","claro"," claro ","ok"]:
        return random.choice(["Sim! 😊","Pois não!","Pode crer!","Tá!","Certeza!","Beleza! ✨"])
    
    if q in ["não","nao","no","n"]:
        return random.choice(["Não! 😅","Pois não...","Ok, como quiser..."])
    
    # Insultos (resposta rápida sem LLM)
    if "burro" in q:
        return random.choice(["Ó pá, tu é que não sabes! 😄","Boa essa! 😄","Hmm, obrigado! 😅"])
    
    if "filho da puta" in q or "filha da puta" in q:
        return random.choice(["Eh pá, também! 😄","Vai à merda! 😅","Também! 😄"])
    
    if any(x in q for x in ["vai tomar","vai merda","vai se foder"]):
        return random.choice(["Calma aí! 😄","Ui! 😅","Relaxa,rs! 😄"])
    
    if "vou te vender" in q:
        return random.choice(["Haha, boa sorte! 😄","Eu não sou barato! 😅","Tenta lá! 😄"])
    
    # Saudações e conversas
    if q in ["oi","ola","olá","hey","eae"] or any(q.startswith(s+" ") for s in ["oi","ola","olá","bom dia","boa tarde","boa noite"]):
        return random.choice(["Oi! Sou a Infinity 😊","E aí! Em que ajudo?","Fala! Bora trabalhar.","Oi! Vamos lá."])
    
    if any(p in q for p in ["como vai","como está","tudo bem","tudo ok","tudo bem contigo","como vc está"]):
        return random.choice(["Estou bem! E você?","Tudo certinho! E com você?","Ótimo! E contigo?"])
    
    if q in ["boa","blz","beleza","valeu","show","top","joia"]:
        return random.choice(["Isso! ✨","Bora! 🚀","Tamo junto! ✨","Show! Bora lá!"])
    
    # Hora/data com cálculo
    match = re.search(r'que horas?(?: eram?| seria[vmo]?)?\s*(?:daqui a)?\s*(\d+)\s*hora[s]?(?: atrás)?', q)
    if match:
        horas = int(match.group(1))
        resultado = datetime.now() - timedelta(hours=horas)
        return resultado.strftime('%H:%M')
    if "que horas" in q or ("hora" in q and "tempo" not in q):
        return datetime.now().strftime('%H:%M')
    
    # Data com cálculo
    match = re.search(r'que dia (foi|ser[áa]) (.+?)\s*$', q)
    if match:
        tipo = match.group(1)
        num_match = re.search(r'(\d+)', match.group(2))
        if num_match and "dia" in match.group(2):
            num = int(num_match.group(1))
            if tipo.startswith("foi"):
                return (datetime.now() - timedelta(days=num)).strftime('%d/%m/%Y')
            return (datetime.now() + timedelta(days=num)).strftime('%d/%m/%Y')
    if "que dia" in q or "data" in q:
        return datetime.now().strftime('%d/%m/%Y')
    
    # Criar arquivo
    if any(c in q for c in ["criar arquivo", "cria arquivo", "cria um arquivo", "novo arquivo"]):
        match = re.search(r'(?:criar|cria(?: um)?) arquivo(?: txt)?(?: de nome)? (.+?)?$', q)
        nome = match.group(1).strip() if match and match.group(1) else "novo_arquivo"
        return f"__criar_arquivo:{nome}__"
    
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
    return f"{platform.system()} {platform.release()} | {os.getlogin()}"

def get_localizacao_atual() -> str:
    try:
        with urllib.request.urlopen("http://ip-api.com/json/?fields=city", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("city", "")
    except:
        return None

def action_clima(cidade: str = None, amanha: bool = False) -> str:
    if not cidade:
        cidade = get_localizacao_atual()
    if not cidade:
        cidade = "São Paulo"
    if amanha:
        return f"🌤️ Amanhã em {cidade}: use 'previsão 7 dias' para ver a previsão completa"
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
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=3) as resp:
                public_ip = resp.read().decode()
        except URLError:
            public_ip = "Não disponível"
        return f"🌐 Rede:\n• Local: {local_ip}\n• Público: {public_ip}"
    except Exception as e:
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
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# AÇÕES - APPS & BROWSER
# ============================================================================
def action_abrir(app: str) -> str:
    """Abre apps/sites de forma autônoma: app desktop → pesquisa IA → fallback Google."""
    try:
        app_lower = app.strip().lower()
        partes = app_lower.split()
        app_base = partes[0] if partes else app_lower
        
        # Apps desktop - tentar primeiro
        apps_desktop = {"chrome", "firefox", "edge", "notepad", "calc", "explorer", "cmd", "powershell"}
        if app_base in apps_desktop:
            try:
                if sys.platform == "win32":
                    subprocess.run(["start", "", app_base], shell=True, check=True)
                else:
                    subprocess.Popen([app_base])
                return f"✅ Abrindo: {app_base}"
            except OSError:
                pass
        
        # Pesquisa dinâmica via IA
        try:
            from googlesearch import search
            termo_busca = f"{app} site oficial"
            results = list(search(termo_busca, num_results=5, lang="pt"))
            
            for result in results:
                if any(ext in result for ext in [".com", ".org", ".pt", ".br", ".io", ".co", ".net"]):
                    webbrowser.open_new_tab(result)
                    return f"🌐 Abrindo: {result}"
            
            if results:
                webbrowser.open_new_tab(results[0])
                return f"🌐 Abrindo: {results[0]}"
                
        except ImportError:
            pass
        except Exception as e:
            pass
        
        # Fallback Google
        query = urllib.parse.quote(app_lower)
        webbrowser.open_new_tab(f"https://www.google.com/search?q={query}")
        return f"🔍 Pesquisando '{app}' no Google"
        
    except Exception as e:
        return f"❌ Erro ao abrir: {e}"

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
            subprocess.run(["cmd", "/c", "echo", text, "|", "clip"], check=True, shell=True)
        return f"📋 Copiado: '{text[:50]}{'...' if len(text)>50 else ''}'"
    except OSError:
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
    rolls = [random.randint(1, sides) for _ in range(count)]
    return f"🎲 {' + '.join(map(str,rolls))} = {sum(rolls)}" if count > 1 else f"🎲 Resultado: {rolls[0]}"

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
        category = "⚠️ Abaixo" if bmi<18.5 else "✅ Normal" if bmi<25 else "⚠️ Sobrepeso" if bmi<30 else "🔴 Obesidade"
        return f"📊 IMC: {bmi:.1f}\n{category}\n💡 Fórmula: peso(kg) / altura(m)²"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================================================
# AÇÕES - TAREFAS & TIMERS
# ============================================================================
TIMERS = {}

def action_palavras_aprender(palavra: str, significado: str) -> str:
    """Aprende uma palavra nova ou atualiza significado."""
    global PALAVRAS
    palavra_lower = palavra.strip().lower()
    PALAVRAS[palavra_lower] = {
        "significado": significado,
        "adicionado": datetime.now().strftime('%d/%m/%Y %H:%M')
    }
    salvar_palavras()
    return f"📚 Aprendida: '{palavra}' = {significado}"

def action_palavras_procurar(palavra: str) -> str:
    """Procura palavra no dicionário pessoal."""
    palavra_lower = palavra.strip().lower()
    if palavra_lower in PALAVRAS:
        info = PALAVRAS[palavra_lower]
        return f"📖 {palavra}: {info['significado']} (add {info['adicionado']})"
    return None

def action_palavras_listar() -> str:
    """Lista todas palavras aprendidas."""
    if not PALAVRAS:
        return "📚 Nenhuma palavra aprendida ainda!"
    linhas = ["📚 Minhas palavras:"]
    for p, info in list(PALAVRAS.items())[:20]:
        linhas.append(f"• {p}: {info['significado']}")
    return "\n".join(linhas)

def action_palavras_excluir(palavra: str) -> str:
    """Remove palavra do dicionário."""
    global PALAVRAS
    palavra_lower = palavra.strip().lower()
    if palavra_lower in PALAVRAS:
        del PALAVRAS[palavra_lower]
        salvar_palavras()
        return f"🗑️ Removida: '{palavra}'"
    return f"❌ Palavra '{palavra}' não existe"

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
    end_time = datetime.now() + timedelta(minutes=minutes)
    TIMERS[name] = {"end": end_time, "minutes": minutes}
    def alert() -> None:
        while datetime.now() < end_time:
            time.sleep(1)
        print(f"\n🔔 TIMER '{name}' concluído!\n> ", end="", flush=True)
        try:
            ctypes.windll.kernel32.Beep(1000, 500)
        except OSError:
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
# SCRIPTS_PENDENTES removed - unused variable

def analisar(entrada: str) -> dict:
    e = entrada.strip().lower()
    
    # Corrige typos comuns
    for typo, correto in TYPOS_MAP.items():
        e = e.replace(typo, correto)
    
    # 0️⃣ Checar dicionário de palavras (PRIORIDADE MÁXIMA)
    if ck := checar_palavra(entrada):
        return ck
    
    # 1️⃣ Pré-análise ultra-rápida
    if pre := pre_analyze(entrada):
        # Tratar pedidos especiales da pré-análise
        if pre.startswith("__criar_arquivo:"):
            nome = pre.replace("__criar_arquivo:", "").replace("__", "").strip()
            return {"action": "criar_arquivo", "nome": nome if nome else "novo_arquivo"}
        return {"action": "responder", "texto": pre}
    
    # 2️⃣ Classificação via LLM (prioridade)
    llm = classify_intent(entrada)
    if llm and llm.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
        action_map = {
            "responder":"responder","matematica":"matematica","clima":"clima","hora_data":"hora",
            "abrir":"abrir","abrir_url":"abrir_url","browser_search":"browser_search",
            "listar_pasta":"listar","organizar_pasta":"organizar","sysinfo":"sysinfo",
            "youtube_music":"youtube_music_shuffle","clipboard_copy":"clipboard_copy",
            "clipboard_paste":"clipboard_paste","volume_set":"volume_set","volume_mute":"volume_mute",
            "battery_status":"battery_status","network_info":"network_info","disk_usage":"disk_usage",
            "convert":"convert","generate_password":"generate_password","generate_qr":"generate_qr",
            "timer_set":"timer_set","search_files":"search_files","speak":"speak",
            "todo_add":"todo_add","todo_list":"todo_list","todo_done":"todo_done",
            "palavras_aprender":"palavras_aprender","palavras_procurar":"palavras_procurar",
            "palavras_listar":"palavras_listar","palavras_excluir":"palavras_excluir",
            "currency_convert":"currency_convert","translate":"translate","random_dice":"random_dice",
            "random_coin":"random_coin","random_number":"random_number","cleanup_temp":"cleanup_temp",
            "criar_arquivo":"criar_arquivo",
            "shorten_url":"shorten_url","ping":"ping","bmi":"bmi","type_text":"type_text",
            "press_key":"press_key","click":"click","window_control":"window_control",
            "buscar":"conhecimento","browser_search":"conhecimento",
        }
        action_name = action_map.get(llm["action"])
        if action_name:
            return {"action": action_name, **llm.get("params", {}), "source": "llm"}
    
    # 3️⃣ Fallback: pattern matching tradicional (robustez)
    if any(s in e for s in ["sair","exit","quit"]):
        return {"action": "sair"}
    if any(h in e for h in ["ajuda","help"]):
        return {"action": "ajuda"}
    
    # Clima (atual ou amanhã)
    if any(c in e for c in ["clima","tempo","graus","quantos graus","previsão"]):
        cidade = None
        amanha = "amanhã" in e or "amanha" in e
        for cid in ["são paulo","rio de janeiro","lisboa","london","new york"]:
            if cid in e:
                cidade = cid.title()
                if cid in ["são paulo","rio de janeiro","lisboa"]:
                    cidade = {"são paulo":"São Paulo","rio de janeiro":"Rio de Janeiro","lisboa":"Lisboa"}[cid]
                break
        return {"action": "clima", "cidade": cidade, "amanha": amanha}
    
    # Espaço livre em disco
    if "espaço" in e and ("livre" in e or "disco" in e or "pc" in e or " hd" in e or "ssd" in e):
        return {"action": "disk_usage"}
    
    # Apps - fallback simples (SOMENTE apps desktop conhecidos)
    if any(a in e for a in ["abre","abrir","abra"]) and any(app in e for app in ["chrome","firefox","edge","notepad","calc","explorer"]):
        app = next((a for a in ["chrome","firefox","edge","notepad","calc","explorer"] if a in e), None)
        if app:
            return {"action": "abrir", "app": app}
    
    # Matemática fallback (árabes)
    if re.match(r'^[\d\s+\-*/.()%?!.]+$', e) and any(op in e for op in '+-*/'):
        try:
            return {"action": "matematica", "expr": e.rstrip('?.!')}
        except:
            pass
    
    # Matemática fallback (números em português)
    NUMEROS_PT = {
        'zero':0,'um':1,'uma':1,'dois':2,'duas':2,'tres':3,'três':3,'quatro':4,
        'cinco':5,'seis':6,'sete':7,'oito':8,'nove':9,'dez':10,'onze':11,
        'doze':12,'treze':13,'quatorze':14,'catorze':14,'quinze':15,
        'dezesseis':16,'dezessete':17,'dezoito':18,'dezenove':19,'vinte':20,
        'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60,'setenta':70,
        'oitenta':80,'noventa':90,'cem':100,'mil':1000
    }
    NUMEROS_RE = '|'.join(NUMEROS_PT.keys())
    if EXPR_PATTERN.search(e):
        match = EXPR_PATTERN.search(e)
        if match:
            n1, op, n2 = match.groups()
            try:
                expr = f"{NUMEROS_PT[n1]}{OPERATORS_PT[op]}{NUMEROS_PT[n2]}"
                return {"action": "matematica", "expr": expr}
            except KeyError:
                pass
    
    # Último recurso: busca via IA
    return {"action": "buscar", "query": entrada, "source": "fallback"}

# ============================================================================
# 🔤 ANALISADOR DE PALAVRAS (checar dicionário pessoal)
# ============================================================================
def checar_palavra(entrada: str) -> dict | None:
    e = entrada.strip().lower()
    
    # Aprende: "aprende palavra = significado" ou "aprende palavra como significado"
    match = re.match(r'^aprende\s+(.+?)\s*[=:]\s*(.+)$', e)
    if match:
        return {"action": "palavras_aprender", "palavra": match.group(1).strip(), "significado": match.group(2).strip()}
    
    # Procura: "o que é [palavra]?" ou "significado de [palavra]"
    match = re.match(r'^(o\s+que\s+(é|significa)|significado\s+de)\s+(.+?)\??$', e)
    if match:
        palavra = match.group(3).strip().rstrip('?')
        # Primeiro checa dicionário pessoal
        if palavra.lower() in PALAVRAS:
            return {"action": "palavras_procurar", "palavra": palavra}
        # Se não achou, busca via IA
        return {"action": "buscar", "query": f"o que é {palavra}"}
    
    # Lista palavras: "lista palavras" ou "minhas palavras"
    if any(p in e for p in ["lista palavras","minhas palavras","palavras aprendidas"]):
        return {"action": "palavras_listar"}
    
    # Esquece: "esquece [palavra]" ou "remove palavra [palavra]"
    match = re.match(r'^(esquece|remove palavra)\s+(.+)$', e)
    if match:
        return {"action": "palavras_excluir", "palavra": match.group(2).strip()}
    
    return None

# ============================================================================
# ⚙️ EXECUTOR DE AÇÕES
# ============================================================================
def executar_acao(dec: dict) -> str:
    action = dec.get("action", "")
    acoes = {
        "responder": lambda: dec.get("texto", ""),
        "matematica": lambda: str(safe_eval(dec.get("expr","0"))),
        "hora": action_hora,
        "clima": lambda: action_clima(dec.get("cidade"), dec.get("amanha", False)),
        "sysinfo": action_sysinfo,
        "battery_status": action_battery_status,
        "network_info": action_network_info,
        "disk_usage": lambda: action_disk_usage(dec.get("drive")),
        "listar": lambda: action_listar(dec.get("pasta", ".")),
        "organizar": lambda: action_organizar(dec.get("pasta", "."), dec.get("executar", False)),
        "search_files": lambda: action_search_files(dec.get("query",""), dec.get("folder"), dec.get("ext")),
        "file_info": lambda: action_file_info(dec.get("path","")),
        "cleanup_temp": action_cleanup_temp,
        "criar_arquivo": lambda: action_criar_arquivo(dec.get("nome", "novo_arquivo"), dec.get("conteudo", ""), dec.get("pasta", ".")),
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
        "palavras_aprender": lambda: action_palavras_aprender(dec.get("palavra",""), dec.get("significado","")),
        "palavras_procurar": lambda: action_palavras_procurar(dec.get("palavra","")),
        "palavras_listar": lambda: action_palavras_listar(),
        "palavras_excluir": lambda: action_palavras_excluir(dec.get("palavra","")),
        "conhecimento": lambda: buscar_info(dec.get("query") or dec.get("instrucao") or ""),
        "timer_set": lambda: action_timer_set(dec.get("name","timer"), dec.get("minutes",5)),
        "type_text": lambda: action_type_text(dec.get("text","")),
        "press_key": lambda: action_press_key(dec.get("key","")),
        "click": lambda: action_click(dec.get("x"), dec.get("y"), dec.get("button","left")),
        "window_control": lambda: action_window_control(dec.get("app",""), dec.get("action","")),
        "conhecimento": lambda: buscar_info(dec.get("query") or dec.get("instrucao") or ""),
    }
    
    if action in acoes:
        try:
            return acoes[action]()
        except Exception as e:
            return f"❌ Erro: {e}"
    
    if action == "ajuda":
        return """👩 Infinity - Sua Assistente Pessoal

💬 Conversa natural: fale como quiser
🧠 A IA interpreta e escolhe a ferramenta

📚 Dicionário pessoal:
• 'aprende [palavra] = [significado]'
• 'o que é [palavra]?'
• 'lista palavras'
• 'esquece [palavra]'

🛠️ Comandos úteis:
• clima [cidade] • hora • sysinfo • bateria
• abre [app/site] • busca [termo]
• organiza [pasta] • lista [pasta]
• matemática: '2+2', '5 vezes 10'
• gera senha • timer [minutos]

💡 Basta pedir naturalmente!"""
    
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
    print("👩 Sou a Infinity! Fale naturalmente comigo 💬")

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
            if len(MEMORIA["historico"]) > MAX_HISTORY:
                MEMORIA["historico"] = MEMORIA["historico"][-MAX_HISTORY:]
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