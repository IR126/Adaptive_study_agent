import asyncio
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from datetime import datetime, timezone
from graph.config import get_graphiti_client


async def ingest_text(content: str, domain: str, source_name: str):
    client: Graphiti = get_graphiti_client()
    await client.build_indices_and_constraints()

    await client.add_episode(
        name=f"[{domain}] {source_name}",
        episode_body=content,
        source=EpisodeType.text,
        source_description=f"Domain: {domain}",
        reference_time=datetime.now(timezone.utc),
    )

    print(f"Ingested: '{source_name}' into domain '{domain}'")
    await client.close()


if __name__ == "__main__":
    sample_notes = """
    Photosynthesis is the process by which plants convert sunlight into glucose.
    It requires chlorophyll, water, and carbon dioxide. The light reactions occur 
    in the thylakoid membrane. The Calvin cycle occurs in the stroma and fixes carbon.
    Chloroplasts are the organelles where photosynthesis takes place.
    """
    asyncio.run(ingest_text(sample_notes, domain="Biology", source_name="Photosynthesis notes"))