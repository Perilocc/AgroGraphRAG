
from dotenv import load_dotenv
import os

load_dotenv()

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small"
)


def validate_config():
    required = {
        "NEO4J_URI": NEO4J_URI,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise ValueError(
            f"Variáveis ausentes no .env: {', '.join(missing)}"
        )
