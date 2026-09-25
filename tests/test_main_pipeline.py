"""
Teste de regressão para o pipeline de execução e geração de PDF do main.py.
Garante que params_dict, gregas, gestão de risco e status são extraídos
e repassados ao gerador de PDF sem NameError.
"""

import os
from unittest.mock import MagicMock
from schemas.output_models import RelatorioExecutivoFinal, ItemParametro, GregasOpcoesModel
from tools.pdf_generator import gerar_pdf_relatorio


def test_main_pdf_pipeline_com_parametros_em_lista(tmp_path):
    """Garante que a extração de parâmetros em lista de RelatorioExecutivoFinal gera PDF válido sem NameError."""
    relatorio = RelatorioExecutivoFinal(
        titulo="Recomendação Trava de Alta - ITUB4",
        ativo_alvo="ITUB4",
        operacao_recomendada="Trava de Alta com Call",
        resumo_executivo="Tese bancária fundamentada em ROE consistente.",
        status_decisao="APROVADO_PRINCIPAL",
        razao_risco_retorno_num=1.85,
        parametros_operacionais=[
            ItemParametro(parametro="Preço de Entrada", valor="R$ 42.00"),
            ItemParametro(parametro="Alvo", valor="R$ 46.00"),
            ItemParametro(parametro="Stop Loss", valor="R$ 40.00"),
            ItemParametro(parametro="Relação R/R", valor="1.85:1"),
        ],
        gregas=GregasOpcoesModel(delta=0.52, gamma=0.07, theta=-0.03, vega=0.10),
        gestao_risco_e_saida="Stop acionado se romper suporte de R$ 40.00."
    )

    # Executa a mesma lógica de main.py
    params_raw = getattr(relatorio, "parametros_operacionais", [])
    params_dict = {}
    if isinstance(params_raw, list):
        for item in params_raw:
            p_nome = getattr(item, "parametro", str(item))
            p_val = getattr(item, "valor", "")
            params_dict[str(p_nome)] = str(p_val)
    elif isinstance(params_raw, dict):
        params_dict = {str(k): str(v) for k, v in params_raw.items()}

    assert "Preço de Entrada" in params_dict
    assert params_dict["Preço de Entrada"] == "R$ 42.00"

    pdf_out = str(tmp_path / "relatorio_teste_main.pdf")
    gregas_dict = {
        "delta": relatorio.gregas.delta,
        "gamma": relatorio.gregas.gamma,
        "theta": relatorio.gregas.theta,
        "vega": relatorio.gregas.vega,
    }

    arquivo = gerar_pdf_relatorio(
        titulo=relatorio.titulo,
        ativo=relatorio.ativo_alvo,
        estrategia=relatorio.operacao_recomendada,
        resumo_executivo=relatorio.resumo_executivo,
        parametros=params_dict,
        gregas=gregas_dict,
        gestao_risco=relatorio.gestao_risco_e_saida,
        status=relatorio.status_decisao,
        caminho_saida=pdf_out
    )

    assert os.path.exists(arquivo)
    assert os.path.getsize(arquivo) > 1000
