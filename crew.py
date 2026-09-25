"""
Definição da Crew da Mesa de Operações B3 utilizando CrewAI oficial com suporte a YAML,
LLM Gemini 2.5 Flash, ferramentas determinísticas e controle estrito de iterações.
"""

import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, task, crew

from tools.brapi_tools import (
    listar_universo_liquidez_b3,
    consultar_cotacoes_cesta_liquidez,
    consultar_dados_fundamentalistas,
    consultar_dados_tecnicos_e_medias,
    consultar_cadeia_opcoes_b3,
)

from tools.options_tools import (
    calcular_gregas_black_scholes,
    calcular_risco_retorno_operacao,
    calcular_payoff_trava_alta,
)
from tools.search_tools import pesquisar_noticias_macro_e_commodities
from schemas.output_models import (
    TeseMacroModel,
    SelecaoFundamentalistaModel,
    AnaliseTecnicaModel,
    PropostaEstrategiaModel,
    DecisaoRiscoModel,
    RelatorioExecutivoFinal,
)

import sys
load_dotenv()

# Ajuste de codificação para consoles Windows (evita falha com emojis)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ajuste de compatibilidade para LiteLLM (CrewAI) com Google Gemini
google_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
if google_key:
    os.environ["GEMINI_API_KEY"] = google_key
    os.environ["GOOGLE_API_KEY"] = google_key

# Patch de resiliência e auto-recovery para picos de demanda e limites de cota (HTTP 503 / 429) no Google Gemini
try:
    import time
    import re
    from crewai.llms.providers.gemini.completion import GeminiCompletion
    _orig_gemini_handle = GeminiCompletion._handle_completion

    # Lista de modelos de alta capacidade com cotas independentes na API Google Gemini
    MODELOS_FALLBACK = [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
    ]

    def _resilient_gemini_handle(self, contents, config, available_functions=None, from_task=None, from_agent=None, response_model=None):
        client = self._get_sync_client()
        contents_for_api = contents
        
        # Constrói fila ordenada de modelos iniciando pelo modelo configurado
        modelo_base = str(self.model).replace("gemini/", "").replace("models/", "").strip()
        candidatos = [modelo_base]
        for m in MODELOS_FALLBACK:
            if m not in candidatos:
                candidatos.append(m)

        ultimo_erro = None
        for modelo_atual in candidatos:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=modelo_atual,
                        contents=contents_for_api,
                        config=config,
                    )
                    usage = self._extract_token_usage(response)
                    self._track_token_usage_internal(usage)
                    return self._process_response_with_tools(
                        response=response,
                        contents=contents,
                        available_functions=available_functions,
                        from_task=from_task,
                        from_agent=from_agent,
                        response_model=response_model,
                    )
                except Exception as e:
                    ultimo_erro = e
                    msg = str(e).lower()
                    
                    # Esgotamento de cota diária do modelo ou modelo indisponível: alterna para o próximo modelo da lista
                    if "resource_exhausted" in msg or "quota exceeded" in msg or "free_tier_requests" in msg or "404" in msg or "not_found" in msg:
                        print(f"⚠️ [Resiliência Gemini] Cota/Modelo esgotado para '{modelo_atual}'. Alternando automaticamente para o próximo modelo com cota fresca...")
                        break
                        
                    # Sobrecarga temporária (503) ou rate-limit temporário por minuto (429 com delay)
                    if "503" in msg or "unavailable" in msg or "demand" in msg or "retry in" in msg or "retrydelay" in msg or "429" in msg:
                        m_delay = re.search(r"retry in (\d+\.?\d*)s", msg) or re.search(r"retrydelay':\s*'(\d+)s'", msg)
                        if m_delay:
                            espera = min(float(m_delay.group(1)) + 1.0, 36.0)
                        else:
                            espera = 2.0 * (attempt + 1)
                        print(f"⚠️ [Resiliência Gemini] Limite temporário da API ({modelo_atual}). Aguardando {espera:.1f}s (tentativa {attempt+1}/3)...")
                        time.sleep(espera)
                        continue
                    
                    # Outro erro
                    break

        if ultimo_erro:
            raise ultimo_erro

    GeminiCompletion._handle_completion = _resilient_gemini_handle
except Exception as _patch_err:
    pass


@CrewBase
class MesaOperacoesCrew:
    """Mesa de Operações Multiagente para B3 (Cesta de Liquidez / IBrX-100)"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        # Configuração do LLM Gemini (modelo padrão estável e de alta cota)
        modelo = os.getenv("MODEL", "gemini/gemini-flash-latest")
        self.llm = LLM(
            model=modelo,
            temperature=0.2,
        )

    # ==========================
    # AGENTES DA MESA
    # ==========================

    @agent
    def macro_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["macro_analyst"],
            tools=[pesquisar_noticias_macro_e_commodities, listar_universo_liquidez_b3],
            llm=self.llm,
            max_iter=3,
            verbose=True,
        )

    @agent
    def fundamentalist_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["fundamentalist_analyst"],
            tools=[consultar_dados_fundamentalistas, consultar_cotacoes_cesta_liquidez],

            llm=self.llm,
            max_iter=3,
            verbose=True,
        )

    @agent
    def technical_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["technical_analyst"],
            tools=[consultar_dados_tecnicos_e_medias],
            llm=self.llm,
            max_iter=3,
            verbose=True,
        )

    @agent
    def senior_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["senior_strategist"],
            tools=[
                consultar_cadeia_opcoes_b3,
                calcular_gregas_black_scholes,
                calcular_risco_retorno_operacao,
                calcular_payoff_trava_alta,
            ],
            llm=self.llm,
            max_iter=3,
            verbose=True,
        )

    @agent
    def risk_coordinator(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_coordinator"],
            tools=[],
            llm=self.llm,
            max_iter=1,
            verbose=True,
        )

    @agent
    def research_publisher(self) -> Agent:
        return Agent(
            config=self.agents_config["research_publisher"],
            tools=[],
            llm=self.llm,
            max_iter=1,
            verbose=True,
        )

    # ==========================
    # TAREFAS DO PIPELINE
    # ==========================

    @task
    def analisar_macro_e_mercado_task(self) -> Task:
        return Task(
            config=self.tasks_config["analisar_macro_e_mercado_task"],
            agent=self.macro_analyst(),
            output_pydantic=TeseMacroModel,
        )

    @task
    def selecionar_ativo_fundamentalista_task(self) -> Task:
        return Task(
            config=self.tasks_config["selecionar_ativo_fundamentalista_task"],
            agent=self.fundamentalist_analyst(),
            output_pydantic=SelecaoFundamentalistaModel,
        )

    @task
    def validar_timing_grafico_task(self) -> Task:
        return Task(
            config=self.tasks_config["validar_timing_grafico_task"],
            agent=self.technical_analyst(),
            output_pydantic=AnaliseTecnicaModel,
        )

    @task
    def estruturar_estrategias_operacao_task(self) -> Task:
        return Task(
            config=self.tasks_config["estruturar_estrategias_operacao_task"],
            agent=self.senior_strategist(),
            output_pydantic=PropostaEstrategiaModel,
        )

    @task
    def auditar_risco_e_aprovar_task(self) -> Task:
        return Task(
            config=self.tasks_config["auditar_risco_e_aprovar_task"],
            agent=self.risk_coordinator(),
            output_pydantic=DecisaoRiscoModel,
        )

    @task
    def gerar_relatorio_executivo_investidor_task(self) -> Task:
        return Task(
            config=self.tasks_config["gerar_relatorio_executivo_investidor_task"],
            agent=self.research_publisher(),
            output_pydantic=RelatorioExecutivoFinal,
            output_file="output/relatorio_recomendacao.md",
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
