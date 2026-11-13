from pyvis.network import Network

TYPE_COLORS = {
    "CulturaAgricola": "#2ecc71",
    "Praga": "#e74c3c",
    "PraticaAgricola": "#3498db",
    "ProdutoAgricola": "#9b59b6",
    "CondicaoAmbiental": "#f39c12",
    "Municipio": "#1abc9c",
    "ImovelRural": "#95a5a6",
    "Detentor": "#e67e22",
    "RegistroDetencao": "#7f8c8d",
    "Documento": "#34495e",
    "Bioma": "#16a085",
    "Regiao": "#2980b9",
    "Estado": "#27ae60",
    "Instituicao": "#f1c40f",
    "Pessoa": "#d35400",
}

COMMUNITY_PALETTE = [
    "#2ecc71",
    "#3498db",
    "#e74c3c",
    "#9b59b6",
    "#f39c12",
    "#1abc9c",
    "#e67e22",
    "#f1c40f",
    "#00bcd4",
    "#ff7043",
]


def render_interactive_graph(
    nodes: list[dict],
    edges: list[dict],
    height: int = 520,
    community_map: dict[str, int] | None = None,
) -> str:
    """
    Gera HTML interativo com PyVis para renderização do subgrafo no Streamlit.
    Tamanho dos nós proporcional ao PageRank (quando disponível).
    """
    net = Network(
        height=f"{height}px",
        width="100%",
        bgcolor="#0e1117",
        font_color="#f8f9fa",
        directed=True,
    )

    net.barnes_hut(
        gravity=-3200,
        central_gravity=0.3,
        spring_length=140,
        spring_strength=0.05,
        damping=0.09,
    )

    added_nodes = set()
    max_pr = max((float(n.get("pagerank", 0.0)) for n in nodes), default=0.0) or 1.0

    for node in nodes:
        nid = str(node.get("id", ""))
        if not nid or nid in added_nodes:
            continue
        added_nodes.add(nid)

        label = str(node.get("nome") or node.get("name") or nid[:10])
        ntype = str(node.get("tipo") or node.get("type") or "Entidade")
        desc = str(node.get("descricao") or "")
        pr = float(node.get("pagerank", 0.0))

        if community_map and nid in community_map:
            comm_idx = community_map[nid]
            color = COMMUNITY_PALETTE[(comm_idx - 1) % len(COMMUNITY_PALETTE)]
            comm_info = f"<br>Comunidade: #{comm_idx}"
        else:
            color = TYPE_COLORS.get(ntype, "#7f8c8d")
            comm_info = ""

        size = 18 + int((pr / max_pr) * 22) if pr > 0 else 20
        title = f"<b>{label}</b><br>Tipo: {ntype}<br>PageRank: {pr:.4f}{comm_info}"
        if desc:
            title += f"<br>{desc[:180]}"

        net.add_node(
            nid,
            label=label[:28] + ("…" if len(label) > 28 else ""),
            title=title,
            color=color,
            size=size,
        )

    for edge in edges:
        src = str(edge.get("source_id", ""))
        tgt = str(edge.get("target_id", ""))
        rel_type = str(edge.get("tipo") or edge.get("type") or "RELACIONA")

        if src not in added_nodes or tgt not in added_nodes:
            continue

        tooltip = rel_type
        if rel_type == "PRODUZ" and edge.get("ano"):
            tooltip = (
                f"PRODUZ ({edge.get('ano')}): "
                f"Área={edge.get('area_plantada_ha')} ha | "
                f"Prod={edge.get('quantidade_ton')} t"
            )

        net.add_edge(
            src,
            tgt,
            label=rel_type,
            title=tooltip,
            color="#94a3b8",
            font={"size": 10, "color": "#cbd5e1", "strokeWidth": 0},
        )

    return net.generate_html()
