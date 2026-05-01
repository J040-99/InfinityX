# Guia de Configuração 100% Gratuito - InfinityX

Este guia explica como configurar a InfinityX para funcionar de forma totalmente gratuita, utilizando modelos locais para IA, Visão e Audição.

## 1. IA e Visão Local (LM Studio)
A InfinityX utiliza o **LM Studio** como o seu "cérebro" local.
1.  Descarregue o [LM Studio](https://lmstudio.ai/).
2.  **Para IA:** Procure e descarregue um modelo como o `Qwen2.5-Coder-3B-Instruct` ou `Llama-3-8B-Instruct`.
3.  **Para Visão:** Procure e descarregue o modelo `Moondream2`.
4.  No separador "Local Server", carregue o modelo desejado e clique em **"Start Server"**.
5.  Certifique-se de que o servidor está em `http://localhost:1234`.

## 2. Audição Local (Faster-Whisper)
A audição agora utiliza o **Faster-Whisper**, que corre no seu CPU/GPU sem custos.
1.  Instale as dependências necessárias:
    ```bash
    pip install faster-whisper SpeechRecognition pyaudio
    ```
2.  Na primeira vez que usar a função de ouvir, a InfinityX irá descarregar automaticamente o modelo `tiny` (cerca de 75MB), que é muito rápido e leve.

## 3. OCR Local (Tesseract)
Para ler texto em imagens:
1.  Instale o motor Tesseract no seu sistema:
    *   **Windows:** Descarregue o instalador do [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
    *   **Linux:** `sudo apt install tesseract-ocr`
    *   **macOS:** `brew install tesseract`
2.  Instale a biblioteca Python:
    ```bash
    pip install pytesseract Pillow
    ```

## 4. Resumo de Instalação
Para instalar todas as bibliotecas Python de uma vez, execute:
```bash
pip install -r requirements.txt
```

## 5. Vantagens desta Configuração
*   **Custo Zero:** Não precisa de chaves de API pagas (OpenAI, Groq, etc.).
*   **Privacidade Total:** Os seus dados de voz, imagem e texto nunca saem do seu computador.
*   **Funciona Offline:** Uma vez descarregados os modelos, pode usar a InfinityX sem internet (exceto para pesquisas web).

---
*Nota: Se o seu computador for mais antigo, a InfinityX fará fallback automático para o Google Speech Recognition (também gratuito) se o Faster-Whisper for demasiado pesado.*
