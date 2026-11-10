from utils.file_utils import discover_files, get_source_info
from utils.paths import DATA_DIR
import streamlit as st
import pandas as pd

st.title("📂 Fontes de Dados")
st.caption("Catálogo dos documentos utilizados pelo projeto.")
st.divider()

files = discover_files()

if not files:
    st.info("Nenhum arquivo encontrado na pasta data/.")
    st.stop()

catalog = []

for file in files:
    category, institution = get_source_info(file)

    catalog.append({
        "Categoria": category,
        "Instituição": institution.upper(),
        "Arquivo": file.name,
        "Formato": file.suffix.upper(),
        "Tamanho (KB)": round(file.stat().st_size / 1024, 2),
        "Caminho": str(file.relative_to(DATA_DIR)),
    })

df = pd.DataFrame(catalog)


# Indicadores
col1, col2, col3 = st.columns(3)

col1.metric("Total de arquivos", len(df))
col2.metric("Instituições", df["Instituição"].nunique())
col3.metric("Formatos", df["Formato"].nunique())
st.divider()


# Filtros
st.subheader("Arquivos cadastrados")

col1, col2 = st.columns(2)

institutions = ["Todas"] + sorted(df["Instituição"].unique())
formats = ["Todos"] + sorted(df["Formato"].unique())

selected_institution = col1.selectbox(
    "Instituição", institutions
)

selected_format = col2.selectbox(
    "Formato", formats
)

filtered_df = df.copy()

if selected_institution != "Todas":
    filtered_df = filtered_df[
        filtered_df["Instituição"] == selected_institution
    ]

if selected_format != "Todos":
    filtered_df = filtered_df[
        filtered_df["Formato"] == selected_format
    ]

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True,
)

st.caption(f"{len(filtered_df)} arquivo(s) encontrado(s).")
