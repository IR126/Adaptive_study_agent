import asyncio
import os
from datetime import datetime, timezone
from neo4j import AsyncGraphDatabase
from graph.config import get_graphiti_client
from utils.confidence_store import get as get_confidence
from dotenv import load_dotenv

load_dotenv()


def decay_weight(last_tested: datetime | None) -> float:
    if last_tested is None:
        return 1.0
    days_since = (datetime.now(timezone.utc) - last_tested).days
    if days_since >= 5:
        return 1.0
    elif days_since >= 2:
        return 0.6
    else:
        return 0.2


def routing_decision(confidence: float) -> str:
    if confidence < 0.3:
        return "teach"
    elif confidence <= 0.6:
        return "guided_quiz"
    else:
        return "cold_quiz"


async def get_concepts_for_domain(domain: str) -> list[str]:
    """Fetch concepts tagged to this domain via direct Cypher."""
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    concepts = []
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e:Episodic)-[:MENTIONS]->(n:Entity)
            WHERE e.name STARTS WITH $tag
            RETURN DISTINCT n.name AS concept
            """,
            tag=f"[{domain}]"
        )
        async for record in result:
            concepts.append(record["concept"])
    await driver.close()
    return concepts


async def get_prereqs_from_graph(concept: str, known_concepts: list[str]) -> list[str]:
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )
    prereqs = []
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (a:Entity)-[r]->(b:Entity)
            WHERE a.name = $concept
            AND type(r) IN ['REQUIRES', 'DEPENDS_ON', 'IS_BASED_ON', 'RELATES_TO']
            AND b.name IN $known
            RETURN b.name AS prereq
            """,
            concept=concept,
            known=known_concepts
        )
        async for record in result:
            prereqs.append(record["prereq"])
    await driver.close()
    return prereqs


async def get_priority_queue(domain: str):
    concepts = await get_concepts_for_domain(domain)

    if not concepts:
        print(f"No concepts found for domain '{domain}'.")
        return []

    # Fetch prereqs for all concepts upfront
    prereq_map = {}
    for concept in concepts:
        prereq_map[concept] = await get_prereqs_from_graph(concept,concepts)

    confidence_map = {c: get_confidence(c) for c in concepts}
    weak_concepts = [c for c, conf in confidence_map.items() if conf < 0.4]

    scored = []
    for concept in concepts:
        conf = confidence_map[concept]
        prereqs = prereq_map[concept]
        weak_prereqs_for_concept = [p for p in prereqs if p in weak_concepts]
        penalty = 0.3 if weak_prereqs_for_concept else 1.0
        score = round((1 - conf) * decay_weight(None) * penalty, 4)
        scored.append((concept, conf, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored


if __name__ == "__main__":
    async def test():
        queue = await get_priority_queue("DSA")
        for concept, conf, score in queue:
            print(f"{concept:<30} conf={conf:.2f}  priority={score:.4f}  → {routing_decision(conf)}")

    asyncio.run(test())