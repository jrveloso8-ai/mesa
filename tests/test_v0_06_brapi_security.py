import os
from unittest.mock import patch, MagicMock
import pytest
from requests.exceptions import ConnectionError
from tools.brapi_tools import (
    consultar_cotacoes_cesta_liquidez,
    consultar_dados_fundamentalistas,
    consultar_dados_tecnicos_e_medias,
    consultar_cadeia_opcoes_b3
)


def test_brapi_tools_passa_token_em_header_e_nao_em_params(monkeypatch):
    """Verifica que requests.get é chamado com headers={'Authorization': 'Bearer ...'} e que params não contém 'token'."""
    test_token = "TEST_SECRET_TOKEN_12345"
    monkeypatch.setenv("BRAPI_TOKEN", test_token)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    fn_cot = getattr(consultar_cotacoes_cesta_liquidez, "func", consultar_cotacoes_cesta_liquidez)
    fn_fund = getattr(consultar_dados_fundamentalistas, "func", consultar_dados_fundamentalistas)
    fn_tec = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
    fn_opc = getattr(consultar_cadeia_opcoes_b3, "func", consultar_cadeia_opcoes_b3)

    with patch("tools.brapi_tools.requests.get", return_value=mock_response) as mock_get:
        fn_cot()
        assert mock_get.called
        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        params = kwargs.get("params") or {}
        assert headers.get("Authorization") == f"Bearer {test_token}"
        assert "token" not in params

    with patch("tools.brapi_tools.requests.get", return_value=mock_response) as mock_get:
        fn_fund("PETR4")
        assert mock_get.called
        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        params = kwargs.get("params") or {}
        assert headers.get("Authorization") == f"Bearer {test_token}"
        assert "token" not in params

    with patch("tools.brapi_tools.requests.get", return_value=mock_response) as mock_get:
        fn_tec("PETR4")
        assert mock_get.called
        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        params = kwargs.get("params") or {}
        assert headers.get("Authorization") == f"Bearer {test_token}"
        assert "token" not in params

    with patch("tools.brapi_tools.requests.get", return_value=mock_response) as mock_get:
        fn_opc("PETR4")
        assert mock_get.called
        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        params = kwargs.get("params") or {}
        assert headers.get("Authorization") == f"Bearer {test_token}"
        assert "token" not in params


def test_brapi_tools_sanitiza_erros_e_nao_vaza_url_nem_token(monkeypatch):
    """Verifica que quando requests.get levanta ConnectionError contendo URL e token, a string de erro não vaza o token nem a URL."""
    test_token = "SECRET_LEAK_TOKEN_999"
    monkeypatch.setenv("BRAPI_TOKEN", test_token)

    erro_com_vazamento = ConnectionError(f"HTTPSConnectionPool(host='brapi.dev', port=443): Max retries exceeded with url: /api/quote/PETR4?range=3mo&token={test_token}")

    fn_cot = getattr(consultar_cotacoes_cesta_liquidez, "func", consultar_cotacoes_cesta_liquidez)
    fn_fund = getattr(consultar_dados_fundamentalistas, "func", consultar_dados_fundamentalistas)
    fn_tec = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
    fn_opc = getattr(consultar_cadeia_opcoes_b3, "func", consultar_cadeia_opcoes_b3)

    for fn, arg in [(fn_cot, None), (fn_fund, "PETR4"), (fn_tec, "PETR4"), (fn_opc, "PETR4")]:
        with patch("tools.brapi_tools.requests.get", side_effect=erro_com_vazamento):
            resultado = fn(arg) if arg else fn()
            msg = str(resultado)
            assert test_token not in msg, f"Token vazou na mensagem: {msg}"
            assert f"token={test_token}" not in msg
            assert "HTTPSConnectionPool" not in msg
