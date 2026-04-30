import re
import urllib.parse
import urllib.request

query = 'tempo clima Torres Vedras Portugal'
url_pesquisa = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

req = urllib.request.Request(url_pesquisa, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})
with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read().decode('utf-8', errors='ignore')

# Ver as primeiras 2000 chars
print(html[:2000])