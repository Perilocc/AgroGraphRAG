
import hashlib


def chunk_pages(
    pages: list[dict],
    source: str,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[dict]:
    """
    Divide páginas de documentos em trechos menores.
    Preserva a origem e o número da página.
    """

    chunks = []

    for page in pages:
        text = page.get("text", "").strip()

        if not text:
            continue

        start = 0

        while start < len(text):
            end = start + chunk_size
            content = text[start:end].strip()

            if content:
                chunk_id = hashlib.sha256(
                    f"{source}:{page['page']}:{start}:{content}".encode()
                ).hexdigest()

                chunks.append({
                    "id": chunk_id,
                    "text": content,
                    "source": source,
                    "page": page["page"],
                })

            if end >= len(text):
                break

            start = end - overlap

    return chunks
