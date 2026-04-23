import requests
import json
import re
import os
import ctypes
import subprocess
import shutil
import math
import random
from datetime import datetime
from pathlib import Path
from collections import defaultdict

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
GROQ_API_KEY = "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"  #Sua key

# ═════════════════════════════════════════════════════════════
# CONTEXTO DE SESSAO (Memoria)
# ═════════════════════════════════════════════════════════════

class SessionContext:
    def __init__(self):
        self.historico = []
        self.variaveis_pessoais = {}
        self.ultima_pasta = None
        
    def adicionar(self, entrada: str, decisao: dict, resposta: str):
        self.historico.append({
            "ent": entrada[:50],
            "dec": decisao.get("action", decisao.get("local_function", "unknown")),
            "res": resposta[:100] if resposta else ""
        })
        if len(self.historico) > 10:
            self._resumir_contexto()
    
    def _resumir_contexto(self):
        """Se histórico >= 10, resumir via Groq."""
        if len(self.historico) < 10:
            return
        historico_str = "\n".join([f"{i+1}. {h['ent']} -> {h['dec']}" for i, h in enumerate(self.historico)])
        prompt = f"""Resuma este histórico de conversa em até 5 linhas, mantendo informações importantes:
{historico_str}

Resuma:"""
        try:
            resumo = call_groq(prompt)
            self.historico = [{"ent": "RESUMO", "dec": "contexto_resumido", "res": resumo[:200]}]
        except:
            self.historico = self.historico[-5:]
    
    def salvar_variavel(self, chave: str, valor):
        self.variaveis_pessoais[chave] = valor
    
    def formatar(self) -> str:
        if not self.historico:
            return "Nenhuma interação anterior."
        linhas = [f"{i+1}. {h['ent']} -> {h['dec']}" for i, h in enumerate(self.historico[-5:])]
        return "\n".join(linhas)
    
    def formatar_variaveis(self) -> str:
        if not self.variaveis_pessoais:
            return "Nenhuma variável salva."
        return ", ".join([f"{k}={v}" for k, v in self.variaveis_pessoais.items()])

contexto_global = SessionContext()

# ═════════════════════════════════════════════════════════════
# PRE-ANALISE TRIVIAL (sem IA)
# ═════════════════════════════════════════════════════════════

def pre_analyze_query(query: str) -> dict | None:
    q = query.strip().lower()
    
    # Saudação com humor e carisma
    saudacoes = ["oi", "ola", "bom dia", "boa tarde", "boa noite", "hey", "hello"]
    if any(saudacao in q for saudacao in saudacoes):
        respostas = [
            "Oi! Tudo bem? Seus arquivos estão esperando por alguma organização, ou está tudo no lugar hoje?",
            "Opa! Prometo não ficar repetindo 'como posso ajudá-lo?' três vezes antes de realmente ajudar.",
            "E aí! Se você precisa procurar algo nos Downloads ou só quer bater um papo rápido, estou aqui.",
            "Fala sério! Que bom te ver. Posso ajudar a achar aquele documento perdido ou apenas ouvir sua opinião sobre o tempo.",
            "Oi! Não sou daquele tipo de assistente que fica dizendo 'entendi' o tempo todo. O que você precisa?",
            "Bom dia! Espero que sua mesa de trabalho esteja menos bagunçada que a minha costuma ficar depois de umas horas trabalhando.",
            "Boa tarde! Hora perfeita para dar uma organizada naqueles arquivos que se acumularam esta manhã.",
            "Boa noite! Mesmo assim estou aqui - enquanto humanos precisam de descanso, eu estou pronto para ajudar se surgir alguma coisa."
        ]
        # Personalizar resposta baseado no tipo de saudação
        if any(temporal in q for temporal in ["bom dia", "boa tarde", "boa noite"]):
            if "bom dia" in q:
                return {"type": "local_direct", "response": "Bom dia! Espero que sua mesa de trabalho esteja menos bagunçada que a minha costuma ficar depois de umas horas trabalhando."}
            elif "boa tarde" in q:
                return {"type": "local_direct", "response": "Boa tarde! Hora perfeita para dar uma organizada naqueles arquivos que se acumularam esta manhã."}
            elif "boa noite" in q:
                return {"type": "local_direct", "response": "Boa noite! Mesmo assim estou aqui - enquanto humanos precisam de descanso, eu estou pronto para ajudar se surgir alguma coisa."}
        else:
            # Saudação genérica
            return {"type": "local_direct", "response": random.choice([
                "Oi! Tudo bem? Seus arquivos estão esperando por alguma organização, ou está tudo no lugar hoje?",
                "Opa! Prometo não ficar repetindo 'como posso ajudá-lo?' três vezes antes de realmente ajudar.",
                "E aí! Se você precisa procurar algo nos Downloads ou só quer bater um papo rápido, estou aqui.",
                "Fala sério! Que bom te ver. Posso ajudar a achar aquele documento perdido ou apenas ouvir sua opinião sobre o tempo.",
                "Oi! Não sou daquele tipo de assistente que fica dizendo 'entendi' o tempo todo. O que você precisa?"
            ])}
    
    # Matematica
    if re.match(r'^[\d\s\+\-\*/\.\(\)%]+$', q) and any(op in q for op in ['+','-','*','/','%']):
        try:
            result = eval(q, {"__builtins__": {}}, {"math": math, "sqrt": math.sqrt, "pow": pow})
            return {"type": "local_direct", "response": f"Resultado: {result}"}
        except: pass
    
    # Clima/Tempo - NAO tratar aqui, deixar ir para o router (autonomo)
    # O router vai detectar e fazer a busca automaticamente
    
    # Datas - usar regex para evitar ambiguidade com "tempo"
    # Só pega data se NÃO tiver palavras de clima
    if not any(k in q for k in ["tempo", "clima", "chover", "chuva", "sol", "calor", "frio", "temperatura"]):
        if re.search(r'\b(hoje|amanha|ontem)\b', q) or "que dia" in q or "data atual" in q:
            now = datetime.now()
            if re.search(r'\bhoje\b', q) or "que dia" in q:
                return {"type": "local_direct", "response": f"Hoje e {now.strftime('%d/%m/%Y')} ({now.strftime('%A')})"}
            elif re.search(r'\bamanha\b', q):
                tomorrow = datetime.fromtimestamp(now.timestamp() + 86400)
                return {"type": "local_direct", "response": f"Amanha: {tomorrow.strftime('%d/%m/%Y')}"}
    
    # 🔤 Texto
    if q.startswith(("maiuscula ", "minuscula ", "upper ", "lower ")):
        if q.startswith("maiuscula ") or q.startswith("upper "):
            text = query.split(" ", 1)[1].strip(); return {"type": "local_direct", "response": f"{text.upper()}"}
        elif q.startswith("minuscula ") or q.startswith("lower "):
            text = query.split(" ", 1)[1].strip(); return {"type": "local_direct", "response": f"{text.lower()}"}
    
    # ❓ Capacidades
    if any(k in q for k in ["o que você faz", "capacidades", "ajuda", "funções"]):
        return {"type": "local_direct", "response": get_capabilities_help()}
    
    return None

def get_capabilities_help() -> str:
    return """Eu posso ajudar com:
ARQUIVOS: listar, organizar por tipo (Downloads, Documents, Pictures, etc.)
SISTEMA: hora/data, informações do SO, abrir apps
VISUAL: alterar wallpaper (com caminho da imagem)
WEB: buscar no Perplexity
TRIVIAL: cálculos, conversão de texto, datas

Eu NAO posso:
• Acessar internet diretamente • Executar comandos admin sem permissão
• Modificar sistema • Acessar dados sensíveis

Dica: Seja específico! Ex: "liste Downloads" em vez de "meus arquivos".""".strip()

# ═════════════════════════════════════════════════════════════
# 🗂️ UTILITÁRIOS
# ═════════════════════════════════════════════════════════════
FOLDER_ALIASES = {
    "transferencias": "Downloads", "transferência": "Downloads", "downloads": "Downloads",
    "documentos": "Documents", "document": "Documents",
    "imagens": "Pictures", "fotos": "Pictures", "pictures": "Pictures",
    "músicas": "Music", "musicas": "Music",
    "vídeos": "Videos", "videos": "Videos",
    "área de trabalho": "Desktop", "area de trabalho": "Desktop", "desktop": "Desktop",
}

def get_user_home() -> Path: return Path(os.path.expanduser("~"))

def resolve_path(folder: str) -> tuple[Path, bool, str]:
    folder = folder.strip().lower().rstrip('\\/')
    if folder in FOLDER_ALIASES:
        base = get_user_home() / FOLDER_ALIASES[folder]
        return (base, True, "") if base.exists() else (base, False, f"Pasta '{FOLDER_ALIASES[folder]}' não existe")
    for p in [Path(folder).resolve(), get_user_home() / folder]:
        if p.exists(): return p, True, ""
    return Path(folder), False, f"Caminho não encontrado: '{folder}'"

def get_available_folders() -> list[str]:
    home = get_user_home()
    m = {"Downloads":"Transferencias","Documents":"Documentos","Pictures":"Imagens",
         "Music":"Musicas","Videos":"Videos","Desktop":"Area de Trabalho"}
    return [f"{v} -> {k}" for k,v in m.items() if (home/k).exists()]

def build_folder_error(folder: str) -> str:
    avail = get_available_folders()
    return f"Pasta nao encontrada: '{folder}'\n\nDisponiveis:\n" + ("\n".join(avail) or "Nenhuma") + "\n\nDica: Use um nome acima ou caminho completo."

FILE_CATEGORIES = {
    "Imagens": [".jpg",".jpeg",".png",".gif",".bmp",".webp",".heic"],
    "Videos": [".mp4",".mkv",".avi",".mov",".wmv"],
    "Documentos": [".pdf",".doc",".docx",".txt",".ppt",".pptx",".xls",".xlsx"],
    "Audio": [".mp3",".wav",".flac",".aac"],
    "Arquivos": [".zip",".rar",".7z",".tar",".iso"],
    "Instaladores": [".exe",".msi"],
    "Codigo": [".py",".js",".ts",".java",".cpp",".html",".css",".json"],
}
def categorize_file(fn: str) -> str:
    ext = Path(fn).suffix.lower()
    for cat, exts in FILE_CATEGORIES.items():
        if ext in exts: return cat
    return "Outros"

# ═════════════════════════════════════════════════════════════
# 🔧 AÇÕES
# ═════════════════════════════════════════════════════════════

def action_change_wallpaper(path_str: str) -> str:
    try:
        path, ok, err = resolve_path(path_str)
        if not ok: return f"Erro: {err}\nDica: Use 'Downloads\\img.jpg' ou caminho completo."
        if path.suffix.lower() not in ['.jpg','.png','.bmp']: return "Erro: Formato nao suportado."
        ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
        return f"Sucesso: Wallpaper alterado para {path.name}"
    except Exception as e: return f"Erro: {e}"

def action_get_time() -> str:
    n = datetime.now(); return f"Data: {n.strftime('%d/%m/%Y')} | Hora: {n.strftime('%H:%M:%S')}"

def action_get_sysinfo() -> str:
    import platform
    return f"Sistema: {platform.system()} {platform.release()}\nUsuario: {os.getlogin()}\nPasta home: {get_user_home()}".strip()

def action_list_files(folder: str = ".") -> str:
    path, ok, err = resolve_path(folder)
    if not ok: return build_folder_error(folder)
    try:
        print(f"Analisando: {path}")
        files = [f.name for f in path.iterdir() if f.is_file()][:25]
        dirs = [f"{d.name}/" for d in path.iterdir() if d.is_dir()][:5]
        r = f"{path.name} ({len(files)} arquivos" + (f", {len(dirs)} pastas" if dirs else "") + "):\n"
        r += "\n".join(f"- {x}" for x in files) if files else "- (vazia)"
        if dirs: r += f"\n\nSubpastas:\n" + "\n".join(f"- {x}" for x in dirs)
        return r
    except PermissionError: return f"Permissao negada: {path}\nDica: Execute como Admin"
    except Exception as e: return f"Erro: {e}"

def action_organize(folder: str = ".", dry: bool = True) -> str:
    path, ok, err = resolve_path(folder)
    if not ok: return build_folder_error(folder)
    try:
        print(f"Analisando: {path}")
        grouped = defaultdict(list)
        for f in path.iterdir():
            if f.is_file() and not f.name.startswith('.'): grouped[categorize_file(f.name)].append(f.name)
        if not grouped: return "Pasta vazia ou sem arquivos organizaveis."
        lines = [f"{'PREVIA' if dry else 'ORGANIZANDO'}: {path.name}"]
        total = 0
        for cat in sorted(grouped):
            items = grouped[cat]; lines.append(f"{cat} ({len(items)}):")
            for x in items[:8]: lines.append(f"  - {x}")
            if len(items)>8: lines.append(f"  ... +{len(items)-8}")
            total += len(items)
        if dry:
            lines.append(f"Dica: {total} arquivos. Diga 'organize de verdade' para executar.")
        else:
            moved = 0
            for cat, items in grouped.items():
                tgt = path / cat; tgt.mkdir(exist_ok=True)
                for fn in items:
                    try:
                        src, dst = path/fn, tgt/fn
                        if dst.exists():
                            b,e = os.path.splitext(fn); dst = tgt/f"{b}_{moved}{e}"
                        shutil.move(str(src), str(dst)); moved+=1
                    except Exception as ex: lines.append(f"Aviso {fn}: {ex}")
            lines.append(f"Concluido: {moved}/{total} arquivos organizados em {len(grouped)} pastas.")
        return "\n".join(lines)
    except Exception as e: return f"❌ {e}"

def action_open_app(app: str) -> str:
    try: subprocess.Popen([app], shell=True); return f"Abrindo: {app}"
    except Exception as e: return f"Erro: {e}"

def action_search_web(q: str) -> str:
    import webbrowser; webbrowser.open(f"https://www.perplexity.ai/search?q={q}"); return f"Buscando: '{q}'"

def action_search_groq(q: str) -> str:
    """Busca informacoes via Groq (IA online)."""
    try:
        resposta = call_groq(f"Responda de forma concisa e útil: {q}")
        return resposta
    except Exception as e:
        return f"Erro ao buscar: {e}"

def action_weather(q: str) -> str:
    """Busca clima via OpenWeatherMap API."""
    import urllib.request
    import urllib.parse
    import json
    
    API_KEY = "df02e5bf3be213be62bdf906028563aa"
    
    # Detectar se é previsão ou clima atual
    q_lower = q.lower()
    
    # Tentar extrair cidade ou usar localização padrão
    # Se mencionar "amanhã" ou "previsão", buscar previsão
    if "amanha" in q_lower or "previsao" in q_lower or "forecast" in q_lower:
        # Previsão 5 dias
        url = f"https://api.openweathermap.org/data/2.5/forecast?q=London&appid={API_KEY}&lang=pt"
    else:
        # Clima atual
        url = f"https://api.openweathermap.org/data/2.5/weather?q=London&appid={API_KEY}&lang=pt"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if "list" in data:  # Previsão
                temps = [item["main"]["temp"] for item in data["list"][:8]]
                temp_min = min(temps)
                temp_max = max(temps)
                desc = data["list"][0]["weather"][0]["description"]
                return f"Previsao para Londres:\nMin: {temp_min-273.15:.1f}°C\nMax: {temp_max-273.15:.1f}°C\n{desc}"
            else:  # Atual
                temp = data["main"]["temp"] - 273.15
                feels = data["main"]["feels_like"] - 273.15
                desc = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                return f"Clima em Londres:\nTemperatura: {temp:.1f}°C\nSensacao: {feels:.1f}°C\nUmidade: {humidity}%\nCondicao: {desc}"
    except Exception as e:
        return f"Erro ao buscar clima: {e}"

def responder_sim(confirmacao: str = "sim") -> str:
    """Responde positivamente a uma confirmacao."""
    return "Ok, feito!"

def responder_nao() -> str:
    """Responde negativamente."""
    return "Ok, sem problemas."

def action_reject(reason: str, sugs: list) -> str:
    msg = f"Nao consigo ajudar.\n\nMotivo: {reason}\n\nSugestoes:"
    for i,s in enumerate(sugs,1): msg += f"\n{i}. {s}"
    return msg

def responder_direto(texto: str) -> str:
    """Responde texto livre diretamente."""
    return texto

def perguntar_usuario(pergunta: str, opcoes: list = None) -> str:
    """Formula pergunta ao usuário."""
    if opcoes:
        opts = " | ".join(opcoes)
        return f"{pergunta}\n\nOpções: [{opts}]"
    return pergunta

def action_save_variable(chave: str, valor) -> str:
    """Salva variável pessoal no contexto."""
    contexto_global.salvar_variavel(chave, valor)
    return f"Ok, anotei: {chave} = {valor}"

LOCAL_ACTIONS = {
    "change_wallpaper": {"func": action_change_wallpaper, "desc": "Altera wallpaper. Ex: 'Downloads\\fundo.jpg'"},
    "get_time": {"func": action_get_time, "desc": "Data/hora atual."},
    "get_system_info": {"func": action_get_sysinfo, "desc": "Info do SO e usuário."},
    "list_files": {"func": action_list_files, "desc": "Lista arquivos. Use: Downloads, Documents, etc."},
    "organize_files": {"func": action_organize, "desc": "Organiza por tipo. Params: folder, dry_run"},
    "open_app": {"func": action_open_app, "desc": "Abre app: notepad, calc, explorer"},
    "search_web": {"func": action_search_web, "desc": "Busca no Perplexity"},
    "search_groq": {"func": action_search_groq, "desc": "Busca via IA Groq"},
    "weather": {"func": action_weather, "desc": "Busca clima via OpenWeatherMap"},
    "responder_direto": {"func": responder_direto, "desc": "Responde texto livre."},
    "perguntar_usuario": {"func": perguntar_usuario, "desc": "Pergunta ao usuário."},
    "responder_sim": {"func": responder_sim, "desc": "Responde SIM a uma confirmacao."},
    "responder_nao": {"func": responder_nao, "desc": "Responde NAO a uma confirmacao."},
    "save_variable": {"func": action_save_variable, "desc": "Salva variável pessoal."},
    "reject": {"func": action_reject, "desc": "Recusa fora do escopo."},
}

# ═════════════════════════════════════════════════════════════
# 🧠 ROUTER ROBUSTO
# ═════════════════════════════════════════════════════════════

def router_analyze(user_input: str, contexto: SessionContext = None) -> dict:
    actions = "\n".join(f"- {k}: {v['desc']}" for k,v in LOCAL_ACTIONS.items())
    historico = contexto.formatar() if contexto else "Nenhuma interação anterior."
    variaveis = contexto.formatar_variaveis() if contexto else "Nenhuma variável salva."
    
    prompt = f"""Você é um assistente local COMPLETAMENTE AUTÔNOMO.
Decisões automáticas, SEM perguntar confirmação.

CHECKLIST DE DECISÃO:
1. Classifique: ação | pergunta | bate-papo | crítica | fora de escopo
2. Se ação → execute imediatamente (infira parâmetros se necessário)
3. Se pergunta → responda diretamente ou use ação disponível
4. Se falta info → infira OU pergunte ao usuário
5. Jamais rejeite entradas casuais ou saudações

CONTEXTO ANTERIOR:
{historico}

VARIÁVEIS PESSOAIS:
{variaveis}

AÇÕES DISPONÍVEIS:
{actions}

REGRAS:
- Responda saudações com humor natural (não rejeite)
- Inferir parâmetros é normal e desejável
- Se não souber algo → PERGUNTE ao usuário (não envie para outra IA)
- Nunca diga "não sei" sem sugerir algo

EXEMPLOS:
"oi" → action="responder_direto", params={{"texto":"Oi! Tudo bem?"}}
"lista downloads" → action="list_files", params={{"folder":"Downloads"}}
"que horas sao" → action="get_time", params={{}}
"organiza Downloads" → action="organize_files", params={{"folder":"Downloads","dry":true}}

Entrada: {user_input}
JSON:"""
    try:
        res = requests.post(LM_STUDIO_URL, json={"model":"local-model","messages":[{"role":"user","content":prompt}],"temperature":0.3,"max_tokens":256}, timeout=15)
        raw = res.json()["choices"][0]["message"]["content"].strip()
        # Extract JSON from response - find first { and last }
        start_idx = raw.find('{')
        end_idx = raw.rfind('}') + 1
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            raw = raw[start_idx:end_idx]
        # Sanitizar JSON: aspas simples para duplas
        raw = raw.replace("'", '"')
        dec = json.loads(raw)
        if "action" not in dec: raise ValueError("JSON sem 'action'")
        
        # VALIDACAO: Corrigir erros comuns do LM Studio
        # Se ele retornar save_variable para respostas simples, corrigir
        ui_lower = user_input.strip().lower()
        if dec.get("action") == "save_variable" and "name" in dec.get("params", {}):
            if ui_lower in ["sim", "s", "yes", "y", "ok", "okay", "claro", "certo"]:
                return {"action": "responder_sim", "params": {}, "reasoning": "Corrigido save_variable para responder_sim (afirmacao)"}
            elif ui_lower in ["nao", "n", "no", "nah", "nao thanks", "negativo"]:
                return {"action": "responder_nao", "params": {}, "reasoning": "Corrigido save_variable para responder_nao (negacao)"}
        
        # AUTONOMIA: Se a entrada for sobre clima/tempo, FORCAR busca via OpenWeatherMap
        # Ignorar o que o LM Studio decidiu
        if any(k in ui_lower for k in ["tempo", "clima", "temperatura", "chover", "chuva", "sol", "calor", "amanha"]):
            return {"action":"weather","params":{"q":user_input},"reasoning":"Autonomo: buscando clima via OpenWeatherMap"}
        
        # Corrigir perguntar_usuario com parametros errados
        if dec.get("action") == "perguntar_usuario":
            params = dec.get("params", {})
            if "pergunta" not in params and "texto" in params:
                params["pergunta"] = params.pop("texto")
                if "opcoes" not in params:
                    params["opcoes"] = ["sim", "nao"]
                dec["params"] = params
        
        # Corrigir open_app com parametros errados
        if dec.get("action") == "open_app":
            params = dec.get("params", {})
            if "app" not in params:
                # Tentar encontrar o app em qualquer parametro
                for k, v in params.items():
                    if isinstance(v, str):
                        params["app"] = v
                        break
                else:
                    # Se nao encontrar, usar fallback
                    if "notepad" in ui_lower or "bloco" in ui_lower:
                        params["app"] = "notepad"
                    elif "explorer" in ui_lower:
                        params["app"] = "explorer"
                    elif "calculadora" in ui_lower or "calc" in ui_lower:
                        params["app"] = "calc"
        
        return dec
    except Exception as e:
        print(f"Router erro: {e}")
        ui = user_input.lower()
        texto = user_input.strip().lower()
        
        # Detectar respostas simples
        if texto in ["sim", "sim!", "sim.", "ok", "sim, pode", "pode", "va", "sim vai"]:
            return {"action":"responder_sim","params":{},"reasoning":"Usuario confirmou"}
        if texto in ["nao", "nao!", "nao.", "nah", "nao thanks", "negativo"]:
            return {"action":"responder_nao","params":{},"reasoning":"Usuario recusou"}
        
        # Detectar hora - APENAS se nao tiver palavra de clima
        if any(k in ui for k in ["hora", "horas"]) and not any(k in ui for k in ["tempo", "clima", "temperatura", "chover", "chuva", "sol", "calor", "amanha", "hoje"]):
            return {"action":"get_time","params":{},"reasoning":"Pegando hora"}
        
        # Detectar clima - AUTONOMO: usa OpenWeatherMap para buscar diretamente
        if any(k in ui for k in ["tempo", "clima", "temperatura", "chover", "chuva", "sol", "calor", "amanha"]):
            return {"action":"weather","params":{"q":user_input},"reasoning":"Buscando clima via OpenWeatherMap"}
        
        # Detectar analise de arquivo/pasta
        if any(k in ui for k in ["analisa", "ver", "checar", "examina", "olha"]):
            if "arquivo" in ui or "pasta" in ui or "diretorio" in ui or "folder" in ui:
                # Extrair caminho do input
                import re as re2
                match = re2.search(r'[A-Z]:\\[\w\\]+', user_input)
                if match:
                    folder = match.group(0)
                else:
                    # Tentar extrair nome da pasta
                    pastas = ["Downloads", "Documents", "Pictures", "Music", "Videos", "Desktop", "Testes"]
                    for p in pastas:
                        if p.lower() in ui:
                            folder = p
                            break
                    else:
                        folder = "Downloads"
                return {"action":"list_files","params":{"folder":folder},"reasoning":"Listando arquivo/pasta"}
        
        # Detectar organizacao
        if any(k in ui for k in ["organiza", "organizar", "ordena"]):
            pastas = ["Downloads", "Documents", "Pictures", "Music", "Videos", "Desktop"]
            for p in pastas:
                if p.lower() in ui:
                    return {"action":"organize_files","params":{"folder":p,"dry":True},"reasoning":"Organizando"}
            return {"action":"organize_files","params":{"folder":"Downloads","dry":True},"reasoning":"Organizando"}
        
        # Detectar arquivos
        if any(k in ui for k in ["lista", "arquivo", "pasta", "download", "document"]):
            pastas = ["Downloads", "Documents", "Pictures", "Music", "Videos", "Desktop"]
            for p in pastas:
                if p.lower() in ui:
                    return {"action":"list_files","params":{"folder":p},"reasoning":"Listando arquivos"}
            return {"action":"list_files","params":{"folder":"Downloads"},"reasoning":"Listando arquivos"}
        
        # Perguntar ao usuario
        return {"action":"perguntar_usuario","params":{"pergunta":"Nao entendi. O que voce quer fazer?","opcoes":["sim", "nao"]},"reasoning":"Fallback"}

# ═════════════════════════════════════════════════════════════
# 🌐 GROQ
# ═════════════════════════════════════════════════════════════

def call_groq(prompt: str) -> str:
    res = requests.post("https://api.groq.com/openai/v1/chat/completions",
        json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],"temperature":0.2,"max_tokens":1024},
        headers={"Authorization":f"Bearer {GROQ_API_KEY}"}, timeout=30)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"].strip()

# ═════════════════════════════════════════════════════════════
# 🔄 EXECUTOR CORRIGIDO
# ═════════════════════════════════════════════════════════════

# Executor com mapeamento de parametros
PARAM_ALIASES = {
    "change_wallpaper": {"imagePath": "path_str", "image": "path_str", "file": "path_str", "path": "path_str"},
    "list_files": {"pasta": "folder", "diretorio": "folder", "path": "folder"},
    "organize_files": {"pasta": "folder", "diretorio": "folder", "path": "folder", "dry_run": "dry"},
"search_web": {"query": "q", "search": "q", "pergunta": "q"},
    "search_groq": {"query": "q", "search": "q", "pergunta": "q"},
    "weather": {"query": "q", "search": "q", "pergunta": "q", "cidade": "q"},
    "open_app": {"aplicativo": "app", "programa": "app", "appname": "app", "application": "app", "app_name": "app"},
    "save_variable": {"name": "chave", "valor": "valor"},
    "perguntar_usuario": {"texto": "pergunta", "mensagem": "pergunta", "message": "pergunta"},
}

def responder_sim(confirmacao: str) -> str:
    """Responde positivamente a uma confirmacao."""
    return f"Ok, feito!"

def responder_nao() -> str:
    """Responde negativamente."""
    return "Ok, sem problemas."

def normalize_params(action: str, params: dict) -> dict:
    """Normaliza parâmetros de acordo com aliases."""
    normalized = {}
    aliases = PARAM_ALIASES.get(action, {})
    for k, v in params.items():
        new_key = aliases.get(k, k)
        normalized[new_key] = v
    return normalized

def execute_decision(dec: dict, original: str, contexto: SessionContext = None) -> str:
    action = dec.get("action", dec.get("local_function", ""))
    params = dec.get("params", dec.get("local_params", {}))
    resposta_texto = dec.get("resposta", dec.get("response", ""))
    
    if action == "local_direct" and resposta_texto:
        return resposta_texto
    
    # Corrigir acoes Problematicas do modelo
    if action in ["save_variable", "responder_texto", "action_save"]:
        # Se o modelo retornou algo errado, verificar se e uma confirmacao
        texto_lower = original.strip().lower()
        if texto_lower in ["sim", "sim!", "sim.", "ok", "pode", "va"]:
            action = "responder_sim"
            params = {}
        elif texto_lower in ["nao", "nao.", "nah"]:
            action = "responder_nao"
            params = {}
        elif resposta_texto:
            return resposta_texto
    
    if action in LOCAL_ACTIONS:
        try:
            # Normalizar parametros
            params = normalize_params(action, params)
            resultado = LOCAL_ACTIONS[action]["func"](**params)
            if contexto:
                contexto.ultima_pasta = params.get("folder", contexto.ultima_pasta)
            return resultado
        except Exception as e:
            return LOCAL_ACTIONS["perguntar_usuario"]["func"](
                pergunta=f"Algo deu errado: {e}",
                opcoes=["tentar novamente", "mudar parametros", "ajuda"]
            )
    elif resposta_texto:
        return resposta_texto
    else:
        return LOCAL_ACTIONS["perguntar_usuario"]["func"](
            pergunta="Nao sei como fazer isso. Posso ajudar de outra forma?",
            opcoes=["sim, me ajude", "nao, obrigado"]
        )

# ═════════════════════════════════════════════════════════════
# 🎮 MAIN v5.2 AUTÔNOMO
# ═════════════════════════════════════════════════════════════

def main():
    print("Assistente Local Autonomo v5.2 Autonomo")
    print("Pastas: Downloads, Documents, Pictures, Music, Videos, Desktop")
    print("Comando: 'ajuda' para capacidades")
    print("="*65)
    
    contexto = contexto_global
    
    while True:
        try:
            ui = input("\n>>> ").strip()
            if not ui or ui.lower() in ["sair","exit","quit"]:
                print("Ate! ate a proxima."); break
            if ui.lower() in ["ajuda","help","capacidades"]:
                print(get_capabilities_help()); continue
            
            # Camada 0: trivial
            trivial = pre_analyze_query(ui)
            if trivial:
                resposta = trivial['response']
                contexto.adicionar(ui, {"action": "pre_analyze"}, resposta)
                print(resposta); continue
            
            # Camada 1: router com contexto
            print("Analisando...")
            dec = router_analyze(ui, contexto)
            print(f"Raciocinio: {dec.get('reasoning','')}")
            print("Executando...")
            
            resposta = execute_decision(dec, ui, contexto)
            contexto.adicionar(ui, dec, resposta)
            print(resposta)
            
        except KeyboardInterrupt:
            print("\n\nInterrompido."); break
        except Exception as e:
            print(f"\nErro: {e}")

if __name__ == "__main__":
    main()