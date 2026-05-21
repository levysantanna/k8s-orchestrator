import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# Database path configuration
db_path = Path(__file__).resolve().parents[1] / 'data' / 'orchestrator.db'
db_path.parent.mkdir(parents=True, exist_ok=True)
db_fallback = f'sqlite:///{db_path}'

# SQLite configuration for better concurrency
engine = create_engine(
    os.environ.get('DATABASE_URL', db_fallback),
    connect_args={
        'timeout': 30,
        'check_same_thread': False
    },
    pool_pre_ping=True,
    pool_recycle=3600
)

Session = sessionmaker(bind=engine)
Base = declarative_base()

def get_db_session():
    """Returns a new database session with SQLite PRAGMAs configured"""
    db_session = Session()
    try:
        # Configure SQLite for better concurrency handling
        db_session.execute(text("PRAGMA journal_mode=WAL"))
        db_session.execute(text("PRAGMA busy_timeout=5000"))
        return db_session
    except Exception as e:
        db_session.rollback()
        db_session.close()
        raise e
