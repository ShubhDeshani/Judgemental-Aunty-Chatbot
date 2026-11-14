"""
Which embedding model finds the right fact? Runs four models on the same 12 questions,
matching each question against the fact TEXT only (no indexed questions).

    python evaluation/compare_models.py

The first run downloads about 700 MB of models, once.
hit@1 = the right fact is first. hit@2 = the right fact is in the top two.
"""

import json
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

with open(config.DATA_PATH, "r", encoding="utf-8") as f:
    facts = json.load(f)
ids = [fact["id"] for fact in facts]
texts = [fact["text"] for fact in facts]

# (question, ids that SHOULD come back)
tests = [
    ("is shubh a topper?", ["studies_1", "studies_2"]),
    ("what marks did shubh get in 10th?", ["studies_1", "studies_2"]),
    ("what books does shubh study from?", ["studies_3"]),
    ("does shubh read self-help books?", ["reading_1"]),
    ("is shubh athletic?", ["gym_1", "gym_2", "gym_3"]),
    ("can shubh do pushups?", ["gym_1"]),
    ("does shubh know how to code?", ["tech_1", "tech_2", "tech_3"]),
    ("has shubh built any projects?", ["tech_1", "tech_3"]),
    ("does shubh do machine learning?", ["tech_2"]),
    ("what does shubh wear?", ["fashion_1", "fashion_2"]),
    ("will shubh get a job?", ["career_1"]),
    ("is shubh ready to get married?", ["marriage_1"]),
]

# model name -> prefix that model expects in front of queries
models = {
    "all-MiniLM-L6-v2": "",
    "multi-qa-MiniLM-L6-cos-v1": "",
    "BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: ",
    "all-mpnet-base-v2": "",
}

for name, prefix in models.items():
    model = SentenceTransformer(name)
    doc_emb = model.encode(texts)
    hit1 = hit2 = 0
    print(f"\n=== {name} ===")
    for query, expected in tests:
        q_emb = model.encode(prefix + query)
        scores = util.cos_sim(q_emb, doc_emb)[0].tolist()
        ranked = sorted(zip(ids, scores), key=lambda pair: pair[1], reverse=True)
        top2 = [fact_id for fact_id, _ in ranked[:2]]
        hit1 += top2[0] in expected
        ok = any(fact_id in expected for fact_id in top2)
        hit2 += ok
        print(f"{'OK  ' if ok else 'MISS'} | {query} -> {top2}")
    print(f"hit@1: {hit1}/{len(tests)} | hit@2: {hit2}/{len(tests)}")
