"""
Módulo determinístico de Gate de Risco Programático (Code-Enforced Risk Governance).
Impõe regras matemáticas inegociáveis de preservação de capital que NENHUMA LLM pode violar.
"""

import re
from typing import Dict, Any, Tuple, Optional
from schemas.output_models import (
    DecisaoRiscoModel,
    RelatorioExecutivoFinal,
    ItemParametro,
    PropostaEstrategiaModel,
    AnaliseTecnicaModel,
)


def calcular_rr_deterministico(entrada: float, alvo: float, stop: float) -> float:
    """
    Calcula deterministamente a razão Risco/Retorno a partir dos preços de tela:
    R/R = (Alvo - Entrada) / (Entrada - Stop)
    """
    try:
        e = float(entrada)
        a = float(alvo)
        s = float(stop)
        if e <= 0 or a <= 0 or s <= 0:
            return 0.0
        ganho = a - e
        perda = e - s
        if perda <= 0 or ganho <= 0:
            return 0.0
        return round(ganho / perda, 2)
    except Exception:
        return 0.0


def extrair_decisao_risco_autentica(
    resultado_crew: Any,
    relatorio_final: Optional[RelatorioExecutivoFinal] = None
) -> DecisaoRiscoModel:
    """
    Extrai a decisão genuína e autenticada do Coordenador de Risco diretamente da sua tarefa
    ('auditar_risco_e_aprovar_task') no CrewAI, impedindo que alucinações ou omissões do
    Research Publisher (última tarefa) mascarem um veto de risco real.
    """
    tasks_output = getattr(resultado_crew, "tasks_output", []) or []
    
    # 1. Busca primeiro por pydantic instance de DecisaoRiscoModel na lista de tarefas
    for task_out in tasks_output:
        pyd = getattr(task_out, "pydantic", None)
        if isinstance(pyd, DecisaoRiscoModel):
            return pyd
        if pyd and getattr(pyd, "__class__", None).__name__ == "DecisaoRiscoModel":
            return pyd

    # 2. Busca pela tarefa pelo nome ou descrição
    for task_out in tasks_output:
        desc = getattr(task_out, "description", "").lower()
        nome = getattr(task_out, "name", "").lower()
        if "auditar_risco" in nome or "auditar_risco" in desc or "comitê de risco" in desc:
            pyd = getattr(task_out, "pydantic", None)
            if pyd and hasattr(pyd, "aprovado_para_divulgacao"):
                return pyd
            # Tenta parsing do raw JSON se necessário
            raw = getattr(task_out, "raw", "")
            if "aprovado_para_divulgacao" in raw:
                try:
                    import json
                    dados = json.loads(raw)
                    return DecisaoRiscoModel(**dados)
                except Exception:
                    pass

    # 3. Fallback defensivo: se não houver tasks_output (testes unitários isolados)
    if relatorio_final is not None:
        status_pub = getattr(relatorio_final, "status_decisao", "REPROVADO_TOTAL")
        is_aprovado = "APROVAD" in str(status_pub).upper()
        return DecisaoRiscoModel(
            status=status_pub,
            estrategia_adotada=getattr(relatorio_final, "operacao_recomendada", "Manutenção em Caixa"),
            aprovado_para_divulgacao=is_aprovado,
            razao_risco_retorno_auditada=getattr(relatorio_final, "razao_risco_retorno_num", 0.0),
            parecer_risco=getattr(relatorio_final, "gestao_risco_e_saida", "Decisão derivada do relatório.")
        )

    return DecisaoRiscoModel(
        status="REPROVADO_TOTAL",
        estrategia_adotada="Manutenção em Caixa",
        aprovado_para_divulgacao=False,
        parecer_risco="Veto preventivo: saída da esteira de risco indisponível."
    )


def extrair_proposta_estrategia(resultado_crew: Any) -> Optional[PropostaEstrategiaModel]:
    """Extrai a PropostaEstrategiaModel produzida pelo Estrategista de Opções."""
    if isinstance(resultado_crew, PropostaEstrategiaModel):
        return resultado_crew
    tasks_output = getattr(resultado_crew, "tasks_output", []) or []
    for task_out in tasks_output:
        pyd = getattr(task_out, "pydantic", None)
        if isinstance(pyd, PropostaEstrategiaModel):
            return pyd
        if pyd and getattr(pyd, "__class__", None).__name__ == "PropostaEstrategiaModel":
            return pyd
    for task_out in tasks_output:
        desc = getattr(task_out, "description", "").lower()
        nome = getattr(task_out, "name", "").lower()
        if "estruturar_estrategias" in nome or "estruturar_estrategias" in desc or "estrategista" in desc:
            pyd = getattr(task_out, "pydantic", None)
            if pyd and hasattr(pyd, "estrategia_principal"):
                return pyd
            raw = getattr(task_out, "raw", "")
            if "estrategia_principal" in raw:
                try:
                    import json
                    dados = json.loads(raw)
                    return PropostaEstrategiaModel(**dados)
                except Exception:
                    pass
    return None


def copiar_campos_estrategia_aprovada(
    resultado_crew: Any,
    relatorio: RelatorioExecutivoFinal,
    decisao_risco: DecisaoRiscoModel
) -> RelatorioExecutivoFinal:
    """
    Copia os parâmetros da estratégia aprovada diretamente da PropostaEstrategiaModel
    do Senior Strategist para o RelatorioExecutivoFinal, eliminando a dependência
    da LLM do Publisher na transposição de números [V0-02b].
    """
    proposta = extrair_proposta_estrategia(resultado_crew)
    estrategia = str(getattr(decisao_risco, "estrategia_aprovada", "")).upper().strip()

    if "ALTERNATIVA" in estrategia:
        if proposta is not None and proposta.estrategia_alternativa is not None:
            alt = proposta.estrategia_alternativa
            relatorio.preco_entrada = alt.preco_entrada if alt.preco_entrada is not None else proposta.preco_entrada
            relatorio.preco_alvo = alt.preco_alvo if alt.preco_alvo is not None else proposta.preco_alvo
            relatorio.preco_stop = alt.preco_stop if alt.preco_stop is not None else proposta.preco_stop
            if alt.nome_estrategia and alt.nome_estrategia != "Aguardar no Caixa":
                relatorio.operacao_recomendada = alt.nome_estrategia
        relatorio.strike_compra = None
        relatorio.strike_venda = None
        relatorio.premio_compra = None
        relatorio.premio_venda = None
        relatorio.origem_premios = None
        relatorio.gregas = None

    elif "PRINCIPAL" in estrategia:
        if proposta is not None and proposta.estrategia_principal is not None:
            princ = proposta.estrategia_principal
            relatorio.strike_compra = princ.strike_compra if princ.strike_compra is not None else proposta.strike_compra
            relatorio.strike_venda = princ.strike_venda if princ.strike_venda is not None else proposta.strike_venda
            relatorio.premio_compra = princ.premio_compra if princ.premio_compra is not None else proposta.premio_compra
            relatorio.premio_venda = princ.premio_venda if princ.premio_venda is not None else proposta.premio_venda
            relatorio.origem_premios = princ.origem_premios or proposta.origem_premios
            relatorio.preco_entrada = princ.preco_entrada if princ.preco_entrada is not None else proposta.preco_entrada
            relatorio.preco_alvo = princ.preco_alvo if princ.preco_alvo is not None else proposta.preco_alvo
            if princ.nome_estrategia and princ.nome_estrategia != "Aguardar no Caixa":
                relatorio.operacao_recomendada = princ.nome_estrategia
            if princ.gregas is not None:
                relatorio.gregas = princ.gregas

            if relatorio.strike_compra is not None and relatorio.premio_compra is not None:
                relatorio.preco_stop = None
            else:
                relatorio.preco_stop = princ.preco_stop if princ.preco_stop is not None else proposta.preco_stop

    elif "NENHUMA" in estrategia or not getattr(decisao_risco, "aprovado_para_divulgacao", False):
        relatorio.preco_entrada = None
        relatorio.preco_alvo = None
        relatorio.preco_stop = None
        relatorio.strike_compra = None
        relatorio.strike_venda = None
        relatorio.premio_compra = None
        relatorio.premio_venda = None
        relatorio.origem_premios = None
        relatorio.gregas = None

    return relatorio


def extrair_preco_atual_medido(resultado_crew: Any, ticker: Optional[str] = None) -> Optional[float]:
    """
    Extrai a cotação real (preco_atual) medida pelo analista técnico ou screener
    durante a mesma execução, a partir dos outputs das tarefas [V0-02b].
    """
    if hasattr(resultado_crew, "preco_atual") and getattr(resultado_crew, "preco_atual", None) is not None:
        try:
            val = float(resultado_crew.preco_atual)
            if val > 0:
                return val
        except Exception:
            pass

    tasks_output = getattr(resultado_crew, "tasks_output", []) or []
    for task_out in tasks_output:
        pyd = getattr(task_out, "pydantic", None)
        if isinstance(pyd, AnaliseTecnicaModel):
            if pyd.preco_atual is not None and float(pyd.preco_atual) > 0:
                return float(pyd.preco_atual)
        if pyd and getattr(pyd, "__class__", None).__name__ == "AnaliseTecnicaModel":
            pa = getattr(pyd, "preco_atual", None)
            if pa is not None and float(pa) > 0:
                return float(pa)

    for task_out in tasks_output:
        desc = getattr(task_out, "description", "").lower()
        nome = getattr(task_out, "name", "").lower()
        if "timing" in desc or "técnico" in desc or "tecnico" in desc or "validar_timing" in nome:
            pyd = getattr(task_out, "pydantic", None)
            if pyd and getattr(pyd, "preco_atual", None) is not None:
                try:
                    val = float(pyd.preco_atual)
                    if val > 0:
                        return val
                except Exception:
                    pass
            raw = str(getattr(task_out, "raw", ""))
            match = re.search(r'["\']preco_atual["\']\s*:\s*([0-9]+\.?[0-9]*)', raw)
            if match:
                try:
                    val = float(match.group(1))
                    if val > 0:
                        return val
                except Exception:
                    pass

    return None


from tools.options_tools import calcular_payoff_trava_alta


def extrair_rr_efetivo(
    relatorio: RelatorioExecutivoFinal,
    decisao_risco: Optional[DecisaoRiscoModel] = None
) -> float:
    """
    Consolida de forma determinística e anti-omissão a Razão Risco/Retorno (R/R) real da operação,
    SEMPRE calculada em código pelos parâmetros numéricos reais da operação:
    - Trava de Alta: lucro_maximo_num / perda_maxima_num (calcular_payoff_trava_alta)
    - Ação a vista: (preco_alvo - preco_entrada) / (preco_entrada - preco_stop)
    - Fallback de compatibilidade via níveis de preços na tabela operacional.
    NUNCA usa R/R declarado ou texto de '2.1:1'.
    """
    # 1. Trava de alta via campos float estruturados
    s_compra = getattr(relatorio, "strike_compra", None)
    s_venda = getattr(relatorio, "strike_venda", None)
    p_compra = getattr(relatorio, "premio_compra", None)
    p_venda = getattr(relatorio, "premio_venda", None)

    if s_compra is not None and s_venda is not None and p_compra is not None and p_venda is not None:
        try:
            fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
            res = fn_payoff(
                strike_compra=float(s_compra),
                premio_pago_compra=float(p_compra),
                strike_venda=float(s_venda),
                premio_recebido_venda=float(p_venda)
            )
            if isinstance(res, dict) and res.get("status") == "sucesso":
                p_max = float(res.get("perda_maxima_num", 0.0))
                l_max = float(res.get("lucro_maximo_num", 0.0))
                if p_max > 0 and l_max > 0:
                    return round(l_max / p_max, 2)
        except Exception:
            pass

    # 2. Ação a vista via campos float estruturados
    e_val = getattr(relatorio, "preco_entrada", None)
    a_val = getattr(relatorio, "preco_alvo", None)
    s_val = getattr(relatorio, "preco_stop", None)

    if e_val is not None and a_val is not None and s_val is not None:
        return calcular_rr_deterministico(float(e_val), float(a_val), float(s_val))

    # 3. Fallback determinístico de preços na tabela de parâmetros operacionais (sem usar texto de R/R)
    preco_entrada = 0.0
    preco_alvo = 0.0
    preco_stop = 0.0

    for item in getattr(relatorio, "parametros_operacionais", []):
        nome = getattr(item, "parametro", "").lower()
        val_str = getattr(item, "valor", "").replace("R$", "").replace(" ", "").strip()
        try:
            if "entrada" in nome:
                preco_entrada = float(val_str.replace(",", "."))
            elif "alvo" in nome:
                preco_alvo = float(val_str.replace(",", "."))
            elif "stop" in nome:
                preco_stop = float(val_str.replace(",", "."))
        except Exception:
            pass

    if preco_entrada > 0 and preco_alvo > 0 and preco_stop > 0:
        return calcular_rr_deterministico(preco_entrada, preco_alvo, preco_stop)

    return 0.0


def auditar_gate_de_risco_programatico(
    decisao_risco: Optional[DecisaoRiscoModel] = None,
    razao_risco_retorno: float = 0.0,
    relatorio: Optional[RelatorioExecutivoFinal] = None,
    preco_entrada: Optional[float] = None,
    preco_alvo: Optional[float] = None,
    preco_stop: Optional[float] = None,
    rr_declarado: Optional[float] = None,
    strike_compra: Optional[float] = None,
    strike_venda: Optional[float] = None,
    premio_compra: Optional[float] = None,
    premio_venda: Optional[float] = None,
    preco_atual_medido: Optional[float] = None,
    origem_premios: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """
    Executa a auditoria programática rígida da recomendação.
    Retorna: (aprovado: bool, status_final: str, motivo: str)
    
    Regras estritas (Código não-burlável):
    1. Se aprovado_para_divulgacao for False ou status REPROVADO_TOTAL -> REPROVADO_TOTAL.
    2. R/R do Gate é SEMPRE o calculado em código a partir dos parâmetros numéricos.
    3. Alvo <= Entrada ou Stop >= Entrada numa compra -> Veto.
    4. R/R declarado divergindo do calculado em mais de 0.05 -> Veto por divergência.
    5. R/R calculado < 1.50 -> Veto por assimetria insuficiente.
    6. Relatório sem parâmetros numéricos tipados -> Veto.
    7. Preço de entrada sem lastro de mercado (> 5% de divergência da cotação medida) -> Veto [V0-02b].
    8. Trava de opções sem prêmios medidos reais da BRAPI -> Veto [V0-02b].
    """
    # Regra 0: Se decisao_risco não foi fornecida, reprova por padrão [V1-01]
    if decisao_risco is None:
        return (
            False,
            "REPROVADO_TOTAL",
            "Decisao de risco ausente: esteira nao produziu deliberacao valida"
        )

    # Regra 1: Veto explícito do coordenador de risco autêntico
    if not decisao_risco.aprovado_para_divulgacao or decisao_risco.status == "REPROVADO_TOTAL":
        return (
            False,
            "REPROVADO_TOTAL",
            f"VETO DO COMITÊ DE RISCO: {decisao_risco.parecer_risco or 'Operação vetada pelo Coordenador de Risco.'}"
        )

    # Coleta de campos numéricos (prioriza argumentos explícitos e em seguida relatorio)
    if relatorio is not None:
        if preco_entrada is None:
            preco_entrada = getattr(relatorio, "preco_entrada", None)
        if preco_alvo is None:
            preco_alvo = getattr(relatorio, "preco_alvo", None)
        if preco_stop is None:
            preco_stop = getattr(relatorio, "preco_stop", None)
        if strike_compra is None:
            strike_compra = getattr(relatorio, "strike_compra", None)
        if strike_venda is None:
            strike_venda = getattr(relatorio, "strike_venda", None)
        if premio_compra is None:
            premio_compra = getattr(relatorio, "premio_compra", None)
        if premio_venda is None:
            premio_venda = getattr(relatorio, "premio_venda", None)
        if origem_premios is None:
            origem_premios = getattr(relatorio, "origem_premios", None)

    # R/R declarado pelo modelo
    if rr_declarado is None:
        if decisao_risco and getattr(decisao_risco, "razao_risco_retorno_auditada", 0.0) > 0:
            rr_declarado = float(decisao_risco.razao_risco_retorno_auditada)
        elif relatorio and getattr(relatorio, "razao_risco_retorno_num", 0.0) > 0:
            rr_declarado = float(relatorio.razao_risco_retorno_num)

    # Determinação estrita do R/R calculado em código:
    rr_calculado = 0.0

    # Caso A: Trava de alta com call
    if strike_compra is not None and strike_venda is not None:
        if premio_compra is None or premio_venda is None:
            return (
                False,
                "REPROVADO_TOTAL",
                "VETO PROGRAMÁTICO DE CÓDIGO: Prêmios de compra ou venda ausentes para cálculo de payoff da trava."
            )
        # Validação de origem de prêmios para trava de opções [V0-02b]
        if origem_premios != "BRAPI_V2_OPTIONS_MEDIDO":
            return (
                False,
                "REPROVADO_TOTAL",
                "Premios sem cotacao real: trava aprovada sem dados de book da BRAPI"
            )
        try:
            fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
            res_payoff = fn_payoff(
                strike_compra=float(strike_compra),
                premio_pago_compra=float(premio_compra),
                strike_venda=float(strike_venda),
                premio_recebido_venda=float(premio_venda)
            )
            if not isinstance(res_payoff, dict) or res_payoff.get("status") != "sucesso":
                msg = res_payoff.get("mensagem", "Falha no cálculo de payoff da trava") if isinstance(res_payoff, dict) else "Erro payoff"
                return False, "REPROVADO_TOTAL", f"VETO PROGRAMÁTICO DE CÓDIGO: {msg}"
            p_max = float(res_payoff.get("perda_maxima_num", 0.0))
            l_max = float(res_payoff.get("lucro_maximo_num", 0.0))
            if p_max <= 0:
                return False, "REPROVADO_TOTAL", "VETO PROGRAMÁTICO DE CÓDIGO: Perda máxima inválida (<= 0) na trava."
            rr_calculado = l_max / p_max
        except Exception as e_trava:
            return False, "REPROVADO_TOTAL", f"VETO PROGRAMÁTICO DE CÓDIGO: Erro no cálculo de payoff: {str(e_trava)}"

    # Caso B: Ação a vista
    elif preco_entrada is not None or preco_alvo is not None or preco_stop is not None:
        if preco_entrada is None or preco_alvo is None or preco_stop is None:
            return (
                False,
                "REPROVADO_TOTAL",
                "VETO PROGRAMÁTICO DE CÓDIGO: Parâmetros numéricos incompletos (entrada, alvo ou stop ausentes)."
            )
        e = float(preco_entrada)
        a = float(preco_alvo)
        s = float(preco_stop)
        if e <= 0 or a <= 0 or s <= 0:
            return False, "REPROVADO_TOTAL", "VETO PROGRAMÁTICO DE CÓDIGO: Preços de entrada, alvo e stop devem ser positivos."
        if a <= e:
            return False, "REPROVADO_TOTAL", "VETO PROGRAMÁTICO DE CÓDIGO: Preço alvo menor ou igual ao preço de entrada numa compra."
        if s >= e:
            return False, "REPROVADO_TOTAL", "VETO PROGRAMÁTICO DE CÓDIGO: Stop loss maior ou igual ao preço de entrada numa compra."

        ganho = a - e
        perda = e - s
        if perda <= 0 or ganho <= 0:
            return False, "REPROVADO_TOTAL", "VETO PROGRAMÁTICO DE CÓDIGO: Parâmetros de risco/retorno inválidos."
        rr_calculado = ganho / perda

    elif relatorio is not None:
        # Se veio um relatório mas nenhum parâmetro numérico foi preenchido: VETO!
        return (
            False,
            "REPROVADO_TOTAL",
            "VETO PROGRAMÁTICO DE CÓDIGO: Operação sem parâmetros numéricos tipados de entrada, alvo ou stop."
        )

    else:
        # Quando relatorio is None e não há parâmetros numéricos (nem preco_entrada nem strike_compra) [V1-01]
        return (
            False,
            "REPROVADO_TOTAL",
            "Operacao sem parametros numericos tipados"
        )

    # Comparação estrita entre R/R declarado pelos agentes e o calculado em código:
    if rr_declarado is not None and rr_declarado > 0:
        divergencia = abs(rr_declarado - rr_calculado)
        divergencia_arredondado = abs(rr_declarado - round(rr_calculado, 2))
        if divergencia > 0.05 and divergencia_arredondado > 0.05:
            return (
                False,
                "REPROVADO_TOTAL",
                f"VETO PROGRAMÁTICO DE CÓDIGO: R/R declarado diverge do calculado (declarado: {rr_declarado:.2f}, calculado: {rr_calculado:.2f})."
            )

    # Piso matemático inegociável de assimetria (mínimo obrigatório 1.5:1)
    if rr_calculado < 1.5:
        return (
            False,
            "REPROVADO_TOTAL",
            f"VETO PROGRAMÁTICO DE CÓDIGO: Relação R/R ({rr_calculado:.2f}:1) é estritamente inferior ao piso obrigatório de 1.50:1 ou foi omitida da recomendação."
        )

    # Validação de lastro de mercado no gate de risco [V0-02b]
    if preco_entrada is not None:
        if preco_atual_medido is None:
            return (
                False,
                "REPROVADO_TOTAL",
                "Preco de entrada sem cotacao de referencia disponivel"
            )
        if abs(float(preco_entrada) - preco_atual_medido) / preco_atual_medido > 0.05:
            return (
                False,
                "REPROVADO_TOTAL",
                f"Preco de entrada sem lastro de mercado: entrada em R$ {float(preco_entrada):.2f} diverge mais de 5% da cotacao medida R$ {preco_atual_medido:.2f}"
            )

    status_aprovado = decisao_risco.status if decisao_risco.status in ["APROVADO_PRINCIPAL", "APROVADO_ALTERNATIVA"] else "APROVADO_PRINCIPAL"
    return True, status_aprovado, f"Aprovado pelo Comitê de Risco e Validado pelo Gate ({status_aprovado} | R/R: {rr_calculado:.2f}:1)."


DISCLAIMER_CVM_OFICIAL = (
    "Este relatório foi elaborado com fins exclusivamente informativos pela Mesa de Operações e não constitui oferta "
    "pública de valores mobiliários. Operações em renda variável e derivativos (opções) envolvem risco substancial "
    "de perda de capital e podem não ser adequadas a todos os perfis de investidor. A rentabilidade obtida no passado "
    "não representa garantia de rentabilidade futura. Todas as tomadas de decisão são de responsabilidade exclusiva "
    "do investidor."
)


def aplicar_contingencia_de_veto(relatorio: RelatorioExecutivoFinal, motivo_veto: str) -> RelatorioExecutivoFinal:
    """
    Ajusta programaticamente o relatório executivo final caso a operação seja vetada pelo Gate de Risco [V1-02].
    Garante que parâmetros especulativos sejam removidos e substituídos por instruções de retenção de caixa,
    eliminando textos alucinados de aprovação e padronizando o disclaimer regulatório.
    """
    relatorio.status_decisao = "REPROVADO_TOTAL"
    relatorio.operacao_recomendada = "Recomendação de Manutenção em Caixa (Operação Vetada por Risco)"
    relatorio.resumo_executivo = (
        f"Operacao vetada pelo gate de risco: {motivo_veto}. "
        "A analise dos agentes foi descartada para fins operacionais. "
        "Mantenha 100% dos recursos em caixa/CDI."
    )
    relatorio.disclaimer_cvm = DISCLAIMER_CVM_OFICIAL
    relatorio.razao_risco_retorno_num = 0.0
    relatorio.preco_entrada = None
    relatorio.preco_alvo = None
    relatorio.preco_stop = None
    relatorio.strike_compra = None
    relatorio.strike_venda = None
    relatorio.premio_compra = None
    relatorio.premio_venda = None
    relatorio.gestao_risco_e_saida = (
        f"GATE DE RISCO ATIVADO: {motivo_veto} "
        "Mantenha 100% dos recursos alocados em caixa / CDI até o surgimento de oportunidade com relação risco/retorno favorável."
    )
    
    # Atualiza ou sobrescreve a tabela de parâmetros para evitar que o investidor execute ordens vetadas
    parametros_seguros = [
        ItemParametro(parametro="Diretriz Operacional", valor="MANTER 100% EM CAIXA"),
        ItemParametro(parametro="Status do Comitê de Risco", valor="REPROVADO_TOTAL (Veto Ativado)"),
        ItemParametro(parametro="Preço de Entrada", valor="N/A - OPERAÇÃO NÃO AUTORIZADA"),
        ItemParametro(parametro="Alvo de Lucro", valor="N/A"),
        ItemParametro(parametro="Stop Loss", valor="N/A"),
        ItemParametro(parametro="Motivo do Veto", valor=motivo_veto)
    ]
    relatorio.parametros_operacionais = parametros_seguros
    relatorio.gregas = None
    return relatorio

