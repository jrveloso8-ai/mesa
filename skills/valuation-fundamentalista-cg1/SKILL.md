---
name: valuation-fundamentalista-cg1
description: Use sempre que o usuário pedir valuation, análise de múltiplos, análise de balanço, cálculo de WACC/ROIC, fluxo de caixa descontado (DCF), governança ou qualidade de lucros em um ativo específico. Cobre o conteúdo do bloco CG1 da certificação CNPI. Dispare para "qual o valuation de X", "o múltiplo de Y está caro", "qual a qualidade dos lucros de Z", "ROIC maior que WACC".
---

# Valuation Fundamentalista (CG1)

Referência bibliográfica e regulatória: Certificação CNPI (Bloco CG1 - Conteúdo Global 1), livro "Valuation: Como Avaliar Empresas e Escolher as Melhores Ações" (Damodaran / McKinsey), Livro TOP Análise de Investimentos (CVM/APIMEC) e framework IIRC de Relato Integrado.

## Princípio de Entrada
Todo número usado no valuation tem que vir de dado real.
- **Fontes Primárias**: BRAPI como fonte primária via ferramentas do sistema e Relações com Investidores (RI) da empresa.
- **Fontes Regulatórias**: CVM RAD $\rightarrow$ dadosdemercado.com.br (agregador que linka aos documentos oficiais CVM) $\rightarrow$ B3 (listagem/governança) $\rightarrow$ StatusInvest / Investidor10 (último recurso, apenas para múltiplos de contexto).
- **Regra de Integridade**: Se o dado não estiver disponível em nenhuma fonte, declare a lacuna — nunca estime "de memória" nem invente números.

## Critério de Veredito — Checklist Objetivo de Confluência (Obrigatório antes de classificar "fundamentos: bom")
Espelha o checklist da análise técnica: nenhum indicador isolado decide. O veredito fundamentalista só é **"bom"** se todos os itens abaixo passarem — não é média, é confluência mínima:

1. **Criação de Valor (ROIC > WACC)**:
   - Este é o critério central: uma empresa que entrega ROIC abaixo do seu próprio custo de capital destrói valor econômico, mesmo que apresente lucro contábil positivo.
   - Calcular ou estimar WACC via CAPM ($R_f$ = NTN-B longa ou Selic real, $\beta$ do setor, prêmio de risco de mercado + risco país Brasil).
   - Sem $ROIC > WACC$, nunca classificar como "bom", mesmo com múltiplos baratos (marca clássica de "value trap").
2. **Endividamento dentro do padrão setorial**:
   - Dívida Líquida / EBITDA < 3.0x como piso geral prudencial (ajustar por setor: utilities e concessões toleram mais até ~3.5x-4.0x; varejo, indústria e tecnologia exigem alavancagem mais baixa).
   - Se EBITDA for negativo ou não aplicável (ex.: holdings rurais com vendas não-recorrentes ou financeiras), usar Dívida Líquida / Patrimônio Líquido < 1.0x como critério substituto.
3. **Cobertura de Juros**:
   - Cobertura de Despesas Financeiras ($EBIT / \text{Despesa Financeira}$) > 2.0x (mínimo aceitável), ideal > 4.0x.
   - Abaixo de 2.0x, a operação fica refém do custo de rolagem da dívida — reportar como risco severo mesmo que o restante pareça bom.
4. **Qualidade de Earnings (Lucros Reais vs Contábeis)**:
   - FCO (Fluxo de Caixa Operacional) não pode ficar consistentemente abaixo do Lucro Líquido.
   - Ausência de itens não-recorrentes relevantes distorcendo o resultado do período utilizado nos múltiplos (ex.: créditos fiscais judiciais, reversões pontuais ou venda de ativos operacionais).
5. **Crescimento de Receita Consistente**:
   - Crescimento real ou nominal de receita positivo em pelo menos 3 dos últimos 5 anos.
   - Crescimento errático ou concentrado em um único ano não-operacional não configura tese estrutural de expansão.
6. **Valuation Relativo com Desconto ou Prêmio Justificado**:
   - P/L, P/VP ou EV/EBITDA abaixo da própria média histórica (3-5 anos) OU com desconto em relação aos pares diretos de mesmo porte e setor.
   - Se estiver negociando com prêmio, precisa haver justificativa explícita e mensurável (ex.: ROE ou margens estruturalmente superiores aos pares).

### Regras Estritas de Exceção:
- Se o **Item 1 (ROIC > WACC)** falhar: o veredito é obrigatoriamente **"ruim"**, independente dos outros itens — nenhuma combinação de múltiplos "baratos" compensa destruição continuada de valor.
- Se o **Item 4 (Qualidade de Earnings)** falhar: o veredito vira no máximo **"neutro"** com ressalva explícita, nunca "bom".

---

## Métodos de Avaliação e Quando Usar Cada Um

### 1. Fluxo de Caixa Descontado (DCF / FCD)
- **Aplicação**: Adequado para empresas com geração de caixa previsível e histórico operacional consistente.
- **Componentes**: FCFF (Fluxo de Caixa Livre da Firma) ou FCFE (para o Acionista), taxa de crescimento na perpetuidade ($g$), e WACC como taxa de desconto.
  $$\text{WACC} = \left(\frac{E}{V} \times K_e\right) + \left(\frac{D}{V} \times K_d \times (1 - T)\right)$$
  Onde $K_e = R_f + \beta \times (\text{Prêmio de Risco de Mercado}) + \text{Risco País}$.
- **Sensibilidade Obrigatória**: Apresentar o valuation em pelo menos 3 cenários de $g$ e WACC (Base, Otimista, Pessimista) — nunca entregar um número único pontual sem faixa.

### 2. Múltiplos Comparáveis (Valuation Relativo)
- **Seleção conforme o Setor**:
  - Bancos e Financeiras: P/VP e ROE.
  - Commodities cíclicas (Petróleo, Minério, Papel): EV/EBITDA normalizado.
  - Varejo e Consumo: EV/EBITDA e P/L.
  - Elétricas e Utilities: Dividend Yield sustentável e EV/EBITDA regulatório.
- **Comparabilidade**: Os pares devem compartilhar o mesmo modelo de negócio, porte e geografia. Sempre normalizar o lucro expurgando itens não-recorrentes.

### 3. Soma das Partes (SOTP - Sum of the Parts)
- Usar quando a companhia possui divisões de negócios distintas com dinâmicas e múltiplos discrepantes (ex.: conglomerados com divisão industrial e braço financeiro/logístico).

---

## Governança Corporativa (Bloco CG1)
Fatores mandatórios a ponderar na tese:
- **Estrutura Acionária**: Ações ON vs PN, existência de tag along de 100% para minoritários, dispersão do capital e free float (> 25%).
- **Segmento de Listagem na B3**: Novo Mercado (máximo padrão de governança), Nível 2, Nível 1 ou Tradicional (desconto de governança aplicado).
- **Alocação de Capital Histórica**: Política de dividendos vs recompra de ações, disciplina em aquisições (M&A) e remuneração da diretoria alinhada ao acionista.

---

## Integração ESG (Bloco CG1)
- O ESG **não é uma camada isolada ou cosmética**, mas sim um **ajuste direto de risco da tese**:
  - Passivos ambientais contingentes (risco regulatório, descarbonização, licenciamentos).
  - Riscos sociais (segurança do trabalho, relações com comunidades e passivos trabalhistas).
  - Riscos de governança (auditorias independentes, partes relacionadas, corrupção).
- Quantificar o impacto potencial no custo de capital ou fluxo de caixa sempre que possível.

---

## Formato de Saída do Analista Fundamentalista
1. **Ativo Analisado e Ticker** (com cotação de tela e data base).
2. **Métodos Utilizados e Racional de Adequação ao Setor**.
3. **Múltiplos e Indicadores Auditados** (P/L, P/VP, EV/EBITDA, ROE, ROIC, Margem Líquida, Dívida Líq/EBITDA).
4. **Checklist de Confluência dos 6 Critérios CG1**:
   - Detalhamento de cada critério (passou / falhou / observação).
5. **Veredito Fundamentalista Final**: `bom` / `neutro` / `ruim`.
6. **Faixa de Valor Intrínseco / Potencial** (Cenário Conservador, Base e Otimista).
7. **Principais Riscos e Gatilhos de Invalidação da Tese**.
