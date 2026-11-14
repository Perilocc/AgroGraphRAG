from pathlib import Path
import streamlit as st

from graph.connection import test_connection
from graph.schema import create_schema
from ingestion.pipeline import ingest_pdf
from ingestion.sncr_pipeline import ingest_sncr
from ui import apply_global_styles, render_kpi_row, render_page_header
from utils.file_utils import discover_files, get_source_info

apply_global_styles()

if "neo4j_status" not in st.session_state:
    st.session_state.neo4j_status = None

badge_text = None
badge_color = "gray"
if st.session_state.neo4j_status is True:
    badge_text = "Neo4j Online"
    badge_color = "green"
elif st.session_state.neo4j_status is False:
    badge_text = "Neo4j Offline"
    badge_color = "red"

render_page_header(
    title="Ingestão & Schema",
    subtitle="Inicialização de constraints/índices no Neo4j e disparo dos pipelines Embrapa e SNCR.",
    icon=":material/sync:",
    badge_text=badge_text,
    badge_color=badge_color,
)

# Descobrir arquivos disponíveis em data/
files = discover_files()
embrapa_pdfs: list[Path] = []
sncr_csvs: list[Path] = []
other_structured: list[tuple[str, Path]] = []

for file_path in files:
    _, institution = get_source_info(file_path)
    inst = institution.upper()
    suffix = file_path.suffix.lower()
    if inst == "EMBRAPA" and suffix == ".pdf":
        embrapa_pdfs.append(file_path)
    elif inst == "SNCR" and suffix == ".csv":
        sncr_csvs.append(file_path)
    else:
        other_structured.append((inst, file_path))

render_kpi_row(
    [
        {"label": "PDFs Embrapa", "value": len(embrapa_pdfs), "help": "Documentos técnicos para NER/RE e embeddings"},
        {"label": "CSVs SNCR", "value": len(sncr_csvs), "help": "Bases cadastrais de imóveis rurais"},
        {"label": "Outras Fontes (IBGE/CONAB)", "value": len(other_structured), "help": "Séries produtivas catalogadas"},
    ]
)

# Seção 1: Infraestrutura & Schema Neo4j
with st.container(border=True):
    st.subheader(":material/schema: Infraestrutura & Schema Neo4j")
    st.caption(
        "Valide a conectividade com o banco de grafos e garanta a criação das constraints "
        "e índices (`entidade_busca` e `trecho_embedding`) antes da ingestão."
    )

    col_conn, col_schema, _ = st.columns([1.2, 1.4, 2.4])
    with col_conn:
        if st.button("Testar Conexão", icon=":material/cable:", width="stretch"):
            try:
                ok = test_connection()
                st.session_state.neo4j_status = bool(ok)
                if ok:
                    st.success("Conexão com Neo4j validada com sucesso.", icon=":material/check_circle:")
                else:
                    st.error("Não foi possível validar a conexão com o Neo4j.", icon=":material/error:")
            except Exception as exc:
                st.session_state.neo4j_status = False
                st.error(f"Erro ao conectar ao Neo4j: {exc}", icon=":material/error:")

    with col_schema:
        if st.button("Inicializar Schema", type="primary", icon=":material/build:", width="stretch"):
            with st.status("Criando constraints e índices no Neo4j...", expanded=True) as status:
                try:
                    create_schema()
                    st.session_state.neo4j_status = True
                    status.update(label="Schema inicializado com sucesso.", state="complete")
                except Exception as exc:
                    status.update(label="Falha ao criar schema.", state="error")
                    st.error(f"Erro ao executar create_schema(): {exc}", icon=":material/error:")

st.divider()

# Seção 2: Pipelines de Ingestão
col_left, col_right = st.columns(2, gap="large")

with col_left:
    with st.container(border=True):
        st.subheader(":material/article: Embrapa (PDFs • NER/RE)")
        st.caption("Leitura, chunking, geração de embeddings, extração de entidades/relações e gravação.")

        if not embrapa_pdfs:
            st.info("Nenhum PDF da Embrapa encontrado em data/.", icon=":material/info:")
        else:
            pdf_options = {p.name: p for p in embrapa_pdfs}
            selected_pdfs = st.multiselect(
                "Selecione os PDFs para ingestão",
                options=list(pdf_options.keys()),
                default=list(pdf_options.keys())[:1],
            )

            if st.button(
                "Executar Ingestão de PDFs",
                type="primary",
                icon=":material/play_arrow:",
                disabled=not selected_pdfs,
                width="stretch",
            ):
                results = []
                with st.status(f"Processando {len(selected_pdfs)} PDF(s)...", expanded=True) as status:
                    try:
                        for name in selected_pdfs:
                            st.write(f"Ingerindo `{name}`...")
                            res = ingest_pdf(pdf_options[name])
                            results.append({"arquivo": name, **res})
                        status.update(label="Ingestão de PDFs concluída.", state="complete")
                    except Exception as exc:
                        status.update(label="Erro durante a ingestão de PDFs.", state="error")
                        st.error(f"Falha: {exc}", icon=":material/error:")

                if results:
                    st.dataframe(results, width="stretch", hide_index=True)

with col_right:
    with st.container(border=True):
        st.subheader(":material/agriculture: SNCR (CSV • Imóveis Rurais)")
        st.caption("Carga em lotes de imóveis rurais, municípios, detentores e registros de detenção.")

        if not sncr_csvs:
            st.info("Nenhum CSV do SNCR encontrado em data/.", icon=":material/info:")
        else:
            csv_options = {p.name: p for p in sncr_csvs}
            selected_csv_name = st.selectbox(
                "Arquivo SNCR",
                options=list(csv_options.keys()),
            )

            c_uf, c_chunk, c_batch = st.columns(3)
            with c_uf:
                expected_uf = st.text_input("UF esperada", value="PB", max_chars=2)
            with c_chunk:
                chunksize = st.number_input("Chunksize", min_value=500, max_value=50000, value=5000, step=500)
            with c_batch:
                batch_size = st.number_input("Batch size", min_value=100, max_value=10000, value=1000, step=100)

            limit_records = st.checkbox("Limitar quantidade de registros (modo teste)", value=False)
            max_records = None
            if limit_records:
                max_records = int(
                    st.number_input("Máximo de registros", min_value=10, max_value=100000, value=500, step=100)
                )

            if st.button(
                "Executar Ingestão SNCR",
                type="primary",
                icon=":material/play_arrow:",
                width="stretch",
            ):
                with st.status(f"Ingerindo `{selected_csv_name}`...", expanded=True) as status:
                    try:
                        summary = ingest_sncr(
                            csv_options[selected_csv_name],
                            chunksize=int(chunksize),
                            batch_size=int(batch_size),
                            expected_uf=expected_uf.strip().upper() or "PB",
                            max_records=max_records,
                        )
                        status.update(label="Ingestão SNCR concluída.", state="complete")
                        st.json(summary)
                    except Exception as exc:
                        status.update(label="Erro durante a ingestão SNCR.", state="error")
                        st.error(f"Falha: {exc}", icon=":material/error:")
