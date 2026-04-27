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
