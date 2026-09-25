"""
Testes unitários do Gate de Risco Programático (Code-Enforced Risk Governance).
Garante que decisões imprudentes da LLM são sumariamente barradas pelo código.
"""

from schemas.output_models import DecisaoRiscoModel, RelatorioExecutivoFinal
from tools.risk_gate import auditar_gate_de_risco_programatico, aplicar_contingencia_de_veto


def test_gate_de_risco_rejeita_se_flag_aprovacao_falsa():
    """Se aprovado_para_divulgacao for False, deve vetar categoricamente."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Trava de Alta",
        parecer_risco="Risco alto",
        pontos_atencao=["Volatilidade"],
        aprovado_para_divulgacao=False
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao, razao_risco_retorno=2.0)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "veto" in motivo.lower()



def test_gate_de_risco_rejeita_se_status_reprovado_total():
    """Se status for REPROVADO_TOTAL, deve confirmar o veto."""
    decisao = DecisaoRiscoModel(
        status="REPROVADO_TOTAL",
        estrategia_adotada="Manutenção em Caixa",
        parecer_risco="Rejeitado por assimetria desfavorável",
        pontos_atencao=["R/R baixo"],
        aprovado_para_divulgacao=False
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao, razao_risco_retorno=0.9)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"


def test_gate_de_risco_veta_programaticamente_se_rr_menor_que_1_5():
    """
    TESTE CRÍTICO: Mesmo se a LLM tiver aprovado erroneamente (status=APROVADO e flag=True),
    o código em Python DEVE vetar a operação se a razão R/R for menor que 1.5:1.
    """
    decisao_alucinada = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Compra de Ação",
        parecer_risco="Parece bom",
        pontos_atencao=[],
        aprovado_para_divulgacao=True  # LLM tentou forçar aprovação
    )
    
    # Razão R/R é 1.1 : 1 (abaixo do piso de 1.5 : 1)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao_alucinada, razao_risco_retorno=1.10)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "VETO PROGRAMÁTICO DE CÓDIGO" in motivo


def test_aplicar_contingencia_de_veto():
    """Valida que o plano de contingência remove parâmetros de compra e prescreve caixa."""
    relatorio = RelatorioExecutivoFinal(
        titulo="Recomendação de Compra",
        ativo_alvo="VALE3",
        operacao_recomendada="Compra a Seco",
        status_decisao="APROVADO_PRINCIPAL"
    )

    relatorio_seguro = aplicar_contingencia_de_veto(relatorio, "Risco excessivo no minério de ferro")
    assert relatorio_seguro.status_decisao == "REPROVADO_TOTAL"
    assert "Manutenção em Caixa" in relatorio_seguro.operacao_recomendada
    assert any("MANTER 100% EM CAIXA" in p.valor for p in relatorio_seguro.parametros_operacionais)
    assert relatorio_seguro.gregas is None


def test_gate_de_risco_veta_se_rr_for_omitido_ou_zero():
    """
    TESTE ANTI-OMISSÃO (Achado A):
    Se a LLM omitir a razão R/R ou passar 0.0, a operação NÃO pode passar.
    O código DEVE vetar imediatamente por ausência de comprovação matemática.
    """
    decisao_sem_rr = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Trava de Alta",
        parecer_risco="Parece bom mas omitiu R/R",
        pontos_atencao=[],
        aprovado_para_divulgacao=True
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao_sem_rr, razao_risco_retorno=0.0)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "estritamente inferior ao piso obrigatório" in motivo or "omitida" in motivo


def test_extrair_decisao_risco_autentica_captura_veto_real_do_coordenador():
    """
    TESTE DE AUTENTICAÇÃO DE TAREFA (Achado B):
    Garante que o veto real emitido pelo Coordenador de Risco prevalece
    mesmo que o Research Publisher subsequente tenha alucinado aprovação.
    """
    from tools.risk_gate import extrair_decisao_risco_autentica

    class MockTaskOutput:
        def __init__(self, name, description, pydantic_obj):
            self.name = name
            self.description = description
            self.pydantic = pydantic_obj

    class MockCrewResult:
        def __init__(self, tasks_output):
            self.tasks_output = tasks_output

    veto_autentico = DecisaoRiscoModel(
        status="REPROVADO_TOTAL",
        estrategia_adotada="Manutenção em Caixa",
        parecer_risco="Veto estrito do comitê de risco.",
        aprovado_para_divulgacao=False
    )

    resultado_crew = MockCrewResult(tasks_output=[
        MockTaskOutput("auditar_risco_e_aprovar_task", "Auditoria de risco da mesa", veto_autentico)
    ])

    relatorio_com_alucinacao = RelatorioExecutivoFinal(
        status_decisao="APROVADO_PRINCIPAL",  # Publisher alucinou aprovação
        operacao_recomendada="Compra arriscada"
    )

    decisao_extraida = extrair_decisao_risco_autentica(resultado_crew, relatorio_com_alucinacao)
    assert decisao_extraida.status == "REPROVADO_TOTAL"
    assert decisao_extraida.aprovado_para_divulgacao is False


def test_extrair_rr_efetivo_calcula_de_precos_e_schema():
    """Testa o cálculo matemático de R/R a partir de níveis de preços e schema estruturado."""
    from tools.risk_gate import extrair_rr_efetivo, calcular_rr_deterministico
    from schemas.output_models import ItemParametro

    # 1. Teste de cálculo determinístico puro: Entrada 10, Alvo 14 (+4), Stop 8 (-2) -> R/R = 4 / 2 = 2.0
    rr_calc = calcular_rr_deterministico(entrada=10.0, alvo=14.0, stop=8.0)
    assert rr_calc == 2.0

    # 2. Teste via tabela de parâmetros operacionais
    relatorio = RelatorioExecutivoFinal(
        parametros_operacionais=[
            ItemParametro(parametro="Preço de Entrada", valor="R$ 50,00"),
            ItemParametro(parametro="Alvo de Lucro", valor="R$ 54,00"),
            ItemParametro(parametro="Stop Loss", valor="R$ 48,00"),
        ]
    )
    # Ganho = 4.0, Risco = 2.0 -> R/R = 2.0
    rr = extrair_rr_efetivo(relatorio)
    assert rr == 2.0


def test_defaults_de_schema_usam_sentinela_dados_indisponiveis():
    """TESTE DE SENTINELAS (Achado C): Garante que defaults não fabricam ITUB4."""
    from schemas.output_models import SelecaoFundamentalistaModel, AnaliseTecnicaModel

    fund = SelecaoFundamentalistaModel()
    assert fund.ticker == "DADOS_INDISPONIVEIS"

    tec = AnaliseTecnicaModel()
    assert tec.ticker == "DADOS_INDISPONIVEIS"

    rel = RelatorioExecutivoFinal()
    assert rel.ativo_alvo == "DADOS_INDISPONIVEIS"

