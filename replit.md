# InfinityX

Assistente local autônoma em Python com IA interpretativa (Groq + LM Studio + fallback Perplexity). REPL em linha de comando, voltado para Windows mas roda em outras plataformas com funcionalidades reduzidas.

## Estrutura (pasta `InfinityX/`)

```
infinityx.py        # ponto de entrada CLI (REPL no terminal)
gui.py              # ponto de entrada GUI (janela Tkinter estilo chat)
config.py           # constantes, .env, mapeamentos, prompt do sistema, deps opcionais
memory.py           # MEMORIA, PALAVRAS, TIMERS — load/save em JSON
utils.py            # safe_eval, resolve_path, categorize_file, get_user_home
llm.py              # chamar_groq, chamar_lm_studio, chamar_perplexity, classify_intent
actions/            # pacote com ~80 ações (sistema, arquivos, web, mídia, last.fm, etc.)
parser.py           # pre_analyze, checar_palavra, analisar, executar_acao, _resumo_conversa
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

Modo terminal (CLI):
```
cd InfinityX
pip install -r requirements.txt
python infinityx.py
```

Modo gráfico (Tkinter — janela de chat):
```
cd InfinityX
python gui.py
```

A GUI usa exactamente o mesmo pipeline (`analisar` + `executar_acao` + `MEMORIA`) que a CLI; só envolve numa janela com balões de mensagem, thread em background para não congelar e botões para limpar a conversa e pedir resumo. Tkinter já vem com a instalação padrão do Python no Windows. Em Linux pode precisar de `sudo apt install python3-tk`.

O workflow `Smoke test` configurado neste repl apenas valida que todos os módulos importam sem erros e que `gui.py` compila — a aplicação real é interactiva e precisa de terminal ou ambiente gráfico.
