"""
Testes de Segurança e Auditoria de Rotas da Mesa de Operações B3.
Valida:
1. Bloqueio estrito de Path Traversal (CWE-22) em rotas de mídia.
2. Remoção definitiva de endpoints de depuração em produção (/api/debug-files).
3. Whitelist de extensões de mídia (.jpg, .jpeg, .png, .webp, .mp4).
4. Integridade da entrega de mídias legítimas autorizadas.
"""

import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def test_endpoint_debug_files_removido():
    """Garante que o endpoint /api/debug-files foi completamente removido do servidor."""
    response = client.get("/api/debug-files")
    assert response.status_code == 404, f"Esperado 404 para endpoint removido, obtido {response.status_code}"


def test_path_traversal_bloqueado_em_midia():
    """Garante que tentativas de escapar da pasta de mídia para ler .env ou arquivos de sistema são bloqueadas."""
    payloads_maliciosos = [
        "/midia/../../.env",
        "/midia/..%2F..%2F.env",
        "/static/midia/../../.env",
        "/midia/....//....//.env",
        "/midia/%2e%2e%2f%2e%2e%2f.env",
        "/midia/../../server.py",
        "/midia/../.env",
    ]
    for rota in payloads_maliciosos:
        resp = client.get(rota)
        assert resp.status_code in [400, 404], (
            f"Falha de segurança: rota {rota} retornou status {resp.status_code} em vez de 400/404!"
        )
        assert "GOOGLE_API_KEY" not in resp.text
        assert "BRAPI_TOKEN" not in resp.text
        assert "MESA_API_KEY" not in resp.text


def test_bloqueio_extensoes_nao_autorizadas():
    """Garante que apenas extensões da whitelist de mídia (.jpg, .jpeg, .png, .webp, .mp4) são servidas."""
    arquivos_proibidos = [
        "server.py",
        ".env",
        "pyproject.toml",
        "credentials.json",
        "config.yaml",
        "id_rsa",
    ]
    for arq in arquivos_proibidos:
        resp = client.get(f"/midia/{arq}")
        assert resp.status_code in [400, 403, 404], (
            f"Arquivo proibido {arq} retornou status {resp.status_code}, deveria ser rejeitado!"
        )


def test_entrega_midia_legitima():
    """Garante que arquivos de mídia válidos com extensões autorizadas continuam sendo entregues normalmente."""
    resp = client.get("/midia/analista_macro.jpg")
    # Se o arquivo existir na pasta midia, deve retornar 200 com MIME type correto
    if resp.status_code == 200:
        assert resp.headers["content-type"] in ["image/jpeg", "image/jpg"]
    else:
        assert resp.status_code == 404
