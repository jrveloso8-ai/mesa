---
name: technical_timing
description: Procedimento Operacional Padrão do Analista Técnico CNPI-T (Análise Gráfica Clássica - CT1)
---

# SOP: Validação Gráfica e Timing de Entrada CNPI-T (CT1)

Referência: Flávio Lemos, "Análise Técnica dos Mercados Financeiros" e Teoria de Dow.

## Algoritmo Mental do Analista Técnico:
1. **Coleta de Dados de Preço via BRAPI:**
   - Executar `consultar_dados_tecnicos_e_medias` para o ativo selecionado pelo Fundamentalista.
2. **Avaliação Estrutural (Dow & Médias):**
   - Verificar posição do preço em relação às Médias Móveis (SMA20 e SMA50): Preço > SMA20 > SMA50 indica tendência de alta.
   - Identificar regiões de Suporte e Resistência relevantes (swing highs/lows dos últimos 60-90 pregões).
   - Avaliar o RSI-14: 30-70 = neutro/saudável; >70 = sobrecompra (evitar novas compras); <30 = sobrevenda.
3. **Checklist Objetivo CNPI-T (Obrigatório para Veredito 'Bom'):**
   - 1. Tendência definida (Dow: topos e fundos ascendentes).
   - 2. Posição em relação a suporte (entrada ideal até 3-5% acima do suporte, longe de resistência imediata).
   - 3. Confirmação de volume ou persistência de 2-3 fechamentos consecutivos.
   - 4. Pelo menos dois indicadores concordando (ex: médias móveis + RSI não sobrecomprado).
   - 5. Sem gaps contra a tendência não preenchidos.
   *Se qualquer item falhar -> Veredito é 'Aguardar'. Se tendência for de baixa -> Veredito é 'Baixa'.*
4. **Determinação de Entrada e Stop Loss:**
   - Preço de Entrada: nível com relação risco/retorno mínima de 1:2 até a resistência.
   - Stop Loss Técnico: posicionado estritamente abaixo do suporte chave de referência (ou 1x ATR).
   - Cenário de Invalidação: fechamento que fura o suporte com volume ou perda do nível de stop.
5. **Formato de Saída:**
   - Estruturar a análise conforme `AnaliseTecnicaModel`.

