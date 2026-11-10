from utils.paths import DATA_DIR

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".csv",
    ".xls",
    ".xlsx",
}


def discover_files():
    """Localiza arquivos suportados dentro de data/."""
    if not DATA_DIR.exists():
        return []

    return sorted(
        file
        for file in DATA_DIR.rglob("*")
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def get_source_info(file_path):
    """Identifica categoria e instituição pela estrutura de pastas."""
    relative_path = file_path.relative_to(DATA_DIR)
    parts = relative_path.parts

    category = parts[0] if len(parts) >= 2 else "unknown"
    institution = parts[1] if len(parts) >= 2 else "unknown"

    return category, institution
