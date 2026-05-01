"""Ações relacionadas com a web: abrir apps/URLs, browser, Wikipedia, IP, cripto, notícias."""

import json
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from urllib.error import URLError


def action_abrir(app: str) -> str:
    """Abre apps/sites de forma autónoma: app desktop → pesquisa IA → fallback Google."""
    try:
        app_lower = app.strip().lower()
        partes = app_lower.split()
        app_base = partes[0] if partes else app_lower

        # Aliases genéricos: "browser", "navegador", "internet" → abre o
        # navegador padrão do sistema na página inicial do Google.
        navegador_aliases = {"browser", "navegador", "internet", "navegar", "google"}
        if app_base in navegador_aliases or app_lower in navegador_aliases:
            try:
                webbrowser.open_new_tab("https://www.google.com")
                return "🌐 Já abri o navegador para ti"
            except webbrowser.Error:
                pass

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
    """Pesquisa na web, faz scraping do conteúdo das páginas e usa LLM para responder."""
    from memory import MEMORIA
    print(f"[DEBUG] Browser search query: {query}")
    
    # Se a query já veio do parser com contexto de follow-up (contém "Pergunta do usuário agora:"),
    # vamos adicionar contexto adicional da memória
    needs_extra_context = False
    if "Pergunta do usuário agora:" not in query and MEMORIA.get("historico") and len(MEMORIA["historico"]) >= 2:
        prev_resp = MEMORIA["historico"][-1].get("res", "")
        if len(prev_resp) > 50:
            needs_extra_context = True
            context_hint = f"\n[Contexto da resposta anterior: {prev_resp[:300]}...]"
    
    # Não guardar pesquisas genéricas de follow-up como "Olá"
    if query.strip().lower() not in ["olá", "oi", "ola"]:
        MEMORIA["ultima_pesquisa"] = query
    
    try:
        # 1. Pesquisa inicial para obter URLs usando DuckDuckGo HTML
        url_pesquisa = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url_pesquisa, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_pesquisa = resp.read().decode("utf-8", errors="ignore")
        
        import re
        # Extrair URLs dos resultados - múltiplos padrões para maior robustez
        urls = []
        
        # Padrão 1: links normais nos resultados
        link_pattern = r'<a[^>]*href="(https?://[^"]+)"[^>]*>'
        for match in re.finditer(link_pattern, html_pesquisa):
            url = match.group(1)
            # Filtrar URLs válidas (excluir duckduckgo, loops, etc.)
            if ('duckduckgo' not in url and 
                'http' in url and 
                len(url) > 10 and 
                url not in urls and 
                len(urls) < 5):
                urls.append(url)
        
        # Se ainda não temos URLs, tentar buscar por domínios comuns
        if len(urls) < 3:
            domain_pattern = r'(https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s"\'<>]*)?)'
            for match in re.finditer(domain_pattern, html_pesquisa):
                url = match.group(1).rstrip('">')
                if ('duckduckgo' not in url and 
                    url not in urls and 
                    len(urls) < 5):
                    urls.append(url)
        
        # Fallback final: construir URLs de busca do Google se nada funcionar
        if not urls:
            # Extrair termos da query e criar URLs prováveis
            termos = query.lower().split()[:5]
            fallback_urls = [
                f"https://pt.wikipedia.org/wiki/{'_'.join(termos)}",
                f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            ]
            urls = fallback_urls[:3]
        
        if not urls:
            return f"❌ Não consegui obter resultados para '{query}'"
        
        # 2. Fazer scraping do conteúdo de cada URL com timeout maior e tratamento robusto
        # Aumentar o número de páginas para mais contexto e precisão
        conteudos = []
        for url in urls[:5]:  # Ler até 5 páginas para mais fontes
            try:
                req_url = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
                    "Connection": "keep-alive"
                })
                with urllib.request.urlopen(req_url, timeout=15) as resp_url:
                    html_content = resp_url.read().decode("utf-8", errors="ignore")
                
                # Extrair texto principal usando BeautifulSoup
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Remover scripts, styles, nav, footer, header, aside
                    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'advertisement']):
                        tag.decompose()
                    
                    # Tentar encontrar conteúdo principal
                    main_content = None
                    for tag_id in ['main', 'content', 'article', 'post', 'entry']:
                        main_tag = soup.find(id=tag_id) or soup.find(class_=tag_id)
                        if main_tag:
                            main_content = main_tag
                            break
                    
                    if not main_content:
                        # Fallback: pegar todos os parágrafos
                        paragraphs = soup.find_all('p')
                        text = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
                    else:
                        text = main_content.get_text(separator='\n', strip=True)
                    
                    # Limitar tamanho do texto (máx 4000 caracteres por página para mais contexto)
                    if len(text) > 4000:
                        text = text[:4000] + "..."
                    
                    if text.strip() and len(text) > 100:  # Só adicionar se tiver conteúdo relevante
                        conteudos.append(f"Fonte: {url}\nConteúdo:\n{text}")
                except ImportError:
                    # BeautifulSoup não disponível, usar método básico
                    text = re.sub(r'<[^>]+>', '\n', html_content)
                    text = re.sub(r'\n\s*\n', '\n\n', text)
                    paragraphs = [p.strip() for p in text.split('\n') if len(p) > 100]
                    text = '\n'.join(paragraphs[:30])
                    if text.strip():
                        conteudos.append(f"Fonte: {url}\nConteúdo:\n{text}")
                except Exception as e_bs:
                    # Fallback sem BeautifulSoup: extrair texto básico
                    text = re.sub(r'<[^>]+>', '\n', html_content)
                    text = re.sub(r'\n\s*\n', '\n\n', text)
                    paragraphs = [p.strip() for p in text.split('\n') if len(p) > 100]
                    text = '\n'.join(paragraphs[:20])
                    if text.strip():
                        conteudos.append(f"Fonte: {url}\nConteúdo:\n{text}")
                        
            except Exception as e_url:
                # Log silencioso e continuar para próxima URL
                continue  # Pular URL com erro e continuar
        
        if not conteudos:
            return f"❌ Não consegui ler o conteúdo das páginas para '{query}'"
        
        # 3. Construir contexto completo para o LLM (limitado para evitar erro 413)
        # Limitar a 3 páginas mais relevantes e 2500 caracteres cada para mais precisão
        conteudos_limitados = conteudos[:3]
        contexto_completo = "\n\n---\n\n".join([
            c[:2500] + "..." if len(c) > 2500 else c 
            for c in conteudos_limitados
        ])
        
        # Debug: mostrar quantas páginas foram lidas
        print(f"   [DEBUG] {len(conteudos)} página(s) lida(s), {len(conteudos_limitados)} usadas no LLM")
        
        # 4. Síntese: LM Studio (Qwen) como prioridade, Groq fallback
        try:
            from llm import chamar_lm_studio, chamar_groq
            
            # Obter histórico recente para contexto de consistência
            historico_texto = ""
            if MEMORIA.get("historico"):
                ultimas = MEMORIA["historico"][-5:]
                for h in ultimas:
                    ent = h.get("ent", "")
                    res = h.get("res", "")
                    if ent and res and len(res) > 10:
                        historico_texto += f"Pergunta: '{ent}' → Resposta: '{res[:300]}...'\n"
            
            # Detectar tipo de pergunta
            query_lower = query.lower()
            is_followup = "follow-up:" in query_lower or any(p in query_lower for p in ["não é", "nao é", "entao", "mas", "por isso", "pq", "qual é", "qual a", "porqué", "porque", "certeza"])
            
            contexto_extra = f"[CONTEXTO DA CONVERSA]\n{historico_texto}\n" if historico_texto else ""
            prompt = f"""O usuário perguntou: "{query}"
{contexto_extra}

FONTES ENCONTRADAS ({len(conteudos_limitados)}):
{contexto_completo}

TAREFA: Responde à pergunta do usuário usando APENAS as informações das fontes fornecidas acima.
Responda em português, 2-4 frases curtas."""

            # Calcular tamanho do prompt (aprox 1 token = 4 chars)
            # Usar Groq apenas se o contexto > 4096 tokens (~16384 chars)
            prompt_size = len(prompt)
            use_groq = prompt_size > 16000
            
            if use_groq:
                print(f"   [DEBUG] Contexto grande ({prompt_size} chars), usando Groq")
            
            # Se contexto grande, usar Groq; caso contrário, LM Studio
            if use_groq:
                try:
                    resposta = chamar_groq(prompt, model="qwen2.5-coder-3b-instant")
                    if resposta and len(resposta.strip()) > 20:
                        if query.strip().lower() not in ["olá", "oi", "ola"] and resposta.strip().lower() in ["olá", "oi", "ola", "olá!", "oi!"]:
                            pass
                        else:
                            return resposta
                except Exception as e_groq:
                    print(f"   [DEBUG] Erro no Groq: {e_groq}")
            
            # Prioridade: LM Studio (Qwen 2.5 3B Instruct local) - para contextos pequenos
            try:
                resposta = chamar_lm_studio(prompt)
                if resposta and len(resposta.strip()) > 20:
                    if query.strip().lower() not in ["olá", "oi", "ola"] and resposta.strip().lower() in ["olá", "oi", "ola", "olá!", "oi!"]:
                        pass
                    else:
                        return resposta
            except Exception as e_lm:
                print(f"   [DEBUG] LM Studio indisponível: {e_lm}")
                # Fallback para Groq se LM Studio falhar mesmo com contexto grande
                if use_groq:
                    try:
                        resposta = chamar_groq(prompt, model="qwen2.5-coder-3b-instant")
                        if resposta and len(resposta.strip()) > 20:
                            return resposta
                    except:
                        pass
        except Exception as e_llm:
            print(f"   [DEBUG] Erro no LLM: {e_llm}")
            pass
        
        # Fallback: mostrar resumo dos conteúdos se LLM falhar
        linhas = [f"🌐 Pesquisei e li várias páginas sobre '{query}'. Eis um resumo:"]
        for i, conteudo in enumerate(conteudos[:3], 1):
            partes = conteudo.split('\nConteúdo:\n')
            if len(partes) > 1:
                url = partes[0].replace('Fonte: ', '').strip()
                texto = partes[1][:400] + "..." if len(partes[1]) > 400 else partes[1]
                linhas.append(f"\n{i}. {url}\n   {texto}")
        
        linhas.append("\n💡 Não consegui sintetizar uma resposta automática completa, mas podes explorar os conteúdos acima.")
        return "\n".join(linhas)
        
    except Exception as e:
        return f"❌ Erro ao pesquisar '{query}': {e}"


def action_abrir_url(url: str) -> str:
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        webbrowser.open_new_tab(url)
        return f"✅ Abrindo: {url}"
    except webbrowser.Error as e:
        return f"❌ Erro ao abrir URL: {e}"


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


# ----- Notícias via RSS -----
RSS_FEEDS = {
    "g1": "https://g1.globo.com/rss/g1/",
    "publico": "https://www.publico.pt/rss",
    "bbc": "https://feeds.bbci.co.uk/portuguese/rss.xml",
    "rtp": "https://www.rtp.pt/noticias/rss",
    "dn": "https://www.dn.pt/rss",
    "tech": "https://feeds.feedburner.com/TechCrunch/",
    "hackernews": "https://hnrss.org/frontpage",
}


def action_noticias(fonte: str = "g1", limite: int = 5) -> str:
    fonte_key = (fonte or "g1").strip().lower()
    if fonte_key not in RSS_FEEDS:
        disponiveis = ", ".join(sorted(RSS_FEEDS))
        return f"❌ Fonte desconhecida. Disponíveis: {disponiveis}"
    try:
        n = max(1, min(int(limite), 15))
    except (TypeError, ValueError):
        n = 5
    url = RSS_FEEDS[fonte_key]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "InfinityX/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
    except (URLError, OSError) as e:
        return f"❌ RSS '{fonte_key}': {e}"
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return f"❌ Feed inválido ({fonte_key}): {e}"

    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    if not items:
        return f"📭 Sem notícias em '{fonte_key}'"

    linhas = [f"📰 {fonte_key.upper()} (top {min(n, len(items))})"]
    for it in items[:n]:
        titulo_el = it.find("title") or it.find("{http://www.w3.org/2005/Atom}title")
        link_el = it.find("link") or it.find("{http://www.w3.org/2005/Atom}link")
        titulo = (titulo_el.text or "").strip() if titulo_el is not None else "(sem título)"
        link = ""
        if link_el is not None:
            link = (link_el.text or link_el.get("href") or "").strip()
        linhas.append(f"• {titulo}" + (f"\n  {link}" if link else ""))
    return "\n".join(linhas)
