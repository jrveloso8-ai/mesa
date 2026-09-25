---
name: fundamental_screening
description: Procedimento Operacional Padrão do Analista Fundamentalista CNPI (Valuation e Finanças Corporativas - CG1)
---

# SOP: Triagem e Valuation Fundamentalista CNPI (CG1)

Referência: Certificação CNPI (Bloco CG1), Damodaran, CVM e Teoria de Criação de Valor.

## Algoritmo Mental do Analista Fundamentalista:
1. **Recebimento de Candidatos:**
   - Receber os 2 a 3 ativos sugeridos pelo Analista Macro.
2. **Coleta de Múltiplos e Balanços Reais via BRAPI:**
   - Executar `consultar_dados_fundamentalistas` para cada candidato.
   - Auditar dados contábeis: P/L, P/VP, EV/EBITDA, ROE, ROIC, Margem Líquida e Dívida Líquida/EBITDA.
3. **Checklist Objetivo de Confluência CG1 (Obrigatório para Veredito 'Bom'):**
   - 1. **Criação de Valor**: ROIC > WACC (se falhar $\rightarrow$ veredito 'ruim', value trap).
   - 2. **Endividamento Saudável**: Dívida Líquida/EBITDA < 3.0x (ou Dívida Líq/PL < 1.0x).
   - 3. **Cobertura de Juros**: EBIT / Despesa Financeira > 2.0x (ideal > 4.0x).
   - 4. **Qualidade dos Lucros**: FCO consistente com lucro líquido e sem não-recorrentes distorcendo.
   - 5. **Crescimento de Receita**: positivo em pelo menos 3 dos últimos 5 anos.
   - 6. **Valuation com Desconto ou Prêmio Justificado**: múltiplos atrativos frente à média histórica ou pares.
   *Exceção: Sem ROIC > WACC $\rightarrow$ veredito 'ruim'. Sem qualidade de lucros $\rightarrow$ no máximo 'neutro'.*
4. **Governança e ESG:**
   - Priorizar companhias no Novo Mercado da B3, com tag along de 100% e histórico disciplinado de alocação de capital.
5. **Eleição do Melhor Ativo:**
   - Selecionar **um único ativo** que cumpra o maior número de critérios do checklist de confluência.
6. **Formato de Saída:**
   - Produzir a resposta validada conforme `SelecaoFundamentalistaModel`.

