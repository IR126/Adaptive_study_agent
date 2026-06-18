# Adaptive Study Agent

A multi-agent study system with persistent temporal memory. It tracks what you understand, how that understanding changes over time, and quizzes you accordingly — instead of treating every session as a blank slate.

## Why this exists

Most quiz tools have no memory of what you specifically know. They cannot tell you that your understanding of dynamic programming is weak because your recursion foundation has a gap, and they forget everything between sessions. This system builds a knowledge graph of concepts and relationships, where every edge carries a confidence score that updates as you answer questions. The graph is bi-temporal, meaning it tracks both when a fact was true and when it was recorded, so stale knowledge can be invalidated without losing history.

## Architecture

The system is composed of five layers.

Neo4j is the graph database that stores concepts, relationships, and episode history. Graphiti sits on top of Neo4j and manages the bi-temporal logic: writing new facts, resolving conflicts, and supporting point-in-time queries. An Ollama instance running locally (llama3.2) handles entity extraction during ingestion and question generation during study sessions. LangGraph orchestrates the agents as a stateful graph with conditional edges, routing between teaching, guided quizzing, and cold quizzing based on a priority score. An MCP server exposes the same knowledge graph and tools to any MCP-compatible client, including Claude Desktop, so the system can be operated conversationally instead of through scripts.

A Streamlit interface is also included as a lighter-weight alternative to MCP, with three tabs for ingesting notes, running a study session, and inspecting the knowledge graph.

## Agents

The Ingestor accepts raw text, sends it to the local LLM for entity and relationship extraction, and writes the resulting triples into the graph through Graphiti. The KG Manager updates confidence scores after every quiz answer and persists them so that future sessions read real history rather than defaults. The Quiz and Teach agent computes a priority score for every concept in a domain and decides whether to teach, run a guided quiz, or run a cold quiz. The Orchestrator is the LangGraph state machine that ties these together, with the routing decision made via conditional edges rather than a fixed sequence.

## Priority scoring

Each concept's priority is computed as:

```
priority_score = (1 - confidence) x decay_weight(last_tested) x prereq_penalty
```

Confidence is a float between 0 and 1, updated after every answer. Decay weight increases priority for concepts that have not been tested recently, implementing a simple form of spaced repetition. Prerequisite penalty reduces the priority of a concept if its prerequisites are still weak, so the system surfaces foundational gaps before downstream symptoms.

Routing based on confidence follows this logic:

```
confidence < 0.3   -> teach mode
0.3 to 0.6         -> guided quiz, hints available
above 0.6          -> cold quiz, no hints
```

## Domain isolation

Each domain (for example DSA, Biology, or any other subject) is tagged at ingestion time by prefixing the episode name, and the priority queue query filters strictly on that tag via a direct Cypher query against Neo4j rather than relying on semantic search. This keeps separate subjects from bleeding into each other's concept lists.

## Setup

### Prerequisites

You will need Python 3.11 or later, Neo4j (via Neo4j Desktop or Docker), and Ollama.

### Install dependencies

```
pip install -r requirements.txt
```

### Start Neo4j

Open Neo4j Desktop, create a local DBMS, set a password, and start it. Note the connection URI, which is typically `bolt://127.0.0.1:7687`.

### Start Ollama and pull models

```
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

### Configure environment variables

Create a `.env` file in the project root:

```
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=adaptive-study-agent
OPENAI_API_KEY=ollama
```

The `OPENAI_API_KEY` value is a placeholder required by the OpenAI-compatible client used to talk to Ollama; it is not a real API key.

## Running the system

### Terminal orchestrator

```
python -m agents.orchestrator
```

This runs a single study session end to end in the terminal, including question generation and answer evaluation through the local LLM.

### Streamlit interface

```
streamlit run app.py
```

This opens a browser-based interface with tabs for ingesting notes, running a study session, and viewing instructions for exploring the graph directly in Neo4j Browser.

### Claude Desktop via MCP

Add the following to your Claude Desktop configuration file, replacing the paths with your own project location:

```json
{
  "mcpServers": {
    "adaptive-study-agent": {
      "command": "/path/to/agenticenv/Scripts/python.exe",
      "args": ["/path/to/adaptive-study-agent/agents/mcp_server.py"],
      "cwd": "/path/to/adaptive-study-agent"
    }
  }
}
```

Restart Claude Desktop after saving. Once connected, you can ask Claude things like "What are my weakest concepts in DSA?" or "Ingest these notes into a domain called Biology," and Claude will call the underlying tools directly against your local knowledge graph.

## Observability

Every agent call made through the terminal orchestrator is traced in LangSmith, including the full state passed between nodes and the latency of each step. This is useful both for debugging the routing logic and for demonstrating exactly how the system makes decisions.

## Project structure

```
adaptive-study-agent/
  agents/
    ingestor.py        Entity and relationship extraction from raw text
    kg_manager.py       Confidence score updates and persistence
    quiz_teach.py        Priority scoring and routing logic
    llm_quiz.py          Question generation and answer evaluation
    orchestrator.py       LangGraph state machine tying agents together
    mcp_server.py        MCP server exposing tools to Claude Desktop
  graph/
    config.py            Graphiti and Neo4j client configuration
  utils/
    confidence_store.py    Persistent confidence score storage
  app.py                  Streamlit interface
  confidence_store.json     Local confidence score data
```

## Possible extensions

The current confidence store is a flat JSON file rather than a graph-native property, which was a deliberate simplification for development speed. A more complete version would store confidence directly as edge properties in Neo4j. The domain isolation approach using episode name tagging is functional but could be made more robust with dedicated namespace support if Graphiti adds it. Swapping the LLM backend from Ollama to a hosted API would also improve extraction quality and reduce latency during ingestion and question generation.
