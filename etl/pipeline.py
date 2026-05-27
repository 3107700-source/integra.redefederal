"""
Pipeline ETL completo - Orquestra extração, transformação e clusterização.
Suporta toda a rede federal ou instituições individuais.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.extractor import IntegraExtractor
from etl.transformer import IntegraTransformer
from etl.clustering import ClusteringClassifier
from etl.database import DatabaseManager


def run_pipeline(siglas=None, skip_extraction=False):
    """
    Executa o pipeline ETL completo.

    Args:
        siglas: Lista de siglas de instituições. None = apenas IFB.
        skip_extraction: Se True, pula a extração e usa dados já existentes no banco.
    """
    print("=" * 70)
    print("   PIPELINE ETL - PORTAL INTEGRA - REDE FEDERAL")
    print("   Extração, Transformação, Clusterização e Ranking")
    print("=" * 70)

    db = DatabaseManager()

    if not skip_extraction:
        # Etapa 1: Extração
        print("\n" + "─" * 70)
        print("  ETAPA 1/3: EXTRAÇÃO (API Integra)")
        print("─" * 70)
        extractor = IntegraExtractor(db)
        extractor.run(siglas)

    # Etapa 2: Transformação e Ranking
    print("\n" + "─" * 70)
    print("  ETAPA 2/3: TRANSFORMAÇÃO E RANKING")
    print("─" * 70)
    transformer = IntegraTransformer()
    # Se uma única sigla, transforma apenas ela; senão, transforma tudo
    target_sigla = siglas[0] if siglas and len(siglas) == 1 else None
    transformer.run(target_sigla)

    # Etapa 3: Clusterização e Classificação ML
    print("\n" + "─" * 70)
    print("  ETAPA 3/3: CLUSTERIZAÇÃO E CLASSIFICAÇÃO (ML)")
    print("─" * 70)
    classifier = ClusteringClassifier()
    classifier.run()

    print("\n" + "=" * 70)
    print("   ✅ PIPELINE CONCLUÍDO COM SUCESSO!")
    print("   Dados prontos para visualização no dashboard.")
    print("   Execute: streamlit run dashboard.py")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline ETL - Rede Federal")
    parser.add_argument("--sigla", type=str, default=None,
                        help="Sigla da instituição (ex: IFB). Padrão: apenas IFB.")
    parser.add_argument("--todas", action="store_true",
                        help="Processa TODAS as instituições da rede federal.")
    parser.add_argument("--skip-extraction", action="store_true",
                        help="Pula a extração e usa dados já existentes no banco.")
    args = parser.parse_args()

    if args.todas:
        run_pipeline(siglas=None, skip_extraction=args.skip_extraction)
    elif args.sigla:
        run_pipeline(siglas=[args.sigla.upper()], skip_extraction=args.skip_extraction)
    else:
        run_pipeline(siglas=["IFB"], skip_extraction=args.skip_extraction)
