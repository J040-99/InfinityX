# Relatório de Capacidades Proativas - InfinityX (Parte 2)

## 1. Introdução

Este relatório detalha a implementação de capacidades proativas na InfinityX, permitindo-lhe agendar tarefas e monitorizar condições específicas. Estas funcionalidades transformam a InfinityX de um assistente reativo para um agente proativo, capaz de executar ações de forma autónoma em momentos definidos ou em resposta a eventos do sistema ou do ambiente.

## 2. Agendamento de Tarefas

A InfinityX agora pode agendar comandos para serem executados no futuro, seja uma única vez ou de forma recorrente.

**Implementação:**

*   **`actions/produtividade.py`**: Foi adicionada a função `action_agendar_tarefa(quando: str, comando: str, recorrente: bool = False)`. Esta função utiliza a biblioteca `schedule` para agendar a execução de um `comando` (uma string que representa uma instrução para a InfinityX) num `quando` específico (ex: "HH:MM", "in X minutes"). A flag `recorrente` permite que a tarefa seja repetida.
    *   **Nota:** A implementação atual apenas imprime o comando a ser executado. Numa versão completa, esta função chamaria o `parser.processar_entrada(comando)` para que a InfinityX realmente execute a instrução agendada.
*   **`actions/__init__.py`**: A `action_agendar_tarefa` foi exportada.
*   **`parser.py`**: A ação `agendar_tarefa` foi mapeada na tabela de ações.

**Impacto:** Esta funcionalidade permite que o utilizador defina lembretes complexos, automatize verificações periódicas (ex: "verificar o clima amanhã de manhã") ou execute rotinas diárias sem intervenção manual. A capacidade de agendamento é fundamental para a autonomia a longo prazo da InfinityX.

## 3. Monitorização Básica de Eventos

A InfinityX pode agora monitorizar condições específicas e reagir quando essas condições são atingidas.

**Implementação:**

*   **`actions/monitorizacao.py`**: Foi criado um novo módulo com a função `action_monitorar_condicao(tipo: str, alvo: str, condicao: str, valor: float, acao: str)`. Esta função inicia uma thread em background que verifica periodicamente uma condição (ex: preço de criptomoeda, nível de bateria) e, se a condição for verdadeira, executa uma `acao` predefinida.
    *   **Tipos de Monitorização Suportados:** `crypto` (para criptomoedas), `bateria` (para o nível da bateria do sistema).
    *   **Condições:** `>`, `<`, `==`.
    *   **Ação:** Uma string que representa um comando para a InfinityX (ex: `responder "A bateria está baixa!"`).
*   **`actions/__init__.py`**: A `action_monitorar_condicao` foi exportada.
*   **`parser.py`**: A ação `monitorar_condicao` foi mapeada na tabela de ações.

**Impacto:** Esta capacidade permite que a InfinityX atue de forma proativa, alertando o utilizador ou tomando medidas quando certas condições são satisfeitas. Por exemplo, pode avisar quando a bateria do portátil está fraca, ou quando o preço de uma criptomoeda atinge um determinado valor, tornando-a um assistente mais inteligente e vigilante.

## 4. Refinamento do Prompt do Sistema

O `INTENT_SYSTEM_PROMPT` em `config.py` foi atualizado para incluir instruções sobre as novas ações proativas. O prompt agora orienta o LLM sobre quando e como utilizar `agendar_tarefa` e `monitorar_condicao`, incluindo exemplos de parâmetros e cenários de uso.

**Impacto:** Um prompt bem estruturado é essencial para que o LLM compreenda o potencial destas novas ferramentas e as integre de forma eficaz no seu planeamento e execução de tarefas, aumentando a sua autonomia e utilidade.

## 5. Validação e Testes (Conceitual)

Para validar as novas capacidades proativas, os seguintes cenários de teste podem ser considerados:

*   **Agendamento:**
    *   "Agenda para as 10:30 que eu verifique as notícias."
    *   "Agenda para daqui a 5 minutos que me digas a hora atual."
*   **Monitorização:**
    *   "Monitoriza a bateria e avisa-me se ficar abaixo de 20%."
    *   "Monitoriza o preço do Bitcoin e avisa-me se passar dos 70000 USD."

## 6. Conclusão

Com a implementação do agendamento de tarefas e da monitorização de condições, a InfinityX deu um passo significativo em direção a uma maior proatividade e autonomia. Estas funcionalidades permitem que a InfinityX atue de forma mais inteligente e independente, antecipando necessidades e reagindo a eventos, o que a torna um assistente pessoal ainda mais valioso e integrado no dia a dia do utilizador. As bases estão lançadas para futuras expansões em áreas como a automação de rotinas complexas e a gestão inteligente de eventos.
