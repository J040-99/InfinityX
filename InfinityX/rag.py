"""Módulo de Memória de Longo Prazo (RAG Local) para a InfinityX.

Este módulo permite indexar e recuperar informações de conversas passadas,
notas e documentos de forma semântica (mesmo que simplificada para execução local).
"""

import os
import json
import re
from typing import List, Dict, Any
from pathlib import Path

# Caminho para o índice da memória de longo prazo
RAG_INDEX_FILE = Path("/home/ubuntu/InfinityX/InfinityX/data/rag_index.json")

def _limpar_texto(texto: str) -> str:
    """Limpa o texto para indexação básica."""
    texto = texto.lower()
    texto = re.sub(r'[^\w\s]', ' ', texto)
    return texto

def indexar_conteudo(conteudo: str, metadados: Dict[str, Any] = None):
    """Adiciona conteúdo ao índice da memória de longo prazo."""
    if not conteudo or len(conteudo.strip()) < 10:
        return

    index = []
    if RAG_INDEX_FILE.exists():
        try:
            with open(RAG_INDEX_FILE, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Evita duplicados exatos
    conteudo_limpo = _limpar_texto(conteudo)
    if any(e["limpo"] == conteudo_limpo for e in index):
        return

    # Cria uma entrada no índice
    entrada = {
        "conteudo": conteudo,
        "limpo": conteudo_limpo,
        "metadados": metadados or {},
        "timestamp": metadados.get("timestamp") if metadados else None
    }
    
    index.append(entrada)
    
    # Mantém apenas as últimas 1000 entradas para performance local
    if len(index) > 1000:
        index = index[-1000:]

    # Garante que a pasta data existe
    RAG_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(RAG_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

def indexar_ficheiro(caminho: str):
    """Lê e indexa o conteúdo de um ficheiro local (TXT, MD, CSV)."""
    path = Path(caminho)
    if not path.exists() or not path.is_file():
        return f"❌ Ficheiro não encontrado: {caminho}"
    
    ext = path.suffix.lower()
    try:
        if ext in [".txt", ".md", ".py", ".js", ".html", ".css"]:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()
        elif ext == ".csv":
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = "Conteúdo CSV:\n" + f.read()
        else:
            return f"❌ Extensão não suportada para indexação direta: {ext}"
            
        # Divide em chunks se for muito grande
        chunks = [conteudo[i:i+2000] for i in range(0, len(conteudo), 1500)]
        for i, chunk in enumerate(chunks):
            indexar_conteudo(chunk, {"fonte": caminho, "tipo": "ficheiro", "chunk": i})
            
        return f"✅ Ficheiro indexado com sucesso: {path.name} ({len(chunks)} partes)"
    except Exception as e:
        return f"❌ Erro ao indexar ficheiro: {e}"

def recuperar_contexto(query: str, limite: int = 3) -> str:
    """Recupera os trechos de informação mais relevantes para a query."""
    if not RAG_INDEX_FILE.exists():
        return ""

    try:
        with open(RAG_INDEX_FILE, 'r', encoding='utf-8') as f:
            index = json.load(f)
    except (json.JSONDecodeError, IOError):
        return ""

    query_limpa = _limpar_texto(query)
    termos_query = set(query_limpa.split())
    
    if not termos_query:
        return ""

    # Sistema de pontuação simplificado baseado em sobreposição de palavras-chave
    resultados = []
    for entrada in index:
        termos_entrada = set(entrada["limpo"].split())
        sobreposicao = len(termos_query.intersection(termos_entrada))
        if sobreposicao > 0:
            # Pontuação ponderada pela sobreposição e recência (opcional)
            resultados.append((sobreposicao, entrada["conteudo"]))

    # Ordena por pontuação (descendente) e pega os melhores
    resultados.sort(key=lambda x: x[0], reverse=True)
    melhores = [r[1] for r in resultados[:limite]]
    
    if not melhores:
        return ""
        
    contexto = "\n---\n".join(melhores)
    return f"\n[MEMÓRIA DE LONGO PRAZO]:\n{contexto}\n"
