from pathlib import Path
from ingestion.sncr import iter_sncr
from ingestion.sncr_transformer import transform_sncr
from graph.repositories import save_sncr_graph


def ingest_sncr(
    file_path: Path,
    chunksize: int = 5000,
    batch_size: int = 1000,
    expected_uf: str = "PB",
    max_records: int | None = None,
    sample_step: int = 1,
) -> dict:
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Arquivo SNCR não encontrado: {file_path}"
        )

    if max_records is not None and max_records <= 0:
        raise ValueError("max_records deve ser maior que zero.")

    if sample_step <= 0:
        raise ValueError("sample_step deve ser maior que zero.")

    total_records = 0
    total_entities = 0
    total_relationships = 0
    total_chunks = 0

    for df in iter_sncr(file_path, chunksize=chunksize):
        if sample_step > 1:
            df = df[df.index % sample_step == 0]

        if df.empty:
            continue

        if max_records is not None:
            remaining = max_records - total_records

            if remaining <= 0:
                break

            df = df.head(remaining)

        if df["uf"].isna().any() or not df["uf"].eq(expected_uf).all():
            raise ValueError(
                f"O arquivo contém registros fora da UF esperada: {expected_uf}"
            )

        graph_data = transform_sncr(
            df,
            source_name=file_path.name,
            start_index=total_records,
        )

        result = save_sncr_graph(
            graph_data,
            batch_size=batch_size,
        )

        total_records += len(df)
        total_entities += result["entities"]
        total_relationships += result["relationships"]
        total_chunks += 1

        print(
            f"Bloco {total_chunks} concluído | "
            f"Registros: {total_records}"
        )

    return {
        "arquivo": file_path.name,
        "registros_lidos": total_records,
        "sample_step": sample_step,
        "blocos_processados": total_chunks,
        "entidades_processadas": total_entities,
        "relacionamentos_processados": total_relationships,
    }
