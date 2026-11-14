"""
Shared text helpers. build_index.py and aunty_core.py both import this file,
so the index and the search always use exactly the same wording rules.
"""

import re
import hashlib

import config


def normalize_for_search(text):
    """In this bot, he / him / his and Shubh's nicknames all mean Shubh.
    Rewriting them to 'Shubh' lets 'is he married?' match 'is Shubh married?'."""
    text = re.sub(r"\bhis\b", "Shubh's", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(he|him|himself)\b", "Shubh", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(shubhu|shubhlu|shubhli|diku|shub)\b", "Shubh", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(green|red)\s*flag\b", r"\1 flag", text, flags=re.IGNORECASE)
    return text


def build_fingerprint():
    """Hash of the facts file, this file and the embedding model name.
    If any of them changes, the index must be rebuilt."""
    digest = hashlib.sha256()
    digest.update(config.EMBED_MODEL.encode("utf-8"))
    for path in (config.DATA_PATH, __file__):
        with open(path, "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()
