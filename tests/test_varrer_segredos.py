"""
Testes unitários para o scanner de credenciais scripts/varrer_segredos.py [V3.1-01].
Garante:
1. "risk-block" e "BRAPI_TOKEN=seu_token_aqui" não disparam alerta (zero falso positivo).
2. Chave real "AIza" + 35 caracteres dispara alerta.
3. Arquivo cadastrado na lista de permitidos é ignorado mesmo contendo padrão de token.
"""

import os
from scripts.varrer_segredos import varrer_arquivos, main


def test_varredura_sem_alerta_para_falsos_positivos(tmp_path):
    """Arquivo contendo 'risk-block' e 'BRAPI_TOKEN=seu_token_aqui' NÃO deve gerar alerta."""
    arq_seguro = tmp_path / "app_fake.js"
    arq_seguro.write_text(
        """
        // Arquivo simulado com padrões CSS e placeholders
        const container = document.querySelector('.risk-block');
        const token = "BRAPI_TOKEN=seu_token_aqui";
        """,
        encoding="utf-8"
    )

    ocorrencias = varrer_arquivos([str(arq_seguro)])
    assert len(ocorrencias) == 0, f"Falso positivo detectado: {ocorrencias}"


def test_varredura_com_alerta_para_chave_real(tmp_path):
    """Arquivo contendo 'AIza' + 35 caracteres deve ser detectado e gerar alerta."""
    chave_aiza = "AIza" + ("B" * 35)
    arq_vazado = tmp_path / "config_vazada.py"
    arq_vazado.write_text(
        f"""
        # Arquivo com chave de API real
        GOOGLE_API_KEY = "{chave_aiza}"
        """,
        encoding="utf-8"
    )

    ocorrencias = varrer_arquivos([str(arq_vazado)])
    assert len(ocorrencias) == 1
    assert ocorrencias[0][0] == str(arq_vazado)
    assert ocorrencias[0][1] == 3  # Linha da chave


def test_varredura_ignora_arquivo_na_lista_de_permitidos(tmp_path):
    """Arquivo contendo chave mas listado em segredos_permitidos.txt deve ser ignorado."""
    chave_aiza = "AIza" + ("C" * 35)
    arq_teste = tmp_path / "test_permitido.py"
    arq_teste.write_text(
        f"""
        # Teste unitário com credencial simulada
        mock_token = "{chave_aiza}"
        """,
        encoding="utf-8"
    )

    arq_permitidos = tmp_path / "segredos_permitidos.txt"
    arq_permitidos.write_text(
        f"{arq_teste.name} - arquivo de teste unitario permitido\n",
        encoding="utf-8"
    )

    ocorrencias = varrer_arquivos([str(arq_teste)], caminho_permitidos=str(arq_permitidos))
    assert len(ocorrencias) == 0, "Arquivo permitido não deveria ter gerado ocorrência"


def test_varredura_cli_retorna_codigo_esperado(tmp_path):
    """Garante que a função main() retorna 0 para arquivos limpos e 1 para arquivos com credenciais."""
    arq_limpo = tmp_path / "limpo.py"
    arq_limpo.write_text("print('hello world')\n", encoding="utf-8")

    code_limpo = main([str(arq_limpo)])
    assert code_limpo == 0

    chave_sk = "sk-" + ("D" * 25)
    arq_vazado = tmp_path / "vazado.py"
    arq_vazado.write_text(f"OPENAI_KEY = '{chave_sk}'\n", encoding="utf-8")

    code_vazado = main([str(arq_vazado)])
    assert code_vazado == 1
