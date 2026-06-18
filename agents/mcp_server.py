import os
import sys
sys.path.insert(0, "D:\\agents\\adaptive-study-agent")
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from agents.kgmanager import get_weakest_concepts, update_confidence
from agents.ingestor import ingest_text
from agents.quiz_teach import get_priority_queue, routing_decision
from utils.confidence_store import load as load_confidence
from agents.llm_quiz import generate_question

app = Server("adaptive-study-agent")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_weakest_concepts",
            description="Get the weakest concepts for a domain, sorted by priority score",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "e.g. DSA, ML, SQL"}
                },
                "required": ["domain"]
            }
        ),
        types.Tool(
            name="get_confidence_state",
            description="Get current confidence scores for all tracked concepts",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="ingest_notes",
            description="Ingest study notes into the knowledge graph",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "domain": {"type": "string"},
                    "source_name": {"type": "string"}
                },
                "required": ["content", "domain", "source_name"]
            }
        ),
        types.Tool(
            name="generate_question",
            description="Generate a study question for a concept",
            inputSchema={
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["teach", "guided_quiz", "cold_quiz"]
                    }
                },
                "required": ["concept", "mode"]
            }
        ),
        types.Tool(
            name="update_confidence",
            description="Update confidence score for a concept after a quiz answer",
            inputSchema={
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "correct": {"type": "boolean"}
                },
                "required": ["concept", "correct"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "get_weakest_concepts":
        queue = await get_priority_queue(arguments["domain"])
        result = [
            {
                "concept": c,
                "confidence": round(conf, 2),
                "priority_score": round(score, 4),
                "mode": routing_decision(conf)
            }
            for c, conf, score in queue
        ]
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_confidence_state":
        store_path = "D:\\agents\\adaptive-study-agent\\confidence_store.json"
        try:
            with open(store_path, "r") as f:
                store = json.load(f)
        except FileNotFoundError:
            store = {}
        print(f"Direct read from {store_path}: {store}", file=sys.stderr)
        return [types.TextContent(type="text", text=json.dumps(store, indent=2))]

    elif name == "ingest_notes":
        await ingest_text(
            content=arguments["content"],
            domain=arguments["domain"],
            source_name=arguments["source_name"]
        )
        return [types.TextContent(type="text", text=f"Ingested '{arguments['source_name']}' into {arguments['domain']}")]

    elif name == "generate_question":
        question = await generate_question(arguments["concept"], arguments["mode"])
        return [types.TextContent(type="text", text=question)]

    elif name == "update_confidence":
        await update_confidence(arguments["concept"], arguments["correct"])
        return [types.TextContent(type="text", text=f"Updated confidence for {arguments['concept']}")]

    return [types.TextContent(type="text", text="Unknown tool")]


async def main():
    print("MCP Server started, waiting for Claude to connect...", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())