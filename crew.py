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

# Patch de resiliência para tratamento de picos de demanda (HTTP 503 / 429) no Google Gemini
try:
    import time
    from crewai.llms.providers.gemini.completion import GeminiCompletion
    _orig_gemini_handle = GeminiCompletion._handle_completion

    def _resilient_gemini_handle(self, contents, config, available_functions=None, from_task=None, from_agent=None, response_model=None):
        client = self._get_sync_client()
        contents_for_api = contents
        modelo_atual = self.model
        tentativas = 5
        for attempt in range(tentativas):
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
                msg = str(e).lower()
                if ("503" in msg or "unavailable" in msg or "demand" in msg or "quota" in msg or "exhausted" in msg) and attempt < tentativas - 1:
                    espera = 2.0 * (attempt + 1)
                    print(f"⚠️ [Resiliência Gemini] Sobrecarga temporária da API ({modelo_atual}). Aguardando {espera:.1f}s (tentativa {attempt+1}/{tentativas})...")
                    time.sleep(espera)
                    continue
                raise e

    GeminiCompletion._handle_completion = _resilient_gemini_handle
except Exception as _patch_err:
    pass


@CrewBase
class MesaOperacoesCrew:
    """Mesa de Operações Multiagente para B3 (Cesta de Liquidez / IBrX-100)"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        # Configuração do LLM Gemini
        modelo = os.getenv("MODEL", "gemini/gemini-3-flash-preview")
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
