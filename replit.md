# InfinityX

Assistente local autônoma em Python com IA interpretativa (Groq + LM Studio + fallback Perplexity). REPL em linha de comando, voltado para Windows mas roda em outras plataformas com funcionalidades reduzidas.

## Estrutura (pasta `InfinityX/`)

```
infinityx.py        # ponto de entrada e loop principal (REPL)
config.py           # constantes, .env, mapeamentos, prompt do sistema, deps opcionais
memory.py           # MEMORIA, PALAVRAS, TIMERS — load/save em JSON
utils.py            # safe_eval, resolve_path, categorize_file, get_user_home
llm.py              # chamar_groq, chamar_lm_studio, chamar_perplexity, classify_intent
actions.py          # implementação de ~39 ações (sistema, arquivos, web, mídia, etc.)
parser.py           # pre_analyze, checar_palavra, analisar, executar_acao
requirements.txt    # dependências Python
memory.json         # histórico persistente
palavras.json       # dicionário pessoal
```

## Pipeline de interpretação (em `parser.analisar`)

1. Correção de typos comuns (`TYPOS_MAP`).
2. `checar_palavra`: dicionário pessoal (aprende/procura/lista/esquece).
3. `pre_analyze`: respostas instantâneas sem IA (matemática PT, saudações, hora, data, criar arquivo).
4. `classify_intent` via Groq (`llama-3.1-8b-instant`) com confiança ≥ 0.85.
5. Fallback por regex (sair, ajuda, clima, disk_usage, abrir apps conhecidos, matemática).
6. Último recurso: `buscar_info` (LM Studio → Groq → Perplexity).

## Variáveis de ambiente (em `InfinityX/.env`)

- `GROQ_API_KEY`
- `OPENWEATHERMAP_API_KEY`
- `LM_STUDIO_URL` (padrão `http://localhost:1234/v1/chat/completions`)

## Como rodar

```
cd InfinityX
pip install -r requirements.txt
python infinityx.py
```

O workflow `Smoke test` configurado neste repl apenas valida que todos os módulos importam sem erros — a aplicação real é interativa e precisa de terminal.
