"""
Does indexing questions help? Compares two ways of searching on the same test set:
  - "text only":        match the message against the fact text
  - "text + questions": also match it against each fact's indexed questions

    python evaluation/compare_indexing.py                (plain)
    python evaluation/compare_indexing.py --normalize    (he/him/his -> Shubh, as the bot does)

hit@1 = the right fact is first. hit@2 = the right fact is in the top two.
Test questions must NOT also appear in the index (the script warns if one does),
otherwise the score only measures memorisation.
"""

import json
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from textutils import normalize_for_search  # noqa: E402

NORMALIZE = "--normalize" in sys.argv


def prep(text):
    """Apply the bot's he/him/his rewrite when --normalize is given."""
    return normalize_for_search(text) if NORMALIZE else text


with open(config.DATA_PATH, 'r', encoding='utf-8') as f:
    facts = json.load(f)

ids = [fact['id'] for fact in facts]
texts = [fact['text'] for fact in facts]

# Flatten every indexed question and remember which fact owns it
q_texts, owners = [], []
for idx, fact in enumerate(facts):
    for q in fact['questions']:
        q_texts.append(q)
        owners.append(idx)

# (question, ids that SHOULD come back)
tests = [
    ("is shubh the topper of his school?", ["studies_1", "studies_2"]),
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
    # 6 more questions that are NOT in the index (they test generalisation)
    ("did shubh get good grades?", ["studies_1", "studies_2"]),
    ("does shubh lift weights or do bodyweight training?", ["gym_1", "gym_2", "gym_3"]),
    ("is shubh good with computers?", ["tech_1", "tech_2", "tech_3"]),
    ("what is shubh reading?", ["reading_1"]),
    ("would any company want shubh?", ["career_1"]),
    ("is shubh well dressed?", ["fashion_1", "fashion_2"]),
]

# Questions that use he / him / his. Run once plain and once with --normalize
# to see what the pronoun rewrite changes.
pronoun_tests = [
    ("does he write code?", ["tech_1", "tech_2", "tech_3"]),
    ("what did he score in the boards?", ["studies_1", "studies_2"]),
    ("what does he do at the gym?", ["gym_1", "gym_2", "gym_3"]),
    ("will his career go well?", ["career_1"]),
]


# Leak check: a test question that is also in the index would fake a good score
def clean(s):
    return s.lower().strip().rstrip('?').strip()


indexed = {clean(prep(q)) for q in q_texts}
for query, _ in tests + pronoun_tests:
    if clean(prep(query)) in indexed:
        print("WARNING - test question is also in the index (leak):", query)


def rank(query, model, doc_emb, q_emb, use_questions):
    query_emb = model.encode(prep(query))
    best = util.cos_sim(query_emb, doc_emb)[0].tolist()   # score of each fact text
    if use_questions:
        q_scores = util.cos_sim(query_emb, q_emb)[0].tolist()
        for owner, score in zip(owners, q_scores):
            best[owner] = max(best[owner], score)          # best of text OR any of its questions
    return sorted(zip(ids, best), key=lambda pair: pair[1], reverse=True)


def evaluate(model, doc_emb, q_emb, test_list, use_questions):
    hit1 = hit2 = 0
    notes = []
    for query, expected in test_list:
        top2 = [i for i, _ in rank(query, model, doc_emb, q_emb, use_questions)[:2]]
        hit1 += top2[0] in expected
        ok = any(i in expected for i in top2)
        hit2 += ok
        if not ok:
            notes.append(f"      MISS    | {query} -> {top2}")
        elif top2[0] not in expected:
            notes.append(f"      #2 ONLY | {query} -> {top2}")
    return hit1, hit2, notes


for name in ["all-MiniLM-L6-v2", "all-mpnet-base-v2"]:
    model = SentenceTransformer(name)
    doc_emb = model.encode([prep(t) for t in texts])
    q_emb = model.encode([prep(q) for q in q_texts])
    print(f"\n=== {name} === (normalize: {NORMALIZE})")
    for use_questions in (False, True):
        label = "text + questions" if use_questions else "text only      "
        for title, test_list in (("main", tests), ("pronoun", pronoun_tests)):
            hit1, hit2, notes = evaluate(model, doc_emb, q_emb, test_list, use_questions)
            print(f"{label} | {title:7} | hit@1: {hit1}/{len(test_list)} | hit@2: {hit2}/{len(test_list)}")
            for note in notes:
                print(note)
