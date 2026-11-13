"""Configuration: .env parser plus accessors read at call time (never frozen at import)."""
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "SVINKKI_DATA_DIR": "C:/Users/onnik/Desktop/Junction-2026-S-pankki-filtered",
    "SVINKKI_DB": "data/svinkki.db",
    "SVINKKI_STATE_DB": "data/state.db",
    "SVINKKI_TODAY": "2026-09-24",
    "SVINKKI_PORT": "8000",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
}


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
