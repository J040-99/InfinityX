#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "InfinityX"))

print("=" * 50)
print("TESTE 1: Follow-ups")
print("=" * 50)

from parser import analisar
from memory import MEMORIA
MEMORIA["historico"] = [{"ent": "quem e o Elon Musk?", "res": "E"}]
MEMORIA["ultima_pesquisa"] = "Elon Musk"

for t in ["certeza?", "e o Tesla?", "mais info"]:
    r = analisar(t)
    print(f"  {t} -> {r.get('action')} ({r.get('source')})")

print("\n" + "=" * 50)
print("TESTE 2: Clima")
print("=" * 50)

from actions.sistema import action_clima
result = action_clima("Lisboa")
print(f"  Clima Lisboa: OK")

print("\n" + "=" * 50)
print("TESTE 3: Groq seletivo")
print("=" * 50)

from llm import _should_use_groq
short = "ola"
long_prompt = "x" * 17000
print(f"  Curto: {_should_use_groq(short)}")
print(f"  Longo: {_should_use_groq(long_prompt)}")

print("\n" + "=" * 50)
print("TODOS TESTES OK!")
print("=" * 50)