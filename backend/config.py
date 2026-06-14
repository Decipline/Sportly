from pathlib import Path
import os
import secrets


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def load_env():
    if not ENV_PATH.exists():
        print(f"Warning: .env file not found at {ENV_PATH}")
        return

    try:
        content = ENV_PATH.read_text(encoding="utf-8-sig")  # Use utf-8-sig to strip BOM
        print(f"Loading .env file from {ENV_PATH}")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().lstrip('\ufeff')  # Remove BOM if present
            os.environ[key] = value.strip()
            print(f"Loaded: {key}")
    except Exception as e:
        print(f"Warning: Could not load .env file: {e}")


load_env()


APP_PORT = int(os.environ.get("APP_PORT", "8000"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Email Configuration (for password reset)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@sportly.com")

# Database Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Session Configuration
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))

# Production Configuration
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")


def gemini_enabled():
    return bool(get_gemini_api_key())


def get_gemini_api_key():
    return os.environ.get("GEMINI_API_KEY", "")


def get_gemini_model():
    return os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


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
