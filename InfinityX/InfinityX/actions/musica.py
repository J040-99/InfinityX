"""Controlo de mídia (teclas multimédia) e integração com YouTube Music.

Inclui:
  • Teclas multimédia OS-wide (play/pause/next/prev/volume) — funcionam
    com qualquer leitor activo, incluindo YT Music gratuito.
  • Pesquisa, reprodução, abertura de playlists e recomendações via
    `ytmusicapi` (sem chave de API). Cai em fallbacks por URL quando a
    biblioteca não está disponível.
"""

import threading
import time
import urllib.parse
import webbrowser

from config import SYSTEM_AUTO_AVAILABLE

from . import lastfm as _lastfm

if SYSTEM_AUTO_AVAILABLE:
    import pyautogui

try:
    from ytmusicapi import YTMusic
    YTMUSIC_AVAILABLE = True
except ImportError:
    YTMUSIC_AVAILABLE = False

_YT_CLIENT: "YTMusic | None" = None


def _yt() -> "YTMusic | None":
    global _YT_CLIENT
    if not YTMUSIC_AVAILABLE:
        return None
    if _YT_CLIENT is None:
        try:
            _YT_CLIENT = YTMusic()
        except Exception:
            return None
    return _YT_CLIENT


# ----- Teclas multimédia (controlo de qualquer player activo) -----
def _press(key: str, label: str) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instala pyautogui para controlo multimédia"
    try:
        pyautogui.press(key)
        return label
    except Exception as e:
        return f"❌ Erro: {e}"


def action_media_play_pause() -> str:
    return _press("playpause", "⏯️ Play/Pause")


def action_media_next() -> str:
    return _press("nexttrack", "⏭️ Próxima")


def action_media_previous() -> str:
    return _press("prevtrack", "⏮️ Anterior")


def action_media_stop() -> str:
    return _press("stop", "⏹️ Stop")


def action_media_volume_up(steps: int = 3) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instala pyautogui para controlo multimédia"
    try:
        n = max(1, min(int(steps), 20))
    except (TypeError, ValueError):
        n = 3
    try:
        for _ in range(n):
            pyautogui.press("volumeup")
        return f"🔊 Volume +{n}"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_media_volume_down(steps: int = 3) -> str:
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Instala pyautogui para controlo multimédia"
    try:
        n = max(1, min(int(steps), 20))
    except (TypeError, ValueError):
        n = 3
    try:
        for _ in range(n):
            pyautogui.press("volumedown")
        return f"🔉 Volume -{n}"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_media_mute() -> str:
    return _press("volumemute", "🔇 Mute")


# ----- YouTube Music -----
def action_youtube_music_shuffle() -> str:
    try:
        webbrowser.open_new_tab("https://music.youtube.com/shuffle")
        return "🎵 YouTube Music em shuffle"
    except webbrowser.Error:
        webbrowser.open_new_tab("https://music.youtube.com")
        return "🎵 YouTube Music aberto"


def _auto_scrobble(artist: str, track: str, album: str | None = None) -> None:
    """Se houver sessão Last.fm, marca como now-playing e agenda scrobble."""
    if not (_lastfm.has_session() and artist and track):
        return
    try:
        _lastfm.action_lastfm_now_playing_set(artist, track, album)
    except Exception:
        pass

    def delayed() -> None:
        time.sleep(35)
        try:
            _lastfm.action_lastfm_scrobble(artist, track, album)
        except Exception:
            pass

    threading.Thread(target=delayed, daemon=True).start()


def action_yt_music_play(query: str) -> str:
    """Procura e abre directamente a primeira música no YT Music."""
    if not query or not query.strip():
        return "❌ Diz o que queres tocar"
    q = query.strip()
    yt = _yt()
    if yt:
        try:
            results = yt.search(q, filter="songs", limit=1)
            if results:
                top = results[0]
                video_id = top.get("videoId")
                titulo = top.get("title", q)
                artistas_lista = [a.get("name", "") for a in top.get("artists", []) if a.get("name")]
                artistas = ", ".join(artistas_lista)
                album = top.get("album", {}).get("name") if isinstance(top.get("album"), dict) else None
                if video_id:
                    webbrowser.open_new_tab(f"https://music.youtube.com/watch?v={video_id}")
                    artista_principal = artistas_lista[0] if artistas_lista else ""
                    if artista_principal:
                        _auto_scrobble(artista_principal, titulo, album)
                    sufixo = f" — {artistas}" if artistas else ""
                    scrobble_marca = " 📡" if _lastfm.has_session() else ""
                    return f"🎶 A tocar: {titulo}{sufixo}{scrobble_marca}"
        except Exception:
            pass
    url = f"https://music.youtube.com/search?q={urllib.parse.quote(q)}"
    webbrowser.open_new_tab(url)
    return f"🔍 YT Music: {q}"


def action_yt_music_search(query: str, tipo: str = "songs", limite: int = 5) -> str:
    if not query or not query.strip():
        return "❌ Indica o que procurar"
    q = query.strip()
    if not YTMUSIC_AVAILABLE:
        webbrowser.open_new_tab(f"https://music.youtube.com/search?q={urllib.parse.quote(q)}")
        return f"🔍 YT Music aberto (instala ytmusicapi para listar aqui): {q}"
    try:
        n = max(1, min(int(limite), 15))
    except (TypeError, ValueError):
        n = 5
    filtros_validos = {"songs", "videos", "albums", "artists", "playlists"}
    f = (tipo or "songs").lower()
    if f not in filtros_validos:
        f = "songs"
    yt = _yt()
    if not yt:
        return "❌ ytmusicapi indisponível"
    try:
        results = yt.search(q, filter=f, limit=n)
    except Exception as e:
        return f"❌ YT Music: {e}"
    if not results:
        return f"📭 Sem resultados para '{q}'"
    icone = {"songs": "🎵", "videos": "🎬", "albums": "💿",
             "artists": "🎤", "playlists": "📜"}[f]
    linhas = [f"{icone} {f.title()} para '{q}':"]
    for i, r in enumerate(results[:n], 1):
        titulo = r.get("title") or r.get("artist") or r.get("name", "(?)")
        artistas = ", ".join(a.get("name", "") for a in r.get("artists", []) if a.get("name"))
        extra = f" — {artistas}" if artistas else ""
        linhas.append(f"  {i}. {titulo}{extra}")
    return "\n".join(linhas)


def action_yt_music_playlist(nome: str) -> str:
    if not nome or not nome.strip():
        return "❌ Indica o nome da playlist"
    q = nome.strip()
    yt = _yt()
    if yt:
        try:
            results = yt.search(q, filter="playlists", limit=1)
            if results:
                top = results[0]
                pid = top.get("browseId") or top.get("playlistId")
                titulo = top.get("title", q)
                if pid:
                    pid_clean = pid[2:] if pid.startswith("VL") else pid
                    webbrowser.open_new_tab(f"https://music.youtube.com/playlist?list={pid_clean}")
                    return f"📜 Playlist: {titulo}"
        except Exception:
            pass
    webbrowser.open_new_tab(
        f"https://music.youtube.com/search?q={urllib.parse.quote(q)}#playlists"
    )
    return f"🔍 Playlists para '{q}'"


def action_yt_music_artist(nome: str) -> str:
    if not nome or not nome.strip():
        return "❌ Indica o artista"
    q = nome.strip()
    yt = _yt()
    if yt:
        try:
            results = yt.search(q, filter="artists", limit=1)
            if results:
                top = results[0]
                bid = top.get("browseId")
                nome_a = top.get("artist") or top.get("title", q)
                if bid:
                    webbrowser.open_new_tab(f"https://music.youtube.com/channel/{bid}")
                    return f"🎤 Artista: {nome_a}"
        except Exception:
            pass
    webbrowser.open_new_tab(
        f"https://music.youtube.com/search?q={urllib.parse.quote(q)}"
    )
    return f"🔍 Artista: {q}"


def action_yt_music_radio(seed: str) -> str:
    """Abre uma rádio infinita no YT Music a partir de uma música."""
    if not seed or not seed.strip():
        return "❌ Diz a música base para a rádio"
    q = seed.strip()
    yt = _yt()
    if yt:
        try:
            results = yt.search(q, filter="songs", limit=1)
            if results:
                top = results[0]
                video_id = top.get("videoId")
                titulo = top.get("title", q)
                if video_id:
                    url = (
                        f"https://music.youtube.com/watch?v={video_id}"
                        f"&list=RDAMVM{video_id}"
                    )
                    webbrowser.open_new_tab(url)
                    return f"📻 Rádio baseada em: {titulo}"
        except Exception:
            pass
    webbrowser.open_new_tab(
        f"https://music.youtube.com/search?q={urllib.parse.quote(q)}"
    )
    return f"🔍 YT Music: {q} (rádio precisa de ytmusicapi)"


def action_yt_music_recommendations(seed: str | None = None, limite: int = 8) -> str:
    """Devolve recomendações; se for dado um termo, baseia-se nele,
    senão usa a homepage de descobertas do YT Music."""
    if not YTMUSIC_AVAILABLE:
        webbrowser.open_new_tab("https://music.youtube.com")
        return "🎵 Abri o YT Music — instala ytmusicapi para ver recomendações no terminal"
    yt = _yt()
    if not yt:
        return "❌ ytmusicapi indisponível"
    try:
        n = max(1, min(int(limite), 20))
    except (TypeError, ValueError):
        n = 8
    try:
        if seed and seed.strip():
            songs = yt.search(seed.strip(), filter="songs", limit=1)
            if not songs:
                return f"📭 Sem músicas para '{seed}'"
            video_id = songs[0].get("videoId")
            if not video_id:
                return "❌ Não consegui obter ID base"
            watch = yt.get_watch_playlist(videoId=video_id, limit=n + 1)
            tracks = watch.get("tracks", [])[1:n + 1]
            base = songs[0].get("title", seed)
            cabec = f"🎼 Parecido com '{base}':"
        else:
            home = yt.get_home(limit=3)
            tracks = []
            for sec in home:
                for c in sec.get("contents", []):
                    if isinstance(c, dict) and c.get("videoId"):
                        tracks.append(c)
                    if len(tracks) >= n:
                        break
                if len(tracks) >= n:
                    break
            cabec = "🏠 Descobertas no YT Music:"
    except Exception as e:
        return f"❌ YT Music: {e}"
    if not tracks:
        return "📭 Sem recomendações de momento"
    linhas = [cabec]
    for i, t in enumerate(tracks[:n], 1):
        titulo = t.get("title", "(?)")
        artistas = ", ".join(a.get("name", "") for a in t.get("artists", []) if a.get("name"))
        extra = f" — {artistas}" if artistas else ""
        linhas.append(f"  {i}. {titulo}{extra}")
    return "\n".join(linhas)
