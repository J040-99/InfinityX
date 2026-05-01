"""Ações de sistema: hora, info do SO, clima, bateria, rede, disco."""

import json
import os
import platform
import socket
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta


def _estado_clima(code: int) -> str:
    """Converte código WMO para estado do tempo."""
    codigos = {
        0: "Céu limpo", 1: "Maioritariamente limpo", 2: "Parcialmente nublado", 3: "Nublado",
        45: "Nevoeiro", 48: "Nevoeiro",
        51: "Garoa leve", 53: "Garoa", 55: "Garoa intensa",
        61: "Chuva leve", 63: "Chuva", 65: "Chuva intensa",
        71: "Neve leve", 73: "Neve", 75: "Neve intensa",
        80: "Chuva leve", 81: "Chuva", 82: "Chuva intensa",
        95: "Trovoada", 96: "Trovoada com granizo", 99: "Trovoada com granizo",
    }
    return codigos.get(code, f"Código {code}")
from pathlib import Path
from urllib.error import URLError

from config import OPENWEATHERMAP_API_KEY, PSUTIL_AVAILABLE

if PSUTIL_AVAILABLE:
    import psutil


def action_hora(mes: str = None) -> str:
    if mes:
        return mes
    n = datetime.now()
    return f"{n.strftime('%d/%m/%Y')} às {n.strftime('%H:%M')}"


def action_sysinfo() -> str:
    try:
        user = os.getlogin()
    except OSError:
        user = os.environ.get("USER") or os.environ.get("USERNAME", "?")
    return f"{platform.system()} {platform.release()} | {user}"


def get_localizacao_atual() -> str | None:
    try:
        with urllib.request.urlopen("http://ip-api.com/json/?fields=city", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("city", "")
    except (URLError, json.JSONDecodeError, OSError):
        return None


def _previsao_openweather(cidade: str, dias_a_frente: int = 1) -> str:
    """Previsão via API forecast (5 dias / 3h). Devolve média do dia alvo.

    dias_a_frente=1 → amanhã. Para 'previsão 7 dias' o OpenWeather grátis só
    devolve 5; mostramos os primeiros disponíveis depois de hoje.
    """
    if not OPENWEATHERMAP_API_KEY:
        return "❌ Sem OPENWEATHERMAP_API_KEY configurada para previsão"
    try:
        cidade_encoded = urllib.parse.quote(cidade.strip())
        url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            f"?q={cidade_encoded}&appid={OPENWEATHERMAP_API_KEY}"
            "&units=metric&lang=pt"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, KeyError, OSError) as e:
        return f"❌ Erro previsão: {e}"

    hoje = datetime.now().date()
    por_dia: dict = {}
    for item in data.get("list", []):
        try:
            ts = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
        d = ts.date()
        if d <= hoje:
            continue
        por_dia.setdefault(d, []).append(item)

    if not por_dia:
        return f"📭 Sem previsão disponível para {cidade}"

    # Caso 'amanhã': escolhe o slot mais próximo do meio-dia
    if dias_a_frente == 1:
        amanha = hoje + timedelta(days=1)
        slots = por_dia.get(amanha)
        if not slots:
            primeira_data = sorted(por_dia)[0]
            slots = por_dia[primeira_data]
        slot = min(slots, key=lambda x: abs(
            datetime.strptime(x["dt_txt"], "%Y-%m-%d %H:%M:%S").hour - 12
        ))
        temp = slot["main"]["temp"]
        tmax = max(s["main"]["temp_max"] for s in slots)
        tmin = min(s["main"]["temp_min"] for s in slots)
        desc = slot["weather"][0]["description"]
        hum = slot["main"]["humidity"]
        dia_str = datetime.strptime(slot["dt_txt"], "%Y-%m-%d %H:%M:%S").strftime("%d/%m")
        return (
            f"🌤️ {cidade} — amanhã ({dia_str}): {temp:.1f}°C "
            f"(min {tmin:.1f} / max {tmax:.1f}) — {desc} (humidade {hum}%)\n"
            f"Fonte: OpenWeatherMap"
        )

    # Vários dias: mostra um sumário por dia
    dias_ordenados = sorted(por_dia)[:dias_a_frente]
    linhas = [f"🌤️ Previsão {cidade} — próximos {len(dias_ordenados)} dias:"]
    for d in dias_ordenados:
        slots = por_dia[d]
        tmax = max(s["main"]["temp_max"] for s in slots)
        tmin = min(s["main"]["temp_min"] for s in slots)
        meio = min(slots, key=lambda x: abs(
            datetime.strptime(x["dt_txt"], "%Y-%m-%d %H:%M:%S").hour - 12
        ))
        desc = meio["weather"][0]["description"]
        linhas.append(f" • {d.strftime('%d/%m')}: {tmin:.1f}–{tmax:.1f}°C, {desc}")
    linhas.append(f"\nFonte: OpenWeatherMap")
    return "\n".join(linhas)


def action_clima(cidade: str | None = None, amanha: bool = False, dias: int = 0, atual: bool = False) -> str:
    if not cidade:
        cidade = get_localizacao_atual()
    if not cidade:
        cidade = "Torres Vedras"
    
    if dias > 1 or dias == 7:
        return _clima_openmeteo_semana(cidade)
    elif amanha:
        return _clima_openmeteo_amanha(cidade)
    else:
        return _clima_openmeteo_atual(cidade)


def _clima_openmeteo_atual(cidade: str) -> str:
    import urllib.request
    import json
    from datetime import datetime
    
    coords = {"Torres Vedras": (39.0, -9.3), "Lisboa": (38.7, -9.1), "Porto": (41.15, -8.61)}
    lat, lon = coords.get(cidade, (39.0, -9.3))
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        current = data.get("current", {})
        temp = current.get("temperature_2m")
        hum = current.get("relative_humidity_2m")
        feels = current.get("apparent_temperature")
        wind = current.get("wind_speed_10m")
        code = current.get("weather_code")
        
        estado = _estado_clima(code)
        
        linhas = [f"🌤️ Atual - {cidade}"]
        linhas.append(f"Temperatura: {temp:.1f}°C")
        linhas.append(f"Sensação: {feels:.1f}°C")
        linhas.append(f"Estado: {estado}")
        linhas.append(f"Humidade: {hum}%")
        linhas.append(f"Vento: {wind:.0f} km/h")
        linhas.append(f"\nFonte: Open-Meteo")
        
        _guardar_clima_historico(cidade, temp, hum, wind, estado)
        
        return "\n".join(linhas)
    except:
        pass
    
    return f"Temperatura: --\nLocal: {cidade}\nFonte: Open-Meteo"


def _guardar_clima_historico(cidade: str, temp: float, hum: int, wind: float, estado: str) -> None:
    """Guarda dados do clima no histórico."""
    from memory import MEMORIA
    from datetime import datetime
    
    if "clima_historico" not in MEMORIA:
        MEMORIA["clima_historico"] = []
    
    entrada = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cidade": cidade,
        "temp": temp,
        "hum": hum,
        "wind": wind,
        "estado": estado,
    }
    
    MEMORIA["clima_historico"].append(entrada)
    
    if len(MEMORIA["clima_historico"]) > 168:
        MEMORIA["clima_historico"] = MEMORIA["clima_historico"][-168:]


def _clima_openmeteo_amanha(cidade: str) -> str:
    import urllib.request
    import json
    from datetime import datetime, timedelta
    
    coords = {"Torres Vedras": (39.0, -9.3), "Lisboa": (38.7, -9.1), "Porto": (41.15, -8.61)}
    lat, lon = coords.get(cidade, (39.0, -9.3))
    
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,weather_code&start_date={amanha}&end_date={amanha}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        daily = data.get("daily", {})
        tmax = daily.get("temperature_2m_max", [None])[0]
        tmin = daily.get("temperature_2m_min", [None])[0]
        code = daily.get("weather_code", [0])[0]
        
        if tmax is None:
            return "Amanhã: sem dados"
        
        estado = _estado_clima(code)
        dia = amanha[8:] + "/" + amanha[5:7]
        return f"🌤️ Amanhã ({dia}) - {cidade}\nTemperatura: {tmin:.0f}°C / {tmax:.0f}°C\nEstado: {estado}\nFonte: Open-Meteo"
    except:
        return "Amanhã: erro"


def _clima_openmeteo_semana(cidade: str) -> str:
    import urllib.request
    import json
    from datetime import datetime, timedelta
    
    coords = {"Torres Vedras": (39.0, -9.3), "Lisboa": (38.7, -9.1), "Porto": (41.15, -8.61)}
    lat, lon = coords.get(cidade, (39.0, -9.3))
    
    hoje = datetime.now()
    inicio = hoje.strftime("%Y-%m-%d")
    fim = (hoje + timedelta(days=6)).strftime("%Y-%m-%d")
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,weather_code&start_date={inicio}&end_date={fim}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        daily = data.get("daily", {})
        datas = daily.get("time", [])
        tmax = daily.get("temperature_2m_max", [])
        tmin = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        
        linhas = [f"📅 Previsão 7 dias - {cidade}:"]
        for i in range(min(7, len(datas))):
            dia = datas[i][8:] + "/" + datas[i][5:7]
            estado = _estado_clima(codes[i])
            linhas.append(f"  • {dia}: {tmin[i]:.0f}°C / {tmax[i]:.0f}°C | {estado}")
        
        linhas.append(f"\nFonte: Open-Meteo")
        return "\n".join(linhas)
    except:
        return "Previsão: erro"
    if amanha or dias:
        if OPENWEATHERMAP_API_KEY and dias and dias > 1:
            return _previsao_openweather(cidade, dias_a_frente=min(dias, 5))
        if OPENWEATHERMAP_API_KEY and amanha:
            try:
                return _previsao_openweather(cidade, dias_a_frente=1)
            except Exception:
                pass
        # Fallback pesquisa web
        return _clima_pesquisa_simples(cidade, False, amanha, dias)
    
    # Clima atual - tenta API, se falhar usa pesquisa web
    if OPENWEATHERMAP_API_KEY:
        try:
            cidade_encoded = urllib.parse.quote(cidade.strip())
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?q={cidade_encoded}&appid={OPENWEATHERMAP_API_KEY}&units=metric&lang=pt"
            )
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                temp = data["main"]["temp"]
                feels = data["main"]["feels_like"]
                desc = data["weather"][0]["description"]
                hum = data["main"]["humidity"]
                return f"{cidade}: {temp:.1f}°C (sensação {feels:.1f}°C) - {desc} (umidade {hum}%)"
        except (URLError, json.JSONDecodeError, KeyError, OSError, Exception):
            pass
    
    # Fallback: pesquisa web com formato simples
    return _clima_pesquisa_simples(cidade, atual, False, 0)


def _clima_pesquisa_simples(cidade: str, atual: bool = False, amanha: bool = False, dias: int = 0) -> str:
    """Pesquisa clima com fallback."""
    from actions.web import action_browser_search
    import re
    
    query = f"{cidade} Portugal temperatura"
    resultado = action_browser_search(query)
    
    linhas = []
    
    temps = re.findall(r'(\d+)[°º]C', resultado)
    if temps:
        linhas.append(f"Temperatura: {temps[0]}°C")
        linhas.append(f"(dados aproximados)")
    else:
        linhas.append("Temperatura: --")
        linhas.append("(sem dados disponíveis)")
    
    linhas.append(f"\nLocal: {cidade}")
    linhas.append(f"Fonte: Web")
    
    return "\n".join(linhas)


def action_battery_status() -> str:
    if not PSUTIL_AVAILABLE:
        return "ℹ️ Instale psutil para status da bateria"
    try:
        battery = psutil.sensors_battery()
        if battery:
            status = "🔌 Carregando" if battery.power_plugged else "🔋 Usando bateria"
            remaining = (
                "" if battery.secsleft == psutil.POWER_TIME_UNLIMITED
                else f" ({battery.secsleft // 60}min)"
            )
            return f"{status}: {battery.percent}%{remaining}"
        return "ℹ️ Bateria não detectada"
    except (AttributeError, OSError):
        return "❌ Não foi possível ler status da bateria"


def action_network_info() -> str:
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=3) as resp:
                public_ip = resp.read().decode()
        except URLError:
            public_ip = "Não disponível"
        return f"🌐 Rede:\n• Local: {local_ip}\n• Público: {public_ip}"
    except OSError as e:
        return f"❌ Erro: {e}"


def action_disk_usage(drive: str | None = None) -> str:
    if not PSUTIL_AVAILABLE:
        return "ℹ️ Instale psutil para info de disco"
    try:
        if not drive:
            drive = str(Path.home().anchor)
            if not drive:
                drive = "C:\\" if sys.platform == "win32" else "/"
        usage = psutil.disk_usage(drive)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        bar = "█" * int(usage.percent / 5) + "░" * (20 - int(usage.percent / 5))
        return (
            f"💾 {drive}:\n[{bar}] {usage.percent:.0f}%\n"
            f"• Usado: {used_gb:.1f}GB\n• Livre: {free_gb:.1f}GB"
        )
    except OSError as e:
        return f"❌ Erro: {e}"

# --- Ações de Controlo de Interface Gráfica (GUI) ---

from config import SYSTEM_AUTO_AVAILABLE

if SYSTEM_AUTO_AVAILABLE:
    import pyautogui

def action_click(x: int = None, y: int = None, clicks: int = 1, button: str = 'left') -> str:
    """Clica numa coordenada específica ou na posição atual do rato."""
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Controlo de GUI não disponível (pyautogui não instalado)."
    
    try:
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, clicks=clicks, button=button)
            return f"✅ Clique {button} em ({x}, {y}) realizado."
        else:
            pyautogui.click(clicks=clicks, button=button)
            return f"✅ Clique {button} na posição atual realizado."
    except Exception as e:
        return f"❌ Erro ao clicar: {e}"

def action_type_text(texto: str, interval: float = 0.1) -> str:
    """Escreve texto como se fosse digitado no teclado."""
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Controlo de GUI não disponível."
    
    try:
        pyautogui.write(texto, interval=interval)
        return f"✅ Texto digitado: '{texto[:20]}...'"
    except Exception as e:
        return f"❌ Erro ao digitar: {e}"

def action_press_key(key: str) -> str:
    """Pressiona uma tecla ou combinação de teclas (ex: 'enter', 'ctrl', 'c')."""
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Controlo de GUI não disponível."
    
    try:
        # Suporta combinações simples separadas por '+'
        keys = key.split('+')
        if len(keys) > 1:
            pyautogui.hotkey(*[k.strip() for k in keys])
        else:
            pyautogui.press(key)
        return f"✅ Tecla(s) pressionada(s): {key}"
    except Exception as e:
        return f"❌ Erro ao pressionar tecla: {e}"

def action_move_mouse(x: int, y: int, duration: float = 0.5) -> str:
    """Move o rato para uma coordenada específica."""
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Controlo de GUI não disponível."
    
    try:
        pyautogui.moveTo(x, y, duration=duration)
        return f"✅ Rato movido para ({x}, {y})."
    except Exception as e:
        return f"❌ Erro ao mover rato: {e}"

def action_screenshot(nome: str = "screenshot.png") -> str:
    """Tira uma captura de ecrã e guarda-a."""
    if not SYSTEM_AUTO_AVAILABLE:
        return "❌ Controlo de GUI não disponível."
    
    try:
        path = f"data/{nome}"
        os.makedirs("data", exist_ok=True)
        pyautogui.screenshot(path)
        return f"✅ Captura de ecrã guardada em: {path}"
    except Exception as e:
        return f"❌ Erro ao tirar captura de ecrã: {e}"

def action_window_control(app_name: str, action: str = "focus") -> str:
    """Controla janelas de aplicações (focus, minimize, maximize, close)."""
    # Nota: O controlo de janelas nativo varia por SO. 
    # Esta é uma implementação simplificada usando comandos de sistema.
    import platform
    import subprocess
    
    try:
        system = platform.system()
        if system == "Windows":
            # Exemplo simplificado para Windows usando powershell
            if action == "focus":
                cmd = f"powershell -command \"$wshell = New-Object -ComObject WScript.Shell; $wshell.AppActivate('{app_name}')\""
                subprocess.run(cmd, shell=True)
                return f"✅ Tentativa de focar na janela: {app_name}"
        elif system == "Linux":
            # Requer xdotool no Linux
            if action == "focus":
                subprocess.run(["xdotool", "search", "--name", app_name, "windowactivate"], check=False)
                return f"✅ Tentativa de focar na janela (xdotool): {app_name}"
        
        return f"⚠️ Ação '{action}' em '{app_name}' enviada (suporte limitado por SO)."
    except Exception as e:
        return f"❌ Erro no controlo de janela: {e}"
