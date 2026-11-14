from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from evaluation.benchmark import (
    compute_citation_score,
    compute_entity_recall,
    judge_faithfulness,
)
from graph.algorithms import (
    compute_subgraph_pagerank,
    detect_subgraph_communities,
)
from ingestion.ibge_pipeline import parse_ibge_csv
from retrieval import cypher_generator, hybrid_search, kag_engine

IBGE_CSV = Path("data/structured/ibge/producao_agricola.csv")


def test_parse_ibge_csv_pb_blocks():
    parsed = parse_ibge_csv(IBGE_CSV, expected_uf="PB")

    assert len(parsed["municipios_encontrados"]) == 223
    assert len(parsed["registros"]) > 0

    milho_rows = [r for r in parsed["registros"] if r["cultura_nome"] == "Milho"]
    assert len(milho_rows) > 100
    assert any(r["area_plantada_ha"] is not None for r in milho_rows)
    assert any(r["quantidade_ton"] is not None for r in milho_rows)


def test_validate_cypher_safety():
    valid = "MATCH (m:Municipio) RETURN m.asset_name, m.offset_val LIMIT 10"
    assert cypher_generator.validate_cypher_safety(valid) == valid

    for dangerous in [
        "CREATE (n:Teste) RETURN n",
        "MATCH (n) SET n.x = 1 RETURN n",
        "MATCH (n) DETACH DELETE n RETURN count(n)",
        "CALL apoc.export.json.all('out.json', {}) YIELD file RETURN file",
        "CALL dbms.components() YIELD name RETURN name",
        "MATCH (n) MERGE (n)-[:X]->(n) RETURN n",
    ]:
        with pytest.raises(ValueError):
            cypher_generator.validate_cypher_safety(dangerous)


def test_execute_safe_cypher_blocks_non_read_explain():
    class WriteSummary:
        query_type = "w"

    class FakeResult:
        def __init__(self, summary):
            self._summary = summary

        def consume(self):
            return self._summary

        def fetch(self, n):
            return []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, query, **kwargs):
            return FakeResult(WriteSummary())

    class FakeDriver:
        def session(self):
            return FakeSession()

    with patch.object(cypher_generator, "get_driver", return_value=FakeDriver()):
        with pytest.raises(ValueError, match="query_type=w"):
            cypher_generator.execute_safe_cypher("MATCH (n) RETURN n")


def test_execute_safe_cypher_allows_read_and_truncates():
    class ReadSummary:
        query_type = "r"

    class FakeRec:
        def __init__(self, idx):
            self.idx = idx

        def data(self):
            return {"idx": self.idx}

    class FakeResult:
        def consume(self):
            return ReadSummary()

        def fetch(self, n):
            return [FakeRec(i) for i in range(n)]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, query, **kwargs):
            return FakeResult()

    class FakeDriver:
        def session(self):
            return FakeSession()

    with patch.object(cypher_generator, "get_driver", return_value=FakeDriver()):
        rows = cypher_generator.execute_safe_cypher("MATCH (n) RETURN n", max_rows=5)
        assert len(rows) == 5


def test_pagerank_and_louvain_on_subgraph():
    nodes = [
        {"id": "c1", "nome": "Milho", "tipo": "CulturaAgricola", "descricao": ""},
        {"id": "p1", "nome": "Lagarta-do-cartucho", "tipo": "Praga", "descricao": ""},
        {"id": "m1", "nome": "Manejo Integrado", "tipo": "PraticaAgricola", "descricao": ""},
        {"id": "c2", "nome": "Soja", "tipo": "CulturaAgricola", "descricao": ""},
        {"id": "p2", "nome": "Percevejo-marrom", "tipo": "Praga", "descricao": ""},
    ]
    edges = [
        {"source_id": "p1", "target_id": "c1", "tipo": "AFETA"},
        {"source_id": "m1", "target_id": "p1", "tipo": "CONTROLA"},
        {"source_id": "p2", "target_id": "c2", "tipo": "AFETA"},
    ]

    ranked = compute_subgraph_pagerank(nodes=nodes, edges=edges, top_k=5)
    assert len(ranked) == 5
    assert ranked[0]["id"] == "c1"
    assert ranked[0]["pagerank"] > 0

    communities = detect_subgraph_communities(nodes=nodes, edges=edges)
    assert len(communities) >= 2
    assert sum(c["size"] for c in communities) == 5


def test_hybrid_retrieve_and_kag_engine_modes():
    fake_chunks = [
        {
            "trecho_id": "t1",
            "texto": "O milho é afetado pela lagarta-do-cartucho, controlada por MIP.",
            "pagina": 4,
            "documento_id": "doc1",
            "fonte": "manejo_pragas_milho.pdf",
            "score": 0.91,
        }
    ]
    fake_entities = [
        {
            "id": "e-milho",
            "nome": "Milho",
            "tipo": "CulturaAgricola",
            "descricao": "Cultura agrícola.",
            "hybrid_score": 0.88,
        }
    ]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, query, **kwargs):
            if "EXTRAIDO_DE" in query and "chunk_ids" in kwargs:
                return []
            if "SHORTEST" not in query and "path =" in query:
                rec = MagicMock()
                rec.data.return_value = {
                    "path_nodes": [
                        {"id": "e-milho", "nome": "Milho", "tipo": "CulturaAgricola", "descricao": ""},
                        {"id": "e-lagarta", "nome": "Lagarta-do-cartucho", "tipo": "Praga", "descricao": ""},
                    ],
                    "path_rels": [
                        {
                            "source_id": "e-lagarta",
                            "source_nome": "Lagarta-do-cartucho",
                            "target_id": "e-milho",
                            "target_nome": "Milho",
                            "tipo": "AFETA",
                            "ano": None,
                            "area_plantada_ha": None,
                            "quantidade_ton": None,
                        }
                    ],
                }
                return [rec]
            return []

    class FakeDriver:
        def session(self):
            return FakeSession()

    fake_llm_resp = MagicMock()
    fake_llm_resp.choices[0].message.content = (
        "O milho sofre ataque [Lagarta-do-cartucho] --(AFETA)--> [Milho] "
        "[Fonte: manejo_pragas_milho.pdf, p. 4]."
    )

    with (
        patch.object(hybrid_search, "generate_embeddings", return_value=[[0.1] * 1536]),
        patch.object(hybrid_search, "search_similar_chunks", return_value=fake_chunks),
        patch.object(hybrid_search, "search_fulltext_chunks", return_value=[]),
        patch.object(hybrid_search, "search_entities_hybrid", return_value=fake_entities),
        patch.object(hybrid_search, "get_driver", return_value=FakeDriver()),
    ):
        ret = hybrid_search.hybrid_retrieve("Como controlar pragas no milho?")

    assert len(ret["nodes"]) == 2
    assert len(ret["paths"]) == 1
    assert ret["confidence"] > 0

    with (
        patch.object(kag_engine, "hybrid_retrieve", return_value=ret),
        patch.object(kag_engine, "generate_and_run_cypher", return_value={"cypher": "", "rows": [], "error": None}),
        patch.object(kag_engine.client.chat.completions, "create", return_value=fake_llm_resp),
    ):
        ans_hybrid = kag_engine.answer_question("Como controlar pragas no milho?", mode="hybrid")

    assert ans_hybrid["mode"] == "hybrid"
    assert "[Lagarta-do-cartucho] --(AFETA)--> [Milho]" in ans_hybrid["answer"]

    with (
        patch.object(kag_engine, "search_similar_chunks", return_value=fake_chunks),
        patch.object(kag_engine.client.chat.completions, "create", return_value=fake_llm_resp),
    ):
        ans_vec = kag_engine.answer_question("Como controlar pragas no milho?", mode="vector")

    assert ans_vec["mode"] == "vector"
    assert ans_vec["paths"] == []


def test_benchmark_metrics_and_judge():
    ans = "A cultura [Lagarta-do-cartucho] --(AFETA)--> [Milho] [Fonte: manejo_pragas_milho.pdf, p. 4]."
    assert compute_entity_recall(ans, ["Milho", "Lagarta-do-cartucho"]) == 1.0
    assert compute_citation_score(ans) == 1.0

    fake_judge = MagicMock()
    fake_judge.choices[0].message.content = '{"faithfulness": 1.0, "unsupported_claims": [], "rationale": "Fiel ao contexto."}'
    with patch("evaluation.benchmark.client.chat.completions.create", return_value=fake_judge):
        res = judge_faithfulness("Pergunta", "Contexto", ans)

    assert res["faithfulness"] == 1.0


def test_render_interactive_graph_html():
    from utils.graph_vis import render_interactive_graph

    nodes = [
        {"id": "n1", "nome": "Milho", "tipo": "CulturaAgricola", "pagerank": 0.6, "descricao": "Grão"},
        {"id": "n2", "nome": "João Pessoa", "tipo": "Municipio", "pagerank": 0.4, "descricao": "Capital"},
    ]
    edges = [
        {
            "source_id": "n2",
            "target_id": "n1",
            "tipo": "PRODUZ",
            "ano": 2025,
            "area_plantada_ha": 100.0,
            "quantidade_ton": 200.0,
        }
    ]
    html = render_interactive_graph(nodes, edges, height=400)
    assert "Milho" in html
    assert "PRODUZ" in html
    assert "<html" in html.lower() or "vis.Network" in html


def test_clean_knowledge_subgraph_and_save_knowledge_mocked():
    from graph import repositories

    executed = []

    class FakeCounters:
        nodes_deleted = 2
        relationships_deleted = 3

    class FakeSummary:
        counters = FakeCounters()

    class FakeResult:
        def consume(self):
            return FakeSummary()

        def single(self):
            return {"total": 1}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, query, **kwargs):
            executed.append(query)
            return FakeResult()

    class FakeDriver:
        def session(self):
            return FakeSession()

    with patch.object(repositories, "get_driver", return_value=FakeDriver()):
        stats = repositories.clean_knowledge_subgraph()
        assert len(stats) == 4
        assert any("e:Documento AND e.origem = 'SNCR'" in q for q in executed)

        executed.clear()
        total = repositories.save_knowledge({
            "entities": [
                {
                    "id": "e1",
                    "nome": "Milho",
                    "tipo": "CulturaAgricola",
                    "descricao": "Grão",
                    "trecho_id": "t1",
                    "embedding": [0.1] * 1536,
                }
            ],
            "relations": [
                {
                    "source_id": "e1",
                    "target_id": "e1",
                    "tipo": "AFETA",
                    "trecho_id": "t1",
                }
            ],
        })
        assert total == 2
        assert any("SET e:CulturaAgricola" in q for q in executed)
        assert any("MERGE (e)-[:EXTRAIDO_DE]->(t)" in q for q in executed)
        assert any("MERGE (source)-[r:AFETA]->(target)" in q for q in executed)
