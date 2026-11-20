import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def _resolve_database_uri() -> str:
    # Check for cloud database URLs (Supabase, Neon, Neon Postgres, Vercel Postgres, Railway, MySQL, TiDB, Aiven)
    # Default to user's TiDB Cloud cluster so serverless deployments never drop to ephemeral /tmp SQLite
    default_cloud_db = "mysql://vPvpLzbHA5TNLVn.root:oECiHgv0WR6AY2KW@gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/jobsnap"
    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_PRISMA_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
        or os.getenv("MYSQL_URL")
        or default_cloud_db
    )
    if db_url:
        # TiDB / MySQL internal schema guard: 'sys' is restricted from user table creation
        if "/sys" in db_url and ("tidbcloud.com" in db_url or "mysql" in db_url):
            db_url = db_url.replace("/sys", "/jobsnap", 1)

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
                    db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

        # MySQL driver normalization (use pure-Python PyMySQL)
        if db_url.startswith("mysql://") and not db_url.startswith("mysql+"):
            db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

        return db_url

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

    # Resilient connection pooling for serverless and cloud MySQL / TiDB / Postgres
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_timeout": 20,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # Session cookie hardening across deployments and redirects
    SESSION_COOKIE_NAME = "jobsnap_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400 * 30  # 30 days
    REMEMBER_COOKIE_DURATION = 86400 * 30    # 30 days
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Upload folder: /tmp/uploads on Vercel, ./uploads locally
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/uploads" if IS_VERCEL else os.path.join(BASE_DIR, "uploads"))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit

    # Enable heavy transformers only if explicitly configured (Sentence-BERT vs TF-IDF)
    ENABLE_HEAVY_TRANSFORMERS = os.getenv("ENABLE_HEAVY_TRANSFORMERS", "false").lower() in ("true", "1")
