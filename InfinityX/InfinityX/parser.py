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

    # Matemática em português - melhorar parsing de "menos um"
    try:
        q_norm = unicodedata.normalize('NFC', q)
        
        # Substituir operadores em português por símbolos
        temp = q_norm
        for pt_op, symbol in OPERATORS_PT.items():
            temp = re.sub(r'\b' + pt_op + r'\b', symbol, temp)
        
        # Substituir números por extenso
        for pt_num, num in NUMEROS_PT.items():
            temp = re.sub(r'\b' + pt_num + r'\b', str(num), temp)
        
        # Remover espaços extras mas manter operadores
        temp = re.sub(r'\s+([+\-*/()])\s*', r'\1', temp)
        temp = re.sub(r'\s+', r'', temp)
        
        # Verificar se é uma expressão matemática válida
        if re.match(r'^[\d+\-*/.()%]+$', temp) and any(op in temp for op in '+-*/'):
            return str(safe_eval(temp))
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
    """Wrapper que garante que `entrada` (o texto original do utilizador)
    fica sempre presente na decisao para o executor poder reusa-lo (ex.:
    accao "responder" com texto vazio precisa de saber o que perguntaste
    para gerar a resposta)."""
    dec = _analisar_core(entrada)
    dec.setdefault("entrada", entrada)
    return dec


def _analisar_core(entrada: str) -> dict:
    e = entrada.strip().lower()

    if ck := checar_palavra(entrada):
        return ck

    # Detector determinístico de insultos/assédio — antes do LLM, para garantir
    # uma resposta curta no tom da Infinity em vez de divagações do classificador.
    if resp := _detectar_insulto_ou_assedio(e):
        return {"action": "responder", "texto": resp, "source": "guardrail"}

    # Percepcao deterministica: microfone e camara antes do LLM, para o
    # utilizador conseguir disparar estas accoes mesmo sem chave de API.
    if re.fullmatch(r"\s*(ouve(?:-me)?|escuta(?:-me)?|p[oo]e-te a ouvir|modo voz|liga (?:o )?microfone)\s*[!?.]*\s*", e):
        return {"action": "ouvir_e_responder"}
    if re.search(r"\b(o que (?:v[eê]s|est[aá]s a ver)|olha (?:para )?(?:isto|aqui|c[aá])|tira (?:uma )?foto|usa a c[aâ]mara|liga a c[aâ]mara|abre a c[aâ]mara|ver com a c[aâ]mara)\b", e):
        return {"action": "ver"}
    m_img = re.match(r"^\s*(?:descreve(?:-me)?|analisa)\s+(?:a\s+|esta\s+|essa\s+)?(?:imagem|foto|figura)\s+(.+?)\s*$", e)
    if m_img:
        return {"action": "descrever_imagem", "path": m_img.group(1).strip().strip('"\'') }

    # Comandos para abrir apps/sites antes do LLM
    abrir_patterns = [
        (r'\babre\s+o?\s*(?:navegador|browser|chrome|firefox|edge|safari)\b', "navegador"),
        (r'\babre\s+o?\s*(?:spotify|netflix|youtube|spotfy|netfliz)\b', None),  # Extract app name
        (r'\babre\s+(?:o\s+)?(.+)', None),  # Generic "abre X"
    ]
    for pattern, fixed_app in abrir_patterns:
        m = re.search(pattern, e)
        if m:
            app = fixed_app
            if app is None and m.lastindex:
                app = m.group(m.lastindex).strip()
            if app:
                # Normalize common app names
                app_lower = app.lower()
                if any(b in app_lower for b in ["navegador", "browser", "chrome", "firefox", "edge", "safari"]):
                    app = "navegador"
                elif any(s in app_lower for s in ["spotify", "spotfy"]):
                    app = "spotify"
                elif any(n in app_lower for n in ["netflix", "netfliz"]):
                    app = "netflix"
                elif any(y in app_lower for y in ["youtube", "youtub"]):
                    app = "youtube"
                return {"action": "abrir", "app": app, "source": "pattern"}

    # Perguntas factuais sobre pessoas/lugares/coisas - antes do LLM
    factual_patterns = [
        r'\bquem\s+(?:é|era|foi)\s+(?:o\s+|a\s+)?(\w+)',
        r'\bqu[eé]\s+(?:é|são|era)\s+(\w+)',
        r'\bdefine\s+(?:o\s+|a\s+)?(\w+)',
        r'\bo\s+que\s+é\s+(\w+)',
    ]
    for pattern in factual_patterns:
        m = re.search(pattern, e)
        if m:
            termo = m.group(1).strip()
            # Skip if it's already handled by other patterns (like "o que é [palavra]" in checar_palavra)
            if termo and len(termo) > 2 and not any(p in e for p in ["palavra", "significado"]):
                return {"action": "buscar", "query": f"o que é {termo}", "source": "factual"}

    if pre := pre_analyze(entrada):
        if pre.startswith("__criar_arquivo:"):
            nome = pre.replace("__criar_arquivo:", "").replace("__", "").strip()
            return {"action": "criar_arquivo", "nome": nome if nome else "novo_arquivo"}
        return {"action": "responder", "texto": pre}

    # Respostas para confirmações simples - deixa a IA decidir baseado no contexto
    confirmacoes = {"ok", "ok!", "sim", "nao", "entendi", "entendeu", "claro", "entao", "blz", "beleza", "tmj", "valeu", "obrigado", "obrigada", "obg", "thanks", "thx", "de nada", "perfeito", "perfeita", "show", "top", "legal"}
    if e in confirmacoes:
        # Deixa a IA decidir a resposta baseado no contexto, não respostas determinísticas
        return {"action": "responder", "texto": ""}
    
# Follow-up: perguntas curtas que referem-se à última pesquisa ou ação (VERIFICA ANTES das confirmações genéricas)
    # EXCETO se for sobre música (para não quebrar o comando "toca musica")
    followup_patterns = [
        r'^certeza\??$', r'^mesmo\??$', r'^mesma\??$',
        r'^ok\??$', r'^sim\??$', r'^nao\??$', r'^não\??$',
        r'^e ?', r'^e o ', r'^e a ',
        r'^mais\b', r'^mais info\b', r'^mais detalhes\b',
        r'^explica\b', r'^explica\s+me\b', r'^como\??$', 
        r'^porqu[ée]\??$', r'^por[áa]?\??$', r'^pq\??$',
        r'^e se\b', r'^e se ',
        r'^sera\b', r'^ser[áa]?\??$', r'^né\b', r'^né\??$',
        r'^segundo\b', r'^segundo a\b', r'^fonte\b', r'^diz que\b',
        r'^não é\b', r'^nao é\b', r'^não é o\b', r'^nao é o\b',
        r'^não é a\b', r'^nao é a\b',
        r'^não\s+é', r'^nao\s+é',
        # Feedback sobre ações recentes
        r'^só\s+', r'^apenas\s+', r'^não\s+', r'^nao\s+',
        r'^abriu\s+(?:uma\s+)?aba', r'^abriu\s+(?:uma\s+)?janela',
        r'^abriu\s+o\s+navegador',
    ]

    # Padrões de correção/feedback sobre ações - tratadas antes de follow-up geral
    correction_patterns = [
        r'^eu\s+dis',
        r'^não\s+era\s+', r'^nao\s+era\s+',
        r'^não\s+é\s+isso', r'^nao\s+é\s+isso',
        r'^não\s+o\s+', r'^nao\s+o\s+',
        r'^quis\s+dizer', r'^queria\s+dizer',
        r'^queria\s+abrir',
        r'^não\s+abriu', r'^nao\s+abriu',
        r'^não\s+era\s+(?:para\s+)?abrir', r'^nao\s+era\s+(?:para\s+)?abrir',
        r'^eu\s+queria',
        r'^eu\s+quis',
    ]
    # Padrões de follow-up mais complexos que devem construir sobre a última resposta
    followup_complex_patterns = [
        r'^entao\s+qual', r'^entao\s+é', r'^entao\s+e', r'^então\??$',
        r'^não é\b', r'^nao é\b', r'^não e\b', r'^nao e\b',
        r'^não é o\b', r'^nao é o\b', r'^não e o\b', r'^nao e o\b',
        r'^não é a\b', r'^nao é a\b', r'^não e a\b', r'^nao e a\b',
        r'^mas\b', r'^porém\b', r'^todavia\b',
        r'^(e|é)\s+(?:o|a)\s+\w+',  # "e o Bugatti", "é o Tesla"
        r'^e\s+(?:se|sera|seria)\b',
        r'^pq\b', r'^por\s+',  # "pq", "por causa que"
        r'^segundo\b', r'^segundo a\b',  # "segundo a fonte..."
    ]
    # Perguntas muito curtas que devem ser sempre follow-ups se houver contexto anterior
    very_short_followups = ["porquê?", "pq?", "por?", "né?", "ok?", "sim?", "não?", "mas?", "e?", "certeza?"]
    # Não tratar como follow-up se a última pesquisa foi sobre música e o usuário disse apenas "certeza?" ou similar
    # Mas permitir follow-up para outros contextos (verificar também o histórico se não há ultima_pesquisa)
    
    # Obter a última interação do histórico para contexto
    historico = MEMORIA.get("historico", [])
    # Verificar último ask e última resposta
    ultima_perg = historico[-1].get("ent", "") if historico else ""
    ultima_resp = historico[-1].get("res", "") if historico else ""
    # Qualquer interação anterior (pergunta ou resposta > 1 char) conta como contexto
    has_previous_context = MEMORIA.get("ultima_pesquisa") or (historico and len(historico) >= 1 and (len(ultima_perg) > 3 or len(ultima_resp) > 1))
    
    if has_previous_context:
        # Verificar primeiro se é uma correção/feedback sobre ação anterior
        is_correction = any(re.search(p, e) for p in correction_patterns)
        if is_correction:
            # Verificar última ação para determinar como corrigir
            historico = MEMORIA.get("historico", [])
            if historico:
                ultima_ent = historico[-1].get("ent", "").lower()
                ultima_res = historico[-1].get("res", "")
                
                # Correção sobre abertura de navegador
                if any(p in ultima_ent for p in ["abre", "browser", "navegador"]) and any(p in e for p in ["janela", "nova", " nova", "não", "nao", "era", "quis", "queria", "diz", "dizer"]):
                    # Tentar abrir em nova janela (comando específico do SO)
                    import subprocess
                    import sys
                    try:
                        if sys.platform == "win32":
                            subprocess.Popen(["cmd", "/c", "start", "chrome", "--new-window", "https://www.google.com"])
                        else:
                            subprocess.Popen(["open", "-n", "https://www.google.com"])
                        return {"action": "responder", "texto": "🔧 Ops,sorry! Abri numa nova janela agora. Corrigido!", "source": "correction"}
                    except Exception:
                        return {"action": "responder", "texto": "🔧 Desculpa, não consegui abrir em nova janela. Queres que tente de outra forma?", "source": "correction_fail"}
        
        # Verificar se é um follow-up complexo (deve usar histórico)
        is_complex_followup = any(re.match(p, e) for p in followup_complex_patterns)
        
        if is_complex_followup:
            # Para follow-ups complexos, incluir a pergunta original na pesquisa
            ultima = MEMORIA.get("ultima_pesquisa")
            if ultima and ("musica" not in ultima.lower() or len(e) > 10):
                return {"action": "browser_search", "query": f"{ultima} {entrada.strip()}", "source": "followup_complex"}
        
        # Follow-up simples (padrões originais) - SEMPRE usar browser_search para mais fontes
        if any(re.match(p, e) for p in followup_patterns):
            ultima = MEMORIA.get("ultima_pesquisa")
            if ultima:
                followup_query = f"{ultima}. Follow-up: {entrada.strip()}"
                return {"action": "browser_search", "query": followup_query, "source": "followup"}
            else:
                historico = MEMORIA.get("historico", [])
                if historico and len(historico) >= 1:
                    ultima_resp = historico[-1].get("res", "")
                    if ultima_resp and len(ultima_resp) > 2:
                        return {"action": "responder", "texto": "Podes explicar melhor o que queres?", "source": "followup_context"}
                return {"action": "browser_search", "query": entrada.strip(), "source": "followup_verify"}

        # Perguntas muito curtas que devem ser sempre follow-up
        if e.strip() in very_short_followups and has_previous_context:
            ultima = MEMORIA.get("ultima_pesquisa")
            if ultima:
                followup_query = f"{ultima}. Follow-up: {entrada.strip()}"
                return {"action": "browser_search", "query": followup_query, "source": "followup_short"}
            else:
                historico = MEMORIA.get("historico", [])
                if historico and len(historico) >= 1:
                    ultima_resp = historico[-1].get("res", "")
                    if ultima_resp and len(ultima_resp) > 2:
                        return {"action": "responder", "texto": "Exato. Em que posso ajudar?", "source": "followup_context"}
                return {"action": "responder", "texto": "O que precisas?", "source": "followup_clarify"}

    # Clima - só se contiver palavras específicas de clima
    if re.search(r'\b(clima|tempo|temperatura|graus|chove|chuva|sol|nublado|frio|calor|previsao|previsão)\b', e):
        if not any(p in e for p in ["fonte", "segundo", "artigo", "artigo", "wikipedia", "diz que", "afirma"]):
            cidade = None
            e_lower = e.lower()
            amanha = "amanha" in e_lower or "amanhã" in e
            dias = 0
            m_dias = re.search(r'previs[ãa]o(?:\s+(?:de|para|dos?))?\s+(\d+)\s*dias?', e)
            if m_dias:
                dias = int(m_dias.group(1))
            elif re.search(r'\bsemana\b', e):
                dias = 7
            for cid in ["são paulo", "rio de janeiro", "lisboa", "porto", "torres vedras",
                        "london", "new york", "madrid", "paris"]:
                if cid in e:
                    cidade = cid.title()
                    if cid in ["são paulo", "rio de janeiro", "lisboa", "torres vedras"]:
                        cidade = {"são paulo": "São Paulo", "rio de janeiro": "Rio de Janeiro",
                                  "lisboa": "Lisboa", "torres vedras": "Torres Vedras"}[cid]
                    break
            return {"action": "clima", "cidade": cidade, "amanha": amanha, "dias": dias, "atual": False}

    # Comandos de música — VERIFICA ANTES dos padrões factuais
    # "toca uma musica", "toca musica", "toca [nome]", "reproduz musica", "põe musica",
    # "coloca musica", "play", "toca [artista]", "toca [musica específica]"
    # "mete uma musica", "mete musica", "por musica"
    if any(c in e for c in ["toca", "toca uma", "tocar", "reproduz", "reproduzir", "põe musica", "poes musica", "coloca musica", "play", "youtube music", "mete", "mete uma", "por musica"]):
        # Extrair o termo da música/artista após o verbo
        termo = None
        match = re.search(r'(?:toca|toca uma|tocar|reproduz|reproduzir|põe|poes|coloca|play|mete|mete uma|por)\s+(?:uma\s+)?(?:musica|música)?\s*(?:a\s+tocar)?\s*(.+)?$', e)
        if match and match.group(1):
            termo = match.group(1).strip()
            if termo in ["?", "por favor", "pfv", "pls", "a tocar"]:
                termo = None
        # Se não extraiu nada ou foi só "toca musica" sem especificar, usa shuffle
        if not termo:
            return {"action": "youtube_music_shuffle"}
        return {"action": "yt_music_play", "query": termo}

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
            "ouvir": "ouvir",
            "ouvir_e_responder": "ouvir_e_responder",
            "ver": "ver",
            "descrever_imagem": "descrever_imagem",
        }
        action_name = action_map.get(llm["action"])
        if action_name:
            return {"action": action_name, **llm.get("params", {}), "source": "llm"}

    if any(s in e for s in ["sair", "exit", "quit"]):
        return {"action": "sair"}
    if any(h in e for h in ["ajuda", "help"]):
        return {"action": "ajuda"}

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

    saudactions = ["oi", "olá", "ola", "opa", "ei", "e ai", "eaí", "oiê", "hey", "yo"]
    if e.strip().lower() in saudactions:
        return {"action": "responder", "texto": "Olá! Como posso ajudar?"}
    
    # Respostas curtas que devem ser "responder" - LLM decide
    if len(e.strip()) <= 15:
        return {"action": "responder", "texto": ""}

    # Detectar perguntas de mês
    if re.search(r'\bem que (mês|mes)\b', e):
        from datetime import datetime
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes = meses[datetime.now().month - 1]
        return {"action": "hora", "mes": mes}

    # Se nenhuma ação foi identificada pelo LLM, faz pesquisa para ter certeza
    return {"action": "browser_search", "query": entrada.strip(), "entrada": entrada, "source": "llm_fallback"}


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
        try:
            result = self_discuss(entrada or "Olá")
            return result if result and result.strip() else "Olá! Como posso ajudar?"
        except Exception:
            return "Olá! Como posso ajudar?"
    
    return {
        "responder": _responder,
        "matematica": lambda: str(safe_eval(dec.get("expr", "0"))),
        "resumo_conversa": _resumo_conversa,
        "hora": lambda: actions.action_hora(dec.get("mes")),
        "clima": lambda: actions.action_clima(
            dec.get("cidade"), dec.get("amanha", False), dec.get("dias", 0), dec.get("atual", False)
        ),
        "localizacao": lambda: f"Moras em: {actions.get_localizacao_atual() or 'não consegui detectar'}",
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
        "ouvir": lambda: actions.action_ouvir(
            dec.get("duracao", 6), dec.get("idioma", "pt-PT"),
        ),
        "ouvir_e_responder": lambda: actions.action_ouvir_e_responder(
            dec.get("duracao", 6), dec.get("idioma", "pt-PT"),
        ),
        "ver": lambda: actions.action_ver(
            dec.get("prompt"), dec.get("camera_idx", 0),
        ),
        "descrever_imagem": lambda: actions.action_descrever_imagem(
            dec.get("path", ""), dec.get("prompt"),
        ),
    }


def executar_acao(dec: dict) -> str:
    action = dec.get("action", "")
    acoes = _build_action_table(dec)

    if action in acoes:
        try:
            result = acoes[action]()
            if not result or result.startswith("❌"):
                print(f"[DEBUG] action_clima result: {result}", file=sys.stderr)
            return result
        except Exception as e:
            print(f"[DEBUG] executar_acao error: {e}", file=sys.stderr)
            return f"❌ Erro: {e}"

    if action == "ajuda":
        return AJUDA_TEXTO
    if action == "sair":
        return "__sair__"

    # Último fallback: browser_search (não Perplexity)
    return actions.action_browser_search(dec.get("query", dec.get("instrucao", "")))
