"""
Ponto de entrada oficial da Mesa de Operações B3.
Executa a esteira multiagente, renderiza o Dashboard Executivo no console via Rich
e gera automaticamente o arquivo PDF formal em output/.
"""

import os
import sys
from datetime import datetime

# Garante suporte a UTF-8 e emojis no console do Windows sem erros de charmap
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

load_dotenv()

from crew import MesaOperacoesCrew
from tools.pdf_generator import gerar_pdf_relatorio


def validar_chaves_ambiente(console: Console) -> bool:
    """Verifica se as chaves mínimas estão presentes no .env."""
    google_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    brapi_token = (os.getenv("BRAPI_TOKEN") or os.getenv("BRAPI_API_KEY") or "").strip()

    faltantes = []
    if not google_key:
        faltantes.append("GOOGLE_API_KEY (ou GEMINI_API_KEY)")
    if not brapi_token:
        faltantes.append("BRAPI_TOKEN (ou BRAPI_API_KEY)")

    if faltantes:
        tabela = Table(box=box.ROUNDED, show_header=False)
        tabela.add_column("Aviso", style="bold red")
        tabela.add_row(f"Atenção: As variáveis de ambiente a seguir não foram preenchidas no arquivo .env:\n- {', '.join(faltantes)}")
        tabela.add_row("Edite o arquivo '.env' e insira suas credenciais antes de executar a mesa completa.")
        console.print(Panel(tabela, title="[bold yellow]Configuração Necessária[/bold yellow]", border_style="yellow"))
        return False
    return True


def exibir_dashboard_console(console: Console, relatorio) -> None:
    """Exibe na tela um dashboard executivo visual e profissional com Rich."""
    console.print("\n")
    titulo_text = Text("🏛️  MESA DE OPERAÇÕES B3 - PAINEL EXECUTIVO DE RECOMENDAÇÃO", style="bold white on dark_blue")
    console.print(Panel(titulo_text, box=box.HEAVY, style="blue"))

    # Grid de Parâmetros Operacionais
    tabela_params = Table(title="📋 Parâmetros da Estrutura Operacional", box=box.ROUNDED, header_style="bold cyan")
    tabela_params.add_column("Item / Métrica", style="bold white", width=30)
    tabela_params.add_column("Detalhamento Oficial", style="green", width=55)

    tabela_params.add_row("Ativo Foco (Cesta de Liquidez B3)", str(getattr(relatorio, "ativo_alvo", "N/A")))
    tabela_params.add_row("Operação Recomendada", str(getattr(relatorio, "operacao_recomendada", "N/A")))

    params = getattr(relatorio, "parametros_operacionais", [])
    if isinstance(params, list):
        for item in params:
            nome = getattr(item, "parametro", str(item))
            val = getattr(item, "valor", "")
            tabela_params.add_row(str(nome), str(val))
    elif isinstance(params, dict):
        for k, v in params.items():
            tabela_params.add_row(str(k), str(v))

    console.print(tabela_params)

    # Painel da Tese de Investimento
    resumo = getattr(relatorio, "resumo_executivo", "N/A")
    console.print(Panel(resumo, title="[bold green]💡 Tese de Investimento & Fundamentos[/bold green]", box=box.ROUNDED))

    # Painel de Gestão de Risco
    risco = getattr(relatorio, "gestao_risco_e_saida", "N/A")
    console.print(Panel(risco, title="[bold red]🛡️ Gestão de Risco & Stop Loss[/bold red]", box=box.ROUNDED))

    # Painel Regulatório CVM
    disclaimer = getattr(relatorio, "disclaimer_cvm", "Em conformidade com a Resolução CVM nº 20/2021.")
    console.print(Panel(disclaimer, title="[bold yellow]⚖️ Aviso Legal Regulatório (CVM 20/2021)[/bold yellow]", box=box.MINIMAL))


def run():
    """Execução principal da Mesa de Operações."""
    console = Console(legacy_windows=False)

    banner = Text(
        "╔════════════════════════════════════════════════════════════════════╗\n"
        "║     MESA DE OPERAÇÕES B3 - TOP 10 LIQUIDEZ (CESTA IBRX-100)        ║\n"
        "║      Macro -> Fundamentalista -> Técnico -> Opções -> Risco        ║\n"
        "╚════════════════════════════════════════════════════════════════════╝",
        style="bold bright_cyan",
    )
    console.print(banner)

    if not validar_chaves_ambiente(console):
        console.print("[dim yellow]Dica: Preencha o arquivo .env e execute novamente: `python main.py`[/dim yellow]\n")
        return

    console.print("\n[bold green]🚀 Iniciando a esteira de análise com os 6 especialistas...[/bold green]")
    console.print("[dim]Aguarde enquanto os agentes processam notícias macro, múltiplos da BRAPI, médias e Black-Scholes...[/dim]\n")

    try:
        mesa = MesaOperacoesCrew()
        resultado = mesa.crew().kickoff()

        # Extração do resultado estruturado
        relatorio = None
        if hasattr(resultado, "pydantic") and resultado.pydantic:
            relatorio = resultado.pydantic
        else:
            relatorio = resultado

        # Auditoria com Gate de Risco Programático em Código (Audit Items A & B)
        from tools.risk_gate import (
            auditar_gate_de_risco_programatico,
            aplicar_contingencia_de_veto,
            extrair_decisao_risco_autentica,
            extrair_rr_efetivo
        )

        # 1. Extração autenticada da decisão direta do Coordenador de Risco (Item B)
        decisao_risco_autentica = extrair_decisao_risco_autentica(resultado, relatorio)

        # 2. Extração consolidada e anti-omissão da Razão R/R (Item A)
        rr_efetivo = extrair_rr_efetivo(relatorio, decisao_risco_autentica)

        # 3. Auditoria programática em código inegociável
        aprovado_gate, status_final, motivo_gate = auditar_gate_de_risco_programatico(
            decisao_risco_autentica,
            rr_efetivo
        )

        if not aprovado_gate:
            relatorio = aplicar_contingencia_de_veto(relatorio, motivo_gate)
            status_final = "REPROVADO_TOTAL"
        else:
            relatorio.status_decisao = status_final
            relatorio.razao_risco_retorno_num = rr_efetivo

        # Exibição no console
        exibir_dashboard_console(console, relatorio)

        # Geração do Relatório PDF com Status Dinâmico Real
        data_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"output/relatorio_operacao_{data_str}.pdf"

        titulo = getattr(relatorio, "titulo", "Relatório de Recomendação - Mesa de Operações B3")
        ativo = getattr(relatorio, "ativo_alvo", "DADOS_INDISPONIVEIS")
        estrategia = getattr(relatorio, "operacao_recomendada", "Operação Aprovada pela Mesa")
        resumo = getattr(relatorio, "resumo_executivo", str(resultado))
        gestao_risco = getattr(relatorio, "gestao_risco_e_saida", "Conforme limites de risco da mesa.")


        # Construção dos parâmetros operacionais para o PDF oficial
        params_raw = getattr(relatorio, "parametros_operacionais", [])
        params_dict = {}
        if isinstance(params_raw, list):
            for item in params_raw:
                p_nome = getattr(item, "parametro", str(item))
                p_val = getattr(item, "valor", "")
                params_dict[str(p_nome)] = str(p_val)
        elif isinstance(params_raw, dict):
            params_dict = {str(k): str(v) for k, v in params_raw.items()}

        gregas_model = getattr(relatorio, "gregas", None)
        gregas_dict = {}
        if gregas_model:
            gregas_dict = {
                "delta": getattr(gregas_model, "delta", 0.0),
                "gamma": getattr(gregas_model, "gamma", 0.0),
                "theta": getattr(gregas_model, "theta", 0.0),
                "vega": getattr(gregas_model, "vega", 0.0),
            }

        arquivo_gerado = gerar_pdf_relatorio(
            titulo=titulo,
            ativo=ativo,
            estrategia=estrategia,
            resumo_executivo=resumo,
            parametros=params_dict,
            gregas=gregas_dict,
            gestao_risco=gestao_risco,
            status=status_final,
            caminho_saida=pdf_path
        )

        console.print(f"\n[bold green]✅ Relatório PDF executivo gerado com sucesso![/bold green]")
        console.print(f"📄 Arquivo disponível em: [bold underline cyan]{arquivo_gerado}[/bold underline cyan]\n")

    except Exception as e:
        console.print(f"\n[bold red]❌ Ocorreu um erro durante a execução da esteira:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    run()
