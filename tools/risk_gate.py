"""
Módulo determinístico de Gate de Risco Programático (Code-Enforced Risk Governance).
Impõe regras matemáticas inegociáveis de preservação de capital que NENHUMA LLM pode violar.
"""

import re
from typing import Dict, Any, Tuple, Optional
from schemas.output_models import DecisaoRiscoModel, RelatorioExecutivoFinal, ItemParametro


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


def extrair_rr_efetivo(
    relatorio: RelatorioExecutivoFinal,
    decisao_risco: Optional[DecisaoRiscoModel] = None
) -> float:
    """
    Consolida de forma resiliente e anti-omissão a Razão Risco/Retorno (R/R) real da operação:
    1. Campo estruturado float no schema de Risco (razao_risco_retorno_auditada).
    2. Campo estruturado float no Relatório Executivo (razao_risco_retorno_num).
    3. Cálculo determinístico via preços de Entrada, Alvo e Stop Loss na tabela.
    4. Parsing numérico em parâmetros textuais de R/R.
    """
    # 1. Do modelo de risco autenticado
    if decisao_risco and decisao_risco.razao_risco_retorno_auditada > 0:
        return float(decisao_risco.razao_risco_retorno_auditada)

    # 2. Do campo estruturado do relatório
    if getattr(relatorio, "razao_risco_retorno_num", 0.0) > 0:
        return float(relatorio.razao_risco_retorno_num)

    # 3. Extração via preços operacionais (deterministico)
    preco_entrada = 0.0
    preco_alvo = 0.0
    preco_stop = 0.0
    rr_texto = 0.0

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
            elif "r/r" in nome or "risco/retorno" in nome or "relação" in nome:
                # Trata formatos "2.1:1" ou "1:2.1" ou "2.1"
                partes = val_str.replace(",", ".").split(":")
                nums = [float(p) for p in partes if re.match(r"^-?\d+(\.\d+)?$", p)]
                if len(nums) == 2:
                    rr_texto = nums[1] if nums[0] == 1.0 else nums[0]
                elif len(nums) == 1:
                    rr_texto = nums[0]
        except Exception:
            pass

    if preco_entrada > 0 and preco_alvo > 0 and preco_stop > 0:
        rr_calc = calcular_rr_deterministico(preco_entrada, preco_alvo, preco_stop)
        if rr_calc > 0:
            return rr_calc

    if rr_texto > 0:
        return rr_texto

    return 0.0


def auditar_gate_de_risco_programatico(
    decisao_risco: DecisaoRiscoModel,
    razao_risco_retorno: float = 0.0
) -> Tuple[bool, str, str]:
    """
    Executa a auditoria programática rígida da recomendação.
    Retorna: (aprovado: bool, status_final: str, motivo: str)
    
    Regras estritas (Código não-burlável):
    1. Se aprovado_para_divulgacao for False -> REPROVADO_TOTAL.
    2. Se status for REPROVADO_TOTAL -> REPROVADO_TOTAL.
    3. Se tentar aprovar COM RAZÃO R/R OMITIDA OU < 1.5:1 -> VETO PROGRAMÁTICO IMEDIATO.
       (Presume-se reprovado a menos que prove matematicamente R/R >= 1.50).
    """
    # Regra 1 e 2: Veto explícito do coordenador de risco autêntico
    if not decisao_risco.aprovado_para_divulgacao or decisao_risco.status == "REPROVADO_TOTAL":
        return (
            False,
            "REPROVADO_TOTAL",
            f"VETO DO COMITÊ DE RISCO: {decisao_risco.parecer_risco or 'Operação vetada pelo Coordenador de Risco.'}"
        )

    # Regra 3: Piso matemático inegociável de assimetria (mínimo obrigatório 1.5:1).
    # Omissão (0.0) ou valor abaixo de 1.5 veta automaticamente.
    if razao_risco_retorno < 1.5:
        return (
            False,
            "REPROVADO_TOTAL",
            f"VETO PROGRAMÁTICO DE CÓDIGO: Relação R/R ({razao_risco_retorno:.2f}:1) é estritamente inferior ao piso obrigatório de 1.50:1 ou foi omitida da recomendação."
        )

    status_aprovado = decisao_risco.status if decisao_risco.status in ["APROVADO_PRINCIPAL", "APROVADO_ALTERNATIVA"] else "APROVADO_PRINCIPAL"
    return True, status_aprovado, f"Aprovado pelo Comitê de Risco e Validado pelo Gate ({status_aprovado} | R/R: {razao_risco_retorno:.2f}:1)."


def aplicar_contingencia_de_veto(relatorio: RelatorioExecutivoFinal, motivo_veto: str) -> RelatorioExecutivoFinal:
    """
    Ajusta programaticamente o relatório executivo final caso a operação seja vetada pelo Gate de Risco.
    Garante que parâmetros especulativos sejam removidos e substituídos por instruções de retenção de caixa.
    """
    relatorio.status_decisao = "REPROVADO_TOTAL"
    relatorio.operacao_recomendada = "Recomendação de Manutenção em Caixa (Operação Vetada por Risco)"
    relatorio.razao_risco_retorno_num = 0.0
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

