"""
Dashboard Streamlit - Análise Temática + Ranking de Pesquisadores
Rede Federal de Educação - Portal Integra
Design moderno com navegação por páginas e UX aprimorada.
"""

import os
import sys
import re
import sqlite3
from io import BytesIO

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    DB_PATH, CLUSTERS_OUTPUT, PUBLICACOES_PROCESSED, PROCESSED_DIR,
    INSTITUICOES, PESOS_RANKING, PESOS_IMPACTO_PRODUCAO
)

# PESOS_TITULACAO may not exist in older config versions
try:
    from config import PESOS_TITULACAO
except ImportError:
    PESOS_TITULACAO = {
        "pos_doutorado": 12, "doutorado": 10, "mestrado": 7,
        "especializacao": 4, "graduacao": 2,
    }

# Import NLP module with fallback
try:
    from nlp_tematicas import (
        extract_topics_lda, compare_institutions, compare_researchers,
        cluster_themes, get_institution_profile, compute_tfidf_similarity,
        preprocess_text, STOPWORDS_PT
    )
    NLP_AVAILABLE = True
except (ImportError, Exception):
    try:
        from etl.nlp_tematicas import (
            extract_topics_lda, compare_institutions, compare_researchers,
            cluster_themes, get_institution_profile, compute_tfidf_similarity,
            preprocess_text, STOPWORDS_PT
        )
        NLP_AVAILABLE = True
    except (ImportError, Exception):
        NLP_AVAILABLE = False
        STOPWORDS_PT = set()

# ─── Configuração ───
st.set_page_config(
    page_title="Integra Rede Federal - Análise Acadêmica",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ───
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
        padding: 1.8rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 20px rgba(26, 54, 93, 0.25);
    }
    .main-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; }
    .main-header p { margin: 0.3rem 0 0 0; opacity: 0.85; font-size: 0.9rem; }
    .kpi-container {
        display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0;
    }
    .kpi-card {
        background: white; border-radius: 10px; padding: 1rem 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06); flex: 1; min-width: 150px;
        border-top: 3px solid #2b6cb0;
    }
    .kpi-card .value { font-size: 1.8rem; font-weight: 700; color: #1a365d; }
    .kpi-card .label { font-size: 0.8rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
    .section-title {
        font-size: 1.3rem; font-weight: 600; color: #1a365d;
        border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; margin: 1.5rem 0 1rem 0;
    }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #f7fafc 0%, #edf2f7 100%); }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ─── Carregamento de dados ───
@st.cache_data(ttl=300)
def load_data():
    """Carrega dados: tenta Parquet primeiro (deploy), depois SQLite (local)."""
    parquet_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "parquet")
    tables = ["prof", "pub", "tccs", "projetos", "detalhes", "formacao", "bancas", "gestao"]
    table_files = {
        "prof": "professores.parquet",
        "pub": "publicacoes.parquet",
        "tccs": "tccs.parquet",
        "projetos": "projetos.parquet",
        "detalhes": "curriculo_detalhes.parquet",
        "formacao": "formacao_academica.parquet",
        "bancas": "bancas.parquet",
        "gestao": "gestao_comissoes.parquet",
    }

    # Tenta Parquet primeiro (mais rápido e funciona no Streamlit Cloud)
    if os.path.exists(parquet_dir) and any(f.endswith(".parquet") for f in os.listdir(parquet_dir)):
        data = {}
        for key, filename in table_files.items():
            filepath = os.path.join(parquet_dir, filename)
            if os.path.exists(filepath):
                try:
                    data[key] = pd.read_parquet(filepath)
                except Exception:
                    data[key] = pd.DataFrame()
            else:
                data[key] = pd.DataFrame()
        return data

    # Fallback: SQLite (uso local)
    if not os.path.exists(DB_PATH):
        return {k: pd.DataFrame() for k in tables}
    conn = sqlite3.connect(DB_PATH)
    try:
        data = {
            "prof": pd.read_sql_query("SELECT * FROM professores", conn),
            "pub": pd.read_sql_query("SELECT * FROM publicacoes", conn),
            "tccs": pd.read_sql_query("SELECT * FROM tccs", conn),
            "projetos": pd.read_sql_query("SELECT * FROM projetos", conn),
            "detalhes": pd.read_sql_query("SELECT * FROM curriculo_detalhes", conn),
        }
        try:
            data["formacao"] = pd.read_sql_query("SELECT * FROM formacao_academica", conn)
        except Exception:
            data["formacao"] = pd.DataFrame()
        try:
            data["bancas"] = pd.read_sql_query("SELECT * FROM bancas", conn)
        except Exception:
            data["bancas"] = pd.DataFrame()
        try:
            data["gestao"] = pd.read_sql_query("SELECT * FROM gestao_comissoes", conn)
        except Exception:
            data["gestao"] = pd.DataFrame()
    except Exception:
        data = {k: pd.DataFrame() for k in tables}
    finally:
        conn.close()
    return data


def calculate_ipa(df_prof, df_pub, df_tccs, df_projetos, df_detalhes, df_formacao, df_bancas):
    """Calcula IPA completo com titulação e gestão."""
    if df_prof is None or df_prof.empty:
        return df_prof
    if "ipa" in df_prof.columns:
        return df_prof

    df = df_prof.copy()

    def norm(s):
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50.0, index=s.index)
        return ((s - mn) / (mx - mn)) * 100

    # Publicações
    if not df_pub.empty:
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
    for col in ["total_publicacoes", "tipos_distintos", "ano_mais_recente", "pub_impacto"]:
        if col not in df.columns:
            df[col] = 0

    # Orientações
    if not df_tccs.empty:
        orient = df_tccs.groupby("slug_professor").size().reset_index(name="total_orientacoes")
        orient = orient.rename(columns={"slug_professor": "slug"})
        df = df.merge(orient, on="slug", how="left")
    if "total_orientacoes" not in df.columns:
        df["total_orientacoes"] = 0

    # Projetos
    if not df_projetos.empty:
        proj = df_projetos.groupby("slug_professor").size().reset_index(name="total_projetos")
        proj = proj.rename(columns={"slug_professor": "slug"})
        df = df.merge(proj, on="slug", how="left")
    if "total_projetos" not in df.columns:
        df["total_projetos"] = 0

    # Detalhes currículo
    if not df_detalhes.empty:
        bancas_det = df_detalhes[df_detalhes["categoria"] == "banca"]
        if not bancas_det.empty:
            b_stats = bancas_det.groupby("slug_professor").size().reset_index(name="total_bancas")
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

    # Titulação
    if df_formacao is not None and not df_formacao.empty:
        df_form_c = df_formacao.copy()
        df_form_c["peso_tit"] = df_form_c["nivel"].map(PESOS_TITULACAO).fillna(0)
        tit_stats = df_form_c.groupby("slug_professor").agg(
            titulacao_score=("peso_tit", "max"),
            total_formacoes=("formacao_id", "count"),
        ).reset_index().rename(columns={"slug_professor": "slug"})
        df = df.merge(tit_stats, on="slug", how="left")

    # Bancas estruturadas
    if df_bancas is not None and not df_bancas.empty:
        bancas_est = df_bancas.groupby("slug_professor").size().reset_index(name="total_bancas_est")
        bancas_est = bancas_est.rename(columns={"slug_professor": "slug"})
        df = df.merge(bancas_est, on="slug", how="left")

    # Gestão acadêmica
    gestao_pats = [
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
        return sum(1 for p in gestao_pats if re.search(p, text))
    df["gestao_score"] = df["resumo"].apply(count_gestao)

    # Preenche NaN
    for col in ["total_publicacoes", "tipos_distintos", "ano_mais_recente", "pub_impacto",
                "total_orientacoes", "total_projetos", "total_bancas", "total_extensao",
                "atividades_ensino", "titulacao_score", "total_formacoes", "total_bancas_est",
                "gestao_score"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    # Bancas final (usa estruturadas se disponíveis)
    df["total_bancas_final"] = df["total_bancas_est"].where(df["total_bancas_est"] > 0, df["total_bancas"])

    # Scores normalizados
    df["score_publicacoes"] = norm(df["total_publicacoes"])
    df["score_impacto"] = norm(df["pub_impacto"])
    df["score_diversidade"] = norm(df["tipos_distintos"])
    df["score_recencia"] = norm(df["ano_mais_recente"])
    df["score_orientacoes"] = norm(df["total_orientacoes"])
    df["score_projetos"] = norm(df["total_projetos"])
    df["score_tempo_docencia"] = norm(df["atividades_ensino"])
    df["score_comissoes_bancas"] = norm(df["total_bancas_final"])
    df["score_extensao"] = norm(df["total_extensao"])
    df["score_titulacao"] = norm(df["titulacao_score"])
    df["score_gestao_academica"] = norm(df["gestao_score"])

    # IPA
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
    df["is_docente"] = df["cargo"].str.contains("Docente", case=False, na=False) if "cargo" in df.columns else False
    return df


# ─── Sidebar ───
def render_sidebar(df_prof, df_tccs):
    """Sidebar com navegação e filtros."""
    st.sidebar.markdown("""
    <div style="text-align:center; padding: 1rem 0;">
        <h2 style="color:#1a365d; margin:0;">🎓 Integra</h2>
        <p style="color:#666; font-size:0.8rem; margin:0;">Rede Federal de Educação</p>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")

    # Navegação
    pagina = st.sidebar.radio(
        "📊 Navegação",
        ["🏠 Visão Geral", "📚 Análise Temática", "🔄 Comparação", "📈 Insights",
         "🏆 Ranking", "📄 Publicações", "👤 Perfil do Professor", "ℹ️ Metodologia"],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔍 Filtros**")

    # Instituição
    siglas = sorted(df_prof["sigla"].dropna().unique().tolist()) if not df_prof.empty else []
    sigla_filtro = st.sidebar.multiselect("Instituição", options=siglas, default=[])

    # Campus
    if sigla_filtro:
        campus_opts = sorted(df_prof[df_prof["sigla"].isin(sigla_filtro)]["campus"].dropna().unique().tolist())
    else:
        campus_opts = sorted(df_prof["campus"].dropna().unique().tolist()) if not df_prof.empty else []
    campus_filtro = st.sidebar.multiselect("Campus", options=campus_opts, default=[])

    # Área CNPq
    area_opts = sorted(df_prof["area_cnpq"].dropna().unique().tolist()) if "area_cnpq" in df_prof.columns else []
    area_filtro = st.sidebar.multiselect("Área CNPq", options=area_opts, default=[])

    # UF
    uf_opts = sorted(df_prof["uf"].dropna().unique().tolist()) if "uf" in df_prof.columns else []
    uf_filtro = st.sidebar.multiselect("UF", options=uf_opts, default=[])

    # Tipo servidor
    tipo_filtro = st.sidebar.selectbox("Tipo de Servidor", ["Todos", "Docente", "Técnico"])

    # Busca
    nome_busca = st.sidebar.text_input("🔎 Buscar por nome", "")

    # Período de tempo
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📅 Período**")
    ano_min, ano_max = st.sidebar.slider(
        "Filtrar por ano",
        min_value=2000, max_value=2026, value=(2000, 2026),
        help="Filtra publicações, TCCs e projetos pelo período selecionado"
    )

    return {
        "pagina": pagina,
        "sigla": sigla_filtro,
        "campus": campus_filtro,
        "area": area_filtro,
        "uf": uf_filtro,
        "tipo": tipo_filtro,
        "nome": nome_busca,
        "ano_min": ano_min,
        "ano_max": ano_max,
    }


def apply_filters(df, filtros):
    """Aplica filtros ao DataFrame."""
    if df is None or df.empty:
        return df
    df_f = df.copy()
    if filtros["sigla"]:
        df_f = df_f[df_f["sigla"].isin(filtros["sigla"])]
    if filtros["campus"]:
        df_f = df_f[df_f["campus"].isin(filtros["campus"])]
    if filtros["area"] and "area_cnpq" in df_f.columns:
        df_f = df_f[df_f["area_cnpq"].isin(filtros["area"])]
    if filtros["uf"] and "uf" in df_f.columns:
        df_f = df_f[df_f["uf"].isin(filtros["uf"])]
    if filtros["tipo"] == "Docente":
        df_f = df_f[df_f["cargo"].str.contains("Docente", case=False, na=False)]
    elif filtros["tipo"] == "Técnico":
        df_f = df_f[~df_f["cargo"].str.contains("Docente", case=False, na=False)]
    if filtros["nome"]:
        df_f = df_f[df_f["nome"].str.contains(filtros["nome"], case=False, na=False)]
    return df_f


def apply_period_filter(df, filtros, ano_col="ano"):
    """Aplica filtro de período a um DataFrame com coluna de ano."""
    if df is None or df.empty:
        return df
    if ano_col not in df.columns:
        return df
    df_f = df.copy()
    df_f["_ano_num"] = pd.to_numeric(df_f[ano_col], errors="coerce")
    df_f = df_f[(df_f["_ano_num"] >= filtros["ano_min"]) & (df_f["_ano_num"] <= filtros["ano_max"]) | df_f["_ano_num"].isna()]
    df_f = df_f.drop(columns=["_ano_num"])
    return df_f


def apply_period_filter_projetos(df, filtros):
    """Aplica filtro de período a projetos (usa data_inicio)."""
    if df is None or df.empty:
        return df
    if "data_inicio" not in df.columns:
        return df
    df_f = df.copy()
    df_f["_ano_num"] = pd.to_numeric(df_f["data_inicio"].str[:4], errors="coerce")
    df_f = df_f[(df_f["_ano_num"] >= filtros["ano_min"]) & (df_f["_ano_num"] <= filtros["ano_max"]) | df_f["_ano_num"].isna()]
    df_f = df_f.drop(columns=["_ano_num"])
    return df_f


# ─── PÁGINA: VISÃO GERAL ───
def page_visao_geral(df_prof, df_pub, df_tccs, df_projetos, df_formacao, df_bancas):
    """Dashboard principal com KPIs e visão geral."""
    st.markdown("""
    <div class="main-header">
        <h1>🎓 Integra Rede Federal - Dashboard Acadêmico</h1>
        <p>Análise de produtividade, temáticas e ranking dos pesquisadores da Rede Federal</p>
    </div>
    """, unsafe_allow_html=True)

    # KPIs principais
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🏛️ Instituições", df_prof["sigla"].nunique() if not df_prof.empty else 0)
    col2.metric("👥 Pesquisadores", f"{len(df_prof):,}" if not df_prof.empty else 0)
    col3.metric("📄 Publicações", f"{len(df_pub):,}" if not df_pub.empty else 0)
    col4.metric("📝 TCCs Orientados", f"{len(df_tccs):,}" if not df_tccs.empty else 0)
    col5.metric("🔬 Projetos", f"{len(df_projetos):,}" if not df_projetos.empty else 0)

    st.markdown("---")

    # Gráficos lado a lado
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<p class="section-title">📊 Pesquisadores por Instituição</p>', unsafe_allow_html=True)
        if not df_prof.empty:
            inst_counts = df_prof["sigla"].value_counts().head(15).reset_index()
            inst_counts.columns = ["Instituição", "Pesquisadores"]
            fig = px.bar(inst_counts, x="Pesquisadores", y="Instituição", orientation="h",
                         color="Pesquisadores", color_continuous_scale="Blues")
            fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig)

    with col_b:
        st.markdown('<p class="section-title">🗺️ Distribuição por UF</p>', unsafe_allow_html=True)
        if not df_prof.empty and "uf" in df_prof.columns:
            uf_counts = df_prof["uf"].value_counts().reset_index()
            uf_counts.columns = ["UF", "Pesquisadores"]
            fig = px.bar(uf_counts, x="UF", y="Pesquisadores", color="Pesquisadores",
                         color_continuous_scale="Viridis")
            fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig)

    # Segunda linha
    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown('<p class="section-title">🎯 Distribuição por Área CNPq</p>', unsafe_allow_html=True)
        if not df_prof.empty and "area_cnpq" in df_prof.columns:
            area_counts = df_prof["area_cnpq"].value_counts().reset_index()
            area_counts.columns = ["Área", "Quantidade"]
            fig = px.pie(area_counts, values="Quantidade", names="Área", hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig)

    with col_d:
        st.markdown('<p class="section-title">🎓 Titulação dos Pesquisadores</p>', unsafe_allow_html=True)
        if df_formacao is not None and not df_formacao.empty:
            nivel_order = {"pos_doutorado": "Pós-Doutorado", "doutorado": "Doutorado",
                          "mestrado": "Mestrado", "especializacao": "Especialização", "graduacao": "Graduação"}
            form_counts = df_formacao["nivel"].map(nivel_order).value_counts().reset_index()
            form_counts.columns = ["Nível", "Quantidade"]
            fig = px.bar(form_counts, x="Nível", y="Quantidade", color="Nível",
                         color_discrete_sequence=["#1a365d", "#2b6cb0", "#4299e1", "#90cdf4", "#bee3f8"])
            fig.update_layout(height=400, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig)
        else:
            st.info("Dados de formação acadêmica ainda sendo extraídos...")


# ─── PÁGINA: ANÁLISE TEMÁTICA ───
def page_analise_tematica(df_tccs, df_pub, df_projetos, filtros):
    """Análise de temáticas em TCCs, Artigos e Projetos."""
    st.markdown("""
    <div class="main-header">
        <h1>📚 Análise Temática</h1>
        <p>Mapeamento das temáticas de pesquisa por instituição, campus e impacto no ensino</p>
    </div>
    """, unsafe_allow_html=True)

    # Filtra por sigla
    df_tccs_f = df_tccs.copy() if not df_tccs.empty else pd.DataFrame()
    df_pub_f = df_pub.copy() if not df_pub.empty else pd.DataFrame()
    df_proj_f = df_projetos.copy() if not df_projetos.empty else pd.DataFrame()

    if filtros["sigla"]:
        if not df_tccs_f.empty:
            df_tccs_f = df_tccs_f[df_tccs_f["sigla"].isin(filtros["sigla"])]
        if not df_pub_f.empty:
            df_pub_f = df_pub_f[df_pub_f["sigla"].isin(filtros["sigla"])]
        if not df_proj_f.empty:
            df_proj_f = df_proj_f[df_proj_f["sigla"].isin(filtros["sigla"])]

    # Sub-abas expandidas
    tab_por_if, tab_por_campus, tab_pesq_ensino, tab_tccs, tab_projetos, tab_evolucao, tab_sobre = st.tabs([
        "🏛️ Por Instituição", "📍 Por Campus", "🎓 Pesquisa → Ensino",
        "📝 TCCs", "🔬 Projetos", "📈 Evolução Temporal", "ℹ️ Sobre"
    ])

    with tab_por_if:
        _tematicas_por_if(df_tccs_f, df_proj_f)
    with tab_por_campus:
        _tematicas_por_campus(df_tccs_f, df_proj_f)
    with tab_pesq_ensino:
        _pesquisa_ensino(df_tccs_f, df_proj_f, df_pub_f)
    with tab_tccs:
        _render_tccs(df_tccs_f)
    with tab_projetos:
        _render_projetos(df_proj_f)
    with tab_evolucao:
        _evolucao_tematica(df_tccs_f, df_pub_f)
    with tab_sobre:
        _sobre_analise_tematica()


def _tematicas_por_if(df_tccs, df_proj):
    """Temáticas mais trabalhadas por instituição."""
    st.markdown('<p class="section-title">🏛️ Temáticas por Instituição</p>', unsafe_allow_html=True)

    if df_tccs.empty or "palavras_chaves" not in df_tccs.columns:
        st.info("Sem dados de palavras-chave disponíveis.")
        return

    siglas = sorted(df_tccs["sigla"].dropna().unique().tolist())
    if not siglas:
        st.info("Nenhuma instituição encontrada.")
        return

    # Top 5 temáticas por IF
    st.markdown("**Top 5 temáticas de pesquisa por instituição** (baseado em palavras-chave dos TCCs)")
    rows = []
    for sigla in siglas:
        kws_sigla = df_tccs[df_tccs["sigla"] == sigla]["palavras_chaves"].dropna()
        all_kw = []
        for kws in kws_sigla:
            for kw in str(kws).split(";"):
                kw = kw.strip().lower()
                if kw and len(kw) > 2 and kw not in STOPWORDS_PT and len(kw) < 60:
                    all_kw.append(kw)
        if all_kw:
            top5 = pd.Series(all_kw).value_counts().head(5)
            for tema, freq in top5.items():
                rows.append({"Instituição": sigla, "Tema": tema, "Frequência": freq})

    if rows:
        df_temas_if = pd.DataFrame(rows)
        # Heatmap: top temas globais por IF
        top_temas_global = df_temas_if.groupby("Tema")["Frequência"].sum().nlargest(20).index.tolist()
        df_heat = df_temas_if[df_temas_if["Tema"].isin(top_temas_global)]
        pivot = df_heat.pivot_table(index="Tema", columns="Instituição", values="Frequência", fill_value=0)

        fig = px.imshow(pivot, color_continuous_scale="YlOrRd",
                        title="Heatmap: Top 20 Temáticas × Instituição",
                        labels=dict(color="Frequência"))
        fig.update_layout(height=600)
        st.plotly_chart(fig)

        # Tabela resumo
        with st.expander("📋 Top 5 temáticas por IF (tabela)"):
            for sigla in siglas:
                sigla_data = df_temas_if[df_temas_if["Instituição"] == sigla].head(5)
                if not sigla_data.empty:
                    temas_str = " | ".join([f"**{r['Tema']}** ({r['Frequência']})" for _, r in sigla_data.iterrows()])
                    st.markdown(f"**{sigla}**: {temas_str}")

    # Relação com projetos
    if not df_proj.empty and "natureza" in df_proj.columns:
        st.markdown("---")
        st.markdown('<p class="section-title">🔬 Projetos de Pesquisa por Instituição</p>', unsafe_allow_html=True)
        proj_por_if = df_proj.groupby(["sigla", "natureza"]).size().reset_index(name="count")
        fig = px.bar(proj_por_if, x="sigla", y="count", color="natureza",
                     title="Projetos por Instituição e Natureza", barmode="stack")
        fig.update_layout(height=400)
        st.plotly_chart(fig)


def _tematicas_por_campus(df_tccs, df_proj):
    """Temáticas por campus."""
    st.markdown('<p class="section-title">📍 Temáticas por Campus</p>', unsafe_allow_html=True)

    if df_tccs.empty or "palavras_chaves" not in df_tccs.columns or "campus" not in df_tccs.columns:
        st.info("Sem dados suficientes.")
        return

    # Seletor de instituição
    siglas = sorted(df_tccs["sigla"].dropna().unique().tolist())
    sigla_sel = st.selectbox("Selecione a instituição:", siglas, key="tematica_campus_if")

    df_if = df_tccs[df_tccs["sigla"] == sigla_sel]
    campi = sorted(df_if["campus"].dropna().unique().tolist())

    if not campi:
        st.info(f"Nenhum campus encontrado para {sigla_sel}.")
        return

    # Top temáticas por campus
    rows = []
    for campus in campi:
        kws_campus = df_if[df_if["campus"] == campus]["palavras_chaves"].dropna()
        all_kw = []
        for kws in kws_campus:
            for kw in str(kws).split(";"):
                kw = kw.strip().lower()
                if kw and len(kw) > 2 and kw not in STOPWORDS_PT and len(kw) < 60:
                    all_kw.append(kw)
        if all_kw:
            top_kw = pd.Series(all_kw).value_counts().head(8)
            for tema, freq in top_kw.items():
                rows.append({"Campus": campus, "Tema": tema, "Frequência": freq})

    if rows:
        df_campus_temas = pd.DataFrame(rows)

        # Gráfico por campus
        fig = px.bar(df_campus_temas, x="Frequência", y="Tema", color="Campus", orientation="h",
                     barmode="group", title=f"Temáticas por Campus - {sigla_sel}")
        fig.update_layout(height=max(400, len(df_campus_temas["Tema"].unique()) * 22),
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)

        # Métricas por campus
        st.markdown("---")
        st.markdown(f"**Resumo por campus ({sigla_sel})**")
        campus_stats = []
        for campus in campi:
            n_tccs = len(df_if[df_if["campus"] == campus])
            n_proj = len(df_proj[(df_proj["sigla"] == sigla_sel) & (df_proj.get("campus", pd.Series()) == campus)]) if not df_proj.empty and "campus" in df_proj.columns else 0
            campus_temas = df_campus_temas[df_campus_temas["Campus"] == campus]
            top_tema = campus_temas.iloc[0]["Tema"] if not campus_temas.empty else "N/A"
            campus_stats.append({
                "Campus": campus, "TCCs": n_tccs,
                "Tema Principal": top_tema,
                "Temas Distintos": len(campus_temas),
            })
        st.dataframe(pd.DataFrame(campus_stats), hide_index=True)
    else:
        st.info("Sem palavras-chave suficientes para análise por campus.")


def _pesquisa_ensino(df_tccs, df_proj, df_pub):
    """Relação entre pesquisa e impacto no ensino."""
    st.markdown('<p class="section-title">🎓 Pesquisa → Ensino: Como a pesquisa impacta o ensino</p>', unsafe_allow_html=True)

    st.markdown("""
    A produção acadêmica dos docentes impacta diretamente o ensino através de:
    - **TCCs orientados**: Temas de pesquisa do docente guiam os trabalhos dos alunos
    - **Projetos de ensino**: Projetos com natureza "ENSINO" aplicam pesquisa na sala de aula
    - **Diversidade temática**: Quanto mais diversa a pesquisa, mais opções de orientação para alunos
    """)

    st.markdown("---")

    # Projetos de ensino vs pesquisa
    if not df_proj.empty and "natureza" in df_proj.columns:
        col_a, col_b = st.columns(2)
        with col_a:
            nat_counts = df_proj["natureza"].value_counts().reset_index()
            nat_counts.columns = ["Natureza", "Quantidade"]
            fig = px.pie(nat_counts, values="Quantidade", names="Natureza", hole=0.4,
                         title="Distribuição de Projetos por Natureza")
            fig.update_layout(height=350)
            st.plotly_chart(fig)

        with col_b:
            # Projetos de ensino por IF
            ensino_proj = df_proj[df_proj["natureza"] == "ENSINO"]
            if not ensino_proj.empty:
                ensino_por_if = ensino_proj["sigla"].value_counts().head(15).reset_index()
                ensino_por_if.columns = ["Instituição", "Projetos de Ensino"]
                fig = px.bar(ensino_por_if, x="Projetos de Ensino", y="Instituição", orientation="h",
                             title="Projetos de Ensino por IF", color="Projetos de Ensino",
                             color_continuous_scale="Greens")
                fig.update_layout(height=350, yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig)

    # Relação orientador-tema: docentes que mais orientam e seus temas
    if not df_tccs.empty and "nome_professor" in df_tccs.columns and "palavras_chaves" in df_tccs.columns:
        st.markdown("---")
        st.markdown('<p class="section-title">👨‍🏫 Top Orientadores e suas Temáticas</p>', unsafe_allow_html=True)

        top_orientadores = df_tccs["nome_professor"].value_counts().head(10).index.tolist()
        orient_data = []
        for nome in top_orientadores:
            tccs_prof = df_tccs[df_tccs["nome_professor"] == nome]
            n_tccs = len(tccs_prof)
            # Extrai temas
            all_kw = []
            for kws in tccs_prof["palavras_chaves"].dropna():
                for kw in str(kws).split(";"):
                    kw = kw.strip().lower()
                    if kw and len(kw) > 2 and kw not in STOPWORDS_PT:
                        all_kw.append(kw)
            top_temas = pd.Series(all_kw).value_counts().head(3).index.tolist() if all_kw else []
            orient_data.append({
                "Orientador": nome,
                "TCCs Orientados": n_tccs,
                "Sigla": tccs_prof["sigla"].mode().iloc[0] if not tccs_prof["sigla"].mode().empty else "",
                "Temas Principais": ", ".join(top_temas) if top_temas else "N/A",
            })

        df_orient = pd.DataFrame(orient_data)
        st.dataframe(df_orient, hide_index=True)

    # Cursos mais impactados pela pesquisa
    if not df_tccs.empty and "curso" in df_tccs.columns:
        st.markdown("---")
        st.markdown('<p class="section-title">📖 Cursos com mais produção de TCCs (impacto no ensino)</p>', unsafe_allow_html=True)

        curso_counts = df_tccs["curso"].value_counts().head(20).reset_index()
        curso_counts.columns = ["Curso", "TCCs"]
        fig = px.bar(curso_counts, x="TCCs", y="Curso", orientation="h",
                     title="Top 20 Cursos por volume de TCCs orientados",
                     color="TCCs", color_continuous_scale="Blues")
        fig.update_layout(height=500, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)

        # Temáticas por curso
        st.markdown("**Temáticas dominantes por curso (Top 5 cursos)**")
        top_cursos = df_tccs["curso"].value_counts().head(5).index.tolist()
        for curso in top_cursos:
            tccs_curso = df_tccs[df_tccs["curso"] == curso]
            all_kw = []
            for kws in tccs_curso["palavras_chaves"].dropna():
                for kw in str(kws).split(";"):
                    kw = kw.strip().lower()
                    if kw and len(kw) > 2 and kw not in STOPWORDS_PT:
                        all_kw.append(kw)
            if all_kw:
                top3 = pd.Series(all_kw).value_counts().head(3).index.tolist()
                st.markdown(f"- **{curso}** ({len(tccs_curso)} TCCs): {', '.join(top3)}")


def _evolucao_tematica(df_tccs, df_pub):
    """Evolução temporal das temáticas."""
    st.markdown('<p class="section-title">📈 Evolução Temporal das Temáticas</p>', unsafe_allow_html=True)

    if df_tccs.empty or "palavras_chaves" not in df_tccs.columns or "ano" not in df_tccs.columns:
        st.info("Sem dados suficientes para análise temporal.")
        return

    df_t = df_tccs.copy()
    df_t["ano"] = pd.to_numeric(df_t["ano"], errors="coerce")
    df_t = df_t[(df_t["ano"] >= 2010) & (df_t["ano"] <= 2025)]

    # Extrai keywords com ano
    rows = []
    for _, row in df_t.iterrows():
        if pd.isna(row.get("palavras_chaves")):
            continue
        ano = int(row["ano"])
        for kw in str(row["palavras_chaves"]).split(";"):
            kw = kw.strip().lower()
            if kw and len(kw) > 2 and kw not in STOPWORDS_PT and len(kw) < 60:
                rows.append({"ano": ano, "tema": kw})

    if not rows:
        st.info("Sem dados de palavras-chave com ano.")
        return

    df_kw_tempo = pd.DataFrame(rows)

    # Top 8 temas globais
    top_temas = df_kw_tempo["tema"].value_counts().head(8).index.tolist()
    df_top = df_kw_tempo[df_kw_tempo["tema"].isin(top_temas)]
    evolucao = df_top.groupby(["ano", "tema"]).size().reset_index(name="frequencia")

    fig = px.line(evolucao, x="ano", y="frequencia", color="tema", markers=True,
                  title="Evolução das Top 8 Temáticas ao Longo do Tempo")
    fig.update_layout(height=450)
    st.plotly_chart(fig)

    # Temas emergentes (crescimento recente)
    st.markdown("---")
    st.markdown("**🆕 Temas Emergentes** (maior crescimento nos últimos 3 anos)")
    recente = df_kw_tempo[df_kw_tempo["ano"] >= 2022]
    antigo = df_kw_tempo[(df_kw_tempo["ano"] >= 2015) & (df_kw_tempo["ano"] <= 2021)]

    if not recente.empty and not antigo.empty:
        freq_recente = recente["tema"].value_counts()
        freq_antigo = antigo["tema"].value_counts()
        # Calcula crescimento relativo
        crescimento = []
        for tema in freq_recente.head(50).index:
            fr = freq_recente.get(tema, 0)
            fa = freq_antigo.get(tema, 0)
            if fa > 0:
                growth = (fr - fa) / fa * 100
            elif fr > 3:
                growth = 999  # tema novo
            else:
                continue
            if growth > 50:
                crescimento.append({"Tema": tema, "Freq. Recente": fr, "Freq. Anterior": fa,
                                    "Crescimento (%)": round(growth, 0)})

        if crescimento:
            df_cresc = pd.DataFrame(crescimento).sort_values("Crescimento (%)", ascending=False).head(10)
            fig = px.bar(df_cresc, x="Crescimento (%)", y="Tema", orientation="h",
                         color="Crescimento (%)", color_continuous_scale="Greens",
                         title="Top 10 Temas com Maior Crescimento")
            fig.update_layout(height=400, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig)
        else:
            st.info("Sem temas com crescimento significativo detectado.")


def _sobre_analise_tematica():
    """Aba sobre da análise temática."""
    st.markdown("""
    ## ℹ️ Sobre a Análise Temática

    ### O que é?
    A análise temática identifica, quantifica e visualiza os **temas de pesquisa** presentes na
    produção acadêmica da Rede Federal, extraídos das palavras-chave registradas nos currículos Lattes.

    ### Fontes de dados
    | Fonte | Dados extraídos | Uso |
    |-------|----------------|-----|
    | **TCCs** | Palavras-chave das orientações concluídas | Principal fonte de temáticas |
    | **Projetos** | Título, natureza (pesquisa/ensino/extensão) | Relação pesquisa-ensino |
    | **Publicações** | Tipo, ano, campus | Volume de produção |

    ### Abas disponíveis

    **🏛️ Por Instituição**: Heatmap mostrando quais temáticas são mais trabalhadas em cada IF.
    Permite identificar vocações institucionais e áreas de excelência.

    **📍 Por Campus**: Detalha as temáticas de cada campus dentro de uma instituição.
    Mostra como diferentes campi se especializam em áreas distintas.

    **🎓 Pesquisa → Ensino**: Analisa como a pesquisa dos docentes impacta o ensino:
    - Projetos de natureza "ENSINO" que aplicam pesquisa na sala de aula
    - Orientadores mais produtivos e seus temas (que guiam os alunos)
    - Cursos mais impactados pela produção de TCCs

    **📝 TCCs**: Análise detalhada dos trabalhos de conclusão — por ano, curso, temáticas.

    **🔬 Projetos**: Distribuição por natureza (pesquisa, extensão, ensino) e evolução temporal.

    **📈 Evolução Temporal**: Como as temáticas mudam ao longo do tempo.
    Identifica temas emergentes (crescimento > 50% nos últimos 3 anos).

    ### Tratamento de texto (NLP)
    - **Stopwords**: 150+ termos removidos (preposições, termos acadêmicos genéricos, nomes institucionais)
    - **Normalização**: Lowercase, remoção de pontuação, filtro por tamanho (3-60 caracteres)
    - **Frequência**: Contagem simples de ocorrências para ranking de relevância
    - **Crescimento**: Comparação de frequência entre períodos (2015-2021 vs 2022-2025)
    """)



def _extract_keywords(df, col="palavras_chaves"):
    """Extrai e conta palavras-chave."""
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=["Tema", "Frequência"])
    all_kw = []
    for kws in df[col].dropna():
        for kw in str(kws).split(";"):
            kw = kw.strip().lower()
            if kw and len(kw) > 2 and len(kw) < 80:
                all_kw.append(kw)
    if not all_kw:
        return pd.DataFrame(columns=["Tema", "Frequência"])
    kw_counts = pd.Series(all_kw).value_counts().head(30).reset_index()
    kw_counts.columns = ["Tema", "Frequência"]
    return kw_counts


def _render_tccs(df_tccs):
    """Renderiza aba de TCCs."""
    if df_tccs.empty:
        st.info("Nenhum TCC encontrado com os filtros atuais.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total TCCs", f"{len(df_tccs):,}")
    col2.metric("Orientadores", df_tccs["nome_professor"].nunique() if "nome_professor" in df_tccs.columns else 0)
    col3.metric("Cursos", df_tccs["curso"].nunique() if "curso" in df_tccs.columns else 0)
    col4.metric("Instituições", df_tccs["sigla"].nunique() if "sigla" in df_tccs.columns else 0)

    col_a, col_b = st.columns(2)
    with col_a:
        if "ano" in df_tccs.columns:
            df_ano = df_tccs.copy()
            df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
            df_ano = df_ano[df_ano["ano"] >= 2000]
            ano_counts = df_ano["ano"].dropna().value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.area(ano_counts, x="Ano", y="Quantidade", title="TCCs por Ano",
                         color_discrete_sequence=["#2b6cb0"])
            fig.update_layout(height=350)
            st.plotly_chart(fig)

    with col_b:
        if "curso" in df_tccs.columns:
            curso_counts = df_tccs["curso"].value_counts().head(12).reset_index()
            curso_counts.columns = ["Curso", "Quantidade"]
            fig = px.bar(curso_counts, x="Quantidade", y="Curso", orientation="h",
                         title="Top 12 Cursos", color="Quantidade", color_continuous_scale="Blues")
            fig.update_layout(height=350, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig)

    # Temáticas
    st.markdown('<p class="section-title">🏷️ Temáticas mais frequentes</p>', unsafe_allow_html=True)
    kw_df = _extract_keywords(df_tccs, "palavras_chaves")
    if not kw_df.empty:
        fig = px.bar(kw_df.head(20), x="Frequência", y="Tema", orientation="h",
                     color="Frequência", color_continuous_scale="Viridis",
                     title="Top 20 Temáticas em TCCs")
        fig.update_layout(height=500, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)

    with st.expander("📋 Tabela completa de TCCs"):
        cols = [c for c in ["titulo", "ano", "curso", "nome_professor", "campus", "sigla"] if c in df_tccs.columns]
        st.dataframe(df_tccs[cols], height=400)
        st.download_button("⬇️ Download CSV", df_tccs[cols].to_csv(index=False).encode("utf-8"), "tccs.csv")


def _render_artigos(df_pub):
    """Renderiza aba de artigos/publicações."""
    if df_pub.empty:
        st.info("Nenhuma publicação encontrada com os filtros atuais.")
        return

    # Filtra apenas artigos publicados para esta aba
    artigos = df_pub[df_pub["tipo"].isin(["Artigo Publicado", "Artigo Aceito para Publicação", "Artigo em Conferência"])] if "tipo" in df_pub.columns else df_pub

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Artigos", f"{len(artigos):,}")
    col2.metric("Autores", artigos["autor"].nunique() if "autor" in artigos.columns else 0)
    col3.metric("Total Publicações (todos tipos)", f"{len(df_pub):,}")

    col_a, col_b = st.columns(2)
    with col_a:
        if "ano" in df_pub.columns:
            df_ano = df_pub.copy()
            df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
            df_ano = df_ano[df_ano["ano"] >= 2000]
            ano_counts = df_ano["ano"].dropna().value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.line(ano_counts, x="Ano", y="Quantidade", title="Publicações por Ano",
                         markers=True, color_discrete_sequence=["#e53e3e"])
            fig.update_layout(height=350)
            st.plotly_chart(fig)

    with col_b:
        if "tipo" in df_pub.columns:
            tipo_counts = df_pub["tipo"].value_counts().head(10).reset_index()
            tipo_counts.columns = ["Tipo", "Quantidade"]
            fig = px.bar(tipo_counts, x="Quantidade", y="Tipo", orientation="h",
                         title="Top 10 Tipos de Produção", color="Quantidade",
                         color_continuous_scale="Reds")
            fig.update_layout(height=350, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig)

    # Por campus
    if "campus" in df_pub.columns:
        campus_counts = df_pub["campus"].dropna().value_counts().head(15).reset_index()
        campus_counts.columns = ["Campus", "Quantidade"]
        fig = px.bar(campus_counts, x="Quantidade", y="Campus", orientation="h",
                     title="Publicações por Campus (Top 15)", color="Quantidade",
                     color_continuous_scale="Oranges")
        fig.update_layout(height=400, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)

    with st.expander("📋 Tabela completa"):
        cols = [c for c in ["titulo", "tipo", "autor", "ano", "campus", "sigla"] if c in df_pub.columns]
        st.dataframe(df_pub[cols], height=400)
        st.download_button("⬇️ Download CSV", df_pub[cols].to_csv(index=False).encode("utf-8"), "publicacoes.csv")


def _render_projetos(df_proj):
    """Renderiza aba de projetos."""
    if df_proj.empty:
        st.info("Nenhum projeto encontrado com os filtros atuais.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Projetos", f"{len(df_proj):,}")
    col2.metric("Pesquisadores", df_proj["nome_professor"].nunique() if "nome_professor" in df_proj.columns else 0)
    col3.metric("Naturezas", df_proj["natureza"].nunique() if "natureza" in df_proj.columns else 0)

    col_a, col_b = st.columns(2)
    with col_a:
        if "natureza" in df_proj.columns:
            nat_counts = df_proj["natureza"].dropna().value_counts().reset_index()
            nat_counts.columns = ["Natureza", "Quantidade"]
            fig = px.pie(nat_counts, values="Quantidade", names="Natureza",
                         title="Projetos por Natureza", hole=0.4)
            fig.update_layout(height=350)
            st.plotly_chart(fig)

    with col_b:
        if "data_inicio" in df_proj.columns:
            df_p = df_proj.copy()
            df_p["ano_inicio"] = df_p["data_inicio"].str[:4]
            df_p["ano_inicio"] = pd.to_numeric(df_p["ano_inicio"], errors="coerce")
            df_p = df_p[df_p["ano_inicio"] >= 2000]
            ano_counts = df_p["ano_inicio"].dropna().value_counts().sort_index().reset_index()
            ano_counts.columns = ["Ano", "Quantidade"]
            fig = px.bar(ano_counts, x="Ano", y="Quantidade", title="Projetos por Ano de Início",
                         color="Quantidade", color_continuous_scale="Greens")
            fig.update_layout(height=350)
            st.plotly_chart(fig)

    with st.expander("📋 Tabela completa"):
        cols = [c for c in ["titulo", "natureza", "nome_professor", "sigla", "data_inicio", "data_fim"] if c in df_proj.columns]
        st.dataframe(df_proj[cols], height=400)
        st.download_button("⬇️ Download CSV", df_proj[cols].to_csv(index=False).encode("utf-8"), "projetos.csv")


def _render_consolidado(df_tccs, df_pub, df_proj):
    """Visão consolidada de todas as temáticas."""
    st.markdown('<p class="section-title">📊 Visão Consolidada - Todas as Temáticas</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("📝 TCCs", f"{len(df_tccs):,}" if not df_tccs.empty else 0)
    col2.metric("📄 Publicações", f"{len(df_pub):,}" if not df_pub.empty else 0)
    col3.metric("🔬 Projetos", f"{len(df_proj):,}" if not df_proj.empty else 0)

    # Combina palavras-chave de todas as fontes
    all_keywords = []
    for df, label, col in [(df_tccs, "TCC", "palavras_chaves"), (df_pub, "Publicação", "titulo")]:
        if df.empty or col not in df.columns:
            continue
        if col == "palavras_chaves":
            for kws in df[col].dropna():
                for kw in str(kws).split(";"):
                    kw = kw.strip().lower()
                    if kw and len(kw) > 2 and len(kw) < 80:
                        all_keywords.append({"tema": kw, "tipo": label})

    if all_keywords:
        df_kw = pd.DataFrame(all_keywords)
        top_temas = df_kw["tema"].value_counts().head(25).index.tolist()
        df_kw_top = df_kw[df_kw["tema"].isin(top_temas)]
        pivot = df_kw_top.groupby(["tema", "tipo"]).size().reset_index(name="count")
        fig = px.bar(pivot, x="count", y="tema", color="tipo", orientation="h",
                     title="Top 25 Temáticas (todas as fontes)",
                     color_discrete_map={"TCC": "#2b6cb0", "Publicação": "#e53e3e", "Projeto": "#38a169"})
        fig.update_layout(height=600, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)
    else:
        st.info("Sem dados de palavras-chave disponíveis para os filtros selecionados.")


# ─── PÁGINA: RANKING ───
def page_ranking(df_prof, df_formacao):
    """Página de ranking com IPA."""
    st.markdown("""
    <div class="main-header">
        <h1>🏆 Ranking de Produtividade Acadêmica</h1>
        <p>Índice de Produtividade Acadêmica (IPA) - 11 componentes ponderados</p>
    </div>
    """, unsafe_allow_html=True)

    if df_prof is None or df_prof.empty or "ipa" not in df_prof.columns:
        st.warning("Dados de ranking não disponíveis. Execute o pipeline primeiro.")
        return

    df_rank = df_prof.sort_values("ipa", ascending=False).reset_index(drop=True)
    df_rank["posicao"] = range(1, len(df_rank) + 1)

    # Top 3
    st.markdown('<p class="section-title">🥇 Top 3 Pesquisadores</p>', unsafe_allow_html=True)
    medals = ["🥇", "🥈", "🥉"]
    cols = st.columns(3)
    for i, col in enumerate(cols):
        if i < len(df_rank):
            row = df_rank.iloc[i]
            col.metric(
                f"{medals[i]} {row.get('nome', 'N/A')}",
                f"IPA: {row['ipa']:.1f}",
                f"{row.get('sigla', '')} • {row.get('campus', '')}"
            )

    # Gráfico Top 20
    st.markdown('<p class="section-title">📊 Top 20 - IPA</p>', unsafe_allow_html=True)
    top20 = df_rank.head(20)
    fig = px.bar(
        top20, x="ipa", y="nome", orientation="h",
        color="ipa", color_continuous_scale="Viridis",
        hover_data=["sigla", "campus", "area_cnpq"] if "area_cnpq" in top20.columns else ["sigla", "campus"],
    )
    fig.update_layout(height=550, yaxis=dict(autorange="reversed"), margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig)

    # Composição do IPA
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<p class="section-title">📐 Composição do IPA (Pesos)</p>', unsafe_allow_html=True)
        pesos_df = pd.DataFrame([
            {"Componente": k.replace("_", " ").title(), "Peso (%)": v * 100}
            for k, v in PESOS_RANKING.items()
        ]).sort_values("Peso (%)", ascending=False)
        fig = px.bar(pesos_df, x="Peso (%)", y="Componente", orientation="h",
                     color="Peso (%)", color_continuous_scale="Blues")
        fig.update_layout(height=400, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)

    with col_b:
        st.markdown('<p class="section-title">🎓 Titulação no Ranking</p>', unsafe_allow_html=True)
        if df_formacao is not None and not df_formacao.empty:
            # Maior titulação por professor
            nivel_map = {"pos_doutorado": "Pós-Doc", "doutorado": "Doutor",
                        "mestrado": "Mestre", "especializacao": "Especialista", "graduacao": "Graduado"}
            df_form_c = df_formacao.copy()
            df_form_c["peso"] = df_form_c["nivel"].map(PESOS_TITULACAO).fillna(0)
            max_tit = df_form_c.groupby("slug_professor")["nivel"].apply(
                lambda x: x.iloc[df_form_c.loc[x.index, "peso"].argmax()] if len(x) > 0 else "graduacao"
            ).reset_index()
            max_tit.columns = ["slug", "maior_titulacao"]
            max_tit["maior_titulacao"] = max_tit["maior_titulacao"].map(nivel_map).fillna("Outro")
            tit_counts = max_tit["maior_titulacao"].value_counts().reset_index()
            tit_counts.columns = ["Titulação", "Quantidade"]
            fig = px.pie(tit_counts, values="Quantidade", names="Titulação", hole=0.4,
                         color_discrete_sequence=["#1a365d", "#2b6cb0", "#4299e1", "#90cdf4", "#bee3f8"])
            fig.update_layout(height=400)
            st.plotly_chart(fig)
        else:
            st.info("Dados de titulação sendo extraídos...")

    # Tabela completa
    with st.expander("📋 Ranking Completo"):
        cols_rank = [c for c in ["posicao", "nome", "sigla", "campus", "area_cnpq", "ipa",
                                  "total_publicacoes", "total_orientacoes", "total_projetos",
                                  "total_bancas_final", "titulacao_score"] if c in df_rank.columns]
        st.dataframe(df_rank[cols_rank], height=500)
        st.download_button("⬇️ Download Ranking", df_rank[cols_rank].to_csv(index=False).encode("utf-8"), "ranking.csv")


# ─── PÁGINA: PUBLICAÇÕES ───
def page_publicacoes(df_pub, filtros):
    """Página dedicada a publicações."""
    st.markdown("""
    <div class="main-header">
        <h1>📄 Publicações</h1>
        <p>Análise detalhada da produção acadêmica por tipo, ano e campus</p>
    </div>
    """, unsafe_allow_html=True)

    if df_pub is None or df_pub.empty:
        st.warning("Nenhuma publicação encontrada.")
        return

    df_pub_f = df_pub.copy()
    if filtros["sigla"]:
        df_pub_f = df_pub_f[df_pub_f["sigla"].isin(filtros["sigla"])]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", f"{len(df_pub_f):,}")
    col2.metric("Tipos", df_pub_f["tipo"].nunique() if "tipo" in df_pub_f.columns else 0)
    col3.metric("Autores", df_pub_f["autor"].nunique() if "autor" in df_pub_f.columns else 0)
    col4.metric("Instituições", df_pub_f["sigla"].nunique() if "sigla" in df_pub_f.columns else 0)

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        if "tipo" in df_pub_f.columns:
            tipo_counts = df_pub_f["tipo"].value_counts().head(15).reset_index()
            tipo_counts.columns = ["Tipo", "Quantidade"]
            fig = px.treemap(tipo_counts, path=["Tipo"], values="Quantidade",
                            title="Distribuição por Tipo de Produção",
                            color="Quantidade", color_continuous_scale="Blues")
            fig.update_layout(height=450)
            st.plotly_chart(fig)

    with col_b:
        if "ano" in df_pub_f.columns:
            df_ano = df_pub_f.copy()
            df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
            df_ano = df_ano[(df_ano["ano"] >= 2000) & (df_ano["ano"] <= 2026)]
            if "tipo" in df_ano.columns:
                # Top 5 tipos ao longo do tempo
                top_tipos = df_ano["tipo"].value_counts().head(5).index.tolist()
                df_top = df_ano[df_ano["tipo"].isin(top_tipos)]
                ano_tipo = df_top.groupby(["ano", "tipo"]).size().reset_index(name="count")
                fig = px.line(ano_tipo, x="ano", y="count", color="tipo",
                             title="Evolução dos Top 5 Tipos", markers=True)
                fig.update_layout(height=450)
                st.plotly_chart(fig)

    with st.expander("📋 Dados completos"):
        cols = [c for c in ["titulo", "tipo", "autor", "ano", "campus", "sigla"] if c in df_pub_f.columns]
        st.dataframe(df_pub_f[cols], height=400)
        st.download_button("⬇️ Download", df_pub_f[cols].to_csv(index=False).encode("utf-8"), "publicacoes_completo.csv")


# ─── PÁGINA: PERFIL DO PROFESSOR ───
def page_perfil_professor(df_prof, df_pub, df_detalhes, df_formacao, df_bancas):
    """Página de perfil individual do professor."""
    st.markdown("""
    <div class="main-header">
        <h1>👤 Perfil do Professor</h1>
        <p>Histórico completo, pontuação detalhada e gráfico radar de produtividade</p>
    </div>
    """, unsafe_allow_html=True)

    if df_prof is None or df_prof.empty:
        st.warning("Sem dados de professores.")
        return

    # Seletor
    nomes = sorted(df_prof["nome"].dropna().unique().tolist())
    nome_sel = st.selectbox("Selecione o professor:", [""] + nomes)

    if not nome_sel:
        st.info("👆 Selecione um professor para ver o perfil completo.")
        return

    prof = df_prof[df_prof["nome"] == nome_sel].iloc[0]
    slug = prof.get("slug", "")

    # Header do professor
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Instituição", prof.get("sigla", "N/A"))
    col2.metric("Campus", prof.get("campus", "N/A"))
    col3.metric("Cargo", prof.get("cargo", "N/A"))
    col4.metric("Área CNPq", prof.get("area_cnpq", "N/A"))
    ipa_val = prof.get("ipa", 0)
    col5.metric("IPA", f"{ipa_val:.1f}" if pd.notna(ipa_val) else "N/A")

    st.markdown("---")

    # Formação acadêmica
    if df_formacao is not None and not df_formacao.empty:
        form_prof = df_formacao[df_formacao["slug_professor"] == slug]
        if not form_prof.empty:
            st.markdown('<p class="section-title">🎓 Formação Acadêmica</p>', unsafe_allow_html=True)
            nivel_map = {"pos_doutorado": "Pós-Doutorado", "doutorado": "Doutorado",
                        "mestrado": "Mestrado", "especializacao": "Especialização", "graduacao": "Graduação"}
            for _, row in form_prof.iterrows():
                nivel = nivel_map.get(row.get("nivel", ""), row.get("nivel", ""))
                curso = row.get("nome_curso", "")
                inst = row.get("nome_instituicao", "")
                ano = row.get("ano_conclusao", "")
                status = row.get("status", "")
                emoji = {"Pós-Doutorado": "🏅", "Doutorado": "🎓", "Mestrado": "📘",
                         "Especialização": "📗", "Graduação": "📙"}.get(nivel, "📄")
                status_txt = f" ({status})" if status and status != "CONCLUIDO" else ""
                st.markdown(f"**{emoji} {nivel}** — {curso} • {inst} • {ano}{status_txt}")

    # Gráfico radar
    if "ipa" in df_prof.columns and pd.notna(ipa_val):
        st.markdown('<p class="section-title">📊 Perfil de Produtividade (Radar)</p>', unsafe_allow_html=True)
        score_cols = [
            ("score_publicacoes", "Publicações"), ("score_impacto", "Impacto"),
            ("score_diversidade", "Diversidade"), ("score_recencia", "Recência"),
            ("score_orientacoes", "Orientações"), ("score_projetos", "Projetos"),
            ("score_tempo_docencia", "Docência"), ("score_comissoes_bancas", "Bancas"),
            ("score_extensao", "Extensão"), ("score_titulacao", "Titulação"),
            ("score_gestao_academica", "Gestão"),
        ]
        categories = [s[1] for s in score_cols]
        values = [float(prof.get(s[0], 0)) for s in score_cols]
        values.append(values[0])
        categories.append(categories[0])

        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill="toself",
                                              fillcolor="rgba(43, 108, 176, 0.2)",
                                              line=dict(color="#2b6cb0", width=2)))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                          height=450, margin=dict(l=50, r=50, t=30, b=30))
        st.plotly_chart(fig)

    # Detalhes da pontuação
    if "ipa" in df_prof.columns:
        st.markdown('<p class="section-title">📐 Detalhamento da Pontuação</p>', unsafe_allow_html=True)
        score_info = [
            ("score_publicacoes", "Publicações", "total_publicacoes", "publicacoes"),
            ("score_impacto", "Impacto", "pub_impacto", "impacto"),
            ("score_diversidade", "Diversidade", "tipos_distintos", "diversidade"),
            ("score_recencia", "Recência", "ano_mais_recente", "recencia"),
            ("score_orientacoes", "Orientações", "total_orientacoes", "orientacoes"),
            ("score_projetos", "Projetos", "total_projetos", "projetos"),
            ("score_tempo_docencia", "Docência", "atividades_ensino", "tempo_docencia"),
            ("score_comissoes_bancas", "Bancas", "total_bancas_final", "comissoes_bancas"),
            ("score_extensao", "Extensão", "total_extensao", "extensao"),
            ("score_titulacao", "Titulação", "titulacao_score", "titulacao"),
            ("score_gestao_academica", "Gestão", "gestao_score", "gestao_academica"),
        ]
        rows_data = []
        for score_col, label, raw_col, peso_key in score_info:
            score_val = prof.get(score_col, 0) if pd.notna(prof.get(score_col, 0)) else 0
            raw_val = prof.get(raw_col, 0) if pd.notna(prof.get(raw_col, 0)) else 0
            peso = PESOS_RANKING.get(peso_key, 0)
            contrib = score_val * peso
            rows_data.append({
                "Componente": label, "Valor Bruto": f"{raw_val:.0f}",
                "Score (0-100)": f"{score_val:.1f}", "Peso": f"{peso*100:.0f}%",
                "Contribuição": f"{contrib:.2f}",
            })
        st.dataframe(pd.DataFrame(rows_data), hide_index=True)

    # Publicações do professor
    if df_pub is not None and not df_pub.empty:
        pub_prof = df_pub[df_pub["slug_professor"] == slug]
        if not pub_prof.empty:
            st.markdown('<p class="section-title">📄 Publicações</p>', unsafe_allow_html=True)
            st.markdown(f"**Total: {len(pub_prof)} publicações**")
            cols = [c for c in ["titulo", "tipo", "ano", "campus"] if c in pub_prof.columns]
            st.dataframe(pub_prof[cols].sort_values("ano", ascending=False), height=300)

    # Bancas
    if df_bancas is not None and not df_bancas.empty:
        bancas_prof = df_bancas[df_bancas["slug_professor"] == slug]
        if not bancas_prof.empty:
            st.markdown('<p class="section-title">📋 Participação em Bancas</p>', unsafe_allow_html=True)
            st.markdown(f"**Total: {len(bancas_prof)} bancas**")
            cols = [c for c in ["tipo_banca", "natureza", "titulo", "ano", "nome_candidato"] if c in bancas_prof.columns]
            st.dataframe(bancas_prof[cols].sort_values("ano", ascending=False) if "ano" in bancas_prof.columns else bancas_prof[cols],
                        height=300)


# ─── PÁGINA: METODOLOGIA ───
def page_metodologia():
    """Página sobre a metodologia do IPA."""
    st.markdown("""
    <div class="main-header">
        <h1>ℹ️ Metodologia</h1>
        <p>Como funciona o Índice de Produtividade Acadêmica (IPA) e a análise temática</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ## 📐 Fórmula do IPA (Índice de Produtividade Acadêmica)

    O IPA é uma métrica composta que avalia a produtividade dos pesquisadores considerando
    **11 dimensões** da atuação acadêmica:

    ```
    IPA = (Pub × 15%) + (Imp × 12%) + (Div × 5%) + (Rec × 8%) + (Ori × 12%)
        + (Proj × 10%) + (Doc × 8%) + (Ban × 8%) + (Ext × 5%) + (Tit × 12%) + (Gest × 5%)
    ```

    ---

    ## 📊 Componentes do IPA

    | # | Componente | Peso | O que mede |
    |---|-----------|------|------------|
    | 1 | **Publicações** | 15% | Total de publicações registradas |
    | 2 | **Impacto** | 12% | Soma ponderada por tipo (Tese=10, Patente=9, Livro=7, Artigo=6) |
    | 3 | **Diversidade** | 5% | Tipos distintos de produção |
    | 4 | **Recência** | 8% | Ano da publicação mais recente |
    | 5 | **Orientações** | 12% | TCCs + IC + outras orientações concluídas |
    | 6 | **Projetos** | 10% | Participação em projetos de pesquisa/extensão |
    | 7 | **Docência** | 8% | Atividades de ensino registradas |
    | 8 | **Bancas** | 8% | Participação em bancas (graduação, mestrado, doutorado, concursos) |
    | 9 | **Extensão** | 5% | Atividades de extensão |
    | 10 | **Titulação** | 12% | Maior titulação (Pós-Doc=12, Doutor=10, Mestre=7, Esp.=4, Grad.=2) |
    | 11 | **Gestão Acadêmica** | 5% | Coordenação, NDE, colegiado, direção, comissões |

    ---

    ## 🎓 Pesos de Titulação

    | Nível | Pontuação |
    |-------|-----------|
    | Pós-Doutorado | 12 |
    | Doutorado | 10 |
    | Mestrado | 7 |
    | Especialização | 4 |
    | Graduação | 2 |

    ---

    ## ⚖️ Pesos de Impacto por Tipo de Produção

    | Peso | Tipos |
    |------|-------|
    | **10** | Tese |
    | **9** | Patente Depositada |
    | **8** | Dissertação |
    | **7** | Livro Publicado |
    | **6** | Artigo Publicado |
    | **5** | Artigo Aceito, Capítulo de Livro, Software, Produto Tecnológico |
    | **4** | Trabalho Completo em Eventos, Processos ou Técnicas |
    | **3** | Preprint, Relatório, Material Didático |
    | **2** | Resumo, Texto em Jornal, Apresentação |
    | **1** | Organização de Evento, Editoração, Outras |

    ---

    ## 🔄 Normalização

    Cada componente é normalizado usando **Min-Max Scaling** (0 a 100):
    ```
    Score = ((valor - mínimo) / (máximo - mínimo)) × 100
    ```

    ---

    ## 📚 Análise Temática

    A análise temática extrai **palavras-chave** de:
    - **TCCs**: Orientações concluídas (campo `palavrasChave` do Lattes)
    - **Artigos**: Produção bibliográfica com palavras-chave
    - **Projetos**: Descrição e título dos projetos de pesquisa

    ---

    ## 🏛️ Fonte dos Dados

    Todos os dados são extraídos da **API interna do Portal Integra** de cada instituição:
    - `/api/portfolio/pessoa/data` — Lista de servidores
    - `/api/portfolio/producao/data` — Publicações
    - `/api/portfolio/pessoa/s/{slug}` — Currículo completo (formação, bancas, projetos, orientações)
    """)


# ─── PÁGINA: COMPARAÇÃO ───
def page_comparacao(df_prof, df_pub, df_tccs, df_projetos, filtros):
    """Página de comparação entre instituições, servidores e temáticas."""
    st.markdown("""
    <div class="main-header">
        <h1>🔄 Comparação</h1>
        <p>Compare instituições, pesquisadores e temáticas usando NLP e similaridade</p>
    </div>
    """, unsafe_allow_html=True)

    tab_inst, tab_pesq, tab_temas, tab_sobre = st.tabs([
        "🏛️ Instituições", "👥 Pesquisadores", "🏷️ Grupos Temáticos", "ℹ️ Sobre"
    ])

    with tab_inst:
        _comparar_instituicoes(df_prof, df_pub, df_tccs, df_projetos)
    with tab_pesq:
        _comparar_pesquisadores(df_prof, df_pub)
    with tab_temas:
        _grupos_tematicos(df_tccs)
    with tab_sobre:
        _sobre_comparacao()


def _comparar_instituicoes(df_prof, df_pub, df_tccs, df_projetos):
    """Compara múltiplas instituições."""
    st.markdown('<p class="section-title">🏛️ Comparação entre Instituições</p>', unsafe_allow_html=True)

    siglas = sorted(df_prof["sigla"].dropna().unique().tolist()) if not df_prof.empty else []
    if len(siglas) < 2:
        st.info("Necessário pelo menos 2 instituições para comparar.")
        return

    default_siglas = ["IFB"] if "IFB" in siglas else siglas[:1]
    siglas_selecionadas = st.multiselect(
        "Selecione as instituições para comparar (2 ou mais):",
        options=siglas, default=default_siglas, key="comp_inst_multi"
    )

    if len(siglas_selecionadas) < 2:
        st.info("Selecione pelo menos 2 instituições.")
        return

    # Tabela comparativa de métricas
    st.markdown("---")
    rows = []
    for sigla in siglas_selecionadas:
        profs = df_prof[df_prof["sigla"] == sigla]
        pubs = df_pub[df_pub["sigla"] == sigla] if not df_pub.empty else pd.DataFrame()
        tccs = df_tccs[df_tccs["sigla"] == sigla] if not df_tccs.empty else pd.DataFrame()
        projs = df_projetos[df_projetos["sigla"] == sigla] if not df_projetos.empty else pd.DataFrame()
        n_prof = len(profs)
        rows.append({
            "Instituição": sigla,
            "Pesquisadores": n_prof,
            "Publicações": len(pubs),
            "Pub/Pesq.": round(len(pubs) / n_prof, 1) if n_prof > 0 else 0,
            "TCCs": len(tccs),
            "TCC/Pesq.": round(len(tccs) / n_prof, 1) if n_prof > 0 else 0,
            "Projetos": len(projs),
            "Proj/Pesq.": round(len(projs) / n_prof, 1) if n_prof > 0 else 0,
        })
    df_comp = pd.DataFrame(rows)
    st.dataframe(df_comp, hide_index=True)

    # Gráfico de barras agrupadas
    fig = px.bar(df_comp, x="Instituição", y=["Pub/Pesq.", "TCC/Pesq.", "Proj/Pesq."],
                 barmode="group", title="Produtividade per capita")
    fig.update_layout(height=400)
    st.plotly_chart(fig)

    # Perfil temático comparativo
    if not df_tccs.empty and "palavras_chaves" in df_tccs.columns and NLP_AVAILABLE:
        st.markdown('<p class="section-title">📊 Perfil Temático Comparativo (NLP)</p>', unsafe_allow_html=True)

        with st.spinner("Calculando perfis temáticos..."):
            profiles = []
            for sigla in siglas_selecionadas:
                kws = df_tccs[df_tccs["sigla"] == sigla]["palavras_chaves"].dropna().tolist()
                profile = get_institution_profile(kws)
                if not profile.empty:
                    profile = profile.head(10)
                    profile["instituicao"] = sigla
                    profiles.append(profile)

            if profiles:
                combined = pd.concat(profiles)
                fig = px.bar(combined, x="frequencia", y="tema", color="instituicao", orientation="h",
                             barmode="group", title="Top 10 Temáticas por Instituição")
                fig.update_layout(height=max(400, len(combined["tema"].unique()) * 25),
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig)

        # Matriz de similaridade
        if len(siglas_selecionadas) >= 2:
            st.markdown('<p class="section-title">🔗 Matriz de Similaridade Temática</p>', unsafe_allow_html=True)
            sim_matrix = pd.DataFrame(index=siglas_selecionadas, columns=siglas_selecionadas, dtype=float)
            for i, sa in enumerate(siglas_selecionadas):
                for j, sb in enumerate(siglas_selecionadas):
                    if i == j:
                        sim_matrix.loc[sa, sb] = 1.0
                    elif i < j:
                        result = compare_institutions(df_tccs, sa, sb)
                        sim_matrix.loc[sa, sb] = result["similaridade"]
                        sim_matrix.loc[sb, sa] = result["similaridade"]

            fig = px.imshow(sim_matrix.astype(float), text_auto=".2f", color_continuous_scale="Blues",
                            title="Similaridade de Cosseno entre Instituições")
            fig.update_layout(height=400)
            st.plotly_chart(fig)

    # Área CNPq comparativa
    if "area_cnpq" in df_prof.columns:
        st.markdown('<p class="section-title">🎯 Distribuição por Área CNPq</p>', unsafe_allow_html=True)
        area_frames = []
        for sigla in siglas_selecionadas:
            area_data = df_prof[df_prof["sigla"] == sigla]["area_cnpq"].value_counts().reset_index()
            area_data.columns = ["Área", "Quantidade"]
            area_data["Instituição"] = sigla
            area_frames.append(area_data)
        combined_area = pd.concat(area_frames)
        fig = px.bar(combined_area, x="Quantidade", y="Área", color="Instituição",
                     barmode="group", orientation="h")
        fig.update_layout(height=450, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)
        st.metric("TCCs", len(tccs_b))
        st.metric("Projetos", len(proj_b))

    # Similaridade temática
    st.markdown("---")
    st.markdown('<p class="section-title">📊 Similaridade Temática (NLP)</p>', unsafe_allow_html=True)

    if not df_tccs.empty and "palavras_chaves" in df_tccs.columns:
        with st.spinner("Calculando similaridade temática..."):
            result = compare_institutions(df_tccs, sigla_a, sigla_b)

        sim_pct = result["similaridade"] * 100
        st.metric("Similaridade de Cosseno", f"{sim_pct:.1f}%",
                  help="0% = nenhuma semelhança, 100% = temáticas idênticas")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f"**Temas em comum ({len(result['comuns'])})**")
            for t in result["comuns"][:10]:
                st.markdown(f"- {t}")
        with col_b:
            st.markdown(f"**Exclusivos {sigla_a} ({len(result['exclusivos_a'])})**")
            for t in result["exclusivos_a"][:10]:
                st.markdown(f"- {t}")
        with col_c:
            st.markdown(f"**Exclusivos {sigla_b} ({len(result['exclusivos_b'])})**")
            for t in result["exclusivos_b"][:10]:
                st.markdown(f"- {t}")

        # Gráfico comparativo de perfis
        if "profile_a" in result and not result["profile_a"].empty:
            pa = result["profile_a"].head(15).copy()
            pb = result["profile_b"].head(15).copy()
            pa["instituicao"] = sigla_a
            pb["instituicao"] = sigla_b
            combined = pd.concat([pa, pb])
            fig = px.bar(combined, x="frequencia", y="tema", color="instituicao", orientation="h",
                         barmode="group", title="Top 15 Temáticas por Instituição")
            fig.update_layout(height=500, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig)

    # Comparação por área CNPq
    if "area_cnpq" in df_prof.columns:
        st.markdown('<p class="section-title">🎯 Distribuição por Área CNPq</p>', unsafe_allow_html=True)
        area_a = prof_a["area_cnpq"].value_counts().reset_index()
        area_a.columns = ["Área", "Quantidade"]
        area_a["Instituição"] = sigla_a
        area_b = prof_b["area_cnpq"].value_counts().reset_index()
        area_b.columns = ["Área", "Quantidade"]
        area_b["Instituição"] = sigla_b
        combined_area = pd.concat([area_a, area_b])
        fig = px.bar(combined_area, x="Quantidade", y="Área", color="Instituição",
                     barmode="group", orientation="h")
        fig.update_layout(height=400, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)


def _comparar_pesquisadores(df_prof, df_pub):
    """Compara múltiplos pesquisadores."""
    st.markdown('<p class="section-title">👥 Comparação entre Pesquisadores</p>', unsafe_allow_html=True)

    if df_prof is None or df_prof.empty:
        st.info("Sem dados de professores.")
        return

    nomes = sorted(df_prof["nome"].dropna().unique().tolist())
    nomes_selecionados = st.multiselect(
        "Selecione pesquisadores para comparar (2 ou mais):",
        options=nomes, default=[], key="comp_pesq_multi"
    )

    if len(nomes_selecionados) < 2:
        st.info("Selecione pelo menos 2 pesquisadores.")
        return

    # Tabela comparativa
    st.markdown("---")
    rows = []
    profs_data = []
    for nome in nomes_selecionados:
        prof = df_prof[df_prof["nome"] == nome].iloc[0]
        profs_data.append(prof)
        rows.append({
            "Nome": nome,
            "Instituição": prof.get("sigla", ""),
            "Campus": prof.get("campus", ""),
            "Área CNPq": prof.get("area_cnpq", ""),
            "IPA": round(float(prof.get("ipa", 0)), 1) if pd.notna(prof.get("ipa", 0)) else 0,
            "Publicações": int(prof.get("total_publicacoes", 0)),
            "Orientações": int(prof.get("total_orientacoes", 0)),
            "Projetos": int(prof.get("total_projetos", 0)),
            "Bancas": int(prof.get("total_bancas_final", 0)) if pd.notna(prof.get("total_bancas_final", 0)) else 0,
            "Titulação": int(prof.get("titulacao_score", 0)) if pd.notna(prof.get("titulacao_score", 0)) else 0,
        })
    df_comp = pd.DataFrame(rows)
    st.dataframe(df_comp, hide_index=True)

    # Radar comparativo (múltiplos)
    if "ipa" in df_prof.columns:
        st.markdown('<p class="section-title">📊 Radar Comparativo</p>', unsafe_allow_html=True)
        score_cols = [
            ("score_publicacoes", "Publicações"), ("score_impacto", "Impacto"),
            ("score_orientacoes", "Orientações"), ("score_projetos", "Projetos"),
            ("score_tempo_docencia", "Docência"), ("score_comissoes_bancas", "Bancas"),
            ("score_extensao", "Extensão"), ("score_titulacao", "Titulação"),
        ]
        cats = [s[1] for s in score_cols] + [score_cols[0][1]]

        colors = px.colors.qualitative.Set2
        fig = go.Figure()
        for i, (nome, prof) in enumerate(zip(nomes_selecionados, profs_data)):
            vals = [float(prof.get(s[0], 0)) if pd.notna(prof.get(s[0], 0)) else 0 for s in score_cols]
            vals.append(vals[0])
            color = colors[i % len(colors)]
            fig.add_trace(go.Scatterpolar(
                r=vals, theta=cats, fill="toself", name=nome,
                line=dict(color=color, width=2)
            ))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=500)
        st.plotly_chart(fig)

    # Gráfico de barras comparativo
    st.markdown('<p class="section-title">📊 Comparação por Componente</p>', unsafe_allow_html=True)
    metrics = ["Publicações", "Orientações", "Projetos", "Bancas"]
    bar_data = []
    for row in rows:
        for m in metrics:
            bar_data.append({"Pesquisador": row["Nome"], "Métrica": m, "Valor": row[m]})
    df_bar = pd.DataFrame(bar_data)
    fig = px.bar(df_bar, x="Métrica", y="Valor", color="Pesquisador", barmode="group",
                 title="Métricas brutas por pesquisador")
    fig.update_layout(height=400)
    st.plotly_chart(fig)


def _grupos_tematicos(df_tccs):
    """Agrupa temáticas usando NLP."""
    st.markdown('<p class="section-title">🏷️ Grupos Temáticos (Clustering NLP)</p>', unsafe_allow_html=True)

    if not NLP_AVAILABLE:
        st.warning("Módulo NLP não disponível. Verifique a instalação do scikit-learn.")
        return

    if df_tccs.empty or "palavras_chaves" not in df_tccs.columns:
        st.info("Sem dados de palavras-chave para agrupar.")
        return

    n_clusters = st.slider("Número de grupos temáticos", 3, 15, 8)

    with st.spinner("Agrupando temáticas com TF-IDF + Clustering Hierárquico..."):
        result = cluster_themes(df_tccs["palavras_chaves"], n_clusters=n_clusters)

    if result.empty:
        st.warning("Dados insuficientes para agrupamento.")
        return

    # Visualização por grupo
    fig = px.bar(result, x="frequencia", y="tema", color="grupo_nome", orientation="h",
                 title="Temáticas agrupadas por similaridade semântica",
                 color_discrete_sequence=px.colors.qualitative.Set3)
    fig.update_layout(height=max(500, len(result) * 18), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig)

    # Tabela de grupos
    with st.expander("📋 Detalhes dos grupos"):
        for grupo in sorted(result["grupo"].unique()):
            grupo_data = result[result["grupo"] == grupo]
            nome_grupo = grupo_data.iloc[0]["grupo_nome"]
            st.markdown(f"**Grupo {grupo + 1}: {nome_grupo}** ({len(grupo_data)} temas)")
            st.dataframe(grupo_data[["tema", "frequencia"]], hide_index=True)


def _sobre_comparacao():
    """Aba sobre da comparação."""
    st.markdown("""
    ## ℹ️ Sobre a Comparação

    ### 🏛️ Comparação entre Instituições
    Compara duas instituições da Rede Federal usando:
    - **Similaridade de Cosseno**: Mede o quão parecidas são as temáticas de pesquisa entre duas instituições.
      Calculada sobre vetores TF (Term Frequency) das palavras-chave dos TCCs.
    - **Temas em comum vs exclusivos**: Identifica quais temáticas são compartilhadas e quais são únicas de cada IF.
    - **Perfil por Área CNPq**: Compara a distribuição de pesquisadores por grande área do conhecimento.

    ### 👥 Comparação entre Pesquisadores
    Compara dois pesquisadores usando:
    - **Métricas brutas**: Publicações, orientações, projetos.
    - **Radar de produtividade**: Visualização dos scores normalizados (0-100) em cada dimensão do IPA.
    - **IPA**: Índice de Produtividade Acadêmica comparado.

    ### 🏷️ Grupos Temáticos
    Agrupa as temáticas de pesquisa usando:
    - **TF-IDF**: Vetorização das palavras-chave com ponderação por frequência e raridade.
    - **Clustering Hierárquico Aglomerativo**: Agrupa temas por similaridade de cosseno.
    - **Stopwords acadêmicas**: Remove termos genéricos que não contribuem para diferenciação temática.
    - O número de grupos pode ser ajustado pelo slider.

    ### Técnicas de NLP utilizadas
    | Técnica | Uso |
    |---------|-----|
    | TF-IDF | Vetorização de texto com ponderação |
    | Similaridade de Cosseno | Medir proximidade entre perfis temáticos |
    | Clustering Hierárquico | Agrupar temas semanticamente próximos |
    | Stopwords customizadas | Remover ruído acadêmico/institucional |
    | LDA (Latent Dirichlet Allocation) | Modelagem de tópicos probabilística |
    """)


# ─── PÁGINA: INSIGHTS ───
def page_insights(df_prof, df_pub, df_tccs, df_projetos, df_formacao, df_bancas):
    """Página de insights com regressão, tendências e análises estatísticas."""
    st.markdown("""
    <div class="main-header">
        <h1>📈 Insights & Tendências</h1>
        <p>Análises estatísticas, regressão linear, tendências e padrões nos dados</p>
    </div>
    """, unsafe_allow_html=True)

    tab_tend, tab_corr, tab_pred, tab_perfil, tab_sobre = st.tabs([
        "📈 Tendências", "🔗 Correlações", "🔮 Projeções", "🏛️ Perfil Institucional", "ℹ️ Sobre"
    ])

    with tab_tend:
        _insight_tendencias(df_pub, df_tccs, df_projetos)
    with tab_corr:
        _insight_correlacoes(df_prof)
    with tab_pred:
        _insight_projecoes(df_pub, df_tccs)
    with tab_perfil:
        _insight_perfil_institucional(df_prof, df_pub, df_tccs, df_projetos, df_formacao)
    with tab_sobre:
        _sobre_insights()


def _insight_tendencias(df_pub, df_tccs, df_projetos):
    """Análise de tendências temporais."""
    st.markdown('<p class="section-title">📈 Tendências de Produção Acadêmica</p>', unsafe_allow_html=True)
    from scipy import stats

    if not df_pub.empty and "ano" in df_pub.columns:
        df_ano = df_pub.copy()
        df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
        df_ano = df_ano[(df_ano["ano"] >= 2005) & (df_ano["ano"] <= 2025)]
        pub_por_ano = df_ano["ano"].value_counts().sort_index().reset_index()
        pub_por_ano.columns = ["Ano", "Publicações"]

        if len(pub_por_ano) >= 3:
            x = pub_por_ano["Ano"].values
            y = pub_por_ano["Publicações"].values
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            pub_por_ano["Tendência"] = slope * x + intercept

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=pub_por_ano["Ano"], y=pub_por_ano["Publicações"],
                                     mode="lines+markers", name="Publicações", line=dict(color="#2b6cb0")))
            fig.add_trace(go.Scatter(x=pub_por_ano["Ano"], y=pub_por_ano["Tendência"],
                                     mode="lines", name=f"Tendência (R²={r_value**2:.3f})",
                                     line=dict(color="#e53e3e", dash="dash")))
            fig.update_layout(title="Publicações por Ano com Regressão Linear", height=400)
            st.plotly_chart(fig)

            col1, col2, col3 = st.columns(3)
            col1.metric("Crescimento anual", f"+{slope:.0f} pub/ano" if slope > 0 else f"{slope:.0f} pub/ano")
            col2.metric("R² (ajuste)", f"{r_value**2:.3f}")
            col3.metric("p-valor", f"{p_value:.4f}")

    if not df_tccs.empty and "ano" in df_tccs.columns:
        st.markdown("---")
        df_ano_tcc = df_tccs.copy()
        df_ano_tcc["ano"] = pd.to_numeric(df_ano_tcc["ano"], errors="coerce")
        df_ano_tcc = df_ano_tcc[(df_ano_tcc["ano"] >= 2005) & (df_ano_tcc["ano"] <= 2025)]
        tcc_por_ano = df_ano_tcc["ano"].value_counts().sort_index().reset_index()
        tcc_por_ano.columns = ["Ano", "TCCs"]

        if len(tcc_por_ano) >= 3:
            x = tcc_por_ano["Ano"].values
            y = tcc_por_ano["TCCs"].values
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            tcc_por_ano["Tendência"] = slope * x + intercept

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tcc_por_ano["Ano"], y=tcc_por_ano["TCCs"],
                                     mode="lines+markers", name="TCCs", line=dict(color="#38a169")))
            fig.add_trace(go.Scatter(x=tcc_por_ano["Ano"], y=tcc_por_ano["Tendência"],
                                     mode="lines", name=f"Tendência (R²={r_value**2:.3f})",
                                     line=dict(color="#e53e3e", dash="dash")))
            fig.update_layout(title="TCCs por Ano com Regressão Linear", height=400)
            st.plotly_chart(fig)


def _insight_correlacoes(df_prof):
    """Análise de correlações entre variáveis do ranking."""
    st.markdown('<p class="section-title">🔗 Correlações entre Componentes do IPA</p>', unsafe_allow_html=True)

    if df_prof is None or df_prof.empty or "ipa" not in df_prof.columns:
        st.info("Dados de ranking necessários.")
        return

    score_cols = ["total_publicacoes", "pub_impacto", "tipos_distintos", "total_orientacoes",
                  "total_projetos", "total_bancas_final", "total_extensao", "atividades_ensino",
                  "titulacao_score", "gestao_score", "ipa"]
    available = [c for c in score_cols if c in df_prof.columns]

    if len(available) < 3:
        st.info("Dados insuficientes.")
        return

    df_corr = df_prof[available].corr()
    fig = px.imshow(df_corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                    title="Matriz de Correlação (Pearson)")
    fig.update_layout(height=500)
    st.plotly_chart(fig)

    # Insights automáticos
    st.markdown('<p class="section-title">💡 Insights Automáticos</p>', unsafe_allow_html=True)
    insights = []
    for i, col_a in enumerate(available):
        for col_b in available[i+1:]:
            corr_val = df_corr.loc[col_a, col_b]
            if abs(corr_val) > 0.5 and col_a != "ipa" and col_b != "ipa":
                direction = "positiva" if corr_val > 0 else "negativa"
                insights.append(f"**{col_a}** e **{col_b}**: correlação {direction} ({corr_val:.2f})")
    if insights:
        for ins in insights[:8]:
            st.markdown(f"- {ins}")

    # Scatter interativo
    st.markdown("---")
    col_x = st.selectbox("Eixo X", available, index=0)
    col_y = st.selectbox("Eixo Y", available, index=len(available)-1)
    fig = px.scatter(df_prof, x=col_x, y=col_y, color="sigla" if "sigla" in df_prof.columns else None,
                     hover_data=["nome"] if "nome" in df_prof.columns else None,
                     trendline="ols", title=f"{col_x} vs {col_y}")
    fig.update_layout(height=450)
    st.plotly_chart(fig)


def _insight_projecoes(df_pub, df_tccs):
    """Projeções futuras."""
    st.markdown('<p class="section-title">🔮 Projeções (Regressão Linear)</p>', unsafe_allow_html=True)
    from scipy import stats

    anos_projecao = st.slider("Projetar para quantos anos à frente?", 1, 5, 3)

    if not df_pub.empty and "ano" in df_pub.columns:
        df_ano = df_pub.copy()
        df_ano["ano"] = pd.to_numeric(df_ano["ano"], errors="coerce")
        df_ano = df_ano[(df_ano["ano"] >= 2010) & (df_ano["ano"] <= 2025)]
        pub_por_ano = df_ano["ano"].value_counts().sort_index()

        if len(pub_por_ano) >= 5:
            x = pub_por_ano.index.values.astype(float)
            y = pub_por_ano.values.astype(float)
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            anos_futuros = np.arange(x.max() + 1, x.max() + 1 + anos_projecao)
            projecao = slope * anos_futuros + intercept

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Histórico", line=dict(color="#2b6cb0")))
            fig.add_trace(go.Scatter(x=anos_futuros, y=projecao, mode="lines+markers",
                                     name="Projeção", line=dict(color="#e53e3e", dash="dot"),
                                     marker=dict(symbol="diamond")))
            fig.update_layout(title="Projeção de Publicações", height=400)
            st.plotly_chart(fig)

            st.markdown(f"""
            **Modelo**: Publicações = {slope:.1f} × Ano + {intercept:.0f}
            - Crescimento: **{slope:.0f} publicações/ano** | R² = {r_value**2:.3f}
            - Projeção {int(anos_futuros[-1])}: **~{int(projecao[-1]):,} publicações**
            """)


def _insight_perfil_institucional(df_prof, df_pub, df_tccs, df_projetos, df_formacao):
    """Perfil comparativo das instituições."""
    st.markdown('<p class="section-title">🏛️ Perfil Institucional Comparativo</p>', unsafe_allow_html=True)

    if df_prof is None or df_prof.empty:
        st.info("Sem dados.")
        return

    siglas = df_prof["sigla"].unique()
    rows = []
    for sigla in siglas:
        profs = df_prof[df_prof["sigla"] == sigla]
        pubs = df_pub[df_pub["sigla"] == sigla] if not df_pub.empty else pd.DataFrame()
        tccs = df_tccs[df_tccs["sigla"] == sigla] if not df_tccs.empty else pd.DataFrame()
        projs = df_projetos[df_projetos["sigla"] == sigla] if not df_projetos.empty else pd.DataFrame()
        n_prof = len(profs)
        doutores = 0
        if df_formacao is not None and not df_formacao.empty:
            form_sigla = df_formacao[df_formacao["sigla"] == sigla]
            doutores = form_sigla[form_sigla["nivel"].isin(["doutorado", "pos_doutorado"])]["slug_professor"].nunique()
        rows.append({
            "Instituição": sigla, "Pesquisadores": n_prof,
            "Publicações": len(pubs), "Pub/Pesq": round(len(pubs)/n_prof, 1) if n_prof else 0,
            "TCCs": len(tccs), "TCC/Pesq": round(len(tccs)/n_prof, 1) if n_prof else 0,
            "Projetos": len(projs), "Proj/Pesq": round(len(projs)/n_prof, 1) if n_prof else 0,
            "Doutores": doutores, "% Doutores": round(doutores/n_prof*100, 1) if n_prof else 0,
        })

    df_perfil = pd.DataFrame(rows).sort_values("Pub/Pesq", ascending=False)

    fig = px.bar(df_perfil, x="Instituição", y=["Pub/Pesq", "TCC/Pesq", "Proj/Pesq"],
                 barmode="group", title="Produtividade per capita por Instituição")
    fig.update_layout(height=400)
    st.plotly_chart(fig)

    if df_perfil["% Doutores"].sum() > 0:
        fig = px.scatter(df_perfil, x="% Doutores", y="Pub/Pesq", size="Pesquisadores",
                         text="Instituição", title="% Doutores vs Publicações per capita", trendline="ols")
        fig.update_traces(textposition="top center")
        fig.update_layout(height=400)
        st.plotly_chart(fig)

    with st.expander("📋 Tabela completa"):
        st.dataframe(df_perfil, hide_index=True)


def _sobre_insights():
    """Aba sobre dos insights."""
    st.markdown("""
    ## ℹ️ Sobre os Insights

    ### 📈 Tendências
    - **Regressão Linear**: Ajusta reta (y = ax + b) aos dados temporais.
    - **R²**: Qualidade do ajuste (0 a 1). Quanto mais próximo de 1, melhor a reta explica os dados.
    - **p-valor**: < 0.05 indica tendência estatisticamente significativa.

    ### 🔗 Correlações
    - **Pearson**: Mede relação linear entre variáveis (-1 a +1).
    - **Heatmap**: Visualiza todas as correlações simultaneamente.
    - **Scatter + OLS**: Explora relações com linha de tendência.

    ### 🔮 Projeções
    - **Extrapolação linear**: Projeta assumindo manutenção da tendência.
    - **Limitação**: Não captura mudanças de comportamento futuras.

    ### 🏛️ Perfil Institucional
    - **Per capita**: Normaliza pelo número de pesquisadores.
    - **% Doutores vs Produtividade**: Testa se titulação correlaciona com produção.

    ### Técnicas utilizadas
    | Técnica | Uso |
    |---------|-----|
    | Regressão Linear (scipy) | Tendências e projeções |
    | Correlação de Pearson | Relações entre variáveis |
    | OLS (plotly) | Linhas de tendência |
    | Normalização per capita | Comparação justa |
    """)


def main():
    """Função principal."""
    data = load_data()
    df_prof = data["prof"]
    df_pub = data["pub"]
    df_tccs = data["tccs"]
    df_projetos = data["projetos"]
    df_detalhes = data["detalhes"]
    df_formacao = data["formacao"]
    df_bancas = data["bancas"]

    if df_prof is None or df_prof.empty:
        st.error("⚠️ Nenhum dado encontrado. Execute o pipeline ETL primeiro:")
        st.code("python etl/pipeline.py --sigla IFB", language="bash")
        return

    # Calcula IPA
    df_prof = calculate_ipa(df_prof, df_pub, df_tccs, df_projetos, df_detalhes, df_formacao, df_bancas)

    # Sidebar
    filtros = render_sidebar(df_prof, df_tccs)
    df_prof_f = apply_filters(df_prof, filtros)

    # Aplica filtro de período aos dados temporais
    df_pub_f = apply_period_filter(df_pub, filtros, "ano")
    df_tccs_f = apply_period_filter(df_tccs, filtros, "ano")
    df_projetos_f = apply_period_filter_projetos(df_projetos, filtros)

    # Roteamento de páginas
    pagina = filtros["pagina"]
    if pagina == "🏠 Visão Geral":
        page_visao_geral(df_prof_f, df_pub_f, df_tccs_f, df_projetos_f, df_formacao, df_bancas)
    elif pagina == "📚 Análise Temática":
        page_analise_tematica(df_tccs_f, df_pub_f, df_projetos_f, filtros)
    elif pagina == "🔄 Comparação":
        page_comparacao(df_prof_f, df_pub_f, df_tccs_f, df_projetos_f, filtros)
    elif pagina == "📈 Insights":
        page_insights(df_prof, df_pub, df_tccs, df_projetos, df_formacao, df_bancas)
    elif pagina == "🏆 Ranking":
        page_ranking(df_prof_f, df_formacao)
    elif pagina == "📄 Publicações":
        page_publicacoes(df_pub_f, filtros)
    elif pagina == "👤 Perfil do Professor":
        page_perfil_professor(df_prof_f, df_pub_f, df_detalhes, df_formacao, df_bancas)
    elif pagina == "ℹ️ Metodologia":
        page_metodologia()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Erro ao carregar o dashboard: {e}")
        st.exception(e)
else:
    try:
        main()
    except Exception as e:
        st.error(f"Erro ao carregar o dashboard: {e}")
        st.exception(e)
