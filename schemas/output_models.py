"""
Modelos de dados Pydantic resilientes para validação sintática das saídas da Mesa de Operações.
Campos com valores padrão inteligentes que impedem quebras de pipeline por falta de chaves da LLM.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ItemMultiplo(BaseModel):
    nome: str = Field(default="Indicador", description="Nome do múltiplo (ex: P/L, ROE, DY, EV/EBITDA)")
    valor: str = Field(default="N/D", description="Valor numérico ou percentual observado")


class ItemParametro(BaseModel):
    parametro: str = Field(default="Parâmetro", description="Nome do parâmetro operacional")
    valor: str = Field(default="N/D", description="Valor ou especificação técnica")


class TeseMacroModel(BaseModel):
    vies_geral: str = Field(default="Cauteloso", description="Viés do mercado: Otimista, Cauteloso ou Pessimista")
    gatilhos_macro: List[str] = Field(default_factory=list, description="Fatores macroeconômicos observados")
    setores_destaque: List[str] = Field(default_factory=list, description="Setores da B3 mais favoráveis no cenário")
    ativos_sugeridos_cesta_liquidez: List[str] = Field(default_factory=list, description="Tickers da cesta de liquidez B3 indicados para triagem")
    ativos_sugeridos_ibrx10: Optional[List[str]] = Field(default=None, description="Alias para retrocompatibilidade")
    resumo_cenario: str = Field(default="Cenário macroeconômico em monitoramento de juros e commodities.", description="Resumo sucinto")


class SelecaoFundamentalistaModel(BaseModel):
    ticker: str = Field(default="DADOS_INDISPONIVEIS", description="Código do ativo selecionado (ex: ITUB4, PETR4)")
    preco_atual: Optional[float] = Field(default=None, description="Preço de tela do ativo em R$")
    multiplos: List[ItemMultiplo] = Field(default_factory=list, description="Lista de múltiplos e indicadores de valuation")
    saude_financeira: str = Field(default="Análise de solvência e saúde financeira", description="Diagnóstico contábil")
    justificativa_escolha: str = Field(default="Ativo com balanço sólido e liquidez institucional", description="Racional fundamentalista")


class AnaliseTecnicaModel(BaseModel):
    ticker: str = Field(default="DADOS_INDISPONIVEIS", description="Ticker do ativo analisado")
    tendencia: str = Field(default="Lateral", description="Tendência técnica (Alta, Baixa ou Lateral)")
    suporte: float = Field(default=0.0, description="Região de suporte relevante em R$")
    resistencia: float = Field(default=0.0, description="Região de resistência relevante em R$")
    rsi_ifr: Optional[float] = Field(default=50.0, description="Índice de Força Relativa (14 períodos)")
    sinal_timing: str = Field(default="Aguardar Confirmação", description="Avaliação de timing")
    preco_entrada_sugerido: float = Field(default=0.0, description="Ponto de entrada ideal em R$")
    stop_loss_tecnico: float = Field(default=0.0, description="Preço de corte de perdas estrito em R$")


class GregasOpcoesModel(BaseModel):
    delta: float = Field(default=0.0, description="Delta da opção")
    gamma: float = Field(default=0.0, description="Gamma da opção")
    theta: float = Field(default=0.0, description="Theta diário da opção em R$")
    vega: float = Field(default=0.0, description="Vega por 1% de volatilidade")


class EstrategiaDetalheModel(BaseModel):
    nome_estrategia: str = Field(default="Aguardar no Caixa", description="Nome da estratégia")
    instrumento: str = Field(default="Ações", description="'Ações' ou 'Opções'")
    ticker_base: str = Field(default="DADOS_INDISPONIVEIS", description="Ticker da ação subjacente")
    opcoes_envolvidas: List[str] = Field(default_factory=list, description="Códigos das opções na B3")
    vencimento: Optional[str] = Field(default="3ª Sexta-Feira do Mês", description="Data ou regra de vencimento")
    strikes: List[float] = Field(default_factory=list, description="Strikes envolvidos")
    custo_ou_credito_unitario: float = Field(default=0.0, description="Custo inicial ou crédito recebido")
    gregas: Optional[GregasOpcoesModel] = Field(default=None, description="Gregas consolidadas")
    lucro_maximo: str = Field(default="N/D", description="Potencial máximo de ganho")
    perda_maxima: str = Field(default="N/D", description="Risco máximo assumido")
    breakeven: float = Field(default=0.0, description="Ponto de equilíbrio no vencimento")
    relacao_risco_retorno: str = Field(default="N/D", description="Relação ganho/perda em texto (ex: 2.1 : 1)")
    razao_risco_retorno_num: float = Field(default=0.0, description="Razão Risco/Retorno numérica pura (ex: 2.15). Se < 1.5, operação é desclassificada.")
    horizonte: str = Field(default="Swing Trade", description="Swing Trade ou Position Mensal")


class PropostaEstrategiaModel(BaseModel):
    ticker: str = Field(default="DADOS_INDISPONIVEIS", description="Ticker do ativo")
    estrategia_principal: EstrategiaDetalheModel = Field(default_factory=EstrategiaDetalheModel, description="Estratégia primária recomendada")
    estrategia_alternativa: EstrategiaDetalheModel = Field(default_factory=EstrategiaDetalheModel, description="Estratégia alternativa de menor risco")
    racional_operacional: str = Field(default="Estrutura operacional da mesa", description="Justificativa")


class DecisaoRiscoModel(BaseModel):
    status: str = Field(default="REPROVADO_TOTAL", description="Status final: 'APROVADO_PRINCIPAL', 'APROVADO_ALTERNATIVA' ou 'REPROVADO_TOTAL'")
    estrategia_adotada: str = Field(default="Manutenção em Caixa", description="Nome da estratégia autorizada")
    razao_risco_retorno_auditada: float = Field(default=0.0, description="Razão R/R verificada pelo comitê de risco (ex: 2.15). Obrigatória para aprovação.")
    parecer_risco: str = Field(default="Parecer prudencial do Coordenador de Mesa", description="Parecer do comitê de risco")
    pontos_atencao: List[str] = Field(default_factory=list, description="Riscos mapeados")
    aprovado_para_divulgacao: bool = Field(default=False, description="Se falso, aciona gate de risco automático de retenção de capital")


class RelatorioExecutivoFinal(BaseModel):
    titulo: str = Field(default="Resumo Executivo da Mesa de Operações", description="Título formal do relatório")
    data_geracao: str = Field(default="", description="Data da elaboração da análise")
    status_decisao: str = Field(default="REPROVADO_TOTAL", description="Status regulatório de decisão de mesa: APROVADO_PRINCIPAL, APROVADO_ALTERNATIVA ou REPROVADO_TOTAL")
    resumo_executivo: str = Field(default="", description="Sumário da tese e contexto para o investidor")
    ativo_alvo: str = Field(default="DADOS_INDISPONIVEIS", description="Ticker do ativo recomendado")
    operacao_recomendada: str = Field(default="Manutenção em Caixa", description="Detalhamento operacional da estratégia")
    razao_risco_retorno_num: float = Field(default=0.0, description="Razão Risco/Retorno numérica auditada (ex: 2.15). Obrigatório >= 1.5 para aprovação.")
    parametros_operacionais: List[ItemParametro] = Field(default_factory=list, description="Tabela de parâmetros: Entrada, Alvo, Stop, Strikes, R/R")
    gregas: Optional[GregasOpcoesModel] = Field(default=None, description="Gregas consolidadas da estrutura calculadas por Black-Scholes")
    gestao_risco_e_saida: str = Field(default="", description="Instruções de risco e plano de contingência")
    disclaimer_cvm: str = Field(default="Em conformidade com a Resolução CVM nº 20/2021.", description="Disclaimer legal")

