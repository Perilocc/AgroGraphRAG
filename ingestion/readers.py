from pathlib import Path
import pandas as pd
import fitz
import re


def normalize_pdf_text(text: str) -> str:
    """Realiza normalizações seguras no texto extraído."""
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pdf(file_path: Path) -> list[dict]:
    """Extrai e normaliza o texto de cada página de um PDF usando PyMuPDF."""
    pages = []

    with fitz.open(file_path) as pdf:
        for index, page in enumerate(pdf):
            data = page.get_text("dict", sort=True)
            blocks = []

            for block in data["blocks"]:
                if "lines" not in block:
                    continue

                lines = []

                for line in block["lines"]:
                    text = "".join(
                        span["text"]
                        for span in line["spans"]
                    ).strip()

                    if text:
                        lines.append(text)

                if lines:
                    blocks.append("\n".join(lines))

            raw_text = "\n\n".join(blocks).strip()
            text = normalize_pdf_text(raw_text) if raw_text else ""

            pages.append({
                "page": index + 1,
                "text": text,
                "needs_ocr": not bool(text),
            })

    return pages


def read_csv(file_path: Path) -> pd.DataFrame:
    """Lê um arquivo CSV."""
    encodings = ["utf-8-sig", "latin-1", "cp1252"]

    for encoding in encodings:
        try:
            return pd.read_csv(
                file_path,
                sep=None,
                engine="python",
                encoding=encoding,
            )
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Não foi possível identificar a codificação de {file_path.name}")


def read_excel(file_path: Path) -> dict[str, pd.DataFrame]:
    """Lê todas as planilhas de um arquivo Excel."""
    excel = pd.ExcelFile(file_path)

    return {
        sheet_name: pd.read_excel(excel, sheet_name=sheet_name)
        for sheet_name in excel.sheet_names
    }


def read_document(file_path: Path) -> dict:
    """Identifica o formato e direciona para o leitor correspondente."""
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        return {
            "type": "pdf",
            "content": read_pdf(file_path),
        }

    if extension == ".csv":
        return {
            "type": "table",
            "content": {"CSV": read_csv(file_path)},
        }

    if extension in {".xls", ".xlsx"}:
        return {
            "type": "table",
            "content": read_excel(file_path),
        }

    raise ValueError(f"Formato não suportado: {extension}")
