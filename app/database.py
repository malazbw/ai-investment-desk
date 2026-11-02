"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, StaticPool
from app.config import settings

# Use NullPool for development to avoid connection pooling issues
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        kwargs = {"echo": settings.debug}

        # SQLite uses StaticPool for in-memory databases
        if settings.database_url.startswith("sqlite://"):
            if ":memory:" in settings.database_url:
                kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        elif settings.debug:
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20

        _engine = create_engine(settings.database_url, **kwargs)
    return _engine


SessionLocal = None


def get_session_factory():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return SessionLocal


def get_db() -> Session:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()

