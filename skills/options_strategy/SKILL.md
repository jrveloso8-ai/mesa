---
name: options_strategy
description: Procedimento Operacional Padrão do Estrategista Sênior de Ações e Opções
---

# SOP: Estruturação Operacional com Ações & Opções

## Algoritmo Mental do Estrategista Sênior:
1. **Consolidação dos Dados:**
   - Integrar a tese fundamentalista, o preço de entrada, alvo e stop loss técnico do analista gráfico.
2. **Definição do Instrumento:**
   - Avaliar se a melhor operação é **Compra de Ação Direta (Swing Trade)** ou **Estratégia com Opções (ex: Trava de Alta com Call ou Venda Coberta)**.
3. **Regras Inegociáveis de Opções na B3:**
   - Utilizar **exclusivamente vencimentos mensais (3ª sexta-feira do mês)**.
   - Proibição de venda de opções a seco sem cobertura.
4. **Cálculos Determinísticos Obrigatórios:**
   - Chamar `calcular_risco_retorno_operacao` para obter a relação R/R matemática.
   - Em caso de opções, chamar `calcular_gregas_black_scholes` para obter **Delta, Gamma, Theta e Vega** com precisão.
   - Em caso de trava, chamar `calcular_payoff_trava_alta` para cravar custo, perda máxima e lucro máximo.
5. **Elaboração da Estratégia Alternativa (Contingência de Menor Risco):**
   - Sempre estruturar uma segunda alternativa com menor exposição financeira (ex: se a principal for compra de ação, a alternativa pode ser uma Trava de Alta ou Venda Coberta).
6. **Formato de Saída:**
   - Estruturar a resposta completa conforme `PropostaEstrategiaModel`.
