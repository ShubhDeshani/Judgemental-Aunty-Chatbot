"""
The engine behind both chat.py and monitor.py.

    message -> normalise -> embed -> find the closest fact in Chroma
            -> relevance gate + once-per-session filter
            -> persona prompt (+ one fact, or none) -> LLM -> reply

chat.py runs this silently. monitor.py runs it with debug=True so every
retrieval decision is printed.
"""

import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer

import config
import persona
from textutils import normalize_for_search, build_fingerprint


class AuntyBot:
    def __init__(self, debug=False):
        self.debug = debug
        self.used_ids = set()  # facts already told in this session

        load_dotenv(config.BASE_DIR / ".env")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise SystemExit(
                "OPENROUTER_API_KEY not found.\n"
                "Copy .env.example to .env and paste your key into it."
            )
        self.llm = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

        self.embedder = SentenceTransformer(config.EMBED_MODEL)
        chroma = chromadb.PersistentClient(path=str(config.DB_PATH))
        try:
            self.collection = chroma.get_collection(name=config.COLLECTION_NAME)
        except Exception:
            raise SystemExit("No search index found. Build it first:  python build_index.py")

        # Refuse to run on a stale index
        if (self.collection.metadata or {}).get("facts_hash") != build_fingerprint():
            raise SystemExit(
                "\nSTOP: the search index does not match data/aunty_facts.json "
                "(or the search rules changed).\n"
                "Rebuild it first:  python build_index.py\n"
            )
        self._log(f"Database OK: {self.collection.count()} vectors, in sync with the facts file")

    def _log(self, message):
        if self.debug:
            print(f"   [debug] {message}")

    def find_fact(self, message):
        """Return the fact text to inject, or None if nothing relevant is left."""
        searched = normalize_for_search(message)  # he/him/his -> Shubh
        self._log(f"searched for: {searched}")
        query_embedding = self.embedder.encode(searched).tolist()

        # The index is tiny, so ask for every vector and rank the facts ourselves
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=self.collection.count(),
        )

        # Several vectors belong to one fact: keep each fact's closest vector
        best = {}  # fact_id -> (distance, fact text)
        for meta, doc, dist in zip(results["metadatas"][0], results["documents"][0], results["distances"][0]):
            fact_id = meta["fact_id"]
            if fact_id not in best or dist < best[fact_id][0]:
                best[fact_id] = (dist, doc)

        ranked = sorted(best.items(), key=lambda item: item[1][0])  # closest first
        if not ranked:
            return None
        self._log("closest facts: " + str([(fid, round(d, 3)) for fid, (d, _) in ranked[:3]]))

        # A fact must be close in absolute terms AND not much worse than the best match.
        # This stops "the right fact is used up, so here is a random leftover".
        closest = ranked[0][1][0]
        limit = min(config.MAX_DISTANCE, closest + config.MARGIN)
        fresh = [
            (fact_id, dist, doc)
            for fact_id, (dist, doc) in ranked
            if fact_id not in self.used_ids and dist <= limit
        ]
        selected = fresh[: config.TOP_K]

        if not selected:
            self._log(f"nothing close enough (limit {limit:.3f}) -> generic roast")
            return None

        fact_id, dist, doc = selected[0]
        self.used_ids.add(fact_id)
        self._log(f"injecting {fact_id} (distance {dist:.3f}, limit {limit:.3f})")
        return doc

    def reply(self, message):
        fact = self.find_fact(message)
        try:
            response = self.llm.chat.completions.create(
                model=config.MODELS[0],
                extra_body={"models": config.MODELS},
                max_tokens=config.MAX_TOKENS,
                messages=[
                    {"role": "system", "content": persona.build_prompt(fact)},
                    {"role": "user", "content": message},
                ],
            )
        except Exception as error:
            self._log(f"API error: {error}")
            return persona.SLEEPING_MESSAGE

        if not response.choices:
            self._log("the model returned no choices")
            return persona.SLEEPING_MESSAGE

        choice = response.choices[0]
        content = choice.message.content
        self._log(
            f"model used: {getattr(response, 'model', '?')} | "
            f"finish_reason: {choice.finish_reason} | reply is empty: {not content}"
        )
        return content if content else persona.SLEEPING_MESSAGE
