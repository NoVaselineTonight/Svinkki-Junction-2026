"""Configuration: .env parser plus accessors read at call time (never frozen at import)."""
import json
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "SVINKKI_DATA_DIR": "dataset",
    "SVINKKI_DB": "data/svinkki.db",
    "SVINKKI_STATE_DB": "data/state.db",
    "SVINKKI_TODAY": "2026-09-26",
    "SVINKKI_PORT": "8000",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
    "ANTHROPIC_API_KEY": "",
    "CLAUDE_MODEL": "",
    "SVINKKI_AI_KEY_FILE": "claude_api_key.txt",
    "SVINKKI_AI_SETTINGS_FILE": "data/ai_settings.json",
}

# Claude models the demo Settings may choose between: (model id, label shown in Settings).
CLAUDE_MODELS = (
    ("claude-opus-5-5", "Claude Opus 5.5 (best answers)"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 (faster)"),
    ("claude-haiku-5-5", "Claude Haiku 5.5 (cheapest)"),
)
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
# The Settings choice is stored under this name. It was "claude_model" while the demo ran on the cheapest
# model; choices saved back then are not read any more, so the coach starts on the best model again.
_MODEL_SETTING = "claude_model_choice"
_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,300}")


def repo_root() -> str:
    return _ROOT


def _parse_env_file(path: str) -> dict:
    out = {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k.startswith("export "):
                    k = k[7:].strip()
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                out[k] = v
    except OSError:
        pass
    return out


def get(name: str) -> str:
    """Environment wins over .env, which wins over the default."""
    if os.environ.get(name, "") != "":
        return os.environ[name]
    # SVINKKI_ENV_FILE (environment only) points at another .env; the tests point it at nothing.
    file_vals = _parse_env_file(os.environ.get("SVINKKI_ENV_FILE") or os.path.join(_ROOT, ".env"))
    if file_vals.get(name, "") != "":
        return file_vals[name]
    return DEFAULTS.get(name, "")


def _resolve(p: str) -> str:
    p = os.path.expanduser(p)
    if not os.path.isabs(p):
        p = os.path.join(_ROOT, p)
    return os.path.normpath(p)


def data_dir() -> str:
    return _resolve(get("SVINKKI_DATA_DIR"))


def db_path() -> str:
    return _resolve(get("SVINKKI_DB"))


def state_db_path() -> str:
    return _resolve(get("SVINKKI_STATE_DB"))


def today() -> str:
    return get("SVINKKI_TODAY")


def port() -> int:
    try:
        return int(get("SVINKKI_PORT"))
    except ValueError:
        return 8000


def gemini_api_key() -> str:
    return get("GEMINI_API_KEY")


def gemini_model() -> str:
    return get("GEMINI_MODEL") or "gemini-3.5-flash-lite"


# --------------------------------------------------------------------------- Claude (SR-25)
# The key is read at call time from the environment (or .env), else from a git-ignored one-line
# file. It is never logged and never returned by any function except claude_api_key().

def ai_key_file() -> str:
    return _resolve(get("SVINKKI_AI_KEY_FILE") or "claude_api_key.txt")


def ai_settings_file() -> str:
    return _resolve(get("SVINKKI_AI_SETTINGS_FILE") or "data/ai_settings.json")


def claude_api_key() -> str:
    k = get("ANTHROPIC_API_KEY").strip()
    if k:
        return k
    try:
        with open(ai_key_file(), "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except (OSError, UnicodeError):
        pass
    return ""


def claude_key_from_env() -> bool:
    """True when the key comes from the environment or .env, so the key file is not what is in use."""
    return bool(get("ANTHROPIC_API_KEY").strip())


def valid_claude_key(key) -> bool:
    return isinstance(key, str) and bool(_KEY_RE.fullmatch(key))


def set_claude_api_key(key: str) -> None:
    """Write the key to the git-ignored key file (owner-only where the system supports it)."""
    if not valid_claude_key(key):
        raise ValueError("invalid key")
    path = ai_key_file()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Written in place: a temporary copy next to it would not be covered by .gitignore.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _ai_settings() -> dict:
    try:
        with open(ai_settings_file(), "r", encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def claude_model() -> str:
    """The model chosen in the demo Settings, else CLAUDE_MODEL, else the default."""
    ids = [m for m, _ in CLAUDE_MODELS]
    saved = _ai_settings().get(_MODEL_SETTING)
    if saved in ids:
        return saved
    env = get("CLAUDE_MODEL").strip()
    return env if env in ids else DEFAULT_CLAUDE_MODEL


def set_claude_model(model: str) -> None:
    if model not in [m for m, _ in CLAUDE_MODELS]:
        raise ValueError("unknown model")
    path = ai_settings_file()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = _ai_settings()
    data[_MODEL_SETTING] = model
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def ai_provider() -> str:
    """"claude" when a Claude key exists, else "gemini" when a Gemini key exists, else "" (built-in rules)."""
    if claude_api_key():
        return "claude"
    if gemini_api_key():
        return "gemini"
    return ""
