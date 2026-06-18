import asyncio
from openai import AsyncOpenAI

OLLAMA_BASE_URL = "http://localhost:11434/v1"
LLM_MODEL = "llama3.2:latest"

_client = None

def get_client():
    """Lazy-load the OpenAI client to avoid connection errors at import time."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key="ollama",
            base_url=OLLAMA_BASE_URL,
        )
    return _client


async def generate_question(concept: str, mode: str) -> str:
    """
    Generates a question about a concept based on routing mode.
    mode: teach | guided_quiz | cold_quiz
    """

    prompts =  {
        "teach": f"""You are a knowledgeable tutor. The student has low confidence in '{concept}'.
Write a clear 3-sentence explanation of '{concept}' with one concrete example.
Be concise. No preamble.""",

        "guided_quiz": f"""You are a knowledgeable tutor. Generate one guided quiz question about '{concept}'.
Include a subtle hint in the question itself.
Format: just the question, nothing else.""",

        "cold_quiz": f"""You are a knowledgeable tutor. Generate one challenging question about '{concept}'.
No hints. Expect the student to know this well.
Format: just the question, nothing else.""",
    }

    response = await get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompts[mode]}],
        max_tokens=200,
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()


async def evaluate_answer(concept: str, question: str, answer: str) -> tuple[bool, str]:
    """
    Uses LLM to evaluate if the answer is correct.
    Returns (is_correct, feedback)
    """

    prompt = f"""You are a CS tutor evaluating a student's answer.

Concept: {concept}
Question: {question}
Student's answer: {answer}

Evaluate if the answer is correct and complete.
Respond in this exact format:
CORRECT: true or false
FEEDBACK: one sentence of feedback"""

    response = await get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.2,
    )

    text = response.choices[0].message.content.strip()

    # Parse response
    correct = "true" in text.lower().split("correct:")[1].split("\n")[0].lower()
    feedback = text.split("FEEDBACK:")[-1].strip() if "FEEDBACK:" in text else "No feedback."

    return correct, feedback


if __name__ == "__main__":
    async def test():
        print("=== Generating guided quiz question ===")
        q = await generate_question("Memoization", "guided_quiz")
        print(f"Q: {q}")

        print("\n=== Evaluating a sample answer ===")
        correct, feedback = await evaluate_answer(
            concept="Memoization",
            question=q,
            answer="Memoization stores results of expensive function calls and returns cached results when the same inputs occur again."
        )
        print(f"Correct: {correct}")
        print(f"Feedback: {feedback}")

    asyncio.run(test())