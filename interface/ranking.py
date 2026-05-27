# -*- coding: utf-8 -*-
"""Módulo: Ranking & Publicações."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from interface.componentes import metric_destaque, render_section_title, render_insight

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PESOS_RANKING, PESOS_IMPACTO_PRODUCAO


def exibir(df_prof, df_pub, df_detalhes, filtros):
    """Exibe ranking e publicações."""

    tab_ranking, tab_pub, tab_historico, tab_detalhes = st.tabs([
        "🏅 Ranking IPA", "📄 Publicações", "👤 Perfil do Servidor", "📐 Metodologia"
    ])

    with tab_ranking:
        _render_ranking(df_prof)

    with tab_pub:
        _render_publicacoes(df_pub, filtros)

    with tab_historico:
        _render_perfil_servidor(df_prof, df_pub, df_detalhes)

    with tab_detalhes:
        _render_metodologia(df_prof)


def _render_ranking(df_prof):
    """Aba de ranking."""
    if df_prof is None or df_prof.empty or "ipa" not in df_prof.columns:
        st.info("Dados de ranking não disponíveis. Execute o pipeline primeiro.")
        return

    df_rank = df_prof.sort_values("ipa", ascending=False).reset_index(drop=True)
    df_rank["posicao"] = range(1, len(df_rank) + 1)

    # Top 3 com destaque
    render_section_title("Pódio - Top 3 Pesquisadores", "🏆")
    medals = ["🥇", "🥈", "🥉"]
    colors = ["#FFD700", "#C0C0C0", "#CD7F32"]

    cols = st.columns(3)
    for i, col in enumerate(cols):
        if i < len(df_rank):
            row = df_rank.iloc[i]
            with col:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {colors[i]}22, {colors[i]}11);
                            border: 2px solid {colors[i]}; border-radius: 16px;
                            padding: 1.5rem; text-align: center;">
                    <div style="font-size: 2.5rem;">{medals[i]}</div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #1E293B; margin: 8px 0;">
                        {row.get('nome', 'N/A')}
                    </div>
                    <div style="font-size: 1.8rem; font-weight: 800; color: #1E40AF;">
                        {row['ipa']:.1f}
                    </div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-top: 4px;">
                        {row.get('sigla', '')} • {row.get('campus', '')}
                    </div>
                    <div style="font-size: 0.75rem; color: #64748B;">
                        {row.get('area_cnpq', '') if 'area_cnpq' in row.index else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # Top 20 gráfico
    render_section_title("Top 20 - Índice de Produtividade Acadêmica", "📊")
    top20 = df_rank.head(20)
    fig = px.bar(
        top20, x="ipa", y="nome", orientation="h",
        color="ipa", color_continuous_scale="Viridis",
        text=top20["ipa"].round(1),
        hover_data=["sigla", "campus"] + (["area_cnpq"] if "area_cnpq" in top20.columns else []),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=600, coloraxis_showscale=False,
        yaxis=dict(autorange="reversed"),
        margin=dict(l=20, r=60, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Composição do IPA
    st.markdown("---")
    render_section_title("Composição do IPA (Pesos)", "⚖️")
    col_pie, col_table = st.columns([1, 1])

    with col_pie:
        pesos_df = pd.DataFrame([
            {"Componente": k.replace("_", " ").title(), "Peso": v * 100}
            for k, v in PESOS_RANKING.items()
        ])
        fig = px.pie(pesos_df, values="Peso", names="Componente",
                     hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
        fig.update_traces(textinfo="percent+label", textposition="inside")
        fig.update_layout(height=380, showlegend=False,
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        pesos_info = pd.DataFrame([
            {"Componente": "Publicações", "Peso": "20%", "Descrição": "Total de publicações"},
            {"Componente": "Impacto", "Peso": "15%", "Descrição": "Soma ponderada por tipo"},
            {"Componente": "Orientações", "Peso": "15%", "Descrição": "TCCs + outras orientações"},
            {"Componente": "Diversidade", "Peso": "10%", "Descrição": "Tipos distintos de produção"},
            {"Componente": "Recência", "Peso": "10%", "Descrição": "Publicação mais recente"},
            {"Componente": "Projetos", "Peso": "10%", "Descrição": "Projetos de pesquisa"},
            {"Componente": "Tempo Docência", "Peso": "10%", "Descrição": "Atividades de ensino"},
            {"Componente": "Bancas", "Peso": "5%", "Descrição": "Bancas examinadoras"},
            {"Componente": "Extensão", "Peso": "5%", "Descrição": "Atividades de extensão"},
        ])
        st.dataframe(pesos_info, hide_index=True, use_container_width=True)

    # Tabela completa
    st.markdown("---")
    with st.expander("📋 Ranking Completo"):
        cols_rank = [c for c in ["posicao", "nome", "sigla", "campus", "area_cnpq", "ipa",
                                  "total_publicacoes", "total_orientacoes", "total_projetos",
                                  "total_bancas", "total_extensao"] if c in df_rank.columns]
        st.dataframe(df_rank[cols_rank], use_container_width=True, height=500, hide_index=True)
        csv = df_rank[cols_rank].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Ranking (CSV)", csv, "ranking_completo.csv", "text/csv")


def _render_publicacoes(df_pub, filtros):
    """Aba de publicações."""
    if df_pub is None or df_pub.empty:
        st.info("Dados de publicações não disponíveis.")
        return

    df = df_pub.copy()
    if filtros.get("sigla"):
        df = df[df["sigla"].isin(filtros["sigla"])]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_destaque("Total", f"{len(df):,}".replace(",", "."), icon="📄")
    with col2:
        metric_destaque("Tipos", df["tipo"].nunique() if "tipo" in df.columns else 0, icon="📂")
    with col3:
        metric_destaque("Autores", df["autor"].nunique() if "autor" in df.columns else 0, icon="✍️")
    with col4:
        metric_destaque("Instituições", df["sigla"].nunique() if "sigla" in df.columns else 0, icon="🏫")

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        render_section_title("Tipos de Produção", "📂")
        if "tipo" in df.columns:
            tipo_counts = df["tipo"].value_counts().head(12).reset_index()
            tipo_counts.columns = ["Tipo", "Quantidade"]
            fig = px.bar(tipo_counts, x="Quantidade", y="Tipo", orientation="h",
                         color="Quantidade", color_continuous_scale="Blues", text="Quantidade")
            fig.update_traces(textposition="outside")
            fig.update_layout(height=420, showlegend=False, coloraxis_showscale=False,
                              yaxis=dict(autorange="reversed"),
                              margin=dict(l=20, r=50, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        render_section_title("Publicações por Ano", "📈")
        if "ano" in df.columns:
            df_ano = df.copy()
            df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
            df_ano = df_ano.dropna(subset=["ano"])
            df_ano = df_ano[df_ano["ano"] >= 2000]
            ano_counts = df_ano["ano"].value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.area(ano_counts, x="Ano", y="Quantidade",
                          color_discrete_sequence=["#3B82F6"])
            fig.update_layout(height=420, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # Por campus
    st.markdown("---")
    render_section_title("Publicações por Campus", "🏫")
    if "campus" in df.columns:
        campus_counts = df["campus"].dropna().value_counts().head(15).reset_index()
        campus_counts.columns = ["Campus", "Quantidade"]
        fig = px.bar(campus_counts, x="Quantidade", y="Campus", orientation="h",
                     color="Quantidade", color_continuous_scale="Greens", text="Quantidade")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=450, showlegend=False, coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"),
                          margin=dict(l=20, r=50, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Tabela
    with st.expander("📋 Ver todas as Publicações"):
        cols_show = [c for c in ["titulo", "tipo", "autor", "ano", "campus", "sigla"] if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True, height=400, hide_index=True)
        csv = df[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Publicações (CSV)", csv, "publicacoes.csv", "text/csv")


def _render_perfil_servidor(df_prof, df_pub, df_detalhes):
    """Perfil individual do servidor."""
    render_section_title("Perfil do Servidor", "👤")

    if df_prof is None or df_prof.empty:
        st.info("Sem dados de professores.")
        return

    nomes = sorted(df_prof["nome"].dropna().unique().tolist())
    nome_sel = st.selectbox("Selecione o servidor:", [""] + nomes, key="perfil_servidor")

    if not nome_sel:
        st.info("Selecione um servidor para ver o perfil completo.")
        return

    prof_row = df_prof[df_prof["nome"] == nome_sel].iloc[0]
    slug = prof_row.get("slug", "")

    # Info básica
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Instituição", prof_row.get("sigla", "N/A"))
    with col2:
        st.metric("Campus", prof_row.get("campus", "N/A"))
    with col3:
        st.metric("Cargo", prof_row.get("cargo", "N/A"))
    with col4:
        st.metric("Área CNPq", prof_row.get("area_cnpq", "N/A"))

    # Radar de competências
    if "ipa" in prof_row.index:
        st.markdown("---")
        render_section_title("Perfil de Produtividade", "📐")

        score_cols = [
            ("score_publicacoes", "Publicações"),
            ("score_impacto", "Impacto"),
            ("score_diversidade", "Diversidade"),
            ("score_recencia", "Recência"),
            ("score_orientacoes", "Orientações"),
            ("score_projetos", "Projetos"),
            ("score_tempo_docencia", "Docência"),
            ("score_comissoes_bancas", "Bancas"),
            ("score_extensao", "Extensão"),
        ]

        categories = [sc[1] for sc in score_cols]
        values = [float(prof_row.get(sc[0], 0)) for sc in score_cols]
        values_closed = values + [values[0]]
        categories_closed = categories + [categories[0]]

        col_radar, col_scores = st.columns([1, 1])

        with col_radar:
            fig = go.Figure(data=go.Scatterpolar(
                r=values_closed, theta=categories_closed,
                fill="toself", fillcolor="rgba(59, 130, 246, 0.15)",
                line=dict(color="#3B82F6", width=2),
                name=nome_sel
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                height=380, margin=dict(l=40, r=40, t=20, b=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_scores:
            st.metric("IPA Final", f"{prof_row.get('ipa', 0):.2f}")
            scores_data = []
            for sc_col, label in score_cols:
                scores_data.append({
                    "Componente": label,
                    "Score (0-100)": f"{prof_row.get(sc_col, 0):.1f}",
                })
            st.dataframe(pd.DataFrame(scores_data), hide_index=True, use_container_width=True)

    # Publicações do servidor
    if df_pub is not None and not df_pub.empty:
        pub_prof = df_pub[df_pub["slug_professor"] == slug].copy()
        if not pub_prof.empty:
            st.markdown("---")
            render_section_title(f"Publicações de {nome_sel}", "📄")
            pub_prof["ano"] = pd.to_numeric(pub_prof["ano"], errors="coerce")
            cols_show = [c for c in ["titulo", "tipo", "ano", "campus"] if c in pub_prof.columns]
            st.dataframe(
                pub_prof[cols_show].sort_values("ano", ascending=False),
                use_container_width=True, height=300, hide_index=True
            )

    # Detalhes do currículo
    if df_detalhes is not None and not df_detalhes.empty:
        det_prof = df_detalhes[df_detalhes["slug_professor"] == slug]
        if not det_prof.empty:
            st.markdown("---")
            render_section_title("Detalhes do Currículo", "📋")
            for cat in det_prof["categoria"].unique():
                cat_data = det_prof[det_prof["categoria"] == cat]
                with st.expander(f"{cat.replace('_', ' ').title()} ({len(cat_data)} registros)"):
                    cols_show = [c for c in ["subcategoria", "titulo", "descricao", "ano_inicio", "ano_fim", "instituicao"]
                                 if c in cat_data.columns]
                    st.dataframe(cat_data[cols_show], use_container_width=True, hide_index=True)


def _render_metodologia(df_prof):
    """Aba de metodologia do IPA."""
    render_section_title("Metodologia do IPA", "📐")

    st.markdown("""
    ### Índice de Produtividade Acadêmica (IPA)

    O IPA é uma métrica composta que avalia a produtividade dos servidores considerando
    **9 dimensões** da atuação acadêmica:

    ```
    IPA = (Pub × 0.20) + (Imp × 0.15) + (Ori × 0.15) + (Div × 0.10) + (Rec × 0.10)
        + (Proj × 0.10) + (Doc × 0.10) + (Ban × 0.05) + (Ext × 0.05)
    ```

    Cada componente é **normalizado de 0 a 100** usando Min-Max Scaling antes da ponderação.

    ---

    ### Pesos de Impacto por Tipo de Produção

    O componente **Impacto** atribui pesos diferenciados:
    """)

    pesos_prod = pd.DataFrame([
        {"Tipo": k, "Peso": v} for k, v in
        sorted(PESOS_IMPACTO_PRODUCAO.items(), key=lambda x: -x[1])
    ])
    st.dataframe(pesos_prod, hide_index=True, use_container_width=True, height=400)

    st.markdown("""
    ---

    ### Normalização

    Cada componente bruto é normalizado:
    - **Maior valor** → Score 100
    - **Menor valor** → Score 0
    - **Valores iguais** → Score 50

    ### Limitações
    - O ranking compara pesquisadores dentro do conjunto filtrado (normalização relativa)
    - Servidores sem dados no Lattes podem ter scores baixos
    - Recomenda-se usar como indicador comparativo, não avaliação absoluta
    """)
