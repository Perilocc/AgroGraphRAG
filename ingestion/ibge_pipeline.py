import csv
from pathlib import Path

from graph.connection import get_driver, get_session
from graph.ontology import canonicalize_entity, normalize_text
from graph.repositories import get_pb_municipios_map
from retrieval.embeddings import generate_embeddings

TARGET_BLOCKS = {
    "Variável - Área plantada ou destinada à colheita (Hectares)": "area_plantada_ha",
    "Variável - Quantidade produzida (Toneladas)": "quantidade_ton",
}


def _parse_ibge_number(value: str) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned in {"-", "..", "...", "X", "x"}:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_ibge_csv(file_path: Path, expected_uf: str = "PB") -> dict:
    """
    Parser dedicado para o CSV da Tabela 5457 do IBGE (PAM).
    Extrai exclusivamente os blocos de Área Plantada e Quantidade Produzida
    para os municípios da UF alvo.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo IBGE não encontrado: {file_path}")

    uf_suffix = f" ({expected_uf.upper()})"
    records_by_key: dict[tuple[str, str, int], dict] = {}
    municipios_encontrados: dict[str, str] = {}

    current_metric: str | None = None
    col_specs: list[tuple[int, int, str]] = []
    years_row: list[str] | None = None
    blocks_parsed: set[str] = set()

    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")

        for row in reader:
            if not row:
                continue

            first_cell = row[0].strip()

            if first_cell in TARGET_BLOCKS:
                current_metric = TARGET_BLOCKS[first_cell]
                col_specs = []
                years_row = None
                blocks_parsed.add(current_metric)
                continue

            if current_metric is None:
                continue

            if first_cell.startswith("Fonte:") or first_cell.startswith("Variável -"):
                current_metric = None
                col_specs = []
                years_row = None
                if len(blocks_parsed) == len(TARGET_BLOCKS):
                    break
                continue

            if first_cell == "Nível" and len(row) > 2:
                col2 = row[2].strip()
                if col2.isdigit() and len(col2) == 4:
                    years_row = row
                elif years_row is not None:
                    current_year = None
                    for idx in range(2, len(row)):
                        if idx < len(years_row) and years_row[idx].strip().isdigit():
                            current_year = int(years_row[idx].strip())
                        product_raw = row[idx].strip()
                        if current_year and product_raw:
                            col_specs.append((idx, current_year, product_raw))
                continue

            if first_cell == "MU" and col_specs and len(row) > 2:
                mun_raw = row[1].strip()
                if not mun_raw.endswith(uf_suffix):
                    continue

                mun_name = mun_raw[: -len(uf_suffix)].strip()
                mun_norm = normalize_text(mun_name)
                municipios_encontrados[mun_norm] = mun_name

                for idx, year, product_raw in col_specs:
                    if idx >= len(row):
                        continue
                    val = _parse_ibge_number(row[idx])
                    if val is None or val <= 0:
                        continue

                    canonical = canonicalize_entity(product_raw, "CulturaAgricola")
                    if not canonical:
                        continue
                    cultura_id, cultura_nome, _ = canonical

                    key = (mun_norm, cultura_id, year)
                    entry = records_by_key.setdefault(
                        key,
                        {
                            "municipio_norm": mun_norm,
                            "municipio_nome": mun_name,
                            "cultura_id": cultura_id,
                            "cultura_nome": cultura_nome,
                            "ano": year,
                            "area_plantada_ha": None,
                            "quantidade_ton": None,
                        },
                    )
                    entry[current_metric] = val

    # Seleciona o ano mais recente com produção/área positiva para cada (município, cultura)
    latest_by_pair: dict[tuple[str, str], dict] = {}
    for entry in records_by_key.values():
        pair_key = (entry["municipio_norm"], entry["cultura_id"])
        existing = latest_by_pair.get(pair_key)
        if existing is None or entry["ano"] > existing["ano"]:
            latest_by_pair[pair_key] = entry

    return {
        "municipios_encontrados": municipios_encontrados,
        "registros": list(latest_by_pair.values()),
    }


def ingest_ibge(
    file_path: Path,
    expected_uf: str = "PB",
    generate_culture_embeddings: bool = True,
) -> dict:
    """
    Integra dados municipais de produção agrícola (IBGE PAM) aos municípios
    existentes no Neo4j, criando nós CulturaAgricola e relações PRODUZ.
    """
    parsed = parse_ibge_csv(file_path, expected_uf=expected_uf)
    municipios_ibge = parsed["municipios_encontrados"]
    registros = parsed["registros"]

    pb_map = get_pb_municipios_map(force_refresh=True)

    matched_rows = []
    matched_muns: set[str] = set()
    unmatched_muns: set[str] = set()
    cultures_by_id: dict[str, dict] = {}

    for reg in registros:
        mun_norm = reg["municipio_norm"]
        mun_id = pb_map.get(mun_norm)
        if not mun_id:
            unmatched_muns.add(reg["municipio_nome"])
            continue

        matched_muns.add(reg["municipio_nome"])
        matched_rows.append({
            **reg,
            "municipio_id": mun_id,
        })
        cultures_by_id.setdefault(
            reg["cultura_id"],
            {
                "id": reg["cultura_id"],
                "nome": reg["cultura_nome"],
                "tipo": "CulturaAgricola",
                "descricao": f"Cultura agrícola ({reg['cultura_nome']}) monitorada pelo IBGE PAM.",
            },
        )

    for mun_norm, mun_name in municipios_ibge.items():
        if mun_norm not in pb_map:
            unmatched_muns.add(mun_name)

    culture_list = list(cultures_by_id.values())
    if culture_list and generate_culture_embeddings:
        vectors = generate_embeddings(
            [f"{c['tipo']}: {c['nome']}" for c in culture_list]
        )
        for culture, vector in zip(culture_list, vectors):
            culture["embedding"] = vector

    culture_query = """
    UNWIND $cultures AS item
    MERGE (c:Entidade {id: item.id})
    SET c:CulturaAgricola
    SET
        c.nome = item.nome,
        c.tipo = item.tipo,
        c.descricao = coalesce(c.descricao, item.descricao)
    FOREACH (_ IN CASE WHEN item.embedding IS NOT NULL THEN [1] ELSE [] END |
        SET c.embedding = item.embedding
    )
    RETURN count(c) AS total
    """

    produz_query = """
    UNWIND $rows AS row
    MATCH (m:Entidade:Municipio {id: row.municipio_id})
    MATCH (c:Entidade:CulturaAgricola {id: row.cultura_id})
    MERGE (m)-[r:PRODUZ {ano: row.ano}]->(c)
    SET
        r.area_plantada_ha = row.area_plantada_ha,
        r.quantidade_ton = row.quantidade_ton,
        r.fonte = 'IBGE_PAM'
    RETURN count(r) AS total
    """

    saved_cultures = 0
    saved_relations = 0

    driver = get_driver()
    with get_session(driver) as session:
        if culture_list:
            res_c = session.run(culture_query, cultures=culture_list).single()
            saved_cultures = res_c["total"] if res_c else 0

        if matched_rows:
            res_r = session.run(produz_query, rows=matched_rows).single()
            saved_relations = res_r["total"] if res_r else 0

    return {
        "arquivo": Path(file_path).name,
        "uf": expected_uf,
        "sncr_vazio": len(pb_map) == 0,
        "municipios_ibge": len(municipios_ibge),
        "municipios_casados": len(matched_muns),
        "municipios_sem_match": sorted(unmatched_muns),
        "culturas_integradas": saved_cultures,
        "relacoes_produz_criadas": saved_relations,
    }
