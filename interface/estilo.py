# -*- coding: utf-8 -*-
"""Tema visual moderno e consistente para o dashboard."""
import streamlit as st


def aplicar_estilo():
    """Aplica CSS customizado com visual moderno e profissional."""
    st.markdown("""
    <style>
    :root {
        --primary: #1E40AF;
        --primary-light: #3B82F6;
        --primary-soft: #DBEAFE;
        --accent: #059669;
        --accent-soft: #D1FAE5;
        --warning: #D97706;
        --warning-soft: #FEF3C7;
        --background: #F8FAFC;
        --surface: #FFFFFF;
        --text: #0F172A;
        --text-muted: #64748B;
        --border: #E2E8F0;
        --shadow: rgba(15, 23, 42, 0.06);
    }

    .stApp {
        background: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 50%, #F8FAFC 100%);
        color: var(--text);
    }

    /* Header oculto */
    header[data-testid="stHeader"] {
        height: 0rem;
        visibility: hidden;
    }

    .block-container {
        padding-top: 1rem !important;
        margin-top: 0rem !important;
        max-width: 1400px;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.95);
        border-right: 1px solid var(--border);
        backdrop-filter: blur(10px);
    }

    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--primary);
    }

    /* Banner principal */
    .main-banner {
        background: linear-gradient(135deg, #1E3A8A 0%, #1E40AF 30%, #3B82F6 70%, #60A5FA 100%);
        padding: 2.2rem 2.5rem;
        border-radius: 20px;
        color: white !important;
        text-align: center;
        margin-bottom: 1.8rem;
        box-shadow: 0 12px 40px rgba(30, 64, 175, 0.2);
        position: relative;
        overflow: hidden;
    }

    .main-banner::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 60%;
        height: 200%;
        background: radial-gradient(ellipse, rgba(255,255,255,0.08) 0%, transparent 70%);
        pointer-events: none;
    }

    .main-banner h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .main-banner p {
        margin: 8px 0 0 0;
        font-size: 1.05rem;
        opacity: 0.9;
        font-weight: 400;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.8);
        padding: 0.6rem 0.8rem;
        border-radius: 16px;
        border: 1px solid var(--border);
        backdrop-filter: blur(8px);
    }

    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.9rem;
        background: transparent;
        padding: 0 1.2rem;
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: var(--primary-soft);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%) !important;
        color: white !important;
        box-shadow: 0 4px 14px rgba(30, 64, 175, 0.25);
    }

    /* Métricas */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid var(--border);
        padding: 1.2rem 1rem;
        border-radius: 16px;
        box-shadow: 0 2px 12px var(--shadow);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(15, 23, 42, 0.1);
    }

    div[data-testid="stMetric"] label {
        color: var(--text-muted) !important;
        font-weight: 500;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--primary) !important;
        font-weight: 700;
        font-size: 1.8rem;
    }

    /* Gráficos e DataFrames */
    .stPlotlyChart {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 16px;
        border: 1px solid var(--border);
        padding: 0.8rem;
        box-shadow: 0 2px 12px var(--shadow);
    }

    div[data-testid="stDataFrame"] {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 16px;
        border: 1px solid var(--border);
        padding: 0.5rem;
        box-shadow: 0 2px 12px var(--shadow);
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 12px;
        border: 1px solid var(--border);
        font-weight: 600;
    }

    /* Botões */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%);
        border: none;
        box-shadow: 0 4px 14px rgba(30, 64, 175, 0.2);
    }

    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(30, 64, 175, 0.3);
        transform: translateY(-1px);
    }

    /* Cards de insight */
    .insight-card {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
        border: 1px solid #BFDBFE;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
        display: flex;
        align-items: center;
        gap: 0.8rem;
    }

    .insight-card .icon {
        font-size: 1.5rem;
    }

    .insight-card .text {
        font-size: 0.95rem;
        color: var(--text);
        line-height: 1.4;
    }

    /* Section headers */
    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--text);
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--primary-soft);
    }

    /* Selectbox e multiselect */
    .stSelectbox, .stMultiSelect {
        margin-bottom: 0.5rem;
    }

    /* Download buttons */
    .stDownloadButton > button {
        background: var(--accent) !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }

    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid var(--border);
        margin: 1.5rem 0;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: var(--text-muted);
        padding: 2rem 0;
        font-size: 0.85rem;
        border-top: 1px solid var(--border);
        margin-top: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)
