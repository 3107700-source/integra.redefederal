# -*- coding: utf-8 -*-
"""Módulo: Análise Temática - TCCs, Artigos e Projetos."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from interface.componentes import (
    metric_destaque, render_section_title, render_insight, extract_keywords
)


def exibir(df_tccs, df_artigos, df_projetos, filtros):
    """Exibe análise temática completa."""

    tab_tccs, tab_artigos, tab_projetos, tab_consolidado = st.tabs([
        "📝 TCCs", "🔬 Artigos Científicos", "🗂️ Projetos", "📊 Visão Consolidada"
    ])

    with tab_tccs:
        _render_tccs(df_tccs)

    with tab_artigos:
        _render_artigos(df_artigos)

    with tab_projetos:
        _render_projetos(df_projetos)

    with tab_consolidado:
        _render_consolidado(df_tccs, df_artigos, df_projetos)


def _render_tccs(df):
    """Aba de TCCs."""
    if df is None or df.empty:
        st.info("Nenhum TCC encontrado. Execute a extração primeiro.")
        return

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_destaque("Total de TCCs", f"{len(df):,}".replace(",", "."), icon="📝")
    with col2:
        metric_destaque("Orientadores", df["nome_professor"].nunique() if "nome_professor" in df.columns else 0, icon="👨‍🏫")
    with col3:
        metric_destaque("Cursos", df["curso"].nunique() if "curso" in df.columns else 0, icon="🎓")
    with col4:
        metric_destaque("Instituições", df["sigla"].nunique() if "sigla" in df.columns else 0, icon="🏫")

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        render_section_title("Produção Anual de TCCs", "📈")
        if "ano" in df.columns:
            df_ano = df.copy()
            df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
            df_ano = df_ano.dropna(subset=["ano"])
            df_ano = df_ano[df_ano["ano"] >= 2000]
            ano_counts = df_ano["ano"].value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.bar(ano_counts, x="Ano", y="Quantidade", text="Quantidade",
                         color_discrete_sequence=["#3B82F6"])
            fig.update_traces(textposition="outside")
            fig.update_layout(height=380, showlegend=False,
                              margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

            # Insight de crescimento
            if len(ano_counts) > 1:
                ultimo = ano_counts.iloc[-1]["Quantidade"]
                penultimo = ano_counts.iloc[-2]["Quantidade"]
                if penultimo > 0:
                    cresc = ((ultimo - penultimo) / penultimo) * 100
                    render_insight(
                        f"Crescimento no último ano: <strong>{cresc:+.1f}%</strong> "
                        f"({int(penultimo)} → {int(ultimo)} TCCs)",
                        "📊"
                    )

    with col_b:
        render_section_title("Top 10 Cursos", "🎓")
        if "curso" in df.columns:
            curso_counts = df["curso"].value_counts().head(10).reset_index()
            curso_counts.columns = ["Curso", "Quantidade"]
            fig = px.bar(curso_counts, x="Quantidade", y="Curso", orientation="h",
                         color="Quantidade", color_continuous_scale="Blues",
                         text="Quantidade")
            fig.update_traces(textposition="outside")
            fig.update_layout(height=380, showlegend=False, coloraxis_showscale=False,
                              yaxis=dict(autorange="reversed"),
                              margin=dict(l=20, r=40, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Temáticas
    render_section_title("Temáticas Mais Frequentes", "🏷️")
    kw_df = extract_keywords(df["palavras_chaves"] if "palavras_chaves" in df.columns else pd.Series())
    if not kw_df.empty:
        col_chart, col_table = st.columns([2, 1])
        with col_chart:
            fig = px.bar(kw_df.head(15), x="frequencia", y="termo", orientation="h",
                         color="frequencia", color_continuous_scale="Viridis",
                         text="frequencia")
            fig.update_traces(textposition="outside")
            fig.update_layout(height=450, showlegend=False, coloraxis_showscale=False,
                              yaxis=dict(autorange="reversed"),
                              margin=dict(l=20, r=40, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with col_table:
            st.dataframe(kw_df.head(20).rename(columns={"termo": "Tema", "frequencia": "Freq."}),
                         hide_index=True, height=450)

    # Top orientadores
    st.markdown("---")
    render_section_title("Top 10 Orientadores", "👨‍🏫")
    if "nome_professor" in df.columns:
        top_orient = df["nome_professor"].value_counts().head(10).reset_index()
        top_orient.columns = ["Orientador", "TCCs"]
        fig = px.bar(top_orient, x="TCCs", y="Orientador", orientation="h",
                     color="TCCs", color_continuous_scale="Greens", text="TCCs")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, showlegend=False, coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"),
                          margin=dict(l=20, r=40, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Tabela completa
    with st.expander("📋 Ver todos os TCCs"):
        cols_show = [c for c in ["titulo", "ano", "curso", "nome_professor", "campus", "sigla", "palavras_chaves"]
                     if c in df.columns]
        st.dataframe(df[cols_show].sort_values("ano", ascending=False) if "ano" in df.columns else df[cols_show],
                     use_container_width=True, height=400, hide_index=True)
        csv = df[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download TCCs (CSV)", csv, "tccs.csv", "text/csv")


def _render_artigos(df):
    """Aba de Artigos."""
    if df is None or df.empty:
        st.info("Nenhum artigo encontrado. Execute a extração primeiro.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_destaque("Total de Artigos", f"{len(df):,}".replace(",", "."), icon="🔬")
    with col2:
        metric_destaque("Autores", df["nome_professor"].nunique() if "nome_professor" in df.columns else 0, icon="✍️")
    with col3:
        metric_destaque("Periódicos", df["journal"].nunique() if "journal" in df.columns else 0, icon="📰")
    with col4:
        metric_destaque("Instituições", df["sigla"].nunique() if "sigla" in df.columns else 0, icon="🏫")

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        render_section_title("Artigos por Ano", "📈")
        if "ano" in df.columns:
            df_ano = df.copy()
            df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
            df_ano = df_ano.dropna(subset=["ano"])
            df_ano = df_ano[df_ano["ano"] >= 2000]
            ano_counts = df_ano["ano"].value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.line(ano_counts, x="Ano", y="Quantidade", markers=True,
                          color_discrete_sequence=["#F59E0B"])
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        render_section_title("Top 10 Periódicos", "📰")
        if "journal" in df.columns:
            journal_counts = df["journal"].dropna().value_counts().head(10).reset_index()
            journal_counts.columns = ["Periódico", "Quantidade"]
            fig = px.bar(journal_counts, x="Quantidade", y="Periódico", orientation="h",
                         color="Quantidade", color_continuous_scale="Oranges", text="Quantidade")
            fig.update_traces(textposition="outside")
            fig.update_layout(height=350, showlegend=False, coloraxis_showscale=False,
                              yaxis=dict(autorange="reversed"),
                              margin=dict(l=20, r=40, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # Temáticas
    st.markdown("---")
    render_section_title("Temáticas Mais Frequentes", "🏷️")
    kw_df = extract_keywords(df["palavras_chaves"] if "palavras_chaves" in df.columns else pd.Series())
    if not kw_df.empty:
        fig = px.bar(kw_df.head(15), x="frequencia", y="termo", orientation="h",
                     color="frequencia", color_continuous_scale="YlOrRd", text="frequencia")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=450, showlegend=False, coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"),
                          margin=dict(l=20, r=40, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Tabela
    with st.expander("📋 Ver todos os Artigos"):
        cols_show = [c for c in ["titulo", "ano", "journal", "nome_professor", "sigla", "doi", "palavras_chaves"]
                     if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True, height=400, hide_index=True)
        csv = df[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Artigos (CSV)", csv, "artigos.csv", "text/csv")


def _render_projetos(df):
    """Aba de Projetos."""
    if df is None or df.empty:
        st.info("Nenhum projeto encontrado. Execute a extração primeiro.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_destaque("Total de Projetos", f"{len(df):,}".replace(",", "."), icon="🗂️")
    with col2:
        metric_destaque("Pesquisadores", df["nome_professor"].nunique() if "nome_professor" in df.columns else 0, icon="🔬")
    with col3:
        metric_destaque("Naturezas", df["natureza"].nunique() if "natureza" in df.columns else 0, icon="🏷️")

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        render_section_title("Projetos por Natureza", "🏷️")
        if "natureza" in df.columns:
            nat_counts = df["natureza"].dropna().value_counts().reset_index()
            nat_counts.columns = ["Natureza", "Quantidade"]
            fig = px.pie(nat_counts, values="Quantidade", names="Natureza",
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        render_section_title("Projetos por Ano de Início", "📅")
        if "data_inicio" in df.columns:
            df_p = df.copy()
            df_p["ano_inicio"] = df_p["data_inicio"].str[:4]
            df_p["ano_inicio"] = pd.to_numeric(df_p["ano_inicio"], errors="coerce")
            df_p = df_p.dropna(subset=["ano_inicio"])
            df_p = df_p[df_p["ano_inicio"] >= 2000]
            ano_counts = df_p["ano_inicio"].value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.bar(ano_counts, x="Ano", y="Quantidade", text="Quantidade",
                         color_discrete_sequence=["#8B5CF6"])
            fig.update_traces(textposition="outside")
            fig.update_layout(height=380, showlegend=False,
                              margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # Top pesquisadores em projetos
    st.markdown("---")
    render_section_title("Top 10 Pesquisadores com Mais Projetos", "🏆")
    if "nome_professor" in df.columns:
        top_pesq = df["nome_professor"].value_counts().head(10).reset_index()
        top_pesq.columns = ["Pesquisador", "Projetos"]
        fig = px.bar(top_pesq, x="Projetos", y="Pesquisador", orientation="h",
                     color="Projetos", color_continuous_scale="Purples", text="Projetos")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, showlegend=False, coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"),
                          margin=dict(l=20, r=40, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Tabela
    with st.expander("📋 Ver todos os Projetos"):
        cols_show = [c for c in ["titulo", "natureza", "nome_professor", "sigla",
                                  "data_inicio", "data_fim", "financiadores"]
                     if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True, height=400, hide_index=True)
        csv = df[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Projetos (CSV)", csv, "projetos.csv", "text/csv")


def _render_consolidado(df_tccs, df_artigos, df_projetos):
    """Visão consolidada de todas as temáticas."""
    render_section_title("Temáticas Consolidadas (TCCs + Artigos + Projetos)", "🌐")

    all_keywords = []
    for df, label, col in [
        (df_tccs, "TCC", "palavras_chaves"),
        (df_artigos, "Artigo", "palavras_chaves"),
    ]:
        if df is None or df.empty or col not in df.columns:
            continue
        for kws in df[col].dropna():
            for kw in str(kws).split(";"):
                kw = kw.strip().lower()
                if kw and len(kw) > 2:
                    all_keywords.append({"tema": kw, "tipo": label})

    if not all_keywords:
        st.info("Sem dados de palavras-chave disponíveis para análise consolidada.")
        return

    df_kw = pd.DataFrame(all_keywords)
    top_temas = df_kw["tema"].value_counts().head(20).index.tolist()
    df_kw_top = df_kw[df_kw["tema"].isin(top_temas)]

    # Gráfico empilhado
    pivot = df_kw_top.groupby(["tema", "tipo"]).size().reset_index(name="count")
    fig = px.bar(
        pivot, x="count", y="tema", color="tipo", orientation="h",
        color_discrete_map={"TCC": "#3B82F6", "Artigo": "#F59E0B", "Projeto": "#10B981"},
        labels={"count": "Frequência", "tema": "Tema", "tipo": "Tipo"}
    )
    fig.update_layout(
        height=600,
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Mapa de calor: Tema x Instituição
    st.markdown("---")
    render_section_title("Mapa de Calor: Temas × Instituições", "🗺️")

    # Combina dados com sigla
    all_data = []
    for df, col in [(df_tccs, "palavras_chaves"), (df_artigos, "palavras_chaves")]:
        if df is None or df.empty or col not in df.columns or "sigla" not in df.columns:
            continue
        for _, row in df[[col, "sigla"]].dropna().iterrows():
            for kw in str(row[col]).split(";"):
                kw = kw.strip().lower()
                if kw and len(kw) > 2 and kw in top_temas[:10]:
                    all_data.append({"tema": kw, "sigla": row["sigla"]})

    if all_data:
        df_heat = pd.DataFrame(all_data)
        top_siglas = df_heat["sigla"].value_counts().head(8).index.tolist()
        df_heat = df_heat[df_heat["sigla"].isin(top_siglas)]
        pivot = df_heat.pivot_table(index="tema", columns="sigla", values="tema",
                                     aggfunc="count", fill_value=0)
        fig_heat = px.imshow(
            pivot, labels=dict(x="Instituição", y="Tema", color="Frequência"),
            aspect="auto", color_continuous_scale="YlGnBu"
        )
        fig_heat.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_heat, use_container_width=True)
