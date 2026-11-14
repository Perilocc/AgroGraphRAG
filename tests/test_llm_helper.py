from unittest.mock import MagicMock, patch
import pytest
from neo4j.exceptions import ServiceUnavailable

from graph import repositories
from ingestion import entity_extractor, pipeline
from utils import llm


def test_create_chat_completion_keeps_temperature_for_standard_model():
    client = MagicMock()
    llm.create_chat_completion(
        client,
        model="gpt-4o-mini",
        temperature=0,
        messages=[{"role": "user", "content": "oi"}],
    )

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0


@pytest.mark.parametrize("model_name", ["gpt-6-luna", "gpt-5-mini", "o3-mini", "o4-mini"])
def test_create_chat_completion_omits_temperature_for_fixed_temp_models(model_name):
    client = MagicMock()
    llm.create_chat_completion(
        client,
        model=model_name,
        temperature=0,
        messages=[{"role": "user", "content": "oi"}],
    )

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == model_name
    assert "temperature" not in kwargs


def test_create_chat_completion_retries_and_caches_on_unsupported_temperature_error():
    llm._FIXED_TEMPERATURE_MODELS.clear()
    fake_resp = MagicMock()
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        Exception(
            "Error code: 400 - Unsupported value: 'temperature' does not support 0 with this model. Only the default (1) value is supported."
        ),
        fake_resp,
        fake_resp,
    ]

    res1 = llm.create_chat_completion(
        client,
        model="custom-reasoning-model",
        temperature=0,
        messages=[{"role": "user", "content": "oi"}],
    )
    assert res1 is fake_resp
    assert client.chat.completions.create.call_count == 2
    assert "temperature" in client.chat.completions.create.call_args_list[0].kwargs
    assert "temperature" not in client.chat.completions.create.call_args_list[1].kwargs

    res2 = llm.create_chat_completion(
        client,
        model="custom-reasoning-model",
        temperature=0,
        messages=[{"role": "user", "content": "oi2"}],
    )
    assert res2 is fake_resp
    assert client.chat.completions.create.call_count == 3
    assert "temperature" not in client.chat.completions.create.call_args_list[2].kwargs


def test_create_chat_completion_reraises_unrelated_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("Error code: 500 - Internal error")

    with pytest.raises(RuntimeError, match="500"):
        llm.create_chat_completion(
            client,
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": "oi"}],
        )

    assert client.chat.completions.create.call_count == 1


def test_extract_knowledge_omits_temperature_for_gpt6_luna():
    fake_response = MagicMock()
    fake_response.choices[0].message.content = '{"entities": [], "relations": []}'

    with (
        patch.object(entity_extractor, "OPENAI_MODEL", "gpt-6-luna"),
        patch(
            "ingestion.entity_extractor.client.chat.completions.create",
            return_value=fake_response,
        ) as mock_create,
    ):
        result = entity_extractor.extract_knowledge("Texto sobre milho.", "chunk-1")

    assert result == {"entities": [], "relations": [], "unresolved_municipalities": []}
    _, kwargs = mock_create.call_args
    assert kwargs["model"] == "gpt-6-luna"
    assert "temperature" not in kwargs


def test_create_openai_client_sets_finite_timeout():
    client = llm.create_openai_client("test-key")
    assert client.timeout == llm.DEFAULT_OPENAI_TIMEOUT
    assert client.max_retries == 2


def test_find_similar_existing_entities_batch_retries_on_transient_read_error():
    class FakeRec:
        def __init__(self, data):
            self._data = data

        def data(self):
            return self._data

    class FlakySession:
        def __init__(self, fail_first):
            self._fail_first = fail_first

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, query, **kwargs):
            if self._fail_first:
                raise ServiceUnavailable("Failed to read from defunct connection")
            return [FakeRec({"source_id": "e1", "id": "db1", "nome": "Milho", "tipo": "CulturaAgricola", "score": 0.95})]

    class FakeDriver:
        def __init__(self, fail_first):
            self._fail_first = fail_first

        def session(self):
            return FlakySession(self._fail_first)

    drivers = iter([FakeDriver(fail_first=True), FakeDriver(fail_first=False)])
    reset_calls = []

    with (
        patch.object(repositories, "get_driver", side_effect=lambda: next(drivers)),
        patch.object(repositories, "reset_driver", side_effect=lambda: reset_calls.append(True)),
    ):
        matches = repositories.find_similar_existing_entities_batch(
            [{"id": "e1", "tipo": "CulturaAgricola", "embedding": [0.1, 0.2]}]
        )

    assert len(reset_calls) == 1
    assert len(matches["e1"]) == 1
    assert matches["e1"][0]["id"] == "db1"


def test_ingest_pdf_reports_progress_for_multiple_chunks(tmp_path):
    pdf_path = tmp_path / "multi.pdf"
    pdf_path.touch()

    fake_pages = [
        {"page": 1, "text": "A " * 500, "needs_ocr": False},
        {"page": 2, "text": "B " * 500, "needs_ocr": False},
    ]
    fake_chunks = [
        {"id": "c1", "text": "Trecho 1", "source": "multi.pdf", "page": 1},
        {"id": "c2", "text": "Trecho 2", "source": "multi.pdf", "page": 2},
    ]
    progress_messages = []

    with (
        patch("ingestion.pipeline.read_document", return_value={"type": "pdf", "content": fake_pages}),
        patch("ingestion.pipeline.chunk_pages", return_value=fake_chunks),
        patch("ingestion.pipeline.generate_embeddings", return_value=[[0.1, 0.2], [0.2, 0.3]]),
        patch("ingestion.pipeline.save_chunks", return_value=2),
        patch("ingestion.pipeline.get_pb_municipios_map", return_value={}),
        patch(
            "ingestion.pipeline.extract_knowledge",
            side_effect=lambda text, cid, pb_municipios_map=None: {
                "entities": [],
                "relations": [],
                "unresolved_municipalities": [],
            },
        ),
    ):
        res = pipeline.ingest_pdf(pdf_path, progress_callback=progress_messages.append)

    assert res["chunks"] == 2
    assert any("2/2 trechos" in m for m in progress_messages)

