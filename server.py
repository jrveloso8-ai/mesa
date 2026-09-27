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
    extrair_rr_efetivo,
    copiar_campos_estrategia_aprovada,
    extrair_preco_atual_medido,
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
    caminhos = [
        "output/resultado_pos_gate.json",
        "/tmp/output/resultado_pos_gate.json"
    ]
    dados = None
    for c in caminhos:
        if os.path.exists(c):
            try:
                import json
                with open(c, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                break
            except Exception:
                continue

    if not dados:
        from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100
        estado_execucao["ranking"] = gerar_ranking_completo_ibrx100()
        fallback = {
            "status_final": "REPROVADO_TOTAL",
            "motivo_veto": "Nenhuma execução registrada",
            "ticker": "N/A"
        }
        estado_execucao["resultado"] = {
            "status_final": "REPROVADO_TOTAL",
            "motivo_veto": "Nenhuma execução registrada",
            "ticker": "N/A",
            "status_decisao": "REPROVADO_TOTAL",
            "titulo": "Nenhuma execução registrada",
            "ativo": "N/A",
            "estrategia": "Nenhuma operação ativa",
            "resumo_executivo": "Nenhuma execução auditada registrada no sistema.",
            "parametros": [],
            "gregas": {},
            "gestao_risco": "Manter 100% em caixa / CDI.",
            "disclaimer_cvm": "Resolução CVM nº 20/2021.",
            "data": time.strftime("%d/%m/%Y %H:%M:%S")
        }
        return fallback

    try:
        status_final = dados.get("status_final", "REPROVADO_TOTAL")
        motivo_veto = dados.get("motivo_veto")
        ticker = dados.get("ticker", "N/A")
        timestamp = dados.get("timestamp", time.strftime("%d/%m/%Y %H:%M:%S"))
        data = dados.get("relatorio_completo", {})
        if not isinstance(data, dict):
            data = {}

        ativo = ticker if ticker and ticker != "N/A" else data.get("ativo_alvo", "N/A")
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
            if ativo and ativo != "N/A":
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
                graficos["suporte"] = dados_tecnicos.get("suporte_recente") if isinstance(dados_tecnicos, dict) else None
                graficos["resistencia"] = dados_tecnicos.get("resistencia_recente") if isinstance(dados_tecnicos, dict) else None
                graficos["preco_atual"] = dados_tecnicos.get("preco_atual") if isinstance(dados_tecnicos, dict) else None
        except Exception as err:
            print(f"Aviso dados tecnicos: {err}")

        # Gráfico de payoff: só quando a operação APROVADA pelo gate for trava de alta, com os strikes e prêmios da proposta
        is_aprovado = (status_final == "APROVADO")
        s_compra = data.get("strike_compra")
        s_venda = data.get("strike_venda")
        p_compra = data.get("premio_compra")
        p_venda = data.get("premio_venda")

        if is_aprovado and s_compra is not None and s_venda is not None and p_compra is not None and p_venda is not None:
            try:
                fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
                payoff_data = fn_payoff(
                    strike_compra=float(s_compra),
                    premio_pago_compra=float(p_compra),
                    strike_venda=float(s_venda),
                    premio_recebido_venda=float(p_venda)
                )
                if isinstance(payoff_data, dict) and payoff_data.get("status") == "sucesso":
                    graficos["payoff"] = payoff_data.get("pontos_curva_payoff", [])
                    graficos["strike_compra"] = float(s_compra)
                    graficos["strike_venda"] = float(s_venda)
                    graficos["breakeven"] = payoff_data.get("breakeven")
                    graficos["mensagem_payoff"] = ""
                else:
                    graficos["payoff"] = []
                    graficos["mensagem_payoff"] = "Sem estrutura de opções aprovada"
            except Exception as err:
                graficos["payoff"] = []
                graficos["mensagem_payoff"] = "Sem estrutura de opções aprovada"
        else:
            graficos["payoff"] = []
            graficos["mensagem_payoff"] = "Sem estrutura de opções aprovada"

        from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100
        estado_execucao["ranking"] = gerar_ranking_completo_ibrx100()

        estado_execucao["resultado"] = {
            "status_final": status_final,
            "motivo_veto": motivo_veto,
            "ticker": ticker,
            "titulo": data.get("titulo", f"Mesa de Operações B3 - {ticker}"),
            "ativo": ativo,
            "estrategia": data.get("operacao_recomendada", "Operação em Ações/Opções"),
            "resumo_executivo": data.get("resumo_executivo", ""),
            "parametros": params_lista,
            "gregas": gregas_dict,
            "status_decisao": status_final,
            "gestao_risco": data.get("gestao_risco_e_saida", ""),
            "disclaimer_cvm": data.get("disclaimer_cvm", "Resolução CVM nº 20/2021."),
            "data": timestamp,
        }
        estado_execucao["graficos"] = graficos
        estado_execucao["pdf_path"] = ultimo_pdf
        estado_execucao["status"] = "concluido"
        adicionar_log(f"Última recomendação pós-gate carregada: {ativo} (Status: {status_final})")
        return dados
    except Exception as e:
        print(f"Aviso ao carregar relatório pós-gate: {e}")
        return dados


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

            # Sobrescreve data_geracao em código com a data/hora exata da execução
            data_execucao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            if hasattr(relatorio, "data_geracao"):
                relatorio.data_geracao = data_execucao

        adicionar_log("🔍 Submetendo resultado ao Gate de Risco Programático de Código...")

        # Coleta do ativo e parâmetros técnicos
        ativo = getattr(relatorio, "ativo_alvo", "ITUB4")
        titulo = getattr(relatorio, "titulo", f"Recomendação Mesa de Operações - {ativo}")
        estrategia = getattr(relatorio, "operacao_recomendada", "Operação Analisada")
        resumo = getattr(relatorio, "resumo_executivo", str(resultado_crew))

        # Aplicação Estrita do Gate de Risco em Código (Audit Items A, B & V0-02b)
        decisao_risco_autentica = extrair_decisao_risco_autentica(resultado_crew, relatorio)
        relatorio = copiar_campos_estrategia_aprovada(resultado_crew, relatorio, decisao_risco_autentica)
        preco_medido = extrair_preco_atual_medido(resultado_crew, ticker=getattr(relatorio, "ativo_alvo", None))

        rr_efetivo = extrair_rr_efetivo(relatorio, decisao_risco_autentica)
        rr_declarado = getattr(decisao_risco_autentica, "razao_risco_retorno_auditada", 0.0) or getattr(relatorio, "razao_risco_retorno_num", 0.0)

        aprovado_gate, status_gate, motivo_gate = auditar_gate_de_risco_programatico(
            decisao_risco=decisao_risco_autentica,
            razao_risco_retorno=rr_efetivo,
            relatorio=relatorio,
            rr_declarado=rr_declarado,
            preco_atual_medido=preco_medido,
            origem_premios=getattr(relatorio, "origem_premios", None),
        )

        params_dict = {}
        params_lista = []

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

            # Montagem priorizando campos float tipados
            if getattr(relatorio, "preco_entrada", None) is not None:
                params_dict["Preço de Entrada"] = f"R$ {relatorio.preco_entrada:.2f}"
            if getattr(relatorio, "preco_alvo", None) is not None:
                params_dict["Alvo de Lucro"] = f"R$ {relatorio.preco_alvo:.2f}"
            if getattr(relatorio, "preco_stop", None) is not None:
                params_dict["Stop Loss"] = f"R$ {relatorio.preco_stop:.2f}"
            if getattr(relatorio, "strike_compra", None) is not None:
                params_dict["Strike Compra"] = f"R$ {relatorio.strike_compra:.2f}"
            if getattr(relatorio, "strike_venda", None) is not None:
                params_dict["Strike Venda"] = f"R$ {relatorio.strike_venda:.2f}"
            if getattr(relatorio, "premio_compra", None) is not None:
                params_dict["Prêmio Compra"] = f"R$ {relatorio.premio_compra:.2f}"
            if getattr(relatorio, "premio_venda", None) is not None:
                params_dict["Prêmio Venda"] = f"R$ {relatorio.premio_venda:.2f}"
            if getattr(relatorio, "razao_risco_retorno_num", None) is not None and relatorio.razao_risco_retorno_num > 0:
                params_dict["Relação Risco/Retorno"] = f"{relatorio.razao_risco_retorno_num:.2f} : 1"

            params_raw = getattr(relatorio, "parametros_operacionais", [])
            if isinstance(params_raw, list):
                for item in params_raw:
                    p_nome = getattr(item, "parametro", str(item))
                    p_val = getattr(item, "valor", "")
                    if str(p_nome) not in params_dict:
                        params_dict[str(p_nome)] = str(p_val)
            elif isinstance(params_raw, dict):
                for k, v in params_raw.items():
                    if str(k) not in params_dict:
                        params_dict[str(k)] = str(v)

            params_lista = [{"parametro": k, "valor": v} for k, v in params_dict.items()]

        # Persistência oficial pós-gate de risco [V0-05]
        import json
        st_norm = "APROVADO" if aprovado_gate and "APROVAD" in str(status_final).upper() and "REPROVAD" not in str(status_final).upper() else "REPROVADO_TOTAL"
        motivo_veto_str = motivo_gate if st_norm == "REPROVADO_TOTAL" else None

        if hasattr(relatorio, "model_dump"):
            rel_dict = relatorio.model_dump()
        elif hasattr(relatorio, "dict"):
            rel_dict = relatorio.dict()
        elif isinstance(relatorio, dict):
            rel_dict = relatorio
        else:
            rel_dict = {"conteudo": str(relatorio)}

        resultado_pos_gate = {
            "status_final": st_norm,
            "motivo_veto": motivo_veto_str,
            "ticker": str(ativo),
            "timestamp": time.strftime("%d/%m/%Y %H:%M:%S"),
            "relatorio_completo": rel_dict
        }

        for p_pasta in ["output", "/tmp/output"]:
            try:
                os.makedirs(p_pasta, exist_ok=True)
                with open(os.path.join(p_pasta, "resultado_pos_gate.json"), "w", encoding="utf-8") as f:
                    json.dump(resultado_pos_gate, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Coleta de Dados Reais de Gráficos (Candlesticks da BRAPI e Payoff)
        adicionar_log(f"📈 Carregando dados técnicos reais e histórico de candles para {ativo}...")
        try:
            fn_tecnica = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
            dados_tecnicos = fn_tecnica(ativo)
        except Exception as e_tec:
            dados_tecnicos = {}
            adicionar_log(f"Aviso dados técnicos: {str(e_tec)}")

        candles = dados_tecnicos.get("candles_recentes", []) if isinstance(dados_tecnicos, dict) else []
        suporte_val = dados_tecnicos.get("suporte_recente") if isinstance(dados_tecnicos, dict) else None
        resistencia_val = dados_tecnicos.get("resistencia_recente") if isinstance(dados_tecnicos, dict) else None
        spot_atual = dados_tecnicos.get("preco_atual") if isinstance(dados_tecnicos, dict) else None

        # Gráfico de payoff: só quando a operação APROVADA pelo gate for trava de alta, com os strikes e prêmios da própria proposta
        is_trava_aprovada = (
            "APROVAD" in status_final.upper()
            and getattr(relatorio, "strike_compra", None) is not None
            and getattr(relatorio, "strike_venda", None) is not None
            and getattr(relatorio, "premio_compra", None) is not None
            and getattr(relatorio, "premio_venda", None) is not None
        )

        pontos_payoff = []
        k_compra = None
        k_venda = None
        breakeven_val = None
        msg_payoff = "Sem estrutura de opções aprovada"

        if is_trava_aprovada:
            k_compra = float(relatorio.strike_compra)
            k_venda = float(relatorio.strike_venda)
            p_compra = float(relatorio.premio_compra)
            p_venda = float(relatorio.premio_venda)
            try:
                fn_payoff = getattr(calcular_payoff_trava_alta, "func", calcular_payoff_trava_alta)
                payoff_data = fn_payoff(
                    strike_compra=k_compra,
                    premio_pago_compra=p_compra,
                    strike_venda=k_venda,
                    premio_recebido_venda=p_venda
                )
                if isinstance(payoff_data, dict) and payoff_data.get("status") == "sucesso":
                    pontos_payoff = payoff_data.get("pontos_curva_payoff", [])
                    breakeven_val = payoff_data.get("breakeven")
                    msg_payoff = ""
            except Exception as e_pay:
                adicionar_log(f"Aviso cálculo payoff: {str(e_pay)}")

        estado_execucao["graficos"] = {
            "ativo": ativo,
            "candles": candles,
            "payoff": pontos_payoff,
            "mensagem_payoff": msg_payoff,
            "suporte": suporte_val,
            "resistencia": resistencia_val,
            "preco_atual": spot_atual,
            "strike_compra": k_compra,
            "strike_venda": k_venda,
            "breakeven": breakeven_val
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
        if not isinstance(dados, dict) or dados.get("status") != "sucesso":
            return JSONResponse(
                {
                    "status": "erro",
                    "mensagem": "Dados de mercado indisponiveis",
                    "ativo": ticker_clean
                },
                status_code=502
            )

        preco_atual = dados.get("preco_atual")
        if preco_atual is None:
            return JSONResponse(
                {
                    "status": "erro",
                    "mensagem": "Dados de mercado indisponiveis",
                    "ativo": ticker_clean
                },
                status_code=502
            )

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

        suporte = dados.get("suporte_recente")
        resistencia = dados.get("resistencia_recente")

        resultado = {
            "status": "sucesso",
            "ativo": ticker_clean,
            "origem": "api_tempo_real",
            "preco_atual": preco_atual,
            "suporte": suporte,
            "resistencia": resistencia,
            "sma20": dados.get("sma20") or dados.get("sma_20"),
            "sma50": dados.get("sma50") or dados.get("sma_50"),
            "volatilidade_anualizada_pct": dados.get("volatilidade_historica_anualizada"),
            "rsi_14": dados.get("rsi_14"),
            "candles": candles_fmt,
            "payoff": [],
            "mensagem_opcoes": "Sem estrutura de opcoes aprovada"
        }

        # Armazenar no cache com proteção de concorrência
        with estado_lock:
            cache_dados_tecnicos[ticker_clean] = {
                "timestamp": agora,
                "dados": resultado
            }

        return JSONResponse(resultado)
    except Exception as e:
        return JSONResponse({"status": "erro", "mensagem": "Dados de mercado indisponiveis", "ativo": ticker_clean}, status_code=502)


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


MAPA_MIDIA_KEYWORDS = {
    "workflow_demo.mp4": ["workflow", "demonstration", ".mp4"],
    "analista_macro.jpg": ["macro"],
    "analista_tecnico.jpg": ["tecnico", "tcnico"],
    "coordenador_risco.jpg": ["risco", "coordenador"],
    "estrategista_opcoes.jpg": ["estrategista", "opcoes", "opco", "opes"],
    "fundamentalista.jpg": ["fundamentalista"],
    "research_publisher.jpg": ["publisher", "research"]
}

EXTENSOES_MIDIA_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".mp4"}


@app.get("/midia/{nome_arquivo}")
@app.get("/static/midia/{nome_arquivo}")
def servir_midia_direta(nome_arquivo: str):
    """
    Serve arquivos estáticos de mídia de forma estritamente confinada à pasta permitida,
    com validação contra Path Traversal (CWE-22) e whitelist de extensões de mídia.
    """
    if not nome_arquivo:
        raise HTTPException(status_code=400, detail="Nome de arquivo não especificado.")

    # 1. Defesa anti-traversal: bloqueia separadores de caminho e caracteres de escape
    if "/" in nome_arquivo or "\\" in nome_arquivo or ".." in nome_arquivo:
        raise HTTPException(status_code=400, detail="Identificador de arquivo inválido.")

    nome_limpo = os.path.basename(nome_arquivo).strip()
    if nome_limpo != nome_arquivo or nome_limpo.startswith("."):
        raise HTTPException(status_code=400, detail="Identificador de arquivo inválido.")

    # 2. Whitelist estrita de extensões permitidas para evitar vazamento de código/segredos
    ext = os.path.splitext(nome_limpo)[1].lower()
    if ext not in EXTENSOES_MIDIA_PERMITIDAS:
        raise HTTPException(status_code=403, detail="Extensão de arquivo não autorizada.")

    tipo_mime = "video/mp4" if ext == ".mp4" else ("image/jpeg" if ext in [".jpg", ".jpeg"] else f"image/{ext.lstrip('.')}")

    dir_base = os.path.dirname(os.path.abspath(__file__))
    pastas_candidatas = [
        os.path.join(dir_base, "static", "midia"),
        os.path.join(dir_base, "midia"),
        os.path.join(dir_base, "Midia"),
        os.path.join(os.getcwd(), "static", "midia"),
        os.path.join(os.getcwd(), "midia"),
        os.path.join(os.getcwd(), "Midia"),
    ]

    # 3. Busca direta pelo nome exato com verificação de confinamento canônico (realpath)
    for pasta in pastas_candidatas:
        if os.path.isdir(pasta):
            pasta_real = os.path.realpath(pasta)
            caminho_candidato = os.path.realpath(os.path.join(pasta_real, nome_limpo))
            # Garante que o arquivo resolvido reside estritamente dentro da pasta de mídia autorizada
            if (caminho_candidato.startswith(pasta_real + os.sep) or caminho_candidato == pasta_real) and os.path.isfile(caminho_candidato):
                return FileResponse(caminho_candidato, media_type=tipo_mime)

    # 4. Busca resiliente por palavras-chave com validação canônica e whitelist
    nome_lower = nome_limpo.lower()
    for alias_chave, kws in MAPA_MIDIA_KEYWORDS.items():
        if alias_chave in nome_lower or any(kw in nome_lower for kw in kws):
            for pasta in pastas_candidatas:
                if os.path.isdir(pasta):
                    pasta_real = os.path.realpath(pasta)
                    try:
                        for arq in os.listdir(pasta_real):
                            arq_ext = os.path.splitext(arq)[1].lower()
                            if arq_ext in EXTENSOES_MIDIA_PERMITIDAS and any(kw in arq.lower() for kw in kws):
                                caminho_candidato = os.path.realpath(os.path.join(pasta_real, arq))
                                if (caminho_candidato.startswith(pasta_real + os.sep)) and os.path.isfile(caminho_candidato):
                                    mime = "video/mp4" if arq_ext == ".mp4" else ("image/jpeg" if arq_ext in [".jpg", ".jpeg"] else f"image/{arq_ext.lstrip('.')}")
                                    return FileResponse(caminho_candidato, media_type=mime)
                    except OSError:
                        continue

    raise HTTPException(status_code=404, detail=f"Arquivo de mídia '{nome_limpo}' não encontrado.")


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
    host = os.getenv("HOST", "127.0.0.1")
    threading.Thread(target=abrir_navegador, args=(porta,), daemon=True).start()
    uvicorn.run(app, host=host, port=porta)


if __name__ == "__main__":
    run_server()


