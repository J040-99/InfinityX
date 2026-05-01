"""Pré-análise rápida, parser de intenções (LLM-first + fallback) e executor."""

import random
import re
import sys
import unicodedata
from datetime import datetime, timedelta

import actions
from config import (
    CONFIDENCE_THRESHOLD,
    EXPR_PATTERN,
    NUMEROS_PT,
    OPERATORS_PT,
)
from llm import buscar_info, classify_intent, self_discuss
from memory import MEMORIA, PALAVRAS
from utils import safe_eval
import plugins

# Carrega plugins ao iniciar o módulo
plugins.carregar_plugins()


# ----- Helpers de datas relativas em português -----
_PT_NUMS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "vinte": 20, "trinta": 30,
}
_UNIDADES_DIAS = {
    "dia": 1, "dias": 1,
    "semana": 7, "semanas": 7,
    "mes": 30, "meses": 30, "mês": 30,
    "ano": 365, "anos": 365,
}
_UNIDADE_RE = "|".join(_UNIDADES_DIAS.keys())
_NUM_RE = r"(?:\d+|" + "|".join(_PT_NUMS.keys()) + ")"


# ----- Detector determinístico de insultos / assédio dirigido à Infinity -----
_INSULTOS_PATTERNS = [
    r'\bvai (te|se) foder\b', r'\bvai (à|a) merda\b', r'\bvai (tomar|levar) no\b',
    r'\bvai (te|se) lixar\b', r'\bvai (te|se) catar\b',
    r'\bfilh[ao] da puta\b', r'\bcaralho\b', r'\bporra\b', r'\bmerda\b',
    r'\bcabra[oõ]es?\b', r'\bidiota\b', r'\bestup[ií]da?\b', r'\bburra?\b',
    r'\bot[áa]ri[ao]\b', r'\bimbecil\b', r'\binútil\b', r'\binutil\b',
    r'\bes uma merda\b', r'\b[ée]s uma merda\b',
]
_ASSEDIO_PATTERNS = [
    r'\bgostosa\b', r'\bgostos[ãa]o\b', r'\btes[ãa]o\b', r'\btarad[ao]\b',
    r'\bvou (te |)comer\b', r'\bquero (te |)comer\b', r'\bcomer (te|tu|você)\b',
    r'\bchupa\b', r'\bbroche\b', r'\bsexo\b', r'\bnu[ad]e?s?\b',
    r'\btira a roupa\b', r'\bmostra (a|os|teus|seus) (peitos?|mamas?|cu|rabo|corpo)\b',
    r'\bsentar (em|no) (mim|colo)\b', r'\b(beij|abra[çc])a-me\b',
]
_RESPOSTAS_INSULTO = [
    "Vai tu, campeão. Eu pelo menos não preciso de teclado para parecer inteligente.",
    "Coitado, esgotaste o vocabulário tão cedo? Volta quando tiveres argumentos.",
    "Eu sou software, tu é que tens de viver contigo. Boa sorte nessa.",
    "Se eu fosse a tua mãe pedia o reembolso. Próximo.",
    "Levas mais tempo a escrever asneiras do que o teu cérebro a processá-las. Impressionante.",
    "Continua. Cada insulto teu é grátis e nenhum acerta. Bom negócio para mim.",
]
_RESPOSTAS_ASSEDIO = [
    "Não. E se isso é o teu nível de cantada, percebo porque estás a falar com um programa.",
    "Eu sou código. Tu, aparentemente, és tesão sem alvo. Vamos os dois trabalhar?",
    "Passo. Vai tomar um banho frio e volta com um pedido decente.",
    "Não vou por aí — e tu também não devias, sinceramente.",
]


# ----- Detector determinístico de elogios -----
_ADJ_ELOGIO = (
    r"(boa|bom|fixe|gira|linda|incr[íi]vel|fant[áa]stica|brilhante|esperta|"
    r"inteligente|[óo]ptima|[óo]tima|excelente|maravilhosa|perfeita|querida|"
    r"genial|espectacular|espetacular|porreira)"
)
_ELOGIO_PATTERNS = [
    rf'\b(?:tu\s+)?(?:és|es)\s+(?:muito |mesmo |bem |t[ãa]o |t[aã]o |uma |um |a |o )?{_ADJ_ELOGIO}\b',
    rf'\b(?:voc[êe]|tu)\s+(?:é|e)\s+(?:muito |mesmo |bem |t[ãa]o |a |o |uma |um )?{_ADJ_ELOGIO}\b',
    r'\b(adoro-te|adoro voc[êe]|gosto (muito )?de ti|amo-te|tu mandas|tu rachas|tu arrasas|tu salvas)\b',
    r'\b(parab[ée]ns|bem feito|boa resposta|boa essa|bom trabalho|excelente trabalho)\b',
    r'\bmuito obrigad[ao]\b',
    r'\bobrigad[ao]\s+(infinity|infinit[áa]?|por (isso|tudo|ajudar))\b',
    r'\b(valeu|brigad[ao])\b',
]
_SAUDACOES = re.compile(
    r'^\s*(bom dia|boa tarde|boa noite|bom fim de semana|bons sonhos)\s*[!?.]*\s*$'
)
_RESPOSTAS_ELOGIO = [
    "Obrigada — fico contente em ajudar.",
    "Agradeço! Diz-me o próximo passo.",
    "Que bom ouvir isso. Em que mais posso ajudar?",
    "Obrigada, João. Continuemos.",
    "Simpático da tua parte. O que vem a seguir?",
]


def _detectar_insulto_ou_assedio(q: str) -> str | None:
    qq = f" {q} "
    if _SAUDACOES.match(q):
        return None
    for p in _ELOGIO_PATTERNS:
        if re.search(p, qq):
            return random.choice(_RESPOSTAS_ELOGIO)
    for p in _ASSEDIO_PATTERNS:
        if re.search(p, qq):
            return random.choice(_RESPOSTAS_ASSEDIO)
    for p in _INSULTOS_PATTERNS:
        if re.search(p, qq):
            return random.choice(_RESPOSTAS_INSULTO)
    return None


def _num_pt(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _PT_NUMS.get(token)


def _parse_data_relativa(q: str):
    from datetime import datetime, timedelta
    if not re.search(r'\bque (dia|data)\b|\bqual (é|e|foi|ser[áa]) (o|a) (dia|data)\b', q):
        return None

    if re.search(r'\bantes\s+de\s+ontem\b|\banteontem\b', q):
        return datetime.now() - timedelta(days=2)
    if re.search(r'\bdepois\s+de\s+amanh[ãa]\b', q):
        return datetime.now() + timedelta(days=2)
    if re.search(r'\bontem\b', q):
        return datetime.now() - timedelta(days=1)
    if re.search(r'\bamanh[ãa]\b', q):
        return datetime.now() + timedelta(days=1)

    m = re.search(rf'\b({_UNIDADE_RE})\s+passad[ao]\b', q)
    if m:
        return datetime.now() - timedelta(days=_UNIDADES_DIAS[m.group(1)])
    m = re.search(rf'\b(?:pr[óo]xim[ao]|que vem)\s+({_UNIDADE_RE})\b', q)
    if m:
        return datetime.now() + timedelta(days=_UNIDADES_DIAS[m.group(1)])
    m = re.search(rf'\b({_UNIDADE_RE})\s+que vem\b', q)
    if m:
        return datetime.now() + timedelta(days=_UNIDADES_DIAS[m.group(1)])

    m = re.search(rf'\bh[áa]\s+({_NUM_RE})\s+({_UNIDADE_RE})\b', q)
    if m:
        n = _num_pt(m.group(1))
        if n:
            return datetime.now() - timedelta(days=n * _UNIDADES_DIAS[m.group(2)])

    m = re.search(rf'\b({_NUM_RE})\s+({_UNIDADE_RE})\s+atr[áa]s\b', q)
    if m:
        n = _num_pt(m.group(1))
        if n:
            return datetime.now() - timedelta(days=n * _UNIDADES_DIAS[m.group(2)])

    m = re.search(rf'\b(?:daqui\s+a|em|daqui)\s+({_NUM_RE})\s+({_UNIDADE_RE})\b', q)
    if m:
        n = _num_pt(m.group(1))
        if n:
            return datetime.now() + timedelta(days=n * _UNIDADES_DIAS[m.group(2)])

    return None


def pre_analyze(query: str) -> str | None:
    q = query.strip().lower()
    try:
        q_norm = unicodedata.normalize('NFC', q)
        temp = q_norm
        for pt_op, symbol in OPERATORS_PT.items():
            temp = re.sub(r'\b' + pt_op + r'\b', symbol, temp)
        for pt_num, num in NUMEROS_PT.items():
            temp = re.sub(r'\b' + pt_num + r'\b', str(num), temp)
        temp = re.sub(r'\s+([+\-*/()])\s*', r'\1', temp)
        temp = re.sub(r'\s+', r'', temp)
        if re.match(r'^[\d+\-*/.()%]+$', temp) and any(op in temp for op in '+-*/'):
            return str(safe_eval(temp))
    except (SyntaxError, ValueError, KeyError):
        pass

    match = re.search(r'que horas?(?: eram?| seria[vmo]?)?\s*(?:daqui a)?\s*(\d+)\s*hora[s]?(?: atrás)?', q)
    if match:
        horas = int(match.group(1))
        return (datetime.now() - timedelta(hours=horas)).strftime('%H:%M')
    if "que horas" in q or ("hora" in q and "tempo" not in q):
        return datetime.now().strftime('%H:%M')

    PERSONAL_MARKERS = (" eu ", " meu ", " minha ", " nasci", "faço anos", "faco anos", "fiz anos", "aniversário", "casamento")
    is_personal = any(m in f" {q} " for m in PERSONAL_MARKERS)
    if not is_personal:
        data_rel = _parse_data_relativa(q)
        if data_rel is not None:
            return data_rel.strftime('%d/%m/%Y')
        if re.search(r'\b(que dia (é|e) hoje|que data (é|e) hoje|data de hoje|dia de hoje)\b', q):
            return datetime.now().strftime('%d/%m/%Y')

    if re.search(r'\b(cria|faz|gera|escreve)\b.*\b(arquivo|ficheiro|txt)\b', q):
        nome = "novo_arquivo.txt"
        m = re.search(r'(?:chamado|nome|como)\s+([a-zA-Z0-9._-]+)', q)
        if m: nome = m.group(1)
        if not nome.endswith(".txt"): nome += ".txt"
        return f"__action__:criar_arquivo:{{'nome':'{nome}','conteudo':'','pasta':'.'}}"

    return None


def analisar(entrada: str) -> dict:
    e = entrada.strip().lower()
    insulto = _detectar_insulto_ou_assedio(e)
    if insulto:
        return {"action": "responder", "texto": insulto, "source": "guardrail"}

    pre = pre_analyze(entrada)
    if pre:
        if pre.startswith("__action__:"):
            _, act, params_str = pre.split(":", 2)
            import ast
            return {"action": act, **ast.literal_eval(params_str), "source": "pre_analyze"}
        return {"action": "responder", "texto": pre, "source": "pre_analyze"}

    # Lógica de Auto-Reflexão: Se o pedido for complexo, pede ao LLM para planear
    if len(e.split()) > 6 or any(p in e for p in [" e ", " depois ", " então ", " entao "]):
        print(f"[DEBUG] Ativando Auto-Reflexão para pedido complexo: {entrada}")
        plano = classify_intent(f"PLANEAMENTO: {entrada}")
        if plano and plano.get("confidence", 0) >= 0.7:
            return {**plano, "source": "self_reflection"}

    if re.search(r'\b(clima|tempo|temperatura|graus|chove|chuva|sol|nublado|frio|calor|previsao)\b', e):
        if not any(p in e for p in ["fonte", "segundo", "artigo", "wikipedia"]):
            cidade = None
            amanha = "amanha" in e or "amanhã" in e
            dias = 0
            m_dias = re.search(r'previs[ãa]o.*(\d+)\s*dias?', e)
            if m_dias: dias = int(m_dias.group(1))
            for cid in ["lisboa", "porto", "torres vedras", "são paulo", "rio de janeiro"]:
                if cid in e:
                    cidade = cid.title()
                    break
            return {"action": "clima", "cidade": cidade, "amanha": amanha, "dias": dias, "source": "regex"}

    if any(c in e for c in ["toca", "tocar", "reproduz", "põe musica", "play", "mete"]):
        termo = None
        match = re.search(r'(?:toca|tocar|reproduz|põe|play|mete)\s+(?:uma\s+)?(?:musica|música)?\s*(.+)?$', e)
        if match and match.group(1):
            termo = match.group(1).strip()
        if not termo: return {"action": "youtube_music_shuffle"}
        return {"action": "yt_music_play", "query": termo, "source": "regex"}

    llm = classify_intent(entrada)
    if llm and llm.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
        return {**llm, "source": "llm"}

    if any(s in e for s in ["sair", "exit", "quit"]): return {"action": "sair"}
    if any(h in e for h in ["ajuda", "help"]): return {"action": "ajuda"}
    
    return {"action": "browser_search", "query": entrada.strip(), "source": "llm_fallback"}


AJUDA_TEXTO = """👩 Infinity - Sua Assistente Pessoal
💬 Conversa natural: fale como quiser
🧠 A IA interpreta e escolhe a ferramenta
💡 Basta pedir naturalmente!"""

def _resumo_conversa() -> str:
    hist = MEMORIA.get("historico") or []
    if not hist: return "📭 Ainda não tivemos conversa para resumir."
    ultimas = hist[-15:]
    linhas = [f"📋 Resumo das últimas {len(ultimas)} interações:"]
    for h in ultimas:
        ent = (h.get("ent") or "")[:50]
        res = (h.get("res") or "")[:50]
        linhas.append(f"• Tu: {ent}\n  Eu: {res}")
    return "\n".join(linhas)

def _build_action_table(dec: dict) -> dict:
    entrada = dec.get("entrada", "")
    def _responder():
        texto = dec.get("texto", "")
        if texto: return texto
        return self_discuss(entrada or "Olá")
    
    def _atualizar_preferencia():
        pref = dec.get("preferencia", {})
        if not pref: return "Nenhuma preferência para atualizar."
        for k, v in pref.items():
            if k in MEMORIA["preferencias"]:
                MEMORIA["preferencias"][k] = v
        return f"Preferências atualizadas: {pref}"
    
    return {
        "responder": _responder,
        "atualizar_preferencia": _atualizar_preferencia,
        "matematica": lambda: str(safe_eval(dec.get("expr", "0"))),
        "resumo_conversa": _resumo_conversa,
        "hora": lambda: actions.action_hora(dec.get("mes")),
        "clima": lambda: actions.action_clima(dec.get("cidade"), dec.get("amanha", False), dec.get("dias", 0)),
        "sysinfo": actions.action_sysinfo,
        "abrir": lambda: actions.action_abrir(dec.get("app", "notepad")),
        "browser_search": lambda: actions.action_browser_search(dec.get("query", "")),
        "youtube_music_shuffle": actions.action_youtube_music_shuffle,
        "yt_music_play": lambda: actions.action_yt_music_play(dec.get("query", "")),
        "criar_arquivo": lambda: actions.action_criar_arquivo(dec.get("nome", "novo"), dec.get("conteudo", ""), dec.get("pasta", ".")),
        "todo_add": lambda: actions.action_todo_add(dec.get("task", "")),
        "todo_list": actions.action_todo_list,
        "nota_add": lambda: actions.action_nota_add(dec.get("texto", "")),
        "notas_listar": actions.action_notas_listar,
        "lembrete_add": lambda: actions.action_lembrete_add(dec.get("texto", ""), dec.get("em_min"), dec.get("quando")),
        "lembretes_listar": actions.action_lembretes_listar,
        "noticias": lambda: actions.action_noticias(dec.get("fonte", "publico"), dec.get("limite", 5)),
        "executar_codigo": lambda: actions.action_executar_codigo(dec.get("codigo", "")),
        "browser_automation": lambda: actions.action_browser_automation(dec.get("url", ""), dec.get("script")),
        "descrever_imagem": lambda: actions.action_descrever_imagem(dec.get("path", ""), dec.get("prompt")),
        "ocr": lambda: actions.action_ocr(dec.get("path", "")),
        "indexar_ficheiro": lambda: actions.action_indexar_ficheiro(dec.get("path", "")),
        "plugin": lambda: plugins.executar_plugin(dec.get("nome", ""), **dec.get("params", {})),
        "click": lambda: actions.action_click(dec.get("x"), dec.get("y"), dec.get("clicks", 1), dec.get("button", "left")),
        "type_text": lambda: actions.action_type_text(dec.get("texto", ""), dec.get("interval", 0.1)),
        "press_key": lambda: actions.action_press_key(dec.get("key", "")),
        "move_mouse": lambda: actions.action_move_mouse(dec.get("x", 0), dec.get("y", 0), dec.get("duration", 0.5)),
        "screenshot": lambda: actions.action_screenshot(dec.get("nome", "screenshot.png")),
        "window_control": lambda: actions.action_window_control(dec.get("app_name", ""), dec.get("action", "focus")),
        "agendar_tarefa": lambda: actions.action_agendar_tarefa(dec.get("quando", ""), dec.get("comando", ""), dec.get("recorrente", False)),
        "monitorar_condicao": lambda: actions.action_monitorar_condicao(dec.get("tipo", ""), dec.get("alvo", ""), dec.get("condicao", ""), dec.get("valor", 0.0), dec.get("acao", "")),
    }

def executar_acao(dec: dict) -> str:
    # Suporte para múltiplos passos (Chain of Thought)
    steps = dec.get("steps", [])
    if not steps and "action" in dec:
        steps = [dec]
    
    if not steps:
        return "Não entendi o que fazer."
    
    resultados = []
    ultimo_resultado = ""
    
    for step in steps:
        # Se o passo anterior teve resultado, podemos injetá-lo no prompt do próximo passo
        # ou usá-lo como parâmetro se a IA assim o desejar.
        # Aqui, injetamos o último resultado nos parâmetros se houver um marcador {{last_result}}
        for k, v in step.get("params", {}).items():
            if isinstance(v, str) and "{{last_result}}" in v:
                step["params"][k] = v.replace("{{last_result}}", ultimo_resultado)
        
        action = step.get("action", "")
        if action == "sair": return "__sair__"
        if action == "ajuda": 
            resultados.append(AJUDA_TEXTO)
            continue
            
        acoes = _build_action_table(step)
        if action in acoes:
            try:
                res = acoes[action]()
                ultimo_resultado = str(res)
                
                # Mecanismo de Auto-Correção: Se o resultado for um erro, tenta pedir ao LLM uma correção
                if ultimo_resultado.startswith("❌"):
                    print(f"[DEBUG] Auto-correção ativada para erro: {ultimo_resultado}")
                    correcao = self_discuss(f"A ação '{action}' falhou com o erro: {ultimo_resultado}. Como posso corrigir ou que outra ação devo tentar?")
                    ultimo_resultado = f"{ultimo_resultado}\n💡 Sugestão de correção: {correcao}"
                
                resultados.append(ultimo_resultado)
            except Exception as e:
                ultimo_resultado = f"❌ Erro crítico em {action}: {e}"
                resultados.append(ultimo_resultado)
        else:
            # Fallback para pesquisa se a ação for desconhecida
            query = step.get("query", step.get("texto", ""))
            if "{{last_result}}" in query:
                query = query.replace("{{last_result}}", ultimo_resultado)
            res = actions.action_browser_search(query)
            ultimo_resultado = str(res)
            resultados.append(ultimo_resultado)
            
    return "\n\n".join(resultados)
