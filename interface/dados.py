# -*- coding: utf-8 -*-
"""Módulo de carregamento e cache de dados."""
import os
import sqlite3

import streamlit as st
import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, CLUSTERS_OUTPUT, PUBLICACOES_PROCESSED, PROFESSORES_PROCESSED
from config import INSTITUICOES, PESOS_RANKING, PESOS_IMPACTO_PRODUCAO


@st.cache_data(ttl=300)
def carregar_dados():
    """Carrega todos os dados do banco SQLite."""
    if not os.path.exists(DB_PATH):
        return None, None, None, None, None, None

    conn = sqlite3.connect(DB_PATH)
    try:
        df_prof = pd.read_sql_query("SELECT * FROM professores", conn)
        df_pub = pd.read_sql_query("SELECT * FROM publicacoes", conn)
        df_tccs = pd.read_sql_query("SELECT * FROM tccs", conn)
        df_artigos = pd.read_sql_query("SELECT * FROM artigos", conn)
        df_projetos = pd.read_sql_query("SELECT * FROM projetos", conn)
        df_detalhes = pd.read_sql_query("SELECT * FROM curriculo_detalhes", conn)
    except Exception:
        return None, None, None, None, None, None
    finally:
        conn.close()

    # Carrega clusters se existir
    if os.path.exists(CLUSTERS_OUTPUT):
        df_clusters = pd.read_csv(CLUSTERS_OUTPUT, encoding="utf-8")
        # Merge cluster info into prof
        cluster_cols = [c for c in df_clusters.columns if c not in df_prof.columns or c == "slug"]
        if "cluster_kmeans" in df_clusters.columns:
            df_prof = df_prof.merge(
                df_clusters[["slug", "cluster_kmeans", "pca_x", "pca_y"]].drop_duplicates("slug"),
                on="slug", how="left"
            )

    return df_prof, df_pub, df_tccs, df_artigos, df_projetos, df_detalhes


def calcular_ranking(df_prof, df_pub, df_tccs, df_projetos, df_detalhes):
    """Calcula IPA se não existir."""
    if df_prof is None or df_prof.empty:
        return df_prof
    if "ipa" in df_prof.columns:
        return df_prof

    df = df_prof.copy()

    # Publicações
    if df_pub is not None and not df_pub.empty:
        df_pub_c = df_pub.copy()
        df_pub_c["peso"] = df_pub_c["tipo"].map(PESOS_IMPACTO_PRODUCAO).fillna(1)
        df_pub_c["ano"] = pd.to_numeric(df_pub_c["ano"], errors="coerce")
        pub_stats = df_pub_c.groupby("slug_professor").agg(
            total_publicacoes=("titulo", "count"),
            tipos_distintos=("tipo", "nunique"),
            ano_mais_recente=("ano", "max"),
            pub_impacto=("peso", "sum"),
        ).reset_index().rename(columns={"slug_professor": "slug"})
        df = df.merge(pub_stats, on="slug", how="left")
    else:
        for col in ["total_publicacoes", "tipos_distintos", "ano_mais_recente", "pub_impacto"]:
            if col not in df.columns:
                df[col] = 0

    # Orientações
    if df_tccs is not None and not df_tccs.empty:
        orient = df_tccs.groupby("slug_professor").size().reset_index(name="total_orientacoes")
        orient = orient.rename(columns={"slug_professor": "slug"})
        df = df.merge(orient, on="slug", how="left")
    if "total_orientacoes" not in df.columns:
        df["total_orientacoes"] = 0

    # Projetos
    if df_projetos is not None and not df_projetos.empty:
        proj = df_projetos.groupby("slug_professor").size().reset_index(name="total_projetos")
        proj = proj.rename(columns={"slug_professor": "slug"})
        df = df.merge(proj, on="slug", how="left")
    if "total_projetos" not in df.columns:
        df["total_projetos"] = 0

    # Detalhes
    if df_detalhes is not None and not df_detalhes.empty:
        bancas = df_detalhes[df_detalhes["categoria"] == "banca"]
        if not bancas.empty:
            b_stats = bancas.groupby("slug_professor").size().reset_index(name="total_bancas")
            b_stats = b_stats.rename(columns={"slug_professor": "slug"})
            df = df.merge(b_stats, on="slug", how="left")

        extensao = df_detalhes[df_detalhes["categoria"] == "extensao"]
        if not extensao.empty:
            e_stats = extensao.groupby("slug_professor").size().reset_index(name="total_extensao")
            e_stats = e_stats.rename(columns={"slug_professor": "slug"})
            df = df.merge(e_stats, on="slug", how="left")

        ensino = df_detalhes[df_detalhes["categoria"] == "ensino"]
        if not ensino.empty:
            en_stats = ensino.groupby("slug_professor").size().reset_index(name="atividades_ensino")
            en_stats = en_stats.rename(columns={"slug_professor": "slug"})
            df = df.merge(en_stats, on="slug", how="left")

    # Preenche NaN
    for col in ["total_publicacoes", "tipos_distintos", "ano_mais_recente",
                "pub_impacto", "total_orientacoes", "total_projetos",
                "total_bancas", "total_extensao", "atividades_ensino"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    # Normaliza
    def norm(s):
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50.0, index=s.index)
        return ((s - mn) / (mx - mn)) * 100

    df["score_publicacoes"] = norm(df["total_publicacoes"])
    df["score_impacto"] = norm(df["pub_impacto"])
    df["score_diversidade"] = norm(df["tipos_distintos"])
    df["score_recencia"] = norm(df["ano_mais_recente"])
    df["score_orientacoes"] = norm(df["total_orientacoes"])
    df["score_projetos"] = norm(df["total_projetos"])
    df["score_tempo_docencia"] = norm(df["atividades_ensino"])
    df["score_comissoes_bancas"] = norm(df["total_bancas"])
    df["score_extensao"] = norm(df["total_extensao"])

    df["ipa"] = (
        df["score_publicacoes"] * PESOS_RANKING["publicacoes"] +
        df["score_impacto"] * PESOS_RANKING["impacto"] +
        df["score_diversidade"] * PESOS_RANKING["diversidade"] +
        df["score_recencia"] * PESOS_RANKING["recencia"] +
        df["score_orientacoes"] * PESOS_RANKING["orientacoes"] +
        df["score_projetos"] * PESOS_RANKING["projetos"] +
        df["score_tempo_docencia"] * PESOS_RANKING["tempo_docencia"] +
        df["score_comissoes_bancas"] * PESOS_RANKING["comissoes_bancas"] +
        df["score_extensao"] * PESOS_RANKING["extensao"]
    )

    df["is_docente"] = df["cargo"].str.contains("Docente", case=False, na=False) if "cargo" in df.columns else False
    return df


def get_instituicoes_info():
    """Retorna dicionário de instituições."""
    return INSTITUICOES
