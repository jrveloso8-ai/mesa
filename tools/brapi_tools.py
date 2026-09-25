"""
Ferramentas de integração oficial com a API da BRAPI (Bolsa Brasileira).
Fornece dados em tempo real de cotações, múltiplos fundamentalistas, dados técnicos,
cálculo de volatilidade histórica real e cadeia de opções para a Cesta de Liquidez B3.
"""

import os
import math
import requests
from typing import Dict, Any, List, Optional

try:
    from crewai.tools import tool
except ImportError:
    def tool(*args, **kwargs):
        def decorator(f):
            f.func = f
            return f
        if len(args) == 1 and callable(args[0]):
            f = args[0]
            f.func = f
            return f
        return decorator

# Cesta curada de alta liquidez da B3 (Top 10 componentes em volume de opções do IBrX-100)
CESTA_LIQUIDEZ_B3 = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "B3SA3", "WEGE3", "RENT3", "SUZB3"]


def _get_brapi_headers_and_token() -> tuple[str, str]:
    token = (os.getenv("BRAPI_TOKEN") or os.getenv("BRAPI_API_KEY") or "").strip()
    base_url = "https://brapi.dev/api"
    return base_url, token


@tool("listar_universo_liquidez_b3")
def listar_universo_liquidez_b3() -> Dict[str, Any]:
    """
    Retorna a lista dos 10 ativos mais líquidos da B3 monitorados pela Mesa de Operações
    (selecionados a partir dos líderes de volume de negócios e opções do índice IBrX-100).
    """

    return {
        "universo": "Cesta de Liquidez B3 (Top 10 do IBrX-100)",
        "descricao": "Ativos de maior liquidez e negociabilidade de ações e opções na B3",
        "classificacao_metodologica": "CURADA_POR_LIQUIDEZ_IBRX100",
        "tickers": CESTA_LIQUIDEZ_B3,
        "setores_representados": {
            "PETR4": "Petróleo, Gás e Biocombustíveis",
            "VALE3": "Mineração e Siderurgia",
            "ITUB4": "Intermediários Financeiros / Bancos",
            "BBDC4": "Intermediários Financeiros / Bancos",
            "BBAS3": "Intermediários Financeiros / Bancos",
            "ABEV3": "Bebidas / Consumo Não Cíclico",
            "B3SA3": "Serviços Financeiros / Bolsa",
            "WEGE3": "Bens Industriais / Máquinas e Equipamentos",
            "RENT3": "Consumo Cíclico / Locação de Veículos",
            "SUZB3": "Madeira e Papel / Celulose",
        }
    }


# Alias para compatibilidade
listar_universo_ibrx10 = listar_universo_liquidez_b3


@tool("consultar_cotacoes_cesta_liquidez")
def consultar_cotacoes_cesta_liquidez() -> Dict[str, Any]:
    """
    Consulta o preço atualizado, variação percentual do dia e volume negociado
    de todos os ativos da cesta de liquidez diretamente na BRAPI.
    """
    base_url, token = _get_brapi_headers_and_token()
    tickers_str = ",".join(CESTA_LIQUIDEZ_B3)
    url = f"{base_url}/quote/{tickers_str}"
    params = {}
    if token:
        params["token"] = token

    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code == 200:
            data = response.json()
            resultados = []
            for item in data.get("results", []):
                preco = item.get("regularMarketPrice")
                if preco is not None:
                    resultados.append({
                        "ticker": item.get("symbol"),
                        "preco_atual": round(float(preco), 2),
                        "variacao_dia_pct": round(float(item.get("regularMarketChangePercent", 0.0)), 2),
                        "maxima_dia": item.get("regularMarketDayHigh"),
                        "minima_dia": item.get("regularMarketDayLow"),
                        "volume": item.get("regularMarketVolume"),
                        "proveniencia": "MEDIDO_BRAPI_REALTIME"
                    })
            return {"status": "sucesso", "total_ativos": len(resultados), "dados": resultados}
        else:
            return {"status": "erro", "codigo_http": response.status_code, "mensagem": response.text}
    except Exception as e:
        return {"status": "erro_conexao", "mensagem": f"Erro de comunicação com BRAPI: {str(e)}"}


# Alias para compatibilidade
consultar_cotacoes_mercado_ibrx10 = consultar_cotacoes_cesta_liquidez



@tool("consultar_dados_fundamentalistas")
def consultar_dados_fundamentalistas(ticker: str) -> Dict[str, Any]:
    """
    Busca indicadores e múltiplos fundamentalistas completos de um ticker da B3 via BRAPI:
    P/L, Dividend Yield, ROE, Margens, EV/EBITDA e Lucro por Ação.
    """
    ticker_clean = ticker.strip().upper()
    base_url, token = _get_brapi_headers_and_token()
    url = f"{base_url}/quote/{ticker_clean}"
    params = {
        "modules": "financialData,defaultKeyStatistics,summaryProfile",
        "fundamental": "true"
    }
    if token:
        params["token"] = token

    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if not results:
                return {
                    "status": "erro",
                    "ticker": ticker_clean,
                    "mensagem": f"Nenhum resultado retornado para {ticker_clean}",
                    "dados_disponiveis": False
                }

            item = results[0]
            fin = item.get("financialData", {})
            stats = item.get("defaultKeyStatistics", {})
            preco = item.get("regularMarketPrice")

            pl = stats.get("forwardPE") or stats.get("trailingPE")
            dy = stats.get("dividendYield")
            roe = fin.get("returnOnEquity")
            roa = fin.get("returnOnAssets")
            ev_ebitda = stats.get("enterpriseToEbitda")
            pvp = stats.get("priceToBook")
            margem_liq = fin.get("profitMargins")
            beta = stats.get("beta")
            ebitda = fin.get("ebitda")
            total_debt = fin.get("totalDebt")
            total_cash = fin.get("totalCash")
            fco = fin.get("operatingCashflow")

            # Cálculo de Dívida Líquida / EBITDA (Métrica CNPI CG1)
            div_liq_ebitda_str = "N/D"
            if total_debt is not None and total_cash is not None and ebitda and ebitda > 0:
                div_liq = total_debt - total_cash
                div_liq_ebitda_str = f"{round(div_liq / ebitda, 2)}x"

            return {
                "status": "sucesso",
                "ticker": ticker_clean,
                "nome_empresa": item.get("longName") or item.get("shortName") or ticker_clean,
                "preco_atual": round(float(preco), 2) if preco is not None else None,
                "pl": f"{round(float(pl), 2)}" if pl is not None else "N/D",
                "pvp": f"{round(float(pvp), 2)}" if pvp is not None else "N/D",
                "dividend_yield": f"{round(float(dy) * 100, 2)}%" if dy is not None else "N/D",
                "roe": f"{round(float(roe) * 100, 2)}%" if roe is not None else "N/D",
                "roa": f"{round(float(roa) * 100, 2)}%" if roa is not None else "N/D",
                "ev_ebitda": f"{round(float(ev_ebitda), 2)}" if ev_ebitda is not None else "N/D",
                "divida_liquida_ebitda": div_liq_ebitda_str,
                "margem_liquida": f"{round(float(margem_liq) * 100, 2)}%" if margem_liq is not None else "N/D",
                "fluxo_caixa_operacional": f"R$ {round(float(fco)/1e6, 2)}M" if fco is not None else "N/D",
                "beta": f"{round(float(beta), 2)}" if beta is not None else "N/D",
                "saude_caixa": "Positiva" if (total_cash or 0) > 0 else "Monitorar",
                "proveniencia": "MEDIDO_BRAPI_OFICIAL"
            }
        else:
            return {
                "status": "erro",
                "ticker": ticker_clean,
                "mensagem": f"BRAPI retornou status {response.status_code}",
                "dados_disponiveis": False
            }
    except Exception as e:
        return {
            "status": "erro_conexao",
            "ticker": ticker_clean,
            "mensagem": f"Falha ao consultar fundamentalista para {ticker_clean}: {str(e)}",
            "dados_disponiveis": False
        }


@tool("consultar_dados_tecnicos_e_medias")
def consultar_dados_tecnicos_e_medias(ticker: str) -> Dict[str, Any]:
    """
    Obtém o histórico diário de preços dos últimos 3 meses da BRAPI para o ticker
    e calcula deterministamente: Média Móvel de 20 (SMA20), Média Móvel de 50 (SMA50),
    Suportes, Resistências, RSI-14 e a Volatilidade Histórica Real Anualizada.
    """
    ticker_clean = ticker.strip().upper()
    base_url, token = _get_brapi_headers_and_token()
    url = f"{base_url}/quote/{ticker_clean}"
    params = {
        "range": "3mo",
        "interval": "1d"
    }
    if token:
        params["token"] = token

    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if not results:
                return {"status": "erro", "mensagem": f"Histórico não encontrado para {ticker_clean}"}

            historico = results[0].get("historicalDataPrice", [])
            if not historico:
                return {"status": "erro", "mensagem": f"Sem dados históricos diários para {ticker_clean}"}

            candles_validos = [h for h in historico if h.get("close") is not None]
            fechamentos = [h.get("close") for h in candles_validos]

            if len(fechamentos) < 20:
                return {"status": "erro", "mensagem": "Histórico insuficiente para cálculo de médias (< 20 pregões)"}

            ultimo_fechamento = fechamentos[-1]
            sma20 = sum(fechamentos[-20:]) / 20.0
            sma50 = sum(fechamentos[-50:]) / len(fechamentos[-50:]) if len(fechamentos) >= 50 else None

            suporte_20d = min(fechamentos[-20:])
            resistencia_20d = max(fechamentos[-20:])

            # RSI-14 determinístico
            gains, losses = [], []
            for i in range(-14, 0):
                diff = fechamentos[i] - fechamentos[i - 1]
                if diff >= 0:
                    gains.append(diff)
                    losses.append(0.0)
                else:
                    gains.append(0.0)
                    losses.append(abs(diff))

            avg_gain = sum(gains) / 14.0
            avg_loss = sum(losses) / 14.0
            rsi = 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))) if avg_loss > 0 else 100.0

            # Cálculo de Volatilidade Histórica Anualizada Real (252 pregões)
            log_returns = []
            for i in range(1, len(fechamentos)):
                if fechamentos[i - 1] > 0 and fechamentos[i] > 0:
                    log_returns.append(math.log(fechamentos[i] / fechamentos[i - 1]))

            vol_anualizada = 0.0
            if len(log_returns) > 5:
                mean_ret = sum(log_returns) / len(log_returns)
                variance = sum((r - mean_ret) ** 2 for r in log_returns) / (len(log_returns) - 1)
                vol_diaria = math.sqrt(variance)
                vol_anualizada = vol_diaria * math.sqrt(252)

            # Extração dos últimos 30 candles estruturados para o gráfico web
            candles_recentes = []
            for c in candles_validos[-30:]:
                candles_recentes.append({
                    "date": c.get("date"),
                    "open": round(float(c.get("open", c.get("close"))), 2),
                    "high": round(float(c.get("high", c.get("close"))), 2),
                    "low": round(float(c.get("low", c.get("close"))), 2),
                    "close": round(float(c.get("close")), 2),
                    "volume": c.get("volume", 0)
                })

            posicao_sma20 = "Acima da SMA20 (Força)" if ultimo_fechamento > sma20 else "Abaixo da SMA20 (Fraqueza)"

            return {
                "status": "sucesso",
                "ticker": ticker_clean,
                "preco_atual": round(ultimo_fechamento, 2),
                "sma_20": round(sma20, 2),
                "sma_50": round(sma50, 2) if sma50 else "Dados < 50 dias",
                "posicao_tendencia": posicao_sma20,
                "suporte_recente": round(suporte_20d, 2),
                "resistencia_recente": round(resistencia_20d, 2),
                "rsi_14": round(rsi, 1),
                "estado_rsi": "Sobrevendido (<30)" if rsi < 30 else "Sobrecomprado (>70)" if rsi > 70 else "Neutro",
                "volatilidade_historica_anualizada": round(vol_anualizada, 4) if vol_anualizada > 0 else 0.28,
                "proveniencia_volatilidade": "CALCULADO_HISTORICO_3M_BRAPI" if vol_anualizada > 0 else "DEFAULT_ESTIMADO",
                "candles_recentes": candles_recentes
            }
        else:
            return {"status": "erro", "mensagem": f"Status {response.status_code} na BRAPI"}
    except Exception as e:
        return {"status": "erro_processamento", "mensagem": f"Erro de processamento técnico: {str(e)}"}


@tool("consultar_cadeia_opcoes_b3")
def consultar_cadeia_opcoes_b3(ticker: str) -> Dict[str, Any]:
    """
    Consulta as opções disponíveis para o ticker na BRAPI. Se o plano da API não tiver
    o endpoint v2/options liberado, busca a cotação real medida e projeta a grade de strikes
    estritamente sobre o preço medido, sem valores fictícios.
    """
    ticker_clean = ticker.strip().upper()
    base_url, token = _get_brapi_headers_and_token()
    url = f"{base_url}/v2/options/{ticker_clean}"
    params = {}
    if token:
        params["token"] = token

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and data.get("results"):
                return {
                    "status": "sucesso",
                    "origem": "BRAPI_V2_OPTIONS_MEDIDO",
                    "dados": data.get("results")
                }
    except Exception:
        pass

    # Consulta estrita da cotação real do ativo objeto para projeção transparente
    try:
        cot_resp = requests.get(f"{base_url}/quote/{ticker_clean}", params={"token": token} if token else {}, timeout=10)
        if cot_resp.status_code != 200:
            return {
                "status": "erro",
                "origem": "FALHA_CONEXAO_BRAPI",
                "mensagem": f"Não foi possível obter cotação de {ticker_clean} para estimar opções. Código HTTP: {cot_resp.status_code}"
            }

        results = cot_resp.json().get("results", [])
        if not results:
            return {
                "status": "erro",
                "origem": "RESPOSTA_VAZIA",
                "mensagem": f"Ativo {ticker_clean} não retornou dados de cotação na BRAPI."
            }

        spot_raw = results[0].get("regularMarketPrice")
        if spot_raw is None or float(spot_raw) <= 0:
            return {
                "status": "erro",
                "origem": "SPOT_INDISPONIVEL",
                "mensagem": f"Preço de mercado para {ticker_clean} está INDISPONÍVEL. Projeção de opções bloqueada para evitar dados falsos."
            }

        spot = float(spot_raw)

        # Regra de vencimento mensal B3: 3ª sexta-feira do mês
        strike_atm = round(spot, 1)
        strike_itm = round(spot * 0.96, 1)
        strike_otm = round(spot * 1.04, 1)

        return {
            "status": "sucesso",
            "origem": "PROJECAO_SOBRE_SPOT_MEDIDO_BRAPI",
            "ticker_base": ticker_clean,
            "preco_ativo_objeto_medido": round(spot, 2),
            "regra_vencimento": "Exclusivamente 3ª Sexta-Feira do Mês (Vencimento Mensal B3)",
            "strikes_sugeridos": {
                "ITM_compra_alta": strike_itm,
                "ATM_neutro": strike_atm,
                "OTM_venda_alta": strike_otm,
            },
            "aviso_metodologico": "Strikes projetados matematicamente a partir da cotação real de mercado na B3. Utilize Black-Scholes para precificar as gregas com a volatilidade medida."
        }
    except Exception as e:
        return {
            "status": "erro",
            "origem": "EXCECAO",
            "mensagem": f"Erro ao consultar ativo {ticker_clean}: {str(e)}"
        }
