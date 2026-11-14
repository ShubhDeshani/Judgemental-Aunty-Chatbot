"""
Add indexed questions to a fact without editing the JSON by hand.

    python tools/add_questions.py praise_1 "Who is Shubh?" "Tell me about Shubh"

Safe to run twice (duplicates are skipped). Your other edits are kept.
Afterwards rebuild the index:  python build_index.py
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

parser = argparse.ArgumentParser(description="Add indexed questions to a fact.")
parser.add_argument("fact_id", help="for example: studies_1")
parser.add_argument("questions", nargs="+", help="one or more questions, each in quotes")
args = parser.parse_args()

with open(config.DATA_PATH, "r", encoding="utf-8") as f:
    facts = json.load(f)

target = next((fact for fact in facts if fact["id"] == args.fact_id), None)
if target is None:
    ids = ", ".join(fact["id"] for fact in facts)
    raise SystemExit(f"No fact with id '{args.fact_id}'. Available ids: {ids}")

existing = {q.lower().strip() for q in target["questions"]}
for question in args.questions:
    if question.lower().strip() in existing:
        print(f"skipped (already there): {question}")
        continue
    target["questions"].append(question)
    existing.add(question.lower().strip())
    print(f"added to {args.fact_id}: {question}")

with open(config.DATA_PATH, "w", encoding="utf-8") as f:
    f.write("[\n" + ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in facts) + "\n]\n")

print("Done. Now rebuild the index:  python build_index.py")
