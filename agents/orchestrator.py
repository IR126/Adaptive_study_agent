import asyncio
import grandalf
import os
from dotenv import load_dotenv
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from agents.ingestor import ingest_text
from agents.kgmanager import update_confidence, get_weakest_concepts
from agents.quiz_teach import get_priority_queue, routing_decision, run_study_session
from agents.llm_quiz import generate_question, evaluate_answer

load_dotenv()

import os
from dotenv import load_dotenv
load_dotenv()

# Enable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "adaptive-study-agent")

# ── State schema ──────────────────────────────────────────
# This is the shared memory that flows between all agents.
# Every agent reads from it and writes back to it.

class StudyState(TypedDict):
    domain: str                          # which domain we're studying
    mode: Literal["ingest", "study", ""] # what triggered this session
    current_concept: str                 # concept being asked right now
    current_confidence: float            # its confidence score
    routing: Literal["teach", "guided_quiz", "cold_quiz", ""]
    user_answer: str                     # what the user typed
    answer_correct: bool                 # did they get it right
    session_complete: bool               # are we done for this session


# ── Agent nodes ───────────────────────────────────────────
# Each function is one node in the LangGraph graph.
# It receives state, does its job, returns updated state.

async def ingestor_node(state: StudyState) -> StudyState:
    print("\n[Orchestrator] → Ingestor")
    await ingest_text(
        content=state.get("content", ""),
        domain=state["domain"],
        source_name=state.get("source_name", "notes"),
    )
    return {**state, "mode": "study"}


async def priority_node(state: StudyState) -> StudyState:
    """Fetches weakest concept and decides routing."""
    print("\n[Orchestrator] → Priority scoring")
    queue = await get_priority_queue(state["domain"])

    if not queue:
        return {**state, "session_complete": True}

    top_concept, top_conf, top_score = queue[0]
    routing = routing_decision(top_conf)

    print(f"  Top concept: {top_concept} (conf={top_conf}, route={routing})")

    return {
        **state,
        "current_concept": top_concept,
        "current_confidence": top_conf,
        "routing": routing,
    }


async def teach_node(state: StudyState) -> StudyState:
    print(f"\n[Orchestrator] → Teach agent")
    print(f"  Teaching: {state['current_concept']}")
    print(f"  [LLM explanation will go here]")
    # Mark as seen — slight confidence bump for exposure
    await update_confidence(state["current_concept"], correct=True)
    return {**state, "session_complete": True}


async def guided_quiz_node(state: StudyState) -> StudyState:
    print(f"\n[Orchestrator] → Guided quiz")
    print(f"  Q: Explain {state['current_concept']} with an example. (Hints available)")
    answer = input("  Your answer: ")
    correct = len(answer.strip()) > 20  # placeholder eval
    await update_confidence(state["current_concept"], correct=correct)
    return {**state, "user_answer": answer, "answer_correct": correct, "session_complete": True}


async def cold_quiz_node(state: StudyState) -> StudyState:
    print(f"\n[Orchestrator] → Cold quiz (no hints)")
    print(f"  Q: Explain {state['current_concept']} and its time complexity.")
    answer = input("  Your answer: ")
    correct = len(answer.strip()) > 20  # placeholder eval
    await update_confidence(state["current_concept"], correct=correct)
    return {**state, "user_answer": answer, "answer_correct": correct, "session_complete": True}


# ── Routing logic (conditional edges) ─────────────────────

def route_after_priority(state: StudyState) -> Literal["teach", "guided_quiz", "cold_quiz", "end"]:
    if state.get("session_complete"):
        return "end"
    return state.get("routing", "guided_quiz")

async def guided_quiz_node(state: StudyState) -> StudyState:
    print(f"\n[Orchestrator] → Guided quiz")
    question = await generate_question(state["current_concept"], "guided_quiz")
    print(f"  Q: {question}")
    answer = input("  Your answer: ")
    correct, feedback = await evaluate_answer(state["current_concept"], question, answer)
    print(f"  Feedback: {feedback}")
    await update_confidence(state["current_concept"], correct=correct)
    return {**state, "user_answer": answer, "answer_correct": correct, "session_complete": True}


async def cold_quiz_node(state: StudyState) -> StudyState:
    print(f"\n[Orchestrator] → Cold quiz (no hints)")
    question = await generate_question(state["current_concept"], "cold_quiz")
    print(f"  Q: {question}")
    answer = input("  Your answer: ")
    correct, feedback = await evaluate_answer(state["current_concept"], question, answer)
    print(f"  Feedback: {feedback}")
    await update_confidence(state["current_concept"], correct=correct)
    return {**state, "user_answer": answer, "answer_correct": correct, "session_complete": True}


async def teach_node(state: StudyState) -> StudyState:
    print(f"\n[Orchestrator] → Teach agent")
    explanation = await generate_question(state["current_concept"], "teach")
    print(f"\n  {explanation}")
    await update_confidence(state["current_concept"], correct=True)
    return {**state, "session_complete": True}


# ── Build the graph ────────────────────────────────────────

def build_graph():
    graph = StateGraph(StudyState)

    graph.add_node("priority", priority_node)
    graph.add_node("teach", teach_node)
    graph.add_node("guided_quiz", guided_quiz_node)
    graph.add_node("cold_quiz", cold_quiz_node)

    graph.set_entry_point("priority")

    graph.add_conditional_edges(
        "priority",
        route_after_priority,
        {
            "teach": "teach",
            "guided_quiz": "guided_quiz",
            "cold_quiz": "cold_quiz",
            "end": END,
        }
    )

    graph.add_edge("teach", END)
    graph.add_edge("guided_quiz", END)
    graph.add_edge("cold_quiz", END)

    return graph.compile()


# ── Run ───────────────────────────────────────────────────

async def run_session(domain: str):
    app = build_graph()
    initial_state = StudyState(
        domain=domain,
        mode="study",
        current_concept="",
        current_confidence=0.0,
        routing="",
        user_answer="",
        answer_correct=False,
        session_complete=False,
    )
    result = await app.ainvoke(initial_state)
    print(f"\n[Session complete]")
    print(f"  Concept tested: {result['current_concept']}")
    print(f"  Answer correct: {result['answer_correct']}")

def visualize_graph():
    app = build_graph()
    print(app.get_graph().draw_ascii())


if __name__ == "__main__":
    visualize_graph()
    asyncio.run(run_session("Biology"))