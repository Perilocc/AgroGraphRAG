from pyvis.network import Network

from ui.components import get_pyvis_network_config
from ui.theme import ENTITY_COLORS

TYPE_COLORS = {
    "CulturaAgricola": ENTITY_COLORS["Cultura"]["fill"],
    "Cultura": ENTITY_COLORS["Cultura"]["fill"],
    "Praga": ENTITY_COLORS["Praga"]["fill"],
    "PraticaAgricola": ENTITY_COLORS["PraticaAgricola"]["fill"],
    "ProdutoAgricola": "#7D5BA6",
    "CondicaoAmbiental": "#D48817",
    "Municipio": ENTITY_COLORS["Municipio"]["fill"],
    "ImovelRural": ENTITY_COLORS["ImovelRural"]["fill"],
    "Detentor": ENTITY_COLORS["Detentor"]["fill"],
    "RegistroDetencao": ENTITY_COLORS["RegistroDetencao"]["fill"],
    "Documento": ENTITY_COLORS["Documento"]["fill"],
    "Bioma": "#2F7A78",
    "Regiao": "#1E6B8C",
    "Estado": ENTITY_COLORS["Estado"]["fill"],
    "Instituicao": "#9C610B",
    "Pessoa": "#5B6B5E",
}

COMMUNITY_PALETTE = [
    "#1F6E43",
    "#1E6B8C",
    "#D48817",
    "#7D5BA6",
    "#C0392B",
    "#2F7A78",
    "#2E8B57",
    "#5B6B5E",
    "#475569",
    "#9C610B",
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
        bgcolor="#FFFFFF",
        font_color="#18221B",
        directed=True,
    )

    net.set_options(get_pyvis_network_config())

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
            color = TYPE_COLORS.get(ntype, ENTITY_COLORS["Entidade"]["fill"])
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
            color="#94A3B8",
            font={"size": 10, "color": "#4B594F", "strokeWidth": 0},
        )

    return net.generate_html()
