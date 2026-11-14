"""
Builds the search index from data/aunty_facts.json.

Every fact becomes several vectors: one for the fact text and one for each
indexed question. All of them point back to the same fact_id, and the text
that comes back from a search is always the fact itself.

Run this every time data/aunty_facts.json or textutils.py changes.
It rebuilds from scratch, so the index can never drift out of sync.
"""

import json

import chromadb
from sentence_transformers import SentenceTransformer

import config
from textutils import normalize_for_search, build_fingerprint

with open(config.DATA_PATH, "r", encoding="utf-8") as f:
    facts = json.load(f)

model = SentenceTransformer(config.EMBED_MODEL)
client = chromadb.PersistentClient(path=str(config.DB_PATH))

try:
    client.delete_collection(config.COLLECTION_NAME)
except Exception:
    pass  # first run: nothing to delete
collection = client.create_collection(
    name=config.COLLECTION_NAME,
    metadata={"facts_hash": build_fingerprint()},
)

ids, documents, metadatas, variants = [], [], [], []
for fact in facts:
    seen = set()
    for n, variant in enumerate([fact["text"]] + fact.get("questions", [])):
        searchable = normalize_for_search(variant)  # he/him/his -> Shubh, same rule as the search
        key = searchable.lower().strip()
        if key in seen:
            continue  # two wordings that become identical add nothing
        seen.add(key)
        ids.append(f"{fact['id']}::{n}")
        documents.append(fact["text"])                       # what comes back is always the fact text
        metadatas.append({"fact_id": fact["id"], "category": fact["category"]})
        variants.append(searchable)                          # what gets embedded and searched

embeddings = model.encode(variants).tolist()
collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

print(f"Stored {collection.count()} vectors for {len(facts)} facts")
