# DIRETRIZES DE PROJETO & BASE DE CONHECIMENTO PERMANENTE
## Mesa de Operações B3 & Sistemas Multiagentes CrewAI (Produção)

Este arquivo define as regras de desenvolvimento obrigatórias e inegociáveis para qualquer alteração, refatoração ou adição de features neste repositório. Ele sintetiza os aprendizados documentados em [`BASE_DE_CONHECIMENTO_ERROS_E_CORRECOES.md`](./BASE_DE_CONHECIMENTO_ERROS_E_CORRECOES.md) e no [`PROMPT_MESTRE_CREWAI_PRODUCAO_V1.md`](./PROMPT_MESTRE_CREWAI_PRODUCAO_V1.md).

---

### 1. ANTI-ALUCINAÇÃO & PROVENIÊNCIA REAL DE DADOS
* **Zero Fabricação:** É expressamente proibido gerar cotações, múltiplos fundamentalistas (P/L, ROE, P/VP) ou preços de strikes fictícios.
* **Cálculos Determinísticos em Python:** Qualquer matemática financeira (Gregas de Black-Scholes, Volatilidade Histórica Anualizada de 252 dias úteis, Stop Loss, Alvos de Risco/Retorno) **deve rodar exclusivamente em Python puro dentro de `tools/`** como `@tool`. A IA nunca faz contas de cabeça.
* **Tratamento de Falhas:** Se a API da BRAPI ou busca web falhar, declare formalmente como dado indisponível ou utilize a base histórica devidamente rotulada com `[DADO_HISTORICO_AUDITADO]`.

---

### 2. RESILIÊNCIA DE LLM & CONTROLE DE COTA (`429 RESOURCE_EXHAUSTED`)
* **Cadeia de Fallback Multi-Modelo:** Nunca fixe um único identificador estático de modelo. Mantenha e utilize a cadeia configurada em `crew.py`:
  `gemini-flash-latest` $\rightarrow$ `gemini-2.5-flash` $\rightarrow$ `gemini-2.0-flash` $\rightarrow$ `gemini-1.5-flash`.
* **Controle Estrito de Iterações:** Mantenha `max_iter=2` ou `max_iter=3` em agentes que utilizam ferramentas de busca web (`search_tools.py`) para evitar loops infinitos e esgotamento de quota.

---

### 3. GOVERNANÇA DE RISCO & VETO PROGRAMÁTICO OBRIGATÓRIO
* O Coordenador de Risco possui autoridade de veto implementada em código (`tools/risk_gate.py`).
* **Sarrafo de R/R:** Se a relação Risco/Retorno for inferior a $1.50 : 1$, a operação deve ser compulsoriamente **VETADA** com a diretriz oficial: `"MANTER 100% EM CAIXA / CDI"`.
* Nenhum agente ou solicitação de usuário pode sobrepor este veto programático.

---

### 4. DERIVATIVOS B3 & LIQUIDEZ REAL
* Opções devem ser estruturadas estritamente com base nos **vencimentos das 3ª sextas-feiras de cada mês** (séries mensais homologadas).
* Séries semanais (W1, W2, etc.) devem ser descartadas por ausência de formador de mercado e iliquidez de book.

---

### 5. PARIDADE LOCAL VS. VERCEL SERVERLESS
* **Vercel Cloud:** Opera como showcase demonstrativo institucional auditado, com dados de referência e banner transparente de `MODO DEMO`.
* **Servidor Local (`iniciar_mesa.bat`):** Executa a esteira CrewAI ao vivo com os 6 agentes de IA, chamadas reais à BRAPI e geração do relatório PDF executivo.
* **Assets Estáticos na Vercel:** Todas as pastas estáticas (`midia/**`, `static/**`, `output/**`) devem estar explicitamente listadas na seção `includeFiles` do [`vercel.json`](./vercel.json).
* **Nomes de Pastas:** Usar estritamente letras minúsculas (ex: `midia/`) para evitar erros de case-sensitivity no Linux da nuvem.

---

### 6. SCRIPTS WINDOWS & CODIFICAÇÃO CLI
* Todo script `.bat` deve iniciar com:
  ```bat
  @echo off
  chcp 65001 >nul
  setlocal enabledelayedexpansion
  ```
* Arquivos `.bat` devem ser salvos estritamente em **UTF-8 sem BOM** e quebras de linha **CRLF**, evitando erros de parsing no `cmd.exe` (`0B`, `cho`, etc.).

---

### 7. DESIGN SYSTEM RESPONSIVO (MOBILE, TABLET, DESKTOP)
* Qualquer alteração no frontend ([`static/style.css`](./static/style.css) ou [`static/apresentacao.css`](./static/apresentacao.css)) deve preservar:
  1. **Zero Overflow Horizontal:** Nenhuma barra de rolagem horizontal não planejada em smartphones ($360\text{px} - 480\text{px}$).
  2. **Grids Fluidos:** Uso de `minmax(min(100%, ...), 1fr)`.
  3. **Gráficos Chart.js:** Manter `responsive: true`, `maintainAspectRatio: false` e redimensionamento via `.resize()` na troca de abas.
  4. **Inputs:** `font-size: 16px` mínimo em mobile para evitar auto-zoom no Safari iOS.
  5. **Tabelas Grandes:** Envolvidas em contêineres com `-webkit-overflow-scrolling: touch;`.

---

### 8. SEGURANÇA DE ROTAS & ANTI-PATH TRAVERSAL (CWE-22)
* **Sem `:path` Irrestrito:** Rotas de download ou arquivos nunca devem utilizar conversores `:path` sem validação rigorosa.
* **Validação Canônica (Realpath):** Todo arquivo servido deve ter seu caminho canônico validado com `os.path.realpath()` garantindo confinamento estrito dentro do diretório autorizado (`startswith(pasta_real + os.sep)`).
* **Whitelist de Extensões:** Apenas extensões homologadas (`.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4` para mídias; `.pdf` para relatórios) podem ser transmitidas. Extensões de código ou dados sensíveis (`.env`, `.py`, `.json`, `.key`, `.yml`) são compulsoriamente bloqueadas.
* **Zero Endpoints de Debug:** Endpoints que expõem listagens de arquivos ou detalhes do sistema de arquivos (`/api/debug-files`, etc.) são proibidos em produção.
* **Binding Seguro:** Em ambiente de desenvolvimento/local, servidores devem escutar por padrão em `127.0.0.1` (localhost) em vez de `0.0.0.0`.

