---
name: analise-tecnica-cnpi-t
description: Use sempre que o usuário pedir leitura de gráfico, identificação de tendência, padrão gráfico (candlestick, ponto e figura), suporte/resistência, ou indicador técnico clássico (médias móveis, RSI, MACD, Bollinger) em um ativo específico. Cobre o conteúdo do bloco CT1 da certificação CNPI-P — distinto de fluxo institucional/oferta-demanda (que é coberto pela skill trade-profissional). Dispare para "como está o gráfico de X", "tem algum padrão se formando em Y", "onde é o suporte/resistência".
---

# Análise Técnica Clássica (CT1)

Referência bibliográfica oficial do exame: Flávio Lemos, "Análise Técnica dos
Mercados Financeiros". Esta skill cobre o conteúdo de edital — leitura gráfica
clássica — e é complementar à skill `trade-profissional` (que cobre fluxo
institucional/oferta-demanda real de B3, um layer diferente e mais avançado).

## Princípio de entrada
Toda leitura técnica exige série de preço real (via conector), nunca descrição de
memória de "como o gráfico costuma se comportar". Se não houver dado de preço
disponível, declarar a limitação.

## Fundamentos (Dow, base de toda análise técnica)
- Mercado desconta tudo (preço reflete toda informação disponível)
- Preço se move em tendências (alta, baixa, lateral) até haver reversão confirmada
- Tendência tem três fases: acumulação, participação pública, distribuição
- Volume deve confirmar a tendência (alta com volume crescente é mais confiável que
  alta com volume caindo)

## Tipos de gráfico e quando cada um é mais útil
- **Linha**: visão macro de longo prazo, menos ruído
- **Barras/Candlestick**: análise de curto/médio prazo, revela psicologia do pregão
  (abertura, máxima, mínima, fechamento)
- **Ponto e Figura**: filtra ruído de tempo, foca só em movimento de preço
  significativo — útil para identificar suporte/resistência sem viés de timeframe
- **Escala aritmética vs logarítmica**: usar log em análises de longo prazo ou ativos
  com variação percentual grande (evita distorção visual em cripto/small caps);
  aritmética para curto prazo

## Padrões de reversão e continuação (candlestick)
**Requer Brapi MCP conectado** (fonte com OHLC real). Se só houver fechamento
disponível (fallback MCP MR), não aplicar esta seção — declarar indisponível em vez
de estimar candle a partir de fechamento.
- Reversão de alta: martelo, engolfo de alta, estrela da manhã
- Reversão de baixa: estrela cadente, engolfo de baixa, estrela da noite
- Continuação: bandeiras, triângulos, retângulos
- Regra prática: padrão de candle isolado tem baixa confiabilidade sem confirmação de
  volume e de contexto de tendência (Dow) — nunca reportar um padrão sem essas duas
  camadas de confirmação.

## Suporte e resistência
- Identificar por: topos/fundos anteriores, médias móveis relevantes (20/50/200),
  níveis de Fibonacci, e OI/volume por preço (Volume Profile) quando disponível.
- Rompimento só é válido com fechamento além do nível + volume acima da média —
  rompimento intraday sem essas confirmações é ruído.

## Indicadores — parâmetros concretos (uso complementar, nunca isolado)
- **Médias móveis**: MM20 (curto), MM50 (médio), MM200 (longo). Tendência de alta
  confirmada = preço > MM20 > MM50 > MM200. Cruzamento MM20 acima da MM50 ("golden
  cross" curto) é gatilho de atenção, não de entrada isolada — tem atraso inerente,
  não usar sozinho em mercado lateral.
- **RSI(14)**: 30-70 = neutro/saudável. >70 = sobrecompra (evitar nova entrada aqui,
  mesmo com tendência de alta). <30 = sobrevenda (pode preceder reversão, mas não é
  confirmação de compra sozinho — precisa de outro item do checklist confirmando).
- **MACD(12,26,9)**: linha MACD cruzando acima da linha de sinal, com histograma
  positivo e crescente, confirma força da tendência de alta identificada nas médias.
  Usar como confirmação de momentum, nunca como gatilho isolado.
- **Bollinger(20,2)**: banda de 20 períodos, 2 desvios-padrão. Compressão das bandas
  sinaliza movimento forte a caminho (não indica direção sozinho). Preço tocando a
  banda superior sem os demais itens do checklist passando é alerta de exaustão, não
  gatilho de compra.
- **Volume vs. média de 20 dias** (requer Brapi MCP conectado): rompimento de
  suporte/resistência só é considerado válido com volume do dia ≥ 1,2x a média de
  volume dos últimos 20 dias. Sem Brapi conectado (fallback MCP MR, sem volume),
  usar o critério de persistência de fechamento (2-3 dias na nova direção) no lugar.
- **Suporte/resistência**: identificar por swing highs/lows dos últimos 60-90
  pregões. Entrada ideal: até ~3-5% acima do suporte de referência, nunca colada
  na resistência sem rompimento confirmado.

## Fonte de dado — Brapi MCP (fonte primária, precisa ser conectada uma vez)
A fonte correta para gráfico/técnico é o **servidor MCP oficial da Brapi**
(`https://brapi.dev/api/mcp/mcp`) — API brasileira que agrega OHLCV real (abertura,
máxima, mínima, fechamento, volume) de ações B3, oficial, já usada em outros
projetos do usuário (Simulador B3). Diferente de um fetch de página, isso é uma API
estruturada e não esbarra em bloqueio de robots.txt.

**Setup (uma vez, feito pelo usuário no Claude.ai ou Claude Code, não pelo agente em
runtime):** adicionar como conector MCP customizado usando a URL acima. As 5
primeiras ferramentas funcionam sem login; histórico completo/módulos avançados
pedem conta Brapi (OAuth automático na primeira conexão). Depois de conectado, o
projeto ganha acesso real a candlestick e volume — reabilitar as seções
correspondentes abaixo quando isso acontecer.

**Enquanto o Brapi MCP não estiver conectado**, usar `MCP MR:get_quotes` como
fallback — mas essa fonte só entrega fechamento diário, sem OHLC/volume (testado).
Nesse caso, aplicar apenas os itens do checklist de entrada que não dependem de
OHLC/volume (ver abaixo) e declarar explicitamente ao usuário que candlestick e
confirmação por volume estão indisponíveis até o Brapi MCP ser conectado.

## Critério de entrada — checklist objetivo (obrigatório antes de classificar "técnico: bom")

Esta é a peça que faltava: sem um critério explícito, "análise técnica" vira opinião
sobre o gráfico em vez de decisão replicável. O veredito técnico que alimenta
`sintese-decisao-timing` só pode ser "bom" (favorável a entrar agora) se **todos** os
itens abaixo forem verdadeiros — não é maioria, é checklist de confirmação.

1. **Tendência definida** (Dow): preço fazendo topos e fundos ascendentes (alta) ou
   claramente lateral em zona de acumulação — nunca "bom" em tendência de baixa
   confirmada, mesmo que pareça estar "barato".
2. **Posição em relação a suporte/resistência**: entrada deve estar próxima a um
   suporte relevante (com stop abaixo dele) — nunca perto de uma resistência forte
   sem rompimento confirmado por fechamento acima dela.
3. **Confirmação de volume** (requer Brapi MCP conectado) OU, se só houver fechamento
   disponível (fallback MCP MR): o rompimento/recuperação precisa se manter por pelo
   menos 2-3 fechamentos consecutivos na nova direção, não um único dia isolado.
4. **Pelo menos dois indicadores concordando**: ex. médias móveis (9/21 ou 20/50) em
   configuração de alta E RSI/estocástico não em sobrecompra extrema no momento da
   entrada. Um indicador isolado nunca é suficiente.
5. **Sem gap contra a tendência não preenchido**: gap/salto de queda recente sem
   recuperação é sinal de fragilidade mesmo com tendência de alta no timeframe maior.

Se qualquer item falhar → veredito técnico é **"aguardar"**, nunca "bom". Se a
tendência de fundo for de baixa confirmada → veredito é **"baixa"** (risco de "pegar
faca caindo"), independente de quão descontado o preço pareça.

## Stop técnico e critério de invalidação (obrigatório em toda entrada)
Todo veredito "bom" vem acompanhado de:
- Nível de stop técnico: abaixo do suporte usado como referência de entrada, ou
  alternativamente 1x ATR(14) abaixo do preço de entrada quando o suporte não for
  claramente definido — ATR mede volatilidade recente e evita stop arbitrário.
- Relação risco/retorno até o próximo nível de resistência relevante (mínimo
  aceitável: 1:2 — declarar quando a relação for pior que isso, mesmo com técnico
  favorável)
- O que exatamente invalida a leitura (ex.: fechamento abaixo do suporte X com
  volume acima da média, ou abaixo de X - 1 ATR)

## Formato de saída
1. Tendência principal identificada (timeframe explícito) + fonte do dado de preço
2. Padrão gráfico relevante, se houver, com confirmação de volume
3. Nível de suporte/resistência mais próximo relevante à decisão
4. Indicadores usados como confirmação (nunca como único fundamento)
5. Checklist de entrada (5 itens acima) — quantos passaram, qual falhou se houver
6. Veredito técnico final: bom / aguardar / baixa — com stop técnico e R:R se "bom"
7. Cenário de invalidação técnica explícito (nível de preço que quebra a leitura)
