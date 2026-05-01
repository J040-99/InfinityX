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
        urls = []
        link_pattern = r'<a[^>]*href="(https?://[^"]+)"[^>]*>'
        for match in re.finditer(link_pattern, html_pesquisa):
            url = match.group(1)
            if ('duckduckgo' not in url and 'http' in url and len(url) > 10 and url not in urls and len(urls) < 5):
                urls.append(url)
        
        if not urls:
            termos = query.lower().split()[:5]
            urls = [f"https://pt.wikipedia.org/wiki/{'_'.join(termos)}", f"https://www.google.com/search?q={urllib.parse.quote(query)}"][:3]
        
        if not urls:
            return f"❌ Não consegui obter resultados para '{query}'"
        
        # 2. Scraping
        conteudos = []
        for url in urls[:3]:
            try:
                req_url = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_url, timeout=10) as resp_url:
                    html_content = resp_url.read().decode("utf-8", errors="ignore")
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                text = soup.get_text(separator='\n', strip=True)
                if len(text) > 3000:
                    text = text[:3000] + "..."
                if text.strip() and len(text) > 100:
                    conteudos.append(f"Fonte: {url}\nConteúdo:\n{text}")
            except Exception:
                continue
        
        if not conteudos:
            return f"❌ Não consegui ler o conteúdo das páginas para '{query}'"
        
        # 3. Síntese via LM Studio
        try:
            from llm import chamar_lm_studio
            
            contexto_completo = "\n\n---\n\n".join(conteudos)
            prompt = f"""O usuário perguntou: "{query}"

FONTES ENCONTRADAS:
{contexto_completo}

TAREFA: Responde à pergunta do usuário usando APENAS as informações das fontes fornecidas acima.
Responda em português, 2-4 frases curtas."""

            return chamar_lm_studio(prompt)
        except Exception as e:
            return f"❌ Erro na síntese local: {e}"
            
    except Exception as e:
        return f"❌ Erro na pesquisa: {e}"


def action_wikipedia(query: str, lang: str = "pt") -> str:
    """Resumo da Wikipedia."""
    try:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "InfinityX/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("extract", "Não encontrei resumo.")
    except Exception as e:
        return f"❌ Erro Wikipedia: {e}"


def action_public_ip() -> str:
    try:
        with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as resp:
            return json.loads(resp.read().decode())["ip"]
    except Exception:
        return "❌ Erro ao obter IP"


def action_crypto_price(coin: str = "bitcoin", currency: str = "eur") -> str:
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={currency}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            price = data[coin][currency]
            return f"💰 {coin.title()}: {price} {currency.upper()}"
    except Exception:
        return "❌ Erro ao obter cotação"


def action_noticias(fonte: str = "publico", limite: int = 5) -> str:
    rss_urls = {
        "publico": "https://www.publico.pt/feeds/actualidade",
        "bbc": "http://feeds.bbci.co.uk/portuguese/rss.xml",
        "hackernews": "https://news.ycombinator.com/rss",
    }
    url = rss_urls.get(fonte, rss_urls["publico"])
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            root = ET.fromstring(resp.read())
            items = root.findall(".//item")[:limite]
            res = [f"📰 Notícias ({fonte}):"]
            for item in items:
                title = item.find("title").text
                res.append(f" • {title}")
            return "\n".join(res)
    except Exception as e:
        return f"❌ Erro notícias: {e}"
