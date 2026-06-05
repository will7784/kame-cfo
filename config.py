import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _fix_postgres_url(url):
    """Railway a veces entrega postgres:// en vez de postgresql://"""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-cfo-2026"
    SQLALCHEMY_DATABASE_URI = _fix_postgres_url(os.environ.get("DATABASE_URL")) or "postgresql://postgres:postgres@localhost:5432/kame_cfo"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB upload max
