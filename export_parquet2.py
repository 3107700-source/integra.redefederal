"""Export all tables to parquet with better compression. Split large files."""
import sqlite3
import pandas as pd
import os

DB_PATH = "data/integra.db"
PARQUET_DIR = "data/parquet"
os.makedirs(PARQUET_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

# Tables with expected sizes
tables = {
    "professores": "SELECT * FROM professores",
    "publicacoes": "SELECT * FROM publicacoes",
    "tccs": "SELECT * FROM tccs",
    "projetos": "SELECT * FROM projetos",
    "curriculo_detalhes": "SELECT * FROM curriculo_detalhes",
    "formacao_academica": "SELECT * FROM formacao_academica",
    "bancas": "SELECT * FROM bancas",
}

# Try gestao_comissoes
try:
    pd.read_sql_query("SELECT COUNT(*) FROM gestao_comissoes", conn)
    tables["gestao_comissoes"] = "SELECT * FROM gestao_comissoes"
except:
    pass

for table, query in tables.items():
    print(f"Exportando {table}...")
    try:
        df = pd.read_sql_query(query, conn)
        if df.empty:
            print(f"  VAZIO - pulando")
            continue
        
        # For large tables, drop heavy text columns to reduce size
        output = f"{PARQUET_DIR}/{table}.parquet"
        
        # Projetos: remove 'descricao' and 'equipe' to reduce size
        if table == "projetos" and "descricao" in df.columns:
            df_export = df.drop(columns=["descricao", "equipe", "financiadores"], errors="ignore")
        # Curriculo_detalhes: remove detalhes_json
        elif table == "curriculo_detalhes" and "detalhes_json" in df.columns:
            df_export = df.drop(columns=["detalhes_json"], errors="ignore")
        else:
            df_export = df
        
        df_export.to_parquet(output, compression="gzip", index=False)
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"  {len(df):,} registros -> {size_mb:.1f} MB")
        
        # If still > 95MB, split into parts
        if size_mb > 95:
            print(f"  GRANDE DEMAIS ({size_mb:.1f} MB) - dividindo...")
            os.remove(output)
            mid = len(df_export) // 2
            df_export.iloc[:mid].to_parquet(f"{PARQUET_DIR}/{table}_part1.parquet", compression="gzip", index=False)
            df_export.iloc[mid:].to_parquet(f"{PARQUET_DIR}/{table}_part2.parquet", compression="gzip", index=False)
            s1 = os.path.getsize(f"{PARQUET_DIR}/{table}_part1.parquet") / (1024*1024)
            s2 = os.path.getsize(f"{PARQUET_DIR}/{table}_part2.parquet") / (1024*1024)
            print(f"  Part1: {s1:.1f} MB, Part2: {s2:.1f} MB")
            
    except Exception as e:
        print(f"  ERRO: {e}")

conn.close()

# Show total
total = sum(os.path.getsize(f"{PARQUET_DIR}/{f}") for f in os.listdir(PARQUET_DIR) if f.endswith(".parquet"))
print(f"\nTotal: {total/(1024*1024):.1f} MB")
for f in sorted(os.listdir(PARQUET_DIR)):
    if f.endswith(".parquet"):
        s = os.path.getsize(f"{PARQUET_DIR}/{f}") / (1024*1024)
        print(f"  {f}: {s:.1f} MB")
