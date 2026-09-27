"""
Testes unitários para [V0-02b]:
- Valida que a aprovação de estratégia alternativa copia os números da alternativa em código.
- Valida que preço de entrada > 5% da cotação medida é vetado pelo Gate de Risco.
- Valida que trava de opções sem prêmios medidos reais da BRAPI é vetada.
- Valida que caso válido é aprovado normalmente.
"""

import pytest
from schemas.output_models import (
    DecisaoRiscoModel,
    RelatorioExecutivoFinal,
    PropostaEstrategiaModel,
    EstrategiaDetalheModel,
    AnaliseTecnicaModel,
)
from tools.risk_gate import (
    copiar_campos_estrategia_aprovada,
    extrair_preco_atual_medido,
    auditar_gate_de_risco_programatico,
)


class MockTaskOutput:
    def __init__(self, name, description, pydantic_obj):
        self.name = name
        self.description = description
        self.pydantic = pydantic_obj


class MockCrewResult:
    def __init__(self, tasks_output):
        self.tasks_output = tasks_output


def test_aprovacao_alternativa_copia_numeros_da_alternativa():
    """Valida que aprovação de estratégia alternativa copia números da alternativa e anula opções."""
    proposta = PropostaEstrategiaModel(
        ticker="PETR4",
        estrategia_principal=EstrategiaDetalheModel(
            nome_estrategia="Trava de Alta com Call",
            instrumento="Opções",
            ticker_base="PETR4",
            strike_compra=38.0,
            strike_venda=42.0,
            premio_compra=1.80,
            premio_venda=0.60,
            origem_premios="BRAPI_V2_OPTIONS_MEDIDO",
        ),
        estrategia_alternativa=EstrategiaDetalheModel(
            nome_estrategia="Compra de Ação à Vista",
            instrumento="Ações",
            ticker_base="PETR4",
            preco_entrada=37.0,
            preco_alvo=44.0,
            preco_stop=34.0,
        ),
    )

    decisao = DecisaoRiscoModel(
        status="APROVADO_ALTERNATIVA",
        estrategia_aprovada="ALTERNATIVA",
        estrategia_adotada="Compra de Ação à Vista",
        razao_risco_retorno_auditada=2.33,
        aprovado_para_divulgacao=True,
    )

    relatorio = RelatorioExecutivoFinal(
        ativo_alvo="PETR4",
        operacao_recomendada="Trava de Alta com Call",  # Inicialmente veio com narrativa da principal
        strike_compra=38.0,
        strike_venda=42.0,
        premio_compra=1.80,
        premio_venda=0.60,
    )

    crew_result = MockCrewResult(tasks_output=[
        MockTaskOutput("estruturar_estrategias_operacao_task", "Estruturação de opções e ações", proposta)
    ])

    rel_atualizado = copiar_campos_estrategia_aprovada(crew_result, relatorio, decisao)

    # Parâmetros copiados da alternativa
    assert rel_atualizado.preco_entrada == 37.0
    assert rel_atualizado.preco_alvo == 44.0
    assert rel_atualizado.preco_stop == 34.0
    assert rel_atualizado.operacao_recomendada == "Compra de Ação à Vista"

    # Campos de opções anulados
    assert rel_atualizado.strike_compra is None
    assert rel_atualizado.strike_venda is None
    assert rel_atualizado.premio_compra is None
    assert rel_atualizado.premio_venda is None
    assert rel_atualizado.origem_premios is None


def test_preco_entrada_divergencia_maior_que_5pct_e_vetada():
    """Valida que preço de entrada com divergência > 5% da cotação medida é sumariamente vetado."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_ALTERNATIVA",
        estrategia_aprovada="ALTERNATIVA",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,
    )

    # Entrada 40.0, mas cotação de PETR4 no mock é 38.0 (divergência de 5.26% > 5%)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=40.0,
        preco_alvo=50.0,
        preco_stop=35.0,
        rr_declarado=2.0,
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "Preco de entrada sem lastro de mercado" in motivo
    assert "diverge mais de 5%" in motivo


def test_trava_sem_premio_medido_e_vetada(monkeypatch):
    """Valida que trava de opções sem origem 'BRAPI_V2_OPTIONS_MEDIDO' é vetada."""
    monkeypatch.setattr(
        "tools.risk_gate.consultar_cadeia_opcoes_b3",
        lambda ticker: {
            "status": "sucesso",
            "origem": "PROJECAO_SOBRE_SPOT_MEDIDO_BRAPI",
        }
    )

    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0,
    )

    # Trava com cadeia sem dados medidos
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=38.0,
        strike_venda=42.0,
        premio_compra=1.80,
        premio_venda=0.60,
        rr_declarado=2.33,
        ticker="PETR4",
    )

    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "Premios sem cotacao real" in motivo


def test_caso_valido_e_aprovado_normalmente():
    """Valida que caso válido dentro da tolerância de 5% e com prêmio medido é aprovado."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_aprovada="PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.33,
    )

    # Trava com origem real BRAPI conferida na cadeia
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=38.0,
        strike_venda=42.0,
        premio_compra=1.80,
        premio_venda=0.60,
        rr_declarado=2.33,
        ticker="PETR4",
    )

    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"
    assert "Aprovado pelo Comitê de Risco" in motivo
