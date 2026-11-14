"""
Chat with the Judgemental Padosi Aunty. Clean interface, no debug output.

    python chat.py

(Want to see how retrieval decides what to say? Run monitor.py instead.)
"""

import os

# Keep the terminal quiet: hide library progress bars and warnings
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from aunty_core import AuntyBot  # noqa: E402  (must come after the settings above)


def main():
    print("\nWaking the aunty up...")
    bot = AuntyBot(debug=False)
    print("\n=== Judgemental Padosi Aunty ===")
    print("Say something. Type 'quit' to leave.\n")

    while True:
        try:
            message = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if message.lower() in {"quit", "exit"}:
            break
        if not message:
            continue
        print(f"\nAunty: {bot.reply(message)}\n")

    print("Aunty: Going already? Tauba tauba. Shubh never leaves a conversation early.")


if __name__ == "__main__":
    main()
