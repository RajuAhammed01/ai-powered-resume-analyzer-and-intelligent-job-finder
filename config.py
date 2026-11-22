import os
import pathlib
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

# Dedicated production Supabase database pooler URL fallback for Vercel serverless deployments
DEFAULT_SUPABASE_DATABASE_URL = (
    "postgresql://postgres.oihepjwiogxmpoxsdhti:CK%26L%2CP%2C-2%2F9UenN"
    "@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres?pgbouncer=true"
)


def _resolve_database_uri() -> str:
    # Resolve PostgreSQL database URL from environment variables or fallback to dedicated Supabase database
    # (e.g. DATABASE_URL, DIRECT_URL, POSTGRES_URL in .env or Vercel Environment Variables)
    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DIRECT_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_PRISMA_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
        or DEFAULT_SUPABASE_DATABASE_URL
    )
    if db_url and "[YOUR-PASSWORD]" not in db_url:
        # SQLAlchemy 1.4+ / 2.0+ requires postgresql:// instead of postgres://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
            try:
                import psycopg  # noqa: F401
            except ImportError:
                try:
                    import psycopg2  # noqa: F401
                except ImportError:
                    # Pure-Python pg8000 ensures seamless serverless & cross-platform support
                    # Note: pg8000.connect() does not accept pgbouncer query parameter
                    db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)
                    db_url = db_url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

        # In production/Vercel, always use the configured cloud database URL
        if IS_VERCEL:
            return db_url

        # In local development, verify that the remote cloud database is reachable and authenticated.
        # If credentials fail (e.g. invalid password), fall back to local SQLite so registration,
        # login, and application features run seamlessly without 500 ProgrammingError crashes.
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.pool import NullPool
            test_engine = create_engine(db_url, poolclass=NullPool, connect_args={"timeout": 3})
            with test_engine.connect() as test_conn:
                test_conn.execute(text("SELECT 1"))
            return db_url
        except Exception as e:
            print(f"[*] Notice: Remote database not authenticated ({type(e).__name__}). Using local SQLite database.", flush=True)

    # Serverless fallback (Vercel filesystem is read-only except /tmp)
    if IS_VERCEL:
        return "sqlite:////tmp/database.db"

    # Local development SQLite
    instance_path = os.path.join(BASE_DIR, "instance")
    try:
        os.makedirs(instance_path, exist_ok=True)
    except Exception:
        pass
    return f"sqlite:///{os.path.join(instance_path, 'database.db')}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "jobsnap-dev-production-secret-key-2026")
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True

    # Configure connection options:
    # NullPool is required on Vercel and with PgBouncer transaction mode (port 6543)
    # to avoid double-pooling and connection exhaustion on Supabase.
    is_pgbouncer = "6543" in SQLALCHEMY_DATABASE_URI or "pgbouncer=true" in SQLALCHEMY_DATABASE_URI
    if IS_VERCEL or is_pgbouncer:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": NullPool,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "pool_timeout": 20,
            "pool_size": 10,
            "max_overflow": 20,
        }

    # Dynamic secure cookie setting:
    # On Vercel (HTTPS) or production, cookies MUST have Secure=True so modern browsers
    # (and Public Suffix List rules for vercel.app) accept and persist them across redirects.
    # On local HTTP (127.0.0.1), Secure remains False.
    COOKIE_SECURE = IS_VERCEL or os.getenv("FLASK_ENV") == "production" or os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1")

    # Session cookie hardening across deployments and redirects
    SESSION_COOKIE_NAME = "jobsnap_session"
    SESSION_COOKIE_PATH = "/"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = 86400 * 30  # 30 days

    # Prevent CSRF referer check failures behind Vercel edge proxies while keeping CSRF token verification active
    WTF_CSRF_SSL_STRICT = False

    # Remember Me cookie hardening
    REMEMBER_COOKIE_NAME = "jobsnap_remember"
    REMEMBER_COOKIE_PATH = "/"
    REMEMBER_COOKIE_DURATION = 86400 * 30    # 30 days
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = COOKIE_SECURE

    # Upload folder: /tmp/uploads on Vercel, ./uploads locally
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads" if IS_VERCEL else os.path.join(BASE_DIR, "uploads"))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit

    # Enable heavy transformers only if explicitly configured (Sentence-BERT vs TF-IDF)
    ENABLE_HEAVY_TRANSFORMERS = os.getenv("ENABLE_HEAVY_TRANSFORMERS", "false").lower() in ("true", "1")
