"""Ações de sistema: hora, info do SO, clima, bateria, rede, disco."""

import json
import os
import platform
import socket
import sys
import urllib.parse
import urllib.request
from datetime import datetime
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


def action_clima(cidade: str | None = None, amanha: bool = False) -> str:
    if not cidade:
        cidade = get_localizacao_atual()
    if not cidade:
        cidade = "São Paulo"
    if amanha:
        return f"🌤️ Amanhã em {cidade}: use 'previsão 7 dias' para ver a previsão completa"
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
