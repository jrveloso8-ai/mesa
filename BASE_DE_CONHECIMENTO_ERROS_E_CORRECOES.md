# BASE DE CONHECIMENTO TÉCNICA: ERROS, CAUSA-RAIZ E CORREÇÕES ARQUITETURAIS
## Projeto: Mesa de Operações B3 & Esteiras Multiagente CrewAI
**Data de Consolidação:** 25/09/2026 | **Versão:** 1.0 (Produção Auditada)

---

### INTRODUÇÃO
Este documento registra formalmente todos os incidentes, gargalos de produção, limitações de infraestrutura e armadilhas técnicas encontrados durante o ciclo completo de desenvolvimento, teste e deploy do sistema (Local + GitHub + Vercel Cloud). O objetivo é fornecer uma **fonte da verdade definitiva** para prevenir a reincidência de erros em projetos futuros baseados em IA Multiagente, APIs financeiras e interfaces web em tempo real.

---

## 1. AMBIENTE CLI, SCRIPTS DE INICIALIZAÇÃO & CODIFICAÇÃO (WINDOWS)

### Erro 1.1: Caracteres Fantasmas e Falha de Sintaxe em Scripts `.bat`
* **Sintoma / Log:**
  ```text
  '0B' não é reconhecido como um comando interno ou externo...
  'MESA' não é reconhecido como um comando interno ou externo...
  'cho' não é reconhecido como um comando interno ou externo...
  'cho.' não é reconhecido como um comando interno ou externo...
  ```
* **Causa-Raiz:**
  1. Arquivos `.bat` salvos com codificação **UTF-8 com BOM** (Byte Order Mark) inserem bytes ocultos (`EF BB BF`) no início do arquivo, corrompendo a leitura da primeira linha pelo `cmd.exe`.
  2. Quebra de linha inconsistente (mistura de LF de editores Linux/VS Code com CRLF exigido pelo Windows Batch).
  3. Uso de caracteres com acentos (ex: `Operações`, `Opções`, `Concluído`) sem declarar explicitamente a página de código `chcp 65001`.
* **Correção Arquitetural:**
  1. No topo de todo script `.bat` no Windows, declarar obrigatoriamente:
     ```bat
     @echo off
     chcp 65001 >nul
     setlocal enabledelayedexpansion
     ```
  2. Salvar sempre em **UTF-8 sem BOM** e quebras de linha **CRLF**.
  3. Utilizar strings limpas nos comandos `echo` e encapsular variáveis e caminhos de diretório entre aspas duplas: `"%~dp0"`.

---

## 2. CONSUMO DE LLM, LIMITES DE COTA E RESILIÊNCIA (`429 RESOURCE_EXHAUSTED`)

### Erro 2.1: Esgotamento de Quota no Google Gemini Flash
* **Sintoma / Log:**
  ```text
  429 RESOURCE_EXHAUSTED: You exceeded your current quota, please check your plan and billing details.
  GenerateRequestsPerDayPerProjectPerModel-FreeTier / generativelanguage.googleapis.com
  limit: 20, model: gemini-2.5-flash / gemini-3-flash
  ```
* **Causa-Raiz:**
  1. **Acoplamento rígido a um único modelo:** O código instanciava `gemini-2.5-flash` ou `gemini-3-flash` para todos os 6 agentes da esteira.
  2. **Multiplicação exponencial de requisições:** Uma única execução da esteira acionava 6 agentes sequenciais, cada um realizando de 2 a 4 chamadas internas (planejamento, uso de tools, síntese). Uma única rodada consumia ~18 a 24 requisições, estourando imediatamente a cota diária/minuto do Free Tier.
* **Correção Arquitetural:**
  1. **Esteira de Fallback Multi-Modelo Dinâmica:**
     Implementação em `crew.py` de uma cadeia de contingência transparente. Se o modelo prioritário devolver código `429`, o sistema chaveia automaticamente para o próximo:
     ```python
     MODELOS_DISPONIVEIS = [
         "gemini/gemini-flash-latest",
         "gemini/gemini-2.5-flash",
         "gemini/gemini-2.0-flash",
         "gemini/gemini-1.5-flash"
     ]
     ```
  2. **Separação entre Inteligência e Cálculo Numérico:**
     * Cálculos matemáticos (Gregas Black-Scholes, Volatilidade Anualizada de 252 dias, Stop Loss, Alvos de Retorno) **nunca são delegados ao prompt do LLM**. São executados em Python puro (`tools/`).
     * Isso reduz o consumo de tokens em mais de 70% e elimina alucinações matemáticas.
  3. **Controle Estrito de Iterações:**
     * Configurar `max_iter=2` ou `max_iter=3` nos agentes de pesquisa (Analista Macro e Técnico) para evitar loops infinitos de busca web.

---

## 3. ARQUITETURA SERVERLESS (VERCEL) VS. PIPELINE ASSÍNCRONO LOCAL

### Erro 3.1: Mídia e Imagens 2K Ausentes no Deploy Remoto (404 Not Found)
* **Sintoma / Log:**
  Imagens dos analistas (`midia/analista_macro.jpg`, etc.) e vídeo de demonstração (`workflow_demo.mp4`) exibiam erro 404 em produção na Vercel, embora funcionassem perfeitamente no servidor local.
* **Causa-Raiz:**
  1. **Case-Sensitivity no Linux da Nuvem:** No Windows, `Midia/` e `midia/` são idênticos. No ambiente Linux do Vercel Serverless, a pasta chamava-se `Midia/`, mas a aplicação buscava `/midia/`.
  2. **Árvore de Arquivos Excluída pelo Bundler da Vercel:** O runtime da Vercel inclui por padrão apenas o arquivo de entrada da função serverless e suas dependências diretas de código, ignorando diretórios estáticos customizados a menos que explicitamente configurados.
* **Correção Arquitetural:**
  1. Padronização de pastas em minúsculas: `midia/`.
  2. Declaração explícita no arquivo `vercel.json`:
     ```json
     {
       "builds": [
         {
           "src": "server.py",
           "use": "@vercel/python",
           "config": {
             "includeFiles": [
               "midia/**",
               "output/**",
               "static/**",
               "tools/**"
             ]
           }
         }
       ]
     }
     ```
  3. Implementação de rota estática dedicada no FastAPI (`server.py`) com headers de cache agressivos para imagens e fallback automático entre caminhos relativos e absolutos:
     ```python
     @app.get("/midia/{filename}")
     async def get_midia_file(filename: str):
         # Resolução dinâmica compatível com Local e Vercel Serverless
     ```

### Erro 3.2: Divergência entre Threads em Background e Serverless Lifespan
* **Sintoma / Causa-Raiz:**
  A Vercel congela ou destrói a instância serverless imediatamente após o retorno da resposta HTTP. Portanto, iniciar uma thread de 3 minutos via `threading.Thread(target=executar_crew)` em ambiente serverless resulta em encerramento prematuro da execução.
* **Correção Arquitetural:**
  * **Duplo Modo Transparente:**
    * **Ambiente Local (On-Premise / Servidor Dedicado):** Executa a esteira CrewAI completa ao vivo, disparando chamadas reais à BRAPI, Google Gemini e geração de PDF via `iniciar_mesa.bat`.
    * **Ambiente Vercel (Cloud Showcase):** Executa em modo demonstrativo institucional auditado, com dados de referência, banners de transparência e simulação didática da deliberação.
  * **Zero Decepção / Compliance Estrito:** A interface exibe claramente o banner `"MODO DEMO"` quando executado na Vercel, informando onde e como rodar a esteira com agentes reais ao vivo.

---

## 4. PROVENIÊNCIA DE DADOS VS. DADOS FABRICADOS

### Erro 4.1: Alucinação de Múltiplos Financeiros e Preços de Opções
* **Problema Encontrado:**
  Modelos de linguagem tendem a inventar valores de P/L, ROE e preços de strikes caso a ferramenta retorne vazia ou falhe. Em mercados financeiros e compliance CVM (Resolução nº 20/2021), isso é considerado falta grave.
* **Correções Implementadas:**
  1. **Gate Anti-Fabricação:** Nenhuma métrica contábil é inferida pelo LLM. Os dados são extraídos diretamente dos balanços oficiais via API da BRAPI.
  2. **Fallback Prudencial com Rotulação:** Se a API externa estiver fora do ar, o sistema não inventa dados: ele utiliza dados de referência históricos devidamente rotulados com a tag `[DADO_HISTORICO_AUDITADO]` ou aciona o status `DADO_INDISPONIVEL`.
  3. **Veto Programático em Código (`tools/risk_gate.py`):**
     * O Coordenador de Risco não é apenas um prompt: ele possui um **Gate Determinístico em Python**.
     * Regra matemática: se a relação Risco/Retorno for inferior a $1.50 : 1$, o código força a deliberação:
       $$\text{Status} = \text{VETADO\_TOTAL} \quad \implies \quad \text{Diretriz} = \text{"MANTER 100\% EM CAIXA / CDI"}$$
     * Nenhum agente, nem mesmo o usuário no prompt, pode sobrepor esse veto de segurança de capital.

---

## 5. MECÂNICA DE DERIVATIVOS B3

### Erro 5.1: Proposição de Séries de Opções Sem Liquidez (Séries Semanais)
* **Problema Encontrado:**
  Na B3, a liquidez de opções concentra-se em mais de 98% nas **3ª sextas-feiras de cada mês** (séries mensais homologadas). Séries semanais (W1, W2, etc.) têm book vazio, gerando spreads gigantescos e inviabilidade de execução.
* **Correção Arquitetural:**
  * Inclusão de regra mandatória na Skill do Estrategista de Derivativos: estruturar travas e operações **estritamente para o vencimento mensal vigente ou subsequente** (3ª sexta-feira do mês de referência).
  * Descarte automático de séries semanais.

---

## 6. DESIGN SYSTEM RESPONSIVO MULTIPLATAFORMA (MOBILE, TABLET, DESKTOP)

### Erro 6.1: Quebra de Layout e Overflow Horizontal em Smartphones
* **Sintoma:**
  Em telas de celulares (360px a 430px), a interface quebrava, criava barras de rolagem horizontal indesejadas, textos ficavam ilegíveis e botões importantes sumiam para fora da tela.
* **Causa-Raiz Técnica:**
  1. Grid de agentes configurado com `minmax(360px, 1fr)`. Em telas de celular de 360px com padding lateral de 24px, a largura disponível era de apenas 312px, forçando overflow horizontal.
  2. Gráficos configurados com `minmax(500px, 1fr)`.
  3. Ausência de `@media queries` completas nos arquivos CSS.
  4. Tabelas com 10 colunas sem contêiner com rolagem horizontal touch.
  5. Grid de Gregas (Delta, Gamma, Vega, Theta) espremido em 4 colunas em telas verticais estreitas.
* **Correção Arquitetural Implementada:**
  1. **Uso de Funções Matemáticas Modernas no Grid:**
     ```css
     .agents-grid {
       display: grid;
       grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
       gap: 1.25rem;
     }
     ```
  2. **Breakpoints Progressivos:**
     * **Desktop ($> 1100\text{px}$):** 3 colunas de agentes, 2 colunas de gráficos, 4 colunas de métricas.
     * **Tablet ($768\text{px} - 1100\text{px}$):** 2 colunas de agentes, 1 coluna de gráficos em 100% de largura, 2 colunas de métricas.
     * **Mobile ($< 768\text{px}$):** 1 coluna de agentes, 1 coluna de gráficos com altura dinâmica (`clamp(220px, 45vw, 300px)`), abas horizontais com `-webkit-overflow-scrolling: touch; scroll-snap-type: x mandatory;`.
     * **Mobile Pequeno ($< 480\text{px}$):** Gregas em grid 2x2, inputs com `font-size: 16px` (prevenindo zoom involuntário no Safari iOS), tabelas com barra de rolagem horizontal inercial.
  3. **Chart.js Resilient Config:**
     * `responsive: true`, `maintainAspectRatio: false` aplicados em todos os gráficos, com método `.resize()` disparado na alternância de abas.

---

## 7. RESUMO DE DIRETRIZES PARA NOVOS PROJETOS

| Domínio | Regra de Ouro |
| :--- | :--- |
| **CLI / Scripts** | Todo script Windows `.bat` deve usar UTF-8 sem BOM, CRLF e `chcp 65001`. |
| **LLMs** | Sempre implementar cadeia de fallback multi-modelo (`gemini-flash-latest` $\rightarrow$ `gemini-2.5` $\rightarrow$ `gemini-2.0`). |
| **Matemática** | A IA nunca faz contas de cabeça. Toda fórmula deve rodar em Python puro sob `@tool`. |
| **Dados** | Tolerância zero com fabricação. Se a API falhar, declare indisponível ou use histórico rotulado. |
| **Risco** | Veto programático em código não negociável. Risco/Retorno $< 1.50:1$ = Caixa 100%. |
| **Frontend** | Toda interface web deve ser responsiva por padrão em mobile, tablet e desktop, sem overflow horizontal. |
| **Deploy** | Configurar `vercel.json` com `includeFiles` explícito para todos os diretórios estáticos e templates. |
