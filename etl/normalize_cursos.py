"""
Normalização de nomes de cursos nos TCCs.
Detecta e corrige:
1. Variações de caixa (case)
2. Erros de digitação (fuzzy matching)
3. Variações de nomenclatura (sinônimos)
4. Prefixos/sufixos desnecessários
"""

import sqlite3
import re
import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


def similarity(a, b):
    """Calcula similaridade entre duas strings (0 a 1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_text(text):
    """Normaliza texto: remove espaços extras, title case."""
    if not text:
        return None
    # Remove espaços extras
    text = re.sub(r'\s+', ' ', text.strip())
    # Se está todo em maiúsculas ou minúsculas com erros de caixa, corrige
    if text.isupper() or text.islower() or text[0].islower():
        text = text.title()
    return text


# Mapeamento manual de correções conhecidas
CORRECOES_MANUAIS = {
    # Erros de digitação comuns
    "admonistração": "Administração",
    "adminstração": "Administração",
    "administracao": "Administração",
    "adiministração": "Administração",
    "egenharia ambiental": "Engenharia Ambiental",
    "engenharia mêcanica": "Engenharia Mecânica",
    "engenharia mecanica": "Engenharia Mecânica",
    "engenharia mecatronica": "Engenharia Mecatrônica",
    "ciências biloógicas": "Ciências Biológicas",
    "ciencias biologicas": "Ciências Biológicas",
    "ciências políticas e sociais": "Ciências Políticas e Sociais",
    "biomedicina": "Biomedicina",
    "enfermagem": "Enfermagem",
    "gastronomia": "Gastronomia",
    "hotelaria": "Hotelaria",
    "geofísica": "Geofísica",
    "arquitetura": "Arquitetura e Urbanismo",

    # Variações de nomenclatura
    "administração de empresas": "Administração",
    "bacharelado em administração": "Administração",
    "tecnologia em gestão de empresas": "Gestão de Empresas",
    "gestao de turismo": "Gestão de Turismo",
    "gestão em empreendimentos turísticos": "Gestão de Turismo",

    # Licenciaturas - padronização
    "licenciatura em química": "Licenciatura em Química",
    "quimica-licenciatura": "Licenciatura em Química",
    "química - licenciatura": "Licenciatura em Química",
    "licenciatura em biologia": "Licenciatura em Ciências Biológicas",
    "biologia - licenciatura": "Licenciatura em Ciências Biológicas",
    "licenciatura em história": "Licenciatura em História",
    "história - licenciatura": "Licenciatura em História",
    "licenciatura em matemática": "Licenciatura em Matemática",
    "matemática - licenciatura": "Licenciatura em Matemática",
    "licenciatura em música": "Licenciatura em Música",
    "filosofia licenciatura": "Licenciatura em Filosofia",
    "filosofia - licenciatura": "Licenciatura em Filosofia",

    # Engenharias
    "engenharia de controle e automação": "Engenharia de Controle e Automação",
    "engenharia de automação": "Engenharia de Controle e Automação",
    "engenharia da computação": "Engenharia da Computação",
    "engenharia civil": "Engenharia Civil",

    # Tecnólogos
    "analise e desenvolvimento de sistemas": "Análise e Desenvolvimento de Sistemas",
    "análise e desenvolvimento de sistemas": "Análise e Desenvolvimento de Sistemas",
    "sistema de informação": "Sistemas de Informação",
    "sistemas de informação": "Sistemas de Informação",
    "sistema elétrico": "Sistemas Elétricos",
    "telemática": "Telemática",
    "tecnologia em laticínios": "Tecnologia em Laticínios",
    "tecnologia em construção de edificios": "Tecnologia em Construção de Edifícios",
    "medicina veterinaria": "Medicina Veterinária",

    # Prefixos desnecessários
    "curso tecnico em alimentos": "Técnico em Alimentos",
    "curso superior de tecnologia em laticínios": "Tecnologia em Laticínios",
}

# Padrões de prefixos para remover
PREFIXOS_REMOVER = [
    r'^curso\s+(superior\s+de\s+)?tecnologia\s+em\s+',
    r'^curso\s+técnico\s+(de\s+nível\s+médio\s+)?em\s+',
    r'^curso\s+de\s+',
    r'^bacharelado\s+em\s+',
    r'^tecnólogo\s+em\s+',
    r'^técnico\s+(integrado\s+)?em\s+',
]


class CursoNormalizer:
    """Normaliza nomes de cursos usando regras + fuzzy matching."""

    def __init__(self):
        self.corrections = {}  # cache de correções aplicadas
        self.canonical_courses = {}  # curso_lower -> forma canônica

    def _clean_basic(self, curso):
        """Limpeza básica do nome do curso."""
        if not curso:
            return None
        # Remove espaços extras e normaliza
        curso = re.sub(r'\s+', ' ', curso.strip())
        # Remove caracteres estranhos no início
        curso = re.sub(r'^[^a-zA-ZÀ-ÿ]+', '', curso)
        if not curso:
            return None
        return curso

    def _apply_manual_corrections(self, curso):
        """Aplica correções manuais."""
        curso_lower = curso.lower().strip()
        if curso_lower in CORRECOES_MANUAIS:
            return CORRECOES_MANUAIS[curso_lower]
        return None

    def _fix_case(self, curso):
        """Corrige problemas de caixa."""
        # Se começa com minúscula ou está todo em maiúsculas/minúsculas erradas
        if curso[0].islower() or curso.isupper():
            # Title case com exceções para preposições
            words = curso.split()
            preposicoes = {'de', 'da', 'do', 'das', 'dos', 'em', 'e', 'para', 'com', 'a', 'o', 'as', 'os', 'na', 'no', 'nas', 'nos'}
            result = []
            for i, w in enumerate(words):
                if i == 0 or w.lower() not in preposicoes:
                    # Capitaliza primeira letra, mantém resto em minúscula
                    if w.isupper() or w.islower():
                        result.append(w.capitalize())
                    else:
                        result.append(w)
                else:
                    result.append(w.lower())
            return ' '.join(result)
        return curso

    def _remove_prefixes(self, curso):
        """Remove prefixos desnecessários."""
        curso_lower = curso.lower()
        for pattern in PREFIXOS_REMOVER:
            match = re.match(pattern, curso_lower)
            if match:
                remainder = curso[match.end():]
                if len(remainder) > 3:
                    return remainder[0].upper() + remainder[1:]
        return curso

    def build_canonical_map(self, cursos_with_counts):
        """Constrói mapa de cursos canônicos a partir dos mais frequentes."""
        # Ordena por frequência (mais frequente = forma canônica)
        sorted_cursos = sorted(cursos_with_counts.items(), key=lambda x: -x[1])

        for curso, count in sorted_cursos:
            if not curso:
                continue
            curso_lower = curso.lower().strip()
            if curso_lower not in self.canonical_courses:
                self.canonical_courses[curso_lower] = curso

    def find_similar(self, curso, threshold=0.85):
        """Encontra curso similar no mapa canônico."""
        curso_lower = curso.lower().strip()

        # Match exato (case-insensitive)
        if curso_lower in self.canonical_courses:
            return self.canonical_courses[curso_lower]

        # Fuzzy matching contra cursos canônicos
        best_match = None
        best_score = 0

        for canonical_lower, canonical_name in self.canonical_courses.items():
            score = similarity(curso_lower, canonical_lower)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = canonical_name

        return best_match

    def normalize(self, curso):
        """Normaliza um nome de curso."""
        if not curso:
            return None

        # 1. Limpeza básica
        curso = self._clean_basic(curso)
        if not curso:
            return None

        # 2. Correção manual
        manual = self._apply_manual_corrections(curso)
        if manual:
            return manual

        # 3. Correção de caixa
        curso = self._fix_case(curso)

        # 4. Remove prefixos
        curso = self._remove_prefixes(curso)

        # 5. Fuzzy match contra canônicos
        similar = self.find_similar(curso)
        if similar:
            return similar

        return curso


def run_normalization():
    """Executa normalização de cursos no banco."""
    print("=" * 60)
    print("  NORMALIZAÇÃO DE NOMES DE CURSOS")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Busca todos os cursos com contagem
    cur.execute("SELECT curso, COUNT(*) as total FROM tccs WHERE curso IS NOT NULL GROUP BY curso")
    cursos_raw = {row[0]: row[1] for row in cur.fetchall()}
    print(f"\nCursos distintos antes: {len(cursos_raw)}")
    print(f"Total de TCCs: {sum(cursos_raw.values())}")

    # 2. Constrói normalizer
    normalizer = CursoNormalizer()
    normalizer.build_canonical_map(cursos_raw)

    # 3. Normaliza cada curso
    mapping = {}  # curso_original -> curso_normalizado
    changes = 0

    for curso_original in cursos_raw.keys():
        normalizado = normalizer.normalize(curso_original)
        if normalizado and normalizado != curso_original:
            mapping[curso_original] = normalizado
            changes += 1

    print(f"\nCursos que serão corrigidos: {changes}")

    # 4. Mostra amostra das correções
    print(f"\nAmostra de correções (primeiras 40):")
    shown = 0
    for original, corrigido in sorted(mapping.items(), key=lambda x: cursos_raw.get(x[0], 0), reverse=True):
        if shown >= 40:
            break
        count = cursos_raw.get(original, 0)
        print(f"  [{count:4d}] '{original}' → '{corrigido}'")
        shown += 1

    # 5. Aplica correções no banco
    print(f"\n{'─'*60}")
    print("  Aplicando correções no banco...")

    total_updated = 0
    for original, corrigido in mapping.items():
        cur.execute("UPDATE tccs SET curso = ? WHERE curso = ?", (corrigido, original))
        total_updated += cur.rowcount

    conn.commit()

    # 6. Verifica resultado
    cur.execute("SELECT COUNT(DISTINCT curso) FROM tccs WHERE curso IS NOT NULL")
    cursos_depois = cur.fetchone()[0]

    print(f"\n  Registros atualizados: {total_updated}")
    print(f"  Cursos distintos antes: {len(cursos_raw)}")
    print(f"  Cursos distintos depois: {cursos_depois}")
    print(f"  Redução: {len(cursos_raw) - cursos_depois} cursos unificados")

    # 7. Mostra top cursos após normalização
    cur.execute("SELECT curso, COUNT(*) as total FROM tccs WHERE curso IS NOT NULL GROUP BY curso ORDER BY total DESC LIMIT 20")
    print(f"\n  Top 20 cursos após normalização:")
    for row in cur.fetchall():
        print(f"    [{row[1]:5d}] {row[0]}")

    conn.close()
    print(f"\n{'='*60}")
    print("  ✅ NORMALIZAÇÃO CONCLUÍDA!")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_normalization()
