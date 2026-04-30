"""Ações sobre ficheiros e pastas: listar, organizar, procurar, info, limpar, criar."""

import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from memory import MEMORIA
from utils import categorize_file, get_user_home, resolve_path


def action_listar(folder: str = ".") -> str:
    path, ok, _ = resolve_path(folder)
    if not ok:
        return f"Pasta não encontrada: {folder}"
    try:
        files = [f.name for f in path.iterdir() if f.is_file()][:25]
        dirs = [f.name for f in path.iterdir() if f.is_dir()][:5]
        r = f"{path.name} ({len(files)} arquivos)"
        if files:
            r += "\n" + "\n".join(f"- {x}" for x in files)
        if dirs:
            r += f"\n\nPastas: {', '.join(dirs)}"
        MEMORIA["ultima_pasta"] = str(path)
        return r if files or dirs else "Pasta vazia."
    except PermissionError:
        return "Sem permissão."
    except OSError as e:
        return f"Erro: {e}"


def action_organizar(folder: str = ".", executar: bool = False) -> str:
    path, ok, _ = resolve_path(folder)
    if not ok:
        return f"Pasta não encontrada: {folder}"
    try:
        grouped = defaultdict(list)
        for f in path.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                grouped[categorize_file(f.name)].append(f.name)
        if not grouped:
            return "Nada pra organizar."
        if not executar:
            total = sum(len(v) for v in grouped.values())
            linhas = [f"{path.name} ({total} arquivos):"]
            for cat in sorted(grouped):
                linhas.append(f"  {cat} ({len(grouped[cat])})")
            linhas.append("\nDiga 'organizar [pasta]' pra valer.")
            return "\n".join(linhas)
        moved = 0
        for cat, itens in grouped.items():
            tgt = path / cat
            tgt.mkdir(exist_ok=True)
            for fn in itens:
                try:
                    src, dst = path / fn, tgt / fn
                    if dst.exists():
                        name, ext = os.path.splitext(fn)
                        dst = tgt / f"{name}_{moved}{ext}"
                    shutil.move(str(src), str(dst))
                    moved += 1
                except OSError:
                    pass
        MEMORIA["ultima_pasta"] = str(path)
        return f"Organizei {moved} arquivos em {len(grouped)} pastas."
    except OSError as e:
        return f"Erro: {e}"


def action_search_files(query: str, folder: str | None = None, ext: str | None = None) -> str:
    if not folder:
        base = get_user_home()
    else:
        base, ok, _ = resolve_path(folder)
        if not ok:
            return f"❌ Pasta não encontrada: {folder}"
    results, query_lower = [], query.lower()
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if query_lower in f.lower() and (not ext or f.lower().endswith(ext.lower())):
                full_path = os.path.join(root, f)
                try:
                    size = os.path.getsize(full_path) / 1024
                except OSError:
                    continue
                results.append(f"• {f} ({size:.1f}KB) - {root}")
                if len(results) >= 15:
                    break
        if len(results) >= 15:
            break
    if not results:
        return f"🔍 Nenhum arquivo encontrado com '{query}'"
    return (
        f"🔍 Resultados para '{query}' ({len(results)}):\n"
        + "\n".join(results[:10])
        + ("..." if len(results) > 10 else "")
    )


def action_file_info(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"❌ Arquivo não encontrado: {path}"
        stat = p.stat()
        size = (
            f"{stat.st_size / (1024 ** 2):.2f} MB"
            if stat.st_size >= 1024 ** 2
            else f"{stat.st_size / 1024:.1f} KB"
        )
        return (
            f"📄 {p.name}\n"
            f"• Tamanho: {size}\n"
            f"• Tipo: {p.suffix or 'Sem extensão'}\n"
            f"• Modificado: {datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M')}\n"
            f"• Caminho: {p.absolute()}"
        )
    except OSError as e:
        return f"❌ Erro: {e}"


def action_cleanup_temp() -> str:
    try:
        import tempfile
        temp_dir = tempfile.gettempdir()
        deleted, freed = 0, 0
        for f in Path(temp_dir).iterdir():
            try:
                if f.is_file():
                    size = f.stat().st_size
                    f.unlink()
                    deleted += 1
                    freed += size
            except OSError:
                pass
        return f"🧹 Limpeza: {deleted} arquivos removidos, {freed / (1024 * 1024):.2f} MB liberados"
    except OSError as e:
        return f"❌ Erro: {e}"


def action_criar_arquivo(nome: str, conteudo: str = "", pasta: str = ".") -> str:
    try:
        path = Path(pasta) if pasta != "." else Path.cwd()
        if not path.exists():
            path = Path.home()
        if not nome.endswith('.txt'):
            nome += '.txt'
        arquivo = path / nome
        arquivo.write_text(conteudo, encoding='utf-8')
        return f"✅ Arquivo criado: {arquivo.absolute()}"
    except OSError as e:
        return f"❌ Erro: {e}"
