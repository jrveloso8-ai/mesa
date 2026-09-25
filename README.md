# 🏛️ Mesa de Operações B3 - Multiagente CrewAI (IBRX-10)

Sistema corporativo de Inteligência Artificial e Mesa de Operações multiagente construído sobre o framework **CrewAI**, integrando dados oficiais da **BRAPI**, análise quantitativa determinística de derivativos (modelo **Black-Scholes**) e governança estrita de risco.

---

## 🏗️ Arquitetura do Pipeline

O pipeline opera de forma sequencial com 6 agentes especializados e contratos tipados com **Pydantic**:

```
[Analista Macro] -> [Analista Fundamentalista] -> [Analista Técnico] -> [Estrategista Opções] -> [Coordenador de Risco] -> [Publisher Research]
      │                         │                       │                     │                          │                       │
DuckDuckGo                 BRAPI Cotações         BRAPI Histórico       Black-Scholes & Payoff        Auditoria Dupla         Dashboard Console
Notícias & Selic         Múltiplos Valuation       SMA20/50 & RSI-14     Gregas & Vencimento B3      Principal / Alternativa    & PDF CVM 20/2021
```

1. **`macro_analyst`:** Analisa conjuntura macroeconômica, juros (Copom/Fed), câmbio, commodities e define os 2 a 3 ativos candidatos do **IBRX-10**.
2. **`fundamentalist_analyst`:** Consulta os múltiplos oficiais via BRAPI (P/L, ROE, DY, Margem Líquida, Dívida) e elege o melhor ativo.
3. **`technical_analyst`:** Analisa médias móveis (SMA20/50), suportes, resistências e RSI-14 para cravar o timing de entrada e o Stop Loss.
4. **`senior_strategist`:** Desenha a operação (Ações ou Opções - Travas / Venda Coberta) focando na **3ª sexta-feira do mês (B3)**, calculando deterministamente as gregas (Delta, Gamma, Theta, Vega) e preparando uma estratégia principal e uma alternativa de menor risco.
5. **`risk_coordinator`:** Audita os parâmetros. Se a principal for arriscada, avalia a alternativa. Se ambas forem reprovadas, orienta espera no caixa.
6. **`research_publisher`:** Formata o Resumo Executivo Formal, renderiza o Dashboard no console e gera o **PDF oficial com o Disclaimer da Resolução CVM nº 20/2021**.

---

## 📂 Estrutura Modular de Pastas

```
Oper/
├── .env                              # Credenciais da API (GOOGLE_API_KEY, BRAPI_TOKEN)
├── .env.example                      # Template de variáveis
├── pyproject.toml                    # Gerenciamento de dependências via uv
├── main.py                           # Ponto de entrada CLI e Dashboard Executivo
├── crew.py                           # Orquestração CrewAI com CrewBase, Agents e Tasks
├── config/
│   ├── agents.yaml                   # Personas, papéis, objetivos e backstories
│   └── tasks.yaml                    # Tarefas declarativas e saídas esperadas
├── skills/                           # Procedimentos Operacionais Padrão (SOPs)
│   ├── macro_analysis/SKILL.md
│   ├── fundamental_screening/SKILL.md
│   ├── technical_timing/SKILL.md
│   ├── options_strategy/SKILL.md
│   ├── risk_governance/SKILL.md
│   └── research_publishing/SKILL.md
├── knowledge/                        # RAG Temático e Regras da B3
│   ├── b3/vencimentos_opcoes.md      # Regras de vencimentos mensais e séries de opções B3
│   ├── risco/politica_mesa.md        # Política de governança de risco e stop loss
│   └── macro/universo_ibrx10.md      # Guia dos 10 ativos do IBRX-10
├── tools/                            # Ferramentas Python determinísticas (@tool)
│   ├── brapi_tools.py                # Cotações, múltiplos, histórico e opções BRAPI
│   ├── options_tools.py              # Black-Scholes exato, Gregas e Payoff de travas
│   ├── search_tools.py               # Busca web em tempo real (DuckDuckGo)
│   └── pdf_generator.py              # Gerador de relatórios formais em PDF (fpdf2)
├── schemas/                          # Contratos de dados Pydantic
│   └── output_models.py              # Modelos tipados e validados sintaticamente
└── output/                           # Relatórios gerados (.md e .pdf)
```

---

## 🚀 Como Executar

### Opção 1: Painel Visual Interativo no Navegador (Recomendado)
Dê um **duplo clique** no arquivo **`iniciar_mesa.bat`** (ou execute `.\iniciar_mesa.bat` no terminal).
- Ele iniciará o servidor FastAPI e abrirá automaticamente o **Dashboard Visual no seu navegador**:
  👉 **`http://localhost:8000`**
- No painel, você visualiza os cards dos 6 agentes em tempo real, os logs ao vivo, a deliberação completa e o botão para baixar o **Relatório PDF**.

### Opção 2: Modo Console Terminal
Caso prefira rodar diretamente dentro da janela de comando:
- Execute **`iniciar_console.bat`** ou `python main.py`.

### 3. Resultados Gerados
- **Console:** Dashboard estilizado com métricas, gregas, tese e aviso legal.
- **Relatório PDF:** Salvo automaticamente em `output/relatorio_operacao_YYYYMMDD_HHMMSS.pdf` pronto para envio ao investidor.
- **Relatório Markdown:** Salvo em `output/relatorio_recomendacao.md`.
