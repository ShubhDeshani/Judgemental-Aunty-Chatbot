# Judgemental Aunty Chatbot

A personalized self-made chatbot made for roasting any type messages sent by users while praising/bragging about her creator - Shubh. The facts about shubh are stored in a vector database. the retrieval pipeline(RAG) selects relevant facts about shubh. The LLM layer finishes the job my replying the user with an awfully funny roast and using the retrieved fact to praise shubh.

I started this as a simple project with just an LLM layer and a system prompt to maintain aunty ji's character. Then i learnt about RAG chatbots and found it extremely interesting! and decided to add it in this project though it was not needed for a small project like this. 

I added the RAG pipeline to learnt about how RAGchatbots work and for future use of this knowledge to create crazier projects.

READ BELOW TO SEE HOW THE RAG PIPELINE WORKS. IT KEEPS GETTING INTERESTING
## Sample

`chat.py` is the clean chat:

```
You: how much did shubh score

Aunty: Arre beta, you ask how much diku scored? He smashed a glittering 93% in his 10th grade
ICSE, while you're probably still debating whether to open a book. Tauba tauba, what pathetic
excuse will you give when everyone talks about his stellar result?
```

`monitor.py` is the same bot with the retrieval decisions printed under every reply (example output):

```
You: how much did shubh score
   [debug] searched for: how much did shubh score
   [debug] closest facts: [('studies_1', 0.504), ('studies_2', 0.591), ('praise_1', 0.621)]
   [debug] injecting studies_1 (distance 0.504, limit 0.654)
   [debug] model used: cohere/north-mini-code:free | finish_reason: stop | reply is empty: False
```

When nothing relevant is left, she falls back to a generic roast:

```
You: but he is a narcissist afterall
   [debug] closest facts: [('marriage_1', 1.397), ('studies_2', 1.452), ('fashion_2', 1.463)]
   [debug] nothing close enough (limit 1.000) -> generic roast
```

## How it works

```
 your message
     |  normalise: he / him / his / nicknames -> "Shubh"
     v
 embed with all-MiniLM-L6-v2
     v
 Chroma: nearest vectors (fact text + indexed questions)
     v
 keep each fact's closest vector -> rank -> relevance gate -> "once per session" filter
     v
 persona prompt + ONE fact (or none)  ->  LLM via OpenRouter (free models)  ->  reply
```

- **The facts** live in `data/aunty_facts.json`. Each fact has an `id`, a `category`, the `text`, and a list of `questions` people might ask about it.
- **The index** (`build_index.py`) stores one vector for the fact text and one for every indexed question. All of them point back to the same fact, and the text returned from a search is always the fact itself. This is the same idea as the multi-vector / hypothetical-question retrieval used in larger RAG systems.
- **The relevance gate** only injects a fact if it is close enough (`MAX_DISTANCE`) and not much worse than the best match overall (`MARGIN`). Otherwise the aunty gives a generic roast instead of dragging in an unrelated fact.
- **Once per session**: a fact is told at most once per run, then the aunty moves on to generic roasts.
- **Stale-index guard**: the index stores a fingerprint of the facts file, the search rules and the embedding model. If any of them changes, the bot refuses to start until you rebuild.

## Two ways to run it

| File | What it is |
|---|---|
| `chat.py` | Clean chat. No debug output. |
| `monitor.py` | Same aunty, plus every retrieval decision printed under her reply. Use it to see why she said what she said. |

Both use the same engine (`aunty_core.py`); the only difference is `debug=False` or `debug=True`.

## Quick start

You need Python 3 and a free [OpenRouter](https://openrouter.ai) API key.

```powershell
git clone https://github.com/ShubhDeshani/judgemental-padosi-aunty.git
cd judgemental-padosi-aunty
python -m venv venv
venv\Scripts\Activate.ps1          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # macOS/Linux: cp .env.example .env
notepad .env                       # paste your OPENROUTER_API_KEY, save
python build_index.py              # builds the search index (first run downloads the embedding model)
python chat.py                     # or: python monitor.py
```

Run `python build_index.py` again whenever you edit `data/aunty_facts.json` or `textutils.py`.

## Make it your own

- Change the facts: edit `data/aunty_facts.json`, then rebuild the index.
- Add questions to a fact without touching the JSON by hand:
  `python tools/add_questions.py studies_1 "Is he good at maths?"`
- Change her personality: edit `persona.py`.
- Change models and thresholds: edit `config.py`.
- Look inside the database: `python tools/inspect_db.py`

## Project structure

```
.
|-- chat.py                  clean chat interface
|-- monitor.py               chat + retrieval monitor
|-- aunty_core.py            the engine: retrieve, gate, prompt, call the LLM
|-- build_index.py           builds the Chroma index from the facts file
|-- persona.py               the aunty's system prompt
|-- config.py                paths, models, thresholds
|-- textutils.py             query normalisation + index fingerprint
|-- data/
|   `-- aunty_facts.json     the facts and their indexed questions
|-- tools/
|   |-- add_questions.py     add indexed questions from the command line
|   `-- inspect_db.py        see what is stored in Chroma
`-- evaluation/
    |-- compare_models.py    4 embedding models on the same questions
    `-- compare_indexing.py  does indexing questions help?
```

## What I measured

Both evaluations use hand-written questions with the fact(s) that should come back. **hit@1** = the right fact is first, **hit@2** = it is in the top two. These are small test sets (one question is about 5%), so read them as directional, not as benchmarks.

**1. Which embedding model? (12 questions, matching against fact text only)**

| Model | hit@1 | hit@2 |
|---|---|---|
| all-MiniLM-L6-v2 | 10/12 | 10/12 |
| multi-qa-MiniLM-L6-cos-v1 | 7/12 | 9/12 |
| BAAI/bge-small-en-v1.5 | 9/12 | 9/12 |
| all-mpnet-base-v2 | 9/12 | 11/12 |

No model fixed the two questions that all four failed ("is shubh a topper?" and "has shubh built any projects?"), so the choice of model was not the main problem. I kept `all-MiniLM-L6-v2`: it had the best top-1 score and is roughly five times smaller than mpnet.

**2. Does indexing questions help? (18 questions, 6 of them never indexed)**

| Model | text only (hit@1 / hit@2) | text + questions (hit@1 / hit@2) |
|---|---|---|
| all-MiniLM-L6-v2 | 17/18 / 17/18 | 17/18 / **18/18** |
| all-mpnet-base-v2 | 14/18 / 16/18 | 16/18 / **18/18** |

These runs were made before the he/him/his rewrite existed. To measure the rewrite on the current data, run `python evaluation/compare_indexing.py` and then `python evaluation/compare_indexing.py --normalize`; the second run adds the rewrite and also reports a separate group of pronoun questions.

## What I learned

- **Embeddings measure similarity, not reasoning.** "93% in boards" and "topper" mean the same to a person, but a small model does not connect them. Indexing the questions people actually ask fixed it better than switching models.
- **A stale index causes most "retrieval bugs".** The same question went from distance 1.04 to 0.105 just by rebuilding. The fix was in code: the bot now refuses to start on a stale index.
- **Short messages are brittle.** "is he a greenflag?" missed an indexed "is shubh a green flag" until pronouns and compound words were normalised on both sides.
- **A relevance cutoff matters as much as ranking.** Without one, the bot injected random facts for chit-chat. Cutoffs were calibrated from logged distances: right facts at 0.1 to 0.95, no-match messages at 1.13 and above.
- **The LLM layer needs engineering too.** An unpinned model router answered with a safety-classifier model once, and reasoning models ran out of tokens before replying. Models are now pinned and given token headroom.
- **At this size, retrieval is overkill.** 15 facts fit comfortably in a prompt, and an LLM reading them all would handle questions like "topper" without help. I built the retrieval layer to learn it and measured where it does and does not work; a project whose data does not fit in a prompt is the right next use of it.

## Limitations

- The embedding model is English-only. Hinglish questions work when they resemble indexed phrasings; how well it generalises to unseen Hinglish has not been measured yet.
- The test sets are small and written by the author.
- OpenRouter's free models are rate limited (at the time of writing, 50 requests per day on free accounts), so a public deployment on the free tier would run out quickly.
- Different free models write in slightly different styles, so the aunty's voice varies a little between replies.

## Roadmap

- A web interface (React frontend, small Python API) with the API key kept on the server.
- A Hinglish test set, and a comparison against a multilingual embedding model.
- A second RAG project over data that does not fit in a prompt.

## Built with

Python, [ChromaDB](https://www.trychroma.com), [sentence-transformers](https://www.sbert.net), [OpenRouter](https://openrouter.ai) and the `openai` Python client. Built as a learning project, with Claude (Anthropic) used as a tutor and pair-programmer.

Related project: [habit-tracker](https://github.com/ShubhDeshani/habit-tracker), the Python habit tracker the aunty brags about.
