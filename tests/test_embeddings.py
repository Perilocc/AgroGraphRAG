from retrieval.embeddings import generate_embeddings

def test_generate_embeddings():
    result = generate_embeddings([
        "O cultivo de milho é importante para o agronegócio brasileiro."
    ])

    assert len(result) == 1
    assert len(result[0]) == 1536
