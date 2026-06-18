import json
import os
import sys

STORE_PATH = r"D:\agents\adaptive-study-agent\confidence_store.json"

def load() -> dict:
    print(f"Reading from: {STORE_PATH}", file=sys.stderr)
    print(f"File exists: {os.path.exists(STORE_PATH)}", file=sys.stderr)
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH, "r") as f:
        return json.load(f)


def get(concept: str) -> float:
    return load().get(concept, 0.5)


def update(concept: str, correct: bool) -> tuple[float, float]:
    store = load()
    old = store.get(concept, 0.5)
    new = min(1.0, old + 0.15) if correct else max(0.0, old - 0.15)
    store[concept] = new
    with open(STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)
    return old, new