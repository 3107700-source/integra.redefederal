"""
Configurações do projeto ETL Integra - Rede Federal.
Suporta extração de dados de todas as instituições da rede federal via Portal Integra.
"""

import json
import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Diretórios
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = str(BASE_DIR / "data")
RAW_DIR = f"{DATA_DIR}/raw"
PROCESSED_DIR = f"{DATA_DIR}/processed"
DB_PATH = str(BASE_DIR / "data" / "integra.db")

# Arquivos de saída (legado - mantidos para compatibilidade)
PROFESSORES_RAW = f"{RAW_DIR}/professores_raw.json"
PUBLICACOES_RAW = f"{RAW_DIR}/publicacoes_raw.json"
PROFESSORES_PROCESSED = f"{PROCESSED_DIR}/professores.csv"
PUBLICACOES_PROCESSED = f"{PROCESSED_DIR}/publicacoes.csv"
CLUSTERS_OUTPUT = f"{PROCESSED_DIR}/professores_clusters.csv"

# ─────────────────────────────────────────────────────────────────────────────
# Configurações de scraping
# ─────────────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.3
MAX_RETRIES = 3
MAX_CONCURRENT = 10
PAGE_SIZE = 50

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

# ─────────────────────────────────────────────────────────────────────────────
# Instituições da Rede Federal (sigla -> [nome, url_integra, uf])
# ─────────────────────────────────────────────────────────────────────────────
INSTITUICOES = {
    "IFAC": ["Instituto Federal do Acre", "https://integra.ifac.edu.br", "AC"],
    "IFAL": ["Instituto Federal de Alagoas", "https://integra.ifal.edu.br", "AL"],
    "IFAP": ["Instituto Federal do Amapá", "https://integra.ifap.edu.br", "AP"],
    "IFAM": ["Instituto Federal do Amazonas", "https://integra.ifam.edu.br", "AM"],
    "IFBA": ["Instituto Federal da Bahia", "https://integra.ifba.edu.br", "BA"],
    "IFB": ["Instituto Federal de Brasília", "https://integra.ifb.edu.br", "DF"],
    "IFCE": ["Instituto Federal do Ceará", "https://integra.ifce.edu.br", "CE"],
    "IFES": ["Instituto Federal do Espírito Santo", "https://integra.ifes.edu.br", "ES"],
    "IFG": ["Instituto Federal de Goiás", "https://integra.ifg.edu.br", "GO"],
    "IFGOIANO": ["Instituto Federal Goiano", "https://integra.ifgoiano.edu.br", "GO"],
    "IFMA": ["Instituto Federal do Maranhão", "https://integra.ifma.edu.br", "MA"],
    "IFMG": ["Instituto Federal de Minas Gerais", "https://integra.ifmg.edu.br", "MG"],
    "IFNMG": ["Instituto Federal do Norte de Minas Gerais", "https://integra.ifnmg.edu.br", "MG"],
    "IFSUDESTEMG": ["Instituto Federal do Sudeste de Minas Gerais", "https://integra.ifsudestemg.edu.br", "MG"],
    "IFSULDEMINAS": ["Instituto Federal do Sul de Minas Gerais", "https://integra.ifsuldeminas.edu.br", "MG"],
    "IFTM": ["Instituto Federal do Triângulo Mineiro", "https://integra.iftm.edu.br", "MG"],
    "IFMT": ["Instituto Federal de Mato Grosso", "https://integra.ifmt.edu.br", "MT"],
    "IFMS": ["Instituto Federal de Mato Grosso do Sul", "https://integra.ifms.edu.br", "MS"],
    "IFPA": ["Instituto Federal do Pará", "https://integra.ifpa.edu.br", "PA"],
    "IFPB": ["Instituto Federal da Paraíba", "https://integra.ifpb.edu.br", "PB"],
    "IFPE": ["Instituto Federal de Pernambuco", "https://integra.ifpe.edu.br", "PE"],
    "IFSertaoPE": ["Instituto Federal do Sertão Pernambucano", "https://integra.ifsertao-pe.edu.br", "PE"],
    "IFPI": ["Instituto Federal do Piauí", "https://integra.ifpi.edu.br", "PI"],
    "IFPR": ["Instituto Federal do Paraná", "https://integra.ifpr.edu.br", "PR"],
    "IFRJ": ["Instituto Federal do Rio de Janeiro", "https://integra.ifrj.edu.br", "RJ"],
    "IFFLUMINENSE": ["Instituto Federal Fluminense", "http://integra.iff.edu.br", "RJ"],
    "IFRN": ["Instituto Federal do Rio Grande do Norte", "https://integra.ifrn.edu.br", "RN"],
    "IFRO": ["Instituto Federal de Rondônia", "https://integra.ifro.edu.br", "RO"],
    "IFRR": ["Instituto Federal de Roraima", "https://integra.ifrr.edu.br", "RR"],
    "IFRS": ["Instituto Federal do Rio Grande do Sul", "https://integra.ifrs.edu.br", "RS"],
    "IFFARROUPILHA": ["Instituto Federal Farroupilha", "https://integra.iffarroupilha.edu.br", "RS"],
    "IFSUL": ["Instituto Federal Sul-rio-grandense", "https://integra.ifsul.edu.br", "RS"],
    "IFSC": ["Instituto Federal de Santa Catarina", "https://integra.ifsc.edu.br", "SC"],
    "IFC": ["Instituto Federal Catarinense", "https://integra.ifc.edu.br", "SC"],
    "IFSP": ["Instituto Federal de São Paulo", "https://integra.ifsp.edu.br", "SP"],
    "IFS": ["Instituto Federal de Sergipe", "https://integra.ifs.edu.br", "SE"],
    "IFTO": ["Instituto Federal do Tocantins", "https://integra.ifto.edu.br", "TO"],
    "CEFET-RJ": ["CEFET Celso Suckow da Fonseca", "https://integra.cefet-rj.br", "RJ"],
    "CEFET-MG": ["CEFET de Minas Gerais", "https://integra.cefetmg.br", "MG"],
}

# URL base padrão (IFB)
BASE_URL = INSTITUICOES["IFB"][1]

# ─────────────────────────────────────────────────────────────────────────────
# Áreas CNPq para classificação
# ─────────────────────────────────────────────────────────────────────────────
AREAS_CNPQ = {
    "Ciências Exatas e da Terra": [
        "matemática", "probabilidade", "estatística", "ciência da computação",
        "astronomia", "física", "química", "geociências", "oceanografia",
        "informática", "computação", "algoritmo", "programação", "software",
    ],
    "Ciências Biológicas": [
        "biologia", "genética", "botânica", "zoologia", "ecologia",
        "morfologia", "fisiologia", "bioquímica", "biofísica", "farmacologia",
        "imunologia", "microbiologia", "parasitologia",
    ],
    "Engenharias": [
        "engenharia", "civil", "minas", "materiais", "metalúrgica",
        "elétrica", "mecânica", "química", "sanitária", "produção",
        "nuclear", "transportes", "naval", "aeroespacial", "biomédica",
    ],
    "Ciências da Saúde": [
        "medicina", "odontologia", "farmácia", "enfermagem",
        "nutrição", "saúde coletiva", "fonoaudiologia", "fisioterapia",
        "terapia ocupacional", "educação física",
    ],
    "Ciências Agrárias": [
        "agronomia", "recursos florestais", "engenharia agrícola",
        "zootecnia", "medicina veterinária", "recursos pesqueiros",
        "ciência e tecnologia de alimentos", "agroecologia", "agropecuária",
    ],
    "Ciências Sociais Aplicadas": [
        "direito", "administração", "economia", "arquitetura", "urbanismo",
        "planejamento urbano", "demografia", "ciência da informação",
        "museologia", "comunicação", "serviço social", "turismo",
        "contabilidade", "gestão pública", "gestão",
    ],
    "Ciências Humanas": [
        "filosofia", "sociologia", "antropologia", "arqueologia",
        "história", "geografia", "psicologia", "educação", "ciência política",
        "teologia", "pedagogia",
    ],
    "Linguística, Letras e Artes": [
        "linguística", "letras", "artes", "música", "dança", "teatro",
        "literatura", "língua", "português", "inglês", "espanhol",
        "design", "desenho industrial", "comunicação visual",
    ],
    "Multidisciplinar": [
        "interdisciplinar", "multidisciplinar", "biotecnologia",
        "nanotecnologia", "meio ambiente", "inovação", "sustentabilidade",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Pesos para o ranking (IPA - Índice de Produtividade Acadêmica)
# ─────────────────────────────────────────────────────────────────────────────
PESOS_RANKING = {
    "publicacoes": 0.15,
    "impacto": 0.12,
    "diversidade": 0.05,
    "recencia": 0.08,
    "orientacoes": 0.12,
    "projetos": 0.10,
    "tempo_docencia": 0.08,
    "comissoes_bancas": 0.08,
    "extensao": 0.05,
    "titulacao": 0.12,
    "gestao_academica": 0.05,
}

# Pesos de titulação para o ranking
PESOS_TITULACAO = {
    "pos_doutorado": 12,
    "doutorado": 10,
    "mestrado": 7,
    "especializacao": 4,
    "graduacao": 2,
}

# Pesos de impacto por tipo de produção
PESOS_IMPACTO_PRODUCAO = {
    "Tese": 10,
    "Dissertação": 8,
    "Patente Depositada": 9,
    "Livro Publicado ou Organizado": 7,
    "Livro": 7,
    "Artigo Publicado": 6,
    "Artigo Aceito para Publicação": 5,
    "Capítulo de Livro": 5,
    "Software Depositado": 5,
    "Produto Tecnológico": 5,
    "Trabalho Completo em Eventos": 4,
    "Artigo em Conferência": 4,
    "Preprint": 3,
    "Relatório de Pesquisa": 3,
    "Trabalho Resumo Expandido em Eventos": 3,
    "Trabalho Resumo em Eventos": 2,
    "Material Didático": 3,
    "Processos ou Técnicas": 4,
    "Conjunto de Dados": 3,
    "Texto em Jornal ou Revista": 2,
    "Apresentação de Trabalho": 2,
    "Curso de Curta Duração Ministrado": 2,
    "Organização de Evento": 1,
    "Editoração": 1,
    "Traduções": 1,
    "Programa Rádio ou TV": 1,
    "Outras Produções": 1,
    "Demais Produções": 1,
    "Outro": 1,
}
