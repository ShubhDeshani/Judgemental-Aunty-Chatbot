"""
All settings in one place. Nothing here needs a network or a model.
"""

from pathlib import Path

# Paths are built from this file's location, so every script works from any folder
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "aunty_facts.json"
DB_PATH = BASE_DIR / "chroma_db"
COLLECTION_NAME = "aunty_facts"

# Embedding model used for BOTH building the index and searching it
EMBED_MODEL = "all-MiniLM-L6-v2"

# Free OpenRouter models, tried in this order. Check openrouter.ai/models (filter: free)
# if one disappears - free models come and go.
MODELS = [
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "poolside/laguna-s-2.1:free",
]
MAX_TOKENS = 1500  # reasoning models spend tokens thinking before they answer

# Retrieval tuning. Distance = how far a fact is from the message (LOWER = CLOSER).
MAX_DISTANCE = 1.0  # never inject a fact farther than this
MARGIN = 0.15       # ...or more than this much worse than the closest fact overall
TOP_K = 1           # facts injected per message
