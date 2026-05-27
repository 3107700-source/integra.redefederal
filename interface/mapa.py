# -*- coding: utf-8 -*-
"""Módulo: Mapa Geográfico da Produção Acadêmica."""
import streamlit as st
import plotly.express as px
import pandas as pd
from interface.componentes import render_section_title, metric_destaque

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import INSTITUICOES


# Mapeamento sigla -> UF
SIGLA_UF = {sigla: info[2] for sigla, info in INSTITUICOES.items()}

GEOJSON_URL = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"


def exibir(df_prof, df_pub, df_tccs, df_artigos, df_projetos):
    """Exibe mapa geográfico da produção."""

    render_section_title("Distribuição Geográfica da Produção Acadêmica", "🗺️")

    # Unifica dados com UF
    registros = []

    if df_prof is not None and not df_prof.empty and "sigla" in df_prof.columns:
        for sigla in df_prof["sigla"].unique():
            uf = SIGLA_UF.get(sigla)
            if uf:
                n_prof = len(df_prof[df_prof["sigla"] == sigla])
                n_pub = len(df_pub[df_pub["sigla"] == sigla]) if df_pub is not None and not df_pub.empty and "sigla" in df_pub.columns else 0
                n_tcc = len(df_tccs[df_tccs["sigla"] == sigla]) if df_tccs is not None and not df_tccs.empty and "sigla" in df_tccs.columns else 0
                n_art = len(df_artigos[df_artigos["sigla"] == sigla]) if df_artigos is not None and not df_artigos.empty and "sigla" in df_artigos.columns else 0
                n_proj = len(df_projetos[df_projetos["sigla"] == sigla]) if df_projetos is not None and not df_projetos.empty and "sigla" in df_projetos.columns else 0
                registros.append({
                    "UF": uf,
                    "Instituição": sigla,
                    "Servidores": n_prof,
                    "Publicações": n_pub,
                    "TCCs": n_tcc,
                    "Artigos": n_art,
                    "Projetos": n_proj,
                    "Total": n_pub + n_tcc + n_art + n_proj,
                })

    if not registros:
        st.warning("Nenhum dado geográfico disponível.")
        return

    df_geo = pd.DataFrame(registros)

    # Agrupa por UF
    df_uf = df_geo.groupby("UF").agg({
        "Servidores": "sum",
        "Publicações": "sum",
        "TCCs": "sum",
        "Artigos": "sum",
        "Projetos": "sum",
        "Total": "sum",
        "Instituição": lambda x: ", ".join(sorted(set(x))),
    }).reset_index()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_destaque("Estados", len(df_uf), icon="🗺️")
    with col2:
        metric_destaque("Instituições", df_geo["Instituição"].nunique(), icon="🏫")
    with col3:
        metric_destaque("Total Servidores", f"{df_uf['Servidores'].sum():,}".replace(",", "."), icon="👥")
    with col4:
        metric_destaque("Total Produções", f"{df_uf['Total'].sum():,}".replace(",", "."), icon="📊")

    st.markdown("---")

    # Mapa coroplético
    metrica_mapa = st.selectbox(
        "Métrica para o mapa:",
        ["Total", "Servidores", "Publicações", "TCCs", "Artigos", "Projetos"],
        index=0
    )

    fig = px.choropleth(
        df_uf,
        geojson=GEOJSON_URL,
        locations="UF",
        featureidkey="properties.sigla",
        color=metrica_mapa,
        color_continuous_scale="Blues",
        hover_data=["Instituição", "Servidores", "Publicações", "TCCs", "Artigos", "Projetos"],
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        height=550,
        margin=dict(l=10, r=10, t=30, b=10),
        coloraxis_colorbar=dict(title=metrica_mapa)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Ranking por UF
    render_section_title("Ranking por Estado", "📊")

    df_rank = df_uf.sort_values("Total", ascending=True)
    fig_rank = px.bar(
        df_rank, x="Total", y="UF", orientation="h",
        color="Total", color_continuous_scale="Blues",
        hover_data=["Instituição", "Servidores"],
        text="Total"
    )
    fig_rank.update_traces(textposition="outside")
    fig_rank.update_layout(
        height=max(400, len(df_rank) * 28),
        showlegend=False, coloraxis_showscale=False,
        margin=dict(l=20, r=50, t=20, b=20),
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    # Tabela detalhada
    st.markdown("---")
    with st.expander("📋 Tabela Detalhada por Instituição"):
        st.dataframe(
            df_geo.sort_values("Total", ascending=False),
            use_container_width=True, hide_index=True
        )
