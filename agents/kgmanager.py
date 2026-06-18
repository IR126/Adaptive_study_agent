import asyncio
from datetime import datetime, timezone
from graphiti_core import Graphiti
from graph.config import get_graphiti_client

from utils.confidence_store import update as update_store, get as get_confidence


async def get_weakest_concepts(domain: str, top_k: int = 3):
    """
    Fetches the weakest concepts from the graph for a given domain.
    Weakness = low confidence score.
    """
    client: Graphiti = get_graphiti_client()

    results = await client.search(
        query=f"weakest concepts in {domain}",
        num_results=top_k,
    )

    await client.close()
    return results

async def update_confidence(concept_name: str, correct: bool):
    client: Graphiti = get_graphiti_client()
    old_conf, new_conf = update_store(concept_name, correct)

    await client.add_episode(
        name=f"quiz_result_{concept_name}_{datetime.now().strftime('%H%M%S')}",
        episode_body=f"User answered question about {concept_name}. Result: {'correct' if correct else 'incorrect'}. Confidence updated from {old_conf:.2f} to {new_conf:.2f}.",
        source_description="quiz feedback",
        reference_time=datetime.now(timezone.utc),
    )

    print(f"Updated '{concept_name}': {old_conf:.2f} → {new_conf:.2f}")
    await client.close()


if __name__ == "__main__":
    async def test():
        print("=== Weakest concepts ===")
        results = await get_weakest_concepts("DSA")
        for r in results:
            print(f" - {r.fact}")

        print("\n=== Simulating wrong answer on Memoization ===")
        await update_confidence("Memoization", correct=False)

        print("\n=== Simulating correct answer on Tabulation ===")
        await update_confidence("Tabulation", correct=True)

    asyncio.run(test())