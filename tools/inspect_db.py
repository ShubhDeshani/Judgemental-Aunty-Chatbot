"""
Look inside the Chroma database: what is stored, and how many vectors each fact owns.

    python tools/inspect_db.py
"""

import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

client = chromadb.PersistentClient(path=str(config.DB_PATH))
collection = client.get_collection(name=config.COLLECTION_NAME)

print("Collection:", collection.name)
print("Collection metadata:", collection.metadata)
print("Total vectors stored:", collection.count())

data = collection.get(include=["documents", "metadatas", "embeddings"])

print("\n--- First 5 stored items (each one is id + embedding + document + metadata) ---")
for i in range(min(5, len(data["ids"]))):
    vector = data["embeddings"][i]
    print(f"id:        {data['ids'][i]}")
    print(f"metadata:  {data['metadatas'][i]}")
    print(f"document:  {data['documents'][i]}")
    print(f"embedding: {len(vector)} numbers, starting {[round(float(x), 3) for x in vector[:4]]}")
    print()

print("--- How many vectors each fact owns ---")
counts = {}
for meta in data["metadatas"]:
    counts[meta["fact_id"]] = counts.get(meta["fact_id"], 0) + 1
for fact_id, n in sorted(counts.items(), key=lambda pair: -pair[1]):
    print(f"{fact_id}: {n}")
