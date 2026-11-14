from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np

from graph.repositories import (
    find_similar_existing_entities,
    find_similar_existing_entities_batch,
    get_pb_municipios_map,
    save_chunks,
    save_knowledge,
)

_DEFAULT_FIND_SIMILAR = find_similar_existing_entities
from ingestion.chunking import chunk_pages
from ingestion.entity_extractor import (
    confirm_entity_equivalence_llm,
    extract_knowledge,
)
from ingestion.readers import read_document
from retrieval.embeddings import generate_embeddings

AUTO_MERGE_THRESHOLD = 0.90
LLM_CONFIRM_MIN_THRESHOLD = 0.75


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _resolve_root(redirect_map: dict[str, str], node_id: str) -> str:
    visited = set()
    curr = node_id
    while curr in redirect_map and curr not in visited:
        visited.add(curr)
        curr = redirect_map[curr]
    return curr


def resolve_semantic_duplicates(
    entities: list[dict],
    relations: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Camada 2 de Entity Resolution:
    1. Gera embeddings em lote para 'tipo: nome' das entidades únicas não-Municipio.
    2. Compara por similaridade de cosseno dentro do lote e contra o índice Neo4j.
    3. Funde automaticamente >= 0.90 e confirma 0.75..0.90 via LLM.
    """
    if not entities:
        return [], relations, []

    non_mun_unique: dict[str, dict] = {}
    for entity in entities:
        if entity["tipo"] == "Municipio":
            continue
        if entity["id"] not in non_mun_unique:
            non_mun_unique[entity["id"]] = dict(entity)

    unique_list = list(non_mun_unique.values())
    if unique_list:
        embed_inputs = [f"{e['tipo']}: {e['nome']}" for e in unique_list]
        vectors = generate_embeddings(embed_inputs)
        for entity, vector in zip(unique_list, vectors):
            entity["embedding"] = vector
            non_mun_unique[entity["id"]]["embedding"] = vector

    redirect_map: dict[str, str] = {}
    merged_records: list[dict] = []
    candidate_llm_pairs: list[dict] = []
    seen_pair_keys: set[tuple[str, str]] = set()

    # 1. Comparação contra entidades já existentes no Neo4j
    if find_similar_existing_entities is _DEFAULT_FIND_SIMILAR:
        matches_by_id = find_similar_existing_entities_batch(
            unique_list,
            top_k=3,
            min_score=LLM_CONFIRM_MIN_THRESHOLD,
        )
    else:
        matches_by_id = {
            entity["id"]: find_similar_existing_entities(
                entity_type=entity["tipo"],
                embedding=entity["embedding"],
                top_k=3,
                min_score=LLM_CONFIRM_MIN_THRESHOLD,
            )
            for entity in unique_list
        }

    for entity in unique_list:
        matches = matches_by_id.get(entity["id"], [])
        for match in matches:
            target_id = match.get("id")
            score = float(match.get("score", 0.0))
            if not target_id or target_id == entity["id"]:
                continue

            pair_key = (entity["id"], target_id)
            if pair_key in seen_pair_keys:
                continue
            seen_pair_keys.add(pair_key)

            if score >= AUTO_MERGE_THRESHOLD:
                redirect_map[entity["id"]] = target_id
                merged_records.append({
                    "origem": entity["nome"],
                    "destino": match["nome"],
                    "tipo": entity["tipo"],
                    "score": round(score, 4),
                    "metodo": "cosseno_neo4j",
                })
                break
            else:
                candidate_llm_pairs.append({
                    "source_id": entity["id"],
                    "target_id": target_id,
                    "name_a": entity["nome"],
                    "name_b": match["nome"],
                    "tipo": entity["tipo"],
                    "score": round(score, 4),
                    "metodo": "cosseno_llm_neo4j",
                })

    # 2. Comparação intra-documento por tipo
    by_type: dict[str, list[dict]] = {}
    for entity in unique_list:
        by_type.setdefault(entity["tipo"], []).append(entity)

    for entity_type, group in by_type.items():
        for i in range(len(group)):
            e_a = group[i]
            if e_a["id"] in redirect_map:
                continue
            for j in range(i + 1, len(group)):
                e_b = group[j]
                if e_b["id"] in redirect_map:
                    continue

                score = _cosine_similarity(e_a["embedding"], e_b["embedding"])
                if score < LLM_CONFIRM_MIN_THRESHOLD:
                    continue

                # Mantém como canônico o nome mais conciso/primeiro extraído
                if len(e_b["nome"]) < len(e_a["nome"]):
                    src, tgt = e_a, e_b
                else:
                    src, tgt = e_b, e_a

                pair_key = (src["id"], tgt["id"])
                if pair_key in seen_pair_keys:
                    continue
                seen_pair_keys.add(pair_key)

                if score >= AUTO_MERGE_THRESHOLD:
                    redirect_map[src["id"]] = tgt["id"]
                    merged_records.append({
                        "origem": src["nome"],
                        "destino": tgt["nome"],
                        "tipo": entity_type,
                        "score": round(score, 4),
                        "metodo": "cosseno_lote",
                    })
                else:
                    candidate_llm_pairs.append({
                        "source_id": src["id"],
                        "target_id": tgt["id"],
                        "name_a": src["nome"],
                        "name_b": tgt["nome"],
                        "tipo": entity_type,
                        "score": round(score, 4),
                        "metodo": "cosseno_llm_lote",
                    })

    # 3. Confirmação por LLM para faixa intermediária (0.75..0.90)
    if candidate_llm_pairs:
        confirmed = confirm_entity_equivalence_llm(candidate_llm_pairs)
        confirmed_set = set(confirmed)
        for pair in candidate_llm_pairs:
            if (pair["source_id"], pair["target_id"]) in confirmed_set:
                if pair["source_id"] not in redirect_map:
                    redirect_map[pair["source_id"]] = pair["target_id"]
                    merged_records.append({
                        "origem": pair["name_a"],
                        "destino": pair["name_b"],
                        "tipo": pair["tipo"],
                        "score": pair["score"],
                        "metodo": pair["metodo"],
                    })

    # 4. Aplica redirecionamentos em entidades e relações
    resolved_entities = []
    seen_entity_chunk = set()

    for entity in entities:
        final_id = _resolve_root(redirect_map, entity["id"])
        key = (final_id, entity["trecho_id"])
        if key in seen_entity_chunk:
            continue
        seen_entity_chunk.add(key)

        canonical_ref = non_mun_unique.get(final_id)
        updated = dict(entity)
        updated["id"] = final_id
        if canonical_ref:
            updated["nome"] = canonical_ref["nome"]
            updated["embedding"] = canonical_ref.get("embedding")
        elif entity["id"] in non_mun_unique:
            updated["embedding"] = non_mun_unique[entity["id"]].get("embedding")

        resolved_entities.append(updated)

    resolved_relations = []
    seen_relations = set()

    for rel in relations:
        src_id = _resolve_root(redirect_map, rel["source_id"])
        tgt_id = _resolve_root(redirect_map, rel["target_id"])
        if src_id == tgt_id:
            continue

        rel_key = (src_id, rel["tipo"], tgt_id, rel["trecho_id"])
        if rel_key in seen_relations:
            continue
        seen_relations.add(rel_key)

        resolved_relations.append({
            **rel,
            "source_id": src_id,
            "target_id": tgt_id,
        })

    return resolved_entities, resolved_relations, merged_records


def ingest_pdf(
    file_path: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> dict:
    """Executa a ingestão completa de um PDF com resolução de entidades em 2 camadas."""
    def _notify(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    file_path = Path(file_path)
    print(f"Processando: {file_path.name}")
    _notify(f"Lendo e segmentando {file_path.name}...")

    document = read_document(file_path)

    if document["type"] != "pdf":
        raise ValueError("Este pipeline aceita apenas PDFs.")

    chunks = chunk_pages(
        pages=document["content"],
        source=str(file_path.name),
    )

    if not chunks:
        return {
            "document": file_path.name,
            "chunks": 0,
            "saved": 0,
            "entities": 0,
            "relations": 0,
            "merged_entities": [],
            "unresolved_municipalities": [],
        }

    _notify(f"Gerando embeddings para {len(chunks)} trechos de {file_path.name}...")
    vectors = generate_embeddings([chunk["text"] for chunk in chunks])

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    _notify(f"Salvando {len(chunks)} trechos no Neo4j...")
    saved = save_chunks(chunks)

    try:
        pb_municipios_map = get_pb_municipios_map()
    except Exception:
        pb_municipios_map = {}

    raw_entities = []
    raw_relations = []
    unresolved_municipalities = []

    if len(chunks) == 1:
        _notify(f"Extraindo entidades (1/1 trecho) de {file_path.name}...")
        chunk_results = [
            extract_knowledge(
                chunks[0]["text"],
                chunks[0]["id"],
                pb_municipios_map=pb_municipios_map,
            )
        ]
    else:
        chunk_results = [None] * len(chunks)
        max_workers = min(4, len(chunks))
        _notify(f"Extraindo entidades (0/{len(chunks)} trechos) de {file_path.name}...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(
                    extract_knowledge,
                    chunk["text"],
                    chunk["id"],
                    pb_municipios_map=pb_municipios_map,
                ): idx
                for idx, chunk in enumerate(chunks)
            }
            completed = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                chunk_results[idx] = future.result()
                completed += 1
                _notify(
                    f"Extraindo entidades ({completed}/{len(chunks)} trechos) de {file_path.name}..."
                )

    for knowledge in chunk_results:
        raw_entities.extend(knowledge.get("entities", []))
        raw_relations.extend(knowledge.get("relations", []))
        unresolved_municipalities.extend(
            knowledge.get("unresolved_municipalities", [])
        )

    _notify(
        f"Resolvendo duplicidades semânticas ({len(raw_entities)} entidades) de {file_path.name}..."
    )
    resolved_entities, resolved_relations, merged_entities = (
        resolve_semantic_duplicates(raw_entities, raw_relations)
    )

    if resolved_entities or resolved_relations:
        _notify(
            f"Salvando {len(resolved_entities)} entidades e {len(resolved_relations)} relações no Neo4j..."
        )
        save_knowledge({
            "entities": resolved_entities,
            "relations": resolved_relations,
        })

    return {
        "document": file_path.name,
        "chunks": len(chunks),
        "saved": saved,
        "entities": len(resolved_entities),
        "relations": len(resolved_relations),
        "merged_entities": merged_entities,
        "unresolved_municipalities": sorted(set(unresolved_municipalities)),
    }
