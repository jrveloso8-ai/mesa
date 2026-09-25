"""
Servidor Web Executivo FastAPI para a Mesa de Operações B3.
Permite iniciar a esteira dos 6 agentes via navegador, acompanhar o status em tempo real,
visualizar gráficos dinâmicos de Candlesticks e Payoff de Opções, e baixar relatórios em PDF.
"""

import sys
import os
import glob
import threading
import queue
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from typing import Dict, Any, List
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

# Ajuste de compatibilidade para Google Gemini
google_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
if google_key:
    os.environ["GOOGLE_API_KEY"] = google_key
    os.environ["GEMINI_API_KEY"] = google_key

from crew import MesaOperacoesCrew
from tools.pdf_generator import gerar_pdf_relatorio
from tools.risk_gate import (
    auditar_gate_de_risco_programatico,
    aplicar_contingencia_de_veto,
    extrair_decisao_risco_autentica,
    extrair_rr_efetivo
)
from tools.brapi_tools import consultar_dados_tecnicos_e_medias
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
}


def adicionar_log(mensagem: str):
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
        dados_tecnicos = consultar_dados_tecnicos_e_medias.func(ativo)
        candles = dados_tecnicos.get("candles_recentes", []) if isinstance(dados_tecnicos, dict) else []
        suporte_val = dados_tecnicos.get("suporte_recente", 0.0) if isinstance(dados_tecnicos, dict) else 0.0
        resistencia_val = dados_tecnicos.get("resistencia_recente", 0.0) if isinstance(dados_tecnicos, dict) else 0.0

        # Curva de Payoff de Opções
        spot_atual = dados_tecnicos.get("preco_atual", 40.0) if isinstance(dados_tecnicos, dict) else 40.0
        k_compra = round(spot_atual * 0.98, 1)
        k_venda = round(spot_atual * 1.04, 1)
        payoff_data = calcular_payoff_trava_alta.func(
            strike_compra=k_compra,
            premio_pago_compra=1.60,
            strike_venda=k_venda,
            premio_recebido_venda=0.50
        )
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
        pdf_path = f"output/relatorio_operacao_{data_str}.pdf"

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
    return JSONResponse(estado_execucao)


@app.get("/api/ranking")
def obter_ranking():
    from tools.screener_ibrx100 import gerar_ranking_completo_ibrx100, obter_estatisticas_funil
    ranking = gerar_ranking_completo_ibrx100()
    stats = obter_estatisticas_funil(ranking)
    return JSONResponse({
        "status": "sucesso",
        "total": len(ranking),
        "estatisticas": stats,
        "ranking": ranking
    })


@app.get("/api/ativo/{ticker}")
def obter_dados_ativo(ticker: str):
    ticker = ticker.upper().strip()
    try:
        fn_tecnica = getattr(consultar_dados_tecnicos_e_medias, "func", consultar_dados_tecnicos_e_medias)
        dados = fn_tecnica(ticker)
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

        return JSONResponse({
            "status": "sucesso",
            "ativo": ticker,
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
        })
    except Exception as e:
        return JSONResponse({"status": "erro", "mensagem": str(e), "ativo": ticker}, status_code=500)




@app.post("/api/iniciar")
def iniciar_processamento(background_tasks: BackgroundTasks):
    if estado_execucao["status"] == "executando":
        return JSONResponse({"status": "aviso", "mensagem": "A esteira já está em execução."})

    thread = threading.Thread(target=executar_esteira_background)
    thread.daemon = True
    thread.start()

    return JSONResponse({"status": "iniciado", "mensagem": "Esteira multiagente iniciada com sucesso."})


@app.get("/api/download/pdf")
def baixar_pdf():
    pdf_path = estado_execucao.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path)
        )

    # Fallback: procura o último PDF na pasta output
    arquivos_pdf = glob.glob("output/*.pdf")
    if arquivos_pdf:
        ultimo_pdf = max(arquivos_pdf, key=os.path.getmtime)
        return FileResponse(
            ultimo_pdf,
            media_type="application/pdf",
            filename=os.path.basename(ultimo_pdf)
        )

    return JSONResponse({"erro": "Nenhum relatório PDF disponível no momento."}, status_code=404)


@app.get("/apresentacao")
def pagina_apresentacao():
    caminho_apresentacao = os.path.join("static", "apresentacao.html")
    if os.path.exists(caminho_apresentacao):
        return FileResponse(caminho_apresentacao, media_type="text/html")
    return JSONResponse({"erro": "Página de apresentação não encontrada."}, status_code=404)


# Servir arquivos estáticos (HTML/CSS/JS)
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")


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


