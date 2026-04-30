# InfinityX

Assistente local em **português (PT-PT)** com três interfaces:

| Interface | Ficheiro | Como correr |
|---|---|---|
| CLI                | `InfinityX/InfinityX/infinityx.py`   | `python infinityx.py` |
| GUI Tkinter        | `InfinityX/InfinityX/gui.py`         | `python gui.py` |
| **Live no browser**| `InfinityX/InfinityX/web_server.py`  | `python web_server.py` (porta 5000) |

A workflow `Start application` arranca o servidor web automaticamente (`http://0.0.0.0:5000`).

## Estrutura

```
InfinityX/InfinityX/
├── infinityx.py       # CLI
├── gui.py             # GUI Tkinter
├── web_server.py      # Servidor Flask (modo live)
├── templates/
│   └── index.html     # Página única "live" (toggles ouvir/ver)
├── parser.py          # `analisar()` + `executar_acao()`
├── llm.py             # Integração Groq (chat + visão)
├── memory.py          # Persistência (memória, lembretes, notas)
├── config.py          # Constantes + INTENT_SYSTEM_PROMPT
├── stats.py           # Métricas por turno
├── utils.py
└── actions/
    ├── __init__.py    # Tabela de acções
    ├── percepcao.py   # ouvir / ver / descrever_imagem
    └── ... (outras categorias)
```

## Modo "Live" (página HTML)

`/` serve uma página com dois interruptores principais:

* 🎤 **Ouvir (microfone)** — usa a Web Speech API do browser para transcrever em PT-PT
  e envia o texto final para `POST /api/chat`.
* 👁️ **Ver (câmara)** — `getUserMedia` mostra o vídeo no painel; de N em N segundos
  (configurável) envia uma frame em JPEG base64 para `POST /api/vision`,
  que chama `action_descrever_imagem` (modelo Groq Llama-4 Scout).
* 🔊 **Ler respostas** — usa `SpeechSynthesis` do browser para falar a resposta.

Endpoints:

* `GET  /`            — página HTML
* `POST /api/chat`    — `{text}` → `{reply, source, footer}`
* `POST /api/vision`  — `{image: dataURL, prompt?}` → `{reply, source, footer}`
* `GET  /api/health`  — sanity check

Toda a captura corre no browser; o backend reutiliza o mesmo pipeline da CLI/GUI.

## Percepção (via CLI/GUI)

`actions/percepcao.py`:

* `action_ouvir` / `action_ouvir_e_responder` — `SpeechRecognition` + Google Web Speech
* `action_ver` — captura webcam via OpenCV
* `action_descrever_imagem` — envia para Groq vision (`meta-llama/llama-4-scout-17b-16e-instruct`)

## Variáveis de ambiente

* `GROQ_API_KEY` (obrigatória para LLM e visão)

## Workflows

* **Smoke test** — `python -c "import …"` valida que todos os módulos importam e `gui.py` compila.
* **Start application** — arranca `web_server.py` em `0.0.0.0:5000` (webview).

## Notas para futuras edições

* Os ficheiros `.py` deste projecto usam **CRLF** (Windows). Para edições, usar
  `python3 - <<PY` com `read_bytes()`/`write_bytes()` quando o `edit` falhar
  por mismatch de fim-de-linha.
* O código vive em `InfinityX/InfinityX/` (pasta nested), **não** em `InfinityX/`.
* Não editar `.replit` directamente — usar a skill `workflows`.
