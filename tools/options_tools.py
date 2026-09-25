"""
Ferramentas matemáticas determinísticas para cálculo de Risco/Retorno e Gregas de Opções (Black-Scholes).
Elimina cálculos 'de cabeça' pela LLM e assegura precisão quantitativa de mesa.
Chaves alinhadas com os modelos Pydantic e geradores de relatórios PDF.
"""

import os
import math
from typing import Dict, Any, Optional
from crewai.tools import tool


def _norm_cdf(x: float) -> float:
    """Função de distribuição acumulada normal padrão determinística (CDF)."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    """Função de densidade de probabilidade normal padrão determinística (PDF)."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@tool("calcular_gregas_black_scholes")
def calcular_gregas_black_scholes(
    spot_price: float,
    strike: float,
    dias_uteis_vencimento: int,
    taxa_juros_anual: Optional[float] = None,
    volatilidade_anual: Optional[float] = None,
    tipo_opcao: str = "call"
) -> Dict[str, Any]:
    """
    Calcula deterministamente o preço teórico e as Gregas (Delta, Gamma, Theta, Vega)
    de uma opção na B3 utilizando o modelo clássico de Black-Scholes.
    - spot_price: Preço atual medido da ação na B3 (ex: 41.50)
    - strike: Preço de exercício da opção (ex: 42.00)
    - dias_uteis_vencimento: Dias úteis até a 3ª sexta-feira do mês de vencimento (ex: 18)
    - taxa_juros_anual: Taxa de juros livre de risco anual (padrão lido da Selic: ex: 0.1075)
    - volatilidade_anual: Volatilidade anualizada calculada (ex: obtida de consultar_dados_tecnicos_e_medias)
    - tipo_opcao: 'call' ou 'put'
    """
    try:
        t = max(int(dias_uteis_vencimento), 1) / 252.0  # Tempo em anos úteis B3
        s = float(spot_price)
        k = float(strike)

        # Taxa Selic padrão via variável de ambiente ou parâmetro
        r_default = float(os.getenv("TAXA_SELIC_ANUAL", "0.1075"))
        r = float(taxa_juros_anual) if taxa_juros_anual is not None else r_default
        sigma = float(volatilidade_anual) if volatilidade_anual is not None else 0.28

        if s <= 0 or k <= 0 or sigma <= 0:
            return {"status": "erro", "mensagem": "Spot, strike e volatilidade devem ser estritamente positivos"}

        d1 = (math.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)

        pdf_d1 = _norm_pdf(d1)
        gamma = pdf_d1 / (s * sigma * math.sqrt(t))
        vega_1pct = (s * pdf_d1 * math.sqrt(t)) / 100.0

        is_call = tipo_opcao.strip().lower() == "call"

        if is_call:
            delta = _norm_cdf(d1)
            preco_teorico = s * delta - k * math.exp(-r * t) * _norm_cdf(d2)
            theta_anual = -(s * pdf_d1 * sigma) / (2.0 * math.sqrt(t)) - r * k * math.exp(-r * t) * _norm_cdf(d2)
        else:
            delta = _norm_cdf(d1) - 1.0
            preco_teorico = k * math.exp(-r * t) * _norm_cdf(-d2) - s * _norm_cdf(-d1)
            theta_anual = -(s * pdf_d1 * sigma) / (2.0 * math.sqrt(t)) + r * k * math.exp(-r * t) * _norm_cdf(-d2)

        theta_diario = theta_anual / 252.0

        return {
            "status": "sucesso",
            "tipo_opcao": "CALL" if is_call else "PUT",
            "spot": round(s, 2),
            "strike": round(k, 2),
            "dias_uteis": int(dias_uteis_vencimento),
            "taxa_juros_utilizada": round(r, 4),
            "volatilidade_utilizada": round(sigma, 4),
            "preco_teorico": round(preco_teorico, 2),
            "delta": round(delta, 3),
            "gamma": round(gamma, 4),
            "theta": round(theta_diario, 3),
            "theta_diario": round(theta_diario, 3),
            "vega": round(vega_1pct, 3),
            "vega_1pct": round(vega_1pct, 3),
            "metodologia": "BLACK_SCHOLES_CONTINUO"
        }
    except Exception as e:
        return {"status": "erro", "mensagem": f"Falha no cálculo de Black-Scholes: {str(e)}"}


@tool("calcular_risco_retorno_operacao")
def calcular_risco_retorno_operacao(
    preco_entrada: float,
    stop_loss: float,
    alvo: float
) -> Dict[str, Any]:
    """
    Calcula matematicamente a relação Risco/Retorno, percentual de ganho e perda potencial de um trade.
    - preco_entrada: Preço planejado de compra ou venda (ex: 30.00)
    - stop_loss: Nível técnico de stop de perda (ex: 28.50)
    - alvo: Preço objetivo de realização de lucro (ex: 34.50)
    """
    try:
        entrada = float(preco_entrada)
        stop = float(stop_loss)
        target = float(alvo)

        risco = abs(entrada - stop)
        retorno = abs(target - entrada)

        if risco <= 0:
            return {"status": "erro", "mensagem": "O stop loss não pode ser idêntico ao preço de entrada."}

        ratio = retorno / risco
        pct_risco = (risco / entrada) * 100.0
        pct_retorno = (retorno / entrada) * 100.0

        return {
            "status": "sucesso",
            "entrada": round(entrada, 2),
            "stop_loss": round(stop, 2),
            "alvo": round(target, 2),
            "risco_por_acao": round(risco, 2),
            "retorno_por_acao": round(retorno, 2),
            "razao_risco_retorno": f"{round(ratio, 2)} : 1",
            "razao_numerica": round(ratio, 2),
            "perda_potencial_pct": f"-{round(pct_risco, 2)}%",
            "ganho_potencial_pct": f"+{round(pct_retorno, 2)}%",
            "parecer_matematico": "Assimetria Favorável (>= 1.5:1)" if ratio >= 1.5 else "Assimetria Desfavorável (< 1.5:1)"
        }
    except Exception as e:
        return {"status": "erro", "mensagem": f"Erro no cálculo de risco/retorno: {str(e)}"}


@tool("calcular_payoff_trava_alta")
def calcular_payoff_trava_alta(
    strike_compra: float,
    premio_pago_compra: float,
    strike_venda: float,
    premio_recebido_venda: float
) -> Dict[str, Any]:
    """
    Calcula deterministamente o Payoff exato de uma Trava de Alta com Call na B3,
    gerando pontos para a curva de payoff (lucro/prejuízo no vencimento vs preço do ativo).
    """
    try:
        k_compra = float(strike_compra)
        k_venda = float(strike_venda)
        p_pago = float(premio_pago_compra)
        p_recebido = float(premio_recebido_venda)

        custo_liquido = p_pago - p_recebido
        largura_spread = k_venda - k_compra

        if largura_spread <= 0:
            return {"status": "erro", "mensagem": "O strike da ponta vendida deve ser superior ao strike da ponta comprada."}
        if custo_liquido <= 0:
            return {"status": "erro", "mensagem": "Custo líquido deve ser positivo para trava de alta a débito."}

        lucro_maximo = largura_spread - custo_liquido
        perda_maxima = custo_liquido
        breakeven = k_compra + custo_liquido
        ratio = lucro_maximo / perda_maxima if perda_maxima > 0 else 0

        # Curva de payoff simulada em 7 pontos de preço no vencimento para o gráfico web
        step = (k_venda - k_compra) / 3.0
        pontos_payoff = []
        precos_teste = [
            round(k_compra - 2 * step, 2),
            round(k_compra - step, 2),
            round(k_compra, 2),
            round(breakeven, 2),
            round((k_compra + k_venda) / 2.0, 2),
            round(k_venda, 2),
            round(k_venda + step, 2)
        ]

        for s_t in precos_teste:
            # Valor intrínseco no vencimento: max(S - Kc, 0) - max(S - Kv, 0) - Custo
            v_compra = max(s_t - k_compra, 0.0)
            v_venda = max(s_t - k_venda, 0.0)
            resultado = v_compra - v_venda - custo_liquido
            pontos_payoff.append({
                "preco_ativo": s_t,
                "resultado_unitario": round(resultado, 2)
            })

        return {
            "status": "sucesso",
            "estrategia": "Trava de Alta com Call (Débito)",
            "strike_compra": k_compra,
            "strike_venda": k_venda,
            "custo_maximo_por_acao": round(custo_liquido, 2),
            "perda_maxima": f"R$ {round(perda_maxima, 2)} por ação (100% do custo pago)",
            "perda_maxima_num": round(perda_maxima, 2),
            "lucro_maximo": f"R$ {round(lucro_maximo, 2)} por ação",
            "lucro_maximo_num": round(lucro_maximo, 2),
            "breakeven": round(breakeven, 2),
            "retorno_sobre_risco_pct": f"{round((lucro_maximo / perda_maxima) * 100, 1)}%",
            "razao_risco_retorno": f"{round(ratio, 2)} : 1",
            "pontos_curva_payoff": pontos_payoff
        }
    except Exception as e:
        return {"status": "erro", "mensagem": f"Erro no cálculo de payoff da trava: {str(e)}"}
