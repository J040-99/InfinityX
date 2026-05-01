# Relatório de Análise de Código - InfinityX

## 1. Introdução

Este relatório apresenta uma análise detalhada do código-fonte do projeto InfinityX, um assistente local autónomo em Python com IA interpretativa. O objetivo é fornecer uma visão abrangente da sua arquitetura, tecnologias empregadas, fluxo de processamento de interações, funcionalidades principais, e uma avaliação da qualidade do código, culminando em sugestões de melhoria.

## 2. Arquitetura Geral

A InfinityX adota uma arquitetura modular e multifacetada, concebida para ser extensível e reutilizável em diferentes interfaces. O projeto é estruturado em torno de um núcleo de lógica de processamento de linguagem natural e execução de ações, que é partilhado por três pontos de entrada distintos:

*   **Interface de Linha de Comando (CLI)**: Implementada em `infinityx.py`, oferece uma interação baseada em texto com formatação ANSI para uma experiência de terminal rica.
*   **Interface Gráfica do Utilizador (GUI)**: Desenvolvida em `gui.py` usando Tkinter, proporciona uma experiência de chat visual.
*   **Servidor Web (Flask)**: Em `web_server.py`, expõe uma interface web que permite interações via browser, incluindo funcionalidades de visão e áudio baseadas em APIs web.

O projeto organiza-se em módulos lógicos, conforme detalhado no `README.md` e confirmado pela estrutura de ficheiros:

| Módulo/Pasta | Descrição Principal |
| :----------- | :------------------ |
| `infinityx.py` | Ponto de entrada da CLI, inicialização e loop principal. |
| `gui.py` | Ponto de entrada da GUI (Tkinter). |
| `web_server.py` | Ponto de entrada do servidor web (Flask). |
| `config.py` | Configurações globais, chaves de API, prompts do sistema, mapeamentos e flags de dependências. |
| `memory.py` | Gestão da memória persistente (histórico, palavras, notas, lembretes) via ficheiros JSON. |
| `utils.py` | Funções utilitárias (avaliação segura de expressões, manipulação de caminhos, categorização de ficheiros). |
| `llm.py` | Camada de abstração para interação com Modelos de Linguagem Grandes (LLMs) como Groq, LM Studio e Perplexity, incluindo classificação de intenções. |
| `parser.py` | O "cérebro" da InfinityX, responsável pela pré-análise, deteção de intenções, guardrails e execução de ações. |
| `stats.py` | Registo de métricas de desempenho (tokens, tempo de resposta) das interações. |
| `actions/` | Pacote que agrupa as diversas funcionalidades e ferramentas que a InfinityX pode executar (e.g., sistema, multimédia, produtividade, web). |
| `templates/` | Contém ficheiros HTML para a interface web. |

## 3. Tecnologias Utilizadas

A InfinityX é construída predominantemente em **Python**, aproveitando um ecossistema de bibliotecas para diversas funcionalidades:

*   **Frameworks Web**: `Flask` para o servidor web.
*   **Interfaces Gráficas**: `Tkinter` para a GUI.
*   **LLMs e APIs**: Integração com `Groq` (para `llama-3.1-8b-instant` e `llama-4-scout-17b-16e-instruct`), `LM Studio` (para modelos locais) e `Perplexity` como fallback. Utiliza `requests` para chamadas HTTP às APIs.
*   **Persistência**: Ficheiros JSON para guardar o estado da memória, palavras, notas e lembretes.
*   **Sistema Operativo**: `ctypes` para ativação de ANSI no Windows, `os`, `platform`, `shutil` para interações com o sistema de ficheiros e ambiente.
*   **Processamento de Linguagem Natural (PLN)**: Expressões regulares (`re`), `unicodedata` para normalização de texto, e lógica determinística para pré-análise e guardrails.
*   **Multimédia e Percepção**: `SpeechRecognition` (com Google Web Speech API) para transcrição de áudio, `OpenCV` para captura de webcam e processamento de imagem (visão).
*   **Produtividade**: `datetime`, `timedelta` para gestão de tempo e lembretes.
*   **Outras APIs**: `OpenWeatherMap` para dados meteorológicos, `Last.fm` para integração musical.
*   **Dependências Opcionais**: `pyautogui` (automação de GUI), `psutil` (informações do sistema), `pyperclip` (clipboard).

## 4. Fluxo de Interpretação e Execução

O `parser.py` é o coração da lógica de decisão da InfinityX, implementando um pipeline de interpretação que combina regras determinísticas com a flexibilidade dos LLMs:

1.  **Normalização e Pré-análise**: A entrada do utilizador passa por correção de typos (`TYPOS_MAP` em `config.py`) e `checar_palavra` (dicionário pessoal). `pre_analyze` (`parser.py`) lida com respostas factuais rápidas sem IA (matemática, saudações, hora, data, criação de ficheiros), incluindo parsing de datas relativas.
2.  **Guardrails Determinísticos**: Antes de qualquer chamada a LLM, são aplicados guardrails para detetar insultos ou assédio (`_detectar_insulto_ou_assedio` em `parser.py`), respondendo com frases curtas pré-definidas para evitar divagações dos LLMs.
3.  **Classificação de Intenção (LLM-first)**: A função `classify_intent` (`llm.py`) utiliza um LLM (preferencialmente Groq com `llama-3.1-8b-instant`) para classificar a intenção do utilizador, gerando um JSON com a `action` a ser executada, `params` e um `confidence` score. O `INTENT_SYSTEM_PROMPT` em `config.py` é crucial aqui, definindo a persona da Infinity e o contrato de saída JSON.
4.  **Fallback Inteligente**: Se a confiança do LLM for baixa (`CONFIDENCE_THRESHOLD`) ou a classificação falhar, o sistema recorre a fallbacks baseados em regex (para ações comuns como sair, ajuda, clima, uso de disco, abrir apps) ou a uma pesquisa mais genérica (`buscar_info` que tenta LM Studio, Groq e Perplexity).
5.  **Execução de Ação**: A função `executar_acao` (`parser.py`) recebe o JSON da intenção e invoca a função correspondente no pacote `actions/`. Este design permite uma fácil adição de novas funcionalidades.

## 5. Funcionalidades Principais

O pacote `actions/` é um repositório de capacidades, organizado por categorias:

*   **Sistema**: `action_hora`, `action_sysinfo`, `action_clima` (com integração OpenWeatherMap/Open-Meteo), `network_info`, `disk_usage`, `battery_status`.
*   **Multimédia**: `action_speak` (TTS), `action_ouvir_e_responder` (microfone), `action_ver` (webcam), `action_descrever_imagem` (visão com LLM), controlo de media (play/pause, volume).
*   **Música**: Integração com `YouTube Music` (tocar, pesquisar, playlists, rádio) e `Last.fm` (histórico, top, artistas, scrobbling).
*   **Produtividade**: `action_todo_add`, `action_todo_list`, `action_timer_set`, `action_nota_add`, `action_lembrete_add` (com scheduler), `action_resumo_dia`.
*   **Ficheiros e Web**: `listar_pasta`, `organizar_pasta`, `search_files`, `file_info`, `criar_arquivo`, `abrir` (apps/sites), `browser_search`, `wikipedia`.
*   **Utilitários**: `translate`, `convert`, `currency_convert`, `generate_password`, `uuid_gen`, `hash_text`, `base64`, `json_format`, `lorem_ipsum`, `public_ip`, `crypto_price`, `noticias`.

## 6. Qualidade do Código e Boas Práticas

### Pontos Fortes:

*   **Modularidade**: O código é bem organizado em módulos e pacotes (`actions/`), facilitando a compreensão e a adição de novas funcionalidades.
*   **Reutilização**: O pipeline central de `analisar` e `executar_acao` é reutilizado nas interfaces CLI, GUI e Web, o que é uma boa prática de engenharia de software.
*   **Persistência Simples**: A utilização de ficheiros JSON para memória é eficaz para um assistente local, mantendo o estado entre sessões.
*   **Robustez**: O tratamento de erros (`try-except`) é visível em várias partes do código, especialmente nas interações com APIs externas e no parsing de JSON.
*   **Documentação Interna**: O uso de docstrings e comentários explica a finalidade de funções e módulos, embora possa ser inconsistente em alguns ficheiros.
*   **Internacionalização (PT)**: A atenção aos detalhes da língua portuguesa (números por extenso, operadores, datas relativas, persona) é notável e bem implementada.
*   **Guardrails**: A implementação de guardrails determinísticos para insultos/assédio é uma solução inteligente para contornar limitações dos LLMs e manter a persona.

### Áreas para Melhoria:

*   **Acoplamento Global**: A dependência de variáveis globais mutáveis (`MEMORIA`, `PALAVRAS`, etc.) em `memory.py` cria um acoplamento forte entre os módulos. Embora funcional, pode dificultar testes unitários e a gestão de concorrência em cenários mais complexos (e.g., múltiplas instâncias do assistente).
*   **Prompt do Sistema em `config.py`**: O `INTENT_SYSTEM_PROMPT` é extremamente longo e detalhado. Embora eficaz para guiar o LLM, a sua manutenção pode ser desafiadora. Pequenas alterações podem ter efeitos colaterais inesperados. Considerar a possibilidade de externalizar partes do prompt ou usar técnicas de prompt engineering mais dinâmicas.
*   **Duplicação de Código**: Há algumas instâncias de duplicação, como a secção "PERCEPCAO (microfone e camara)" repetida em `config.py`. Isso pode levar a inconsistências se uma das cópias for atualizada e a outra não.
*   **Tratamento de Exceções Genéricas**: O uso de `except Exception as exc: # noqa: BLE001` em `web_server.py` e outras partes do código é um antipadrão. Capturar exceções genéricas pode mascarar erros e dificultar a depuração. É preferível capturar exceções mais específicas.
*   **Gestão de Dependências Opcionais**: A forma como as dependências opcionais são verificadas (`try-except ImportError`) é funcional, mas poderia ser mais formalizada (e.g., com um sistema de plugins ou um gestor de dependências mais robusto para funcionalidades opcionais).
*   **Testes**: Embora existam ficheiros `test_*.py`, a extensão e cobertura dos testes não são imediatamente claras. Testes unitários e de integração mais abrangentes seriam benéficos para garantir a estabilidade e prevenir regressões.
*   **Segurança (safe_eval)**: Embora `safe_eval` em `utils.py` tente restringir o ambiente de `eval()`, o uso de `eval()` é inerentemente arriscado e deve ser evitado sempre que possível. Para expressões matemáticas, um parser de expressões mais seguro ou uma biblioteca dedicada seria preferível.
*   **Concorrência**: O scheduler de lembretes em `produtividade.py` usa um loop infinito em uma thread separada. Embora funcione, a gestão de threads e a sincronização com o estado global (`MEMORIA`) podem ser fontes de bugs difíceis de diagnosticar. A utilização de um framework de concorrência mais robusto (e.g., `asyncio` para operações assíncronas) poderia ser considerada para futuras melhorias.

## 7. Sugestões de Melhoria

Com base na análise, as seguintes sugestões podem ser consideradas para aprimorar o projeto InfinityX:

1.  **Refatorar a Gestão de Estado Global**: Explorar padrões de injeção de dependência ou um sistema de mensagens para reduzir o acoplamento direto às variáveis globais em `memory.py`. Isso melhoraria a testabilidade e a manutenibilidade.
2.  **Otimizar o `INTENT_SYSTEM_PROMPT`**: Dividir o prompt em secções menores e mais gerenciáveis, talvez com prompts específicos para diferentes tipos de tarefas, ou usar um sistema de templates para construí-lo dinamicamente. Isso facilitaria a atualização e a experimentação.
3.  **Eliminar Duplicação de Código**: Realizar uma auditoria para identificar e remover código duplicado, especialmente em `config.py` e nos módulos de ações.
4.  **Refinar o Tratamento de Exceções**: Substituir exceções genéricas por tipos mais específicos para permitir um tratamento de erros mais preciso e informativo.
5.  **Implementar Testes Abrangentes**: Desenvolver uma suíte de testes unitários e de integração robusta para as principais funcionalidades, garantindo a estabilidade e a qualidade do código.
6.  **Reavaliar `safe_eval`**: Substituir a função `safe_eval` por uma abordagem mais segura para o parsing e avaliação de expressões matemáticas, como uma biblioteca de parsing de expressões ou a conversão para uma representação de árvore de sintaxe abstrata (AST) antes da avaliação.
7.  **Considerar `asyncio` para Concorrência**: Para operações que envolvem I/O (chamadas de API, acesso a ficheiros) e tarefas em segundo plano (scheduler de lembretes), a adoção de `asyncio` pode melhorar a eficiência e a escalabilidade, tornando o código mais reativo e menos propenso a problemas de concorrência.
8.  **Melhorar a Documentação**: Padronizar o uso de docstrings e comentários, talvez adotando um formato específico (e.g., Google Style Python Docstrings) para melhorar a clareza e a consistência.

## 8. Conclusão

A InfinityX é um projeto ambicioso e bem-sucedido na criação de um assistente autónomo local. A sua arquitetura modular e a abordagem "LLM-first" com fallbacks inteligentes são pontos fortes significativos. As sugestões de melhoria visam aprimorar a manutenibilidade, a robustez e a segurança do código, garantindo a sua evolução contínua e a capacidade de lidar com requisitos cada vez mais complexos. O projeto demonstra um excelente esforço em integrar diversas tecnologias de IA e automação de sistema numa experiência de utilizador coesa e em português europeu.
