import streamlit as st
import asyncio
from agents.ingestor import ingest_text
from agents.quiz_teach import get_priority_queue, routing_decision
from agents.llm_quiz import generate_question, evaluate_answer
from agents.kgmanager import update_confidence

st.set_page_config(page_title="Adaptive Study Agent", layout="wide")
st.title(" Adaptive Study Agent")

# Sidebar — model selector (Ollama only for now)
with st.sidebar:
    st.subheader("Model")
    model_choice = st.selectbox(
        "LLM backend",
        ["Ollama (local) — llama3.2", "Anthropic API (coming soon)"],
        disabled=False
    )
    if "coming soon" in model_choice:
        st.warning("API mode not wired up yet — using Ollama for now.")

tab_ingest, tab_study, tab_graph = st.tabs(["📥 Ingest", "🎯 Study Session", "🕸️ Knowledge Graph"])

# ── INGEST TAB ──────────────────────────────────────
with tab_ingest:
    st.subheader("Add study material")
    domain = st.text_input("Domain name", placeholder="e.g. DSA, Biology, SQL")
    source_name = st.text_input("Source name", placeholder="e.g. Chapter 3 notes")
    content = st.text_area("Paste your notes", height=200)

    if st.button("Ingest", type="primary"):
        if not domain or not content:
            st.error("Domain and content are required.")
        else:
            with st.spinner("Extracting concepts via local LLM... (can take 1-3 min)"):
                asyncio.run(ingest_text(content, domain, source_name or "untitled"))
            st.success(f"Ingested into domain '{domain}'")

# ── STUDY SESSION TAB ───────────────────────────────
with tab_study:
    st.subheader("Run a study session")
    study_domain = st.text_input("Which domain?", key="study_domain", placeholder="e.g. DSA")

    if st.button("Get priority queue"):
        with st.spinner("Scoring concepts..."):
            queue = asyncio.run(get_priority_queue(study_domain))
        if not queue:
            st.warning("No concepts found for this domain. Ingest some notes first.")
        else:
            st.session_state["queue"] = queue
            st.session_state["queue_idx"] = 0

    if "queue" in st.session_state and st.session_state["queue"]:
        queue = st.session_state["queue"]
        idx = st.session_state.get("queue_idx", 0)

        st.write("**Priority queue (weakest first):**")
        for c, conf, score in queue:
            st.write(f"- {c} — confidence {conf:.2f} — priority {score:.3f}")

        if idx < len(queue):
            concept, conf, score = queue[idx]
            mode = routing_decision(conf)
            st.divider()
            st.write(f"### Now testing: {concept}  `{mode}`")

            if "current_question" not in st.session_state:
                with st.spinner("Generating question..."):
                    st.session_state["current_question"] = asyncio.run(
                        generate_question(concept, mode)
                    )

            st.info(st.session_state["current_question"])
            answer = st.text_area("Your answer", key=f"answer_{idx}")

            if st.button("Submit answer", key=f"submit_{idx}"):                
                with st.spinner("Evaluating..."):
                    correct, feedback = asyncio.run(
                        evaluate_answer(concept, st.session_state["current_question"], answer)
                    )
                    asyncio.run(update_confidence(concept, correct))
                st.session_state["last_result"] = (correct, feedback)

            if "last_result" in st.session_state:
                correct, feedback = st.session_state["last_result"]
                st.write(f"**Correct:** {correct}")
                st.write(f"**Feedback:** {feedback}")
                is_last_concept = idx >= len(queue) - 1
                if is_last_concept:
                    st.success("Session complete! All concepts in queue covered.")
                else:
                    if st.button("Next concept →",key=f"next_{idx}"):
                        del st.session_state["current_question"]
                        del st.session_state["last_result"]
                        st.session_state["queue_idx"] = idx + 1
                        st.rerun()
                    

# ── KNOWLEDGE GRAPH TAB ─────────────────────────────
with tab_graph:
    st.subheader("Explore your knowledge graph")
    st.write("Open Neo4j Browser to visually explore the full graph:")
    st.code("http://localhost:7474", language=None)
    st.write("Run this query to see everything:")
    st.code("MATCH (n) RETURN n LIMIT 50", language="cypher")