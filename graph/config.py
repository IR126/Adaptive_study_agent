import os
from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.llm_client import OpenAIClient, LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OLLAMA_BASE_URL = "http://localhost:11434/v1"
LLM_MODEL = "llama3.2:latest"
EMBED_MODEL = "nomic-embed-text:latest"


def get_graphiti_client() -> Graphiti:
    llm_client = OpenAIClient(
        config=LLMConfig(
        api_key="ollama",
        model="llama3.2:latest",
        small_model="llama3.2:latest",
        base_url=OLLAMA_BASE_URL,
        )
    )

    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key="ollama",
            embedding_model="nomic-embed-text:latest",
            base_url=OLLAMA_BASE_URL,
            embedding_dim=768,
        )
    )

    return Graphiti(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        llm_client=llm_client,
        embedder=embedder,
    )