from dotenv import load_dotenv
import os

load_dotenv()

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME") or "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE") or None

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
OPENAI_EMBEDDING_MODEL = (
    os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"
)
OPENAI_JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL") or "gpt-4o"


def validate_config(require_openai: bool = True):
    required = {
        "NEO4J_URI": NEO4J_URI,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
    }
    if require_openai:
        required["OPENAI_API_KEY"] = OPENAI_API_KEY

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise ValueError(
            f"Variáveis ausentes no .env: {', '.join(missing)}"
        )
