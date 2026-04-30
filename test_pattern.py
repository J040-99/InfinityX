import re

factual_patterns = [
    r'\bmais rapid[oa]\b', r'\bmais veloz\b', r'\bmaior velocidade\b',
    r'\bmais caro\b', r'\bmais barato\b', r'\bmelhor\b.*\bdo mundo\b',
    r'\bquem é\b', r'\bquem foi\b', r'\bqual é\b', r'\bqual a\b',
    r'\bquanto custa\b', r'\bpreço de\b', r'\bcapital\b',
    r'\brecorde\b', r'\branking\b', r'\bpopulação\b',
    r'\bmais popular\b', r'\bmais vendido\b',
]

texts = [
    "segundo a fonte o mais rápido é o Koenigsegg Jesko Absolut",
    "qual é o carro mais rápido do mundo?",
    "como estás?",
    "mais rápido do mundo"
]

for text in texts:
    print(f"\nTestando: '{text}'")
    e_lower = text.strip().lower()
    for p in factual_patterns:
        if re.search(p, e_lower, re.IGNORECASE):
            print(f"  MATCH: {p}")
            break
    else:
        print(f"  NENHUM MATCH")