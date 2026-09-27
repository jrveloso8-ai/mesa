import os
import json
import pytest
from server import carregar_ultimo_resultado_salvo, estado_execucao
from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100


def test_carregar_ultimo_resultado_ignora_md_e_usa_resultado_pos_gate(tmp_path):
    """Testa que carregar_ultimo_resultado_salvo() lê EXCLUSIVAMENTE resultado_pos_gate.json e ignora relatorio_recomendacao.md."""
    os.makedirs("output", exist_ok=True)
    caminho_md = os.path.join("output", "relatorio_recomendacao.md")
    caminho_json = os.path.join("output", "resultado_pos_gate.json")

    backup_md = open(caminho_md, "r", encoding="utf-8").read() if os.path.exists(caminho_md) else None
    backup_json = open(caminho_json, "r", encoding="utf-8").read() if os.path.exists(caminho_json) else None

    try:
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
    finally:
        if backup_md is not None:
            with open(caminho_md, "w", encoding="utf-8") as f:
                f.write(backup_md)
        elif os.path.exists(caminho_md):
            os.remove(caminho_md)

        if backup_json is not None:
            with open(caminho_json, "w", encoding="utf-8") as f:
                f.write(backup_json)
        elif os.path.exists(caminho_json):
            os.remove(caminho_json)


def test_carregar_ultimo_resultado_fallback_quando_arquivo_inexistente():
    """Testa que se resultado_pos_gate.json não existir, retorna o fallback explícito com REPROVADO_TOTAL."""
    caminho_json = os.path.join("output", "resultado_pos_gate.json")
    backup = None
    if os.path.exists(caminho_json):
        with open(caminho_json, "r", encoding="utf-8") as f:
            backup = f.read()
        os.remove(caminho_json)

    try:
        resultado = carregar_ultimo_resultado_salvo()
        assert resultado["status_final"] == "REPROVADO_TOTAL"
        assert resultado["motivo_veto"] == "Nenhuma execução registrada"
        assert resultado["ticker"] == "N/A"
        assert estado_execucao["resultado"]["status_final"] == "REPROVADO_TOTAL"
    finally:
        if backup is not None:
            with open(caminho_json, "w", encoding="utf-8") as f:
                f.write(backup)


def test_screener_reflete_status_resultado_pos_gate():
    """Testa que o screener reflete o status de resultado_pos_gate.json no ativo auditado."""
    os.makedirs("output", exist_ok=True)
    caminho_json = os.path.join("output", "resultado_pos_gate.json")
    backup = None
    if os.path.exists(caminho_json):
        with open(caminho_json, "r", encoding="utf-8") as f:
            backup = f.read()

    try:
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

    finally:
        if backup is not None:
            with open(caminho_json, "w", encoding="utf-8") as f:
                f.write(backup)
        elif os.path.exists(caminho_json):
            os.remove(caminho_json)
