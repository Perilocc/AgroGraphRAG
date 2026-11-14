import json
import pandas as pd
import plotly.express as px
import streamlit as st
from pyvis.network import Network

from graph.queries import (
    get_imoveis_com_detentores,
    get_imoveis_por_area,
    get_imoveis_por_municipio,
    get_subgraph,
)
from ui import (
    ENTITY_COLORS,
    apply_global_styles,
    get_pyvis_network_config,
    render_entity_legend,
    render_kpi_row,
    render_page_header,
)

apply_global_styles()

render_page_header(
    title="Explorador de Grafo",
    subtitle="Visualização interativa do Labeled Property Graph e consultas analíticas sobre SNCR e entidades.",
    icon=":material/hub:",
)


def _build_pyvis_html(subgraph: dict) -> str:
    """Constrói o HTML interativo do PyVis com toolbar (zoom/reset/filtro) e painel de detalhes."""
    net = Network(height="580px", width="100%", bgcolor="#FFFFFF", font_color="#18221B", directed=True)
    net.set_options(get_pyvis_network_config())

    node_details: dict[str, dict] = {}
    for node in subgraph.get("nodes", []):
        nid = str(node["id"])
        group = node.get("group", "Entidade")
        palette = ENTITY_COLORS.get(group, ENTITY_COLORS["Entidade"])
        props = node.get("properties", {})
        node_label = str(node.get("label", ""))

        # Tooltip em texto puro (evita vazamento de tags HTML no vis-network)
        lines = [f"[{group}] {node_label}"]
        for k, v in list(props.items())[:5]:
            lines.append(f"{k}: {str(v)[:100]}")
        tooltip = "\n".join(lines)

        net.add_node(
            nid,
            label=node_label[:28],
            title=tooltip,
            color={"background": palette["fill"], "border": palette["border"]},
        )
        node_details[nid] = {
            "id": nid,
            "label": node_label,
            "group": group,
            "color": palette["fill"],
            "properties": {str(k): str(v) for k, v in props.items()},
        }

    for edge in subgraph.get("edges", []):
        net.add_edge(edge["source"], edge["target"], label=edge.get("type", ""))

    raw_html = net.generate_html()

    # Injeta toolbar (Zoom +/-, Reset, Filtro) e painel lateral de detalhes ao clicar no nó
    details_json = json.dumps(node_details, ensure_ascii=False)
    ux_overlay = f"""
    <style>
      #agro-toolbar {{
        position: absolute; top: 12px; left: 12px; z-index: 20;
        display: flex; align-items: center; gap: 6px;
        background: rgba(255,255,255,0.95); border: 1px solid #DCE3D5;
        border-radius: 8px; padding: 6px 8px; box-shadow: 0 2px 8px rgba(24,34,27,0.08);
        font-family: Inter, sans-serif;
      }}
      #agro-toolbar button {{
        border: 1px solid #DCE3D5; background: #F6F7F3; color: #18221B;
        border-radius: 6px; padding: 4px 9px; font-size: 13px; font-weight: 600;
        cursor: pointer;
      }}
      #agro-toolbar button:hover {{ background: #EDF1E8; border-color: #1F6E43; color: #1F6E43; }}
      #agro-search {{
        border: 1px solid #DCE3D5; border-radius: 6px; padding: 4px 8px;
        font-size: 12px; width: 165px; outline: none; color: #18221B;
      }}
      #agro-search:focus {{ border-color: #1F6E43; }}
      #agro-detail-panel {{
        position: absolute; top: 12px; right: 12px; z-index: 20;
        width: 270px; max-height: 540px; overflow-y: auto;
        background: rgba(255,255,255,0.97); border: 1px solid #DCE3D5;
        border-radius: 8px; padding: 12px 14px; box-shadow: 0 4px 14px rgba(24,34,27,0.1);
        font-family: Inter, sans-serif; font-size: 12.5px; color: #18221B;
        display: none;
      }}
      #agro-detail-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
      #agro-detail-badge {{
        display: inline-block; padding: 2px 8px; border-radius: 999px;
        color: #FFFFFF; font-size: 11px; font-weight: 600;
      }}
      #agro-detail-close {{
        border: none; background: transparent; cursor: pointer; font-size: 16px; color: #6E7C72;
      }}
      #agro-detail-title {{ font-size: 14px; font-weight: 700; margin: 4px 0 10px 0; word-break: break-word; }}
      .agro-prop-row {{ border-top: 1px solid #EDF1E8; padding: 5px 0; }}
      .agro-prop-key {{ font-size: 11px; color: #6E7C72; font-weight: 600; }}
      .agro-prop-val {{ font-size: 12px; color: #18221B; word-break: break-word; }}
    </style>
    <div id="agro-toolbar">
      <button id="btn-zoom-in" title="Aproximar">+</button>
      <button id="btn-zoom-out" title="Afastar">−</button>
      <button id="btn-reset" title="Resetar visualização">Resetar</button>
      <input id="agro-search" type="text" placeholder="Filtrar nó no grafo..." />
    </div>
    <div id="agro-detail-panel">
      <div id="agro-detail-header">
        <span id="agro-detail-badge"></span>
        <button id="agro-detail-close" title="Fechar">&times;</button>
      </div>
      <div id="agro-detail-title"></div>
      <div id="agro-detail-props"></div>
    </div>
    <script>
      (function() {{
        const details = {details_json};
        const panel = document.getElementById("agro-detail-panel");
        const badgeEl = document.getElementById("agro-detail-badge");
        const titleEl = document.getElementById("agro-detail-title");
        const propsEl = document.getElementById("agro-detail-props");

        document.getElementById("agro-detail-close").onclick = () => {{ panel.style.display = "none"; }};
        document.getElementById("btn-zoom-in").onclick = () => {{
          if (typeof network !== "undefined") network.moveTo({{ scale: network.getScale() * 1.25, animation: true }});
        }};
        document.getElementById("btn-zoom-out").onclick = () => {{
          if (typeof network !== "undefined") network.moveTo({{ scale: network.getScale() * 0.8, animation: true }});
        }};
        document.getElementById("btn-reset").onclick = () => {{
          document.getElementById("agro-search").value = "";
          if (typeof nodes !== "undefined") {{
            nodes.forEach((n) => nodes.update({{ id: n.id, hidden: false }}));
          }}
          if (typeof network !== "undefined") network.fit({{ animation: true }});
        }};
        document.getElementById("agro-search").addEventListener("input", function(e) {{
          const q = e.target.value.trim().toLowerCase();
          if (typeof nodes === "undefined") return;
          nodes.forEach((n) => {{
            const match = !q || (n.label && n.label.toLowerCase().includes(q));
            nodes.update({{ id: n.id, hidden: !match }});
          }});
        }});

        if (typeof network !== "undefined") {{
          network.on("click", function(params) {{
            if (params.nodes && params.nodes.length > 0) {{
              const info = details[params.nodes[0]];
              if (!info) return;
              badgeEl.textContent = info.group;
              badgeEl.style.backgroundColor = info.color;
              titleEl.textContent = info.label;
              propsEl.innerHTML = Object.entries(info.properties)
                .map(([k, v]) => `<div class="agro-prop-row"><div class="agro-prop-key">${{k}}</div><div class="agro-prop-val">${{v}}</div></div>`)
                .join("") || "<div class='agro-prop-val'>Sem propriedades adicionais.</div>";
              panel.style.display = "block";
            }} else {{
              panel.style.display = "none";
            }}
          }});
        }}
      }})();
    </script>
    """
    return raw_html.replace("</body>", f"{ux_overlay}</body>")


tab_graph, tab_analytics = st.tabs(
    [
        ":material/hub: Visualização Interativa",
        ":material/bar_chart: Consultas Analíticas SNCR",
    ]
)

with tab_graph:
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.4, 1.4, 1, 1], vertical_alignment="bottom")
        with c1:
            label_filter = st.selectbox(
                "Filtrar por Label",
                options=["Todos"] + list(ENTITY_COLORS.keys()),
            )
        with c2:
            municipio_code = st.text_input(
                "Código IBGE do Município (opcional)",
                placeholder="Ex.: 2507507",
            )
        with c3:
            node_limit = st.number_input(
                "Limite de nós",
                min_value=10,
                max_value=200,
                value=60,
                step=10,
            )
        with c4:
            load_clicked = st.button(
                "Carregar Grafo",
                type="primary",
                icon=":material/refresh:",
                width="stretch",
            )

    if "explorer_subgraph" not in st.session_state or load_clicked:
        try:
            st.session_state.explorer_subgraph = get_subgraph(
                label=label_filter,
                codigo_municipio=municipio_code.strip() or None,
                limit=int(node_limit),
            )
            st.session_state.explorer_error = None
        except Exception as exc:
            st.session_state.explorer_subgraph = {"nodes": [], "edges": []}
            st.session_state.explorer_error = str(exc)

    if st.session_state.get("explorer_error"):
        st.error(
            f"Não foi possível consultar o Neo4j: {st.session_state.explorer_error}",
            icon=":material/error:",
        )
    else:
        subgraph = st.session_state.explorer_subgraph
        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])
        present_groups = sorted({n.get("group", "Entidade") for n in nodes})

        render_kpi_row(
            [
                {"label": "Nós Exibidos", "value": len(nodes)},
                {"label": "Arestas Exibidas", "value": len(edges)},
                {"label": "Labels Distintos", "value": len(present_groups)},
            ]
        )

        if present_groups:
            render_entity_legend(present_groups)

        if not nodes:
            st.info("Nenhum nó encontrado para os filtros selecionados.", icon=":material/info:")
        else:
            col_canvas, col_details = st.columns([2.3, 1], gap="medium")
            with col_canvas:
                graph_html = _build_pyvis_html(subgraph)
                st.iframe(graph_html, height=580)
            with col_details:
                with st.container(border=True):
                    st.subheader("Distribuição por Label")
                    dist_df = (
                        pd.DataFrame([{"Label": n.get("group", "Entidade")} for n in nodes])
                        .value_counts()
                        .reset_index(name="Quantidade")
                    )
                    st.dataframe(dist_df, width="stretch", hide_index=True)

with tab_analytics:
    st.subheader("Municípios com Maior Quantidade de Imóveis")
    col_m1, col_m2 = st.columns([1, 3], vertical_alignment="bottom")
    with col_m1:
        mun_limit = st.number_input("Top municípios", min_value=5, max_value=50, value=10, step=5)
    with col_m2:
        run_mun = st.button("Consultar Municípios", icon=":material/play_arrow:")

    if run_mun:
        try:
            mun_data = get_imoveis_por_municipio(limit=int(mun_limit))
            if not mun_data:
                st.info("Nenhum dado retornado.", icon=":material/info:")
            else:
                df_mun = pd.DataFrame(mun_data)
                fig = px.bar(
                    df_mun,
                    x="municipio",
                    y="total_imoveis",
                    color_discrete_sequence=["#1F6E43"],
                    labels={"municipio": "Município", "total_imoveis": "Total de Imóveis"},
                )
                fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=320)
                st.plotly_chart(fig, width="stretch")
                st.dataframe(df_mun, width="stretch", hide_index=True)
        except Exception as exc:
            st.error(f"Erro ao consultar municípios: {exc}", icon=":material/error:")

    st.divider()

    col_a, col_d = st.columns(2, gap="large")
    with col_a:
        st.subheader("Imóveis por Área Mínima")
        min_area = st.number_input("Área mínima (ha)", min_value=0.0, value=100.0, step=50.0)
        if st.button("Filtrar por Área", icon=":material/filter_alt:"):
            try:
                area_data = get_imoveis_por_area(min_area=float(min_area), limit=20)
                st.dataframe(pd.DataFrame(area_data), width="stretch", hide_index=True)
            except Exception as exc:
                st.error(f"Erro: {exc}", icon=":material/error:")

    with col_d:
        st.subheader("Imóveis e Detentores (2 Saltos)")
        cod_mun = st.text_input("Código IBGE", value="2507507")
        if st.button("Consultar Detentores", icon=":material/badge:"):
            try:
                det_data = get_imoveis_com_detentores(codigo_municipio=cod_mun.strip(), limit=20)
                st.dataframe(pd.DataFrame(det_data), width="stretch", hide_index=True)
            except Exception as exc:
                st.error(f"Erro: {exc}", icon=":material/error:")
