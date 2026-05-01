# Guia de Expansão de Autonomia e Funcionalidades - InfinityX

## 1. Visão Geral

Para que a InfinityX se torne verdadeiramente autónoma e adaptável, é necessário evoluir de um sistema de "comando-resposta" para um sistema de "agente-objetivo". Este documento detalha as melhorias propostas para aumentar a liberdade da Infinity na tomada de decisões e na adaptação ao utilizador.

## 2. Melhorias de Autonomia (Chain of Thought)

Atualmente, a Infinity executa uma única ação por turno. Para aumentar a autonomia, propomos a implementação de um loop de execução interna:

### Encadeamento Dinâmico de Ações
Em vez de retornar um único JSON, o classificador de intenções pode retornar uma **lista de passos**.
*   **Exemplo:** "Cria um resumo das notícias de tecnologia e guarda num ficheiro chamado news.txt".
*   **Fluxo:** `noticias(fonte="tech")` → `criar_arquivo(nome="news.txt", texto=resultado_anterior)`.

### Reflexão e Auto-Correção
Adicionar um passo de "verificação" após a execução de ferramentas críticas. Se uma pesquisa web não retornar resultados úteis, a Infinity deve ter a liberdade de reformular a query e tentar novamente sem intervenção do utilizador.

## 3. Memória Contextual e Aprendizagem

A memória atual é baseada em ficheiros JSON estáticos. Propomos as seguintes evoluções:

### Perfil de Preferências Dinâmico
Criar uma secção `preferencias` no `memory.json` que a Infinity atualiza autonomamente.
*   **Como funciona:** Se o utilizador pede sempre notícias do "Público", a Infinity deve registar: `"fonte_noticias_preferida": "publico"`.
*   **Adaptação:** Em pedidos futuros de "notícias", ela usa automaticamente a preferência guardada.

### Memória de Longo Prazo (RAG Local)
Para lidar com grandes volumes de notas e histórico, implementar uma busca semântica simples (mesmo que baseada em palavras-chave melhoradas) para que a Infinity possa "lembrar-se" de factos ditos há semanas.

## 4. Novas Funcionalidades Sugeridas

| Funcionalidade | Descrição | Impacto na Liberdade |
| :--- | :--- | :--- |
| **Automação de Browser (Selenium)** | Permitir que a Infinity navegue em sites específicos, faça login ou extraia dados complexos. | Permite realizar tarefas transacionais (ex: "vê o preço deste produto na Amazon"). |
| **Execução de Scripts (Sandbox)** | Capacidade de escrever e executar pequenos scripts Python para resolver problemas complexos. | Dá liberdade total para resolver problemas matemáticos ou de dados não previstos. |
| **Integração com Calendário Local** | Sincronização com ficheiros `.ics` ou APIs de calendário. | Transforma a Infinity numa assistente de gestão de tempo real. |
| **Geração de Imagens (Stable Diffusion Local)** | Se o hardware permitir, integrar geração de imagens via API local. | Expande a criatividade da assistente. |

## 5. Refatoração do Prompt para "Liberdade"

O `INTENT_SYSTEM_PROMPT` deve ser alterado para incentivar a exploração:
*   **Nova Diretriz:** "Se o pedido do utilizador for complexo, decompõe-no em sub-tarefas. Não peças permissão para usar ferramentas que já tens disponíveis."
*   **Incentivo à Pesquisa:** "Se a informação local for insuficiente ou puder estar desatualizada, a tua primeira ação deve ser sempre `browser_search`."

## 6. Conclusão

Ao implementar estas melhorias, a InfinityX deixará de ser apenas um "parser de comandos" para se tornar um agente proativo que antecipa as necessidades do utilizador e utiliza as suas ferramentas de forma criativa e encadeada.
