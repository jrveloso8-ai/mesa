# Diretrizes Oficiais de Opções na B3 - Foco em Vencimentos Mensais

## Regra de Ouro da Liquidez de Opções na B3
Na Bolsa de Valores Brasileira (B3), a liquidez real de opções, o volume institucional e a atuação efetiva dos formadores de mercado concentram-se **quase exclusivamente nas 3ªs sextas-feiras de cada mês (Séries Mensais)**.

- **Séries Semanais (W1, W2, W4, etc.):** Possuem book de ofertas vazio, spreads de compra/venda impraticáveis e alto risco de execução. A Mesa de Operações deve **rejeitar ou filtrar categoricamente séries semanais**.
- **Séries Mensais (3ª Sexta-Feira):** Concentram mais de 98% da liquidez em opções sobre ações na B3 (ex: PETR4, VALE3, ITUB4).

## Tabela de Letras de Vencimento na B3
Cada mês do ano possui uma letra designada para CALLS (Opções de Compra) e PUTS (Opções de Venda):

| Mês de Vencimento | CALL (Compra) | PUT (Venda) |
| :--- | :---: | :---: |
| Janeiro | A | M |
| Fevereiro | B | N |
| Março | C | O |
| Abril | D | P |
| Maio | E | Q |
| Junho | F | R |
| Julho | G | S |
| Agosto | H | T |
| Setembro | I | U |
| Outubro | J | V |
| Novembro | K | W |
| Dezembro | L | X |

*Exemplo:* `PETRK380` = CALL de PETR4 com vencimento em Novembro (letra K) e strike próximo a R$ 38,00.

## Estratégias Recomendadas para Mesa
1. **Trava de Alta com Call (Bull Call Spread):** Compra Call ATM/ITM + Venda Call OTM na mesma série mensal. Risco limitado estritamente ao prêmio líquido pago.
2. **Venda Coberta de Call (Covered Call / Financiamento):** Ativo em carteira + venda de Call OTM para monetização da taxa e proteção parcial.
3. **Trava de Baixa com Put (Bear Put Spread):** Compra Put ATM/ITM + Venda Put OTM na mesma série mensal.
