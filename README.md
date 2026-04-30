# InfinityX

Assistente local autônoma em Python com IA interpretativa (Groq + LM Studio + fallback Perplexity). REPL em linha de comando, voltado para Windows mas roda em outras plataformas com funcionalidades reduzidas.

## Estrutura (pasta `InfinityX/`)

```
infinityx.py        # ponto de entrada CLI (REPL com layout colorido ANSI)
gui.py              # ponto de entrada GUI (janela Tkinter estilo chat)
config.py           # constantes, .env, mapeamentos, prompt do sistema, deps opcionais
memory.py           # MEMORIA, PALAVRAS, TIMERS — load/save em JSON
utils.py            # safe_eval, resolve_path, categorize_file, get_user_home
llm.py              # chamar_groq, chamar_lm_studio, chamar_perplexity, classify_intent
stats.py            # métricas (origem, tokens, tempo) da última interacção
actions/            # pacote de ações agrupadas por categoria
  midia.py          # clipboard, teclado/rato, TTS (action_speak)
  percepcao.py      # ouvir (microfone) + ver (câmara/imagens via Groq vision)
  musica.py         # YouTube Music + media keys
  lastfm.py         # integração Last.fm
  produtividade.py  # notas, lembretes, palavras, todos
  sistema.py        # clima, hora, sysinfo, bateria, rede, disco
  arquivos.py / util.py / web.py # ficheiros, utilitários e browser
parser.py           # pre_analyze, checar_palavra, analisar, executar_acao, _resumo_conversa
requirements.txt    # dependências Python
memory.json         # histórico persistente
palavras.json       # dicionário pessoal
```

## Pipeline de interpretação (em `parser.analisar`)

1. Correção de typos comuns (`TYPOS_MAP`).
2. `checar_palavra`: dicionário pessoal (aprende/procura/lista/esquece).
3. **Guardrail determinístico** de insultos/assédio (`_detectar_insulto_ou_assedio`): se a entrada bate em padrões conhecidos (palavrões dirigidos, conteúdo sexual), devolve directamente uma resposta curta no tom da Infinity, sem chamar o LLM (que costumava divagar).
4. `pre_analyze`: respostas instantâneas sem IA (matemática PT, saudações, hora, data, criar arquivo). Inclui `_parse_data_relativa` para "ontem/anteontem/amanhã/depois de amanhã", "há N (dias|semanas|meses|anos)", "N atrás", "daqui a N", "semana/mês/ano passado", "próxima semana/mês/ano".
5. `classify_intent` via Groq (`llama-3.1-8b-instant`) com confiança ≥ 0.85.
6. Fallback por regex (sair, ajuda, clima/previsão N dias, disk_usage, abrir apps conhecidos, matemática).
7. Último recurso: `buscar_info` (LM Studio → Groq → Perplexity).

### Métricas de tempo e tokens (`stats.py`)

Cada interacção actualiza um dict global `stats.LAST` com a origem (`groq`, `lm_studio`, `perplexity`, `pre_analyze`, `guardrail`, etc.), o modelo, os tokens (entrada/saída/total quando aplicável) e o tempo decorrido em ms. A CLI e a GUI lêem `stats.format_footer()` e mostram-no por baixo de cada resposta — ex.: `groq · llama-3.1-8b-instant · 412 tok (320↑ 92↓) · 842ms`.

A CLI (`infinityx.py`) usa cores ANSI (no Windows activa `ENABLE_VIRTUAL_TERMINAL_PROCESSING`), banner com `═`, separadores `─` por turno, hora à frente do nome de cada interlocutor e indentação das respostas.

### Clima e previsão

`action_clima(cidade, amanha, dias)` usa duas APIs do OpenWeatherMap:
- tempo actual via `/data/2.5/weather`
- previsão (amanhã ou N dias, máx 5 no plano gratuito) via `/data/2.5/forecast` em `_previsao_openweather`. Para "amanhã" agrupa os 8 slots de 3h e mostra o slot mais próximo do meio-dia mais a min/max do dia.

### Percepção (microfone e câmara)

A Infinity sabe ouvir e ver:

- **Ouvir**: gatilhos como `ouve-me`, `liga o microfone`, `modo voz` chamam `action_ouvir_e_responder`. Capturaáudio com `SpeechRecognition` (transcrição pelo Google Web Speech, grátis), passa o texto pelo mesmo `analisar`+`executar_acao` da CLI e devolve a resposta. Se faltar `pyaudio`/microfone, o utilizador recebe uma mensagem clara em vez de um stack trace.
- **Ver**: gatilhos como `o que vês?`, `tira uma foto`, `olha para isto`, `usa a câmara` chamam `action_ver`. Captura uma frame da webcam com OpenCV, codifica em base64 e envia a `meta-llama/llama-4-scout-17b-16e-instruct` no Groq, devolvendo a descrição em português.
- **Descrever uma imagem qualquer**: `descreve a imagem foto.png` ou `analisa esta imagem /tmp/x.jpg` enviam o ficheiro local à mesma API de visão.

Dependências opcionais (já listadas em `requirements.txt`): `SpeechRecognition`, `pyaudio` (Windows: `pip install pipwin && pipwin install pyaudio`), `opencv-python`. Sem elas as restantes funcionalidades continuam intactas.

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
