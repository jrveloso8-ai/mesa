"""
Testes unitários de persistência e leitura do resultado pós-gate de risco [V0-05] e isolamento [V1-03].
Utiliza estritamente tmp_path e monkeypatch para impedir que testes toquem na pasta output/ real do projeto.
"""

import os
import json
import pytest
from server import carregar_ultimo_resultado_salvo, estado_execucao
from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100


def test_carregar_ultimo_resultado_ignora_md_e_usa_resultado_pos_gate(tmp_path, monkeypatch):
    """Testa que carregar_ultimo_resultado_salvo() lê EXCLUSIVAMENTE resultado_pos_gate.json e ignora relatorio_recomendacao.md."""
    monkeypatch.chdir(tmp_path)
    os.makedirs("output", exist_ok=True)
    caminho_md = os.path.join("output", "relatorio_recomendacao.md")
    caminho_json = os.path.join("output", "resultado_pos_gate.json")

    # Salva .md simulando aprovação antiga
    with open(caminho_md, "w", encoding="utf-8") as f:
        json.dump({"ativo_alvo": "PETR4", "status_decisao": "APROVADO_PRINCIPAL"}, f)

    # Salva resultado_pos_gate.json com veto oficial do Gate de Risco
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump({
            "status_final": "REPROVADO_TOTAL",
            "motivo_veto": "Veto do Gate de Risco: R/R < 1.50",
            "ticker": "PETR4",
            "timestamp": "27/09/2026 15:00:00",
            "relatorio_completo": {"ativo_alvo": "PETR4", "status_decisao": "REPROVADO_TOTAL"}
        }, f)

    resultado = carregar_ultimo_resultado_salvo()
    assert resultado["status_final"] == "REPROVADO_TOTAL"
    assert estado_execucao["resultado"]["status_decisao"] == "REPROVADO_TOTAL"


def test_carregar_ultimo_resultado_fallback_quando_arquivo_inexistente(tmp_path, monkeypatch):
    """Testa que se resultado_pos_gate.json não existir, retorna o fallback explícito com REPROVADO_TOTAL."""
    monkeypatch.chdir(tmp_path)
    # Diretório output vazio / sem arquivo
    os.makedirs("output", exist_ok=True)

    resultado = carregar_ultimo_resultado_salvo()
    assert resultado["status_final"] == "REPROVADO_TOTAL"
    assert resultado["motivo_veto"] == "Nenhuma execução registrada"
    assert resultado["ticker"] == "N/A"
    assert estado_execucao["resultado"]["status_final"] == "REPROVADO_TOTAL"


def test_screener_reflete_status_resultado_pos_gate(tmp_path, monkeypatch):
    """Testa que o screener reflete o status de resultado_pos_gate.json no ativo auditado."""
    monkeypatch.chdir(tmp_path)
    os.makedirs("output", exist_ok=True)
    caminho_json = os.path.join("output", "resultado_pos_gate.json")

    # 1. Teste com ativo vetado
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump({
            "status_final": "REPROVADO_TOTAL",
            "motivo_veto": "Veto de Risco em Teste",
            "ticker": "PETR4",
            "timestamp": "27/09/2026 15:00:00",
            "relatorio_completo": {"ativo_alvo": "PETR4"}
        }, f)

    ranking_vetado = gerar_ranking_completo_ibrx100()
    petr4_item = next((r for r in ranking_vetado if r["ticker"] == "PETR4"), None)
    assert petr4_item is not None
    assert petr4_item["status_funil"] == "VETADO_GATE_RISCO"

    # 2. Teste com ativo aprovado
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump({
            "status_final": "APROVADO",
            "motivo_veto": None,
            "ticker": "PETR4",
            "timestamp": "27/09/2026 15:00:00",
            "relatorio_completo": {"ativo_alvo": "PETR4"}
        }, f)

    ranking_aprovado = gerar_ranking_completo_ibrx100()
    petr4_aprovado = next((r for r in ranking_aprovado if r["ticker"] == "PETR4"), None)
    assert petr4_aprovado is not None
    assert petr4_aprovado["status_funil"] == "APROVADO_OPERACIONAL"
