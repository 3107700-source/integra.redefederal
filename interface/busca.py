# -*- coding: utf-8 -*-
"""Módulo: Busca Avançada."""
import streamlit as st
import pandas as pd
from interface.componentes import render_section_title, metric_destaque


def exibir(df_prof, df_pub, df_tccs, df_artigos, df_projetos):
    """Busca avançada em todos os dados."""

    render_section_title("Busca Avançada", "🔍")

    st.markdown("Pesquise em toda a base de dados por título, autor, tema ou palavra-chave.")

    # Campo de busca
    col_busca, col_tipo = st.columns([3, 1])
    with col_busca:
        termo = st.text_input("🔎 Digite o termo de busca:", "", placeholder="Ex: machine learning, sustentabilidade, educação...")
    with col_tipo:
        tipo_busca = st.selectbox("Buscar em:", ["Tudo", "Publicações", "TCCs", "Artigos", "Projetos", "Servidores"])

    if not termo or len(termo) < 3:
        st.info("Digite pelo menos 3 caracteres para buscar.")
        return

    termo_lower = termo.lower()
    resultados = {}

    # Busca em publicações
    if tipo_busca in ["Tudo", "Publicações"] and df_pub is not None and not df_pub.empty:
        mask = df_pub.apply(lambda row: termo_lower in str(row.get("titulo", "")).lower() or
                            termo_lower in str(row.get("autor", "")).lower() or
                            termo_lower in str(row.get("tipo", "")).lower(), axis=1)
        resultados["Publicações"] = df_pub[mask]

    # Busca em TCCs
    if tipo_busca in ["Tudo", "TCCs"] and df_tccs is not None and not df_tccs.empty:
        mask = df_tccs.apply(lambda row: termo_lower in str(row.get("titulo", "")).lower() or
                             termo_lower in str(row.get("palavras_chaves", "")).lower() or
                             termo_lower in str(row.get("nome_professor", "")).lower() or
                             termo_lower in str(row.get("resumo", "")).lower(), axis=1)
        resultados["TCCs"] = df_tccs[mask]

    # Busca em artigos
    if tipo_busca in ["Tudo", "Artigos"] and df_artigos is not None and not df_artigos.empty:
        mask = df_artigos.apply(lambda row: termo_lower in str(row.get("titulo", "")).lower() or
                                termo_lower in str(row.get("palavras_chaves", "")).lower() or
                                termo_lower in str(row.get("journal", "")).lower() or
                                termo_lower in str(row.get("nome_professor", "")).lower(), axis=1)
        resultados["Artigos"] = df_artigos[mask]

    # Busca em projetos
    if tipo_busca in ["Tudo", "Projetos"] and df_projetos is not None and not df_projetos.empty:
        mask = df_projetos.apply(lambda row: termo_lower in str(row.get("titulo", "")).lower() or
                                 termo_lower in str(row.get("descricao", "")).lower() or
                                 termo_lower in str(row.get("nome_professor", "")).lower(), axis=1)
        resultados["Projetos"] = df_projetos[mask]

    # Busca em servidores
    if tipo_busca in ["Tudo", "Servidores"] and df_prof is not None and not df_prof.empty:
        mask = df_prof.apply(lambda row: termo_lower in str(row.get("nome", "")).lower() or
                             termo_lower in str(row.get("temas", "")).lower() or
                             termo_lower in str(row.get("resumo", "")).lower() or
                             termo_lower in str(row.get("area_cnpq", "")).lower(), axis=1)
        resultados["Servidores"] = df_prof[mask]

    # Exibe resultados
    total_resultados = sum(len(v) for v in resultados.values())

    if total_resultados == 0:
        st.warning(f"Nenhum resultado encontrado para '{termo}'.")
        return

    st.success(f"**{total_resultados:,}** resultados encontrados para '{termo}'".replace(",", "."))

    # Métricas por tipo
    cols = st.columns(len(resultados))
    for i, (tipo, df_res) in enumerate(resultados.items()):
        with cols[i]:
            st.metric(tipo, len(df_res))

    st.markdown("---")

    # Exibe cada tipo
    for tipo, df_res in resultados.items():
        if df_res.empty:
            continue

        with st.expander(f"📋 {tipo} ({len(df_res)} resultados)", expanded=(len(resultados) == 1)):
            if tipo == "Publicações":
                cols_show = [c for c in ["titulo", "tipo", "autor", "ano", "campus", "sigla"] if c in df_res.columns]
            elif tipo == "TCCs":
                cols_show = [c for c in ["titulo", "ano", "curso", "nome_professor", "sigla", "palavras_chaves"] if c in df_res.columns]
            elif tipo == "Artigos":
                cols_show = [c for c in ["titulo", "ano", "journal", "nome_professor", "sigla", "doi"] if c in df_res.columns]
            elif tipo == "Projetos":
                cols_show = [c for c in ["titulo", "natureza", "nome_professor", "sigla", "data_inicio"] if c in df_res.columns]
            elif tipo == "Servidores":
                cols_show = [c for c in ["nome", "sigla", "campus", "cargo", "area_cnpq", "temas"] if c in df_res.columns]
            else:
                cols_show = df_res.columns.tolist()[:6]

            st.dataframe(df_res[cols_show].head(100), use_container_width=True, hide_index=True)

            if len(df_res) > 100:
                st.caption(f"Mostrando 100 de {len(df_res)} resultados.")

            csv = df_res[cols_show].to_csv(index=False).encode("utf-8")
            st.download_button(
                f"⬇️ Download {tipo} (CSV)",
                csv, f"busca_{tipo.lower()}_{termo}.csv", "text/csv",
                key=f"download_{tipo}_{termo}"
            )
