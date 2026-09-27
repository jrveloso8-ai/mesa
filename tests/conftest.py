"""
Configurações globais e fixtures para a suíte de testes pytest.
Garante isolamento: nenhum teste chama a BRAPI de verdade (Item V0-02c).
"""

import pytest


@pytest.fixture(autouse=True)
def default_mock_brapi_para_testes(monkeypatch):
    """
    Mock padrão automático para consultar_dados_tecnicos_e_medias e consultar_cadeia_opcoes_b3
    dentro de tools.risk_gate, garantindo que nenhum teste acesse a rede ou falhe por falta de cotação.
    Testes específicos podem sobrescrever estes mocks conforme necessário.
    """
    def _mock_dados_tecnicos(ticker="ITUB4"):
        t_clean = str(ticker).strip().upper() if ticker else "ITUB4"
        precos_map = {
            "PETR4": 38.0,
            "VALE3": 40.0,
            "ITUB4": 45.0,
            "B3SA3": 12.0,
            "BBAS3": 28.0,
        }
        p = precos_map.get(t_clean, 45.0)
        return {
            "status": "sucesso",
            "ticker": t_clean,
            "preco_atual": p,
            "sma_20": p * 0.98,
        }

    def _mock_cadeia_opcoes(ticker="ITUB4"):
        t_clean = str(ticker).strip().upper() if ticker else "ITUB4"
        return {
            "status": "sucesso",
            "origem": "BRAPI_V2_OPTIONS_MEDIDO",
            "dados": [
                {"symbol": f"{t_clean}D380", "strike": 38.0, "close": 1.80},
                {"symbol": f"{t_clean}D400", "strike": 40.0, "close": 1.50},
                {"symbol": f"{t_clean}D420", "strike": 42.0, "close": 0.60},
                {"symbol": f"{t_clean}D440", "strike": 44.0, "close": 0.50},
                {"symbol": f"{t_clean}D480", "strike": 48.0, "close": 1.50},
                {"symbol": f"{t_clean}D485", "strike": 48.50, "close": 1.45},
                {"symbol": f"{t_clean}D505", "strike": 50.50, "close": 0.60},
                {"symbol": f"{t_clean}D520", "strike": 52.0, "close": 0.50},
            ]
        }

    monkeypatch.setattr("tools.risk_gate.consultar_dados_tecnicos_e_medias", _mock_dados_tecnicos)
    monkeypatch.setattr("tools.risk_gate.consultar_cadeia_opcoes_b3", _mock_cadeia_opcoes)
