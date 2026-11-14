import pandas as pd
import streamlit as st
from ui import apply_global_styles, render_kpi_row, render_page_header
from utils.file_utils import discover_files, get_source_info
from utils.paths import DATA_DIR

apply_global_styles()

render_page_header(
    title="Fontes de Dados",
    subtitle="Catálogo dos documentos estruturados e não estruturados utilizados pelo projeto.",
    icon=":material/dataset:",
)

files = discover_files()

if not files:
    st.info("Nenhum arquivo encontrado na pasta data/.", icon=":material/info:")
    st.stop()

catalog = []
for file in files:
    category, institution = get_source_info(file)
    catalog.append(
        {
            "Categoria": category,
            "Instituição": institution.upper(),
            "Arquivo": file.name,
            "Formato": file.suffix.upper().lstrip("."),
            "Tamanho (KB)": round(file.stat().st_size / 1024, 2),
            "Caminho": str(file.relative_to(DATA_DIR)),
        }
    )

df = pd.DataFrame(catalog)
total_mb = round(df["Tamanho (KB)"].sum() / 1024, 2)

render_kpi_row(
    [
        {"label": "Total de Arquivos", "value": len(df)},
        {"label": "Instituições", "value": df["Instituição"].nunique()},
        {"label": "Formatos", "value": df["Formato"].nunique()},
        {"label": "Volume Total", "value": f"{total_mb} MB"},
    ]
)

with st.container(border=True):
    st.subheader("Arquivos Cadastrados")
    col_f1, col_f2, col_f3 = st.columns([1.4, 1.2, 1.4])

    institutions = sorted(df["Instituição"].unique())
    formats = sorted(df["Formato"].unique())

    with col_f1:
        selected_institutions = st.pills(
            "Instituição",
            options=institutions,
            selection_mode="multi",
        )
    with col_f2:
        selected_formats = st.pills(
            "Formato",
            options=formats,
            selection_mode="multi",
        )
    with col_f3:
        search_query = st.text_input(
            "Buscar arquivo",
            placeholder="Ex.: soja, Imoveis, milho...",
        )

filtered_df = df.copy()
if selected_institutions:
    filtered_df = filtered_df[filtered_df["Instituição"].isin(selected_institutions)]
if selected_formats:
    filtered_df = filtered_df[filtered_df["Formato"].isin(selected_formats)]
if search_query:
    filtered_df = filtered_df[
        filtered_df["Arquivo"].str.contains(search_query, case=False, na=False)
    ]

st.dataframe(
    filtered_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Tamanho (KB)": st.column_config.NumberColumn(
            "Tamanho (KB)",
            format="%.2f KB",
        ),
        "Formato": st.column_config.TextColumn("Formato", width="small"),
        "Instituição": st.column_config.TextColumn("Instituição", width="small"),
    },
)

st.caption(f"{len(filtered_df)} arquivo(s) exibido(s) de {len(df)} catalogado(s).")
