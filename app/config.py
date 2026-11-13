"""Configuration: .env parser plus accessors read at call time (never frozen at import)."""
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "SVINKKI_DATA_DIR": "C:/Users/onnik/Desktop/Junction-2026-S-pankki-filtered",
    "SVINKKI_DB": "data/svinkki.db",
    "SVINKKI_STATE_DB": "data/state.db",
    "SVINKKI_TODAY": "2026-09-26",
    "SVINKKI_PORT": "8000",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
    "CLAUDE_MODEL": "claude-opus-5-5",
    "SVINKKI_AI_KEY_FILE": "claude_api_key.txt",
    "SVINKKI_AI_SETTINGS": "data/ai_settings.json",
}

CLAUDE_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


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
    file_vals = _parse_env_file(os.path.join(_ROOT, ".env"))
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


# ---------------------------------------------------------------- Claude (AI model) settings
# The key is only ever read here and handed to the HTTP client header. Never log or print it.

def claude_key_file() -> str:
    return _resolve(get("SVINKKI_AI_KEY_FILE") or "claude_api_key.txt")


def ai_settings_path() -> str:
    return _resolve(get("SVINKKI_AI_SETTINGS") or "data/ai_settings.json")


def claude_api_key() -> str:
    """Env ANTHROPIC_API_KEY when defined (even empty: then no key), else the key file's first line."""
    if "ANTHROPIC_API_KEY" in os.environ:
        return os.environ["ANTHROPIC_API_KEY"].strip()
    env_val = _parse_env_file(os.path.join(_ROOT, ".env")).get("ANTHROPIC_API_KEY", "")
    if env_val.strip():
        return env_val.strip()
    try:
        with open(claude_key_file(), "r", encoding="utf-8-sig") as f:
            return f.readline().strip()
    except OSError:
        return ""


def _read_ai_settings() -> dict:
    import json
    try:
        with open(ai_settings_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _atomic_write(path: str, text: str) -> None:
    import tempfile
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def claude_model() -> str:
    m = _read_ai_settings().get("model")
    if isinstance(m, str) and m in CLAUDE_MODELS:
        return m
    return get("CLAUDE_MODEL") or "claude-opus-5-5"


def set_claude_model(model: str) -> None:
    import json
    if model not in CLAUDE_MODELS:
        raise ValueError("unknown model")
    d = _read_ai_settings()
    d["model"] = model
    _atomic_write(ai_settings_path(), json.dumps(d))


def set_claude_key(key: str) -> None:
    if not isinstance(key, str) or not key.strip() or any(c.isspace() for c in key.strip()):
        raise ValueError("invalid key")
    _atomic_write(claude_key_file(), key.strip() + chr(10))


def clear_claude_key() -> None:
    try:
        os.remove(claude_key_file())
    except OSError:
        pass


def ai_provider() -> str:
    if claude_api_key():
        return "claude"
    if gemini_api_key():
        return "gemini"
    return "none"
