# Relatório de Aprimoramento de Visão e Audição - InfinityX

## 1. Introdução

Este relatório detalha as melhorias implementadas nas capacidades sensoriais da InfinityX, focando no aprimoramento da audição e da visão. O objetivo foi tornar a InfinityX mais precisa na transcrição de áudio e mais capaz na interpretação de imagens, utilizando soluções locais e APIs mais robustas, reduzindo a dependência de serviços externos genéricos.

## 2. Audição Aprimorada com Suporte a Whisper

A capacidade de audição da InfinityX foi significativamente melhorada através da integração do modelo Whisper da OpenAI, conhecido pela sua alta precisão na transcrição de fala para texto.

**Implementação:**

*   **`actions/percepcao.py`**: A função `action_ouvir` foi refatorada para primeiro tentar utilizar a API Whisper da OpenAI (se a `OPENAI_API_KEY` estiver configurada). O áudio capturado é temporariamente guardado num ficheiro WAV e enviado para a API Whisper para transcrição. Em caso de falha ou ausência da chave API, o sistema faz fallback para o reconhecimento de voz do Google (Google Speech Recognition).

**Impacto:** Esta melhoria resulta numa transcrição de áudio muito mais precisa e fiável, especialmente em ambientes com ruído ou para sotaques diversos. A InfinityX agora compreende melhor as instruções faladas, tornando a interação por voz mais fluida e eficaz.

## 3. Visão Local via LM Studio (Moondream/Llava)

A funcionalidade de visão da InfinityX, que anteriormente dependia de serviços externos (Groq), foi redesenhada para utilizar modelos multimodais locais através do LM Studio. Isso permite que a InfinityX "veja" e descreva imagens sem enviar dados para a nuvem, aumentando a privacidade e a capacidade offline.

**Implementação:**

*   **`actions/percepcao.py`**: A função `action_descrever_imagem` foi modificada para enviar imagens (codificadas em Base64) para o endpoint de chat completions do LM Studio. O LLM é instruído a usar um modelo de visão (como "moondream2" ou similar, que o utilizador deve ter carregado no LM Studio) para descrever o conteúdo da imagem. Em caso de erro, uma mensagem informativa é retornada, orientando o utilizador sobre a configuração necessária.

**Impacto:** A InfinityX agora pode processar e interpretar informações visuais localmente, o que é crucial para aplicações sensíveis à privacidade ou para cenários onde a conectividade à internet é limitada. Esta capacidade abre caminho para a InfinityX interagir com o mundo visual do utilizador de forma mais direta e contextualizada.

## 4. Integração de OCR (Reconhecimento Ótico de Caracteres)

Para complementar a capacidade de descrição de imagens, foi adicionada uma funcionalidade de Reconhecimento Ótico de Caracteres (OCR), permitindo à InfinityX extrair texto diretamente de imagens.

**Implementação:**

*   **`actions/percepcao.py`**: Uma nova função `action_ocr(path: str)` foi criada. Esta função utiliza a biblioteca `pytesseract` e o motor Tesseract OCR para extrair texto de uma imagem especificada pelo caminho. Suporta múltiplos idiomas (português e inglês) e retorna o texto extraído ou uma mensagem de erro se nenhum texto for detetado ou se o Tesseract não estiver instalado.
*   **`actions/__init__.py`**: A nova ação `action_ocr` foi exportada.
*   **`parser.py`**: A ação `ocr` foi adicionada à tabela de ações, permitindo que o LLM a invoque quando a intenção do utilizador for extrair texto de uma imagem.
*   **`config.py`**: O `INTENT_SYSTEM_PROMPT` foi atualizado para informar o LLM sobre a capacidade de usar `ocr`.

**Impacto:** A adição de OCR permite que a InfinityX não apenas descreva o que vê, mas também "leia" e compreenda o texto presente em imagens. Isso é fundamental para tarefas como digitalização de documentos, extração de informações de capturas de ecrã ou processamento de imagens que contenham texto relevante.

## 5. Refinamento do Prompt do Sistema

O `INTENT_SYSTEM_PROMPT` em `config.py` foi atualizado para guiar o LLM na utilização inteligente destas novas capacidades sensoriais. As instruções agora incluem diretrizes sobre quando usar `action_ouvir`, `action_ver`, `action_descrever_imagem` e `action_ocr`, incentivando o LLM a escolher a ferramenta mais apropriada com base no contexto do pedido do utilizador.

**Impacto:** Um prompt mais refinado garante que a InfinityX aproveite ao máximo as suas novas "perceções", integrando a audição e a visão de forma coesa na sua tomada de decisão e na execução de tarefas.

## 6. Validação e Testes (Conceitual)

Para validar as novas capacidades sensoriais, os seguintes cenários de teste podem ser considerados:

*   **Audição:**
    *   Fazer perguntas complexas ou com sotaque através do microfone e verificar a precisão da transcrição.
    *   Testar em ambientes com ruído de fundo para avaliar a robustez do Whisper.
*   **Visão e OCR:**
    *   Pedir à InfinityX para descrever uma imagem com objetos variados e texto legível.
    *   Fornecer uma imagem de um documento ou uma captura de ecrã e pedir para extrair o texto contido nela.
    *   Combinar visão e RAG: Pedir para descrever uma imagem e, em seguida, fazer perguntas sobre o texto extraído ou os objetos descritos, esperando que a InfinityX use o contexto da imagem.

## 7. Conclusão

As melhorias nas capacidades de visão e audição representam um avanço significativo na forma como a InfinityX interage com o mundo real. Com a integração do Whisper para transcrição de áudio de alta qualidade, a visão local via LM Studio para interpretação de imagens e a funcionalidade de OCR para extração de texto, a InfinityX está agora equipada com um conjunto de "sentidos" muito mais apurado. Estas capacidades sensoriais aprimoradas, combinadas com a sua autonomia e flexibilidade, tornam a InfinityX um assistente pessoal ainda mais poderoso e versátil, capaz de perceber e responder ao ambiente do utilizador de formas mais ricas e inteligentes.
