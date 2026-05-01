import sys
sys.path.insert(0, ".")
from parser import analisar

print("TESTE: Acoes do Sistema")
for entradas in ["abre chrome", "meu ip", "espaco em disco"]:
    r = analisar(entradas)
    print(f"  {entradas} -> action={r.get('action')}")

print("\nFIM TESTES")