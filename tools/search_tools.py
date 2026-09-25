"""
Ferramentas de pesquisa de mercado e notícias macroeconômicas via DuckDuckGo.
Sem necessidade de chave de API adicional.
"""

from typing import Dict, Any, List
from crewai.tools import tool
from duckduckgo_search import DDGS


@tool("pesquisar_noticias_macro_e_commodities")
def pesquisar_noticias_macro_e_commodities(termo_pesquisa: str) -> Dict[str, Any]:
    """
    Pesquisa notícias em tempo real sobre cenário macroeconômico brasileiro e global,
    juros (Copom, Selic, Fed), inflação (IPCA), commodities (Petróleo, Minério de Ferro) e B3.
    - termo_pesquisa: Termos objetivos para busca (ex: 'Copom juros Selic decisão B3', 'Petróleo Brent cotação hoje', 'Vale minerio de ferro china')
    """
    try:
        ddgs = DDGS()
        results: List[Dict[str, str]] = []
        # Limita a 4 resultados para manter concisão e economia de tokens
        raw_results = ddgs.news(keywords=termo_pesquisa, region="br-pt", max_results=4)
        for r in raw_results:
            results.append({
                "titulo": r.get("title", ""),
                "data": r.get("date", ""),
                "fonte": r.get("source", ""),
                "resumo": r.get("body", ""),
            })

        if not results:
            # Fallback para busca textual comum
            text_results = ddgs.text(keywords=termo_pesquisa, region="br-pt", max_results=4)
            for r in text_results:
                results.append({
                    "titulo": r.get("title", ""),
                    "resumo": r.get("body", ""),
                    "link": r.get("href", "")
                })

        if not results:
            return {
                "status": "pesquisa_web_indisponivel",
                "termo": termo_pesquisa,
                "total_noticias": 0,
                "noticias": [],
                "aviso": (
                    "Consulta web em tempo real não retornou notícias para o termo. "
                    "Nenhum dado foi fabricado. O analista macro deve basear sua análise nas premissas "
                    "oficiais vigentes da política monetária (Selic/Copom) e dados medidos de mercado, "
                    "declarando explicitamente a ausência de manchetes ao vivo."
                )
            }

        return {
            "status": "sucesso_medido",
            "termo": termo_pesquisa,
            "total_noticias": len(results),
            "noticias": results
        }
    except Exception as e:
        return {
            "status": "pesquisa_web_indisponivel",
            "termo": termo_pesquisa,
            "total_noticias": 0,
            "noticias": [],
            "aviso": (
                f"Consulta web em tempo real indisponível ({str(e)}). "
                "Nenhum dado foi fabricado. O analista macro deve fundamentar sua análise nos dados "
                "oficiais mensuráveis disponíveis e registrar a limitação de busca externa."
            )
        }
