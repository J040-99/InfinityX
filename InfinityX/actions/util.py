"""Ferramentas utilitárias diversas: conversões, geradores, codificações, texto, cores."""

import base64 as _base64
import hashlib
import json
import os
import random
import re
import secrets
import socket
import string
import time
import urllib.parse
import urllib.request
import uuid
from urllib.error import URLError


# ----- Conversões -----
def action_convert(value: float, from_unit: str, to_unit: str) -> str:
    conversions = {
        ('c', 'f'): lambda x: x * 9 / 5 + 32, ('f', 'c'): lambda x: (x - 32) * 5 / 9,
        ('km', 'mi'): lambda x: x * 0.621371, ('mi', 'km'): lambda x: x * 1.60934,
        ('kg', 'lb'): lambda x: x * 2.20462, ('lb', 'kg'): lambda x: x * 0.453592,
    }
    key = (from_unit.lower(), to_unit.lower())
    if key in conversions:
        return f"🔄 {value} {from_unit} = {conversions[key](value):.2f} {to_unit}"
    if from_unit.lower() == to_unit.lower():
        return f"🔄 {value} {from_unit} = {value} {to_unit}"
    return f"❌ Conversão não suportada: {from_unit} → {to_unit}"


def action_currency_convert(amount: float, from_curr: str, to_curr: str) -> str:
    try:
        from_curr, to_curr = from_curr.upper(), to_curr.upper()
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            rates = data.get('rates', {})
            if to_curr in rates:
                result = amount * rates[to_curr]
                return (
                    f"💱 {amount:.2f} {from_curr} = {result:.2f} {to_curr}\n"
                    f"📊 Taxa: 1 {from_curr} = {rates[to_curr]:.4f} {to_curr}"
                )
            return f"❌ Moeda '{to_curr}' não encontrada"
    except (URLError, json.JSONDecodeError, KeyError, OSError) as e:
        return f"❌ Erro: {e}"


def action_translate(text: str, to_lang: str = "en") -> str:
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target=to_lang).translate(text)
        lang_names = {"pt": "Português", "en": "Inglês", "es": "Espanhol", "fr": "Francês", "de": "Alemão"}
        return f"🌐 Tradução ({lang_names.get(to_lang, to_lang)}):\n{translated}"
    except ImportError:
        return "❌ Instale: pip install deep-translator"
    except Exception as e:
        return f"❌ Erro: {e}"


# ----- Geradores -----
def action_generate_password(length: int = 16, special: bool = True) -> str:
    chars = string.ascii_letters + string.digits + ("!@#$%^&*()_+-=" if special else "")
    password = ''.join(secrets.choice(chars) for _ in range(length))
    return f"🔐 Senha:\n`{password}`\n💡 Salve em um gerenciador!"


def action_generate_qr(text: str, filename: str = "qrcode.png") -> str:
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filename)
        return f"📱 QR Code salvo: {os.path.abspath(filename)}"
    except ImportError:
        return "❌ Instale: pip install qrcode[pil]"
    except Exception as e:
        return f"❌ Erro: {e}"


def action_shorten_url(url: str) -> str:
    try:
        api_url = f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}"
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            short = resp.read().decode().strip()
            if short.startswith("http"):
                return f"🔗 Encurtado:\nOriginal: {url}\nCurto: {short}"
            return "❌ Não foi possível encurtar"
    except (URLError, OSError) as e:
        return f"❌ Erro: {e}"


def action_random_dice(sides: int = 6, count: int = 1) -> str:
    rolls = [random.randint(1, sides) for _ in range(count)]
    if count > 1:
        return f"🎲 {' + '.join(map(str, rolls))} = {sum(rolls)}"
    return f"🎲 Resultado: {rolls[0]}"


# ----- Rede e saúde -----
def action_ping(host: str) -> str:
    try:
        start = time.time()
        socket.setdefaulttimeout(5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, 80))
        elapsed = (time.time() - start) * 1000
        return f"🌐 {host}: ✅ Online ({elapsed:.0f}ms)"
    except OSError:
        return f"🌐 {host}: ❌ Offline"


def action_bmi(weight: float, height: float) -> str:
    try:
        height_m = height / 100
        bmi = weight / (height_m ** 2)
        if bmi < 18.5:
            category = "⚠️ Abaixo"
        elif bmi < 25:
            category = "✅ Normal"
        elif bmi < 30:
            category = "⚠️ Sobrepeso"
        else:
            category = "🔴 Obesidade"
        return f"📊 IMC: {bmi:.1f}\n{category}\n💡 Fórmula: peso(kg) / altura(m)²"
    except (ZeroDivisionError, ValueError) as e:
        return f"❌ Erro: {e}"


# ----- Ferramentas para devs -----
def action_uuid_gen(count: int = 1) -> str:
    try:
        n = max(1, min(int(count), 20))
    except (TypeError, ValueError):
        n = 1
    return "\n".join(str(uuid.uuid4()) for _ in range(n))


def action_hash_text(text: str, algo: str = "sha256") -> str:
    if not text:
        return "❌ Texto vazio"
    algo = (algo or "sha256").lower()
    if algo not in {"md5", "sha1", "sha256", "sha512"}:
        return f"❌ Algoritmo desconhecido: {algo}"
    h = hashlib.new(algo, text.encode("utf-8")).hexdigest()
    return f"{algo}: {h}"


def action_base64(text: str, mode: str = "encode") -> str:
    if not text:
        return "❌ Texto vazio"
    try:
        if (mode or "encode").lower().startswith("dec"):
            return _base64.b64decode(text.encode("utf-8")).decode("utf-8", errors="replace")
        return _base64.b64encode(text.encode("utf-8")).decode("ascii")
    except (ValueError, UnicodeError) as e:
        return f"❌ Base64: {e}"


def action_url_codec(text: str, mode: str = "encode") -> str:
    if not text:
        return "❌ Texto vazio"
    if (mode or "encode").lower().startswith("dec"):
        return urllib.parse.unquote(text)
    return urllib.parse.quote(text, safe="")


def action_text_tools(text: str, op: str = "count") -> str:
    if text is None:
        return "❌ Texto vazio"
    op = (op or "count").lower()
    if op == "count":
        chars = len(text)
        chars_no_ws = len(re.sub(r"\s", "", text))
        words = len(text.split())
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        return f"📝 {words} palavras · {chars} caracteres ({chars_no_ws} sem espaços) · {lines} linhas"
    if op == "upper":
        return text.upper()
    if op == "lower":
        return text.lower()
    if op == "title":
        return text.title()
    if op == "reverse":
        return text[::-1]
    if op == "trim":
        return "\n".join(line.strip() for line in text.splitlines())
    if op == "dedupe":
        seen, out = set(), []
        for line in text.splitlines():
            if line not in seen:
                seen.add(line)
                out.append(line)
        return "\n".join(out)
    if op == "sort":
        return "\n".join(sorted(text.splitlines()))
    return f"❌ Operação desconhecida: {op}"


def action_json_format(text: str, indent: int = 2) -> str:
    if not text:
        return "❌ Texto vazio"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return f"❌ JSON inválido: {e.msg} (linha {e.lineno}, col {e.colno})"
    return json.dumps(data, ensure_ascii=False, indent=int(indent or 2), sort_keys=False)


def action_color_convert(value: str) -> str:
    if not value:
        return "❌ Cor vazia"
    v = value.strip().lower().replace("#", "")
    if re.fullmatch(r"[0-9a-f]{6}", v):
        r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
        return f"🎨 #{v} → rgb({r}, {g}, {b})"
    if re.fullmatch(r"[0-9a-f]{3}", v):
        r, g, b = (int(c * 2, 16) for c in v)
        return f"🎨 #{v} → rgb({r}, {g}, {b})"
    m = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", value.strip().lower())
    if m:
        r, g, b = (max(0, min(255, int(x))) for x in m.groups())
        return f"🎨 rgb({r}, {g}, {b}) → #{r:02x}{g:02x}{b:02x}"
    return "❌ Use #RRGGBB, #RGB ou rgb(r, g, b)"


_LOREM_BASE = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
    "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute "
    "irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
    "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia "
    "deserunt mollit anim id est laborum."
)


def action_lorem_ipsum(paragraphs: int = 1) -> str:
    try:
        n = max(1, min(int(paragraphs), 10))
    except (TypeError, ValueError):
        n = 1
    return "\n\n".join(_LOREM_BASE for _ in range(n))
