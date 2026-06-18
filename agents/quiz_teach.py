import asyncio
from datetime import datetime, timezone, timedelta
from graphiti_core import Graphiti
from graph.config import get_graphiti_client
from utils.confidence_store import get as get_confidence


def decay_weight(last_tested: datetime | None) -> float:
    """
    Boosts priority if concept hasn't been tested recently.
    Not tested in 5+ days → weight = 1.0 (full boost)
    Tested today → weight = 0.2 (low boost)
    """
    if last_tested is None:
        return 1.0  

    days_since = (datetime.now(timezone.utc) - last_tested).days

    if days_since >= 5:
        return 1.0
    elif days_since >= 2:
        return 0.6
    else:
        return 0.2


def prereq_penalty(concept_name: str, weak_prereqs: list[str]) -> float:
    """
    If a concept has weak prerequisites, penalize it
    and ask the prereq first instead.
    prereq_map defines what each concept depends on.
    """
    prereq_map = {
        "Dynamic Programming": ["Recursion"],
        "Memoization": ["Dynamic Programming", "Recursion"],
        "Tabulation": ["Dynamic Programming"],
    }

    prereqs = prereq_map.get(concept_name, [])
    weak = [p for p in prereqs if p in weak_prereqs]

    if weak:
        return 0.3  # deprioritize — fix the foundation first
    return 1.0


def compute_priority(concept_name: str, confidence: float,
                     last_tested: datetime | None,
                     weak_prereqs: list[str]) -> float:
    score = (1 - confidence) \
            * decay_weight(last_tested) \
            * prereq_penalty(concept_name, weak_prereqs)
    return round(score, 4)


from neo4j import AsyncGraphDatabase
import os

async def get_priority_queue(domain: str):
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

    if not concepts:
        return []

    weak_prereqs = [c for c in concepts if get_confidence(c) < 0.4]
    scored = []
    for concept in concepts:
        conf = get_confidence(concept)
        score = compute_priority(concept, conf, None, weak_prereqs)
        scored.append((concept, conf, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored


def routing_decision(confidence: float) -> str:
    """
    The conditional edge logic from your spec.
    """
    if confidence < 0.3:
        return "teach"
    elif confidence <= 0.6:
        return "guided_quiz"
    else:
        return "cold_quiz"


async def run_study_session(domain: str):
    print(f"\n=== Study Session: {domain} ===\n")

    queue = await get_priority_queue(domain)

    print("Priority queue (weakest first):")
    for concept, conf, score in queue:
        mode = routing_decision(conf)
        print(f"  {concept:<25} conf={conf:.2f}  priority={score:.4f}  → {mode}")

    # Pick the top concept
    top_concept, top_conf, top_score = queue[0]
    mode = routing_decision(top_conf)

    print(f"\nAsking about: {top_concept} (mode: {mode})")

    if mode == "teach":
        print(f"\n[TEACH] {top_concept} has low confidence ({top_conf}).")
        print(f"Explanation: {top_concept} is a core concept. Let's review it together.")
        print("(Full LLM explanation goes here in next step)")

    elif mode == "guided_quiz":
        print(f"\n[GUIDED QUIZ] Here's a question about {top_concept}:")
        print(f"Q: What is the difference between {top_concept} and Tabulation?")
        print("(Hint available if needed)")

    elif mode == "cold_quiz":
        print(f"\n[COLD QUIZ] No hints. Timer starts now.")
        print(f"Q: Explain {top_concept} and give an example.")


if __name__ == "__main__":
    asyncio.run(run_study_session("DSA"))