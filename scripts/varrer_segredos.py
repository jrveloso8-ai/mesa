#!/usr/bin/env python3
"""
Scanner determinístico de credenciais e segredos em arquivos de código.
Procura exclusivamente padrões reais de chaves e tokens (Google, OpenAI, GitHub e tokens de configuração),
evitando falsos positivos em classes CSS, strings curtas ou arquivos explicitamente permitidos.
"""

import os
import sys
import re
from typing import List, Tuple, Set, Optional

PADROES_SEGREDOS = [
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}"),
    re.compile(r"(?i)\b(?:token|api_key|apikey|secret)\s*[=:]\s*[\"']?([A-Za-z0-9_-]{16,})[\"']?(?!\w|\s*\()"),
]


def carregar_arquivos_permitidos(caminho_permitidos: Optional[str] = None) -> Set[str]:
    """Carrega lista de arquivos autorizados a conter strings de teste/exemplo."""
    if caminho_permitidos is None:
        candidatos = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "segredos_permitidos.txt"),
            os.path.join("scripts", "segredos_permitidos.txt"),
        ]
        for c in candidatos:
            if os.path.exists(c):
                caminho_permitidos = c
                break

    permitidos = set()
    if caminho_permitidos and os.path.exists(caminho_permitidos):
        with open(caminho_permitidos, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                linha = line.strip()
                if not linha or linha.startswith("#"):
                    continue
                partes = linha.split("-", 1)
                caminho = partes[0].strip()
                if caminho:
                    permitidos.add(os.path.normpath(caminho).replace("\\", "/").lower())
    return permitidos


def deve_ignorar_arquivo(caminho_arquivo: str, permitidos: Set[str]) -> bool:
    """Verifica se o arquivo deve ser ignorado pela varredura."""
    norm = os.path.normpath(caminho_arquivo).replace("\\", "/").lower()
    
    # Ignora o próprio script de varredura
    if norm.endswith("varrer_segredos.py"):
        return True
        
    for p in permitidos:
        if norm == p or norm.endswith("/" + p) or norm.endswith(p):
            return True
            
    return False


def varrer_arquivos(
    lista_arquivos: List[str], caminho_permitidos: Optional[str] = None
) -> List[Tuple[str, int]]:
    """
    Varre os arquivos informados procurando padrões de credenciais.
    Retorna lista de tuplas (arquivo, numero_linha).
    """
    permitidos = carregar_arquivos_permitidos(caminho_permitidos)
    ocorrencias: List[Tuple[str, int]] = []

    for arq in lista_arquivos:
        arq = arq.strip()
        if not arq or not os.path.exists(arq) or os.path.isdir(arq):
            continue

        if deve_ignorar_arquivo(arq, permitidos):
            continue

        try:
            with open(arq, "r", encoding="utf-8", errors="ignore") as f:
                for num_linha, linha in enumerate(f, 1):
                    for padrao in PADROES_SEGREDOS:
                        if padrao.search(linha):
                            ocorrencias.append((arq, num_linha))
                            break
        except Exception:
            continue

    return ocorrencias


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    arquivos: List[str] = []

    # Se foram passados arquivos via argumentos
    if argv:
        for arg in argv:
            if arg == "-":
                arquivos.extend(sys.stdin.read().splitlines())
            else:
                arquivos.append(arg)
    # Se stdin tiver dados via pipe
    elif not sys.stdin.isatty():
        arquivos.extend(sys.stdin.read().splitlines())

    # Remover linhas vazias e duplicadas mantendo ordem
    vistos = set()
    arquivos_limpos = []
    for a in arquivos:
        a_strip = a.strip()
        if a_strip and a_strip not in vistos:
            vistos.add(a_strip)
            arquivos_limpos.append(a_strip)

    if not arquivos_limpos:
        return 0

    ocorrencias = varrer_arquivos(arquivos_limpos)

    if ocorrencias:
        for arq, linha in ocorrencias:
            print(f"{arq}:{linha}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
