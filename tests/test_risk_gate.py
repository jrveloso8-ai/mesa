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
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao_alucinada,
        preco_entrada=50.0,
        preco_alvo=51.10,
        preco_stop=49.0,
        rr_declarado=1.10
    )
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "VETO PROGRAMÁTICO DE CÓDIGO" in motivo


def test_aplicar_contingencia_de_veto():
    """Valida que o plano de contingência remove parâmetros de compra e prescreve caixa [V1-02]."""
    relatorio = RelatorioExecutivoFinal(
        titulo="Recomendação de Compra",
        ativo_alvo="VALE3",
        operacao_recomendada="Compra a Seco",
        status_decisao="APROVADO_PRINCIPAL",
        resumo_executivo="A operação de compra recomendada para VALE3 foi aprovada pelo estrategista com alto potencial.",
        disclaimer_cvm="Relatório elaborado por analistas certificados CNPI."
    )

    relatorio_seguro = aplicar_contingencia_de_veto(relatorio, "Risco excessivo no minério de ferro")
    assert relatorio_seguro.status_decisao == "REPROVADO_TOTAL"
    assert "Manutenção em Caixa" in relatorio_seguro.operacao_recomendada
    assert any("MANTER 100% EM CAIXA" in p.valor for p in relatorio_seguro.parametros_operacionais)
    assert relatorio_seguro.gregas is None

    # Validações [V1-02]
    resumo_lower = relatorio_seguro.resumo_executivo.lower()
    assert "aprovad" not in resumo_lower
    assert "recomendad" not in resumo_lower
    assert "operacao vetada pelo gate de risco" in resumo_lower

    disclaimer_lower = relatorio_seguro.disclaimer_cvm.lower()
    assert "certificado" not in disclaimer_lower
    assert "cnpi" not in disclaimer_lower
    assert "exclusivamente informativos" in disclaimer_lower


def test_gate_de_risco_veta_se_rr_for_omitido_ou_zero():
    """
    TESTE ANTI-OMISSÃO (Achado A):
    Se a LLM omitir a razão R/R ou passar 0.0, a operação NÃO pode passar.
    O código DEVE vetar imediatamente por ausência de comprovação matemática.
    """
    decisao_sem_rr = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Compra de Ação",
        parecer_risco="Parece bom mas omitiu R/R",
        pontos_atencao=[],
        aprovado_para_divulgacao=True
    )
    # Entrada sem parâmetros de preço válidos (retorna REPROVADO_TOTAL)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao_sem_rr)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "sem parametros numericos" in motivo.lower()


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


def test_v0_01_gate_rejeita_precos_com_rr_fraco_mesmo_com_declarado_alto():
    """
    [V0-01] Teste com preços 50/51/48 (R/R real 0.5) e declarado 1.6:
    O Gate DEVE rejeitar com REPROVADO_TOTAL porque o R/R calculado em código (0.5) < 1.50.
    """
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Compra Ação",
        razao_risco_retorno_auditada=1.6,
        aprovado_para_divulgacao=True
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=50.0,
        preco_alvo=51.0,
        preco_stop=48.0,
        rr_declarado=1.6
    )
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"


def test_v0_01_gate_registra_alerta_quando_rr_declarado_diverge_do_calculado():
    """
    [V2-01] Teste com preços 43.55/50/41.50 (R/R calculado ~3.15) e declarado 1.55:
    Divergência não veta a operação (aprova pois 3.15 >= 1.50) e registra alerta_rr.
    """
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Compra Ação",
        razao_risco_retorno_auditada=1.55,
        aprovado_para_divulgacao=True
    )
    res = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=43.55,
        preco_alvo=50.0,
        preco_stop=41.50,
        rr_declarado=1.55
    )
    aprovado, status, motivo = res
    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"
    assert res.alerta_rr is not None
    assert "R/R declarado pelo agente 1.55; calculado 3.15; usado o calculado" in res.alerta_rr


def test_v0_01_gate_aprova_quando_declarado_e_calculado_sao_consistentes():
    """
    [V0-01] Teste com preços 43.55/50/41.50 e declarado 3.15:
    Calculado ~3.15 e declarado 3.15 -> Gate aprova.
    """
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        estrategia_adotada="Compra Ação",
        razao_risco_retorno_auditada=3.15,
        aprovado_para_divulgacao=True
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=43.55,
        preco_alvo=50.0,
        preco_stop=41.50,
        rr_declarado=3.15,
        preco_atual_medido=43.55
    )
    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"
    assert "3.15" in motivo


def test_v0_01_gate_veta_se_alvo_menor_igual_entrada_ou_stop_maior_igual_entrada():
    """[V0-01] Validação de compra: alvo <= entrada ou stop >= entrada resulta em veto."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        aprovado_para_divulgacao=True
    )
    # Alvo menor que entrada
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=50.0,
        preco_alvo=49.0,
        preco_stop=45.0
    )
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "alvo menor ou igual" in motivo.lower()

    # Stop maior que entrada
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        preco_entrada=50.0,
        preco_alvo=60.0,
        preco_stop=52.0
    )
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "stop loss maior ou igual" in motivo.lower()


def test_v0_01_gate_trava_de_alta_payoff():
    """[V0-01] Validação de cálculo determinístico para Trava de Alta com Call."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        aprovado_para_divulgacao=True
    )
    # Trava com R/R < 1.50 (spread 2.0, custo 0.85 -> lucro 1.15, perda 0.85 -> R/R = 1.35)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=48.50,
        strike_venda=50.50,
        premio_compra=1.45,
        premio_venda=0.60,
        rr_declarado=1.35,
        origem_premios="BRAPI_V2_OPTIONS_MEDIDO"
    )
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"

    # Trava com R/R 3.0 (spread 4.0, custo 1.0 -> lucro 3.0, perda 1.0 -> R/R = 3.0)
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        strike_compra=48.0,
        strike_venda=52.0,
        premio_compra=1.50,
        premio_venda=0.50,
        rr_declarado=3.0,
        origem_premios="BRAPI_V2_OPTIONS_MEDIDO"
    )
    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"


def test_v1_01_gate_reprova_quando_decisao_risco_is_none():
    """[V1-01] Garantir que auditar_gate_de_risco_programatico(None, 2.0) retorne REPROVADO_TOTAL."""
    aprovado, status, motivo = auditar_gate_de_risco_programatico(None, 2.0)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "Decisao de risco ausente: esteira nao produziu deliberacao valida" in motivo


def test_v1_01_gate_reprova_quando_sem_parametros_numericos():
    """[V1-01] Quando relatorio is None e não há parâmetros numéricos, deve vetar."""
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        aprovado_para_divulgacao=True
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao_risco=decisao)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "Operacao sem parametros numericos tipados" in motivo


def test_v0_02_relatorio_sem_campos_float_resulta_em_veto():
    """
    [V0-02] Relatório sem campos numéricos tipados float resulta em veto pelo Gate de Risco.
    """
    relatorio = RelatorioExecutivoFinal(
        titulo="Recomendação de Compra",
        ativo_alvo="VALE3",
        operacao_recomendada="Compra de Ação",
        status_decisao="APROVADO_PRINCIPAL",
        # Campos float ausentes (None)
        preco_entrada=None,
        preco_alvo=None,
        preco_stop=None
    )
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        aprovado_para_divulgacao=True
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(decisao_risco=decisao, relatorio=relatorio)
    assert aprovado is False
    assert status == "REPROVADO_TOTAL"
    assert "sem parâmetros numéricos" in motivo.lower()


def test_v0_02_relatorio_com_campos_float_e_data_execucao():
    """
    [V0-02] Relatório com campos numéricos tipados float e data de execução.
    """
    from datetime import datetime
    data_atual = datetime.now().strftime("%d/%m/%Y")
    relatorio = RelatorioExecutivoFinal(
        titulo="Recomendação de Compra",
        ativo_alvo="VALE3",
        operacao_recomendada="Compra de Ação",
        status_decisao="APROVADO_PRINCIPAL",
        preco_entrada=40.0,
        preco_alvo=50.0,
        preco_stop=35.0,
        razao_risco_retorno_num=2.0,
        data_geracao=data_atual
    )
    # Entrada 40, Alvo 50 (+10), Stop 35 (-5) -> R/R = 2.0
    decisao = DecisaoRiscoModel(
        status="APROVADO_PRINCIPAL",
        aprovado_para_divulgacao=True,
        razao_risco_retorno_auditada=2.0
    )
    aprovado, status, motivo = auditar_gate_de_risco_programatico(
        decisao_risco=decisao,
        relatorio=relatorio,
        preco_atual_medido=40.0
    )
    assert aprovado is True
    assert status == "APROVADO_PRINCIPAL"
    assert relatorio.data_geracao == data_atual
    assert relatorio.preco_entrada == 40.0
    assert relatorio.preco_alvo == 50.0
    assert relatorio.preco_stop == 35.0



