# -*- coding: utf-8 -*-
"""Módulo: Visão Geral - Comparação entre TCCs, Artigos e Projetos."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from interface.componentes import metric_destaque, render_section_title, render_insight


def exibir(df_prof, df_pub, df_tccs, df_artigos, df_projetos, filtros):
    """Exibe visão geral consolidada da produção acadêmica."""

    # ── MÉTRICAS GERAIS ───────────────────────────────────────────────────────
    total_geral = len(df_tccs) + len(df_artigos) + len(df_projetos) + len(df_pub)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        metric_destaque("Servidores", f"{len(df_prof):,}".replace(",", "."), icon="👥")
    with col2:
        metric_destaque("Publicações", f"{len(df_pub):,}".replace(",", "."), icon="📄")
    with col3:
        metric_destaque("TCCs Orientados", f"{len(df_tccs):,}".replace(",", "."), icon="📝")
    with col4:
        metric_destaque("Artigos", f"{len(df_artigos):,}".replace(",", "."), icon="🔬")
    with col5:
        metric_destaque("Projetos", f"{len(df_projetos):,}".replace(",", "."), icon="🗂️")

    st.markdown("---")

    # ── EVOLUÇÃO TEMPORAL ─────────────────────────────────────────────────────
    render_section_title("Evolução Temporal da Produção", "📈")

    # Publicações por ano
    if not df_pub.empty and "ano" in df_pub.columns:
        df_pub_ano = df_pub.copy()
        df_pub_ano["ano"] = pd.to_numeric(df_pub_ano["ano"], errors="coerce")
        df_pub_ano = df_pub_ano.dropna(subset=["ano"])
        df_pub_ano = df_pub_ano[df_pub_ano["ano"] >= 2000]
        pub_por_ano = df_pub_ano.groupby("ano").size().reset_index(name="count")
        pub_por_ano["tipo"] = "Publicações"
    else:
        pub_por_ano = pd.DataFrame()

    # TCCs por ano
    if not df_tccs.empty and "ano" in df_tccs.columns:
        df_tcc_ano = df_tccs.copy()
        df_tcc_ano["ano"] = pd.to_numeric(df_tcc_ano["ano"], errors="coerce")
        df_tcc_ano = df_tcc_ano.dropna(subset=["ano"])
        df_tcc_ano = df_tcc_ano[df_tcc_ano["ano"] >= 2000]
        tcc_por_ano = df_tcc_ano.groupby("ano").size().reset_index(name="count")
        tcc_por_ano["tipo"] = "TCCs"
    else:
        tcc_por_ano = pd.DataFrame()

    # Artigos por ano
    if not df_artigos.empty and "ano" in df_artigos.columns:
        df_art_ano = df_artigos.copy()
        df_art_ano["ano"] = pd.to_numeric(df_art_ano["ano"], errors="coerce")
        df_art_ano = df_art_ano.dropna(subset=["ano"])
        df_art_ano = df_art_ano[df_art_ano["ano"] >= 2000]
        art_por_ano = df_art_ano.groupby("ano").size().reset_index(name="count")
        art_por_ano["tipo"] = "Artigos"
    else:
        art_por_ano = pd.DataFrame()

    df_tempo = pd.concat([pub_por_ano, tcc_por_ano, art_por_ano], ignore_index=True)

    if not df_tempo.empty:
        fig = px.line(
            df_tempo, x="ano", y="count", color="tipo",
            markers=True,
            labels={"count": "Quantidade", "ano": "Ano", "tipo": "Tipo"},
            color_discrete_map={
                "Publicações": "#3B82F6",
                "TCCs": "#10B981",
                "Artigos": "#F59E0B"
            }
        )
        fig.update_layout(
            height=400,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── RANKING DE INSTITUIÇÕES ───────────────────────────────────────────────
    render_section_title("Ranking de Instituições por Produção", "🏫")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**📄 Top 10 — Publicações**")
        if not df_pub.empty and "sigla" in df_pub.columns:
            top_pub = df_pub["sigla"].value_counts().head(10).reset_index()
            top_pub.columns = ["Instituição", "Quantidade"]
            fig1 = px.bar(top_pub, x="Instituição", y="Quantidade",
                          color_discrete_sequence=["#3B82F6"], text="Quantidade")
            fig1.update_traces(textposition="outside")
            fig1.update_layout(height=350, showlegend=False, xaxis_tickangle=-30,
                               margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown("**📝 Top 10 — TCCs**")
        if not df_tccs.empty and "sigla" in df_tccs.columns:
            top_tcc = df_tccs["sigla"].value_counts().head(10).reset_index()
            top_tcc.columns = ["Instituição", "Quantidade"]
            fig2 = px.bar(top_tcc, x="Instituição", y="Quantidade",
                          color_discrete_sequence=["#10B981"], text="Quantidade")
            fig2.update_traces(textposition="outside")
            fig2.update_layout(height=350, showlegend=False, xaxis_tickangle=-30,
                               margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    with col3:
        st.markdown("**🔬 Top 10 — Artigos**")
        if not df_artigos.empty and "sigla" in df_artigos.columns:
            top_art = df_artigos["sigla"].value_counts().head(10).reset_index()
            top_art.columns = ["Instituição", "Quantidade"]
            fig3 = px.bar(top_art, x="Instituição", y="Quantidade",
                          color_discrete_sequence=["#F59E0B"], text="Quantidade")
            fig3.update_traces(textposition="outside")
            fig3.update_layout(height=350, showlegend=False, xaxis_tickangle=-30,
                               margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")

    # ── COMPARAÇÃO POR IF ─────────────────────────────────────────────────────
    render_section_title("Comparação por Instituição", "📊")

    if not df_pub.empty and "sigla" in df_pub.columns:
        top_inst = df_pub["sigla"].value_counts().head(10).index.tolist()
        df_comp = pd.DataFrame({
            "Instituição": top_inst,
            "Publicações": [len(df_pub[df_pub["sigla"] == i]) for i in top_inst],
            "TCCs": [len(df_tccs[df_tccs["sigla"] == i]) if not df_tccs.empty and "sigla" in df_tccs.columns else 0 for i in top_inst],
            "Artigos": [len(df_artigos[df_artigos["sigla"] == i]) if not df_artigos.empty and "sigla" in df_artigos.columns else 0 for i in top_inst],
            "Projetos": [len(df_projetos[df_projetos["sigla"] == i]) if not df_projetos.empty and "sigla" in df_projetos.columns else 0 for i in top_inst],
        })
        df_melted = df_comp.melt(id_vars="Instituição", var_name="Tipo", value_name="Quantidade")
        fig_comp = px.bar(
            df_melted, x="Instituição", y="Quantidade", color="Tipo",
            barmode="group",
            color_discrete_map={
                "Publicações": "#3B82F6", "TCCs": "#10B981",
                "Artigos": "#F59E0B", "Projetos": "#8B5CF6"
            },
            text="Quantidade"
        )
        fig_comp.update_traces(textposition="outside", textfont_size=9)
        fig_comp.update_layout(
            height=450, xaxis_tickangle=-30,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_comp, use_container_width=True)

    # ── DISTRIBUIÇÃO POR ÁREA CNPq ────────────────────────────────────────────
    if "area_cnpq" in df_prof.columns:
        st.markdown("---")
        render_section_title("Distribuição por Área do Conhecimento (CNPq)", "🧠")

        col_a, col_b = st.columns(2)
        with col_a:
            area_counts = df_prof["area_cnpq"].value_counts().reset_index()
            area_counts.columns = ["Área", "Quantidade"]
            area_counts = area_counts[area_counts["Área"] != "Não Classificado"]
            fig_area = px.pie(
                area_counts, values="Quantidade", names="Área",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_area.update_traces(textinfo="percent+label", textposition="outside")
            fig_area.update_layout(height=420, showlegend=False,
                                   margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_area, use_container_width=True)

        with col_b:
            # Área por campus (heatmap)
            if "campus" in df_prof.columns:
                top_campus = df_prof["campus"].value_counts().head(8).index.tolist()
                top_areas = area_counts.head(6)["Área"].tolist()
                df_heat = df_prof[
                    (df_prof["campus"].isin(top_campus)) &
                    (df_prof["area_cnpq"].isin(top_areas))
                ]
                if not df_heat.empty:
                    pivot = df_heat.pivot_table(
                        index="area_cnpq", columns="campus",
                        values="slug", aggfunc="count", fill_value=0
                    )
                    fig_heat = px.imshow(
                        pivot, labels=dict(x="Campus", y="Área CNPq", color="Servidores"),
                        aspect="auto", color_continuous_scale="Blues"
                    )
                    fig_heat.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig_heat, use_container_width=True)
