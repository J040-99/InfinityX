"""Produtividade pessoal: dicionário, todos, timers, notas, lembretes, resumo do dia."""

import ctypes
import json
import os
import threading
import time
from datetime import datetime, timedelta

from config import PSUTIL_AVAILABLE, TODO_FILE
from memory import (
    LEMBRETES,
    NOTAS,
    PALAVRAS,
    TIMERS,
    salvar_lembretes,
    salvar_notas,
    salvar_palavras,
)

from .sistema import action_battery_status, action_clima


# ----- Dicionário pessoal -----
def action_palavras_aprender(palavra: str, significado: str) -> str:
    palavra_lower = palavra.strip().lower()
    PALAVRAS[palavra_lower] = {
        "significado": significado,
        "adicionado": datetime.now().strftime('%d/%m/%Y %H:%M'),
    }
    salvar_palavras()
    return f"📚 Aprendida: '{palavra}' = {significado}"


def action_palavras_procurar(palavra: str) -> str | None:
    palavra_lower = palavra.strip().lower()
    if palavra_lower in PALAVRAS:
        info = PALAVRAS[palavra_lower]
        return f"📖 {palavra}: {info['significado']} (add {info['adicionado']})"
    return None


def action_palavras_listar() -> str:
    if not PALAVRAS:
        return "📚 Nenhuma palavra aprendida ainda!"
    linhas = ["📚 Minhas palavras:"]
    for p, info in list(PALAVRAS.items())[:20]:
        linhas.append(f"• {p}: {info['significado']}")
    return "\n".join(linhas)


def action_palavras_excluir(palavra: str) -> str:
    palavra_lower = palavra.strip().lower()
    if palavra_lower in PALAVRAS:
        del PALAVRAS[palavra_lower]
        salvar_palavras()
        return f"🗑️ Removida: '{palavra}'"
    return f"❌ Palavra '{palavra}' não existe"


# ----- Tarefas -----
def action_todo_add(task: str, priority: str = "medium") -> str:
    try:
        todos = []
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, 'r', encoding='utf-8') as f:
                todos = json.load(f)
        todo = {
            "id": len(todos) + 1, "task": task, "priority": priority,
            "done": False, "created": datetime.now().strftime('%d/%m %H:%M'),
        }
        todos.append(todo)
        with open(TODO_FILE, 'w', encoding='utf-8') as f:
            json.dump(todos, f, ensure_ascii=False, indent=2)
        return f"✅ Tarefa #{todo['id']} adicionada: '{task}' [{priority}]"
    except (OSError, json.JSONDecodeError) as e:
        return f"❌ Erro: {e}"


def action_todo_list(show_done: bool = False) -> str:
    try:
        if not os.path.exists(TODO_FILE):
            return "📋 Nenhuma tarefa cadastrada."
        with open(TODO_FILE, 'r', encoding='utf-8') as f:
            todos = json.load(f)
        filtered = [t for t in todos if show_done or not t['done']]
        if not filtered:
            return "🎉 Todas concluídas!" if not show_done else "📋 Lista vazia."
        lines = ["📋 Suas tarefas:"]
        for t in filtered[:10]:
            status = "✅" if t['done'] else "⏳"
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t['priority'], "⚪")
            lines.append(f"{status} #{t['id']} {prio} {t['task']} ({t['created']})")
        suffix = f"\n... e mais {len(filtered) - 10}" if len(filtered) > 10 else ""
        return "\n".join(lines) + suffix
    except (OSError, json.JSONDecodeError) as e:
        return f"❌ Erro: {e}"


# ----- Timers -----
def action_timer_set(name: str, minutes: int) -> str:
    end_time = datetime.now() + timedelta(minutes=minutes)
    TIMERS[name] = {"end": end_time, "minutes": minutes}

    def alert() -> None:
        while datetime.now() < end_time:
            time.sleep(1)
        print(f"\n🔔 TIMER '{name}' concluído!\n> ", end="", flush=True)
        try:
            ctypes.windll.kernel32.Beep(1000, 500)
        except (AttributeError, OSError):
            pass

    threading.Thread(target=alert, daemon=True).start()
    return f"⏱️ Timer '{name}': {minutes}min (termina {end_time.strftime('%H:%M')})"


# ----- Notas -----
def action_nota_add(texto: str) -> str:
    if not texto or not texto.strip():
        return "❌ Nota vazia"
    NOTAS.append({"texto": texto.strip(), "ts": datetime.now().isoformat(timespec="seconds")})
    salvar_notas()
    return f"📝 Nota guardada (#{len(NOTAS)})"


def action_notas_listar() -> str:
    if not NOTAS:
        return "📭 Sem notas guardadas"
    linhas = []
    for i, n in enumerate(NOTAS, 1):
        ts = n.get("ts", "")[:16].replace("T", " ")
        linhas.append(f"{i}. [{ts}] {n.get('texto', '')}")
    return "📒 Notas:\n" + "\n".join(linhas)


def action_nota_excluir(idx: int) -> str:
    try:
        i = int(idx) - 1
    except (TypeError, ValueError):
        return "❌ Índice inválido"
    if not (0 <= i < len(NOTAS)):
        return f"❌ Não existe nota #{idx}"
    removida = NOTAS.pop(i)
    salvar_notas()
    return f"🗑️ Removida: {removida.get('texto', '')[:60]}"


# ----- Lembretes (com agendador em background) -----
def _parse_quando(quando: str) -> datetime | None:
    """Aceita 'HH:MM', 'YYYY-MM-DD HH:MM', 'DD/MM HH:MM', 'DD/MM/YYYY HH:MM' ou ISO."""
    if not quando:
        return None
    s = quando.strip()
    formatos = [
        "%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%d/%m %H:%M",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in formatos:
        try:
            dt = datetime.strptime(s, fmt)
            agora = datetime.now()
            if fmt == "%H:%M":
                dt = dt.replace(year=agora.year, month=agora.month, day=agora.day)
                if dt <= agora:
                    dt += timedelta(days=1)
            elif fmt == "%d/%m %H:%M":
                dt = dt.replace(year=agora.year)
                if dt <= agora:
                    dt = dt.replace(year=agora.year + 1)
            return dt
        except ValueError:
            continue
    return None


def action_lembrete_add(texto: str, em_min: int | None = None, quando: str | None = None) -> str:
    if not texto or not texto.strip():
        return "❌ Lembrete vazio"
    due: datetime | None = None
    if em_min is not None:
        try:
            due = datetime.now() + timedelta(minutes=int(em_min))
        except (TypeError, ValueError):
            return "❌ 'em_min' inválido"
    elif quando:
        due = _parse_quando(quando)
        if not due:
            return f"❌ Não consegui interpretar '{quando}'. Usa HH:MM ou DD/MM HH:MM."
    else:
        return "❌ Indica em quanto tempo (em_min) ou quando (HH:MM, DD/MM HH:MM)"
    LEMBRETES.append({
        "texto": texto.strip(),
        "due": due.isoformat(timespec="seconds"),
        "notified": False,
    })
    salvar_lembretes()
    return f"⏰ Lembrete agendado para {due.strftime('%d/%m %H:%M')}: {texto.strip()}"


def action_lembretes_listar() -> str:
    if not LEMBRETES:
        return "📭 Sem lembretes ativos"
    agora = datetime.now()
    items = sorted(LEMBRETES, key=lambda x: x.get("due", ""))
    linhas = ["⏰ Lembretes:"]
    for i, l in enumerate(items, 1):
        try:
            due = datetime.fromisoformat(l["due"])
        except (KeyError, ValueError):
            continue
        marca = "✅" if l.get("notified") else ("🔔" if due <= agora else "⏳")
        linhas.append(f"{i}. {marca} {due.strftime('%d/%m %H:%M')} — {l.get('texto', '')}")
    return "\n".join(linhas)


def action_lembrete_excluir(idx: int) -> str:
    try:
        i = int(idx) - 1
    except (TypeError, ValueError):
        return "❌ Índice inválido"
    if not (0 <= i < len(LEMBRETES)):
        return f"❌ Não existe lembrete #{idx}"
    items = sorted(LEMBRETES, key=lambda x: x.get("due", ""))
    alvo = items[i]
    LEMBRETES.remove(alvo)
    salvar_lembretes()
    return f"🗑️ Lembrete removido: {alvo.get('texto', '')[:60]}"


_scheduler_started = False


def iniciar_scheduler_lembretes(intervalo_seg: int = 30) -> None:
    """Arranca uma thread daemon que verifica lembretes vencidos e notifica."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def loop() -> None:
        while True:
            try:
                agora = datetime.now()
                mudou = False
                for l in LEMBRETES:
                    if l.get("notified"):
                        continue
                    try:
                        due = datetime.fromisoformat(l["due"])
                    except (KeyError, ValueError):
                        continue
                    if due <= agora:
                        print(f"\n🔔 LEMBRETE: {l.get('texto', '')}\n> ", end="", flush=True)
                        try:
                            ctypes.windll.kernel32.Beep(880, 400)
                        except (AttributeError, OSError):
                            pass
                        l["notified"] = True
                        mudou = True
                if mudou:
                    salvar_lembretes()
            except Exception:
                pass
            time.sleep(intervalo_seg)

    threading.Thread(target=loop, daemon=True).start()


# ----- Resumo do dia -----
def action_resumo_dia() -> str:
    partes = [f"📅 {datetime.now().strftime('%A, %d/%m/%Y · %H:%M')}"]
    try:
        clima = action_clima(None, False)
        if clima and not clima.startswith("❌"):
            partes.append(clima)
    except Exception:
        pass
    try:
        if PSUTIL_AVAILABLE:
            bat = action_battery_status()
            if bat and not bat.startswith("❌"):
                partes.append(bat)
    except Exception:
        pass
    try:
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, "r", encoding="utf-8") as f:
                todos = json.load(f)
            pendentes = [t for t in todos if not t.get("done")]
            if pendentes:
                top = pendentes[:5]
                partes.append("✅ Pendentes:\n" + "\n".join(f" • {t.get('task','')}" for t in top))
            else:
                partes.append("✅ Sem tarefas pendentes")
    except (IOError, json.JSONDecodeError):
        pass
    if LEMBRETES:
        agora = datetime.now()
        proximos = []
        for l in sorted(LEMBRETES, key=lambda x: x.get("due", "")):
            if l.get("notified"):
                continue
            try:
                due = datetime.fromisoformat(l["due"])
            except (KeyError, ValueError):
                continue
            if due >= agora:
                proximos.append(f" • {due.strftime('%d/%m %H:%M')} — {l.get('texto', '')}")
                if len(proximos) >= 5:
                    break
        if proximos:
            partes.append("⏰ Próximos lembretes:\n" + "\n".join(proximos))
    if NOTAS:
        ultimas = NOTAS[-3:]
        partes.append("📝 Notas recentes:\n" + "\n".join(
            f" • {n.get('texto', '')[:80]}" for n in ultimas
        ))
    return "\n\n".join(partes)
