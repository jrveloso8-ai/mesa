"""
Testes de integridade para [V0-03]:
Garante que constantes de fallback não são exibidas como dados de mercado e que
falhas de cotação retornam HTTP 502 com erro claro sem fabricação de dados.
"""

import requests
from fastapi.testclient import TestClient
from server import app, cache_dados_tecnicos

client = TestClient(app)


def test_v0_03_api_ativo_falha_retorna_502(monkeypatch):
    """
    [V0-03] Com requests.get forçado a falhar, GET /api/ativo/PETR4 retorna HTTP 502
    com 'Dados de mercado indisponiveis' e nenhuma constante de fallback.
    """
    def mock_get_falha(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Falha de conexão com a BRAPI")

    monkeypatch.setattr(requests, "get", mock_get_falha)
    cache_dados_tecnicos.clear()

    resp = client.get("/api/ativo/PETR4")
    assert resp.status_code == 502
    assert "Dados de mercado indisponiveis" in resp.text

    valores_proibidos = ["46.80", "50.43", "48.09", "48.50", "1.45", "1.60", "0.38"]
    for val in valores_proibidos:
        assert val not in resp.text, f"Valor proibido {val} encontrado na resposta de erro"


def test_v0_03_codigo_e_telas_sem_constantes_de_fallback():
    """
    [V0-03] Nenhuma resposta, tela ou código de backend/frontend contém as constantes
    fictícias 46.80, 50.43, 48.09, 48.50, 1.45, 1.60 ou 0.38.
    """
    valores_proibidos = ["46.80", "50.43", "48.09", "48.50", "1.45", "1.60", "0.38"]
    
    with open("server.py", "r", encoding="utf-8") as f:
        conteudo_server = f.read()

    with open("static/app.js", "r", encoding="utf-8") as f:
        conteudo_js = f.read()

    for val in valores_proibidos:
        assert val not in conteudo_server, f"Valor proibido {val} encontrado em server.py"
        assert val not in conteudo_js, f"Valor proibido {val} encontrado em static/app.js"
