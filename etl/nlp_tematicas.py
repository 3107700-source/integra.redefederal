"""
Módulo de NLP para agrupamento temático.
Usa TF-IDF, LDA (Latent Dirichlet Allocation) e similaridade de cosseno
para identificar grupos temáticos nas produções acadêmicas.
"""

import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering


# ─── Stopwords PT-BR expandidas para contexto acadêmico ───
STOPWORDS_PT = set([
    # Artigos e preposições
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
    "por", "para", "com", "sem", "sob", "sobre", "entre", "até",
    "ao", "aos", "à", "às", "pelo", "pela", "pelos", "pelas",
    # Conjunções e pronomes
    "e", "ou", "mas", "que", "se", "como", "quando", "onde",
    "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas", "isto", "isso", "aquilo",
    "seu", "sua", "seus", "suas", "meu", "minha", "nosso", "nossa",
    "ele", "ela", "eles", "elas", "nós", "vós", "eu", "tu", "você",
    # Verbos auxiliares
    "ser", "estar", "ter", "haver", "ir", "vir", "fazer", "poder",
    "foi", "era", "são", "está", "tem", "há", "vai", "pode",
    "sido", "sendo", "tendo", "tendo", "feito", "dado",
    # Advérbios comuns
    "não", "mais", "muito", "bem", "já", "ainda", "também",
    "sempre", "nunca", "apenas", "só", "assim", "então", "aqui",
    "ali", "lá", "onde", "quando", "como", "porque", "porquê",
    # Palavras acadêmicas genéricas (stopwords de domínio)
    "estudo", "análise", "pesquisa", "trabalho", "artigo", "tcc",
    "monografia", "dissertação", "tese", "projeto", "proposta",
    "resultado", "resultados", "método", "metodologia", "abordagem",
    "objetivo", "objetivos", "conclusão", "conclusões", "introdução",
    "revisão", "literatura", "referências", "bibliográfica",
    "caso", "casos", "uso", "utilização", "aplicação", "desenvolvimento",
    "processo", "processos", "forma", "formas", "tipo", "tipos",
    "área", "áreas", "campo", "parte", "partes", "aspecto", "aspectos",
    "base", "bases", "dado", "dados", "informação", "informações",
    "sistema", "sistemas", "modelo", "modelos", "ferramenta", "ferramentas",
    "contexto", "cenário", "perspectiva", "perspectivas", "visão",
    "relação", "relações", "impacto", "impactos", "efeito", "efeitos",
    "papel", "importância", "contribuição", "contribuições",
    "problema", "problemas", "desafio", "desafios", "questão", "questões",
    "prática", "práticas", "teoria", "teórica", "teórico",
    "novo", "nova", "novos", "novas", "atual", "atuais",
    "grande", "grandes", "pequeno", "pequena", "maior", "menor",
    "primeiro", "segunda", "terceiro", "último", "próximo",
    "possível", "necessário", "importante", "principal", "diferentes",
    # Institucionais
    "instituto", "federal", "universidade", "faculdade", "campus",
    "professor", "professora", "aluno", "aluna", "alunos", "alunas",
    "docente", "discente", "servidor", "servidora",
    "curso", "disciplina", "aula", "ensino", "aprendizagem",
    "educação", "escola", "escolar", "acadêmico", "acadêmica",
    "brasil", "brasileiro", "brasileira", "nacional",
])


def preprocess_text(text):
    """Pré-processa texto: lowercase, remove pontuação, stopwords."""
    if not text or not isinstance(text, str):
        return ""
    text = text.lower()
    # Remove URLs, emails, números isolados
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'\b\d+\b', '', text)
    # Remove pontuação mas mantém hífens em palavras compostas
    text = re.sub(r'[^\w\s\-]', ' ', text)
    # Remove espaços extras
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove stopwords
    words = [w for w in text.split() if w not in STOPWORDS_PT and len(w) > 2]
    return ' '.join(words)


def extract_topics_lda(texts, n_topics=10, n_words=8):
    """
    Extrai tópicos usando LDA (Latent Dirichlet Allocation).
    Retorna lista de tópicos com suas palavras-chave e pesos.
    """
    if not texts or len(texts) < 10:
        return [], None, None

    # Pré-processa
    processed = [preprocess_text(t) for t in texts]
    processed = [t for t in processed if len(t) > 10]

    if len(processed) < 10:
        return [], None, None

    # Vetorização com CountVectorizer (melhor para LDA)
    vectorizer = CountVectorizer(
        max_features=2000,
        min_df=3,
        max_df=0.85,
        ngram_range=(1, 2),
    )

    try:
        doc_term_matrix = vectorizer.fit_transform(processed)
    except ValueError:
        return [], None, None

    # LDA
    n_topics = min(n_topics, len(processed) // 5)
    n_topics = max(2, n_topics)

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
        learning_method='online',
        n_jobs=-1,
    )

    doc_topics = lda.fit_transform(doc_term_matrix)
    feature_names = vectorizer.get_feature_names_out()

    # Extrai tópicos
    topics = []
    for idx, topic in enumerate(lda.components_):
        top_indices = topic.argsort()[-n_words:][::-1]
        top_words = [(feature_names[i], float(topic[i])) for i in top_indices]
        topics.append({
            "id": idx,
            "words": top_words,
            "label": ", ".join([w[0] for w in top_words[:3]]),
        })

    return topics, doc_topics, lda


def compute_tfidf_similarity(texts_a, texts_b, labels_a="A", labels_b="B"):
    """
    Calcula similaridade TF-IDF entre dois conjuntos de textos.
    Útil para comparar temáticas entre instituições.
    """
    if not texts_a or not texts_b:
        return 0.0, None

    # Combina e processa
    processed_a = [preprocess_text(t) for t in texts_a if t]
    processed_b = [preprocess_text(t) for t in texts_b if t]
    processed_a = [t for t in processed_a if len(t) > 10]
    processed_b = [t for t in processed_b if len(t) > 10]

    if not processed_a or not processed_b:
        return 0.0, None

    # Cria documento agregado por grupo
    doc_a = ' '.join(processed_a)
    doc_b = ' '.join(processed_b)

    vectorizer = TfidfVectorizer(
        max_features=1000,
        ngram_range=(1, 2),
        min_df=1,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform([doc_a, doc_b])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(sim), vectorizer
    except ValueError:
        return 0.0, None


def get_institution_profile(keywords_list):
    """
    Cria perfil temático de uma instituição a partir de suas palavras-chave.
    Retorna TF-IDF das palavras-chave mais relevantes.
    """
    if not keywords_list:
        return pd.DataFrame()

    # Processa keywords
    all_kw = []
    for kws in keywords_list:
        if not kws:
            continue
        for kw in str(kws).split(";"):
            kw = kw.strip().lower()
            if kw and len(kw) > 2 and kw not in STOPWORDS_PT:
                all_kw.append(kw)

    if not all_kw:
        return pd.DataFrame()

    # Conta frequências
    kw_counts = pd.Series(all_kw).value_counts()
    total = kw_counts.sum()

    # Calcula TF (frequência relativa)
    profile = pd.DataFrame({
        "tema": kw_counts.index,
        "frequencia": kw_counts.values,
        "tf": kw_counts.values / total,
    })

    return profile.head(50)


def compare_institutions(df_tccs, sigla_a, sigla_b):
    """
    Compara duas instituições por similaridade temática.
    Retorna: similaridade, temas em comum, temas exclusivos.
    """
    kw_a = df_tccs[df_tccs["sigla"] == sigla_a]["palavras_chaves"].dropna().tolist()
    kw_b = df_tccs[df_tccs["sigla"] == sigla_b]["palavras_chaves"].dropna().tolist()

    profile_a = get_institution_profile(kw_a)
    profile_b = get_institution_profile(kw_b)

    if profile_a.empty or profile_b.empty:
        return {"similaridade": 0, "comuns": [], "exclusivos_a": [], "exclusivos_b": []}

    # Temas em comum
    temas_a = set(profile_a["tema"].tolist())
    temas_b = set(profile_b["tema"].tolist())
    comuns = temas_a & temas_b
    exclusivos_a = temas_a - temas_b
    exclusivos_b = temas_b - temas_a

    # Similaridade via cosseno dos perfis TF
    all_temas = sorted(temas_a | temas_b)
    vec_a = np.array([profile_a[profile_a["tema"] == t]["tf"].values[0] if t in temas_a else 0 for t in all_temas])
    vec_b = np.array([profile_b[profile_b["tema"] == t]["tf"].values[0] if t in temas_b else 0 for t in all_temas])

    # Cosseno
    dot = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    sim = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0

    return {
        "similaridade": float(sim),
        "comuns": sorted(comuns)[:20],
        "exclusivos_a": sorted(exclusivos_a)[:15],
        "exclusivos_b": sorted(exclusivos_b)[:15],
        "profile_a": profile_a,
        "profile_b": profile_b,
    }


def compare_researchers(df_pub, slug_a, slug_b):
    """Compara dois pesquisadores por produção."""
    pub_a = df_pub[df_pub["slug_professor"] == slug_a]
    pub_b = df_pub[df_pub["slug_professor"] == slug_b]

    # Títulos como texto
    texts_a = pub_a["titulo"].dropna().tolist()
    texts_b = pub_b["titulo"].dropna().tolist()

    sim, _ = compute_tfidf_similarity(texts_a, texts_b)

    # Tipos em comum
    tipos_a = set(pub_a["tipo"].dropna().unique())
    tipos_b = set(pub_b["tipo"].dropna().unique())

    return {
        "similaridade": sim,
        "pub_a": len(pub_a),
        "pub_b": len(pub_b),
        "tipos_comuns": sorted(tipos_a & tipos_b),
        "tipos_exclusivos_a": sorted(tipos_a - tipos_b),
        "tipos_exclusivos_b": sorted(tipos_b - tipos_a),
    }


def cluster_themes(keywords_series, n_clusters=8):
    """
    Agrupa temáticas usando TF-IDF + Agglomerative Clustering.
    Retorna DataFrame com tema e cluster atribuído.
    """
    # Extrai todas as keywords
    all_kw = []
    for kws in keywords_series.dropna():
        for kw in str(kws).split(";"):
            kw = kw.strip().lower()
            if kw and len(kw) > 2 and kw not in STOPWORDS_PT:
                all_kw.append(kw)

    if len(all_kw) < 20:
        return pd.DataFrame()

    # Top keywords
    kw_counts = pd.Series(all_kw).value_counts()
    top_kw = kw_counts.head(100).index.tolist()

    if len(top_kw) < 10:
        return pd.DataFrame()

    # TF-IDF dos temas (cada tema como "documento")
    vectorizer = TfidfVectorizer(ngram_range=(1, 1), max_features=500)
    try:
        tfidf = vectorizer.fit_transform(top_kw)
    except ValueError:
        return pd.DataFrame()

    # Clustering hierárquico
    n_clusters = min(n_clusters, len(top_kw) // 3)
    n_clusters = max(2, n_clusters)

    clustering = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric='cosine',
        linkage='average',
    )
    labels = clustering.fit_predict(tfidf.toarray())

    result = pd.DataFrame({
        "tema": top_kw,
        "frequencia": [kw_counts[kw] for kw in top_kw],
        "grupo": labels,
    })

    # Nomeia grupos pelo tema mais frequente
    group_names = {}
    for g in result["grupo"].unique():
        group_themes = result[result["grupo"] == g].sort_values("frequencia", ascending=False)
        group_names[g] = group_themes.iloc[0]["tema"]
    result["grupo_nome"] = result["grupo"].map(group_names)

    return result.sort_values(["grupo", "frequencia"], ascending=[True, False])
