# 🎓 ETL Integra IFB - Dashboard de Pesquisadores

Sistema ETL (Extract, Transform, Load) que extrai dados de professores e publicações do [Portal Integra IFB](https://integra.ifb.edu.br), aplica algoritmos de clusterização e classificação por área do CNPq, e apresenta os resultados em um dashboard interativo feito com Streamlit.

---

## 📁 Estrutura do Projeto

```
projeto/
├── config.py                # Configurações gerais (URLs, paths, áreas CNPq)
├── dashboard.py             # Dashboard Streamlit (visualização)
├── requirements.txt         # Dependências Python
├── README.md                # Este arquivo
├── etl/
│   ├── __init__.py
│   ├── extractor.py         # Extração via web scraping
│   ├── transformer.py       # Transformação e limpeza dos dados
│   ├── clustering.py        # Clusterização (K-Means) e Classificação (Random Forest)
│   └── pipeline.py          # Orquestrador do pipeline ETL completo
└── data/
    ├── raw/                 # Dados brutos (JSON)
    │   ├── professores_raw.json
    │   └── publicacoes_raw.json
    └── processed/           # Dados processados (CSV)
        ├── professores.csv
        ├── publicacoes.csv
        └── professores_clusters.csv
```

---

## 🛠️ Instalação

### Pré-requisitos

- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)

### Passo a passo

1. **Clone ou copie o projeto** para um diretório local.

2. **Crie um ambiente virtual** (recomendado):

```bash
python -m venv venv
```

3. **Ative o ambiente virtual**:

- Windows (CMD):
```cmd
venv\Scripts\activate
```

- Windows (PowerShell):
```powershell
.\venv\Scripts\Activate.ps1
```

- Linux/Mac:
```bash
source venv/bin/activate
```

4. **Instale as dependências**:

```bash
pip install -r requirements.txt
```

---

## 📦 Dependências

| Pacote | Versão | Descrição |
|--------|--------|-----------|
| requests | 2.31.0 | Requisições HTTP para web scraping |
| beautifulsoup4 | 4.12.3 | Parser HTML para extração de dados |
| pandas | 2.2.2 | Manipulação e análise de dados |
| numpy | 1.26.4 | Computação numérica |
| scikit-learn | 1.5.0 | Algoritmos de ML (K-Means, Random Forest, TF-IDF) |
| streamlit | 1.35.0 | Framework para dashboard interativo |
| plotly | 5.22.0 | Gráficos interativos |
| lxml | 5.2.2 | Parser XML/HTML de alta performance |
| tqdm | 4.66.4 | Barras de progresso |

---

## 🚀 Como Executar

### Etapa 1: Executar o Pipeline ETL

O pipeline extrai dados do portal, transforma e aplica os algoritmos de ML:

```bash
python etl/pipeline.py
```

> ⚠️ **Nota**: A extração faz web scraping do portal Integra IFB. O processo pode levar alguns minutos dependendo da quantidade de dados e da velocidade da conexão. Um delay de 1.5s entre requisições é aplicado para não sobrecarregar o servidor.

Você também pode executar cada etapa separadamente:

```bash
# Apenas extração
python etl/extractor.py

# Apenas transformação (requer dados brutos já extraídos)
python etl/transformer.py

# Apenas clusterização (requer dados transformados)
python etl/clustering.py
```

### Etapa 2: Iniciar o Dashboard

Após a execução do pipeline:

```bash
streamlit run dashboard.py
```

O dashboard será aberto automaticamente no navegador (geralmente em `http://localhost:8501`).

---

## 📊 Funcionalidades do Dashboard

### Filtros Disponíveis (Barra Lateral)

- **Área CNPq**: Filtra por grande área do conhecimento
- **Campus**: Filtra por campus do IFB
- **Tipo de Servidor**: Docente, Técnico Administrativo
- **Cluster (K-Means)**: Grupos identificados pelo algoritmo
- **Mínimo de Publicações**: Slider para filtrar por produtividade
- **Busca por Nome**: Campo de texto para busca

### Abas do Dashboard

1. **Classificação por Área**: Distribuição por área CNPq, campus, produção média e heatmap
2. **Clusters**: Visualização PCA 2D dos clusters por área
3. **Publicações**: Análise temporal, por tipo e por campus
4. **Ranking**: Ranking dos pesquisadores pelo Índice de Produtividade Acadêmica (IPA)
5. **Dados Detalhados**: Tabela completa com opção de download CSV
6. **Sobre**: Informações sobre o projeto, algoritmos e métricas

---

## 🧠 Algoritmos Utilizados

### Clusterização - K-Means
- Agrupa professores por similaridade textual (temas, resumo)
- Usa TF-IDF para vetorização do texto
- PCA para redução dimensional e visualização 2D
- Silhouette Score para avaliação da qualidade dos clusters

### Classificação - Random Forest
- Classifica professores nas grandes áreas do CNPq
- Treinado com features TF-IDF extraídas do currículo
- Validação cruzada (cross-validation) para avaliação
- Índice de confiança para cada classificação

### Classificação por Regras
- Classificação inicial baseada em keywords das áreas CNPq
- Usa temas (palavras-chave) e resumo do currículo
- Serve como baseline e dados de treino para o modelo ML

### Métrica de Ranking - IPA (Índice de Produtividade Acadêmica)

```
IPA = (Pub × 0.40) + (Div × 0.20) + (Rec × 0.20) + (Conf × 0.20)
```

| Componente | Peso | Descrição |
|---|---|---|
| Publicações (Pub) | 40% | Total de publicações registradas (normalizado 0-100) |
| Diversidade (Div) | 20% | Quantidade de tipos distintos de produção (normalizado 0-100) |
| Recência (Rec) | 20% | Ano da publicação mais recente (normalizado 0-100) |
| Confiança ML (Conf) | 20% | Confiança do modelo Random Forest na classificação (0-100) |

---

## 🔧 Configuração

O arquivo `config.py` permite ajustar:

- URLs e endpoints do portal
- Diretórios de saída
- Parâmetros de scraping (timeout, delay, retries)
- Keywords das áreas CNPq para classificação

---

## ⚠️ Observações

- O portal Integra IFB possui uma API interna consumida pelo frontend Vue.js.
- Endpoints utilizados: `/api/portfolio//pessoa/data`, `/api/portfolio//producao/data`, `/api/portfolio//palavraschave/{id}`
- Respeite os limites do servidor: o delay entre requisições está configurado em 0.5 segundos.
- Os dados extraídos são públicos e disponíveis no portal.
- A qualidade da classificação depende da quantidade e qualidade das informações nos currículos.
- Acurácia do modelo de classificação: ~75% (validação cruzada 4-fold).

---

## 📄 Licença

Projeto acadêmico/educacional. Dados públicos do Portal Integra IFB.
