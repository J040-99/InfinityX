"""Ações de sistema: hora, info do SO, clima, bateria, rede, disco."""

import json
import os
import platform
import socket
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError

from config import OPENWEATHERMAP_API_KEY, PSUTIL_AVAILABLE

if PSUTIL_AVAILABLE:
    import psutil


def action_hora() -> str:
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
            f"(min {tmin:.1f} / max {tmax:.1f}) — {desc} (humidade {hum}%)"
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
    return "\n".join(linhas)


def action_clima(cidade: str | None = None, amanha: bool = False, dias: int = 0) -> str:
    if not cidade:
        cidade = get_localizacao_atual()
    if not cidade:
        cidade = "São Paulo"
    if dias and dias > 1:
        return _previsao_openweather(cidade, dias_a_frente=min(dias, 5))
    if amanha:
        return _previsao_openweather(cidade, dias_a_frente=1)
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
    except (URLError, json.JSONDecodeError, KeyError, OSError) as e:
        return f"Erro clima: {e}"


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
