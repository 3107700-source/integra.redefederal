"""
Módulo de transformação - Gera DataFrames processados a partir do banco SQLite.
Calcula métricas de ranking considerando todos os aspectos do currículo.
"""

import os
import sys

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PROCESSED_DIR, PROFESSORES_PROCESSED, PUBLICACOES_PROCESSED,
    PESOS_RANKING, PESOS_IMPACTO_PRODUCAO, PESOS_TITULACAO, DB_PATH
)
from etl.database import DatabaseManager


class IntegraTransformer:
    """Transforma dados do banco SQLite em DataFrames processados com ranking."""

    def __init__(self):
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        self.db = DatabaseManager()

    def load_professores(self, sigla=None) -> pd.DataFrame:
        """Carrega professores do banco."""
        query = "SELECT * FROM professores"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        return self.db.query_to_dataframe(query, params)

    def load_publicacoes(self, sigla=None) -> pd.DataFrame:
        """Carrega publicações do banco."""
        query = "SELECT * FROM publicacoes"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        return self.db.query_to_dataframe(query, params)

    def load_tccs(self, sigla=None) -> pd.DataFrame:
        """Carrega TCCs do banco."""
        query = "SELECT * FROM tccs"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        return self.db.query_to_dataframe(query, params)

    def load_artigos(self, sigla=None) -> pd.DataFrame:
        """Carrega artigos do banco."""
        query = "SELECT * FROM artigos"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        return self.db.query_to_dataframe(query, params)

    def load_projetos(self, sigla=None) -> pd.DataFrame:
        """Carrega projetos do banco."""
        query = "SELECT * FROM projetos"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        return self.db.query_to_dataframe(query, params)

    def load_curriculo_detalhes(self, sigla=None) -> pd.DataFrame:
        """Carrega detalhes do currículo."""
        query = "SELECT * FROM curriculo_detalhes"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        return self.db.query_to_dataframe(query, params)

    def load_formacao_academica(self, sigla=None) -> pd.DataFrame:
        """Carrega formação acadêmica do banco."""
        query = "SELECT * FROM formacao_academica"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        try:
            return self.db.query_to_dataframe(query, params)
        except Exception:
            return pd.DataFrame()

    def load_bancas(self, sigla=None) -> pd.DataFrame:
        """Carrega bancas do banco."""
        query = "SELECT * FROM bancas"
        params = []
        if sigla:
            query += " WHERE sigla = ?"
            params = [sigla]
        try:
            return self.db.query_to_dataframe(query, params)
        except Exception:
            return pd.DataFrame()

    def _normalize_series(self, series: pd.Series) -> pd.Series:
        """Normaliza série para 0-100."""
        min_val = series.min()
        max_val = series.max()
        if max_val == min_val:
            return pd.Series(50.0, index=series.index)
        return ((series - min_val) / (max_val - min_val)) * 100

    def calculate_ranking(self, df_prof: pd.DataFrame, df_pub: pd.DataFrame,
                          df_tccs: pd.DataFrame, df_projetos: pd.DataFrame,
                          df_detalhes: pd.DataFrame, df_formacao: pd.DataFrame = None,
                          df_bancas: pd.DataFrame = None) -> pd.DataFrame:
        """
        Calcula o IPA (Índice de Produtividade Acadêmica) considerando:
        - Publicações (quantidade)
        - Impacto (peso por tipo de produção)
        - Diversidade (tipos distintos)
        - Recência (publicação mais recente)
        - Orientações (TCCs + outras orientações)
        - Projetos (participação em projetos)
        - Tempo de docência
        - Comissões/Bancas
        - Extensão
        """
        if df_prof.empty:
            return df_prof

        df = df_prof.copy()

        # ─── Publicações ───
        if not df_pub.empty:
            df_pub_copy = df_pub.copy()
            df_pub_copy["peso"] = df_pub_copy["tipo"].map(PESOS_IMPACTO_PRODUCAO).fillna(1)
            df_pub_copy["ano"] = pd.to_numeric(df_pub_copy["ano"], errors="coerce")

            pub_stats = df_pub_copy.groupby("slug_professor").agg(
                total_publicacoes=("titulo", "count"),
                tipos_distintos=("tipo", "nunique"),
                ano_mais_recente=("ano", "max"),
                pub_impacto=("peso", "sum"),
            ).reset_index().rename(columns={"slug_professor": "slug"})

            df = df.merge(pub_stats, on="slug", how="left")
        else:
            df["total_publicacoes"] = 0
            df["tipos_distintos"] = 0
            df["ano_mais_recente"] = 0
            df["pub_impacto"] = 0

        # ─── Orientações ───
        if not df_tccs.empty:
            orient_stats = df_tccs.groupby("slug_professor").agg(
                total_orientacoes=("tcc_id", "count"),
            ).reset_index().rename(columns={"slug_professor": "slug"})
            df = df.merge(orient_stats, on="slug", how="left")
        else:
            df["total_orientacoes"] = 0

        # Adiciona orientações do currículo_detalhes
        if not df_detalhes.empty:
            orient_det = df_detalhes[df_detalhes["categoria"].isin(["orientacao_concluida", "orientacao_andamento"])]
            if not orient_det.empty:
                orient_det_stats = orient_det.groupby("slug_professor").size().reset_index(name="orientacoes_curriculo")
                orient_det_stats = orient_det_stats.rename(columns={"slug_professor": "slug"})
                df = df.merge(orient_det_stats, on="slug", how="left")
                df["orientacoes_curriculo"] = df["orientacoes_curriculo"].fillna(0)
                df["total_orientacoes"] = df["total_orientacoes"].fillna(0) + df["orientacoes_curriculo"]
                df = df.drop(columns=["orientacoes_curriculo"])

        # ─── Projetos ───
        if not df_projetos.empty:
            proj_stats = df_projetos.groupby("slug_professor").agg(
                total_projetos=("projeto_id", "count"),
            ).reset_index().rename(columns={"slug_professor": "slug"})
            df = df.merge(proj_stats, on="slug", how="left")
        else:
            df["total_projetos"] = 0

        # ─── Tempo de docência, Bancas, Extensão ───
        if not df_detalhes.empty:
            # Ensino
            ensino = df_detalhes[df_detalhes["categoria"] == "ensino"]
            if not ensino.empty:
                ensino_stats = ensino.groupby("slug_professor").size().reset_index(name="atividades_ensino")
                ensino_stats = ensino_stats.rename(columns={"slug_professor": "slug"})
                df = df.merge(ensino_stats, on="slug", how="left")
            else:
                df["atividades_ensino"] = 0

            # Bancas
            bancas = df_detalhes[df_detalhes["categoria"] == "banca"]
            if not bancas.empty:
                banca_stats = bancas.groupby("slug_professor").size().reset_index(name="total_bancas")
                banca_stats = banca_stats.rename(columns={"slug_professor": "slug"})
                df = df.merge(banca_stats, on="slug", how="left")
            else:
                df["total_bancas"] = 0

            # Extensão
            extensao = df_detalhes[df_detalhes["categoria"] == "extensao"]
            if not extensao.empty:
                ext_stats = extensao.groupby("slug_professor").size().reset_index(name="total_extensao")
                ext_stats = ext_stats.rename(columns={"slug_professor": "slug"})
                df = df.merge(ext_stats, on="slug", how="left")
            else:
                df["total_extensao"] = 0

            # Tempo de atuação profissional (proxy para tempo de docência)
            atuacao = df_detalhes[df_detalhes["categoria"] == "atuacao_profissional"]
            if not atuacao.empty:
                atuacao_c = atuacao.copy()
                atuacao_c["ano_inicio_num"] = pd.to_numeric(atuacao_c["ano_inicio"], errors="coerce")
                tempo = atuacao_c.groupby("slug_professor")["ano_inicio_num"].min().reset_index()
                tempo["anos_atuacao"] = 2026 - tempo["ano_inicio_num"]
                tempo = tempo.rename(columns={"slug_professor": "slug"})
                df = df.merge(tempo[["slug", "anos_atuacao"]], on="slug", how="left")
            else:
                df["anos_atuacao"] = 0
        else:
            df["atividades_ensino"] = 0
            df["total_bancas"] = 0
            df["total_extensao"] = 0
            df["anos_atuacao"] = 0

        # Preenche NaN
        for col in ["total_publicacoes", "tipos_distintos", "ano_mais_recente",
                    "pub_impacto", "total_orientacoes", "total_projetos",
                    "atividades_ensino", "total_bancas", "total_extensao", "anos_atuacao"]:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # ─── Titulação (formação acadêmica) ───
        if df_formacao is not None and not df_formacao.empty:
            # Atribui pontuação pela maior titulação
            df_formacao_c = df_formacao.copy()
            df_formacao_c["peso_titulacao"] = df_formacao_c["nivel"].map(PESOS_TITULACAO).fillna(0)
            # Pega a maior titulação de cada professor
            titulacao_max = df_formacao_c.groupby("slug_professor").agg(
                titulacao_score=("peso_titulacao", "max"),
                total_formacoes=("formacao_id", "count"),
            ).reset_index().rename(columns={"slug_professor": "slug"})
            df = df.merge(titulacao_max, on="slug", how="left")
        else:
            df["titulacao_score"] = 0
            df["total_formacoes"] = 0

        # ─── Bancas (estruturadas) ───
        if df_bancas is not None and not df_bancas.empty:
            bancas_stats = df_bancas.groupby("slug_professor").agg(
                total_bancas_estruturadas=("banca_id", "count"),
            ).reset_index().rename(columns={"slug_professor": "slug"})
            df = df.merge(bancas_stats, on="slug", how="left")
            # Usa bancas estruturadas se disponíveis, senão mantém as do curriculo_detalhes
            df["total_bancas_final"] = df["total_bancas_estruturadas"].fillna(0)
            df.loc[df["total_bancas_final"] == 0, "total_bancas_final"] = df["total_bancas"]
        else:
            df["total_bancas_estruturadas"] = 0
            df["total_bancas_final"] = df["total_bancas"]

        # ─── Gestão acadêmica (extraída do resumo) ───
        import re
        gestao_patterns = [
            r'\b(coordenad[oa]r?[ao]? de curso|coordena[çc][aã]o de curso)\b',
            r'\b(n[uú]cleo docente estruturante)\b',
            r'\b(colegiado|conselho de curso)\b',
            r'\b(diret[oa]r?[ao]? (?:de|do|da)|dire[çc][aã]o|pr[oó]-reit)\b',
            r'\b(chefe de departamento|chefia|coordenad[oa]r?[ao]? de [aá]rea)\b',
            r'\b(comiss[aã]o|membro de comit[eê])\b',
        ]

        def count_gestao(resumo):
            if not resumo or not isinstance(resumo, str):
                return 0
            text = resumo.lower()
            score = 0
            for pat in gestao_patterns:
                if re.search(pat, text):
                    score += 1
            return score

        df["gestao_score"] = df["resumo"].apply(count_gestao)

        # Preenche NaN finais
        for col in ["titulacao_score", "total_formacoes", "total_bancas_final", "gestao_score"]:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # ─── Calcula IPA ───
        df["score_publicacoes"] = self._normalize_series(df["total_publicacoes"])
        df["score_impacto"] = self._normalize_series(df["pub_impacto"])
        df["score_diversidade"] = self._normalize_series(df["tipos_distintos"])
        df["score_recencia"] = self._normalize_series(df["ano_mais_recente"])
        df["score_orientacoes"] = self._normalize_series(df["total_orientacoes"])
        df["score_projetos"] = self._normalize_series(df["total_projetos"])
        df["score_tempo_docencia"] = self._normalize_series(df["anos_atuacao"])
        df["score_comissoes_bancas"] = self._normalize_series(df["total_bancas_final"])
        df["score_extensao"] = self._normalize_series(df["total_extensao"])
        df["score_titulacao"] = self._normalize_series(df["titulacao_score"])
        df["score_gestao_academica"] = self._normalize_series(df["gestao_score"])

        # IPA final
        df["ipa"] = (
            df["score_publicacoes"] * PESOS_RANKING["publicacoes"] +
            df["score_impacto"] * PESOS_RANKING["impacto"] +
            df["score_diversidade"] * PESOS_RANKING["diversidade"] +
            df["score_recencia"] * PESOS_RANKING["recencia"] +
            df["score_orientacoes"] * PESOS_RANKING["orientacoes"] +
            df["score_projetos"] * PESOS_RANKING["projetos"] +
            df["score_tempo_docencia"] * PESOS_RANKING["tempo_docencia"] +
            df["score_comissoes_bancas"] * PESOS_RANKING["comissoes_bancas"] +
            df["score_extensao"] * PESOS_RANKING["extensao"] +
            df["score_titulacao"] * PESOS_RANKING["titulacao"] +
            df["score_gestao_academica"] * PESOS_RANKING["gestao_academica"]
        )

        df["is_docente"] = df["cargo"].str.contains("Docente", case=False, na=False)

        return df

    def run(self, sigla=None) -> tuple:
        """Executa transformação completa."""
        print("\n🔄 Iniciando transformação dos dados...")

        df_prof = self.load_professores(sigla)
        df_pub = self.load_publicacoes(sigla)
        df_tccs = self.load_tccs(sigla)
        df_projetos = self.load_projetos(sigla)
        df_detalhes = self.load_curriculo_detalhes(sigla)
        df_formacao = self.load_formacao_academica(sigla)
        df_bancas = self.load_bancas(sigla)

        print(f"  Professores: {len(df_prof)}")
        print(f"  Publicações: {len(df_pub)}")
        print(f"  TCCs: {len(df_tccs)}")
        print(f"  Projetos: {len(df_projetos)}")
        print(f"  Detalhes currículo: {len(df_detalhes)}")
        print(f"  Formação acadêmica: {len(df_formacao)}")
        print(f"  Bancas: {len(df_bancas)}")

        # Calcula ranking
        df_prof = self.calculate_ranking(df_prof, df_pub, df_tccs, df_projetos, df_detalhes, df_formacao, df_bancas)

        # Salva CSVs
        if not df_prof.empty:
            df_prof.to_csv(PROFESSORES_PROCESSED, index=False, encoding="utf-8")
        if not df_pub.empty:
            df_pub.to_csv(PUBLICACOES_PROCESSED, index=False, encoding="utf-8")

        print(f"\n✓ Dados transformados salvos.")
        return df_prof, df_pub, df_tccs, df_projetos, df_detalhes


if __name__ == "__main__":
    transformer = IntegraTransformer()
    transformer.run()
