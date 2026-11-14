from utils.config import (
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
)
from utils.llm import create_openai_client

client = create_openai_client(OPENAI_API_KEY)


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Gera embeddings em lotes usando a API da OpenAI."""
    if not texts:
        return []

    embeddings = []
    batch_size = 100

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]

        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=batch,
        )

        ordered = sorted(response.data, key=lambda item: item.index)
        embeddings.extend(item.embedding for item in ordered)

    return embeddings
