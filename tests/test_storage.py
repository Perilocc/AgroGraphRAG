from graph.repositories import save_chunks

def test_save_chunks():
    chunks = [{
        "id": "teste-agro-001",
        "text": "O milho é uma cultura agrícola importante.",
        "source": "teste_agro.pdf",
        "page": 1,
        "embedding": [0.01] * 1536,
    }]

    total = save_chunks(chunks)

    assert total == 1
