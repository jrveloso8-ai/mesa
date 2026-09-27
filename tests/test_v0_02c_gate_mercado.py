"""
Testes unitários para [V0-02c]:
Validação estrita de mercado e opções diretamente no Gate de Risco sem confiar nos agentes.
Pronto quando:
1. Trava com origem digitada pelo agente mas cadeia simulada como PROJECAO -> veto.
2. Prêmio 20% acima do da cadeia -> veto.
3. Strike inexistente na cadeia -> veto.
4. Trava coerente com a cadeia simulada -> aprova.
5. Ação com entrada 10% acima do preço simulado -> veto.
6. Ferramenta de cotação falhando -> veto.
"""

import pytest
from schemas.output_models import DecisaoRiscoModel, RelatorioExecutivoFinal
from tools.risk_gate import auditar_gate_de_risco_programatico


@pytest.fixture
def mock_dados_tecnicos_ok(monkeypatch):
    """Simula retorno com sucesso da ferramenta de dados técnicos com spot em R$ 40,00."""
    monkeypatch.setattr(
        "tools.risk_gate.consultar_dados_tecnicos_e_medias",
        lambda ticker: {
            "status": "sucesso",
            "ticker": ticker,
            "preco_atual": 40.0,
            "sma_20": 39.5,
        }
    )


@pytest.fixture
def mock_cadeia_opcoes_medida_ok(monkeypatch):
    """Simula cadeia de opções auditada da BRAPI com strikes 40 e 44."""
    monkeypatch.setattr(
        "tools.risk_gate.consultar_cadeia_opcoes_b3",
        lambda ticker: {
            "status": "sucesso",
            "origem": "BRAPI_V2_OPTIONS_MEDIDO",
            "dados": [
                {"symbol": f"{ticker}D400", "strike": 40.0, "close": 1.50},
                {"symbol": f"{ticker}D440", "strike": 44.0, "close": 0.50},
            ]
        }
    )


def test_1_trava_origem_digitada_mas_cadeia_projecao_veta(monkeypatch, mock_dados_tecnicos_ok):
    """(1) Trava com origem digitada pelo agente mas cadeia simulada como PROJEÇÃO -> veto."""
    monkeypatch.setattr(
        "tools.risk_gate.consultar_cadeia_opcoes_b3",
        lambda ticker: {
            "status": "sucesso",
            "origem": "PROJECAO_SOBRE_SPOT_MEDIDO_BRAPI",
            "strikes_sugeridos": {"ITM_compra_alta": 38.4, "ATM_neutro": 40.0, "OTM_venda_alta": 41.6}
        }
    )

    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=3.0,
        ativo="PETR4",
    )

    # Agente tentou burlar escrevendo origem_premios="BRAPI_V2_OPTIONS_MEDIDO"
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=40.0,
        strike_venda=44.0,
        premio_compra=1.50,
        premio_venda=0.50,
        rr_declarado=3.0,
        origem_premios="BRAPI_V2_OPTIONS_MEDIDO",
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "Premios sem cotacao real" in motivo or "PROJECAO" in motivo.upper()


def test_2_trava_premio_20pct_acima_da_cadeia_veta(mock_dados_tecnicos_ok, mock_cadeia_opcoes_medida_ok):
    """(2) Prêmio 20% acima do da cadeia (1.80 vs 1.50 da cadeia) -> veto."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,
        ativo="PETR4",
    )

    # Cadeia tem compra em 1.50; proposta enviou 1.80 (20% de divergência > 5%)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=40.0,
        strike_venda=44.0,
        premio_compra=1.80,
        premio_venda=0.50,
        rr_declarado=2.0,
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "diverge mais de 5%" in motivo


def test_3_trava_strike_inexistente_na_cadeia_veta(mock_dados_tecnicos_ok, mock_cadeia_opcoes_medida_ok):
    """(3) Strike inexistente na cadeia (strike 38 não existe na cadeia simulada) -> veto."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=3.0,
        ativo="PETR4",
    )

    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=38.0,  # Inexistente
        strike_venda=44.0,
        premio_compra=1.50,
        premio_venda=0.50,
        rr_declarado=3.0,
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "inexistente na cadeia de opcoes" in motivo


def test_4_trava_coerente_com_cadeia_simulada_aprova(mock_dados_tecnicos_ok, mock_cadeia_opcoes_medida_ok):
    """(4) Trava coerente com a cadeia simulada -> aprova."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=3.0,
        ativo="PETR4",
    )

    # Spread 4.0, custo 1.0 (1.50 - 0.50) -> Lucro 3.0, R/R = 3.0
    # Strike 40.0 é idêntico ao spot 40.0 (0% <= 10%)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=40.0,
        strike_venda=44.0,
        premio_compra=1.50,
        premio_venda=0.50,
        rr_declarado=3.0,
        ticker="PETR4",
    )

    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"
    assert "Aprovado pelo Comitê de Risco" in motivo


def test_5_acao_entrada_10pct_acima_preco_simulado_veta(mock_dados_tecnicos_ok):
    """(5) Ação com entrada 10% acima do preço simulado (44.0 vs 40.0) -> veto."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,
        ativo="PETR4",
    )

    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=44.0,  # 10% acima de 40.0
        preco_alvo=50.0,
        preco_stop=41.0,
        rr_declarado=2.0,
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "diverge mais de 5%" in motivo


def test_6_ferramenta_cotacao_falhando_veta(monkeypatch):
    """(6) Ferramenta de cotação falhando -> veto 'Sem cotacao de referencia'."""
    monkeypatch.setattr(
        "tools.risk_gate.consultar_dados_tecnicos_e_medias",
        lambda ticker: {"status": "erro", "mensagem": "Falha de rede na BRAPI"}
    )

    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,
        ativo="PETR4",
    )

    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=40.0,
        preco_alvo=50.0,
        preco_stop=35.0,
        rr_declarado=2.0,
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "Sem cotacao de referencia" in motivo
