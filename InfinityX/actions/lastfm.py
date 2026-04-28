"""Integração Last.fm — histórico, top, similares, info de artistas.

Usa apenas a API pública (read-only), por isso só é preciso uma API key
gratuita em https://www.last.fm/api/account/create. O username é opcional
mas, se for definido em LASTFM_USERNAME, evita ter de o passar sempre.

Scrobbling (escrita de plays) precisa de auth com sessão — não está
incluído aqui por requerer credenciais sensíveis; pode ser adicionado
mais tarde.
"""

import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

from config import LASTFM_API_KEY, LASTFM_USERNAME

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"

PERIODS = {"overall", "7day", "1month", "3month", "6month", "12month"}
KINDS = {"tracks": "user.gettoptracks",
         "artists": "user.gettopartists",
         "albums": "user.gettopalbums"}


def _check_key() -> str | None:
    if not LASTFM_API_KEY:
        return ("❌ Define LASTFM_API_KEY em InfinityX/.env "
                "(grátis em last.fm/api/account/create)")
    return None


def _resolve_user(user: str | None) -> str | None:
    u = (user or "").strip() or LASTFM_USERNAME
    if not u:
        return None
    return u


def _call(method: str, **params) -> dict | str:
    params.update({"method": method, "api_key": LASTFM_API_KEY, "format": "json"})
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{LASTFM_API}?{qs}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "InfinityX/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        return f"❌ Last.fm HTTP {e.code}: {e.reason}"
    except (URLError, OSError, json.JSONDecodeError) as e:
        return f"❌ Last.fm: {e}"
    if isinstance(data, dict) and data.get("error"):
        return f"❌ Last.fm: {data.get('message', 'erro')}"
    return data


def action_lastfm_now_playing(user: str | None = None) -> str:
    if err := _check_key():
        return err
    u = _resolve_user(user)
    if not u:
        return "❌ Indica utilizador (ou define LASTFM_USERNAME)"
    data = _call("user.getrecenttracks", user=u, limit=1)
    if isinstance(data, str):
        return data
    tracks = data.get("recenttracks", {}).get("track", [])
    if not tracks:
        return f"📭 {u}: sem histórico recente"
    t = tracks[0] if isinstance(tracks, list) else tracks
    artista = t.get("artist", {}).get("#text", "?")
    titulo = t.get("name", "?")
    nowplaying = t.get("@attr", {}).get("nowplaying") == "true"
    if nowplaying:
        return f"🎧 {u} está a ouvir: {titulo} — {artista}"
    quando = t.get("date", {}).get("#text", "")
    extra = f" ({quando})" if quando else ""
    return f"🕒 Última de {u}: {titulo} — {artista}{extra}"


def action_lastfm_recent(user: str | None = None, limite: int = 10) -> str:
    if err := _check_key():
        return err
    u = _resolve_user(user)
    if not u:
        return "❌ Indica utilizador (ou define LASTFM_USERNAME)"
    try:
        n = max(1, min(int(limite), 30))
    except (TypeError, ValueError):
        n = 10
    data = _call("user.getrecenttracks", user=u, limit=n)
    if isinstance(data, str):
        return data
    tracks = data.get("recenttracks", {}).get("track", [])
    if not tracks:
        return f"📭 {u}: sem histórico"
    if not isinstance(tracks, list):
        tracks = [tracks]
    linhas = [f"🕒 Últimas de {u}:"]
    for t in tracks[:n]:
        artista = t.get("artist", {}).get("#text", "?")
        titulo = t.get("name", "?")
        marca = "▶️ " if t.get("@attr", {}).get("nowplaying") == "true" else "  • "
        quando = t.get("date", {}).get("#text", "")
        suf = f"  ({quando})" if quando else ""
        linhas.append(f"{marca}{titulo} — {artista}{suf}")
    return "\n".join(linhas)


def action_lastfm_top(user: str | None = None, kind: str = "artists",
                     period: str = "overall", limite: int = 10) -> str:
    if err := _check_key():
        return err
    u = _resolve_user(user)
    if not u:
        return "❌ Indica utilizador (ou define LASTFM_USERNAME)"
    k = (kind or "artists").lower()
    if k not in KINDS:
        return f"❌ kind: {sorted(KINDS)}"
    p = (period or "overall").lower()
    if p not in PERIODS:
        return f"❌ period: {sorted(PERIODS)}"
    try:
        n = max(1, min(int(limite), 30))
    except (TypeError, ValueError):
        n = 10
    data = _call(KINDS[k], user=u, period=p, limit=n)
    if isinstance(data, str):
        return data
    chave = {"tracks": "toptracks", "artists": "topartists", "albums": "topalbums"}[k]
    item_key = {"tracks": "track", "artists": "artist", "albums": "album"}[k]
    items = data.get(chave, {}).get(item_key, [])
    if not items:
        return f"📭 {u}: sem top {k}"
    icone = {"tracks": "🎵", "artists": "🎤", "albums": "💿"}[k]
    linhas = [f"{icone} Top {k} de {u} ({p}):"]
    for i, it in enumerate(items[:n], 1):
        nome = it.get("name", "?")
        artista = it.get("artist", {})
        artista = artista.get("name") if isinstance(artista, dict) else artista
        plays = it.get("playcount", "?")
        sufixo = f" — {artista}" if artista and k != "artists" else ""
        linhas.append(f"  {i}. {nome}{sufixo}  ·  {plays} plays")
    return "\n".join(linhas)


def action_lastfm_similar_artist(artista: str, limite: int = 10) -> str:
    if err := _check_key():
        return err
    if not artista or not artista.strip():
        return "❌ Indica o artista"
    try:
        n = max(1, min(int(limite), 20))
    except (TypeError, ValueError):
        n = 10
    data = _call("artist.getsimilar", artist=artista.strip(), limit=n)
    if isinstance(data, str):
        return data
    items = data.get("similarartists", {}).get("artist", [])
    if not items:
        return f"📭 Sem artistas semelhantes a '{artista}'"
    linhas = [f"🎤 Parecidos com '{artista}':"]
    for i, it in enumerate(items[:n], 1):
        nome = it.get("name", "?")
        match = it.get("match")
        sufixo = f"  ({float(match) * 100:.0f}% match)" if match else ""
        linhas.append(f"  {i}. {nome}{sufixo}")
    return "\n".join(linhas)


def action_lastfm_similar_track(artista: str, track: str, limite: int = 10) -> str:
    if err := _check_key():
        return err
    if not (artista and artista.strip() and track and track.strip()):
        return "❌ Indica artista E música"
    try:
        n = max(1, min(int(limite), 20))
    except (TypeError, ValueError):
        n = 10
    data = _call("track.getsimilar", artist=artista.strip(),
                 track=track.strip(), limit=n)
    if isinstance(data, str):
        return data
    items = data.get("similartracks", {}).get("track", [])
    if not items:
        return f"📭 Sem músicas semelhantes a '{track}' de {artista}"
    linhas = [f"🎵 Parecidas com '{track}' — {artista}:"]
    for i, it in enumerate(items[:n], 1):
        nome = it.get("name", "?")
        art = it.get("artist", {}).get("name", "?")
        linhas.append(f"  {i}. {nome} — {art}")
    return "\n".join(linhas)


def action_lastfm_artist_info(artista: str) -> str:
    if err := _check_key():
        return err
    if not artista or not artista.strip():
        return "❌ Indica o artista"
    data = _call("artist.getinfo", artist=artista.strip())
    if isinstance(data, str):
        return data
    a = data.get("artist", {})
    if not a:
        return f"📭 '{artista}' não encontrado"
    nome = a.get("name", artista)
    listeners = a.get("stats", {}).get("listeners", "?")
    plays = a.get("stats", {}).get("playcount", "?")
    tags = ", ".join(t.get("name", "") for t in a.get("tags", {}).get("tag", [])[:5])
    bio = a.get("bio", {}).get("summary", "").split("<a")[0].strip()
    if len(bio) > 400:
        bio = bio[:400].rsplit(" ", 1)[0] + "…"
    partes = [f"🎤 {nome}", f"👥 {listeners} ouvintes · {plays} plays"]
    if tags:
        partes.append(f"🏷️ {tags}")
    if bio:
        partes.append(bio)
    return "\n".join(partes)
