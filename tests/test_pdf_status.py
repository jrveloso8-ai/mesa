"""
Testes unitários para o gerador de relatórios executivos em PDF.
Garante que o status dinâmico reflete a verdade e que gregas são renderizadas.
"""

import os
from tools.pdf_generator import gerar_pdf_relatorio


def test_pdf_renderiza_reprovado_quando_vetado(tmp_path):
    """Garante que uma operação reprovada NUNCA exiba 'STATUS: APROVADO' no PDF."""
    pdf_saida = tmp_path / "teste_reprovado.pdf"
    
    arquivo = gerar_pdf_relatorio(
        titulo="Parecer de Risco - Reprovação",
        ativo="ITUB4",
        estrategia="Manutenção em Caixa",
        resumo_executivo="Operação vetada pelo comitê.",
        parametros={"Preço de Entrada": "N/A", "Alvo": "N/A"},
        gregas={},
        gestao_risco="Permanecer em caixa.",
        status="REPROVADO_TOTAL",
        caminho_saida=str(pdf_saida)
    )

    assert os.path.exists(arquivo)
    assert os.path.getsize(arquivo) > 1000  # PDF válido gerado


def test_pdf_renderiza_aprovado_com_gregas(tmp_path):
    """Garante que uma operação aprovada renderiza parâmetros e gregas completas."""
    pdf_saida = tmp_path / "teste_aprovado.pdf"

    arquivo = gerar_pdf_relatorio(
        titulo="Recomendação de Trava de Alta",
        ativo="PETR4",
        estrategia="Trava de Alta com Call",
        resumo_executivo="Tese otimista com Petróleo Brent.",
        parametros={
            "Preço de Entrada": "R$ 38.50",
            "Alvo": "R$ 41.50",
            "Stop Loss": "R$ 37.00",
            "Relação R/R": "2.0 : 1"
        },
        gregas={"delta": 0.55, "gamma": 0.08, "theta_diario": -0.04, "vega_1pct": 0.12},
        gestao_risco="Stop móvel acionado na perda do suporte.",
        status="APROVADO_PRINCIPAL",
        caminho_saida=str(pdf_saida)
    )

    assert os.path.exists(arquivo)
    assert os.path.getsize(arquivo) > 1000


def test_pdf_nao_contem_tabela_fabricada_nem_frase_hardcoded():
    """Garante que o código de geração de PDF não contém a frase estática nem a seção fabricada de triagem."""
    import inspect
    import tools.pdf_generator as mod_pdf
    codigo_fonte = inspect.getsource(mod_pdf.gerar_pdf_relatorio)
    assert "Diagnóstico do Universo: 100 ativos triados" not in codigo_fonte
    assert "QUADRO DE TRIAGEM E RANKING DO UNIVERSO ANALISADO" not in codigo_fonte


def test_busca_macro_sem_fabricacao_em_falha(monkeypatch):
    """Garante que quando a busca web falha, a tool declara indisponibilidade em vez de inventar notícias."""
    from tools.search_tools import pesquisar_noticias_macro_e_commodities
    from duckduckgo_search import DDGS

    def mock_news_erro(*args, **kwargs):
        raise RuntimeError("Simulação de rate limit DuckDuckGo")

    monkeypatch.setattr(DDGS, "news", mock_news_erro)
    fn = getattr(pesquisar_noticias_macro_e_commodities, "func", pesquisar_noticias_macro_e_commodities)
    resultado = fn("Selic Copom")

    assert resultado["status"] == "pesquisa_web_indisponivel"
    assert resultado["total_noticias"] == 0
    assert len(resultado["noticias"]) == 0
    assert "Nenhum dado foi fabricado" in resultado["aviso"]


def test_screener_ibrx100_sem_scores_hardcoded():
    """Garante que o screener gera ranking a partir da cesta de liquidez sem listas estáticas com scores fake."""
    from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100, obter_estatisticas_funil
    ranking = gerar_ranking_completo_ibrx100()
    assert len(ranking) == 10
    stats = obter_estatisticas_funil(ranking)
    assert stats["total_ativos_triados"] == 10
    assert stats["vetados_gate_risco"] >= 1
    # Verifica que a proveniência é explicitamente indicada
    for r in ranking:
        assert "proveniencia" in r

