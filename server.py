"""
Servidor Web Executivo FastAPI para a Mesa de Operações B3.
Permite iniciar a esteira dos 6 agentes via navegador, acompanhar o status em tempo real,
visualizar gráficos dinâmicos de Candlesticks e Payoff de Opções, e baixar relatórios em PDF.
"""

import sys
import os
import re
import glob
import threading
import queue
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from typing import Dict, Any, List, Optional
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

# Ajuste de compatibilidade para Google Gemini
google_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
if google_key:
    os.environ["GOOGLE_API_KEY"] = google_key
    os.environ["GEMINI_API_KEY"] = google_key

# Configurações de Ambiente e Segurança
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
AMBIENTE_NOME = "DEMO_CLOUD_VERCEL" if IS_VERCEL else "OPERACIONAL_LOCAL"
MESA_API_KEY = (os.getenv("MESA_API_KEY") or "").strip()

# Lock de concorrência para proteção de estado compartilhado
estado_lock = threading.Lock()

# Cache em memória para requisições de cotação técnica (proteção contra DoS e estouro de cota BRAPI)
cache_dados_tecnicos: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SEGUNDOS = 120.0

try:
    from crew import MesaOperacoesCrew
except ImportError:
    MesaOperacoesCrew = None
from tools.pdf_generator import gerar_pdf_relatorio
from tools.risk_gate import (
    auditar_gate_de_risco_programatico,
    aplicar_contingencia_de_veto,
    extrair_decisao_risco_autentica,
    extrair_rr_efetivo
)
from tools.brapi_tools import consultar_dados_tecnicos_e_medias, CESTA_LIQUIDEZ_B3
from tools.options_tools import calcular_payoff_trava_alta
from schemas.output_models import DecisaoRiscoModel


app = FastAPI(title="Mesa de Operações B3 - Dashboard Executivo com Gráficos")

# Estado global da execução
estado_execucao = {
    "status": "ocioso",  # 'ocioso', 'executando', 'concluido', 'erro'
    "etapa_atual": 0,    # 0 a 6
    "progresso_pct": 0,  # 0 a 100
    "agente_ativo": "",
    "logs": [],
    "resultado": None,
    "graficos": {
        "candles": [],
        "payoff": [],
        "suporte": 0.0,
        "resistencia": 0.0,
        "entrada": 0.0,
        "stop": 0.0,
        "alvo": 0.0,
    },
    "pdf_path": None,
    "erro": None,
    "is_demo": IS_VERCEL,
    "ambiente": AMBIENTE_NOME,
    "aviso_ambiente": (
        "Ambiente de Demonstração Institucional (Vercel Serverless). "
        "A esteira completa com 6 agentes autônomos e chamadas ilimitadas em tempo real "
        "roda no servidor local da Mesa (iniciar_mesa.bat)."
        if IS_VERCEL else
        "Servidor Operacional Local com IA Multiagente e Conexão em Tempo Real."
    )
}


def adicionar_log(mensagem: str):
    with estado_lock:
        timestamp = time.strftime("%H:%M:%S")
        entrada = f"[{timestamp}] {mensagem}"
        estado_execucao["logs"].append(entrada)
        if len(estado_execucao["logs"]) > 300:
            estado_execucao["logs"].pop(0)


def carregar_ultimo_resultado_salvo():
    global estado_execucao
    caminho_md = "output/relatorio_recomendacao.md"
    if not os.path.exists(caminho_md):
        return
    try:
        import json
        with open(caminho_md, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
        if not conteudo:
            return

        if conteudo.startswith("{") and conteudo.endswith("}"):
            data = json.loads(conteudo)
        else:
            import re
            m = re.search(r"\{.*\}", conteudo, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
            else:
                return

        ativo = data.get("ativo_alvo", "PETR4")
        params_lista = data.get("parametros_operacionais", [])
        gregas_dict = data.get("gregas", {})

        arquivos_pdf = glob.glob("output/*.pdf")
        ultimo_pdf = max(arquivos_pdf, key=os.path.getmtime) if arquivos_pdf else None

        graficos = {
            "candles": [],
            "payoff": [],
            "suporte": 0.0,
            "resistencia": 0.0,
            "entrada": 0.0,
            "stop": 0.0,
            "alvo": 0.0,
        }

        try:
            fn_tecnica = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
            dados_tecnicos = fn_tecnica(ativo)
            candles_raw = dados_tecnicos.get("candles_recentes", []) if isinstance(dados_tecnicos, dict) else []
            import datetime as dt
            candles_fmt = []
            for c in candles_raw:
                c_item = dict(c)
                d_val = c.get("date")
                if isinstance(d_val, (int, float)):
                    ms = d_val if d_val > 1e11 else d_val
                    c_item["date_str"] = dt.datetime.fromtimestamp(ms).strftime("%d/%m")
                else:
                    c_item["date_str"] = str(d_val)
                candles_fmt.append(c_item)

            graficos["candles"] = candles_fmt
            graficos["suporte"] = dados_tecnicos.get("suporte_recente", 46.80)
            graficos["resistencia"] = dados_tecnicos.get("resistencia_recente", 50.43)
            graficos["preco_atual"] = dados_tecnicos.get("preco_atual", 48.09)
        except Exception as err:
            print(f"Aviso dados tecnicos: {err}")

        try:
            fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
            payoff_data = fn_payoff(
                strike_compra=48.50,
                premio_pago_compra=1.45,
                strike_venda=50.50,
                premio_recebido_venda=0.60
            )
            graficos["payoff"] = payoff_data.get("pontos_curva_payoff", [])
            graficos["strike_compra"] = 48.50
            graficos["strike_venda"] = 50.50
            graficos["breakeven"] = payoff_data.get("breakeven", 49.35)
        except Exception as err:
            print(f"Aviso payoff: {err}")

        from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100
        estado_execucao["ranking"] = gerar_ranking_completo_ibrx100()

        estado_execucao["resultado"] = {
            "titulo": data.get("titulo", "Mesa de Operações B3"),
            "ativo": ativo,
            "estrategia": data.get("operacao_recomendada", "Operação em Ações/Opções"),
            "resumo_executivo": data.get("resumo_executivo", ""),
            "parametros": params_lista,
            "gregas": gregas_dict,
            "status_decisao": data.get("status_decisao", "APROVADO_PRINCIPAL"),
            "gestao_risco": data.get("gestao_risco_e_saida", ""),
            "disclaimer_cvm": data.get("disclaimer_cvm", "Resolução CVM nº 20/2021."),
            "data": data.get("data_geracao", time.strftime("%d/%m/%Y")),
        }
        estado_execucao["graficos"] = graficos
        estado_execucao["pdf_path"] = ultimo_pdf
        estado_execucao["status"] = "concluido"
        adicionar_log(f"Última recomendação carregada: {ativo} ({data.get('operacao_recomendada', '')})")
    except Exception as e:
        print(f"Aviso ao carregar relatório prévio: {e}")


# Carrega relatório prévio para o dashboard iniciar preenchido
carregar_ultimo_resultado_salvo()




def executar_esteira_background():
    global estado_execucao
    try:
        estado_execucao["status"] = "executando"
        estado_execucao["etapa_atual"] = 1
        estado_execucao["agente_ativo"] = "Analista Macro"
        estado_execucao["progresso_pct"] = 15
        estado_execucao["erro"] = None
        estado_execucao["logs"] = []
        estado_execucao["resultado"] = None
        estado_execucao["pdf_path"] = None

        adicionar_log("🚀 Iniciando esteira autônoma da Mesa de Operações B3...")
        adicionar_log("🌐 [Fase 1/6] Analista Macro varrendo notícias, Selic, Fed e pré-selecionando ativos...")

        if MesaOperacoesCrew is None or IS_VERCEL:
            adicionar_log("ℹ️ [MODO DEMONSTRAÇÃO VERCEL] Apresentando pipeline executivo e caso auditado...")
            time.sleep(0.3)
            adicionar_log("🌐 [DEMO - Fase 1/6] Analista Macro: Apresentação da diretriz macroeconômica e juros Selic.")
            estado_execucao["etapa_atual"] = 2
            estado_execucao["agente_ativo"] = "Fundamentalista"
            estado_execucao["progresso_pct"] = 35
            time.sleep(0.3)
            adicionar_log("📊 [DEMO - Fase 2/6] Analista Fundamentalista: Demonstração da triagem de múltiplos na Cesta B3.")
            estado_execucao["etapa_atual"] = 3
            estado_execucao["agente_ativo"] = "Analista Técnico"
            estado_execucao["progresso_pct"] = 55
            time.sleep(0.3)
            adicionar_log("📈 [DEMO - Fase 3/6] Analista Técnico CNPI-T: Médias SMA20/50 e RSI-14 de referência.")
            estado_execucao["etapa_atual"] = 4
            estado_execucao["agente_ativo"] = "Estrategista de Opções"
            estado_execucao["progresso_pct"] = 75
            time.sleep(0.3)
            adicionar_log("⚡ [DEMO - Fase 4/6] Estrategista de Opções: Modelagem de trava e gregas Black-Scholes.")
            estado_execucao["etapa_atual"] = 5
            estado_execucao["agente_ativo"] = "Coordenador de Risco"
            estado_execucao["progresso_pct"] = 90
            time.sleep(0.3)
            adicionar_log("🛡️ [DEMO - Fase 5/6] Gate de Risco Programático: Sarrafo R/R 1.44 < 1.50 -> Veto institucional acionado.")
            estado_execucao["etapa_atual"] = 6
            estado_execucao["agente_ativo"] = "Research Publisher"
            estado_execucao["progresso_pct"] = 98

            from schemas.output_models import RelatorioExecutivoFinal, ItemParametro, GregasOpcoesModel
            relatorio = RelatorioExecutivoFinal(
                titulo="Parecer de Risco - Veto de Trava de Alta (PETR4) [DEMO ILUSTRATIVA]",
                ativo_alvo="PETR4",
                operacao_recomendada="Manutenção em Caixa / Veto Preventivo",
                resumo_executivo=(
                    "[DEMONSTRAÇÃO DE FLUXO INSTITUCIONAL] Caso de referência auditado da Cesta de Liquidez B3. "
                    "A estrutura de opções simulada apresentou relação Risco/Retorno de 1.44:1, "
                    "inferior ao piso regulamentar de 1.50:1, demonstrando a atuação do Veto Programático de Código. "
                    "Para análise autônoma ao vivo com os 6 agentes de IA, execute via 'iniciar_mesa.bat' no servidor local."
                ),
                status_decisao="REPROVADO_TOTAL",
                razao_risco_retorno_num=1.44,
                parametros_operacionais=[
                    ItemParametro(parametro="Ativo Objeto", valor="PETR4"),
                    ItemParametro(parametro="Ambiente", valor="Demonstração Cloud (Vercel)"),
                    ItemParametro(parametro="Estratégia", valor="Manutenção em Caixa"),
                    ItemParametro(parametro="Relação R/R Calculada", valor="1.44 : 1 (Abaixo de 1.50:1)"),
                    ItemParametro(parametro="Veredito do Gate", valor="VETADO NO RISCO"),
                ],
                gregas=GregasOpcoesModel(delta=0.0, gamma=0.0, theta=0.0, vega=0.0),
                gestao_risco_e_saida="Preservação total de capital. Aguardar expansão de spread para R/R > 1.8:1.",
                disclaimer_cvm="Relatório em conformidade com a Resolução CVM nº 20/2021. Demonstração de arquitetura."
            )
            resultado_crew = relatorio
        else:
            mesa = MesaOperacoesCrew()
            crew_inst = mesa.crew()

            def callback_tarefa(task_output):
                try:
                    desc = str(getattr(task_output, "description", "")).lower()
                    agent_name = str(getattr(task_output, "agent", "")).lower()
                    
                    if "macro" in desc or "macro" in agent_name:
                        estado_execucao["etapa_atual"] = 2
                        estado_execucao["agente_ativo"] = "Fundamentalista"
                        estado_execucao["progresso_pct"] = 35
                        adicionar_log("🌐 [Fase 1 Concluída] Analista Macro definiu a tese macroeconômica e pré-selecionou os candidatos.")
                        adicionar_log("📊 [Fase 2/6] Analista Fundamentalista auditando múltiplos e balanços via BRAPI...")
                    elif "fundamentalista" in desc or "múltiplos" in desc or "valuation" in desc:
                        estado_execucao["etapa_atual"] = 3
                        estado_execucao["agente_ativo"] = "Analista Técnico"
                        estado_execucao["progresso_pct"] = 55
                        adicionar_log("📊 [Fase 2 Concluída] Analista Fundamentalista elegeu o melhor ativo com base em valuation e solvência.")
                        adicionar_log("📈 [Fase 3/6] Analista Técnico CNPI-T iniciando análise gráfica, médias (SMA20/50), RSI-14 e checklist Dow...")
                    elif "timing" in desc or "gráfico" in desc or "técnico" in agent_name or "analise" in desc:
                        estado_execucao["etapa_atual"] = 4
                        estado_execucao["agente_ativo"] = "Estrategista de Opções"
                        estado_execucao["progresso_pct"] = 75
                        adicionar_log("📈 [Fase 3 Concluída] Analista Técnico CNPI-T validou timing, suporte/resistência e stop loss técnico.")
                        adicionar_log("⚡ [Fase 4/6] Estrategista Sênior formulando estruturas de opções (Travas/Venda Coberta) e gregas Black-Scholes...")
                    elif "estruturar" in desc or "opções" in desc or "estrategista" in agent_name or "derivativos" in desc:
                        estado_execucao["etapa_atual"] = 5
                        estado_execucao["agente_ativo"] = "Coordenador de Risco"
                        estado_execucao["progresso_pct"] = 90
                        adicionar_log("⚡ [Fase 4 Concluída] Estrategista formulou propostas com gregas e vencimentos mensais.")
                        adicionar_log("🛡️ [Fase 5/6] Coordenador de Risco auditando relação Risco/Retorno e governança...")
                    elif "risco" in desc or "auditar" in desc or "risco" in agent_name:
                        estado_execucao["etapa_atual"] = 6
                        estado_execucao["agente_ativo"] = "Research Publisher"
                        estado_execucao["progresso_pct"] = 98
                        adicionar_log("🛡️ [Fase 5 Concluída] Coordenador de Risco deliberou sobre a operação.")
                        adicionar_log("📝 [Fase 6/6] Research Publisher redigindo relatório executivo formal e disclaimer CVM nº 20/2021...")
                    else:
                        adicionar_log(f"✅ Etapa concluída por: {getattr(task_output, 'agent', 'Especialista')}")
                except Exception as e_cb:
                    print(f"Erro no task_callback: {e_cb}")

            def callback_passo(step_output):
                try:
                    tool_name = getattr(step_output, "tool", None)
                    if tool_name:
                        adicionar_log(f"⚙️ Consultando mercado: {tool_name}...")
                except Exception:
                    pass

            crew_inst.task_callback = callback_tarefa
            crew_inst.step_callback = callback_passo

            adicionar_log("Disparando execução autônoma multiagente com verificação em tempo real...")
            resultado_crew = crew_inst.kickoff()

            # Extração dos dados do relatório
            relatorio = None
            if hasattr(resultado_crew, "pydantic") and resultado_crew.pydantic:
                relatorio = resultado_crew.pydantic
            else:
                relatorio = resultado_crew

        adicionar_log("🔍 Submetendo resultado ao Gate de Risco Programático de Código...")

        # Coleta do ativo e parâmetros técnicos
        ativo = getattr(relatorio, "ativo_alvo", "ITUB4")
        titulo = getattr(relatorio, "titulo", f"Recomendação Mesa de Operações - {ativo}")
        estrategia = getattr(relatorio, "operacao_recomendada", "Operação Analisada")
        resumo = getattr(relatorio, "resumo_executivo", str(resultado_crew))
        params_raw = getattr(relatorio, "parametros_operacionais", [])

        # Identifica a relação Risco/Retorno numérica declarada nos parâmetros
        rr_declarado = 0.0
        entrada_num, alvo_num, stop_num = 0.0, 0.0, 0.0

        params_dict = {}
        params_lista = []
        if isinstance(params_raw, list):
            for item in params_raw:
                p_nome = getattr(item, "parametro", str(item))
                p_val = getattr(item, "valor", "")
                params_dict[str(p_nome)] = str(p_val)
                params_lista.append({"parametro": str(p_nome), "valor": str(p_val)})
                if "r/r" in p_nome.lower() or "risco/retorno" in p_nome.lower():
                    try:
                        part = p_val.split(":")[0].replace("R$", "").replace(",", ".").strip()
                        rr_declarado = float(part)
                    except Exception:
                        pass
        elif isinstance(params_raw, dict):
            params_dict = params_raw
            for k, v in params_raw.items():
                params_lista.append({"parametro": str(k), "valor": str(v)})

        # Aplicação Estrita do Gate de Risco em Código (Audit Items A & B)
        decisao_risco_autentica = extrair_decisao_risco_autentica(resultado_crew, relatorio)
        rr_efetivo = extrair_rr_efetivo(relatorio, decisao_risco_autentica)

        aprovado_gate, status_gate, motivo_gate = auditar_gate_de_risco_programatico(
            decisao_risco_autentica,
            rr_efetivo
        )

        if not aprovado_gate:
            adicionar_log(f"🛡️ GATE DE RISCO ATIVADO: {motivo_gate}")
            relatorio = aplicar_contingencia_de_veto(relatorio, motivo_gate)
            status_final = "REPROVADO_TOTAL"
            estrategia = relatorio.operacao_recomendada
            params_lista = [{"parametro": p.parametro, "valor": p.valor} for p in relatorio.parametros_operacionais]
            params_dict = {p.parametro: p.valor for p in relatorio.parametros_operacionais}
        else:
            status_final = status_gate
            relatorio.status_decisao = status_final
            relatorio.razao_risco_retorno_num = rr_efetivo
            adicionar_log(f"✅ Operação validada e aprovada pelo Gate de Risco ({status_final} | R/R: {rr_efetivo:.2f}:1)!")


        # Coleta de Dados Reais de Gráficos (Candlesticks da BRAPI e Payoff)
        adicionar_log(f"📈 Carregando dados técnicos reais e histórico de candles para {ativo}...")
        try:
            fn_tecnica = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
            dados_tecnicos = fn_tecnica(ativo)
        except Exception as e_tec:
            dados_tecnicos = {}
            adicionar_log(f"Aviso dados técnicos: {str(e_tec)}")

        candles = dados_tecnicos.get("candles_recentes", []) if isinstance(dados_tecnicos, dict) else []
        suporte_val = dados_tecnicos.get("suporte_recente", 0.0) if isinstance(dados_tecnicos, dict) else 0.0
        resistencia_val = dados_tecnicos.get("resistencia_recente", 0.0) if isinstance(dados_tecnicos, dict) else 0.0

        # Curva de Payoff de Opções
        spot_atual = dados_tecnicos.get("preco_atual", 48.0) if isinstance(dados_tecnicos, dict) and dados_tecnicos.get("preco_atual") else 48.0
        k_compra = round(spot_atual * 0.98, 1)
        k_venda = round(spot_atual * 1.04, 1)
        try:
            fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
            payoff_data = fn_payoff(
                strike_compra=k_compra,
                premio_pago_compra=1.60,
                strike_venda=k_venda,
                premio_recebido_venda=0.50
            )
        except Exception as e_pay:
            payoff_data = {}
            adicionar_log(f"Aviso cálculo payoff: {str(e_pay)}")
        pontos_payoff = payoff_data.get("pontos_curva_payoff", []) if isinstance(payoff_data, dict) else []

        estado_execucao["graficos"] = {
            "ativo": ativo,
            "candles": candles,
            "payoff": pontos_payoff,
            "suporte": suporte_val,
            "resistencia": resistencia_val,
            "preco_atual": spot_atual,
            "strike_compra": k_compra,
            "strike_venda": k_venda,
            "breakeven": payoff_data.get("breakeven", round(k_compra + 1.10, 2)) if isinstance(payoff_data, dict) else 0.0
        }

        # Extração de Gregas
        gregas_model = getattr(relatorio, "gregas", None)
        gregas_dict = {}
        if gregas_model:
            gregas_dict = {
                "delta": getattr(gregas_model, "delta", 0.0),
                "gamma": getattr(gregas_model, "gamma", 0.0),
                "theta": getattr(gregas_model, "theta", 0.0),
                "vega": getattr(gregas_model, "vega", 0.0),
            }

        # Geração do Relatório PDF com Status Dinâmico Real
        data_str = time.strftime("%Y%m%d_%H%M%S")
        if os.getenv("VERCEL") or not os.access(".", os.W_OK):
            pasta_dest = "/tmp/output"
        else:
            pasta_dest = "output"
        try:
            os.makedirs(pasta_dest, exist_ok=True)
        except Exception:
            pasta_dest = "/tmp"
        pdf_path = os.path.join(pasta_dest, f"relatorio_operacao_{data_str}.pdf")

        arquivo_gerado = gerar_pdf_relatorio(
            titulo=titulo,
            ativo=ativo,
            estrategia=estrategia,
            resumo_executivo=getattr(relatorio, "resumo_executivo", resumo),
            parametros=params_dict,
            gregas=gregas_dict,
            gestao_risco=getattr(relatorio, "gestao_risco_e_saida", "Gestão de risco da mesa."),
            status=status_final,
            caminho_saida=pdf_path
        )

        estado_execucao["resultado"] = {
            "titulo": titulo,
            "ativo": ativo,
            "estrategia": estrategia,
            "resumo_executivo": getattr(relatorio, "resumo_executivo", resumo),
            "parametros": params_lista,
            "gregas": gregas_dict,
            "status_decisao": status_final,
            "gestao_risco": getattr(relatorio, "gestao_risco_e_saida", "Gestão de risco da mesa."),
            "disclaimer_cvm": getattr(relatorio, "disclaimer_cvm", "Resolução CVM nº 20/2021."),
            "data": time.strftime("%d/%m/%Y %H:%M"),
        }
        estado_execucao["pdf_path"] = arquivo_gerado
        estado_execucao["etapa_atual"] = 6
        estado_execucao["progresso_pct"] = 100
        estado_execucao["status"] = "concluido"
        adicionar_log(f"📄 Relatório PDF oficial gerado com sucesso: {arquivo_gerado}")

    except Exception as e:
        estado_execucao["status"] = "erro"
        estado_execucao["erro"] = str(e)
        adicionar_log(f"❌ Erro na execução da esteira: {str(e)}")


@app.get("/api/status")
def obter_status():
    with estado_lock:
        return JSONResponse(dict(estado_execucao))


@app.get("/api/ranking")
def obter_ranking():
    from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100, obter_estatisticas_funil
    ranking = gerar_ranking_completo_ibrx100()
    stats = obter_estatisticas_funil(ranking)
    return JSONResponse({
        "status": "sucesso",
        "tipo_base": "estatica_referencia",
        "nota_auditoria": "Dataset estático do IBrX-100 para triagem offline rápida. A esteira em tempo real valida e consome ativos prioritários da CESTA_LIQUIDEZ_B3.",
        "total": len(ranking),
        "estatisticas": stats,
        "ranking": ranking
    })


@app.get("/api/ativo/{ticker}")
def obter_dados_ativo(ticker: str):
    ticker_clean = ticker.upper().strip()
    
    # Validação e sanitização estrita do formato do ticker (B3 padrão: ex PETR4, VALE3)
    if not re.match(r"^[A-Z0-9]{4,6}$", ticker_clean):
        return JSONResponse(
            {
                "status": "erro",
                "mensagem": "Formato de ticker inválido. Use formato padrão B3 (ex: PETR4, VALE3)."
            },
            status_code=400
        )

    # Proteção de cota e DoS: apenas ativos aprovados na cesta de alta liquidez são consultados na API pública
    if ticker_clean not in CESTA_LIQUIDEZ_B3:
        return JSONResponse(
            {
                "status": "erro",
                "mensagem": f"Ticker '{ticker_clean}' não autorizado na API pública. Ativos disponíveis na cesta de liquidez: {', '.join(CESTA_LIQUIDEZ_B3)}",
                "ativos_permitidos": list(CESTA_LIQUIDEZ_B3)
            },
            status_code=403
        )

    # Verificação de Cache em Memória com TTL de 120s
    agora = time.time()
    with estado_lock:
        if ticker_clean in cache_dados_tecnicos:
            item_cache = cache_dados_tecnicos[ticker_clean]
            if agora - item_cache["timestamp"] < CACHE_TTL_SEGUNDOS:
                dados_em_cache = dict(item_cache["dados"])
                dados_em_cache["origem"] = "cache_memoria"
                dados_em_cache["ttl_restante"] = int(CACHE_TTL_SEGUNDOS - (agora - item_cache["timestamp"]))
                return JSONResponse(dados_em_cache)

    try:
        fn_tecnica = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
        dados = fn_tecnica(ticker_clean)
        candles_raw = dados.get("candles_recentes", []) if isinstance(dados, dict) else []
        import datetime as dt
        candles_fmt = []
        for c in candles_raw:
            c_item = dict(c)
            d_val = c.get("date")
            if isinstance(d_val, (int, float)):
                ms = d_val if d_val > 1e11 else d_val
                if d_val < 2e9:
                    ms = d_val
                c_item["date_str"] = dt.datetime.fromtimestamp(ms).strftime("%d/%m")
            else:
                c_item["date_str"] = str(d_val)
            candles_fmt.append(c_item)

        preco_atual = dados.get("preco_atual", 50.0)
        suporte = dados.get("suporte_recente", round(preco_atual * 0.96, 2))
        resistencia = dados.get("resistencia_recente", round(preco_atual * 1.05, 2))

        strike_compra = round(preco_atual * 1.01, 2)
        strike_venda = round(preco_atual * 1.05, 2)
        largura = strike_venda - strike_compra
        debito = round(largura * 0.38, 2)

        fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
        payoff_data = fn_payoff(
            strike_compra=strike_compra,
            premio_pago_compra=debito + 0.30,
            strike_venda=strike_venda,
            premio_recebido_venda=0.30
        )

        resultado = {
            "status": "sucesso",
            "ativo": ticker_clean,
            "origem": "api_tempo_real",
            "preco_atual": preco_atual,
            "suporte": suporte,
            "resistencia": resistencia,
            "sma20": dados.get("sma20"),
            "sma50": dados.get("sma50"),
            "volatilidade_anualizada_pct": dados.get("volatilidade_anualizada_pct"),
            "rsi_14": dados.get("rsi_14"),
            "candles": candles_fmt,
            "strike_compra": strike_compra,
            "strike_venda": strike_venda,
            "debito": debito,
            "breakeven": payoff_data.get("breakeven", strike_compra + debito),
            "payoff": payoff_data.get("pontos_curva_payoff", [])
        }

        # Armazenar no cache com proteção de concorrência
        with estado_lock:
            cache_dados_tecnicos[ticker_clean] = {
                "timestamp": agora,
                "dados": resultado
            }

        return JSONResponse(resultado)
    except Exception as e:
        return JSONResponse({"status": "erro", "mensagem": str(e), "ativo": ticker_clean}, status_code=500)


@app.post("/api/iniciar")
def iniciar_processamento(
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    key: Optional[str] = Query(None)
):
    # Proteção de autenticação: Se MESA_API_KEY estiver configurada, exige chave válida
    if MESA_API_KEY:
        chave_fornecida = (x_api_key or key or "").strip()
        if chave_fornecida != MESA_API_KEY:
            return JSONResponse(
                {
                    "status": "erro",
                    "mensagem": "Acesso não autorizado. Chave de API MESA_API_KEY ausente ou inválida."
                },
                status_code=401
            )

    with estado_lock:
        if estado_execucao["status"] == "executando":
            return JSONResponse({"status": "aviso", "mensagem": "A esteira já está em execução."})
        estado_execucao["status"] = "executando"

    if IS_VERCEL:
        # Em ambiente Serverless (Vercel), executa o fluxo demonstrativo transparente
        executar_esteira_background()
        return JSONResponse({
            "status": "concluido",
            "ambiente": AMBIENTE_NOME,
            "is_demo": True,
            "mensagem": "Demonstração institucional executada com sucesso no Vercel Serverless."
        })
    else:
        thread = threading.Thread(target=executar_esteira_background)
        thread.daemon = True
        thread.start()
        return JSONResponse({
            "status": "iniciado",
            "ambiente": AMBIENTE_NOME,
            "is_demo": False,
            "mensagem": "Esteira multiagente com IA iniciada com sucesso em segundo plano."
        })


@app.get("/api/download/pdf")
def baixar_pdf():
    pdf_path = estado_execucao.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path)
        )

    # Fallback: procura o último PDF gerado em pastas graváveis
    pastas = ["/tmp/output", "/tmp", "output"]
    for pasta in pastas:
        arquivos_pdf = glob.glob(f"{pasta}/*.pdf")
        if arquivos_pdf:
            ultimo_pdf = max(arquivos_pdf, key=os.path.getmtime)
            return FileResponse(
                ultimo_pdf,
                media_type="application/pdf",
                filename=os.path.basename(ultimo_pdf)
            )

    return JSONResponse({"erro": "Nenhum relatório PDF disponível no momento."}, status_code=404)


@app.get("/apresentacao")
@app.get("/apresentacao.html")
def pagina_apresentacao():
    dir_base = os.path.dirname(os.path.abspath(__file__))
    caminho_apresentacao = os.path.join(dir_base, "static", "apresentacao.html")
    if os.path.exists(caminho_apresentacao):
        return FileResponse(caminho_apresentacao, media_type="text/html")
    return JSONResponse({"erro": "Página de apresentação não encontrada."}, status_code=404)


@app.get("/midia/{nome_arquivo:path}")
@app.get("/static/midia/{nome_arquivo:path}")
def servir_midia_direta(nome_arquivo: str):
    dir_base = os.path.dirname(os.path.abspath(__file__))
    pastas_busca = [
        os.path.join(dir_base, "static", "midia"),
        os.path.join(dir_base, "Midia"),
        "static/midia",
        "Midia"
    ]
    for pasta in pastas_busca:
        caminho = os.path.join(pasta, nome_arquivo)
        if os.path.exists(caminho):
            ext = os.path.splitext(nome_arquivo)[1].lower()
            tipo_mime = "video/mp4" if ext == ".mp4" else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "application/octet-stream")
            return FileResponse(caminho, media_type=tipo_mime)
    return JSONResponse({"erro": f"Arquivo de mídia '{nome_arquivo}' não encontrado."}, status_code=404)


# Servir arquivos estáticos (HTML/CSS/JS)
dir_static = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(dir_static, exist_ok=True)
app.mount("/", StaticFiles(directory=dir_static, html=True), name="static")


def encontrar_porta_livre(porta_base=8000):
    import socket
    for p in range(porta_base, porta_base + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return porta_base


def abrir_navegador(porta):
    time.sleep(1.8)
    try:
        import webbrowser
        webbrowser.open(f"http://localhost:{porta}")
    except Exception:
        pass
    try:
        print("\n" + "=" * 60)
        print(f" [PAINEL VISUAL ATIVO] Acesse: http://localhost:{porta}")
        print(" [NAVEGADOR] Abrindo dashboard automaticamente no navegador padrao...")
        print("=" * 60 + "\n")
    except Exception:
        pass


def run_server():
    import uvicorn
    porta = encontrar_porta_livre(8000)
    threading.Thread(target=abrir_navegador, args=(porta,), daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=porta)


if __name__ == "__main__":
    run_server()


