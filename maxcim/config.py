"""Environment-based configuration with safe demonstration defaults."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent


def env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def database_uri() -> str:
    uri = os.getenv("DATABASE_URL", "").strip()
    if not uri:
        return f"sqlite:///{(BASE_DIR / 'instance' / 'maxcim_demo.db').as_posix()}"
    if uri.startswith("mysql://"):
        return uri.replace("mysql://", "mysql+pymysql://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SECRET_KEY_EPHEMERAL = not bool(os.getenv("SECRET_KEY"))
    SQLALCHEMY_DATABASE_URI = database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    DEMO_MODE = env_flag("DEMO_MODE", not bool(os.getenv("GOOGLE_API_KEY")))
    DEMO_EMAIL = os.getenv("DEMO_EMAIL", "docente@maxcim.demo")
    DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "MaxcimDemo2026!")
    SEED_DEMO_DATA = env_flag("SEED_DEMO_DATA", DEMO_MODE)
    AUTO_CREATE_DB = env_flag("AUTO_CREATE_DB", True)

    AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "demo").strip().lower()
    CIMA_API_BASE_URL = os.getenv(
        "CIMA_API_BASE_URL", "https://apicima.colegiocima.edu.pe:8086"
    ).strip()
    CIMA_API_SYSTEM_ID = env_int("CIMA_API_SYSTEM_ID", 21)
    CIMA_API_IDENTIFIER = os.getenv("CIMA_API_IDENTIFIER", "").strip()
    CIMA_API_TEACHER_ID_CLAIM = os.getenv("CIMA_API_TEACHER_ID_CLAIM", "").strip()
    CIMA_API_USER_LOGIN_PATH = os.getenv(
        "CIMA_API_USER_LOGIN_PATH", "/api/v2/authentication/with/user"
    ).strip()
    CIMA_API_EMAIL_LOGIN_PATH = os.getenv(
        "CIMA_API_EMAIL_LOGIN_PATH", "/api/v2/authentication/with/email"
    ).strip()
    CIMA_API_CLASSROOMS_PATH = os.getenv(
        "CIMA_API_CLASSROOMS_PATH", "/api/v2/gradesection/list/group/user/{teacher_id}"
    ).strip()
    CIMA_API_STUDENTS_PATH = os.getenv(
        "CIMA_API_STUDENTS_PATH",
        "/api/v2/studentschool/list/gradesectiongroup/{classroom_id}"
        "/type/{classroom_type}/order/{order}",
    ).strip()
    CIMA_API_TIMEOUT_SECONDS = env_float("CIMA_API_TIMEOUT_SECONDS", 8.0)
    CIMA_API_VERIFY_TLS = env_flag("CIMA_API_VERIFY_TLS", True)
    CIMA_API_SESSION_MAX_AGE_SECONDS = env_int("CIMA_API_SESSION_MAX_AGE_SECONDS", 28_800)
    CIMA_TOKEN_ENCRYPTION_KEY = os.getenv("CIMA_TOKEN_ENCRYPTION_KEY", "").strip()
    CIMA_ALLOW_INSECURE_LOCAL_COOKIES = env_flag("CIMA_ALLOW_INSECURE_LOCAL_COOKIES", False)

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
    GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Puck")
    DISPLAY_TIMEZONE = os.getenv("DISPLAY_TIMEZONE", "America/Lima")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    MAX_TEXT_CHARS = 30_000
    MAX_QUESTIONS_PER_TYPE = 15
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))
    ALLOWED_DOCUMENT_EXTENSIONS = {".txt", ".pdf", ".docx"}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_flag("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_TIME_LIMIT = 8 * 60 * 60

    RATELIMIT_ENABLED = env_flag("RATELIMIT_ENABLED", True)
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
