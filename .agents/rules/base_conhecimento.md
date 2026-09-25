# Regras Operacionais e Base de Conhecimento Permanente
Referência direta aos arquivos do projeto:
- [`BASE_DE_CONHECIMENTO_ERROS_E_CORRECOES.md`](../../BASE_DE_CONHECIMENTO_ERROS_E_CORRECOES.md)
- [`PROMPT_MESTRE_CREWAI_PRODUCAO_V1.md`](../../PROMPT_MESTRE_CREWAI_PRODUCAO_V1.md)
- [`GEMINI.md`](../../GEMINI.md)

Toda e qualquer alteração neste repositório deve consultar e obedecer rigorosamente:
1. Anti-fabricação de dados: APIs oficiais reais (BRAPI / DuckDuckGo) ou falha prudencial rotulada.
2. Cálculos determinísticos em Python puro sob `tools/`.
3. Veto programático de risco se R/R < 1.50:1.
4. Vencimentos mensais de opções na B3 (3ª sextas-feiras).
5. Scripts Windows em UTF-8 sem BOM, CRLF e `chcp 65001`.
6. Paridade serverless Vercel (`includeFiles` no `vercel.json` e minúsculas para pastas de mídia).
7. Responsividade mobile total (320px–768px, tablets e desktops).
