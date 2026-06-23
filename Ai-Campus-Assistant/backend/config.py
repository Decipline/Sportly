from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env()


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")


def supabase_enabled():
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def openai_enabled():
    return bool(get_openai_api_key())


def get_openai_api_key():
    return os.environ.get("OPENAI_API_KEY", "")


def get_openai_model():
    return os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")


def set_env_value(key: str, value: str):
    os.environ[key] = value
    lines = []
    found = False

    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    updated = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)

    if not found:
        updated.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")
