"""Pré-análise rápida, parser de intenções (LLM-first + fallback) e executor."""

import random
import re
import unicodedata
from datetime import datetime, timedelta

import actions
from config import (
    CONFIDENCE_THRESHOLD,
    EXPR_PATTERN,
    NUMEROS_PT,
    OPERATORS_PT,
)
from llm import buscar_info, classify_intent
from memory import MEMORIA, PALAVRAS
from utils import safe_eval


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
# Quando o classificador LLM falha (caso real visto: "vai tomar no cu" tratado
# como "encontrar trabalho num veículo"), capturamos aqui antes e damos uma
# resposta curta no tom da personagem, sem moralismo nem texto longo.
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
# Exige sujeito explícito ("és", "tu", "você") perto do adjectivo para evitar
# falsos positivos em "bom dia", "está bom o tempo", "previsão boa", etc.
_ADJ_ELOGIO = (
    r"(boa|bom|fixe|gira|linda|incr[íi]vel|fant[áa]stica|brilhante|esperta|"
    r"inteligente|[óo]ptima|[óo]tima|excelente|maravilhosa|perfeita|querida|"
    r"genial|espectacular|espetacular|porreira)"
)
_ELOGIO_PATTERNS = [
    # Sujeito explícito "tu" / "você" (3ª pessoa "é" sozinha causa falsos
    # positivos: "a previsão é boa", "o filme é bom", etc.)
    rf'\b(?:tu\s+)?(?:és|es)\s+(?:muito |mesmo |bem |t[ãa]o |t[aã]o |uma |um |a |o )?{_ADJ_ELOGIO}\b',
    rf'\b(?:voc[êe]|tu)\s+(?:é|e)\s+(?:muito |mesmo |bem |t[ãa]o |a |o |uma |um )?{_ADJ_ELOGIO}\b',
    r'\b(adoro-te|adoro voc[êe]|gosto (muito )?de ti|amo-te|tu mandas|tu rachas|tu arrasas|tu salvas)\b',
    r'\b(parab[ée]ns|bem feito|boa resposta|boa essa|bom trabalho|excelente trabalho)\b',
    r'\bmuito obrigad[ao]\b',
    r'\bobrigad[ao]\s+(infinity|infinit[áa]?|por (isso|tudo|ajudar))\b',
    r'\b(valeu|brigad[ao])\b',
]
# Saudações comuns que NÃO devem ser tratadas como elogio.
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
    # Saudações tipo "bom dia" / "boa noite" não são elogios; deixa o pre_analyze
    # tratar disso.
    if _SAUDACOES.match(q):
        return None
    # Elogio tem prioridade — evita confusões e é o caso mais comum.
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
    """Devolve um datetime ou None.

    Reconhece, em português PT/BR:
      • ontem / anteontem / antes de ontem
      • amanhã / depois de amanhã
      • há/ha N (dia|semana|mês|ano)(s)
      • N (dia|semana|...)(s) atrás
      • daqui a N (dia|semana|...)(s) | em N (dia|...)(s)
      • semana passada / mês passado / ano passado
      • próxima semana / próximo mês / próximo ano
      • uma semana atrás / daqui a uma semana
    Só dispara se o utilizador estiver a perguntar uma data ("que dia",
    "que data", "qual o dia"); caso contrário devolve None.
    """
    from datetime import datetime, timedelta  # import local
    if not re.search(r'\bque (dia|data)\b|\bqual (é|e|foi|ser[áa]) (o|a) (dia|data)\b', q):
        return None

    # Marcadores absolutos simples
    if re.search(r'\bantes\s+de\s+ontem\b|\banteontem\b', q):
        return datetime.now() - timedelta(days=2)
    if re.search(r'\bdepois\s+de\s+amanh[ãa]\b', q):
        return datetime.now() + timedelta(days=2)
    if re.search(r'\bontem\b', q):
        return datetime.now() - timedelta(days=1)
    if re.search(r'\bamanh[ãa]\b', q):
        return datetime.now() + timedelta(days=1)

    # "semana passada" / "mês passado" / "ano passado"
    m = re.search(rf'\b({_UNIDADE_RE})\s+passad[ao]\b', q)
    if m:
        return datetime.now() - timedelta(days=_UNIDADES_DIAS[m.group(1)])
    # "próxima semana" / "próximo mês" / "próximo ano" / "que vem"
    m = re.search(rf'\b(?:pr[óo]xim[ao]|que vem)\s+({_UNIDADE_RE})\b', q)
    if m:
        return datetime.now() + timedelta(days=_UNIDADES_DIAS[m.group(1)])
    m = re.search(rf'\b({_UNIDADE_RE})\s+que vem\b', q)
    if m:
        return datetime.now() + timedelta(days=_UNIDADES_DIAS[m.group(1)])

    # "há N unidades" / "ha N unidades"
    m = re.search(rf'\bh[áa]\s+({_NUM_RE})\s+({_UNIDADE_RE})\b', q)
    if m:
        n = _num_pt(m.group(1))
        if n:
            return datetime.now() - timedelta(days=n * _UNIDADES_DIAS[m.group(2)])

    # "N unidades atrás"
    m = re.search(rf'\b({_NUM_RE})\s+({_UNIDADE_RE})\s+atr[áa]s\b', q)
    if m:
        n = _num_pt(m.group(1))
        if n:
            return datetime.now() - timedelta(days=n * _UNIDADES_DIAS[m.group(2)])

    # "daqui a N unidades" / "em N unidades" / "daqui N unidades"
    m = re.search(rf'\b(?:daqui\s+a|em|daqui)\s+({_NUM_RE})\s+({_UNIDADE_RE})\b', q)
    if m:
        n = _num_pt(m.group(1))
        if n:
            return datetime.now() + timedelta(days=n * _UNIDADES_DIAS[m.group(2)])

    return None


# ----- Pré-análise determinística (sem IA, só dados objetivos) -----
def pre_analyze(query: str) -> str | None:
    """Atende apenas o que tem resposta factual (matemática, hora, data, criar
    ficheiro). Reações conversacionais — saudações, confirmações, insultos —
    são deixadas para o classificador LLM, que gera o texto seguindo as
    instruções do system prompt."""
    q = query.strip().lower()

    # Matemática em português
    try:
        q_norm = unicodedata.normalize('NFC', q)
        tokens = [t.strip('.,!?;:') for t in q_norm.split() if t.strip('.,!?;:')]
        i = 0
        while i < len(tokens) - 1:
            combined = f"{tokens[i]} {tokens[i + 1]}"
            if combined in NUMEROS_PT:
                tokens[i] = combined
                tokens.pop(i + 1)
            i += 1

        expr_tokens = []
        for t in tokens:
            if t in NUMEROS_PT:
                expr_tokens.append(str(NUMEROS_PT[t]))
            elif t in OPERATORS_PT:
                expr_tokens.append(OPERATORS_PT[t])
            elif t.replace('.', '').replace('-', '').isdigit() or t in '+-*/().%':
                expr_tokens.append(t)

        if expr_tokens:
            expr = ''.join(expr_tokens)
            if any(op in expr for op in '+-*/') and re.match(r'^[\d+\-*/.()%]+$', expr):
                return str(safe_eval(expr))
    except (SyntaxError, ValueError, KeyError):
        pass

    # Hora — pedido factual sobre o relógio
    match = re.search(r'que horas?(?: eram?| seria[vmo]?)?\s*(?:daqui a)?\s*(\d+)\s*hora[s]?(?: atrás)?', q)
    if match:
        horas = int(match.group(1))
        return (datetime.now() - timedelta(hours=horas)).strftime('%H:%M')
    if "que horas" in q or ("hora" in q and "tempo" not in q):
        return datetime.now().strftime('%H:%M')

    # Data — só responde se for um pedido factual GENÉRICO sobre o calendário.
    # Perguntas pessoais ("que dia eu nasci?", "que dia faço anos?", "que dia
    # foi o casamento?") NÃO devem ser respondidas com a data de hoje — são
    # encaminhadas ao LLM/fallback que pede contexto ao utilizador.
    PERSONAL_MARKERS = (
        " eu ", " meu ", " minha ", " nasci", "faço anos", "faco anos",
        "fiz anos", "aniversário", "aniversario", "casamento", "casei",
        "te conheci", "nos conhecemos", "começamos", "comecamos",
    )
    is_personal = any(m in f" {q} " for m in PERSONAL_MARKERS)

    if not is_personal:
        # Datas relativas determinísticas
        data_rel = _parse_data_relativa(q)
        if data_rel is not None:
            return data_rel.strftime('%d/%m/%Y')

        # Pedido genérico sobre a data de hoje
        if re.search(r'\b(que dia (é|e) hoje|que data (é|e) hoje|data de hoje|dia de hoje|hoje (é|e) que dia|qual (é|e) (a )?data|que dia (é|e))\b', q):
            return datetime.now().strftime('%d/%m/%Y')
        if re.search(r'\bem que (anos?|mês|mês|semana) estamos?\b', q):
            return datetime.now().strftime('%Y')
        if re.search(r'\bque (anos?|mês|mês|semana|hora) (são|é)\b', q):
            return datetime.now().strftime('%d/%m/%Y')
        if re.fullmatch(r'\s*(data|hoje)\s*\??', q):
            return datetime.now().strftime('%d/%m/%Y')

    # Criar ficheiro — comando determinístico
    if any(c in q for c in ["criar arquivo", "cria arquivo", "cria um arquivo", "novo arquivo"]):
        match = re.search(r'(?:criar|cria(?: um)?) arquivo(?: txt)?(?: de nome)? (.+?)?$', q)
        nome = match.group(1).strip() if match and match.group(1) else "novo_arquivo"
        return f"__criar_arquivo:{nome}__"

    return None


# ----- Dicionário pessoal -----
def checar_palavra(entrada: str) -> dict | None:
    e = entrada.strip().lower()

    match = re.match(r'^aprende\s+(.+?)\s*[=:]\s*(.+)$', e)
    if match:
        return {
            "action": "palavras_aprender",
            "palavra": match.group(1).strip(),
            "significado": match.group(2).strip(),
        }

    match = re.match(r'^(o\s+que\s+(é|significa)|significado\s+de)\s+(.+?)\??$', e)
    if match:
        palavra = match.group(3).strip().rstrip('?')
        if palavra.lower() in PALAVRAS:
            return {"action": "palavras_procurar", "palavra": palavra}
        return {"action": "buscar", "query": f"o que é {palavra}"}

    if any(p in e for p in ["lista palavras", "minhas palavras", "palavras aprendidas"]):
        return {"action": "palavras_listar"}

    match = re.match(r'^(esquece|remove palavra)\s+(.+)$', e)
    if match:
        return {"action": "palavras_excluir", "palavra": match.group(2).strip()}

    return None


# ----- Parser principal -----
def analisar(entrada: str) -> dict:
    e = entrada.strip().lower()

    if ck := checar_palavra(entrada):
        return ck

    # Detector determinístico de insultos/assédio — antes do LLM, para garantir
    # uma resposta curta no tom da Infinity em vez de divagações do classificador.
    if resp := _detectar_insulto_ou_assedio(e):
        return {"action": "responder", "texto": resp, "source": "guardrail"}

    if pre := pre_analyze(entrada):
        if pre.startswith("__criar_arquivo:"):
            nome = pre.replace("__criar_arquivo:", "").replace("__", "").strip()
            return {"action": "criar_arquivo", "nome": nome if nome else "novo_arquivo"}
        return {"action": "responder", "texto": pre}

    # Follow-up: perguntas curtas que referem-se à última pesquisa
    followup_patterns = [
        r'^certeza\??$', r'^mesmo\??$', r'^mesma\??$',
        r'^e ?', r'^e o ', r'^e a ',
        r'^mais\b', r'^mais info\b', r'^mais detalhes\b',
        r'^mais\b', r'^mais\b',
        r'^explica\b', r'^como\??$', r'^porquê\b', r'^porque\b',
        r'^e se\b', r'^e se ',
        r'^e ?\w+\??$',
    ]
    if MEMORIA.get("ultima_pesquisa") and any(re.match(p, e) for p in followup_patterns):
        return {"action": "browser_search", "query": MEMORIA["ultima_pesquisa"], "source": "followup"}

    # Perguntas que devem usar browser_search (facts que mudam frequentemente)
    # VERIFICA PRIMEIRO, independente da confiança do LLM
    factual_patterns = [
        r'\bmais rapid[oa]\b', r'\bmais veloz\b', r'\bmaior velocidade\b',
        r'\bmais caro\b', r'\bmais barato\b', r'\bmelhor\b.*\bdo mundo\b',
        r'\bquem é\b', r'\bquem foi\b', r'\bqual é\b', r'\bqual a\b',
        r'\bquanto custa\b', r'\bpreço de\b', r'\bcapital\b',
        r'\brecorde\b', r'\branking\b', r'\bpopulação\b',
        r'\bmais popular\b', r'\bmais vendido\b',
    ]
    e_lower = entrada.strip().lower()
    if any(re.search(p, e_lower, re.IGNORECASE) for p in factual_patterns):
        return {"action": "browser_search", "query": entrada.strip(), "source": "fallback"}
    
    llm = classify_intent(entrada)
    
    if llm and llm.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
        action_map = {
            "responder": "responder", "matematica": "matematica",
            "clima": "clima", "hora_data": "hora",
            "abrir": "abrir", "abrir_url": "abrir_url",
            "browser_search": "browser_search",
            "listar_pasta": "listar", "organizar_pasta": "organizar",
            "sysinfo": "sysinfo", "youtube_music": "youtube_music_shuffle",
            "clipboard_copy": "clipboard_copy", "clipboard_paste": "clipboard_paste",
            "volume_set": "volume_set", "volume_mute": "volume_mute",
            "battery_status": "battery_status", "network_info": "network_info",
            "disk_usage": "disk_usage", "convert": "convert",
            "generate_password": "generate_password", "generate_qr": "generate_qr",
            "timer_set": "timer_set", "search_files": "search_files",
            "speak": "speak", "todo_add": "todo_add", "todo_list": "todo_list",
            "todo_done": "todo_done",
            "palavras_aprender": "palavras_aprender",
            "palavras_procurar": "palavras_procurar",
            "palavras_listar": "palavras_listar",
            "palavras_excluir": "palavras_excluir",
            "currency_convert": "currency_convert", "translate": "translate",
            "random_dice": "random_dice", "random_coin": "random_coin",
            "random_number": "random_number", "cleanup_temp": "cleanup_temp",
            "criar_arquivo": "criar_arquivo", "shorten_url": "shorten_url",
            "ping": "ping", "bmi": "bmi",
            "type_text": "type_text", "press_key": "press_key",
            "click": "click", "window_control": "window_control",
            "buscar": "browser_search",
            "uuid_gen": "uuid_gen", "hash_text": "hash_text",
            "base64": "base64", "url_codec": "url_codec",
            "text_tools": "text_tools", "json_format": "json_format",
            "color_convert": "color_convert", "lorem_ipsum": "lorem_ipsum",
            "public_ip": "public_ip", "wikipedia": "wikipedia",
            "crypto_price": "crypto_price",
            "nota_add": "nota_add", "notas_listar": "notas_listar",
            "nota_excluir": "nota_excluir",
            "resumo_dia": "resumo_dia",
            "noticias": "noticias",
            "lembrete_add": "lembrete_add",
            "lembretes_listar": "lembretes_listar",
            "lembrete_excluir": "lembrete_excluir",
            "media_play_pause": "media_play_pause",
            "media_next": "media_next",
            "media_previous": "media_previous",
            "media_stop": "media_stop",
            "media_volume_up": "media_volume_up",
            "media_volume_down": "media_volume_down",
            "media_mute": "media_mute",
            "yt_music_play": "yt_music_play",
            "yt_music_search": "yt_music_search",
            "yt_music_playlist": "yt_music_playlist",
            "yt_music_artist": "yt_music_artist",
            "yt_music_recommendations": "yt_music_recommendations",
            "yt_music_radio": "yt_music_radio",
            "lastfm_now_playing": "lastfm_now_playing",
            "lastfm_recent": "lastfm_recent",
            "lastfm_top": "lastfm_top",
            "lastfm_similar_artist": "lastfm_similar_artist",
            "lastfm_similar_track": "lastfm_similar_track",
            "lastfm_artist_info": "lastfm_artist_info",
            "lastfm_setup": "lastfm_setup",
            "lastfm_logout": "lastfm_logout",
            "lastfm_scrobble": "lastfm_scrobble",
            "lastfm_now_playing_set": "lastfm_now_playing_set",
            "resumo_conversa": "resumo_conversa",
        }
        action_name = action_map.get(llm["action"])
        if action_name:
            return {"action": action_name, **llm.get("params", {}), "source": "llm"}

    if any(s in e for s in ["sair", "exit", "quit"]):
        return {"action": "sair"}
    if any(h in e for h in ["ajuda", "help"]):
        return {"action": "ajuda"}

    if any(c in e for c in ["clima", "tempo", "graus", "quantos graus", "previsão", "previsao"]):
        cidade = None
        amanha = "amanhã" in e or "amanha" in e
        # "previsão 7 dias", "previsão de 5 dias", "previsão para 3 dias"
        dias = 0
        m_dias = re.search(r'previs[ãa]o(?:\s+(?:de|para|dos?))?\s+(\d+)\s*dias?', e)
        if m_dias:
            dias = int(m_dias.group(1))
        elif "previsão" in e or "previsao" in e:
            # "previsão semana" / "previsão da semana"
            if re.search(r'\bsemana\b', e):
                dias = 7
        for cid in ["são paulo", "rio de janeiro", "lisboa", "porto", "torres vedras",
                    "london", "new york", "madrid", "paris"]:
            if cid in e:
                cidade = cid.title()
                if cid in ["são paulo", "rio de janeiro", "lisboa", "torres vedras"]:
                    cidade = {"são paulo": "São Paulo", "rio de janeiro": "Rio de Janeiro",
                              "lisboa": "Lisboa", "torres vedras": "Torres Vedras"}[cid]
                break
        return {"action": "clima", "cidade": cidade, "amanha": amanha, "dias": dias}

    if "espaço" in e and ("livre" in e or "disco" in e or "pc" in e or " hd" in e or "ssd" in e):
        return {"action": "disk_usage"}

    apps_conhecidos = [
        "chrome", "firefox", "edge", "notepad", "calc", "explorer",
        "browser", "navegador", "internet",
    ]
    if any(a in e for a in ["abre", "abrir", "abra"]) and any(app in e for app in apps_conhecidos):
        app = next((a for a in apps_conhecidos if a in e), None)
        if app:
            return {"action": "abrir", "app": app}

    # Resumo da conversa actual — não é factual nem precisa de LLM externo,
    # construímos a partir do histórico em memória.
    if re.search(r'\b(resum[oae]|resumir|sintese|síntese)\b.*\b(conversa|di[áa]logo|chat|hist[óo]rico)\b', e) \
       or re.search(r'\b(conversa|di[áa]logo|chat|hist[óo]rico)\b.*\b(resum[oae]|resumir|sintese|síntese)\b', e):
        return {"action": "resumo_conversa"}

    if re.match(r'^[\d\s+\-*/.()%?!.]+$', e) and any(op in e for op in '+-*/'):
        return {"action": "matematica", "expr": e.rstrip('?.!')}

    if EXPR_PATTERN.search(e):
        match = EXPR_PATTERN.search(e)
        if match:
            n1, op, n2 = match.groups()
            try:
                expr = f"{NUMEROS_PT[n1]}{OPERATORS_PT[op]}{NUMEROS_PT[n2]}"
                return {"action": "matematica", "expr": expr}
            except KeyError:
                pass

    # Padrões simples que devem ser "responder" (não factual)
    saudactions = ["oi", "olá", "ola", "opa", "ei", "e ai", "eaí", "oiê", "hey", "yo", "ok", "beleza", "blz", "tmj", "valeu", "obrigado", "obrigada", "sim", "não"]
    if e.strip().lower() in saudactions:
        return {"action": "responder", "texto": "Olá! Como posso ajudar?"}
    
    # Respostas curtas que devem ser "responder"
    if len(e.strip()) <= 15 and not any(p in e for p in factual_patterns):
        return {"action": "responder", "texto": ""}  # LLM decide

    # Detectar perguntas de mês
    if re.search(r'\bem que (mês|mes)\b', e):
        from datetime import datetime
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes = meses[datetime.now().month - 1]
        return {"action": "hora", "mes": mes}

    # Se é factual, usa browser_search (pesquisa real)
    if any(re.search(p, e, re.IGNORECASE) for p in factual_patterns):
        return {"action": "browser_search", "query": entrada.strip(), "entrada": entrada, "source": "fallback"}

    # Se não é factual, usa "responder" (chat com LLM)
    if not any(re.search(p, e, re.IGNORECASE) for p in factual_patterns):
        return {"action": "responder", "texto": "", "entrada": entrada, "source": "fallback"}

    return {"action": "responder", "texto": "", "entrada": entrada, "source": "fallback"}


# ----- Executor -----
AJUDA_TEXTO = """👩 Infinity - Sua Assistente Pessoal

💬 Conversa natural: fale como quiser
🧠 A IA interpreta e escolhe a ferramenta

📚 Dicionário pessoal:
• 'aprende [palavra] = [significado]'
• 'o que é [palavra]?'
• 'lista palavras' • 'esquece [palavra]'

📝 Notas:
• 'anota [texto]' • 'minhas notas' • 'apaga nota [n]'

🛠️ Sistema e ficheiros:
• clima [cidade] • hora • sysinfo • bateria
• rede • espaço em disco • ip público
• abre [app/site] • organiza [pasta] • lista [pasta]
• gera senha • timer [minutos] • screenshot

🌐 Pesquisa:
• wikipedia [termo] • busca [termo]
• cotação [btc/eth/...] • cotação dólar/euro

🔧 Ferramentas para devs:
• gera uuid • hash [texto] • base64 [texto]
• url encode [texto] • formata json [texto]
• converte cor #ff8800 • lorem 3

✨ Outros:
• matemática: '2+2', '5 vezes 10'
• tradução • bmi • dados/moeda
• 'resumo do dia' • 'resumo da conversa'

💡 Basta pedir naturalmente!"""


def _resumo_conversa() -> str:
    """Resumo da conversa actual a partir do histórico em memória."""
    from memory import MEMORIA  # import local para evitar ciclos

    hist = MEMORIA.get("historico") or []
    if not hist:
        return "📭 Ainda não tivemos conversa para resumir."
    ultimas = hist[-15:]
    linhas = [f"📋 Resumo das últimas {len(ultimas)} interações:"]
    for h in ultimas:
        ent = (h.get("ent") or "").strip().replace("\n", " ")
        res = (h.get("res") or "").strip().replace("\n", " ")
        if len(ent) > 80:
            ent = ent[:77] + "..."
        if len(res) > 100:
            res = res[:97] + "..."
        linhas.append(f"• Tu: {ent}\n  Eu: {res}")
    return "\n".join(linhas)


def _build_action_table(dec: dict) -> dict:
    entrada = dec.get("entrada", "")
    
    def _responder():
        texto = dec.get("texto", "")
        if texto:
            return texto
        # Se texto vazio, chama LLM para gerar resposta
        from llm import self_discuss
        try:
            return self_discuss(entrada or "Olá")
        except Exception:
            return "Olá! Como posso ajudar?"
    
    return {
        "responder": _responder,
        "matematica": lambda: str(safe_eval(dec.get("expr", "0"))),
        "resumo_conversa": _resumo_conversa,
        "hora": lambda: actions.action_hora(dec.get("mes")),
        "clima": lambda: actions.action_clima(
            dec.get("cidade"), dec.get("amanha", False), dec.get("dias", 0)
        ),
        "sysinfo": actions.action_sysinfo,
        "battery_status": actions.action_battery_status,
        "network_info": actions.action_network_info,
        "disk_usage": lambda: actions.action_disk_usage(dec.get("drive")),
        "listar": lambda: actions.action_listar(dec.get("pasta", ".")),
        "organizar": lambda: actions.action_organizar(dec.get("pasta", "."), dec.get("executar", False)),
        "search_files": lambda: actions.action_search_files(
            dec.get("query", ""), dec.get("folder"), dec.get("ext")
        ),
        "file_info": lambda: actions.action_file_info(dec.get("path", "")),
        "cleanup_temp": actions.action_cleanup_temp,
        "criar_arquivo": lambda: actions.action_criar_arquivo(
            dec.get("nome", "novo_arquivo"), dec.get("conteudo", ""), dec.get("pasta", ".")
        ),
        "abrir": lambda: actions.action_abrir(dec.get("app", "notepad")),
        "abrir_url": lambda: actions.action_abrir_url(dec.get("url", "")),
        "browser_search": lambda: actions.action_browser_search(
            dec.get("query", ""), dec.get("engine", "google")
        ),
        "youtube_music_shuffle": actions.action_youtube_music_shuffle,
        "speak": lambda: actions.action_speak(dec.get("text", ""), dec.get("lang", "pt")),
        "clipboard_copy": lambda: actions.action_clipboard_copy(dec.get("text", "")),
        "clipboard_paste": actions.action_clipboard_paste,
        "translate": lambda: actions.action_translate(dec.get("text", ""), dec.get("to_lang", "en")),
        "convert": lambda: actions.action_convert(
            dec.get("value", 0), dec.get("from", ""), dec.get("to", "")
        ),
        "currency_convert": lambda: actions.action_currency_convert(
            dec.get("amount", 0), dec.get("from", ""), dec.get("to", "")
        ),
        "generate_password": lambda: actions.action_generate_password(
            dec.get("length", 16), dec.get("special", True)
        ),
        "generate_qr": lambda: actions.action_generate_qr(
            dec.get("text", ""), dec.get("filename", "qrcode.png")
        ),
        "shorten_url": lambda: actions.action_shorten_url(dec.get("url", "")),
        "random_dice": lambda: actions.action_random_dice(dec.get("sides", 6), dec.get("count", 1)),
        "random_coin": lambda: actions.action_random_dice(2, 1),
        "random_number": lambda: f"🎲 {random.randint(dec.get('min_val', 1), dec.get('max_val', 100))}",
        "ping": lambda: actions.action_ping(dec.get("host", "google.com")),
        "bmi": lambda: actions.action_bmi(dec.get("weight", 70), dec.get("height", 170)),
        "todo_add": lambda: actions.action_todo_add(dec.get("task", ""), dec.get("priority", "medium")),
        "todo_list": lambda: actions.action_todo_list(dec.get("show_done", False)),
        "palavras_aprender": lambda: actions.action_palavras_aprender(
            dec.get("palavra", ""), dec.get("significado", "")
        ),
        "palavras_procurar": lambda: actions.action_palavras_procurar(dec.get("palavra", "")),
        "palavras_listar": actions.action_palavras_listar,
        "palavras_excluir": lambda: actions.action_palavras_excluir(dec.get("palavra", "")),
        "conhecimento": lambda: actions.action_browser_search(dec.get("query") or dec.get("instrucao") or ""),
        "timer_set": lambda: actions.action_timer_set(dec.get("name", "timer"), dec.get("minutes", 5)),
        "type_text": lambda: actions.action_type_text(dec.get("text", "")),
        "press_key": lambda: actions.action_press_key(dec.get("key", "")),
        "click": lambda: actions.action_click(dec.get("x"), dec.get("y"), dec.get("button", "left")),
        "window_control": lambda: actions.action_window_control(
            dec.get("app", ""), dec.get("action", "")
        ),
        "uuid_gen": lambda: actions.action_uuid_gen(dec.get("count", 1)),
        "hash_text": lambda: actions.action_hash_text(
            dec.get("text", ""), dec.get("algo", "sha256")
        ),
        "base64": lambda: actions.action_base64(
            dec.get("text", ""), dec.get("mode", "encode")
        ),
        "url_codec": lambda: actions.action_url_codec(
            dec.get("text", ""), dec.get("mode", "encode")
        ),
        "text_tools": lambda: actions.action_text_tools(
            dec.get("text", ""), dec.get("op", "count")
        ),
        "json_format": lambda: actions.action_json_format(
            dec.get("text", ""), dec.get("indent", 2)
        ),
        "color_convert": lambda: actions.action_color_convert(dec.get("value", "")),
        "lorem_ipsum": lambda: actions.action_lorem_ipsum(dec.get("paragraphs", 1)),
        "public_ip": actions.action_public_ip,
        "wikipedia": lambda: actions.action_wikipedia(
            dec.get("query", ""), dec.get("lang", "pt")
        ),
        "crypto_price": lambda: actions.action_crypto_price(
            dec.get("coin", "bitcoin"), dec.get("currency", "usd")
        ),
        "nota_add": lambda: actions.action_nota_add(dec.get("texto", "")),
        "notas_listar": actions.action_notas_listar,
        "nota_excluir": lambda: actions.action_nota_excluir(dec.get("idx", 0)),
        "resumo_dia": actions.action_resumo_dia,
        "noticias": lambda: actions.action_noticias(
            dec.get("fonte", "g1"), dec.get("limite", 5)
        ),
        "lembrete_add": lambda: actions.action_lembrete_add(
            dec.get("texto", ""), dec.get("em_min"), dec.get("quando")
        ),
        "lembretes_listar": actions.action_lembretes_listar,
        "lembrete_excluir": lambda: actions.action_lembrete_excluir(dec.get("idx", 0)),
        "media_play_pause": actions.action_media_play_pause,
        "media_next": actions.action_media_next,
        "media_previous": actions.action_media_previous,
        "media_stop": actions.action_media_stop,
        "media_volume_up": lambda: actions.action_media_volume_up(dec.get("steps", 3)),
        "media_volume_down": lambda: actions.action_media_volume_down(dec.get("steps", 3)),
        "media_mute": actions.action_media_mute,
        "yt_music_play": lambda: actions.action_yt_music_play(dec.get("query", "")),
        "yt_music_search": lambda: actions.action_yt_music_search(
            dec.get("query", ""), dec.get("tipo", "songs"), dec.get("limite", 5)
        ),
        "yt_music_playlist": lambda: actions.action_yt_music_playlist(dec.get("nome", "")),
        "yt_music_artist": lambda: actions.action_yt_music_artist(dec.get("nome", "")),
        "yt_music_recommendations": lambda: actions.action_yt_music_recommendations(
            dec.get("seed"), dec.get("limite", 8)
        ),
        "yt_music_radio": lambda: actions.action_yt_music_radio(dec.get("seed", "")),
        "lastfm_now_playing": lambda: actions.action_lastfm_now_playing(dec.get("user")),
        "lastfm_recent": lambda: actions.action_lastfm_recent(
            dec.get("user"), dec.get("limite", 10)
        ),
        "lastfm_top": lambda: actions.action_lastfm_top(
            dec.get("user"), dec.get("kind", "artists"),
            dec.get("period", "overall"), dec.get("limite", 10)
        ),
        "lastfm_similar_artist": lambda: actions.action_lastfm_similar_artist(
            dec.get("artista", ""), dec.get("limite", 10)
        ),
        "lastfm_similar_track": lambda: actions.action_lastfm_similar_track(
            dec.get("artista", ""), dec.get("track", ""), dec.get("limite", 10)
        ),
        "lastfm_artist_info": lambda: actions.action_lastfm_artist_info(
            dec.get("artista", "")
        ),
        "lastfm_setup": actions.action_lastfm_setup,
        "lastfm_logout": actions.action_lastfm_logout,
        "lastfm_scrobble": lambda: actions.action_lastfm_scrobble(
            dec.get("artista", ""), dec.get("track", ""),
            dec.get("album"), dec.get("timestamp"),
        ),
        "lastfm_now_playing_set": lambda: actions.action_lastfm_now_playing_set(
            dec.get("artista", ""), dec.get("track", ""), dec.get("album"),
        ),
    }


def executar_acao(dec: dict) -> str:
    action = dec.get("action", "")
    acoes = _build_action_table(dec)

    if action in acoes:
        try:
            return acoes[action]()
        except Exception as e:
            return f"❌ Erro: {e}"

    if action == "ajuda":
        return AJUDA_TEXTO
    if action == "sair":
        return "__sair__"

    # Último fallback: browser_search (não Perplexity)
    return actions.action_browser_search(dec.get("query", dec.get("instrucao", "")))
