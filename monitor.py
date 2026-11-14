"""
Same aunty as chat.py, but every retrieval decision is printed under her reply:

    python monitor.py

For each message you will see:
  - what was actually searched (after he/him/his -> Shubh)
  - the three closest facts and their distances (lower = closer)
  - which fact was injected, or why none was
  - which LLM answered and why it stopped
"""

from aunty_core import AuntyBot


def main():
    print("\nAunty monitor - loading...")
    bot = AuntyBot(debug=True)
    print("\n=== Judgemental Padosi Aunty (monitor mode) ===")
    print("Type 'quit' to leave.\n")

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
        reply = bot.reply(message)  # the debug lines print while this runs
        print(f"\nAunty: {reply}\n")


if __name__ == "__main__":
    main()
