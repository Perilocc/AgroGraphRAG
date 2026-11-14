import pandas as pd
import streamlit as st

from graph.connection import test_connection
from graph.repositories import (
    clean_knowledge_subgraph,
    ensure_municipio_normalized_names,
)
from graph.schema import create_schema
from ingestion.ibge_pipeline import ingest_ibge
from ingestion.pipeline import ingest_pdf
from ingestion.sncr_pipeline import ingest_sncr
from ui import apply_global_styles, render_kpi_row, render_page_header
from utils.file_utils import discover_files, get_source_info
from utils.paths import STRUCTURED_DIR, UNSTRUCTURED_DIR

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
    title="Ingestão & Modelagem LPG",
    subtitle=(
        "Fluxo guiado para limpar dados legados, aplicar constraints/índices no Neo4j "
        "e ingerir SNCR, IBGE e manuais da Embrapa na ordem correta."
    ),
    icon=":material/sync:",
    badge_text=badge_text,
    badge_color=badge_color,
)

# KPIs rápidos dos arquivos disponíveis em data/
files = discover_files()
embrapa_count = sum(
    1 for f in files if get_source_info(f)[1].upper() == "EMBRAPA" and f.suffix.lower() == ".pdf"
)
sncr_count = sum(
    1 for f in files if get_source_info(f)[1].upper() == "SNCR" and f.suffix.lower() == ".csv"
)
other_count = len(files) - embrapa_count - sncr_count

render_kpi_row(
    [
        {"label": "PDFs Embrapa", "value": embrapa_count, "help": "Documentos técnicos para NER/RE e embeddings"},
        {"label": "CSVs SNCR", "value": sncr_count, "help": "Bases cadastrais de imóveis rurais"},
        {"label": "Outras Fontes (IBGE/CONAB)", "value": other_count, "help": "Séries produtivas catalogadas"},
    ]
)

# Passo 0 & Passo 1: Infraestrutura Neo4j
col_a, col_b, col_c = st.columns(3)

with col_a:
    with st.container(border=True):
        st.subheader(":material/cable: Conexão Neo4j")
        st.caption("Valide a conectividade com o banco antes de iniciar o pipeline.")
        if st.button("Testar Conexão Aura", icon=":material/cable:", width="stretch"):
            try:
                if test_connection():
                    st.session_state.neo4j_status = True
                    st.success("Conexão com Neo4j estabelecida com sucesso!", icon=":material/check_circle:")
            except Exception as exc:
                st.session_state.neo4j_status = False
                st.error(f"Falha na conexão: {exc}", icon=":material/error:")

with col_b:
    with st.container(border=True):
        st.subheader(":material/cleaning_services: Passo 0: Limpeza Segura")
        st.caption(
            "Remove trechos, relações :RELACIONA antigas e entidades de PDFs, "
            "preservando integralmente o subgrafo SNCR."
        )
        if st.button("Limpar Subgrafo de Conhecimento", icon=":material/delete_sweep:", width="stretch"):
            with st.spinner("Executando limpeza em transações no Neo4j..."):
                try:
                    stats = clean_knowledge_subgraph()
                    st.success("Subgrafo de conhecimento limpo com sucesso!")
                    st.json(stats)
                except Exception as exc:
                    st.error(f"Erro na limpeza: {exc}")

with col_c:
    with st.container(border=True):
        st.subheader(":material/schema: Passo 1: Schema LPG")
        st.caption("Cria constraints (id, codigo_ibge) e índices (B-Tree, Fulltext e Vector).")
        if st.button("Criar/Atualizar Schema", type="primary", icon=":material/build:", width="stretch"):
            with st.spinner("Aplicando constraints e índices no Neo4j..."):
                try:
                    create_schema()
                    updated = ensure_municipio_normalized_names()
                    st.session_state.neo4j_status = True
                    st.success(f"Schema aplicado! Municípios existentes normalizados: {updated}")
                except Exception as exc:
                    st.error(f"Erro ao criar schema: {exc}")

st.divider()

tab_sncr, tab_ibge, tab_pdf = st.tabs([
    ":material/agriculture: Passo 2: SNCR (Imóveis Rurais)",
    ":material/bar_chart: Passo 3: Ponte IBGE (PAM)",
    ":material/article: Passo 4: PDFs Embrapa (Text-to-Graph)",
])

with tab_sncr:
    with st.container(border=True):
        st.subheader("Ingestão Estruturada — SNCR / INCRA (Paraíba)")
        st.warning(
            "**Nota de Capacidade (Neo4j Aura Free — teto de 200.000 nós):** "
            "O arquivo completo da PB possui ~237 mil registros (>700 mil nós). "
            "Utilize **amostragem uniforme (`sample_step = 6`)** com limite máximo de "
            "**40.000 registros** (~120 mil nós), preservando cobertura proporcional "
            "de todos os municípios da Paraíba.",
            icon=":material/warning:",
        )

        sncr_dir = STRUCTURED_DIR / "sncr"
        sncr_files = sorted(sncr_dir.glob("*.csv")) if sncr_dir.exists() else []

        if not sncr_files:
            st.info("Nenhum arquivo SNCR encontrado em data/structured/sncr/.")
        else:
            selected_sncr = st.selectbox(
                "Arquivo SNCR",
                options=sncr_files,
                format_func=lambda p: p.name,
            )
            c1, c2, c3 = st.columns(3)
            sample_step = c1.number_input("Amostragem uniforme (1 a cada N linhas)", min_value=1, max_value=20, value=6)
            max_records = c2.number_input("Limite máximo de registros", min_value=10, max_value=45000, value=40000, step=500)
            chunk_size = c3.number_input("Tamanho do bloco CSV", min_value=100, max_value=10000, value=5000, step=500)

            if st.button("Executar Ingestão SNCR", type="primary", icon=":material/play_arrow:"):
                with st.spinner(f"Ingerindo {selected_sncr.name}..."):
                    try:
                        res = ingest_sncr(
                            file_path=selected_sncr,
                            chunksize=int(chunk_size),
                            batch_size=1000,
                            expected_uf="PB",
                            max_records=int(max_records),
                            sample_step=int(sample_step),
                        )
                        st.success("Ingestão SNCR concluída!")
                        st.json(res)
                    except Exception as exc:
                        st.error(f"Erro na ingestão SNCR: {exc}")

with tab_ibge:
    with st.container(border=True):
        st.subheader("Ingestão Ponte Agrícola — IBGE Produção Agrícola Municipal")
        st.info(
            "Extrai os blocos de **Área Plantada (ha)** e **Quantidade Produzida (t)** "
            "para a Paraíba e conecta os municípios já carregados do SNCR às culturas "
            "(`:CulturaAgricola`) via relações `:PRODUZ`.",
            icon=":material/info:",
        )

        ibge_file = STRUCTURED_DIR / "ibge" / "producao_agricola.csv"
        if not ibge_file.exists():
            st.warning("Arquivo data/structured/ibge/producao_agricola.csv não encontrado.")
        else:
            if st.button("Integrar Produção Agrícola IBGE (PB)", type="primary", icon=":material/play_arrow:"):
                with st.spinner("Processando CSV IBGE e conectando municípios no Neo4j..."):
                    try:
                        res = ingest_ibge(ibge_file, expected_uf="PB")
                        if res.get("sncr_vazio"):
                            st.warning(
                                "Nenhum nó :Municipio (PB) encontrado no banco! "
                                "Execute a ingestão SNCR (Passo 2) antes do IBGE."
                            )
                        else:
                            st.success("Ponte IBGE integrada com sucesso!")

                        render_kpi_row(
                            [
                                {"label": "Municípios IBGE (PB)", "value": res["municipios_ibge"]},
                                {"label": "Municípios Casados (SNCR)", "value": res["municipios_casados"]},
                                {"label": "Culturas Integradas", "value": res["culturas_integradas"]},
                                {"label": "Relações :PRODUZ", "value": res["relacoes_produz_criadas"]},
                            ]
                        )

                        if res["municipios_sem_match"]:
                            with st.expander(
                                f"Municípios sem correspondência no SNCR ({len(res['municipios_sem_match'])})"
                            ):
                                st.write(res["municipios_sem_match"])
                    except Exception as exc:
                        st.error(f"Erro na ingestão IBGE: {exc}")

with tab_pdf:
    with st.container(border=True):
        st.subheader("Pipeline Text-to-Graph — Manuais Técnicos Embrapa (PDF)")
        st.info(
            "Extrai trechos, gera embeddings, aplica NER/RE restrito à ontologia LPG "
            "e executa **Entity Resolution em 2 camadas** (dicionário de sinônimos + "
            "similaridade de cosseno + confirmação LLM).",
            icon=":material/info:",
        )

        embrapa_dir = UNSTRUCTURED_DIR / "embrapa"
        pdf_files = sorted(embrapa_dir.glob("*.pdf")) if embrapa_dir.exists() else []

        if not pdf_files:
            st.warning("Nenhum PDF encontrado em data/unstructured/embrapa/.")
        else:
            selected_pdfs = st.multiselect(
                "Selecione os PDFs para ingestão",
                options=pdf_files,
                default=pdf_files,
                format_func=lambda p: p.name,
            )

            if st.button(
                "Executar Ingestão Text-to-Graph",
                type="primary",
                icon=":material/play_arrow:",
                disabled=not selected_pdfs,
            ):
                progress = st.progress(0)
                status_box = st.empty()
                results = []

                for idx, pdf_path in enumerate(selected_pdfs):
                    with st.spinner(f"Processando {pdf_path.name} ({idx + 1}/{len(selected_pdfs)})..."):
                        try:
                            res = ingest_pdf(
                                pdf_path,
                                progress_callback=lambda msg, i=idx: status_box.caption(
                                    f"[{i + 1}/{len(selected_pdfs)}] {msg}"
                                ),
                            )
                            results.append(res)
                        except Exception as exc:
                            st.error(f"Erro ao processar {pdf_path.name}: {exc}")
                    progress.progress((idx + 1) / len(selected_pdfs))
                status_box.empty()

                if results:
                    st.success(f"Processamento concluído para {len(results)} documento(s)!")
                    summary_rows = [
                        {
                            "Documento": r["document"],
                            "Chunks": r["chunks"],
                            "Entidades": r["entities"],
                            "Relações": r["relations"],
                            "Fusões Semânticas": len(r.get("merged_entities", [])),
                            "Municípios Descartados (fora PB)": len(r.get("unresolved_municipalities", [])),
                        }
                        for r in results
                    ]
                    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

                    all_merges = [
                        {"documento": r["document"], **m}
                        for r in results
                        for m in r.get("merged_entities", [])
                    ]
                    if all_merges:
                        with st.expander(f"Ver Fusões de Entity Resolution ({len(all_merges)})"):
                            st.dataframe(pd.DataFrame(all_merges), width="stretch", hide_index=True)
