"""
Módulo gerador de relatório executivo em formato PDF profissional com governança estrita de risco.
Reflete dinamicamente o status real da decisão do Comitê de Risco (Aprovado / Reprovado),
renderiza gregas de derivativos e o disclaimer regulatório CVM 20/2021.
"""

import os
from datetime import datetime
from fpdf import FPDF


class RelatorioExecutivoPDF(FPDF):
    def header(self):
        # Faixa superior azul marinho institucional
        self.set_fill_color(15, 32, 67)  # Navy Blue #0F2043
        self.rect(0, 0, 210, 22, "F")

        # Título principal no cabeçalho
        self.set_xy(10, 5)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.cell(120, 7, "MESA DE OPERAÇÕES B3 | RESEARCH & TRADING", 0, 0, "L")

        self.set_font("Helvetica", "", 9)
        self.set_text_color(200, 220, 255)
        data_str = datetime.now().strftime("%d/%m/%Y")
        self.cell(70, 7, f"DATA: {data_str} | CESTA DE LIQUIDEZ B3", 0, 1, "R")
        self.ln(12)

    def footer(self):
        self.set_y(-18)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, "Mesa de Operações B3 - Documento Confidencial | Em conformidade com a Resolução CVM nº 20/2021", 0, 1, "C")
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", 0, 0, "C")


def sanitizar_texto(texto: str) -> str:
    """Substitui caracteres especiais e fora do Latin-1 para PDF seguro e legível."""
    if not texto:
        return ""
    substituicoes = {
        "—": "-", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'",
        "•": "*", "…": "...", "→": "->", "≥": ">=", "≤": "<=", "≠": "!=",
        "&middot;": "-", "\u2013": "-", "\u2014": "-", "\u2022": "*"
    }
    res = str(texto)
    for k, v in substituicoes.items():
        res = res.replace(k, v)
    return res.encode("latin-1", "replace").decode("latin-1")


def gerar_pdf_relatorio(
    titulo: str,
    ativo: str,
    estrategia: str,
    resumo_executivo: str,
    parametros: dict,
    gregas: dict = None,
    gestao_risco: str = "",
    status: str = "APROVADO",
    caminho_saida: str = "output/relatorio_operacao.pdf"
) -> str:
    """
    Gera o arquivo PDF executivo formatado da operação recomendada.
    O status reflete dinamicamente a decisão do Comitê de Risco (APROVADO ou REPROVADO).
    """
    # Ajuste de caminho para ambientes somente-leitura (ex: Vercel Serverless / Lambda)
    dir_saida = os.path.dirname(caminho_saida) or "."
    try:
        os.makedirs(dir_saida, exist_ok=True)
        teste_path = os.path.join(dir_saida, f".test_w_{os.getpid()}")
        with open(teste_path, "w") as f:
            f.write("1")
        os.remove(teste_path)
    except (OSError, PermissionError):
        dir_tmp = "/tmp/output" if os.path.exists("/tmp") else os.path.join(os.path.expanduser("~"), "tmp_mesa")
        os.makedirs(dir_tmp, exist_ok=True)
        caminho_saida = os.path.join(dir_tmp, os.path.basename(caminho_saida))

    pdf = RelatorioExecutivoPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Identificação se a operação foi Aprovada ou Reprovada pelo Comitê de Risco
    is_aprovado = "APROVAD" in status.upper()

    # Título do Relatório
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(15, 32, 67)
    pdf.cell(0, 10, sanitizar_texto(titulo), ln=True, align="L")

    # Tarja de Destaque com Status Dinâmico Real
    pdf.set_line_width(0.3)
    if is_aprovado:
        pdf.set_fill_color(240, 250, 244)  # Verde suave
        pdf.set_draw_color(16, 185, 129)
    else:
        pdf.set_fill_color(254, 242, 242)  # Vermelho suave
        pdf.set_draw_color(239, 68, 68)

    start_y = pdf.get_y()
    pdf.rect(10, start_y, 190, 24, "FD")

    # Linha 1: ATIVO à esquerda, STATUS à direita
    pdf.set_xy(14, start_y + 2)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(30, 40, 60)
    pdf.cell(75, 5.5, sanitizar_texto(f"ATIVO: {ativo}"), 0, 0)

    # Status Dinâmico Auditado (Alinhado à direita)
    pdf.set_xy(90, start_y + 2)
    if is_aprovado:
        pdf.set_text_color(16, 140, 70)
        status_label = "STATUS: APROVADO PELA MESA"
    else:
        pdf.set_text_color(200, 30, 30)
        status_label = "STATUS: REPROVADO (MANTER CAIXA)"
    pdf.cell(106, 5.5, status_label, 0, 1, align="R")

    # Linha 2: ESTRATÉGIA com largura total
    pdf.set_xy(14, start_y + 8.5)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(50, 60, 80)
    pdf.cell(182, 5.5, sanitizar_texto(f"ESTRATÉGIA: {estrategia}"), 0, 1)

    # Linha 3: Horizonte operacional
    pdf.set_xy(14, start_y + 15)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(182, 5, sanitizar_texto("Horizonte: Swing Trade / Position Mensal | Vencimento de Opções: 3ª Sexta-Feira"), 0, 1)

    pdf.set_y(start_y + 28)


    # Seção 1: Resumo Executivo da Tese
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 32, 67)
    pdf.cell(0, 7, "1. RESUMO EXECUTIVO E TESE MACRO/FUNDAMENTALISTA", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 4.5, sanitizar_texto(resumo_executivo))
    pdf.ln(3)

    # Seção 2: Parâmetros Operacionais (Tabela)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 32, 67)
    pdf.cell(0, 7, "2. PARÂMETROS OPERACIONAIS E RISCO/RETORNO", ln=True)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(225, 235, 248)
    pdf.set_text_color(20, 30, 50)
    pdf.cell(95, 6, "PARÂMETRO OPERACIONAL", 1, 0, "L", True)
    pdf.cell(95, 6, "VALOR ESTIMADO / NÍVEL TÉCNICO", 1, 1, "L", True)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(40, 40, 40)
    if parametros and isinstance(parametros, dict):
        for chave, valor in parametros.items():
            pdf.cell(95, 5.5, sanitizar_texto(str(chave)), 1, 0, "L")
            pdf.cell(95, 5.5, sanitizar_texto(str(valor)), 1, 1, "L")
    else:
        pdf.cell(190, 5.5, "Parâmetros não informados.", 1, 1, "C")
    pdf.ln(3)

    # Seção 3: Gregas da Opção (Modelo Black-Scholes)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 32, 67)
    pdf.cell(0, 7, "3. ANÁLISE DE GREGAS (MODELO BLACK-SCHOLES)", ln=True)

    gregas_dict = gregas or {}
    delta_val = gregas_dict.get("delta")
    gamma_val = gregas_dict.get("gamma")
    theta_val = gregas_dict.get("theta") or gregas_dict.get("theta_diario")
    vega_val = gregas_dict.get("vega") or gregas_dict.get("vega_1pct")

    if delta_val is not None:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(240, 240, 245)
        pdf.cell(47, 6, "DELTA", 1, 0, "C", True)
        pdf.cell(47, 6, "GAMMA", 1, 0, "C", True)
        pdf.cell(48, 6, "THETA (DIÁRIO)", 1, 0, "C", True)
        pdf.cell(48, 6, "VEGA (1% VOL)", 1, 1, "C", True)

        pdf.set_font("Helvetica", "", 8.5)
        pdf.cell(47, 5.5, str(delta_val), 1, 0, "C")
        pdf.cell(47, 5.5, str(gamma_val), 1, 0, "C")
        pdf.cell(48, 5.5, str(theta_val), 1, 0, "C")
        pdf.cell(48, 5.5, str(vega_val), 1, 1, "C")
    else:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5.5, sanitizar_texto("Operação à vista ou veto de risco: sem gregas ativas na estrutura."), 0, 1, "L")
    pdf.ln(3)

    # Seção 4: Gestão de Risco & Parecer da Mesa
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 32, 67)
    pdf.cell(0, 7, "4. GESTÃO DE RISCO E PLANO DE CONTINGÊNCIA", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 4.5, sanitizar_texto(gestao_risco))
    pdf.ln(4)

    # Seção 5: Disclaimer Regulatório CVM nº 20/2021
    pdf.set_fill_color(248, 249, 250)
    pdf.set_draw_color(210, 215, 220)
    y_disc = pdf.get_y()
    pdf.rect(10, y_disc, 190, 24, "FD")
    pdf.set_xy(12, y_disc + 2)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(100, 30, 30)
    pdf.cell(0, 3.5, "5. AVISO LEGAL E REGULATÓRIO - RESOLUÇÃO CVM Nº 20/2021", ln=True)

    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 6.2)
    pdf.set_text_color(90, 90, 90)
    disclaimer = (
        "Este relatório foi elaborado com fins exclusivamente informativos pela Mesa de Operações e não constitui oferta "
        "pública de valores mobiliários. Operações em renda variável e derivativos (opções) envolvem risco substancial "
        "de perda de capital e podem não ser adequadas a todos os perfis de investidor. A rentabilidade obtida no passado "
        "não representa garantia de rentabilidade futura. Todas as tomadas de decisão são de responsabilidade exclusiva "
        "do investidor."
    )
    pdf.multi_cell(186, 3.2, sanitizar_texto(disclaimer))

    try:
        pdf.output(caminho_saida)
    except (OSError, PermissionError):
        dir_tmp = "/tmp/output" if os.path.exists("/tmp") else os.path.join(os.path.expanduser("~"), "tmp_mesa")
        os.makedirs(dir_tmp, exist_ok=True)
        caminho_saida = os.path.join(dir_tmp, os.path.basename(caminho_saida))
        pdf.output(caminho_saida)

    return os.path.abspath(caminho_saida)
