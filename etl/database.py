"""
Camada de persistência - SQLite para armazenar dados extraídos de toda a rede federal.
Tabelas: professores, tccs, artigos, projetos, publicacoes, curriculo_detalhes.
"""

import sqlite3
import os
from contextlib import closing

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, DATA_DIR


def clean_value(value):
    """Limpa valor para inserção no banco."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


class DatabaseManager:
    """Gerencia o banco SQLite com dados de toda a rede federal."""

    def __init__(self, db_name=None):
        self.db_name = db_name or DB_PATH
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)
        self._create_tables()

    def _connect(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _create_tables(self):
        with closing(self._connect()) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS professores (
                    professor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sigla TEXT NOT NULL,
                    nome TEXT,
                    campus TEXT,
                    cargo TEXT,
                    slug TEXT NOT NULL,
                    url_final TEXT,
                    lattes_id TEXT,
                    resumo TEXT,
                    temas TEXT,
                    area_cnpq TEXT,
                    data_entrada_instituicao TEXT,
                    uf TEXT,
                    UNIQUE(sigla, slug)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tccs (
                    tcc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER NOT NULL,
                    slug_professor TEXT,
                    nome_professor TEXT,
                    sigla TEXT,
                    instituicao TEXT,
                    uf TEXT,
                    campus TEXT,
                    ano TEXT,
                    curso TEXT,
                    autores TEXT,
                    titulo TEXT,
                    resumo TEXT,
                    palavras_chaves TEXT,
                    FOREIGN KEY (professor_id) REFERENCES professores(professor_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artigos (
                    artigo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER NOT NULL,
                    slug_professor TEXT,
                    nome_professor TEXT,
                    sigla TEXT,
                    ano TEXT,
                    titulo TEXT,
                    journal TEXT,
                    doi TEXT,
                    palavras_chaves TEXT,
                    FOREIGN KEY (professor_id) REFERENCES professores(professor_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projetos (
                    projeto_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER NOT NULL,
                    slug_professor TEXT,
                    nome_professor TEXT,
                    sigla TEXT,
                    titulo TEXT,
                    descricao TEXT,
                    natureza TEXT,
                    equipe TEXT,
                    financiadores TEXT,
                    data_inicio TEXT,
                    data_fim TEXT,
                    FOREIGN KEY (professor_id) REFERENCES professores(professor_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS publicacoes (
                    publicacao_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER,
                    sigla TEXT,
                    slug_professor TEXT,
                    titulo TEXT,
                    tipo TEXT,
                    tipo_producao TEXT,
                    autor TEXT,
                    ano INTEGER,
                    campus TEXT,
                    lattes_id TEXT,
                    fonte TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curriculo_detalhes (
                    detalhe_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER NOT NULL,
                    sigla TEXT,
                    slug_professor TEXT,
                    categoria TEXT,
                    subcategoria TEXT,
                    titulo TEXT,
                    descricao TEXT,
                    ano_inicio TEXT,
                    ano_fim TEXT,
                    instituicao TEXT,
                    detalhes_json TEXT,
                    FOREIGN KEY (professor_id) REFERENCES professores(professor_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS formacao_academica (
                    formacao_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER NOT NULL,
                    sigla TEXT,
                    slug_professor TEXT,
                    nivel TEXT,
                    nome_curso TEXT,
                    nome_instituicao TEXT,
                    ano_inicio TEXT,
                    ano_conclusao TEXT,
                    status TEXT,
                    titulo_trabalho TEXT,
                    nome_orientador TEXT,
                    bolsa TEXT,
                    agencia_financiadora TEXT,
                    FOREIGN KEY (professor_id) REFERENCES professores(professor_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bancas (
                    banca_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    professor_id INTEGER NOT NULL,
                    sigla TEXT,
                    slug_professor TEXT,
                    tipo_banca TEXT,
                    natureza TEXT,
                    titulo TEXT,
                    ano TEXT,
                    nome_candidato TEXT,
                    nome_instituicao TEXT,
                    nome_curso TEXT,
                    FOREIGN KEY (professor_id) REFERENCES professores(professor_id)
                )
            """)
            # Índices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_formacao_prof ON formacao_academica(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_formacao_sigla ON formacao_academica(sigla)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bancas_prof ON bancas(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bancas_sigla ON bancas(sigla)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prof_sigla_slug ON professores(sigla, slug)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tccs_prof ON tccs(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artigos_prof ON artigos(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projetos_prof ON projetos(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pub_prof ON publicacoes(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_curriculo_prof ON curriculo_detalhes(professor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prof_sigla ON professores(sigla)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tccs_sigla ON tccs(sigla)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artigos_sigla ON artigos(sigla)")

    def save_professores(self, sigla, professores):
        """Salva lista de professores no banco."""
        if not professores:
            return
        rows = [
            (
                clean_value(sigla),
                clean_value(p.get("nome")),
                clean_value(p.get("campus")),
                clean_value(p.get("cargo")),
                clean_value(p.get("slug")),
                clean_value(p.get("url_final")),
                clean_value(p.get("lattes_id")),
                clean_value(p.get("resumo")),
                clean_value(p.get("temas")),
                clean_value(p.get("area_cnpq")),
                clean_value(p.get("data_entrada_instituicao")),
                clean_value(p.get("uf")),
            )
            for p in professores
            if p.get("slug")
        ]
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT OR REPLACE INTO professores
                (sigla, nome, campus, cargo, slug, url_final, lattes_id, resumo, temas, area_cnpq, data_entrada_instituicao, uf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def get_professor_id(self, sigla, slug):
        """Retorna o ID do professor pela sigla e slug."""
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "SELECT professor_id FROM professores WHERE sigla = ? AND slug = ?",
                (clean_value(sigla), clean_value(slug)),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def save_tccs(self, rows):
        """Salva TCCs no banco."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO tccs (
                    professor_id, slug_professor, nome_professor, sigla,
                    instituicao, uf, campus, ano, curso, autores,
                    titulo, resumo, palavras_chaves
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def save_artigos(self, rows):
        """Salva artigos no banco."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO artigos (
                    professor_id, slug_professor, nome_professor, sigla,
                    ano, titulo, journal, doi, palavras_chaves
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def save_projetos(self, rows):
        """Salva projetos no banco."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO projetos (
                    professor_id, slug_professor, nome_professor, sigla,
                    titulo, descricao, natureza, equipe, financiadores,
                    data_inicio, data_fim
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def save_publicacoes(self, rows):
        """Salva publicações no banco."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO publicacoes (
                    professor_id, sigla, slug_professor, titulo, tipo,
                    tipo_producao, autor, ano, campus, lattes_id, fonte
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def save_curriculo_detalhes(self, rows):
        """Salva detalhes do currículo (orientações, bancas, comissões, etc.)."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO curriculo_detalhes (
                    professor_id, sigla, slug_professor, categoria,
                    subcategoria, titulo, descricao, ano_inicio, ano_fim,
                    instituicao, detalhes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def save_formacao_academica(self, rows):
        """Salva formação acadêmica no banco."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO formacao_academica (
                    professor_id, sigla, slug_professor, nivel,
                    nome_curso, nome_instituicao, ano_inicio, ano_conclusao,
                    status, titulo_trabalho, nome_orientador, bolsa, agencia_financiadora
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def save_bancas(self, rows):
        """Salva participação em bancas no banco."""
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany("""
                INSERT INTO bancas (
                    professor_id, sigla, slug_professor, tipo_banca,
                    natureza, titulo, ano, nome_candidato,
                    nome_instituicao, nome_curso
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def get_all_professores(self, sigla=None):
        """Retorna todos os professores, opcionalmente filtrados por sigla."""
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            if sigla:
                cur = conn.execute("SELECT * FROM professores WHERE sigla = ?", (sigla,))
            else:
                cur = conn.execute("SELECT * FROM professores")
            return [dict(row) for row in cur.fetchall()]

    def get_status_summary(self):
        """Retorna resumo de dados por instituição."""
        resumo = {}
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT DISTINCT sigla FROM professores ORDER BY sigla")
            siglas = [row[0] for row in cur.fetchall()]
            for sigla in siglas:
                total_prof = conn.execute(
                    "SELECT COUNT(*) FROM professores WHERE sigla = ?", (sigla,)
                ).fetchone()[0]
                total_tcc = conn.execute(
                    "SELECT COUNT(*) FROM tccs WHERE sigla = ?", (sigla,)
                ).fetchone()[0]
                total_art = conn.execute(
                    "SELECT COUNT(*) FROM artigos WHERE sigla = ?", (sigla,)
                ).fetchone()[0]
                total_proj = conn.execute(
                    "SELECT COUNT(*) FROM projetos WHERE sigla = ?", (sigla,)
                ).fetchone()[0]
                total_pub = conn.execute(
                    "SELECT COUNT(*) FROM publicacoes WHERE sigla = ?", (sigla,)
                ).fetchone()[0]
                resumo[sigla] = {
                    "professores": total_prof,
                    "tccs": total_tcc,
                    "artigos": total_art,
                    "projetos": total_proj,
                    "publicacoes": total_pub,
                }
        return resumo

    def query_to_dataframe(self, query, params=None):
        """Executa query e retorna como lista de dicts."""
        import pandas as pd
        with closing(self._connect()) as conn:
            return pd.read_sql_query(query, conn, params=params or [])
