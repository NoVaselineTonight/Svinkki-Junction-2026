"""Check the Claude key the app would use, after switching it:  python -m deploy.check_key

It reads the key exactly as the app does (ANTHROPIC_API_KEY in the environment or .env, else the key file),
sends ONE tiny request (a few tokens, billed to that key) and prints whether it works, with which model, and
only the last four characters of the key. The key is never printed, logged or written anywhere.

Exit code 0: the key works. 1: no key is configured. 2: the key was refused or the model could not be reached.
`--no-call` only reports where the key comes from, without a request.
"""
import os
import sys


def describe(config):
    """(source, last four characters) of the key the app would use, or (None, None)."""
    key = config.claude_api_key()
    if not key:
        return None, None
    source = "ANTHROPIC_API_KEY" if config.claude_key_from_env() else "the key file (%s)" % os.path.basename(config.ai_key_file())
    return source, key[-4:]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import config, llm_claude
    source, last4 = describe(config)
    if not source:
        print("No Claude key is configured: set ANTHROPIC_API_KEY, or put the key on one line in %s."
              % os.path.basename(config.ai_key_file()))
        return 1
    model = config.claude_model()
    print("Key from %s, ending in ...%s. Model: %s." % (source, last4, model))
    if "--no-call" in argv:
        return 0
    try:
        answered = llm_claude.ping(config.claude_api_key(), model)
    except llm_claude.ClaudeError as e:
        print("The key did NOT work: %s." % " ".join(str(e).split())[:160])
        return 2
    print("The key works. Answered by %s." % answered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
