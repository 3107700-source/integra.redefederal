# -*- coding: utf-8 -*-
"""Componentes reutilizáveis do dashboard."""
import streamlit as st
import pandas as pd


def metric_destaque(label, value, delta=None, icon=""):
    """Métrica com estilo destacado."""
    delta_html = ""
    if delta is not None:
        color = "#059669" if delta >= 0 else "#DC2626"
        sinal = "+" if delta >= 0 else ""
        delta_html = f'<span style="color:{color}; font-size:0.85rem;">{sinal}{delta:.1f}%</span>'

    st.markdown(f"""
    <div style="background: white; border: 1px solid #E2E8F0; border-radius: 14px;
                padding: 1.2rem; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
        <div style="font-size: 1.8rem; margin-bottom: 4px;">{icon}</div>
        <div style="font-size: 1.6rem; font-weight: 700; color: #1E40AF;">{value}</div>
        <div style="font-size: 0.8rem; color: #64748B; text-transform: uppercase;
                    letter-spacing: 0.05em; margin-top: 4px;">{label}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_banner(titulo, subtitulo):
    """Renderiza o banner principal."""
    st.markdown(f"""
    <div class="main-banner">
        <h1>{titulo}</h1>
        <p>{subtitulo}</p>
    </div>
    """, unsafe_allow_html=True)


def render_section_title(title, icon=""):
    """Renderiza título de seção."""
    st.markdown(f"""
    <div class="section-title">{icon} {title}</div>
    """, unsafe_allow_html=True)


def render_insight(message, icon="💡"):
    """Renderiza card de insight."""
    st.markdown(f"""
    <div class="insight-card">
        <div class="icon">{icon}</div>
        <div class="text">{message}</div>
    </div>
    """, unsafe_allow_html=True)


def render_footer():
    """Renderiza rodapé."""
    st.markdown("""
    <div class="footer">
        <p><strong>Dashboard de Produção Acadêmica - Rede Federal de Educação</strong></p>
        <p>Dados extraídos do Portal Integra • Atualizado automaticamente</p>
    </div>
    """, unsafe_allow_html=True)


def extract_keywords(series, top_n=20, sep=";"):
    """Extrai e conta palavras-chave de uma Series."""
    all_kw = []
    for text in series.dropna():
        for kw in str(text).split(sep):
            kw = kw.strip().lower()
            if kw and len(kw) > 2:
                all_kw.append(kw)
    if not all_kw:
        return pd.DataFrame(columns=["termo", "frequencia"])
    counts = pd.Series(all_kw).value_counts().head(top_n).reset_index()
    counts.columns = ["termo", "frequencia"]
    return counts


def filtrar_por_periodo(df, col_ano, ano_min, ano_max):
    """Filtra DataFrame por período."""
    df = df.copy()
    df[col_ano] = pd.to_numeric(df[col_ano], errors="coerce")
    return df[(df[col_ano] >= ano_min) & (df[col_ano] <= ano_max)]
