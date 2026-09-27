"""
Testes unitários para [V2-01]:
Validação de que a divergência de R/R não veta operações válidas, priorizando o R/R calculado
e registrando alerta_rr, mantendo o veto se o calculado for inferior ao piso de 1.50:1.
"""

import pytest
from schemas.output_models import DecisaoRiscoModel, RelatorioExecutivoFinal
from tools.risk_gate import auditar_gate_de_risco_programatico


def test_rr_calculado_3_declarado_2_aprova_e_grava_alerta_rr(monkeypatch):
    """
    [V2-01] Teste com calculado 3.00 e declarado 2.00 aprova (se as demais regras passarem)
    e grava alerta_rr ('R/R declarado pelo agente X; calculado Y; usado o calculado').
    """
    # Spot em 40.0
    monkeypatch.setattr(
        "tools.risk_gate.consultar_dados_tecnicos_e_medias",
        lambda ticker: {
            "status": "sucesso",
            "ticker": ticker,
            "preco_atual": 40.0,
            "sma_20": 39.5,
        }
    )

    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,  # Declarado 2.00
        ativo="PETR4",
    )

    relatorio = RelatorioExecutivoFinal(
        ativo_alvo="PETR4",
        preco_entrada=40.0,
        preco_alvo=46.0,  # Ganho = 6.0
        preco_stop=38.0,  # Perda = 2.0 -> Calculado = 6.0 / 2.0 = 3.00
    )

    res = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        relatorio=relatorio,
        preco_entrada=40.0,
        preco_alvo=46.0,
        preco_stop=38.0,
        rr_declarado=2.0,
        ticker="PETR4",
    )

    aprovado, status, motivo = res
    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"
    assert "3.00" in motivo

    # Verifica gravação do alerta_rr no resultado e no relatório
    assert res.alerta_rr is not None
    assert "R/R declarado pelo agente 2.00" in res.alerta_rr
    assert "calculado 3.00" in res.alerta_rr
    assert "usado o calculado" in res.alerta_rr
    assert relatorio.alerta_rr == res.alerta_rr


def test_rr_calculado_1_20_declarado_2_veta_pelo_piso(monkeypatch):
    """
    [V2-01] Teste com calculado 1.20 e declarado 2.00 veta pelo piso de 1.50:1.
    """
    monkeypatch.setattr(
        "tools.risk_gate.consultar_dados_tecnicos_e_medias",
        lambda ticker: {
            "status": "sucesso",
            "ticker": ticker,
            "preco_atual": 40.0,
            "sma_20": 39.5,
        }
    )

    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,  # Declarado 2.00
        ativo="PETR4",
    )

    relatorio = RelatorioExecutivoFinal(
        ativo_alvo="PETR4",
        preco_entrada=40.0,
        preco_alvo=42.40,  # Ganho = 2.40
        preco_stop=38.0,   # Perda = 2.00 -> Calculado = 2.40 / 2.00 = 1.20 (< 1.50)
    )

    res = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        relatorio=relatorio,
        preco_entrada=40.0,
        preco_alvo=42.40,
        preco_stop=38.0,
        rr_declarado=2.0,
        ticker="PETR4",
    )

    aprovado, status, motivo = res
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "piso obrigatório de 1.50:1" in motivo or "inferior ao piso" in motivo
