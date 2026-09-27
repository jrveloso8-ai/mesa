"""
Testes unitários para [V0-04]:
Garante que o screener não fabrica veto do gate nem estatística de aprovação falsa:
- Sem cotação ou volume: score None, status_funil "SEM_DADOS", ativo no fim da lista.
- Quando BRAPI está indisponível: retorna 10 ativos "SEM_DADOS", nenhum vetado, taxa 0.
- Estatísticas: aprovados conta apenas APROVADO_OPERACIONAL.
"""

from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100, obter_estatisticas_funil
import tools.screener_ibrx100 as screener_mod
from tools import brapi_tools


def test_v0_04_brapi_indisponivel_retorna_10_sem_dados_e_nenhum_vetado(monkeypatch):
    """
    [V0-04] Quando a BRAPI está indisponível (retorno vazio/erro):
    Retorna 10 ativos com status_funil 'SEM_DADOS', score None, nenhum vetado e taxa 0.
    """
    def mock_cotacoes_falha():
        return {"status": "erro", "dados": []}

    monkeypatch.setattr(brapi_tools.consultar_cotacoes_cesta_liquidez, "func", mock_cotacoes_falha)
    monkeypatch.setattr(screener_mod, "_obter_deliberacao_recente", lambda: None)

    ranking = gerar_ranking_completo_ibrx100()
    assert len(ranking) == 10

    for item in ranking:
        assert item["status_funil"] == "SEM_DADOS"
        assert item["score_geral"] is None

    stats = obter_estatisticas_funil(ranking)
    assert stats["total_ativos_triados"] == 10
    assert stats["vetados_gate_risco"] == 0
    assert stats["aprovados_ou_top_picks"] == 0
    assert stats["taxa_aprovacao_final_pct"] == 0.0


def test_v0_04_estatisticas_conta_apenas_aprovado_operacional():
    """
    [V0-04] obter_estatisticas_funil conta apenas APROVADO_OPERACIONAL em aprovados
    e calcula taxa = aprovados / ativos com dados.
    """
    ranking_mock = [
        {"ticker": "PETR4", "status_funil": "APROVADO_OPERACIONAL", "score_geral": 80.0},
        {"ticker": "VALE3", "status_funil": "VETADO_NO_RISCO", "score_geral": 75.0},
        {"ticker": "ITUB4", "status_funil": "ELEGIVEL_EM_ESPERA", "score_geral": 70.0},
        {"ticker": "BBDC4", "status_funil": "SEM_DADOS", "score_geral": None},
    ]
    stats = obter_estatisticas_funil(ranking_mock)
    assert stats["aprovados_ou_top_picks"] == 1  # Apenas PETR4
    assert stats["vetados_gate_risco"] == 1       # VALE3
    assert stats["elegiveis_em_espera"] == 1      # ITUB4
    assert stats["sem_dados"] == 1                # BBDC4
    # Ativos com dados = 3 (PETR4, VALE3, ITUB4). Taxa = 1 / 3 = 33.3%
    assert stats["taxa_aprovacao_final_pct"] == 33.3
