"""
Módulo de Clusterização e Classificação.
Aplica algoritmos de ML para agrupar professores por perfil de pesquisa.
"""

import os
import sys

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import silhouette_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROFESSORES_PROCESSED, CLUSTERS_OUTPUT, PROCESSED_DIR, AREAS_CNPQ


class ClusteringClassifier:
    """
    Classe que aplica algoritmos de clusterização e classificação
    para agrupar professores por área de pesquisa.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words=self._get_stopwords(),
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
        )
        self.pca = PCA(n_components=2)

    def _get_stopwords(self) -> list[str]:
        """Retorna lista de stopwords em português para TF-IDF."""
        return [
            "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
            "um", "uma", "uns", "umas", "o", "a", "os", "as", "e", "ou",
            "que", "se", "para", "por", "com", "como", "mais", "mas",
            "foi", "ser", "são", "tem", "ter", "sua", "seu", "seus", "suas",
            "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
            "entre", "sobre", "após", "desde", "até", "também", "já",
            "ainda", "quando", "muito", "pela", "pelo", "pelas", "pelos",
            "onde", "qual", "quais", "quanto", "quantos", "toda", "todo",
            "todas", "todos", "cada", "outro", "outra", "outros", "outras",
            "mesmo", "mesma", "mesmos", "mesmas", "assim", "bem", "sem",
            "instituto", "federal", "brasília", "ifb", "campus", "professor",
            "professora", "docente", "curso", "área", "atuação",
        ]

    def _prepare_text_features(self, df: pd.DataFrame):
        """Prepara features textuais usando TF-IDF."""
        # Combina temas e resumo para criar representação textual
        df = df.copy()
        df["text_features"] = (
            df["temas"].fillna("") + " " +
            df["resumo"].fillna("")
        )

        # Remove registros sem texto suficiente
        mask = df["text_features"].str.strip().str.len() > 10
        valid_df = df[mask].copy()

        if len(valid_df) < 5:
            print("  AVISO: Poucos registros com texto suficiente para clusterização.")
            return None, valid_df

        tfidf_matrix = self.vectorizer.fit_transform(valid_df["text_features"])
        return tfidf_matrix, valid_df

    def apply_kmeans(self, df: pd.DataFrame, n_clusters: int = None) -> pd.DataFrame:
        """
        Aplica K-Means para clusterização dos professores.
        Se n_clusters não for informado, usa o número de grandes áreas CNPq.
        """
        print("\n📊 Aplicando K-Means Clustering...")

        result = self._prepare_text_features(df)

        if result[0] is None:
            df["cluster_kmeans"] = -1
            df["pca_x"] = np.nan
            df["pca_y"] = np.nan
            return df

        tfidf_matrix, valid_df = result

        if n_clusters is None:
            n_clusters = min(len(AREAS_CNPQ), len(valid_df) // 5)
            n_clusters = max(2, min(n_clusters, 9))

        # Aplica K-Means
        kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10,
            max_iter=300
        )
        clusters = kmeans.fit_predict(tfidf_matrix)

        # Calcula silhouette score
        if len(set(clusters)) > 1:
            sil_score = silhouette_score(tfidf_matrix, clusters)
            print(f"  Silhouette Score: {sil_score:.3f}")

        # Atribui clusters
        valid_df = valid_df.copy()
        valid_df["cluster_kmeans"] = clusters

        # PCA para visualização 2D
        pca_result = self.pca.fit_transform(tfidf_matrix.toarray())
        valid_df["pca_x"] = pca_result[:, 0]
        valid_df["pca_y"] = pca_result[:, 1]

        # Merge de volta com o DataFrame original
        df = df.drop(columns=["cluster_kmeans", "pca_x", "pca_y"], errors="ignore")
        df = df.merge(
            valid_df[["slug", "cluster_kmeans", "pca_x", "pca_y"]],
            on="slug",
            how="left"
        )
        df["cluster_kmeans"] = df["cluster_kmeans"].fillna(-1).astype(int)

        print(f"  Clusters formados: {n_clusters}")
        print(f"  Distribuição por cluster:")
        cluster_dist = df[df["cluster_kmeans"] >= 0]["cluster_kmeans"].value_counts().sort_index()
        print("  " + cluster_dist.to_string().replace("\n", "\n  "))

        return df

    def apply_classification(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica classificação supervisionada (Random Forest) usando
        a área CNPq como label e features textuais.
        """
        print("\n🎯 Aplicando Classificação (Random Forest)...")

        # Filtra apenas registros com área classificada e texto
        df_work = df.copy()
        df_work["text_features"] = (
            df_work["temas"].fillna("") + " " +
            df_work["resumo"].fillna("")
        )

        classified = df_work[
            (df_work["area_cnpq"] != "Não Classificado") &
            (df_work["text_features"].str.strip().str.len() > 10)
        ].copy()

        if len(classified) < 10:
            print("  AVISO: Poucos registros classificados para treinar modelo.")
            df["area_cnpq_ml"] = df["area_cnpq"]
            df["confianca_classificacao"] = 0.0
            return df

        # Verifica se há classes suficientes
        class_counts = classified["area_cnpq"].value_counts()
        valid_classes = class_counts[class_counts >= 2].index.tolist()

        if len(valid_classes) < 2:
            print("  AVISO: Poucas classes com amostras suficientes.")
            df["area_cnpq_ml"] = df["area_cnpq"]
            df["confianca_classificacao"] = 0.0
            return df

        classified = classified[classified["area_cnpq"].isin(valid_classes)].copy()

        # Vectorização
        vectorizer = TfidfVectorizer(
            max_features=300,
            stop_words=self._get_stopwords(),
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
        )

        X = vectorizer.fit_transform(classified["text_features"])
        le = LabelEncoder()
        y = le.fit_transform(classified["area_cnpq"])

        # Treina Random Forest
        rf = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10,
            min_samples_split=3,
        )

        # Cross-validation
        n_classes = len(set(y))
        cv_folds = min(5, min(class_counts[valid_classes].values))
        cv_folds = max(2, cv_folds)

        if cv_folds >= 2 and len(classified) >= cv_folds * n_classes:
            try:
                scores = cross_val_score(rf, X, y, cv=cv_folds, scoring="accuracy")
                print(f"  Acurácia (cross-val {cv_folds}-fold): {scores.mean():.3f} (+/- {scores.std():.3f})")
            except Exception as e:
                print(f"  Cross-validation falhou: {e}")

        # Treina modelo final com todos os dados
        rf.fit(X, y)

        # Predição para todos os registros com texto
        all_valid = df_work[df_work["text_features"].str.strip().str.len() > 10].copy()

        if len(all_valid) > 0:
            X_all = vectorizer.transform(all_valid["text_features"])
            predictions = rf.predict(X_all)
            probabilities = rf.predict_proba(X_all).max(axis=1)

            all_valid["area_cnpq_ml"] = le.inverse_transform(predictions)
            all_valid["confianca_classificacao"] = probabilities

            df = df.drop(columns=["area_cnpq_ml", "confianca_classificacao"], errors="ignore")
            df = df.merge(
                all_valid[["slug", "area_cnpq_ml", "confianca_classificacao"]],
                on="slug",
                how="left"
            )
        else:
            df["area_cnpq_ml"] = df["area_cnpq"]
            df["confianca_classificacao"] = 0.0

        # Preenche valores faltantes
        df["area_cnpq_ml"] = df["area_cnpq_ml"].fillna(df["area_cnpq"])
        df["confianca_classificacao"] = df["confianca_classificacao"].fillna(0.0)

        print(f"  Classificação ML concluída.")
        print(f"\n  Distribuição por área (ML):")
        print("  " + df["area_cnpq_ml"].value_counts().to_string().replace("\n", "\n  "))

        return df

    def run(self) -> pd.DataFrame:
        """Executa pipeline completo de clusterização e classificação."""
        print("\n🧠 Iniciando Clusterização e Classificação...")

        if not os.path.exists(PROFESSORES_PROCESSED):
            print(f"  ERRO: Arquivo {PROFESSORES_PROCESSED} não encontrado.")
            print("  Execute primeiro o ETL (extractor + transformer).")
            return pd.DataFrame()

        df = pd.read_csv(PROFESSORES_PROCESSED, encoding="utf-8")
        print(f"  Registros carregados: {len(df)}")

        # Aplica K-Means
        df = self.apply_kmeans(df)

        # Aplica Classificação
        df = self.apply_classification(df)

        # Remove coluna auxiliar se existir
        if "text_features" in df.columns:
            df = df.drop(columns=["text_features"])

        # Salva resultado
        df.to_csv(CLUSTERS_OUTPUT, index=False, encoding="utf-8")
        print(f"\n✓ Resultado salvo em {CLUSTERS_OUTPUT}")

        return df


if __name__ == "__main__":
    classifier = ClusteringClassifier()
    classifier.run()
