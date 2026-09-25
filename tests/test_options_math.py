"""
Testes unitários automatizados para as ferramentas determinísticas de opções e Black-Scholes.
"""

import pytest
from tools.options_tools import (
    calcular_gregas_black_scholes,
    calcular_risco_retorno_operacao,
    calcular_payoff_trava_alta
)


def test_black_scholes_call_greeks():
    """Valida o cálculo das gregas de uma CALL ATM com parâmetros conhecidos."""
    res = calcular_gregas_black_scholes.func(
        spot_price=40.0,
        strike=40.0,
        dias_uteis_vencimento=63,  # ~0.25 anos
        taxa_juros_anual=0.1075,
        volatilidade_anual=0.30,
        tipo_opcao="call"
    )

    assert res["status"] == "sucesso"
    assert res["tipo_opcao"] == "CALL"
    assert res["spot"] == 40.0
    assert res["strike"] == 40.0
    # Delta de Call ATM deve estar entre 0.50 e 0.65 (com taxa positiva)
    assert 0.50 <= res["delta"] <= 0.65
    # Gamma deve ser estritamente positivo
    assert res["gamma"] > 0
    # Theta diário deve ser negativo (decaimento temporal)
    assert res["theta"] < 0
    # Vega deve ser estritamente positivo
    assert res["vega"] > 0
    assert res["preco_teorico"] > 0


def test_black_scholes_put_delta_negative():
    """Valida que o Delta de uma PUT é estritamente negativo entre -1.0 e 0.0."""
    res = calcular_gregas_black_scholes.func(
        spot_price=40.0,
        strike=40.0,
        dias_uteis_vencimento=63,
        taxa_juros_anual=0.1075,
        volatilidade_anual=0.30,
        tipo_opcao="put"
    )

    assert res["status"] == "sucesso"
    assert res["tipo_opcao"] == "PUT"
    assert -1.0 <= res["delta"] <= 0.0


def test_calcular_risco_retorno():
    """Valida a precisão matemática da relação risco/retorno."""
    res = calcular_risco_retorno_operacao.func(
        preco_entrada=30.00,
        stop_loss=28.00,
        alvo=35.00
    )

    assert res["status"] == "sucesso"
    assert res["risco_por_acao"] == 2.00
    assert res["retorno_por_acao"] == 5.00
    assert res["razao_numerica"] == 2.50
    assert res["razao_risco_retorno"] == "2.5 : 1"
    assert "Favorável" in res["parecer_matematico"]


def test_calcular_payoff_trava_alta():
    """Valida o cálculo exato do payoff de trava de alta a débito."""
    res = calcular_payoff_trava_alta.func(
        strike_compra=38.00,
        premio_pago_compra=2.20,
        strike_venda=41.00,
        premio_recebido_venda=0.70
    )

    assert res["status"] == "sucesso"
    # Custo líquido = 2.20 - 0.70 = 1.50
    assert res["custo_maximo_por_acao"] == 1.50
    assert res["perda_maxima_num"] == 1.50
    # Lucro máximo = (41.00 - 38.00) - 1.50 = 1.50
    assert res["lucro_maximo_num"] == 1.50
    # Breakeven = 38.00 + 1.50 = 39.50
    assert res["breakeven"] == 39.50
    assert len(res["pontos_curva_payoff"]) == 7
